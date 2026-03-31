
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

# --- Scraper Models ---

class ExplorerPlan(BaseModel):
    """Output of the Explorer node — identifies the next skill to investigate."""
    skill_name: str = Field(description="Short, descriptive name for the skill/pattern being investigated (e.g. 'form-validation', 'auth-flow').")
    entry_points: List[str] = Field(description="List of vocabulary entry-point names to inspect for this skill.")
    strategy: str = Field(description="Brief explanation of what this skill covers and why these entry points were chosen.")

class NoteDecision(BaseModel):
    """Output of the NoteTaker node — decides whether exploration is complete."""
    remaining_skills: List[str] = Field(default_factory=list, description="List of skill topic names still worth exploring. Empty if done.")
    is_done: bool = Field(description="True if the codebase has been sufficiently explored and no more skills remain.")

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
    
    # Scraper State
    current_skill: str                                      # Name of skill being investigated
    documented_skills: Annotated[List[str], operator.add]   # Skills already written
    skill_queue: List[str]                                  # Remaining skill topics to explore
    
class WorkerState(TypedDict):
    """Input state for a parallel worker."""
    target: InspectionTarget
