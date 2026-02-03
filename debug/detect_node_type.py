from analyzer.core.languages import get_parser
import sys

def inspect_node(node, source, indent=0):
    text = source[node.start_byte:node.end_byte].decode('utf-8')
    if "MessageBox" in text or node.type in ("generic_type", "type_reference", "object_type"):
        print(f"{'  ' * indent}{node.type} field={node.child_by_field_name('name')}")

    for child in node.children:
        inspect_node(child, source, indent + 1)

file_path = "repro_messagebox.d.ts"
with open(file_path, "rb") as f:
    source = f.read()

parser = get_parser(file_path)
tree = parser.parse(source)

# Find the variable declaration for MessageBox
def find_decl(node):
    if node.type == "variable_declarator":
         name = node.child_by_field_name("name")
         if name and source[name.start_byte:name.end_byte].decode('utf-8') == "MessageBox":
             return node
    for child in node.children:
        res = find_decl(child)
        if res: return res
    return None

decl = find_decl(tree.root_node)
if decl:
    print(f"Found declaration: {decl.type}")
    type_node = decl.child_by_field_name("type") # type_annotation
    if type_node:
        print(f"Type Annotation: {type_node.type}")
        for child in type_node.children:
            print(f"Child of type_annotation: {child.type}")
            if child.type == "generic_type":
                print("It IS generic_type")
                name_node = child.child_by_field_name("name")
                print(f"Generic Name: {source[name_node.start_byte:name_node.end_byte].decode('utf-8')}")
                targs = child.child_by_field_name("type_arguments")
                if targs:
                    print("Has type_arguments")
                    for arg in targs.children:
                        print(f"Arg: {arg.type}")
            else:
                # deeper inspection
                print(f"Inspecting {child.type}...")
                for grand in child.children:
                    print(f"  Grandchild: {grand.type}")
else:
    print("Declaration not found via recursion.")
    # Debug recursion
    print("Root children:")
    for c in tree.root_node.children:
        print(f"  {c.type}")
