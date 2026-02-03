from typing import List, Tuple, Dict, Set
from tree_sitter import Node
from ..models import CallUsage, JSXUsage, ComponentDefinition, TypeDefinition, ReferenceUsage, ConstantDefinition
from ..core.languages import get_parser
from ..core.node_utils import get_full_chain, get_jsx_name, get_jsx_props, get_jsx_props_with_types
from ..core.dts_provider import find_dts_file, parse_dts_definitions, resolve_import_path, get_function_signature
from .imports import extract_js_imports
from pathlib import Path

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

def extract_component_props(node: Node, source: bytes) -> Tuple[List[str], Dict[str, str]]:
    """Extract prop names and types from a component definition (function/arrow parameters)."""
    params_node = node.child_by_field_name("parameters")
    if not params_node:
        return [], {}
    
    # Props is usually the first parameter (ignore symbols)
    actual_params = [c for c in params_node.children if c.type not in ("(", ")", ",", "type_annotation")]
    if not actual_params:
        return [], {}
        
    first_param = actual_params[0]
    prop_types = {}
    
    def extract_from_pattern(p_node: Node) -> List[str]:
        found = []
        if p_node.type in ("identifier", "shorthand_property_identifier_pattern"):
            name = source[p_node.start_byte:p_node.end_byte].decode('utf-8')
            found.append(name)
            
        elif p_node.type == "object_pattern":
            for child in p_node.children:
                if child.type == "shorthand_property_identifier_pattern":
                    name = source[child.start_byte:child.end_byte].decode('utf-8')
                    found.append(name)
                elif child.type == "pair_pattern":
                    # key is usually the first child or have 'key' field
                    key = child.child_by_field_name("key")
                    if not key and child.children: key = child.children[0]
                    if key: 
                        name = source[key.start_byte:key.end_byte].decode('utf-8')
                        found.append(name)
                elif child.type == "object_assignment_pattern":
                    # first child is the pattern
                    if child.children: found.extend(extract_from_pattern(child.children[0]))
                elif child.type == "rest_pattern":
                    for c in child.children:
                        if c.type == "identifier":
                            found.append(source[c.start_byte:c.end_byte].decode('utf-8'))
        
        elif p_node.type in ("required_parameter", "optional_parameter", "parameter"):
            # Start recursion
            for child in p_node.children:
                if child.type in ("identifier", "object_pattern", "shorthand_property_identifier_pattern", "pair_pattern", "object_assignment_pattern", "rest_pattern"):
                    found_names = extract_from_pattern(child)
                    found.extend(found_names)
                    break 
        return found
    
    # If first param is `required_parameter` -> identifier + type
    # e.g. `props: ButtonProps`
    if first_param.type in ("required_parameter", "parameter"):
         # Check for type annotation
         for child in first_param.children:
             if child.type == "type_annotation":
                 raw_type = source[child.start_byte:child.end_byte].decode('utf-8')
                 # Clean up ": "
                 if raw_type.startswith(":"): raw_type = raw_type[1:].strip()
                 # If it's an object type literal: `{ name: string }`
                 if child.children:
                     for sub in child.children:
                         if sub.type == "object_type":
                             obj_type = sub
                             for prop_sig in obj_type.children:
                                 if prop_sig.type in ("property_signature", "property_definition"):
                                     pname_node = prop_sig.child_by_field_name("name")
                                     ptype_node = prop_sig.child_by_field_name("type")
                                     if pname_node and ptype_node:
                                         pname = source[pname_node.start_byte:pname_node.end_byte].decode('utf-8')
                                         ptype = source[ptype_node.start_byte:ptype_node.end_byte].decode('utf-8')
                                         if ptype.startswith(":"): ptype = ptype[1:].strip()
                                         prop_types[pname] = ptype
                             break

    extracted_props = extract_from_pattern(first_param)
    return extracted_props, prop_types

def extract_return_type(node: Node, source: bytes) -> str:
    """Extract return type of a function."""
    # check for type_annotation on the function node itself
    # node is function_declaration/arrow_function
    # usually it's a child with field `return_type` or just a child `type_annotation` after parameters
    ret_type = node.child_by_field_name("return_type")
    if ret_type:
        code = source[ret_type.start_byte:ret_type.end_byte].decode('utf-8')
        if code.startswith(":"): code = code[1:].strip()
        return code
    return ""

def extract_call_args(node: Node, source: bytes) -> Tuple[List[str], Dict[str, str]]:
    """Extract argument names/indices and infer types."""
    # node is call_expression
    args_node = node.child_by_field_name("arguments")
    if not args_node:
        return [], {}
    
    args_list = []
    types_map = {}
    
    # Children of arguments: "(", arg1, ",", arg2, ")"
    actual_args = [c for c in args_node.children if c.type not in ("(", ")", ",")]
    
    for i, arg in enumerate(actual_args):
        # Name: just use index for positional
        name = str(i)
        args_list.append(name)
        
        # Infer type
        inferred = "unknown"
        if arg.type == "string": inferred = "string"
        elif arg.type == "number": inferred = "number"
        elif arg.type in ("true", "false", "boolean"): inferred = "boolean"
        elif arg.type == "object":
            # Extract object properties with their types
            obj_props = extract_object_properties(arg, source)
            if obj_props:
                inferred = obj_props  # Now a dict like {"activeEngines": "identifier", ...}
            else:
                inferred = "object"
        elif arg.type in ("arrow_function", "function"): inferred = "function"
        elif arg.type == "identifier": inferred = "identifier"
        elif arg.type == "call_expression": inferred = "call"
        
        types_map[name] = inferred
        
    return args_list, types_map

def infer_value_type(value_node: Node, source: bytes) -> str:
    """Infer the type of a value node."""
    if not value_node:
        return "unknown"
    
    t = value_node.type
    if t == "string": return "string"
    elif t == "number": return "number"
    elif t in ("true", "false"): return "boolean"
    elif t == "null": return "null"
    elif t == "undefined": return "undefined"
    elif t == "array": return "array"
    elif t == "object": return "object"
    elif t in ("arrow_function", "function"): return "function"
    elif t == "identifier": 
        # Return the identifier name for reference tracking
        return source[value_node.start_byte:value_node.end_byte].decode('utf-8')
    elif t == "call_expression":
        # Extract call chain
        func_node = value_node.child_by_field_name("function")
        if func_node:
            return source[func_node.start_byte:func_node.end_byte].decode('utf-8') + "()"
        return "call"
    elif t == "member_expression":
        return source[value_node.start_byte:value_node.end_byte].decode('utf-8')
    elif t == "template_string":
        return "string"
    elif t == "binary_expression":
        return "expression"
    elif t == "unary_expression":
        return "expression"
    elif t == "ternary_expression" or t == "conditional_expression":
        return "conditional"
    else:
        return t  # Return the node type as fallback

def extract_object_properties(obj_node: Node, source: bytes) -> Dict[str, str]:
    """Extract property names and their value types from an object literal node."""
    props = {}
    for child in obj_node.children:
        if child.type == "pair":
            # For pair: key: value
            key_node = child.child_by_field_name("key")
            value_node = child.child_by_field_name("value")
            if key_node:
                key_text = source[key_node.start_byte:key_node.end_byte].decode('utf-8')
                value_type = infer_value_type(value_node, source) if value_node else "unknown"
                props[key_text] = value_type
        elif child.type == "shorthand_property_identifier":
            # For shorthand: { foo } means foo: foo (identifier)
            key = source[child.start_byte:child.end_byte].decode('utf-8')
            props[key] = "identifier"
        elif child.type == "spread_element":
            # For spread: { ...obj }
            spread_arg = None
            for c in child.children:
                if c.type not in ("...",):
                    spread_arg = c
                    break
            if spread_arg:
                spread_text = source[spread_arg.start_byte:spread_arg.end_byte].decode('utf-8')
                props["..." + spread_text] = "spread"
            else:
                props["..."] = "spread"
    return props

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
            
    # Load authoritative types from .d.ts if available (for local file)
    dts_path = find_dts_file(file_path)
    dts_defs = {}
    if dts_path:
        dts_defs = parse_dts_definitions(dts_path)
    
    scope_types = {} # { var_name: dts_info }

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
                    c_props, c_prop_types = extract_call_args(node, source)
                    
                    # 1. Try scope types first (local overrides from hooks/destructuring)
                    dts_info = scope_types.get(chain)

                    # 2. Override with authoritative DTS types if available
                    if not dts_info:
                        dts_info = dts_defs.get(chain)
                    
                    # 3. If not found in current file's .d.ts, try external .d.ts
                    if not dts_info:
                        import_src = findImportSource(extracted_imports_dict, chain)
                        if import_src and import_src != "Declaration":
                            ext_def_path = resolve_import_path(file_path, import_src)
                            if ext_def_path:
                                ext_defs = parse_dts_definitions(ext_def_path)
                                dts_info = ext_defs.get(chain)
                    
                    # Hook return analysis (Destructuring)
                    if chain.startswith("use") and dts_info and dts_info.get("return_type_expanded"):
                        parent = node.parent
                        if parent and parent.type == "variable_declarator":
                            name_node = parent.child_by_field_name("name")
                            if name_node and name_node.type == "object_pattern":
                                ret_expanded = dts_info["return_type_expanded"]
                                for child in name_node.children:
                                    var_name = None
                                    prop_name = None
                                    
                                    if child.type == "shorthand_property_identifier_pattern":
                                        var_name = source[child.start_byte:child.end_byte].decode('utf-8')
                                        prop_name = var_name
                                    elif child.type == "pair_pattern":
                                        key_node = child.child_by_field_name("key")
                                        val_node = child.child_by_field_name("value")
                                        if key_node and val_node:
                                            prop_name = source[key_node.start_byte:key_node.end_byte].decode('utf-8')
                                            var_name = source[val_node.start_byte:val_node.end_byte].decode('utf-8')
                                    
                                    if var_name and prop_name and prop_name in ret_expanded:
                                        # Create a pseudo dts_info for this variable
                                        type_str = ret_expanded[prop_name]
                                        scope_types[var_name] = {
                                            "parameters": [type_str], # Best effort mapping
                                            "type": "function",
                                            "return_type": "unknown"
                                        }
                    
                    # Fallback: check global function registry (for destructured hook returns)
                    if not dts_info:
                        # Find repo root by walking up to find dist-types
                        repo_root = None
                        p = Path(file_path).parent
                        for _ in range(10):
                            if (p / "dist-types").exists():
                                repo_root = str(p)
                                break
                            if p == p.parent:
                                break
                            p = p.parent
                        if repo_root:
                            dts_info = get_function_signature(chain, repo_root)
                    
                    if dts_info and dts_info.get("parameters"):
                        params = dts_info["parameters"]
                        # Map positional args to DTS types
                        for i in range(len(c_props)):
                            if i < len(params):
                                # Override inferred type
                                # We assume c_props are positional indices strings "0", "1"
                                c_prop_types[str(i)] = params[i]
                    
                    # Extract DTS signature (full type definition for classes, parameters for functions)
                    dts_signature = None
                    if dts_info:
                        if dts_info.get("kind") == "class":
                            # For classes, include full definition with constructor and methods
                            dts_signature = {
                                "kind": "class",
                                "constructor": dts_info.get("constructor"),
                                "methods": dts_info.get("methods"),
                                "properties": dts_info.get("properties")
                            }
                        elif dts_info.get("parameters") is not None:
                            # For functions, include parameters and return type
                            dts_signature = {
                                "type": "function",
                                "parameters": dts_info["parameters"],
                                "return_type": dts_info.get("return_type"),
                                "return_type_expanded": dts_info.get("return_type_expanded")
                            }
                    
                    calls.append(CallUsage(
                        chain=chain,
                        code=source[node.start_byte:node.end_byte].decode('utf-8', errors='replace'),
                        file=file_path,
                        line=node.start_point[0] + 1,
                        structure="",
                        source_import=findImportSource(extracted_imports_dict, chain),
                        props=c_props,
                        prop_types=c_prop_types,
                        return_type=dts_info.get("return_type", "") if dts_info else "", 
                        context=context[:],
                        extension=file_path.split('.')[-1],
                        dts_signature=dts_signature
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
                        props=[],
                        prop_types={},
                        return_type="boolean",
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
        
        # 4. Type Definitions (Interfaces & Type Aliases)
        elif node.type in ("interface_declaration", "type_alias_declaration"):
            name_node = node.child_by_field_name("name")
            if name_node:
                t_name = source[name_node.start_byte:name_node.end_byte].decode('utf-8')
                kind = "interface" if node.type == "interface_declaration" else "type"
                type_defs.append(TypeDefinition(
                    name=t_name,
                    kind=kind,
                    code=source[node.start_byte:node.end_byte].decode('utf-8', errors='replace'),
                    file=file_path,
                    line=node.start_point[0] + 1,
                    source_import=findImportSource(extracted_imports_dict, t_name),
                    extension=file_path.split('.')[-1]
                ))

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
                     c_props, c_prop_types = extract_component_props(node, source)
                     
                     # Enrich with authoritative types from DTS
                     dts_info = dts_defs.get(name)
                     final_ret_type = extract_return_type(node, source)

                     if dts_info:
                         # Merge props
                         if dts_info.get("props"):
                             auth_props = dts_info["props"]
                             c_prop_types.update(auth_props)
                             # Ensure all authoritative props are listed
                             for p in auth_props:
                                 if p not in c_props: c_props.append(p)
                                 
                         # Merge return type
                         if dts_info.get("return_type") and dts_info["return_type"] != "unknown":
                             final_ret_type = dts_info["return_type"]

                     component_defs.append(ComponentDefinition(
                        name=name,
                        code=code,
                        file=file_path,
                        props=c_props,
                        prop_types=c_prop_types,
                        return_type=final_ret_type,
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
                props = get_jsx_props(jsx_node, source) # keep for name list
                prop_types = get_jsx_props_with_types(jsx_node, source)
                
                # --- ENRICHMENT LOGIC ---
                # Attempt to resolve external definition
                import_src = findImportSource(extracted_imports_dict, name)
                
                # Check external defs
                if import_src and import_src != "Declaration":
                    def_path = resolve_import_path(file_path, import_src)
                    
                    if def_path:
                        ext_defs = parse_dts_definitions(def_path)
                        
                        # Try exact match or default
                        comp_def = ext_defs.get(name)
                        if comp_def and "props" in comp_def:
                            for pname, ptype in comp_def["props"].items():
                                # Override inferred AST type with authoritative type
                                prop_types[pname] = ptype
                
                jsxs.append(JSXUsage(
                    name=name,
                    source_import=import_src,
                    props=props, 
                    prop_types=prop_types,
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
    return calls, jsxs, component_defs, type_defs, constant_defs, [ReferenceUsage(name=ref.name, source_import=ref.source_import) for ref in references]
