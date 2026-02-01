import re
from typing import List, Dict
from tree_sitter import Node
from ..core.languages import TS_PARSER, JS_PARSER

def extract_js_imports(code: str) -> dict[str, list[str]]:
    '''
    Extract npm package imports using Tree-sitter for robust parsing.
    Handles both JavaScript and TypeScript code, including Vue SFC.
    Returns a list of package names.
    '''
    try:
        # For Vue SFC, extract the script section first
        script_match = re.search(r'<script.*?>(.*?)</script>', code, re.DOTALL)
        if script_match:
            code = script_match.group(1).strip()

        # Try parsing as TypeScript first, then JavaScript
        code_bytes = bytes(code, "utf8")
        try:
            tree = TS_PARSER.parse(code_bytes)
        except Exception as e:
            print(f"TypeScript parsing failed: {e}")
            try:
                tree = JS_PARSER.parse(code_bytes)
            except Exception as e:
                print(f"JavaScript parsing failed: {e}")
                tree = None

        if tree is None:
            raise Exception("Both TypeScript and JavaScript parsing failed")
        packages_dict: dict[str, list[str]] = {}
        def extract_package_name(node: Node) -> str | None:
            """Extract npm package name from string or template string. 
            Returns None for local aliases like @/ or relative paths."""
            if node.type in ['string', 'string_fragment']:
                pkg_path = code_bytes[node.start_byte:node.end_byte].decode('utf8').strip('"\'')
                if pkg_path.startswith('.') or pkg_path.startswith('/'):
                    return None  # relative, absolute, or alias path

                # Scoped npm package: @scope/package/...
                if pkg_path.startswith('@'):
                    parts = pkg_path.split('/')
                    if len(parts) >= 2:
                        return '/'.join(parts[:2])

                # Regular npm package: "lodash/cloneDeep" -> "lodash"
                return pkg_path.split('/')[0]

            elif node.type == 'template_string':
                content = ''
                has_template_var = False
                for child in node.children:
                    if child.type == 'string_fragment':
                        content += code_bytes[child.start_byte:child.end_byte].decode('utf8')
                    elif child.type == 'template_substitution':
                        has_template_var = True

                if not content or content.startswith('.') or content.startswith('/') or content.startswith('@/'):
                    return None

                if has_template_var:
                    if content.endswith('-literal'):
                        return 'package-template-literal'
                    return None

                if content.startswith('@'):
                    parts = content.split('/')
                    if len(parts) >= 2:
                        return '/'.join(parts[:2])
                return content.split('/')[0]

            return None

        def add_piece(pkg: str, piece: str):
            if pkg not in packages_dict:
                packages_dict[pkg] = []
            if piece not in packages_dict[pkg]:
                packages_dict[pkg].append(piece)

        def visit_node(node: Node) -> None:
            if node.type == 'import_statement':
                # Get package name and pieces
                pkg_name = None
                clause_node = None
                
                for child in node.children:
                    if child.type == 'string':
                        # print(code_bytes[child.start_byte:child.end_byte].decode('utf8'))
                        # pkg_name = extract_package_name(child)
                        pkg_name = code_bytes[child.start_byte:child.end_byte].decode('utf8')
                        # print(pkg_name)
                    elif child.type == 'import_clause':
                        clause_node = child
                
                if pkg_name:
                    if pkg_name not in packages_dict:
                        packages_dict[pkg_name] = []
                    
                    if clause_node:
                        for child in clause_node.children:
                            if child.type == 'identifier': # Default import
                                name = code_bytes[child.start_byte:child.end_byte].decode('utf8')
                                add_piece(pkg_name, f"DEFAULT:{name}")
                            elif child.type == 'namespace_import': # * as alias
                                for sub in child.children:
                                    if sub.type == 'identifier':
                                        name = code_bytes[sub.start_byte:sub.end_byte].decode('utf8')
                                        add_piece(pkg_name, f"NAMESPACE:{name}")
                            elif child.type == 'named_imports':
                                for specifier in child.children:
                                    if specifier.type == 'import_specifier':
                                        # (import_specifier (identifier) (as) (identifier))
                                        ids = [code_bytes[c.start_byte:c.end_byte].decode('utf8') 
                                               for c in specifier.children if c.type == 'identifier']
                                        if len(ids) == 1:
                                            add_piece(pkg_name, f"PART:{ids[0]}")
                                        elif len(ids) == 2:
                                            add_piece(pkg_name, f"PART:{ids[0]} as {ids[1]}")

            elif node.type == 'export_statement':
                # Handle re-exports
                for child in node.children:
                    if child.type == 'string':
                        pkg_name = extract_package_name(child)
                        if pkg_name and pkg_name not in packages_dict:
                            packages_dict[pkg_name] = []

            elif node.type == 'call_expression':
                # Handle require/import calls
                is_import_call = False
                for child in node.children:
                    if child.type in ['identifier', 'import'] and child.text:
                        if child.text.decode('utf8') in ['require', 'import']:
                            is_import_call = True
                    elif child.type == 'arguments' and is_import_call:
                        if child.named_children:
                            pkg_name = extract_package_name(child.named_children[0])
                            if pkg_name and pkg_name not in packages_dict:
                                packages_dict[pkg_name] = []

            # Recursively visit children
            for child in node.children:
                visit_node(child)

        visit_node(tree.root_node)
        return packages_dict

    except Exception as e:
        print(f"Tree-sitter parsing failed: {e}")
        # Fallback to basic regex parsing if tree-sitter fails
        packages: Dict[str, List[str]] = {}

        # First try to extract script section for Vue SFC
        script_match = re.search(r'<script.*?>(.*?)</script>', code, re.DOTALL)
        if script_match:
            code = script_match.group(1).strip()

        # Look for imports
        import_patterns = [
            # dynamic imports
            r'(?:import|require)\s*\(\s*[\'"](@?[\w-]+(?:/[\w-]+)*)[\'"]',
            # static imports
            r'(?:import|from)\s+[\'"](@?[\w-]+(?:/[\w-]+)*)[\'"]',
            # require statements
            r'require\s*\(\s*[\'"](@?[\w-]+(?:/[\w-]+)*)[\'"]',
        ]
        for pattern in import_patterns:
            matches = re.finditer(pattern, code)
            for match in matches:
                pkg_name = match.group(1)
                if not pkg_name.startswith('.'):
                    if pkg_name.startswith('@'):
                        parts = pkg_name.split('/')
                        if len(parts) >= 2:
                            packages.setdefault('/'.join(parts[:2]), []).append(pkg_name)
                    else:
                        packages.setdefault(pkg_name.split('/')[0], []).append(pkg_name)

        return packages
