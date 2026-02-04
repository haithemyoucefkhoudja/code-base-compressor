
from typing import List, TypedDict, Annotated, Any, Literal, Optional
import operator
from pydantic import BaseModel, Field

# --- Pydantic Models for Structured Output ---

class InspectionTarget(BaseModel):
    family: str = Field(description="The precise component family name to inspect (e.g. 'Button', 'Sidebar').")
    hypothesis: str = Field(description="Why we are inspecting this component.")

class ResearchPlan(BaseModel):
    targets: List[InspectionTarget] = Field(description="List of components to visually inspect.")
    strategy: str = Field(description="High-level research strategy.")

class DiscoveryResult(BaseModel):
    """Result of the component discovery step."""
    status: str = Field(description="Search status: 'SEARCH_COMPLETE' or 'SEARCH_CONTINUE'")
    new_targets: List[str] = Field(default_factory=list, description="List of EXACT component family names to inspect next.")

# --- LangGraph State Definitions ---

class ResearchState(TypedDict):
    """Global state for the research session."""
    topic: str
    plan: Optional[ResearchPlan]
    inspection_results: Annotated[List[str], operator.add]
    final_report: str
    
    # Recursion State
    visited_targets: Annotated[List[str], operator.add] # Track what we've seen
    pending_targets: List[str] # The NEXT batch to inspect
    
class WorkerState(TypedDict):
    """Input state for a parallel worker."""
    target: InspectionTarget
