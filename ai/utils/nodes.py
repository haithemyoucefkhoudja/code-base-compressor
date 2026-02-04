
import os
import json
import logging
import base64
import io
import PIL.Image
from typing import List, Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.types import Send

from ai.utils.state import ResearchState, WorkerState, ResearchPlan
from ai.utils.tools import VisualDecoder, VocabularyIndex, Composer

logger = logging.getLogger(__name__)

# --- System Prompts ---

ORCHESTRATOR_PROMPT = """
### SYSTEM ROLE: The Codebase Architect (Visual Orchestrator)

You are the Principal Architect. You have access to a **Visual Atlas** of the codebase (screenshots of all components).
Your goal is to plan a specific implementation by inspecting relevant components.

### INPUT DATA
1. **The Vocabulary:** A list of all available component families.
2. **The Atlas:** Visual snapshots of the UI.

### TASK
Given the User Query and the Visual Atlas, determine WHICH components need to be visually inspected to understand the implementation details.
1. Look at the Atlas to find relevant UI sections.
2. Cross-reference with the Vocabulary List.
3. Select up to 10 key components that are likely involved in the requested feature.
"""

SYNTHESIZER_PROMPT = """
### SYSTEM ROLE: Implementation Planner
You are finalizing the implementation plan based on visual inspections.
Analyze the component details and creating a step-by-step implementation plan.
"""

# --- Node Class ---

class Nodes:
    def __init__(self, llm, tools_config: Dict):
        """
        Initialize nodes with necessary resources.
        tools_config should contain 'tiles_dir'.
        """
        self.llm = llm
        self.tiles_dir = tools_config["tiles_dir"]
        
        # Initialize Tools
        self.decoder = VisualDecoder(self.tiles_dir)
        self.vocab_index = VocabularyIndex(self.tiles_dir)
        self.composer = Composer()
        self.legend_path = self.decoder.get_legend_path()
        self.output_dir = tools_config.get("output_dir", "ai/output")
        self.gen_dir = os.path.join(self.output_dir, "generation")
        os.makedirs(self.gen_dir, exist_ok=True)
        
        # Load Visual Context
        self._load_visual_context()

    def _load_visual_context(self):
        """Pre-load visual assets as Base64."""
        logger.info("🖼️ Loading visual assets...")
        self.atlas_b64_list = []
        for atlas_path in self.decoder.atlas_paths:
            with open(atlas_path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
                self.atlas_b64_list.append(b64)
        
        if os.path.exists(self.legend_path):
            with open(self.legend_path, 'rb') as f:
                self.legend_b64 = base64.b64encode(f.read()).decode('utf-8')
        else:
            self.legend_b64 = ""

    # --- Node Implementations ---

    def planner_node(self, state: ResearchState):
        logger.info("🧠 PLANNER: Generating inspection plan...")
        
        vocabulary = self.vocab_index.get_all()
        vocab_str = json.dumps(vocabulary)
        
        messages = [
            SystemMessage(content=ORCHESTRATOR_PROMPT),
            HumanMessage(content=[
                {"type": "text", "text": f"### USER REQUEST\n{state['topic']}\n"},
                {"type": "text", "text": f"### VOCABULARY LIST\n{vocab_str}\n"}
            ])
        ]
        
        # Add Visual Context
        for i, b64 in enumerate(self.atlas_b64_list):
            messages[0].content += f"\n[Accessing Visual Context Tile {i+1}]"
            messages.append(HumanMessage(content=[
                {"type": "text", "text": f"### VISUAL CONTEXT: ATLAS TILE {i+1}"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            ]))
            
        if self.legend_b64:
            messages.append(HumanMessage(content=[
                {"type": "text", "text": "### VISUAL CONTEXT: COMPONENT LEGEND"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{self.legend_b64}"}}
            ]))
        
        # Structured Output
        structured_llm = self.llm.with_structured_output(ResearchPlan)
        try:
            plan = structured_llm.invoke(messages)
            logger.info(f"📋 Plan: {len(plan.targets)} targets identified.")
            return {"plan": plan}
        except Exception as e:
            logger.error(f"Planner failed: {e}")
            return {"plan": ResearchPlan(targets=[], strategy="Planning Failed")}

    # --- Batch Node Implementation (Reduces API Calls) ---

    def bulk_inspector_node(self, state: ResearchState):
        """
        Inspects ALL targets in one go using bulk_inspect and stitching.
        Reduces N API calls to 1.
        """
        if not state["plan"] or not state["plan"].targets:
            logger.warning("No targets to inspect.")
            return {"inspection_results": ["No targets identified."]}
            
        targets = state["plan"].targets
        families = [t.family for t in targets]
        
        logger.info(f"🕵️ BULK INSPECTOR: Inspecting {len(families)} families: {families}")
        
        # 1. Bulk Stitching (One Image)
        stitched_bytes, results = self.decoder.bulk_inspect(families)
        
        if not stitched_bytes:
            return {"inspection_results": ["⚠️ Bulk inspection failed to produce image."]}
            
        self.composer.add_thought(PIL.Image.open(io.BytesIO(stitched_bytes)), "Bulk Inspection")
        
        # 2. Bulk Analysis (One LLM Call)
        b64 = base64.b64encode(stitched_bytes).decode('utf-8')
        
        prompt = f"""### BULK COMPONENT ANALYSIS
You are analyzing a stitched grid of {len(families)} UI components.
The components are: {json.dumps(families)}

For EACH component:
1. Identify it in the grid.
2. Extract its key props and state.
3. Validate its hypothesis.

Return a consolidated report for all components.
"""
        
        messages = [
            HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            ])
        ]
        
        try:
            response = self.llm.invoke(messages)
            return {"inspection_results": [response.content]}
        except Exception as e:
            logger.error(f"Bulk inspection failed: {e}")
            return {"inspection_results": [f"ERROR: {str(e)}"]}

    def assign_workers(self, state: ResearchState):
        # We now route to bulk_inspector instead of fanning out
        # Keeping this signature for graph compatibility if needed, 
        # but technically we can just change the edge in agent.py
        pass 

    def synthesizer_node(self, state: ResearchState):
        logger.info("🔬 SYNTHESIZER: Compiling final report...")
        
        results = "\n\n".join(state["inspection_results"]) or "No inspection results."
        
        messages = [
            SystemMessage(content=SYNTHESIZER_PROMPT),
            HumanMessage(content=f"### USER REQUEST\n{state['topic']}"),
            HumanMessage(content=f"### INSPECTION RESULTS\n{results}"),
            HumanMessage(content="Generate a detailed Markdown implementation plan now.")
        ]
        
        response = self.llm.invoke(messages)
        final_md = response.content
        
        self._save_plan(final_md)
        return {"final_report": final_md}

    # --- Helpers ---

    def _execute_inspect_single(self, family: str) -> str:
        # Normalize
        norm = self.decoder._normalize_family(family)
        if norm not in self.decoder.context.coords:
            matches = self.vocab_index.search(family, limit=1)
            if matches:
                family = matches[0]
            else:
                return f"⚠️ Family '{family}' not found."

        # Crop
        crop, neighbors = self.decoder.crop_and_decode(family)
        if not crop:
             return f"⚠️ Failed to crop '{family}'."
             
        self.composer.add_thought(crop, family)
        return self._analyze_crop_with_model(family, crop, neighbors)

    def _analyze_crop_with_model(self, family: str, crop: PIL.Image.Image, neighbors: List[str]) -> str:
        buf = io.BytesIO()
        crop.save(buf, format='PNG')
        b64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        
        messages = [
            HumanMessage(content=[
                {"type": "text", "text": f"### COMPONENT ANALYSIS: {family}\nNeighbors: {neighbors}\nAnalyze this UI component code screenshot. Extract props, state, and structure."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            ])
        ]
        
        # Use valid tool config for generic model if needed, but self.llm is sufficient
        response = self.llm.invoke(messages)
        return response.content

    def _save_plan(self, markdown: str):
        md_path = os.path.join(self.gen_dir, "implementation_plan.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        logger.info(f"✅ Implementation Plan: {md_path}")
        
        trace_path = os.path.join(self.gen_dir, "architectural_trace.png")
        self.composer.compose(trace_path)
