This is a classic "monolithic script" refactoring task. Your code performs three distinct types of work: **Parsing/Extraction**, **Data Modelling**, and **Data Aggregation/Reporting**. Separating these concerns will make the code easier to maintain, test, and extend.

Here is the recommended folder structure and where your specific code snippets should go.

### 1. Recommended Directory Structure

```text
code-analyzer/
│
├── main.py                  # Entry point (CLI runner)
├── requirements.txt         # Dependencies (tree-sitter, etc.)
├── .gitignore               # Ignore venv, __pycache__, repo/
│
└── analyzer/                # The main package
    ├── __init__.py          # Exposes key functions
    ├── config.py            # Constants (Paths, Filters)
    ├── models.py            # Dataclasses (CallUsage, JSXUsage)
    │
    ├── core/                # Low-level AST helpers
    │   ├── __init__.py
    │   ├── languages.py     # Tree-sitter language/parser init
    │   └── node_utils.py    # Helpers (get_full_chain, find_jsx)
    │
    ├── extractors/          # Logic to pull data from code
    │   ├── __init__.py
    │   ├── imports.py       # extract_js_imports logic
    │   └── usages.py        # extract_usages (Walks the tree)
    │
    └── processing/          # Logic to clean/group data
        ├── __init__.py
        ├── aggregators.py   # Grouping calls/JSX, dynamic threshold
        └── cleaning.py      # Merging JSX parents (CardHeader -> Card)
```

---

### 2. Detailed File Breakdown

Here is where specific parts of your `main.py` should move:

#### `analyzer/models.py`
Move all your `@dataclass` definitions here. This prevents circular imports.
```python
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class CallUsage:
    chain: str
    code: str
    # ... rest of fields ...

@dataclass
class JSXUsage:
    name: str
    # ... rest of fields ...

# Add TypeDefinition, ComponentDefinition, FileAnalysis here
```

#### `analyzer/core/languages.py`
Setup your Tree-sitter instances here. This isolates external library configuration.
```python
from tree_sitter import Parser, Language
import tree_sitter_javascript
import tree_sitter_typescript

JS_LANGUAGE = Language(tree_sitter_javascript.language())
TS_LANGUAGE = Language(tree_sitter_typescript.language_typescript())
# ... TSX/JSX setups ...

def get_parser(path: str) -> Parser:
    if path.endswith(".tsx"): return TSX_PARSER
    # ... rest of logic ...
```

#### `analyzer/core/node_utils.py`
Move the helper functions that operate on Tree-sitter nodes here.
```python
from tree_sitter import Node

def get_full_chain(node: Node, source: bytes) -> str:
    # ... your existing get_full_chain logic ...

def get_jsx_props(node: Node, source: bytes) -> List[str]:
    # ... your existing get_jsx_props logic ...

def get_jsx_name(node: Node, source: bytes) -> str:
    # ... your existing get_jsx_name logic ...
```

#### `analyzer/extractors/imports.py`
Your `extract_js_imports` function is complex enough to deserve its own file.
```python
from tree_sitter import Node
from analyzer.core.languages import TS_PARSER, JS_PARSER

def extract_js_imports(code: str) -> dict[str, list[str]]:
    # ... copy the large extract_js_imports function here ...
```

#### `analyzer/extractors/usages.py`
This is the heart of the scanner.
```python
import os
from analyzer.core.languages import get_parser
from analyzer.core.node_utils import get_full_chain, get_jsx_name
from analyzer.models import CallUsage, JSXUsage, ComponentDefinition
from .imports import extract_js_imports

def extract_usages(file_path: str):
    # ... copy your extract_usages function here ...
    # Ensure you update it to import models and utils from the new locations
```

#### `analyzer/processing/aggregators.py`
Move the logic that happens *after* the file scan (counting, thresholding, JSON prep).
```python
from collections import defaultdict, Counter

def group_and_filter(all_calls, all_jsxs, threshold_percent=0.25):
    # ... logic for calculating median_freq ...
    # ... logic for creating calls_by_chain ...
    # ... return the filtered data ...
```

#### `analyzer/processing/cleaning.py`
Move the specific logic regarding JSX parent merging (The "CardHeader" -> "Card" logic).
```python
def merge_jsx_parents(jsx_patterns):
    # ... logic for parent_map ...
    # ... logic for grouped_jsx ...
    return cleaned_jsx
```

#### `main.py`
Your entry point becomes clean and readable, acting as a coordinator.

```python
import os
import glob
import json
from analyzer.extractors.usages import extract_usages
from analyzer.processing.aggregators import group_and_filter
from analyzer.processing.cleaning import merge_jsx_parents

TARGET_REPO_PATH = "repo"

def main():
    # 1. Scan Files
    files = glob.glob(os.path.join(TARGET_REPO_PATH, "**/*.ts"), recursive=True) 
    # ... (add other patterns) ...
    
    all_calls = []
    all_jsxs = []

    print(f"Scanning {len(files)} files...")
    for file_path in files:
        try:
            calls, jsxs, _, _ = extract_usages(file_path)
            all_calls.extend(calls)
            all_jsxs.extend(jsxs)
        except Exception as e:
            print(f"Skipping {file_path}: {e}")

    # 2. Process Data
    call_patterns, jsx_patterns = group_and_filter(all_calls, all_jsxs)
    
    # 3. Clean/Merge
    final_jsx = merge_jsx_parents(jsx_patterns)

    # 4. Save
    output = {
        "call_patterns": call_patterns,
        "jsx_patterns": final_jsx
        # ... rest of structure ...
    }
    
    with open("repo_patterns.json", "w") as f:
        json.dump(output, f, indent=2)

if __name__ == "__main__":
    main()
```

---

### 3. Best Practices Checklist

1.  **Dependency Management (`requirements.txt`)**:
    Don't rely on global packages. Create a file listing versions:
    ```text
    tree-sitter==0.20.1
    tree-sitter-javascript==0.20.0
    tree-sitter-typescript==0.20.0
    ```

2.  **Configuration**:
    Avoid hardcoding `TARGET_REPO_PATH = "repo"` deep in functions. Pass paths as arguments or use a `config.py` file or `argparse` to accept the path via command line:
    `python main.py --path ./my-project`

3.  **Exception Handling**:
    In your `extract_js_imports`, you have a broad `try...except`. In a structured project, try to be specific (e.g., catch `UnicodeDecodeError` specifically when reading files) so you don't hide logic bugs.

4.  **Relative Imports**:
    Inside the `analyzer` folder, use relative imports (e.g., `from .models import CallUsage`). This makes the package portable.

5.  **Type Hints**:
    You are already doing a great job with `typing`. Keep doing this. In the new structure, ensure you don't have circular imports (e.g., if `models.py` needs something from `utils.py`, and `utils.py` needs `models.py`). *Models* should usually have zero dependencies.

6.  **Performance**:
    Your script reads the file content multiple times (once for `extract_js_imports`, once for parsing).
    *Optimization:* Read the file contents once in `extract_usages` and pass the byte string to the import extractor.