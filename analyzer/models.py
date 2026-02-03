from dataclasses import dataclass, field
from typing import Any, List, Dict,  Optional

@dataclass
class CallUsage:
    """A function/method call."""
    chain: str              # Full chain: "supabase.storage.from" or "createServerAction.input.handler"
    code: str
    file: str
    extension: str
    line: int
    structure: str          # Abstract structure of arguments
    source_import: str # Dependency source
    props: List[str] = field(default_factory=list) # Argument names (for keyword args) or indices (for positional)
    prop_types: Dict[str, str] = field(default_factory=dict) # Map of prop/arg name (or index) to its type
    return_type: str = "" # Inferred return type
    context: List[str] = field(default_factory=list) # Stack of parent call/structures
    dts_signature: dict[str, Any] | None = None  # Type signature from .d.ts (constructor_params or parameters)

@dataclass(unsafe_hash=True)
class ReferenceUsage:
    """A reference usage."""
    name: str
    source_import: str = field(compare=False)

@dataclass
class ConstantDefinition:
    """A constant definition."""
    name: str
    code: str
    file: str
    line: int
    source_import: str
    extension: str
    context: List[str] = field(default_factory=list)

@dataclass
class TypeDefinition:
    """A TypeScript interface, type alias, or enum definition."""
    name: str
    kind: str           # "interface", "type", "enum"
    code: str
    file: str
    line: int
    source_import: str
    extension: str
    
@dataclass
class ComponentDefinition:
    """A Component definition (function body)."""
    name: str
    code: str
    file: str
    line: int
    props: List[str]
    source_import: str
    extension: str
    prop_types: Dict[str, str] = field(default_factory=dict)
    return_type: str = ""
    context: List[str] = field(default_factory=list)
    

@dataclass
class JSXUsage:
    """A JSX component usage."""
    name: str               # Component name: "Button", "Alert"
    props: List[str]        # List of prop names used: ["variant", "className", "onClick"]
    code: str
    file: str
    line: int
    source_import: str
    extension: str
    has_children: bool      # Whether it wraps children or self-closing
    prop_types: Dict[str, str] = field(default_factory=dict)
    context: List[str] = field(default_factory=list) # Stack of parent call/structures

@dataclass
class FileAnalysis:
    calls: List[CallUsage]
    jsxs: List[JSXUsage]
    imports: List[str]
    environment: Optional[str]
