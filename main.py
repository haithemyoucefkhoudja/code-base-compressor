import os
import glob
import json
import argparse
import tiktoken
from analyzer.extractors.usages import extract_usages
from analyzer.processing.aggregators import group_and_filter
from analyzer.processing.cleaning import clean_call_patterns, clean_jsx_patterns, clean_constant_patterns

def count_tokens(files, model="gpt-4", exclude_dts=False):
    """Count the total number of tokens in the given files using tiktoken."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    
    total_tokens = 0
    for file_path in files:
        if exclude_dts and file_path.endswith(".d.ts"):
            continue
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                total_tokens += len(encoding.encode(content))
        except Exception as e:
            print(f"Error counting tokens for {file_path}: {e}")
    return total_tokens

def load_config(config_path: str, cli_args: argparse.Namespace) -> dict:
    """Load configuration from a JSON file and merge with CLI defaults."""
    # Default configuration
    config = {
        "patterns": ["**/*.ts", "**/*.tsx", "**/*.js", "**/*.jsx"],
        "exclude_dirs": ["node_modules", ".next", "dist", "build", ".git"],
        "exclude_dts": False,
        "threshold_percent": 0.25,
        "min_freq": 2,
        "model": "gpt-4"
    }
    
    # Load from JSON file if provided
    if config_path:
        if os.path.exists(config_path):
            print(f"Loading configuration from {config_path}...")
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    config.update(file_config)
            except Exception as e:
                print(f"Error loading config file: {e}. Using defaults.")
        else:
            print(f"Warning: Configuration file {config_path} not found. Using defaults.")

    # CLI arguments override config file
    if cli_args.exclude_dts:
        config["exclude_dts"] = True

    return config

def main():
    parser = argparse.ArgumentParser(description="Analyze a codebase for call and JSX patterns.")
    parser.add_argument("--path", default="repo", help="The path to the repository to analyze.")
    parser.add_argument("--output", help="The path to save the output JSON file. Defaults to <reponame>_patterns.json")
    parser.add_argument("--exclude-dts", action="store_true", help="Exclude .d.ts files from analysis and token count.")
    parser.add_argument("--config", help="Path to a configuration JSON file.")
    args = parser.parse_args()

    # 1. Load Configuration
    config = load_config(args.config, args)

    target_repo_path = args.path
    
    # Determine output file path
    if args.output:
        output_file_path = args.output
    else:
        repo_name = os.path.basename(os.path.abspath(target_repo_path))
        output_file_path = f"{repo_name}_patterns.json"

    print(f"Target: {os.path.abspath(target_repo_path)}")
    print(f"Using file patterns: {config['patterns']}")
    print(f"Excluding directories/patterns: {config['exclude_dirs']}")

    # 2. Scan Files
    all_raw_files = []
    for pattern in config["patterns"]:
        all_raw_files.extend(glob.glob(os.path.join(target_repo_path, pattern), recursive=True))

    # Apply configured exclusions (e.g., node_modules, .next)
    files = [
        f for f in all_raw_files 
        if not any(excluded in f for excluded in config["exclude_dirs"])
    ]
    
    if config["exclude_dts"]:
        files = [f for f in files if not f.endswith(".d.ts")]
    
    # Count tokens
    print(f"Counting tokens in {len(files)} files...")
    total_tokens = count_tokens(files, model=config["model"], exclude_dts=config["exclude_dts"])
    print(f"Total tokens in repository: {total_tokens:,}")
    
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
            calls, jsxs, cdefs, tdefs, csdefs, refs = extract_usages(file_path, source_code)
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

    # 3. Process Data: Group and filter
    call_patterns, jsx_patterns, const_patterns, ref_patterns, raw_vocab = group_and_filter(
        all_calls, all_jsxs, all_constant_defs, all_references,
        threshold_percent=config["threshold_percent"],
        min_freq=config["min_freq"]
    )
    
    # 4. Clean/Merge
    cleaned_calls = clean_call_patterns(call_patterns)
    cleaned_jsx = clean_jsx_patterns(jsx_patterns)
    cleaned_constants = clean_constant_patterns(const_patterns)
    
    # Create a set of all names already captured to avoid duplicates
    captured_names = set()
    
    cleaned_components = [comp for comp in all_component_defs]
    captured_names.update(jsx['component'] for jsx in cleaned_jsx)
    for jsx in cleaned_jsx:
        captured_names.update(jsx.get('sub_components', []))
    
    captured_names.update(typedef.name for typedef in all_type_defs)

    captured_names.update(call['chain'] for call in cleaned_calls)
    for call in cleaned_calls:
        captured_names.update(call.get('sub_patterns', []))
    
    # Filter constants: Remove if already in captured_names
    cleaned_constants = [c for c in cleaned_constants if c['constant'] not in captured_names]
    
    # Add final constants to captured names
    captured_names.update(c['constant'] for c in cleaned_constants)

    # Filter references: Remove if already in captured_names
    cleaned_references = [r for r in ref_patterns if r['name'] not in captured_names]
    
    # 5. Compress & Prepare abstract forms
    definitions = {}
    for comp in cleaned_components:
        name = comp.name
        examples = comp.code
        if name and examples:
            definitions[name] = examples

    print(f"Abstracting with {len(raw_vocab)} vocabulary terms and {len(definitions)} definitions...")
    
    for comp in cleaned_components:
        forms = set()
        sig = comp.code
        if sig: forms.add(sig)
        comp.abstract_forms = sorted(list(forms))
        if hasattr(comp, 'code'):
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
                sig = ex
                if sig: forms.add(sig)
            
            item["abstract_forms"] = sorted(list(forms))
            if "examples" in item: del item["examples"]

    # 6. Save
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
        if c.name == 'ChatProvider':
            print("c.code", c.abstract_forms)
        if c.name:
            final_output["component_definitions"].append({
                "component": c.name,
                "file": os.path.relpath(c.file, target_repo_path),
                "abstract_forms": c.abstract_forms,
                "props": c.props,
                "prop_types": c.prop_types,
                "return_type": c.return_type
            })
            
    print("Processing references...")
    
    # Process Type Definitions
    cleaned_types = []
    seen_types = set()
    for t in all_type_defs:
        key = (t.name, t.file)
        if key not in seen_types:
            cleaned_types.append({
                "name": t.name,
                "file": os.path.relpath(t.file, target_repo_path),
                "code": t.code
            })
            seen_types.add(key)

    with open(output_file_path, "w", encoding='utf-8') as f:
        final_output["type_definitions"] = cleaned_types
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