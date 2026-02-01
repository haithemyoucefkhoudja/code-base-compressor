from typing import List, Tuple, Dict, Set
from tree_sitter import Node
from ..models import CallUsage, JSXUsage, ComponentDefinition, TypeDefinition, ReferenceUsage, ConstantDefinition
from ..core.languages import get_parser
from ..core.node_utils import get_full_chain, get_jsx_name, get_jsx_props
from .imports import extract_js_imports

global_definitions: Dict[str, str] = {}

def findImportSource(extracted_imports_dict: Dict[str, List[str]], target_text: str) -> str:
    try:
        if "." in target_text:
            target_text = target_text.split(".")[0]
        for import_name, items in extracted_imports_dict.items():
            for item in items:
                raw_symbol = None
                # Safe checking for prefixes
                if "PART:" in item:
                    
                    parts = item.split("PART:")
                    if len(parts) > 1: raw_symbol = parts[1]
                elif "NAMESPACE:" in item:
                    parts = item.split("NAMESPACE:")
                    if len(parts) > 1: raw_symbol = parts[1]
                elif "DEFAULT:" in item:
                    parts = item.split("DEFAULT:")
                    if len(parts) > 1: raw_symbol = parts[1]
                
                if raw_symbol:
                    # Logic to handle 'import { original as alias }'
                    if " as " in raw_symbol:
                        actual_used_name = raw_symbol.split(" as ")[1].strip()
                    else:
                        actual_used_name = raw_symbol.strip()
                    if actual_used_name == target_text:
                        return import_name
                    
        return "Declaration"
    except Exception as e:
        print(f"Error finding import source: {e}")
        return "Declaration"

def extract_component_props(node: Node, source: bytes) -> List[str]:
    """Extract prop names from a component definition (function/arrow parameters)."""
    params_node = node.child_by_field_name("parameters")
    if not params_node:
        return []
    
    # Props is usually the first parameter (ignore symbols)
    actual_params = [c for c in params_node.children if c.type not in ("(", ")", ",", "type_annotation")]
    if not actual_params:
        return []
        
    first_param = actual_params[0]

    def extract_from_pattern(p_node: Node) -> List[str]:
        found = []
        if p_node.type in ("identifier", "shorthand_property_identifier_pattern"):
            found.append(source[p_node.start_byte:p_node.end_byte].decode('utf-8'))
        elif p_node.type == "object_pattern":
            for child in p_node.children:
                if child.type == "shorthand_property_identifier_pattern":
                    found.append(source[child.start_byte:child.end_byte].decode('utf-8'))
                elif child.type == "pair_pattern":
                    # key is usually the first child or have 'key' field
                    key = child.child_by_field_name("key")
                    if not key and child.children: key = child.children[0]
                    if key: found.append(source[key.start_byte:key.end_byte].decode('utf-8'))
                elif child.type == "object_assignment_pattern":
                    # first child is the pattern
                    if child.children: found.extend(extract_from_pattern(child.children[0]))
                elif child.type == "rest_pattern":
                    for c in child.children:
                        if c.type == "identifier":
                            found.append(source[c.start_byte:c.end_byte].decode('utf-8'))
        elif p_node.type in ("required_parameter", "optional_parameter", "parameter"):
            # Recurse into children to find pattern
            for child in p_node.children:
                if child.type in ("identifier", "object_pattern", "shorthand_property_identifier_pattern", "pair_pattern", "object_assignment_pattern", "rest_pattern"):
                    found.extend(extract_from_pattern(child))
                    break # Usually only one pattern per parameter
        return found

    return extract_from_pattern(first_param)

def extract_usages(file_path: str, source_code: bytes) -> Tuple[List[CallUsage], List[JSXUsage], List[ComponentDefinition], List[TypeDefinition], List[ConstantDefinition], List[ReferenceUsage]]:
    """Extract all call, JSX, and structural usages from a file."""
    parser = get_parser(file_path)
    source = source_code
    
    tree = parser.parse(source)
    calls = []
    jsxs = []
    component_defs = []
    type_defs = []
    constant_defs = []
    references: Set[ReferenceUsage] = set()

    extracted_imports_dict = extract_js_imports(source.decode('utf-8', errors='replace'))
    for key, value in extracted_imports_dict.items():
        for item in value:
            references.add(ReferenceUsage(name=item, source_import=key))
    
    def walk(node: Node, context: List[str] = []):
        current_context = context[:]
        
        # 1. Calls & New Expressions
        if node.type in ("call_expression", "new_expression"):
            func_node = node.child_by_field_name("function") or \
                        node.child_by_field_name("constructor")
            if not func_node and node.children:
                func_node = node.children[0]

            if func_node:
                chain = get_full_chain(func_node, source)
                
                if chain != "<unknown>":
                    calls.append(CallUsage(
                        chain=chain,
                        code=source[node.start_byte:node.end_byte].decode('utf-8', errors='replace'),
                        file=file_path,
                        line=node.start_point[0] + 1,
                        structure="",
                        source_import=findImportSource(extracted_imports_dict, chain),
                        context=context[:],
                        extension=file_path.split('.')[-1]
                    ))
                    current_context = context + [chain]

        # 2. Structural/Flow logic as "Calls"
        elif node.type == "binary_expression":
            operator = node.child_by_field_name("operator")
            if operator and source[operator.start_byte:operator.end_byte].decode('utf-8') == "instanceof":
                right = node.child_by_field_name("right")
                if right:
                    check_type = get_full_chain(right, source)
                    calls.append(CallUsage(
                        chain=f"instanceof {check_type}",
                        code=source[node.start_byte:node.end_byte].decode('utf-8', errors='replace'),
                        file=file_path,
                        line=node.start_point[0] + 1,
                        structure="type_check",
                        source_import=findImportSource(extracted_imports_dict, check_type),
                        context=context[:],
                        extension=file_path.split('.')[-1]
                    ))
        # 3. Constants
        elif node.type == "lexical_declaration":
            kind = node.child_by_field_name("kind")
            if kind and source[kind.start_byte:kind.end_byte].decode('utf-8') == "const":
                # We look for the first declarator name
                for child in node.children:
                    if child.type == "variable_declarator":
                        name_node = child.child_by_field_name("name")
                        if name_node:
                            constant_defs.append(ConstantDefinition(
                                name=source[name_node.start_byte:name_node.end_byte].decode('utf-8'),
                                code=source[node.start_byte:node.end_byte].decode('utf-8', errors='replace'),
                                file=file_path,
                                line=node.start_point[0] + 1,
                                source_import="Declaration",
                                context=context[:],
                                extension=file_path.split('.')[-1]
                            ))
        # # 4. Referencing
        # elif
        # 2b. Other Structural Nodes (Update context only)
        elif node.type in ("try_statement", "if_statement", "catch_clause"):
            name = node.type.replace("_statement", "").replace("_clause", "")
            current_context = context + [name]
            
        # 3. Functions / Methods (Definition Mapping)
        elif node.type in ("function_declaration", "method_definition", "arrow_function", "function_expression"):
            name = ""
            if node.type == "function_declaration" or node.type == "method_definition":
                name_node = node.child_by_field_name("name")
                if name_node: name = source[name_node.start_byte:name_node.end_byte].decode('utf-8')
            
            if not name and node.parent and node.parent.type == "variable_declarator":
                id_node = node.parent.child_by_field_name("name")
                if id_node: name = source[id_node.start_byte:id_node.end_byte].decode('utf-8')

            if name:
                code = source[node.start_byte:node.end_byte].decode('utf-8', errors='replace')
                global_definitions[name] = code
                
                if name[0].isupper() and len(name) > 1:
                     component_defs.append(ComponentDefinition(
                        name=name,
                        code=code,
                        file=file_path,
                        props=extract_component_props(node, source),
                        line=node.start_point[0] + 1,
                        source_import=findImportSource(extracted_imports_dict, name),
                        context=context[:],
                        extension=file_path.split('.')[-1]
                     ))
                
                current_context = context + [f"fn:{name}"]

        # 4. JSX
        jsx_node = None
        if node.type in ("jsx_element", "jsx_self_closing_element"):
            jsx_node = node
        
        if jsx_node:
            name = get_jsx_name(jsx_node, source)
            if name and name[0].isupper():
                props = get_jsx_props(jsx_node, source)
                jsxs.append(JSXUsage(
                    name=name,
                    source_import=findImportSource(extracted_imports_dict, name),
                    props=props,
                    code=source[jsx_node.start_byte:jsx_node.end_byte].decode('utf-8', errors='replace'),
                    file=file_path,
                    extension=file_path.split('.')[-1],
                    line=jsx_node.start_point[0] + 1,
                    has_children=jsx_node.type == "jsx_element",
                    context=context[:],
                ))
                current_context = context + [name]

        for child in node.children:
            walk(child, current_context)
    
    walk(tree.root_node)
    # print("file", file_path)
    # print("Extracted", len(calls), "call usages,", len(jsxs), "JSX usages.", len(component_defs), "component definitions,", len(type_defs), "type definitions.")
    return calls, jsxs, component_defs, type_defs, constant_defs, [ReferenceUsage(name=ref.name, source_import=ref.source_import) for ref in references]
