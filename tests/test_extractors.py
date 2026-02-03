from analyzer.extractors.usages import extract_usages
import pytest
# --- Tests for extract_usages ---

@pytest.fixture
def mock_fs(tmp_path):
    """Creates a temporary file system structure for usage extraction tests."""
    (tmp_path / "src").mkdir()
    
    # A component file
    (tmp_path / "src" / "Button.tsx").write_text("""
        import React from 'react';
        import { cn } from '../lib/utils';
        
        export const Button = ({ className, children }) => {
            return <button className={cn("p-2", className)}>{children}</button>;
        }
        
        function HelperComponent() {
            return <span>Help</span>
        }
    """)
    
    # A file that uses the component and other libraries
    (tmp_path / "src" / "app.tsx").write_text("""
        import { Button } from './Button';
        import { z } from 'zod';
        import { db } from './db';

        const schema = z.object({ name: z.string().min(1) });

        function Page() {
            const result = db.select().from("users").all();
            
            return (
                <div>
                    <h1>My App</h1>
                    <Button className="primary">Click Me</Button>
                    <Button>Cancel</Button>
                </div>
            );
        }
    """)
    return tmp_path

def test_extract_usages_from_file(mock_fs):
    file_path = str(mock_fs / "src" / "app.tsx")
    with open(file_path, 'rb') as f:
        source_code = f.read()
        
    calls, jsxs, cdefs, _, _, _ = extract_usages(file_path, source_code)
    for call in calls:
        print(call.chain)
    # Test Calls
    assert len(calls) == 6
    call_chains = [c.chain for c in calls]
    assert "z.object" in call_chains
    assert "z.string.min" in call_chains
    assert "db.select.from.all" in call_chains
    
    # Test JSX
    assert len(jsxs) == 2
    jsx_names = [j.name for j in jsxs]
    assert jsx_names.count("Button") == 2
    
    button_jsx = next(j for j in jsxs if j.name == "Button" and j.props)
    assert "className" in button_jsx.props
    assert button_jsx.has_children == True

    # Test Component Definitions
    # In app.tsx, `Page` is a component definition
    assert len(cdefs) == 1
    assert cdefs[0].name == "Page"

def test_extract_component_definition(mock_fs):
    file_path = str(mock_fs / "src" / "Button.tsx")
    with open(file_path, 'rb') as f:
        source_code = f.read()

    _, _, cdefs, _, _, _ = extract_usages(file_path, source_code)
    
    # `Button` and `HelperComponent` should be detected
    assert len(cdefs) == 2
    cdef_names = [c.name for c in cdefs]
    assert "Button" in cdef_names
    assert "HelperComponent" in cdef_names