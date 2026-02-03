from typing import List, Dict, Any, Set
from collections import defaultdict
import json

def clean_call_patterns(call_patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merges call patterns based on their root (regardless of import path)."""
    grouped_calls = {}
    for item in call_patterns:
        chain = item['chain']
        source_import = item['source_import']
        # Determine Root
        if '.' in chain:
            root = chain.split('.')[0]
        else:
            root = chain

        # Group by ROOT ONLY (merge different import paths)
        key = root
        if key not in grouped_calls:
            grouped_calls[key] = {
                "chain": root,
                "source_import": source_import,  # Primary import (first seen)
                "source_imports": set(),  # All imports seen
                "frequency": 0,
                "files": set(),
                "examples": [],
                "sub_patterns": [],
                "signature": None,  # Type signature from .d.ts
                "call_variations": []  # Actual call patterns with their values
            }
        
        # Track all source imports
        grouped_calls[key]["source_imports"].add(source_import)
        
        # Merge Data
        grouped_calls[key]["frequency"] += len(item["usages"])
        grouped_calls[key]["files"].update(u.file for u in item["usages"])
        grouped_calls[key]["examples"].extend(u.code for u in item["usages"])
        grouped_calls[key]["sub_patterns"].append(chain)
        
        for u in item["usages"]:
            # Extract signature from first usage that has it
            if u.dts_signature and grouped_calls[key]["signature"] is None:
                grouped_calls[key]["signature"] = u.dts_signature
            
            # Construct call variation (actual values passed)
            # u.prop_types is {0: type, 1: type} or {0: dict_of_props, ...}
            if not u.prop_types:
                sig = []
            else:
                max_idx = max([int(k) for k in u.prop_types.keys()] + [-1])
                sig = []
                for i in range(max_idx + 1):
                    val = u.prop_types.get(str(i), "unknown")
                    sig.append(val)  # val can be string or dict
            
            # Convert sig to JSON string for comparison (handles dicts)
            sig_key = json.dumps(sig, sort_keys=True)
            
            # Add to call_variations
            found = False
            for var in grouped_calls[key]["call_variations"]:
                var_key = json.dumps(var["args"], sort_keys=True)
                if var_key == sig_key:
                    var["count"] += 1
                    found = True
                    break
            if not found:
                grouped_calls[key]["call_variations"].append({ "args": sig, "count": 1 })

    # Reconstruct Call List
    cleaned_calls = []
    for key, details in grouped_calls.items():
        details["files"] = list(details["files"])
        details["examples"] = list(set(details["examples"]))
        # Convert source_imports set to list and pick first as primary
        source_imports = list(details["source_imports"])
        if len(source_imports) > 1:
            details["source_imports"] = source_imports
        else:
            del details["source_imports"]  # Remove if only one
        # Sort call_variations by count
        details["call_variations"].sort(key=lambda x: x["count"], reverse=True)
        # Remove signature if None
        if details["signature"] is None:
            del details["signature"]
        cleaned_calls.append(details)

    cleaned_calls.sort(key=lambda x: x['frequency'], reverse=True)
    return cleaned_calls

def clean_jsx_patterns(jsx_patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merges JSX patterns based on component prefixes and source import."""
    
    all_components = [item['name'] for item in jsx_patterns]
    all_components.sort(key=len)

    parent_map = {}
    for comp in all_components:
        parent = comp
        for candidate in all_components:
            if candidate == comp:
                continue
            if len(candidate) > len(comp):
                break
            
            if comp.startswith(candidate):
                remainder = comp[len(candidate):]
                if remainder and remainder[0].isupper():
                    parent = candidate
                    if candidate in parent_map:
                        parent = parent_map[candidate]
                    break 
        parent_map[comp] = parent

    grouped_jsx = {}
    for item in jsx_patterns:
        comp_name = item['name']
        source_import = item['source_import']
        root = parent_map.get(comp_name, comp_name)

        key = (root, source_import)
        if key not in grouped_jsx:
            grouped_jsx[key] = {
                "component": root,
                "source_import": source_import,
                "frequency": 0,
                "common_props": set(),
                "files": set(),
                "examples": [],
                "sub_components": [],
                "shapes": [] # List of { "props": {"prop": "type"}, "count": 1 }
            }

        grouped_jsx[key]["frequency"] += len(item["usages"])
        grouped_jsx[key]["common_props"].update(prop for u in item["usages"] for prop in u.props)
        grouped_jsx[key]["files"].update(u.file for u in item["usages"])
        grouped_jsx[key]["examples"].extend(u.code for u in item["usages"])
        grouped_jsx[key]["sub_components"].append(comp_name)
        
        for u in item["usages"]:
            # Shape for JSX is the prop_types map
            # Sort keys to ensure stability
            sig = u.prop_types # dict of prop -> type
            
            # Simple list-based check might fail with dicts, so we iterate
            found = False
            for shape in grouped_jsx[key]["shapes"]:
                if shape["props"] == sig:
                    shape["count"] += 1
                    found = True
                    break
            if not found:
                 grouped_jsx[key]["shapes"].append({ "props": sig, "count": 1 })

    cleaned_jsx = []
    for key, details in grouped_jsx.items():
        details["common_props"] = list(details["common_props"])
        details["files"] = list(details["files"])
        details["examples"] = list(set(details["examples"]))
        details["shapes"].sort(key=lambda x: x["count"], reverse=True)
        cleaned_jsx.append(details)

    cleaned_jsx.sort(key=lambda x: x['frequency'], reverse=True)
    return cleaned_jsx

def clean_constant_patterns(constant_patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merges constant patterns based on their root and source import."""
    grouped_constants = {}
    for item in constant_patterns:
        name = item['name']
        source_import = item['source_import']
        
        # Determine Root
        if '.' in name:
            root = name.split('.')[0]
        else:
            root = name

        key = (root, source_import)
        if key not in grouped_constants:
            grouped_constants[key] = {
                "constant": root,
                "source_import": source_import,
                "frequency": 0,
                "files": set(),
                "examples": [],
                "sub_patterns": []
            }
        
        # Merge Data
        grouped_constants[key]["frequency"] += len(item["usages"])
        grouped_constants[key]["files"].update(u.file for u in item["usages"])
        grouped_constants[key]["examples"].extend(u.code for u in item["usages"])
        grouped_constants[key]["sub_patterns"].append(name)

    # Reconstruct Constant List
    cleaned_constants = []
    for key, details in grouped_constants.items():
        details["files"] = list(details["files"])
        details["examples"] = list(set(details["examples"]))
        cleaned_constants.append(details)

    cleaned_constants.sort(key=lambda x: x['frequency'], reverse=True)
    return cleaned_constants

