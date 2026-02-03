from analyzer.extractors.usages import extract_usages
import pytest
import os

@pytest.fixture
def mock_dts_fs(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "dist-types").mkdir()
    (tmp_path / "dist-types" / "src").mkdir()
    
    # Source Component (Untyped or partial)
    source_file = tmp_path / "src" / "Comp.tsx"
    source_file.write_text("""
    import React from 'react';
    export const Comp = ({ label, count }) => {
        return <div>{label}</div>
    }
    """)
    
    # DTS File (Typed)
    dts_file = tmp_path / "dist-types" / "src" / "Comp.d.ts"
    dts_file.write_text("""
    import * as React from 'react';
    export declare const Comp: ({ label, count }: { label: string; count: number }) => import("react/jsx-runtime").JSX.Element;
    """)
    
    return tmp_path

def test_dts_integration(mock_dts_fs):
    file_path = str(mock_dts_fs / "src" / "Comp.tsx")
    with open(file_path, 'rb') as f:
        source = f.read()
        
    # The integration relies on find_dts_file finding the parallel folder.
    # verify extract_usages picks it up
    _, _, cdefs, _, _, _ = extract_usages(file_path, source)
    
    comp = next(c for c in cdefs if c.name == "Comp")
    
    # Without DTS, these would be empty strings or unknown inferred types
    # With DTS, they should be string and number
    assert comp.prop_types.get("label") == "string"
    assert comp.prop_types.get("count") == "number"
    assert "label" in comp.props
    assert "count" in comp.props
