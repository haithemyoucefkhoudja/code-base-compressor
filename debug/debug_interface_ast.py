import os
from analyzer.core.languages import get_parser
from tree_sitter import Node

# Test parsing chat-provider.d.ts to understand AST structure
DTS_PATH = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_blimpt\dist-types\providers\chat-provider.d.ts"

with open(DTS_PATH, 'rb') as f:
    source = f.read()

parser = get_parser(DTS_PATH)
tree = parser.parse(source)

with open("debug_interface_ast.txt", "w", encoding="utf-8") as out:
    out.write("--- Interface AST Structure ---\n\n")
    
    def dump_node(n: Node, indent: int = 0):
        prefix = "  " * indent
        text = ""
        if n.child_count == 0:
            text = f" = '{source[n.start_byte:n.end_byte].decode('utf-8')[:50]}'"
        out.write(f"{prefix}{n.type}{text}\n")
        for child in n.children:
            dump_node(child, indent + 1)
    
    # Find interface declarations
    for node in tree.root_node.children:
        if node.type == "interface_declaration":
            # Get interface name
            name_node = None
            for c in node.children:
                if c.type == "type_identifier":
                    name_node = c
                    break
            if name_node:
                out.write(f"\n=== Interface: {source[name_node.start_byte:name_node.end_byte].decode('utf-8')} ===\n")
            
            # Dump first 3 children to understand structure
            for child in node.children[:10]:
                dump_node(child, 1)
            
            # Look specifically for object_type body
            for child in node.children:
                if child.type == "object_type":
                    out.write(f"\n  Found object_type with {child.child_count} children\n")
                    # Dump first property_signature
                    for member in child.children[:5]:
                        out.write(f"\n  --- Member: {member.type} ---\n")
                        dump_node(member, 2)
            break  # Just check first interface
