
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

# --- LangGraph State Definitions ---

class ResearchState(TypedDict):
    """Global state for the research session."""
    topic: str
    plan: Optional[ResearchPlan]
    inspection_results: Annotated[List[str], operator.add]
    final_report: str
    
class WorkerState(TypedDict):
    """Input state for a parallel worker."""
    target: InspectionTarget
