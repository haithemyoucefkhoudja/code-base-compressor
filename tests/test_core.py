from analyzer.core.languages import JS_PARSER, TSX_PARSER
from analyzer.core.node_utils import get_full_chain, get_jsx_props, get_jsx_name, get_constant_name


def test_find_identifier():
    code = b"""const a = 1;
    function call(constant){
        return constant;
    }
    call(a)
    """
    tree = JS_PARSER.parse(code)
    
    # helper to find all nodes of a certain type
    def find_nodes(node, node_type, results):
        if node.type == node_type:
            results.append(node)
        for child in node.children:
            find_nodes(child, node_type, results)
    
    identifiers = []
    find_nodes(tree.root_node, "identifier", identifiers)
    
    names = [code[n.start_byte:n.end_byte].decode('utf-8') for n in identifiers]
    
    # Expected identifiers in order: 
    # 'a' (decl), 'call' (fn name), 'constant' (param), 'constant' (usage), 'call' (usage), 'a' (usage)
    assert "a" in names
    assert "call" in names
    assert "constant" in names
    assert names.count("constant") == 2

def test_find_global_constant():
    code = b"""const a = 1;
    function call(constant){
        return constant;
    }
    call(a)
    """
    tree = JS_PARSER.parse(code)
    
    constants = []
    # Only iterate through top-level nodes of the program
    for node in tree.root_node.children:
        if node.type == "lexical_declaration":
            # Check if it's a 'const'
            kind = node.child_by_field_name("kind")
            if kind and code[kind.start_byte:kind.end_byte] == b"const":
                # Find variable_declarator
                for child in node.children:
                    if child.type == "variable_declarator":
                        name_node = child.child_by_field_name("name")
                        if name_node and name_node.type == "identifier":
                            name = code[name_node.start_byte:name_node.end_byte].decode('utf-8')
                            constants.append(name)
    
    assert constants == ["a"]

def test_find_constants():
    code = b"const a = 1;"
    tree = JS_PARSER.parse(code)
    assert get_constant_name(tree.root_node.child(0),code) == "a"

# --- Tests for get_full_chain ---
def test_get_full_chain_simple():
    code = b"myFunction()"
    tree = JS_PARSER.parse(code)
    
    # root -> expression_statement -> call_expression
    expr_stmt = tree.root_node.child(0)
    call_node = expr_stmt.child(0)
    
    assert call_node is not None
    assert call_node.type == "call_expression"
    
    func_node = call_node.child_by_field_name("function")
    assert func_node is not None
    assert get_full_chain(func_node, code) == "myFunction"

def test_get_full_chain_member_access():
    code = b"console.log('hello')"
    tree = JS_PARSER.parse(code)
    
    # root -> expression_statement -> call_expression
    expr_stmt = tree.root_node.child(0)
    call_node = expr_stmt.child(0)
    
    assert call_node is not None
    func_node = call_node.child_by_field_name("function")
    assert func_node is not None
    assert get_full_chain(func_node, code) == "console.log"

def test_get_full_chain_deeply_nested():
    code = b"a.b.c.d.e.f()"
    tree = JS_PARSER.parse(code)
    
    # root -> expression_statement -> call_expression
    expr_stmt = tree.root_node.child(0)
    call_node = expr_stmt.child(0)
    
    assert call_node is not None
    func_node = call_node.child_by_field_name("function")
    assert func_node is not None
    assert get_full_chain(func_node, code) == "a.b.c.d.e.f"

def test_get_full_chain_from_chained_calls():
        # createServerAction().input().handler()
        code = b"createServerAction().input().handler()"
        tree = JS_PARSER.parse(code)
        
        # tree.root_node is (program)
        # tree.root_node.child(0) is (expression_statement)
        expression_stmt = tree.root_node.child(0)
        
        # You need to go one level deeper to get the (call_expression)
        outer_call = expression_stmt.child(0)
        
        assert outer_call is not None
        assert outer_call.type == "call_expression"
        
        outer_func = outer_call.child_by_field_name("function")
        assert outer_func is not None

# --- Tests for get_jsx_name and get_jsx_props ---

def test_get_jsx_self_closing():
    code = b'<MyComponent prop1="hello" prop2={world} />'
    tree = TSX_PARSER.parse(code)
    
    # tree.root_node is (program)
    # child(0) is (expression_statement)
    expression_stmt = tree.root_node.child(0)
    
    # The actual JSX node is inside the statement
    jsx_node = expression_stmt.child(0)
    
    assert jsx_node is not None
    assert jsx_node.type == "jsx_self_closing_element"
    assert get_jsx_name(jsx_node, code) == "MyComponent"
    props = get_jsx_props(jsx_node, code)
    assert "prop1" in props
    assert "prop2" in props

def test_get_jsx_with_children():
    code = b'<DataProvider client={db}><App /></DataProvider>'
    tree = TSX_PARSER.parse(code)
    
    expression_stmt = tree.root_node.child(0)
    jsx_node = expression_stmt.child(0)
    
    assert jsx_node is not None
    assert jsx_node.type == "jsx_element"
    assert get_jsx_name(jsx_node, code) == "DataProvider"
    props = get_jsx_props(jsx_node, code)
    assert "client" in props
    assert len(props) == 1
    
def test_get_jsx_member_expression_name():
    code = b'<Components.Button variant="primary" />'
    tree = TSX_PARSER.parse(code)
    
    expression_stmt = tree.root_node.child(0)
    jsx_node = expression_stmt.child(0)
    
    assert jsx_node is not None
    # The input code is self-closing <... /> so the type is jsx_self_closing_element
    assert jsx_node.type == "jsx_self_closing_element"
    assert get_jsx_name(jsx_node, code) == "Components.Button"
    props = get_jsx_props(jsx_node, code)
    assert "variant" in props