
from typing import Tuple, List
from tree_sitter import Node

def import_name(import_name: str) -> Tuple[str, str]:
    try:

        raw_symbol = None
        actual_used_name = None
        _type = None
        # Safe checking for prefixes
        if "PART:" in import_name:
            _type = "PART"
            parts = import_name.split("PART:")
            if len(parts) > 1: raw_symbol = parts[1]
        elif "NAMESPACE:" in import_name:
            _type = "NAMESPACE"
            parts = import_name.split("NAMESPACE:")
            if len(parts) > 1: raw_symbol = parts[1]
        elif "DEFAULT:" in import_name:
            _type = "DEFAULT"
            parts = import_name.split("DEFAULT:")
            if len(parts) > 1: raw_symbol = parts[1]
        else:
            raise ValueError(f"Something Went Wrong {import_name}")
            
        
        if raw_symbol:
            # Logic to handle 'import { original as alias }'
            if " as " in raw_symbol:
                actual_used_name = raw_symbol.split(" as ")[1].strip()
            else:
                actual_used_name = raw_symbol.strip()
            
            return (actual_used_name, _type)
        return ("None", "LanguageTool")
    except Exception as e:
        print(f"Error finding import: {e}")
        return ('None','Lanugage Tool')
    

def get_constant_name(node: Node, source: bytes):
    """Returns the name of a constant if the node is a const declaration."""
    target_node = node
    print("target_node.type:",target_node.type)
    if target_node.type == "lexical_declaration":
        kind = target_node.child_by_field_name("kind")
        if kind and source[kind.start_byte:kind.end_byte].decode('utf-8') == "const":
            # We look for the first declarator name
            for child in target_node.children:
                if child.type == "variable_declarator":
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        return source[name_node.start_byte:name_node.end_byte].decode('utf-8')
    return None



def find_jsx(n):
    if n.type in ("jsx_element", "jsx_self_closing_element"):
        return n
    for child in n.children:
        res = find_jsx(child)
        if res: return res
    return None

def get_full_chain(node: Node, source: bytes) -> str:
    """
    Extract the COMPLETE method chain from a call expression.
    e.g., supabase.storage.from(...) -> "supabase.storage.from"
    e.g., createServerAction().input(...).handler(...) -> "createServerAction.input.handler"
    """
    parts = []
    current = node
    
    while current:
        if current.type == "identifier":
            parts.append(source[current.start_byte:current.end_byte].decode('utf-8'))
            break
        elif current.type == "property_identifier":
            parts.append(source[current.start_byte:current.end_byte].decode('utf-8'))
            current = current.parent
        elif current.type == "member_expression":
            # Get the property
            prop = current.child_by_field_name("property")
            if prop:
                parts.append(source[prop.start_byte:prop.end_byte].decode('utf-8'))
            # Move to object
            current = current.child_by_field_name("object")
        elif current.type == "call_expression":
            # It's a chained call: foo().bar()
            func = current.child_by_field_name("function")
            if func:
                current = func
            else:
                break
        else:
            break
    
    parts.reverse()
    return ".".join(parts) if parts else "<unknown>"

def get_jsx_props(node: Node, source: bytes) -> List[str]:
    """Extract all prop names from a JSX element."""
    props = []
    
    def find_props(n: Node):
        if n.type == "jsx_attribute":
            # First child is the prop name
            for child in n.children:
                if child.type == "property_identifier" or child.type == "identifier":
                    props.append(source[child.start_byte:child.end_byte].decode('utf-8'))
                    break
        for child in n.children:
            find_props(child)
    
    find_props(node)
    return props

def get_jsx_name(node: Node, source: bytes) -> str:
    """Extract JSX component name."""
    # For jsx_element, look in opening_element
    if node.type == "jsx_element":
        for child in node.children:
            if child.type == "jsx_opening_element":
                for c in child.children:
                    if c.type in ("identifier", "member_expression"):
                        return source[c.start_byte:c.end_byte].decode('utf-8')
    # For self-closing
    elif node.type == "jsx_self_closing_element":
        for child in node.children:
            if child.type in ("identifier", "member_expression"):
                return source[child.start_byte:child.end_byte].decode('utf-8')
    return "<unknown>"
