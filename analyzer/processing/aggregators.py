from analyzer.models import ReferenceUsage
from collections import defaultdict
from typing import List, Dict, Tuple
from ..models import CallUsage, JSXUsage, ConstantDefinition
from ..core.node_utils  import import_name

def group_and_filter(all_calls: List[CallUsage], all_jsxs: List[JSXUsage], all_constant_defs: List[ConstantDefinition], all_references: List[ReferenceUsage], threshold_percent: float = 0.25, min_freq: int = 2) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict], List[str]]:
    """Groups call and JSX usages, and filters them based on a dynamic frequency threshold."""
    
    # Group calls by FULL CHAIN and SOURCE IMPORT
    calls_by_id: Dict[Tuple[str, str], List[CallUsage]] = defaultdict(list)
    for call in all_calls:
        calls_by_id[(call.chain, call.source_import)].append(call)

    # Group JSX by component name and SOURCE IMPORT
    jsx_by_id: Dict[Tuple[str, str], List[JSXUsage]] = defaultdict(list)
    for jsx in all_jsxs:
        jsx_by_id[(jsx.name, jsx.source_import)].append(jsx)

    # Group constants by name and SOURCE IMPORT
    constants_by_id: Dict[Tuple[str, str], List[ConstantDefinition]] = defaultdict(list)
    for constant in all_constant_defs:
        constants_by_id[(constant.name, constant.source_import)].append(constant)
    
    # Group references by name and SOURCE IMPORT
    references_by_id: Dict[Tuple[str, str], List[ReferenceUsage]] = defaultdict(list)
    for reference in all_references:
        references_by_id[(reference.name, reference.source_import)].append(reference)
    
    # Calculate dynamic threshold for filtering
    all_counts = [len(u) for u in calls_by_id.values()] + [len(u) for u in jsx_by_id.values()] + [len(u) for u in constants_by_id.values()] + [len(u) for u in references_by_id.values()]
    median_freq = 0
    if all_counts:
        all_counts.sort()
        n = len(all_counts)
        if n % 2 == 1:
            median_freq = all_counts[n // 2]
        else:
            median_freq = (all_counts[n // 2 - 1] + all_counts[n // 2]) / 2.0

    filt_threshold = max(min_freq, median_freq * threshold_percent)
    print(f"Dynamic Filter Threshold: >= {filt_threshold:.2f} (Median: {median_freq})")
    
    # Filter for patterns with >= threshold occurrences
    call_patterns = [
        {
            "chain": chain,
            "source_import": source_import,
            "usages": usages,
        }
        for (chain, source_import), usages in calls_by_id.items() 
        if len(usages) >= filt_threshold
    ]
    call_patterns.sort(key=lambda x: len(x["usages"]), reverse=True)
    for chain in call_patterns[:10]:
        print(f"call_pattern: {chain['chain']} from {chain['source_import']}")

    jsx_patterns = [
        {
            "name": name,
            "source_import": source_import,
            "usages": usages,
        } 
        for (name, source_import), usages in jsx_by_id.items() 
        if len(usages) >= filt_threshold
    ]
    jsx_patterns.sort(key=lambda x: len(x["usages"]), reverse=True)
    for jsx in jsx_patterns[:10]:
        print(f"jsx_pattern: {jsx['name']} from {jsx['source_import']}")

    # Filter constants
    constant_patterns = [
        {
            "name": name,
            "source_import": source_import,
            "usages": usages,
        } 
        for (name, source_import), usages in constants_by_id.items() 
        if len(usages) >= filt_threshold 
    ]
    constant_patterns.sort(key=lambda x: len(x["usages"]), reverse=True)
    for constant in constant_patterns[:10]:
        print(f"constant_pattern: {constant['name']} from {constant['source_import']}")

    reference_patterns = [
        {
            "name": actual_name,
            "type": import_type,
            "source_import": source_import,
            "usages": len(usages),
        } 
        for (name, source_import), usages in references_by_id.items() 
        for actual_name, import_type in [import_name(name)]
        if len(usages) >= filt_threshold
    ]
    reference_patterns.sort(key=lambda x: x["usages"], reverse=True)
    for ref in reference_patterns[:10]:
        print(f"reference_pattern: {ref['name']} from {ref['source_import']}")
    # Get raw vocabulary from filtered patterns
    raw_vocab = set()
    for pattern in call_patterns:
        chain = pattern["chain"]
        raw_vocab.add(chain)
        if "." in chain:
            raw_vocab.add(chain.split(".")[0])
    
    for pattern in jsx_patterns:
        name = pattern["name"]
        raw_vocab.add(name)
        if "." in name:
            raw_vocab.add(name.split(".")[0])
    
    for pattern in constant_patterns:
        name = pattern["name"]
        raw_vocab.add(name)
        if "." in name:
            raw_vocab.add(name.split(".")[0])
    
    for pattern in reference_patterns:
        name = pattern["name"]
        raw_vocab.add(name)
        if "." in name:
            raw_vocab.add(name.split(".")[0])
            
    return call_patterns, jsx_patterns, constant_patterns, reference_patterns, sorted(list(raw_vocab))
