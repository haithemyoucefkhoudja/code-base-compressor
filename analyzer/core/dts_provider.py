import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from tree_sitter import Node
from .languages import get_parser
from functools import lru_cache

def find_dts_file(source_file_path: str) -> Optional[str]:
    """
    Attempts to find the corresponding .d.ts file in a dist-types directory.
    Heuristic: Walk up to find a 'dist-types' directory effectively parallel to source root.
    """
    path = Path(source_file_path)
    current = path.parent
    
    # We look for a directory containing 'dist-types'
    root = None
    # Limit traversal to avoid going too far up system
    for _ in range(10):
        try:
            if (current / "dist-types").exists():
                root = current
                break
            if str(current) == str(current.parent): # FS root
                break
            current = current.parent
        except (PermissionError, OSError):
             break
        
    if not root:
        return None
        
    try:
        rel_path = path.relative_to(root)
    except ValueError:
        return None
        
    # Map repo/foo/bar.tsx -> repo/dist-types/foo/bar.d.ts
    dts_path = root / "dist-types" / rel_path.with_suffix(".d.ts")
    
    if dts_path.exists():
        return str(dts_path)
    
    return None

def resolve_import_path(base_file_path: str, import_source: str) -> Optional[str]:
    """
    Resolves an import string (e.g. "./foo", "react") to a concrete file path on disk.
    Prioritizes .d.ts, then .ts, .tsx.
    """
    if not base_file_path or not import_source:
        return None

    # Strip surrounding quotes that may come from AST extraction
    import_source = import_source.strip("\"'")

    # Handle @/ alias
    if import_source.startswith("@/"):
        # Find repo root
        p = Path(base_file_path).resolve()
        repo_root = None
        for _ in range(10):
            if (p / "dist-types").exists() or (p / "package.json").exists():
                repo_root = p
                break
            if p.parent == p:
                break
            p = p.parent
            
        if repo_root:
            relative = import_source[2:]
            # Try root and src
            bases = [repo_root / relative, repo_root / "src" / relative]
            
            for candidate_base in bases:
                try:
                   candidate_base = candidate_base.resolve()
                except:
                    continue
                    
                # Check directly
                if candidate_base.is_file():
                    return str(candidate_base)
                
                # Check extensions
                extensions = [".d.ts", ".ts", ".tsx", ".js", ".jsx"]
                if candidate_base.is_dir():
                    for ext in extensions:
                        p_idx = candidate_base / f"index{ext}"
                        if p_idx.is_file():
                            dts = find_dts_file(str(p_idx))
                            if dts: return dts
                            return str(p_idx)
                            
                for ext in extensions:
                     p_ext = Path(str(candidate_base) + ext)
                     if p_ext.is_file():
                         dts = find_dts_file(str(p_ext))
                         if dts: return dts
                         return str(p_ext)
            
            return None        

    # Ignore node_modules for now unless we want to be very fancy
    if not import_source.startswith("."):
        # TODO: Handle node_modules resolution if needed
        return None

    base_dir = Path(base_file_path).parent
    
    # Simple resolution
    try:
        candidate_base = (base_dir / import_source).resolve()
    except (ValueError, OSError):
        return None

    # Check for direct file (e.g. import "./foo.ts")
    if candidate_base.is_file():
        return str(candidate_base)
        
    # Check extensions
    extensions = [".d.ts", ".ts", ".tsx", ".js", ".jsx"]
    
    # 2. Check directory / index
    if candidate_base.is_dir():
        for ext in extensions:
            p = candidate_base / f"index{ext}"
            if p.is_file():
                # Found index file. Check if there is a better dts for it?
                # For index.tsx -> dist-types/.../index.d.ts
                resolved = str(p)
                dts = find_dts_file(resolved)
                if dts: return dts
                return resolved
                
    # 1. Check file with extensions
    for ext in extensions:
        # candidate_base might already have an extension if import_source had one
        # But import usually doesn't have .tsx
        
        # Try appending extension
        p_str = str(candidate_base) + ext
        p = Path(p_str)
        if p.is_file():
            resolved = str(p)
            # Try to upgrade to .d.ts if possible
            dts = find_dts_file(resolved)
            if dts:
                return dts
            return resolved
            
    return None

def extract_type_annotation(node: Node, source: bytes) -> str:
    """Extracts cleaner type string from a type annotation node."""
    if not node: return "unknown"
    # Often node is `type_annotation` which starts with `:`.
    # We want to skip the colon.
    text = source[node.start_byte:node.end_byte].decode('utf-8').strip()
    if text.startswith(":"):
        text = text[1:].strip()
    
    # Clean up some common noise if needed
    return text

def parse_object_type(node: Node, source: bytes) -> Dict[str, str]:
    """Parses { key: type; ... } object types."""
    props = {}
    # node is `object_type`
    for child in node.children:
        if child.type == "property_signature":
            name_node = child.child_by_field_name("name")
            type_node = child.child_by_field_name("type")
            if name_node and type_node:
                name = source[name_node.start_byte:name_node.end_byte].decode('utf-8')
                type_str = extract_type_annotation(type_node, source)
                props[name] = type_str
    return props

def parse_interface_functions(iface_node: Node, source: bytes, definitions: Dict[str, Dict[str, Any]]) -> None:
    """
    Parses interface members and extracts function signatures.
    For members like `handleFormSubmit: (query: string, ...) => void`, 
    adds them to definitions with their parameter types.
    """
    # interface_declaration has a body child which is interface_body (not object_type)
    body = None
    for child in iface_node.children:
        if child.type in ("object_type", "interface_body"):
            body = child
            break
            
    if not body:
        return
        
    for member in body.children:
        if member.type == "property_signature":
            name_node = member.child_by_field_name("name")
            type_node = member.child_by_field_name("type")
            
            if not name_node or not type_node:
                continue
                
            name = source[name_node.start_byte:name_node.end_byte].decode('utf-8')
            
            # Check if type_node is or contains a function_type
            # type_node is usually type_annotation containing the actual type
            func_type = None
            
            def find_function_type(n: Node) -> Node | None:
                if n.type == "function_type":
                    return n
                for c in n.children:
                    result = find_function_type(c)
                    if result:
                        return result
                return None
            
            func_type = find_function_type(type_node)
            
            if func_type:
                # Extract parameter types
                params_list = []
                # Find formal_parameters child (not via field name)
                params = None
                for fc in func_type.children:
                    if fc.type == "formal_parameters":
                        params = fc
                        break
                
                if params:
                    for param in params.children:
                        if param.type in ("required_parameter", "optional_parameter", "parameter"):
                            p_type = "any"
                            p_type_node = param.child_by_field_name("type")
                            if p_type_node:
                                p_type = extract_type_annotation(p_type_node, source)
                            params_list.append(p_type)
                
                # Extract return type (it's the last type node after =>)
                ret_type = "void"
                # Find last predefined_type, type_identifier, etc. after formal_parameters
                for fc in func_type.children:
                    if fc.type in ("predefined_type", "type_identifier", "generic_type", "union_type", "array_type"):
                        ret_type = source[fc.start_byte:fc.end_byte].decode('utf-8')
                        break
                
                # Add to definitions (don't overwrite if already exists from direct declaration)
                if name not in definitions:
                    definitions[name] = {
                        "props": {},
                        "parameters": params_list,
                        "return_type": ret_type,
                        "type": "interface_function"
                    }

def parse_interface_properties(iface_node: Node, source: bytes) -> Dict[str, str]:
    """
    Parses all interface members and returns a dict of {property_name: type}.
    This is used to expand type references like `Config` into their full definitions.
    """
    # Get interface name
    iface_name = None
    for child in iface_node.children:
        if child.type == "type_identifier":
            iface_name = source[child.start_byte:child.end_byte].decode('utf-8')
            break
    
    # Find interface body
    body = None
    for child in iface_node.children:
        if child.type in ("object_type", "interface_body"):
            body = child
            break
            
    if not body:
        return {}
        
    props = {}
    for member in body.children:
        if member.type == "property_signature":
            name_node = member.child_by_field_name("name")
            type_node = member.child_by_field_name("type")
            
            if name_node:
                name = source[name_node.start_byte:name_node.end_byte].decode('utf-8')
                type_str = extract_type_annotation(type_node, source) if type_node else "unknown"
                props[name] = type_str
    
    return props

def parse_class_definition(class_node: Node, source: bytes, interface_defs: Dict[str, Dict[str, str]]) -> Optional[Dict[str, Any]]:
    """
    Parses a class declaration and extracts the full type definition.
    Includes constructor params and all method signatures.
    Expands type references (like `Config`) to their full interface definitions.
    """
    # Get class name
    class_name = None
    for child in class_node.children:
        if child.type in ("type_identifier", "identifier"):
            class_name = source[child.start_byte:child.end_byte].decode('utf-8')
            break
    
    if not class_name:
        return None
    
    # Find class body
    body = None
    for child in class_node.children:
        if child.type == "class_body":
            body = child
            break
    
    if not body:
        return None
    
    constructor_params = []
    methods = {}
    properties = {}
    
    for member in body.children:
        # Handle Methods (signatures and definitions)
        if member.type in ("method_signature", "method_definition"):
            name_node = member.child_by_field_name("name")
            if not name_node:
                continue
            
            method_name = source[name_node.start_byte:name_node.end_byte].decode('utf-8')
            
            # Extract parameters
            params_info = []
            params_node = member.child_by_field_name("parameters")
            if params_node:
                for param in params_node.children:
                    if param.type in ("required_parameter", "optional_parameter", "parameter"):
                        param_name_node = param.child_by_field_name("name") or param.child_by_field_name("pattern")
                        param_type_node = param.child_by_field_name("type")
                        
                        if param_name_node:
                            param_name = source[param_name_node.start_byte:param_name_node.end_byte].decode('utf-8')
                            param_type = extract_type_annotation(param_type_node, source) if param_type_node else "any"
                            
                            # Check if type is a reference to an interface and expand it
                            if param_type in interface_defs:
                                params_info.append({
                                    "name": param_name,
                                    "type": param_type,
                                    "expanded": interface_defs[param_type]
                                })
                            else:
                                params_info.append({
                                    "name": param_name,
                                    "type": param_type
                                })
            
            # Extract return type
            ret_type = None
            ret_type_node = member.child_by_field_name("return_type")
            if ret_type_node:
                ret_type = extract_type_annotation(ret_type_node, source)
            
            if method_name == "constructor":
                constructor_params = params_info
            else:
                methods[method_name] = {
                    "params": params_info,
                    "return_type": ret_type or "void"
                }

        # Handle Properties/Fields
        elif member.type in ("field_definition", "public_field_definition", "class_field"):
           name_node = member.child_by_field_name("property") or member.child_by_field_name("name")
           if name_node:
               prop_name = source[name_node.start_byte:name_node.end_byte].decode('utf-8')
               
               type_node = member.child_by_field_name("type")
               prop_type = extract_type_annotation(type_node, source) if type_node else "any"
               
               # Check validation modifiers
               modifiers = []
               for child in member.children:
                   if child.type == "accessibility_modifier":
                       modifiers.append(source[child.start_byte:child.end_byte].decode('utf-8'))
               
               properties[prop_name] = {
                   "type": prop_type,
                   "modifiers": modifiers
               }
    
    return {
        "name": class_name,
        "kind": "class",
        "constructor": constructor_params if constructor_params else None,
        "methods": methods if methods else None,
        "properties": properties if properties else None
    }


@lru_cache(maxsize=128)
def parse_dts_definitions(dts_path: str) -> Dict[str, Dict[str, Any]]:
    """
    Parses a .d.ts file and returns a registry of symbols.
    Returns:
       {
          "ComponentName": {
              "props": { "propName": "propType" },
              "return_type": "string"
          }
       }
    """
    definitions = {}
    
    try:
        with open(dts_path, 'rb') as f:
            source = f.read()
    except OSError:
        return {} # File read error
        
    parser = get_parser(dts_path)
    tree = parser.parse(source)
    
    # Traverse top-level
    target_nodes = []
    interface_nodes = []
    class_nodes = []
    interface_defs = {}  # Store interface definitions for type expansion
    
    def collect_declarations(n: Node):
        # We need to flatten the structure to handle the detached expression_statement issue
        if n.type in ("export_statement", "ambient_declaration"):
            for child in n.children:
                collect_declarations(child)
        elif n.type in ("function_signature", "lexical_declaration", "function_declaration", "expression_statement"):
            target_nodes.append(n)
        elif n.type == "interface_declaration":
            interface_nodes.append(n)
        elif n.type == "class_declaration":
            class_nodes.append(n)
            
    for node in tree.root_node.children:
        collect_declarations(node)
    
    # Parse interfaces first to get function signatures AND property definitions
    for iface_node in interface_nodes:
        parse_interface_functions(iface_node, source, definitions)
        
        # Also store interface property definitions for type expansion
        iface_name = None
        for child in iface_node.children:
            if child.type == "type_identifier":
                iface_name = source[child.start_byte:child.end_byte].decode('utf-8')
                break
        if iface_name:
            interface_defs[iface_name] = parse_interface_properties(iface_node, source)
    
    # Parse classes to extract full type definition
    for class_node in class_nodes:
        class_info = parse_class_definition(class_node, source, interface_defs)
        if class_info:
            definitions[class_info["name"]] = {
                "props": {},
                "kind": "class",
                "constructor": class_info.get("constructor"),
                "methods": class_info.get("methods"),
                "properties": class_info.get("properties"),
                "type": "class"
            }

    pending_component_name = None
    
    for t_node in target_nodes:
        # 1. Function Signature (or Declaration)
        if t_node.type in ("function_signature", "function_declaration"):
                pending_component_name = None 
                name_node = t_node.child_by_field_name("name")
                if name_node:
                    name = source[name_node.start_byte:name_node.end_byte].decode('utf-8')
                    
                     # Props (Arguments for functions)
                    params_list = []
                    params = t_node.child_by_field_name("parameters")
                    if params:
                        for param in params.children:
                            if param.type in ("required_parameter", "optional_parameter", "parameter"):
                                # Extract types
                                p_type = "any"
                                t_node_param = param.child_by_field_name("type") # type_annotation
                                if t_node_param:
                                    p_type = extract_type_annotation(t_node_param, source)
                                params_list.append(p_type)

                    ret_type = "unknown"
                    rt_node = t_node.child_by_field_name("return_type")
                    if rt_node:
                        ret_type = extract_type_annotation(rt_node, source)

                    definitions[name] = {
                        "props": {},
                        "parameters": params_list,
                        "return_type": ret_type,
                        "type": "function"
                    }

        # 2. Const / Lexical
        elif t_node.type == "lexical_declaration":
            pending_component_name = None
            for child in t_node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    type_node = child.child_by_field_name("type") # type_annotation
                    
                    if name_node and type_node:
                        name = source[name_node.start_byte:name_node.end_byte].decode('utf-8')
                        
                        props_map = {}
                        params_list = []
                        def_type = "unknown"
                        return_type_val = "unknown"
                        return_type_expanded = None
                        
                        # Helper to unwrap types
                        def resolve_props_from_type_node(tnode: Node):
                            nonlocal return_type_val, return_type_expanded
                            potential_targets = [tnode]
                            if tnode.type == "type_annotation":
                                potential_targets = tnode.children
                                
                            for sub in potential_targets:
                                if sub.type == "function_type":
                                    params = sub.child_by_field_name("parameters")
                                    if params:
                                        for param in params.children:
                                            if param.type in ("required_parameter", "optional_parameter", "parameter"):
                                                ptype = param.child_by_field_name("type") 
                                                p_type_str = "any"
                                                if ptype:
                                                    p_type_str = extract_type_annotation(ptype, source)
                                                params_list.append(p_type_str)
                                    
                                    # Extract return type
                                    rt_node = sub.child_by_field_name("return_type")
                                    if rt_node:
                                        return_type_val = extract_type_annotation(rt_node, source)
                                        if return_type_val in interface_defs:
                                            return_type_expanded = interface_defs[return_type_val]

                                    return "const_function"

                                elif sub.type == "object_type":
                                    props_map.update(parse_object_type(sub, source))
                                    return "const_object"
                                    
                                elif sub.type == "generic_type":
                                    name_sub = sub.child_by_field_name("name")
                                    type_args = sub.child_by_field_name("type_arguments")
                                    if type_args:
                                        for arg in type_args.children:
                                            if arg.type in ("object_type", "type_literal"): 
                                                props_map.update(parse_object_type(arg, source))
                                                return "component"
                                    return "component"
                            
                            return "unknown"

                        def_type = resolve_props_from_type_node(type_node)
                        
                        # Store definition
                        if def_type != "unknown":
                            definitions[name] = {
                                "props": props_map,
                                "parameters": params_list,
                                "return_type": return_type_val,
                                "return_type_expanded": return_type_expanded,
                                "type": def_type
                            }
                        
                        # Set pending if it looks like a component but we didn't find props yet (or even if we did, maybe they are detached?)
                        # In the broken AST case, 'def_type' might be 'unknown' or just 'component' without extracted props
                        if name[0].isupper():
                             # If we didn't extract props (empty map) or type is generic but empty args
                             # We mark it pending
                             pending_component_name = name
                             
                             if name not in definitions:
                                  definitions[name] = { "props": {}, "parameters": [], "return_type": "unknown", "type": "component" }

        # 3. Detached Expression Statement (The broken AST fix)
        elif t_node.type == "expression_statement":
            if pending_component_name:
                # Look for type_assertion -> type_arguments -> object_type
                # Or just type_arguments -> object_type directly?
                # Dump showed: expression_statement -> type_assertion -> type_arguments -> object_type
                
                # We can just search children recursively for object_type
                found_props = {}
                
                def find_object_type_props(n: Node):
                     if n.type == "object_type":
                         found_props.update(parse_object_type(n, source))
                         return True
                     for c in n.children:
                         if find_object_type_props(c): return True
                     return False

                if find_object_type_props(t_node):
                    if pending_component_name in definitions:
                        definitions[pending_component_name]["props"].update(found_props)
                
                # Reset pending after processing the immediate next statement
                pending_component_name = None

    return definitions

# Global registry cache
_global_function_registry: Dict[str, Dict[str, Any]] = {}
_registry_initialized = False

def build_global_function_registry(repo_root: str) -> Dict[str, Dict[str, Any]]:
    """
    Builds a global registry of function signatures from all .d.ts files in dist-types.
    This is useful for looking up functions that are destructured from hooks.
    """
    global _global_function_registry, _registry_initialized
    
    if _registry_initialized:
        return _global_function_registry
    
    dist_types_dir = Path(repo_root) / "dist-types"
    if not dist_types_dir.exists():
        _registry_initialized = True
        return _global_function_registry
    
    # Find all .d.ts files
    for dts_file in dist_types_dir.rglob("*.d.ts"):
        try:
            defs = parse_dts_definitions(str(dts_file))
            # Only add functions (with parameters) to avoid polluting with non-functions
            for name, info in defs.items():
                if info.get("parameters") and name not in _global_function_registry:
                    _global_function_registry[name] = info
        except Exception:
            pass  # Skip files that fail to parse
    
    _registry_initialized = True
    return _global_function_registry

def get_function_signature(func_name: str, repo_root: str|None = None) -> Optional[Dict[str, Any]]:
    """
    Look up a function signature from the global registry.
    """
    global _global_function_registry, _registry_initialized
    
    if repo_root and not _registry_initialized:
        build_global_function_registry(repo_root)
    
    return _global_function_registry.get(func_name)

def clear_global_registry():
    """Clear the global function registry (useful for testing)."""
    global _global_function_registry, _registry_initialized
    _global_function_registry = {}
    _registry_initialized = False

