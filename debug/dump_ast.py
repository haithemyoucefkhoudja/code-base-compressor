from analyzer.core.languages import get_parser
import sys

def dump_node(node, source, indent=0):
    print(f"{'  ' * indent}{node.type} [{source[node.start_byte:node.end_byte].decode('utf-8')[:20]}]")
    for child in node.children:
        dump_node(child, source, indent + 1)

file_path = "repro_messagebox.d.ts"
with open(file_path, "rb") as f:
    source = f.read()

parser = get_parser(file_path)
tree = parser.parse(source)
dump_node(tree.root_node, source)
