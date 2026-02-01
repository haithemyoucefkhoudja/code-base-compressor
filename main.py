
from ast import List
from analyzer.abstract import AbstractGenerator
import os
import glob
import json
import argparse
from analyzer.config import PATTERNS
from analyzer.extractors.usages import extract_usages
from analyzer.processing.aggregators import group_and_filter
from analyzer.processing.cleaning import clean_call_patterns, clean_jsx_patterns, clean_constant_patterns

def main():
    parser = argparse.ArgumentParser(description="Analyze a codebase for call and JSX patterns.")
    parser.add_argument("--path", default="repo", help="The path to the repository to analyze.")
    parser.add_argument("--output", help="The path to save the output JSON file. Defaults to <reponame>_patterns.json")
    args = parser.parse_args()

    target_repo_path = args.path
    
    # Determine output file path
    if args.output:
        output_file_path = args.output
    else:
        repo_name = os.path.basename(os.path.abspath(target_repo_path))
        output_file_path = f"{repo_name}_patterns.json"

    print(f"Target: {os.path.abspath(target_repo_path)}")

    # 1. Scan Files
    files = []
    for pattern in PATTERNS:
        files.extend(glob.glob(os.path.join(target_repo_path, pattern), recursive=True))

    files = [f for f in files if "node_modules" not in f and ".next" not in f]
    
    all_calls = []
    all_jsxs = []
    all_component_defs = []
    all_type_defs = []
    all_constant_defs = []
    all_references = []

    print(f"Scanning {len(files)} files...")
    for file_path in files:
        try:
            with open(file_path, 'rb') as f:
                source_code = f.read()
            calls, jsxs, cdefs, tdefs,csdefs,refs = extract_usages(file_path, source_code)
            all_calls.extend(calls)
            all_jsxs.extend(jsxs)
            all_component_defs.extend(cdefs)
            all_type_defs.extend(tdefs)
            all_constant_defs.extend(csdefs)
            all_references.extend(refs)
        except Exception as e:
            print(f"Skipping {file_path}: {e}")

    print("=" * 80)
    print(f"Extracted {len(all_calls)} call usages, {len(all_jsxs)} JSX usages. {len(all_component_defs)} component definitions, {len(all_type_defs)} type definitions.")

    # 2. Process Data: Group and filter
    call_patterns, jsx_patterns, const_patterns, ref_patterns, raw_vocab = group_and_filter(all_calls, all_jsxs, all_constant_defs, all_references)
    
    # 3. Clean/Merge
    cleaned_calls = clean_call_patterns(call_patterns)
    cleaned_jsx = clean_jsx_patterns(jsx_patterns)
    cleaned_constants = clean_constant_patterns(const_patterns)
    cleaned_components = all_component_defs
    # Create a set of all names already captured to avoid duplicates
    captured_names = set()
    captured_names.update(jsx['component'] for jsx in cleaned_jsx)
    for jsx in cleaned_jsx:
        captured_names.update(jsx.get('sub_components', []))
    
    captured_names.update(call['chain'] for call in cleaned_calls)
    for call in cleaned_calls:
        captured_names.update(call.get('sub_patterns', []))
    
    captured_names.update(comp.name for comp in cleaned_components)

    # Filter constants: Remove if already in captured_names
    cleaned_constants = [c for c in cleaned_constants if c['constant'] not in captured_names]
    
    # Add final constants to captured names
    captured_names.update(c['constant'] for c in cleaned_constants)

    # Filter references: Remove if already in captured_names
    cleaned_references = [r for r in ref_patterns if r['name'] not in captured_names]
    

    # 4. compress
    definitions = {}
    
    for comp in cleaned_components:
        name = comp.name
        examples = comp.code
        if name and examples:
            definitions[name] = examples

    # for p in cleaned_calls: raw_vocab.add(p["chain"])
    # for p in cleaned_jsx: raw_vocab.add(p["component"])
    # for p in cleaned_components: raw_vocab.add(p["component"])
    # raw_vocab.update(definitions.keys())

    abstractor = AbstractGenerator(raw_vocab, definitions)
    print(f"Abstracting with {len(raw_vocab)} vocabulary terms and {len(definitions)} definitions...")

    # 3. Process
    
    for comp in cleaned_components:
        forms = set()
        sig = abstractor.generate(comp.code)
        if sig: forms.add(sig)
        comp.abstract_forms = sorted(list(forms))
        del comp.code

    sections = ["call_patterns", "jsx_patterns"]
    for key in sections:
        items = cleaned_calls if key == "call_patterns" else cleaned_jsx
        print(f"Processing {len(items)} items in {key}...")
        for item in items:
            forms = set()
            examples = item.get("examples")
            if examples is None:
                raise ValueError(f"Examples not found for item: {item}")
            for ex in examples:
                sig = abstractor.generate(ex)
                if sig: forms.add(sig)
            
            item["abstract_forms"] = sorted(list(forms))
            if "examples" in item: del item["examples"]

    # 5. Save
    summary = {
        "total_calls": sum(x['frequency'] for x in cleaned_calls),
        "total_jsx": sum(x['frequency'] for x in cleaned_jsx),
        "total_constants": sum(x['frequency'] for x in cleaned_constants),
        "unique_call_chains": len(cleaned_calls),
        "unique_components": len(cleaned_jsx),
        "unique_constants": len(cleaned_constants),
        "unique_references": len(cleaned_references),
    }

    final_output = {
        "summary": summary,
        "vocabulary": raw_vocab,
        "call_patterns": cleaned_calls,
        "jsx_patterns": cleaned_jsx,
        "constant_patterns": cleaned_constants,
        "reference_patterns": cleaned_references,
        "component_definitions": []
        
    }
    for c in cleaned_components:
        if c.name not in raw_vocab:
            final_output["component_definitions"].append({
                "component": c.name,
                "file": os.path.relpath(c.file, target_repo_path),
                "abstract_forms": c.abstract_forms,
                "props":c.props
            })
    print("Processing references...")
    
    
    with open(output_file_path, "w", encoding='utf-8') as f:
        json.dump(final_output, f, indent=2)

    print("=" * 80)
    print("Successfully cleaned and processed patterns.")
    print(f"Call patterns reduced to {len(cleaned_calls)}")
    print(f"JSX patterns reduced to {len(cleaned_jsx)}")
    print(f"Constant patterns reduced to {len(cleaned_constants)}")
    print(f"Reference patterns reduced to {len(cleaned_references)}")
    print(f"Exported to {output_file_path}")

if __name__ == "__main__":
    main()