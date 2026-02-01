import pytest
from analyzer.models import CallUsage, JSXUsage
from analyzer.processing.aggregators import group_and_filter
from analyzer.processing.cleaning import clean_call_patterns, clean_jsx_patterns

# --- Mock Data ---

def create_mock_call(chain, file, deps=None):
    if deps is None:
        deps = [d.split('.')[0] for d in chain.split('.')]
    return CallUsage(chain=chain, file=file, code=f"{chain}()", line=1, structure="", source_import="", context=[], extension=".ts")

def create_mock_jsx(name, file, props=None, deps=None):
    if props is None:
        props = ["prop1"]
    if deps is None:
        deps = [name]
    return JSXUsage(name=name, file=file, props=props, code=f"<{name} />", line=1, has_children=False, source_import="", context=[], extension=".tsx")

@pytest.fixture
def mock_usages():
    all_calls = [
        # To be merged into 'z'
        create_mock_call("z.string.min", "file1.ts", deps=["zod"]),
        create_mock_call("z.string.min", "file2.ts", deps=["zod"]),
        create_mock_call("z.string.max", "file1.ts", deps=["zod"]),
        create_mock_call("z.number", "file2.ts", deps=["zod"]),
        # To be merged into 'db'
        create_mock_call("db.select", "file1.ts", deps=["drizzle"]),
        create_mock_call("db.select", "file2.ts", deps=["drizzle"]),
        # Standalone, high frequency
        create_mock_call("cn", "file1.ts", deps=["clsx"]),
        create_mock_call("cn", "file2.ts", deps=["clsx"]),
        create_mock_call("cn", "file3.ts", deps=["clsx"]),
        # Low frequency, should be filtered out
        create_mock_call("React.useState", "file3.ts", deps=["react"]),
    ]
    
    all_jsxs = [
        # To be merged into 'Card'
        create_mock_jsx("Card", "file1.tsx", props=["p1"], deps=["@/components/ui/card"]),
        create_mock_jsx("CardHeader", "file1.tsx", props=["p2"], deps=["@/components/ui/card"]),
        create_mock_jsx("CardTitle", "file1.tsx", props=["p3"], deps=["@/components/ui/card"]),
        # To be merged into 'Button'
        create_mock_jsx("Button", "file2.tsx", props=["variant"], deps=["@/components/ui/button"]),
        create_mock_jsx("Button", "file3.tsx", props=["size"], deps=["@/components/ui/button"]),
        # Standalone, should be filtered out
        create_mock_jsx("Avatar", "file3.tsx", props=["src"], deps=["@/components/ui/avatar"]),
    ]
    return all_calls, all_jsxs

# --- Tests for aggregators.py ---

def test_group_and_filter(mock_usages):
    all_calls, all_jsxs = mock_usages
    
    # Use a threshold that should filter out React.useState and Avatar
    # Frequencies: z:3, db:2, cn:3, React:1 | Card:3, Button:2, Avatar:1
    # Total items: 7. Median will be 3. Threshold = max(2, 3*0.25) = 2.
    # So, anything with frequency < 2 will be filtered.
    
    call_patterns, jsx_patterns, vocab = group_and_filter(all_calls, all_jsxs, threshold_percent=0.25)
    call_chains = [p["chain"] for p in call_patterns]
    assert "z.string.min" in call_chains
    assert "db.select" in call_chains
    assert "cn" in call_chains
    assert "React.useState" not in call_chains # Filtered out
    
    jsx_names = [p["name"] for p in jsx_patterns]
    assert "Card" not in jsx_names
    assert "Button" in jsx_names
    assert "Avatar" not in jsx_names # Filtered out

    # Test vocab
    assert "z" in vocab
    assert "db" in vocab
    assert "cn" in vocab
    assert "z.string.min" in vocab
    assert "db.select" in vocab
    assert "Button" in vocab

# --- Tests for cleaning.py ---

def test_clean_call_patterns(mock_usages):
    all_calls, _ = mock_usages
    call_patterns, _, _ = group_and_filter(all_calls, [], threshold_percent=0.1)
    
    cleaned_calls = clean_call_patterns(call_patterns)
    
    # Should be grouped into 'z', 'db', and 'cn'
    assert len(cleaned_calls) == 3
    
    z_pattern = next(p for p in cleaned_calls if p["chain"] == "z")
    assert z_pattern["frequency"] == 2
    assert "zod" in z_pattern["dependencies"]
    
    db_pattern = next(p for p in cleaned_calls if p["chain"] == "db")
    assert db_pattern["frequency"] == 2
    assert "drizzle" in db_pattern["dependencies"]

def test_clean_jsx_patterns(mock_usages):
    _, all_jsxs = mock_usages
    _, jsx_patterns, _ = group_and_filter([], all_jsxs, threshold_percent=0.1)

    cleaned_jsx = clean_jsx_patterns(jsx_patterns)
    
    # Should be grouped into 'Card' and 'Button'
    assert len(cleaned_jsx) == 1
    
    button_pattern = next(p for p in cleaned_jsx if p["component"] == "Button")
    assert button_pattern["frequency"] == 2
    assert "variant" in button_pattern["common_props"]
    assert "size" in button_pattern["common_props"]
