
import os
import json
import logging
import base64
import io
import PIL.Image
from typing import List, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from utils.state import ResearchState,  ResearchPlan
from utils.tools import VisualDecoder, VocabularyIndex, Composer

from utils.cost import CostTracker

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
        self.stitch_count = 0
        
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
            
            # INITIALIZE RECURSION STATE
            # We treat the initial plan targets as the first batch of "pending targets"
            initial_targets = [t.family for t in plan.targets]
            
            return {
                "plan": plan, 
                "pending_targets": initial_targets,
                "visited_targets": []
            }
        except Exception as e:
            logger.error(f"Planner failed: {e}")
            return {"plan": ResearchPlan(targets=[], strategy="Planning Failed"), "pending_targets": []}

    # --- Batch Node Implementation (Recursive) ---

    def bulk_inspector_node(self, state: ResearchState):
        """
        Processes the CURRENT batch of 'pending_targets'.
        This node does ONE pass: Stitch -> Analyze -> Discover Next.
        The Graph handles the recursion if 'pending_targets' is non-empty.
        """
        targets = state.get("pending_targets", [])
        
        # Filter out already visited (Dedup)
        # Note: In Graph state, 'visited_targets' accumulates. 
        # But we need to check if the *current* targets have been visited.
        # However, logic downstream should prevent adding visited to pending. 
        # We'll double check here to be safe.
        already_visited = list(state.get("visited_targets", []))
        
        current_batch = [t for t in targets if t not in already_visited]
        
        if not current_batch:
            logger.info("🕵️ Inspector: No new targets to inspect (all visited).")
            return {"pending_targets": []} # Clear pending to stop recursion
            
        logger.info(f"🕵️ BULK INSPECTOR: Processing batch of {len(current_batch)}: {current_batch}")
        
        # 1. Bulk Stitching (One Image)
        stitched_bytes, results = self.decoder.bulk_inspect(current_batch)
        
        if not stitched_bytes:
            return {"inspection_results": ["⚠️ Batch produced no image."], "pending_targets": []}
            
        # SAVE STITCHED IMAGE
        self.stitch_count += 1
        stitch_filename = f"bulk_stitch_{self.stitch_count}.png"
        stitch_path = os.path.join(self.gen_dir, stitch_filename)
        with open(stitch_path, "wb") as f:
            f.write(stitched_bytes)
        logger.info(f"💾 Saved stitched image: {stitch_path}")

        self.composer.add_thought(PIL.Image.open(io.BytesIO(stitched_bytes)), f"Batch {self.stitch_count}")
        
        # 2. Analyze Batch
        b64 = base64.b64encode(stitched_bytes).decode('utf-8')
        import dataclasses
        results_json = json.dumps([dataclasses.asdict(r) for r in results], indent=2)

        analysis_prompt = f"""### COMPONENT ANALYSIS (Batch {self.stitch_count})
The components are: {json.dumps(current_batch)}

GOAL: Extract specific implementation details to answer the user request: "{state['topic']}"

For EACH component:
1. Identify it.
2. Analyze its Props, State, and Dependencies.
3. Check for any missing child components or imports.
"""
        messages = [
            SystemMessage(content="You are a strict Code Auditor. Use temperature=0.0."),
            HumanMessage(content=[
                {"type": "text", "text": analysis_prompt},
                {"type": "text", "text": f"### METADATA:\n{results_json}"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            ])
        ]
        
        # Main Analysis
        response = self.llm.bind(temperature=0.0).invoke(messages)
        CostTracker().track_response(response)
        analysis_text = response.content
        
        # Log
        log_path = os.path.join(self.gen_dir, "analysis_log.txt")
        # Initialize log if first run
        if self.stitch_count == 1:
             with open(log_path, "w", encoding="utf-8") as f: f.write("--- Analysis Log ---\n")
             
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n=== BATCH {self.stitch_count} ({len(current_batch)} items) ===\n{analysis_text}\n")
            
        # 3. Discovery Tool (Next Steps)
        discovery_prompt = """
### DISCOVERY STEP
Based on the analysis, are there **missing components** we need to inspect?
Use the tool to either complete the search or queue more targets.
"""
        messages.append(HumanMessage(content=analysis_text))
        messages.append(HumanMessage(content=discovery_prompt))
        
        from utils.state import DiscoveryResult
        tool_llm = self.llm.bind_tools([DiscoveryResult], tool_choice="DiscoveryResult")
        
        next_targets = []
        try:
             discovery_response = tool_llm.bind(temperature=0.0).invoke(messages)
             CostTracker().track_response(discovery_response)
             
             if discovery_response.tool_calls:
                 args = discovery_response.tool_calls[0]['args']
                 result = DiscoveryResult(**args)
                 
                 log_msg = f"Tool: {result.status}, New: {result.new_targets}"
                 with open(log_path, "a", encoding="utf-8") as f: f.write(f"\n>>> {log_msg}\n")
                 
                 if result.status == "SEARCH_CONTINUE":
                      # Filter: Don't re-queue what we just visited or have visited
                      for t in result.new_targets:
                          if t and t not in already_visited and t not in current_batch:
                              next_targets.append(t)
                              
                 logger.info(f"⏭️ Next Targets: {next_targets}")
                 
        except Exception as e:
            logger.error(f"Discovery failed: {e}")
            
        return {
            "inspection_results": [f"### Batch {self.stitch_count}\n{analysis_text}"],
            "visited_targets": current_batch,
            "pending_targets": next_targets # REPLACES pending with the new batch
        }

    def assign_workers(self, state: ResearchState):
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
        
        full_content = ""
        
        # Max continuation loops to prevent infinite loops (e.g. 5)
        for _ in range(5):
            response = self.llm.invoke(messages)
            CostTracker().track_response(response)
            
            chunk = response.content
            full_content += chunk
            
            # Check finish reason
            # OpenAI/Together usually return 'length' if max_tokens reached
            finish_reason = response.response_metadata.get("finish_reason")
            
            if finish_reason == "length":
                logger.info("⚠️ Response truncated (length). Continuing generation...")
                from langchain_core.messages import AIMessage
                messages.append(AIMessage(content=chunk))
                messages.append(HumanMessage(content="Continue exactly where you left off."))
            else:
                break
        
        self._save_plan(full_content)
        
        # Save Cost Report
        cost_path = os.path.join(self.gen_dir, "cost_report.txt")
        with open(cost_path, "w", encoding="utf-8") as f:
            f.write(CostTracker().get_summary_string())
            
        return {"final_report": full_content}

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
        CostTracker().track_response(response) # Track usage here too
        return response.content

    def _save_plan(self, markdown: str):
        md_path = os.path.join(self.gen_dir, "implementation_plan.md")
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(markdown)
        logger.info(f"✅ Implementation Plan: {md_path}")
        
        trace_path = os.path.join(self.gen_dir, "architectural_trace.png")
        self.composer.compose(trace_path)
