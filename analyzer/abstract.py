import tree_sitter_typescript
from tree_sitter import Language, Parser
from typing import List, Union, Set, Dict
# ==========================================
# 1. SETUP
# ==========================================
TSX_LANGUAGE = Language(tree_sitter_typescript.language_tsx())
PARSER = Parser(TSX_LANGUAGE)

class AbstractGenerator:
    def __init__(self, vocabulary: List[str] = [], definitions: Dict[str, str] = {}):
        self.parser = PARSER
        self.vocabulary = vocabulary
        self.definitions = definitions
        self.inlining_stack = set()
        
        self.protected_globals = {
            "React", "console", "Error", "Promise", "Object", "Array", "JSON",
            "Math", "Date", "Map", "Set", "await", "null", "undefined", "true", "false",
            "window", "document", "process", "items", "map", "filter", "length", "push"
        }

    def get_text(self, node, source_bytes):
        if not node: return ""
        try:
            text = source_bytes[node.start_byte:node.end_byte].decode('utf-8').strip()
            return " ".join(text.split())
        except:
            return ""

    def generate(self, code_snippet: str) -> str:
        if not code_snippet: return ""
        try:
            source_bytes = bytes(code_snippet, "utf8", "replace")
            tree = self.parser.parse(source_bytes)
            return self._abstract_node(tree.root_node, source_bytes).strip()
        except Exception:
            return ""

    def generate_body(self, code_snippet: str) -> str:
        """Extracts and abstracts ONLY the body of a function/component definition."""
        if not code_snippet: return ""
        try:
            source_bytes = bytes(code_snippet, "utf8", "replace")
            tree = self.parser.parse(source_bytes)
            
            def find_func(n):
                if n.type in ("function_declaration", "arrow_function", "function_expression", "method_definition"):
                    return n
                for c in n.children:
                    res = find_func(c)
                    if res: return res
                return None

            func_node = find_func(tree.root_node)
            if func_node:
                # Try field first, then scan children for block
                body = func_node.child_by_field_name("body")
                if not body:
                    for child in func_node.children:
                        if child.type == "statement_block":
                            body = child
                            break
                
                if body:
                    return self._abstract_node(body, source_bytes).strip()
            
            # Fallback
            return self._abstract_node(tree.root_node, source_bytes).strip()
        except Exception:
            return ""

    def _abstract_node(self, node, source_bytes) -> str:
        if not node: return ""

        # --- 1. EXPLICIT SKIP LIST ---
        if node.type in ("comment", ";", ",", "[", "]"):
            return ""

        # --- 2. JSX (Priority) ---
        if node.type in ["jsx_element", "jsx_self_closing_element", "jsx_fragment"]:
            return self._abstract_jsx(node, source_bytes)

        # --- 3. FUNCTION DEFINITIONS ---
        if node.type in ("function_declaration", "arrow_function", "function_expression", "method_definition"):
            # Robust Body Finding: Field OR Child Scan
            body = node.child_by_field_name("body")
            if not body:
                for child in node.children:
                    if child.type == "statement_block":
                        body = child
                        break
            
            if body: 
                return f"fn() => {{ {self._abstract_node(body, source_bytes)} }}"
            
            # If no body found (e.g. declare function), return empty or signature
            return "fn"

        # --- 4. CALLS & CHAINS ---
        if node.type in ("call_expression", "new_expression"):
            return self._abstract_call(node, source_bytes)

        # --- 5. WRAPPERS (Parens & Return) ---
        if node.type == "parenthesized_expression":
            valid_sigs = []
            for child in node.children:
                if child.type in ("(", ")", "comment"): continue
                sig = self._abstract_node(child, source_bytes)
                if sig: valid_sigs.append(sig)
            return " ".join(valid_sigs)

        if node.type == "return_statement":
            # Scan all children to find the return value
            val_sig = ""
            for child in node.children:
                if child.type not in ("return", ";", "comment"):
                    val_sig = self._abstract_node(child, source_bytes)
                    if val_sig: break 
            
            if val_sig: return f"return {val_sig}"
            return "return"

        # --- 6. FLOW CONTROL ---
        if node.type == "try_statement":
            body = node.child_by_field_name("body")
            handlers = [self._abstract_node(c, source_bytes) for c in node.children if c.type == "catch_clause"]
            return f"try {{ {self._abstract_node(body, source_bytes)} }} {' '.join(handlers)}"

        if node.type == "catch_clause":
            body = node.child_by_field_name("body")
            return f"catch {{ {self._abstract_node(body, source_bytes)} }}"

        if node.type == "if_statement":
            cond = node.child_by_field_name("condition")
            cons = node.child_by_field_name("consequence")
            alt = node.child_by_field_name("alternative")
            
            cond_sig = self._abstract_node(cond, source_bytes)
            cons_sig = self._abstract_node(cons, source_bytes)
            
            if not any(v in cond_sig for v in self.vocabulary):
                cond_sig = "?"

            res = f"if ({cond_sig}) {{ {cons_sig} }}"
            if alt:
                alt_sig = self._abstract_node(alt, source_bytes)
                if alt_sig.startswith("else") or alt_sig.startswith("if"):
                    res += f" {alt_sig}"
                else: 
                     res += f" else {{ {alt_sig} }}"
            return res

        # --- 7. BLOCKS & CONTAINERS ---
        if node.type in ("statement_block", "program", "expression_statement", "jsx_expression_container", "export_statement"):
            sigs = []
            for child in node.children:
                if child.type in ("{", "}", "export"): continue
                sig = self._abstract_node(child, source_bytes)
                if sig and sig not in ("ID", "."): sigs.append(sig)
            return " ".join(sigs)

        # --- 8. OBJECTS ---
        if node.type == "object":
            keys = []
            for child in node.children:
                if child.type == "pair":
                    key_node = child.child_by_field_name("key")
                    val_node = child.child_by_field_name("value")
                    if key_node and val_node:
                        k_txt = self.get_text(key_node, source_bytes)
                        val_sig = self._abstract_node(val_node, source_bytes)
                        
                        if self._is_frequent(k_txt) or any(c in val_sig for c in "<{("):
                            keys.append(f"{k_txt}: {val_sig}")
                        else:
                            keys.append(".")
            
            final = []
            has_dot = False
            for k in keys:
                if k == ".":
                    if not has_dot: final.append("..."); has_dot = True
                else: final.append(k)
            return f"{{ {', '.join(final)} }}"

        # --- 9. LEAFS ---
        if node.type == "member_expression":
            obj = node.child_by_field_name("object")
            prop = node.child_by_field_name("property")
            obj_sig = self._abstract_node(obj, source_bytes)
            prop_txt = self.get_text(prop, source_bytes)
            
            if not obj_sig or obj_sig in ("ID", ".", "expression"):
                return f"?.{prop_txt}" if self._is_frequent(prop_txt) else prop_txt
            return f"{obj_sig}.{prop_txt}"

        if node.type in ["identifier", "property_identifier", "shorthand_property_identifier_pattern"]:
            txt = self.get_text(node, source_bytes)
            return txt if self._is_frequent(txt) else "ID"
        
        if node.type == "string": return '""'
        if node.type == "number": return "#"

        # --- 10. FALLBACK ---
        found = []
        for child in node.children:
            sig = self._abstract_node(child, source_bytes)
            if sig and sig not in ("ID", "."): found.append(sig)
        return " ".join(found)

    def _is_frequent(self, name: str) -> bool:
        if name in self.vocabulary or name in self.protected_globals: return True
        if "." in name and name.split('.')[0] in self.vocabulary: return True
        return False

    def _abstract_call(self, node, source_bytes) -> str:
        # Extract Name
        func_node = node.child_by_field_name("function") or node.child_by_field_name("constructor")
        if not func_node: 
             for c in node.children:
                  if c.type in ("identifier", "member_expression", "call_expression"):
                       func_node = c
                       break
        
        raw_name = self.get_text(func_node, source_bytes)
        name_sig = self._abstract_node(func_node, source_bytes)
        
        # Extract Args
        args_node = node.child_by_field_name("arguments")
        arg_sigs = []
        if args_node:
            for child in args_node.children:
                if child.type not in ("(", ")", ","):
                    sig = self._abstract_node(child, source_bytes)
                    if sig and sig != "ID": arg_sigs.append(sig)

        # Inlining
        if raw_name in self.definitions and len(self.inlining_stack) < 3:
            if raw_name not in self.inlining_stack:
                self.inlining_stack.add(raw_name)
                inlined_body = self.generate_body(self.definitions[raw_name])
                self.inlining_stack.remove(raw_name)
                if inlined_body:
                    return f"exec({raw_name}) {{ {inlined_body} }}"

        args_str = ", ".join(arg_sigs)
        if not name_sig or name_sig in ("ID", "."): return f"call({args_str})"
        return f"{name_sig}({args_str})"

    def _abstract_jsx(self, node, source_bytes) -> str:
        # Fragment (Implicit or Explicit)
        if node.type == "jsx_fragment":
            children = self._get_jsx_children(node, source_bytes)
            return f"Fragment[{', '.join(children)}]"

        # Component Name
        opening = node if node.type == "jsx_self_closing_element" else node.child_by_field_name("opening_element")
        
        # Fallback if field name fails
        if not opening:
            for child in node.children:
                if child.type == "jsx_opening_element":
                    opening = child
                    break
        
        # If still no opening element, it's weird, but return fallback
        if not opening: return "<>"

        name_node = opening.child_by_field_name("name")
        
        # Fallback: scan opening element children for identifier/member_expression
        if not name_node:
            for child in opening.children:
                if child.type in ("identifier", "member_expression", "this_expression", "jsx_namespace_name"):
                    name_node = child
                    break
        
        raw_name = ""
        if name_node:
            raw_name = self.get_text(name_node, source_bytes)

        # If we have a raw name, check inlining
        if raw_name:
            if raw_name in self.definitions and len(self.inlining_stack) < 3:
                if raw_name not in self.inlining_stack:
                    self.inlining_stack.add(raw_name)
                    inlined_body = self.generate_body(self.definitions[raw_name])
                    self.inlining_stack.remove(raw_name)
                    if inlined_body:
                        return f"<{raw_name}> {{ {inlined_body} }} </{raw_name}>"
        else:
            # No name means Fragment (e.g. <>...</>)
            children = self._get_jsx_children(node, source_bytes)
            return f"Fragment[{', '.join(children)}]"

        # Standard Children
        children_sigs = []
        if node.type == "jsx_element":
            children_sigs = self._get_jsx_children(node, source_bytes)

        if children_sigs:
            return f"<{raw_name}> {', '.join(children_sigs)} </{raw_name}>"
        return f"<{raw_name} />"

    def _get_jsx_children(self, node, source_bytes) -> List[str]:
        sigs = []
        for child in node.children:
            if child.type in ("jsx_opening_element", "jsx_closing_element", "jsx_text", "<", ">", "/"): continue
            sig = self._abstract_node(child, source_bytes)
            if sig and sig not in ("ID", "."): sigs.append(sig)
        return sigs