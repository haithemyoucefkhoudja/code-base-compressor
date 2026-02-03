import os
import sys
from analyzer.extractors.usages import extract_usages

# Setup paths
WORKSPACE_ROOT = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_blimpt"
TARGET_FILE = os.path.join(WORKSPACE_ROOT, "components", "shortcut-ui", "message-list.tsx")

with open("debug_integration_results.txt", "w", encoding="utf-8") as out:
    out.write(f"--- Debugging Extraction Integration ---\n")
    out.write(f"Target File: {TARGET_FILE}\n")

    # Read source
    with open(TARGET_FILE, 'rb') as f:
        source_code = f.read()

    # Run extraction
    out.write("Running extract_usages...\n")
    try:
        calls, jsxs, cdefs, tdefs, csdefs, refs = extract_usages(TARGET_FILE, source_code)
        
        # DEBUG: Check imports extraction
        out.write("\nRunning extract_js_imports...\n")
        from analyzer.extractors.imports import extract_js_imports
        imports = extract_js_imports(source_code.decode('utf-8'))
        out.write(f"Extracted Imports: {imports}\n")
        
        out.write(f"\nExtracted {len(jsxs)} JSX usages.\n")
        
        # Check MessageBox
        found_mbox = False
        for jsx in jsxs:
            if jsx.name == "MessageBox":
                found_mbox = True
                out.write(f"\n[MessageBox Usage]\n")
                out.write(f"Line: {jsx.line}\n")
                out.write(f"Source Import: {jsx.source_import}\n")
                out.write(f"Prop Types: {jsx.prop_types}\n")
                
                # Validation
                if jsx.prop_types.get("message") == "Message":
                    out.write("SUCCESS: 'message' prop has type 'Message'\n")
                else:
                    out.write(f"FAILURE: 'message' prop has type '{jsx.prop_types.get('message')}' (Expected 'Message')\n")
                    
        if not found_mbox:
            out.write("\nFAILURE: MessageBox usage not found!\n")

    except Exception as e:
        out.write(f"\nEXCEPTION: {e}\n")
        import traceback
        out.write(traceback.format_exc())
