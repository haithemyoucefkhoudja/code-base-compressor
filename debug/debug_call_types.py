import os
from analyzer.core.dts_provider import parse_dts_definitions

# Clear the LRU cache to force re-parsing
parse_dts_definitions.cache_clear()

# Test parsing chat-provider.d.ts for handleFormSubmit
DTS_PATH = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_blimpt\dist-types\providers\chat-provider.d.ts"

with open("debug_call_types.txt", "w", encoding="utf-8") as out:
    out.write("--- Debugging Call Argument Type Enrichment ---\n\n")
    
    # Step 1: Test parse_dts_definitions on chat-provider.d.ts
    out.write("Step 1: Parsing chat-provider.d.ts\n")
    defs = parse_dts_definitions(DTS_PATH)
    out.write(f"Found {len(defs)} definitions\n\n")
    
    # Show all definitions with parameters
    out.write("Functions with parameters:\n")
    for name, info in defs.items():
        if info.get("parameters"):
            out.write(f"  {name}: params={info.get('parameters')}, ret={info.get('return_type')}\n")
    
    # Step 2: Check if handleFormSubmit is parsed
    out.write("\nStep 2: Looking for handleFormSubmit\n")
    hfs = defs.get("handleFormSubmit")
    if hfs:
        out.write(f"SUCCESS: Found handleFormSubmit\n")
        out.write(f"  Parameters: {hfs.get('parameters')}\n")
        out.write(f"  Return Type: {hfs.get('return_type')}\n")
    else:
        out.write("FAILURE: handleFormSubmit not found in definitions\n")
        out.write(f"Available keys: {list(defs.keys())}\n")
