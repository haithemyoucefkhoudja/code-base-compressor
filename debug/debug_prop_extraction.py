import os
from pathlib import Path
from analyzer.core.dts_provider import resolve_import_path, parse_dts_definitions, find_dts_file

# Setup paths based on user's workspace
WORKSPACE_ROOT = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_blimpt"
SOURCE_FILE = os.path.join(WORKSPACE_ROOT, "components", "shortcut-ui", "message-list.tsx")
IMPORT_SOURCE = "./message-box"

print(f"--- Debugging Prop Extraction ---")
print(f"Source File: {SOURCE_FILE}")
print(f"Import Source: {IMPORT_SOURCE}")

# 1. Test Resolution
resolved_path = resolve_import_path(SOURCE_FILE, IMPORT_SOURCE)
print(f"\n[Resolution]")
print(f"resolve_import_path result: {resolved_path}")

expected_dts = os.path.join(WORKSPACE_ROOT, "dist-types", "components", "shortcut-ui", "message-box.d.ts")
print(f"Expected DTS path: {expected_dts}")
if resolved_path:
    print(f"Matches expected? {os.path.normpath(resolved_path) == os.path.normpath(expected_dts)}")
else:
    print(f"Failed to resolve anything.")

# 2. Test Finding DTS (if resolution returned .tsx)
if resolved_path and not resolved_path.endswith(".d.ts"):
    print(f"\n[Upgrade to DTS]")
    found_dts = find_dts_file(resolved_path)
    print(f"find_dts_file result: {found_dts}")
    if found_dts:
        resolved_path = found_dts

# 3. Test Parsing
if resolved_path and resolved_path.endswith(".d.ts"):
    print(f"\n[Parsing {resolved_path}]")
    defs = parse_dts_definitions(resolved_path)
    print(f"Definitions found: {list(defs.keys())}")
    
    if "MessageBox" in defs:
        print("MessageBox definition found:")
        print(defs["MessageBox"])
    else:
        print("ERROR: MessageBox not found in definitions!")
        
        # Dump AST to see what's wrong
        from analyzer.core.languages import get_parser
        parser = get_parser(resolved_path)
        with open(resolved_path, 'rb') as f:
            source = f.read()
        tree = parser.parse(source)
        
        def print_tree(node, depth=0):
            print(f"{'  ' * depth}{node.type}  -- '{source[node.start_byte:node.end_byte].decode('utf-8')[:20]}...'")
            for child in node.children:
                print_tree(child, depth + 1)
                
        print("\n--- AST DUMP ---")
        
        with open("debug_ast.txt", "w", encoding="utf-8") as out:
            def print_tree_to_file(node, depth=0):
                line = f"{'  ' * depth}{node.type}  -- '{source[node.start_byte:node.end_byte].decode('utf-8')[:20]}...'\n"
                out.write(line)
                for child in node.children:
                    print_tree_to_file(child, depth + 1)
            
            print_tree_to_file(tree.root_node)
            
        print("AST dumped to debug_ast.txt")
        print("--- END AST DUMP ---")
else:
    print("\nSkipping parsing tests because we don't have a .d.ts path.")
