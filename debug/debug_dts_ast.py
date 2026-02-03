
import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from analyzer.core.languages import get_parser

file_path = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_blimpt\dist-types\components\ChatIndicator.d.ts"
copy_path = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_blimpt\dist-types\components\Copy.d.ts"

def print_tree(node, source, f_out, indent=0):
    f_out.write("  " * indent + f"{node.type} [{node.start_point}-{node.end_point}]\n")
    if node.type in ("identifier", "type_identifier", "property_identifier", "string_fragment"):
        content = source[node.start_byte:node.end_byte].decode('utf-8')
        f_out.write("  " * indent + f"  Content: {content}\n")
    
    for child in node.children:
        print_tree(child, source, f_out, indent + 1)

def inspect(path, f_out):
    f_out.write(f"--- Inspecting {path} ---\n")
    with open(path, 'rb') as f:
        source = f.read()
    
    parser = get_parser(path)
    tree = parser.parse(source)
    print_tree(tree.root_node, source, f_out)

with open("debug_ast_output.txt", "w", encoding="utf-8") as f_out:
    inspect(file_path, f_out)
    inspect(copy_path, f_out)
