from tree_sitter import Parser, Language
import tree_sitter_javascript
import tree_sitter_typescript

JS_LANGUAGE = Language(tree_sitter_javascript.language())
TS_LANGUAGE = Language(tree_sitter_typescript.language_typescript())
TSX_LANGUAGE = Language(tree_sitter_typescript.language_tsx())
JSX_LANGUAGE = Language(tree_sitter_typescript.language_tsx())
JS_PARSER = Parser(JS_LANGUAGE)
TS_PARSER = Parser(TS_LANGUAGE)
TSX_PARSER = Parser(TSX_LANGUAGE)
JSX_PARSER = Parser(JSX_LANGUAGE)

def get_parser(path: str) -> Parser:
    if path.endswith(".tsx"): return TSX_PARSER
    if path.endswith(".ts"): return TS_PARSER
    if path.endswith(".jsx"): return JSX_PARSER
    return JS_PARSER
