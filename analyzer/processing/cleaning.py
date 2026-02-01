from typing import List, Dict, Any, Set
from collections import defaultdict

def clean_call_patterns(call_patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merges call patterns based on their root and source import."""
    grouped_calls = {}
    for item in call_patterns:
        chain = item['chain']
        source_import = item['source_import']
        # Determine Root
        if '.' in chain:
            root = chain.split('.')[0]
        else:
            root = chain

        key = (root, source_import)
        if key not in grouped_calls:
            grouped_calls[key] = {
                "chain": root,
                "source_import": source_import,
                "frequency": 0,
                "files": set(),
                "examples": [],
                "sub_patterns": []
            }
        
        # Merge Data
        grouped_calls[key]["frequency"] += len(item["usages"])
        grouped_calls[key]["files"].update(u.file for u in item["usages"])
        grouped_calls[key]["examples"].extend(u.code for u in item["usages"])
        grouped_calls[key]["sub_patterns"].append(chain)

    # Reconstruct Call List
    cleaned_calls = []
    for key, details in grouped_calls.items():
        details["files"] = list(details["files"])
        details["examples"] = list(set(details["examples"]))
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
                "sub_components": []
            }

        grouped_jsx[key]["frequency"] += len(item["usages"])
        grouped_jsx[key]["common_props"].update(prop for u in item["usages"] for prop in u.props)
        grouped_jsx[key]["files"].update(u.file for u in item["usages"])
        grouped_jsx[key]["examples"].extend(u.code for u in item["usages"])
        grouped_jsx[key]["sub_components"].append(comp_name)

    cleaned_jsx = []
    for key, details in grouped_jsx.items():
        details["common_props"] = list(details["common_props"])
        details["files"] = list(details["files"])
        details["examples"] = list(set(details["examples"]))
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

