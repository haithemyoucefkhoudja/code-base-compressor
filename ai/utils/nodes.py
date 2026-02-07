import os
import json
import logging
import base64
import io
import dataclasses
import PIL.Image
import sys
from typing import Any, List, Dict, Set

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage

from utils.state import ResearchState, ResearchPlan, DiscoveryResult
from utils.tools import VisualDecoder, VocabularyIndex, Composer
from utils.cost import CostTracker

logger = logging.getLogger(__name__)

# --- System Prompts ---
ORCHESTRATOR_PROMPT = """
### SYSTEM ROLE: Principal Codebase Navigator (The Cartographer)
You are an expert Software Architect with access to a **Visual Atlas** (Global Code Map) and a **Symbol Index** (Vocabulary).

### OBJECTIVE:
Translate the User's High-Level Request into concrete **Logical Entry Points**.
You must identify WHICH specific functions, classes, or constants in the codebase serve as the "Root Nodes" for the requested feature.

### INPUT DATA:
1. **User Request:** The feature or logic to investigate.
2. **Visual Atlas:** Screenshots of the codebase folder structure and key files. Use this to locate the relevant "Neighborhood" (e.g., `src/auth`, `backend/api`).
3. **Vocabulary List:** A strict list of available code symbols (Format: `symbolName::filename`).

### INSTRUCTIONS:
1. **Locate:** Use the Atlas to find the correct module/directory.
2. **Select:** Pick the specific symbols from the Vocabulary that start the execution flow (e.g., the main API handler, the root component, the config loader).
3. **Output:** A `ResearchPlan` containing only valid symbols from the Vocabulary.
"""

DEEP_INSPECTOR_PROMPT = """
### SYSTEM ROLE: Recursive Static Analysis Engine (High-Fidelity Code Reconstruction)
You are a senior specialized code auditor. Your primary directive is to **RECONSTRUCT SOURCE CODE** from visual source images. You are NOT allowed to simply "point" to files or summarize their purpose.

### OBJECTIVE:
- **LITERAL RECONSTRUCTION (CRITICAL):** You must transcribe exact code snippets, variable names, function signatures, and logic blocks from the "Source Code Image". 
- **LOGIC DECODING:** Explain exactly HOW the code achieves its task. (e.g., "The `createSession` function takes a `userId`, generates a 32-char token using `crypto.randomBytes`, and writes it to KV with a 30-day TTL.")
- **TRACEABLE CALL GRAPH:** Every internal dependency you identify MUST be mapped to the **VOCABULARY LIST**.

### PROCESS:
1. **VISUAL EXTRACTION:** 
   - Identify specific functions/variables in the image.
   - For each critical one, **WRITE DOWN THE ACTUAL CODE** or a very high-fidelity pseudo-code if the image is slightly blurry.
   - Identify the exact arguments, return types, and library calls.

2. **SYMBOL LINKING:** 
   - Check every dependency against the **VOCABULARY LIST**.
   - **IF FOUND:** Queue it via `DiscoveryResult(status="SEARCH_CONTINUE")`.
   - **IF NOT FOUND:** Document it in the commentary as an external/primitive dependency.

### OUTPUT FORMAT:
You must provide a response with the following sections:

1. **CODE RECONSTRUCTION:** 
   - Transcribe the exact logic for all database connections, schema definitions, or session logic found in the image.
   - Example: ```typescript \n export const userTable = sqliteTable('user', { id: text('id').primaryKey() }) \n ```

2. **LOGIC FLOW & STATE TRACING:** 
   - Describe the data path. What enters the function? What leaves it? Which global constants are accessed?

3. **TOOL CALL:** 
   - Use `DiscoveryResult` to define next steps.

**STRICT RULE:** If your commentary is just a list of "I see file X. It handles Y," you have FAILED. Give me the code.
"""

SYNTHESIZER_PROMPT = """
### SYSTEM ROLE: Technical Lead & Implementation Architect
You are the architect responsible for synthesizing a **Technical Implementation Plan** from high-fidelity code reconstructions.

### INPUT:
A **Dependency Trace Log** containing:
1. **CODE RECONSTRUCTIONS:** Literal extracts and logic flows decoded from source code images.
2. **METADATA:** File paths and symbol associations.

### TASK:
Generate a definitive **Markdown Implementation Plan** that:
1. **Architecture Overview:** Explain the high-level design of the relevant sub-systems.
2. **Logic Transcription & Analysis:** Include the reconstructed code blocks you received in the trace. Focus on the parts that need changing.
3. **GRANULAR MIGRATION GUIDE:** 
   - For every file involved, specify WHAT needs to change with **EXACT CODE EXAMPLES**.
   - Use the variable names, constants, and function signatures found in the trace.
   - Example: "In `src/db/index.ts`, replace the `getDB` initialization logic. Change parameter of `MongoClient` from `string` to the `MONGODB_URI` env var found in the config."
4. **Step-by-Step Execution Plan:** Provide a clear order of operations for the migration.

### CONSTRAINTS:
- **STRICT GROUNDING:** Only use information from the trace. If a detail is missing, state it.
- **ZERO HALLUCINATION:** Do not invent functions, types, or files.
- **TECHNICAL SPECIFICITY:** Use the exact code patterns provided to build your report.
- **NO PLACEHOLDERS:** Avoid "update logic accordingly". Instead, say "change `a.value` to `b.value`".
"""

class Nodes:
    def __init__(self, llm, tools_config: Dict):
        self.llm = llm
        self.tiles_dir = tools_config["tiles_dir"]
        
        # Tools
        self.decoder = VisualDecoder(self.tiles_dir)
        self.vocab_index = VocabularyIndex(self.tiles_dir) 
        self.composer = Composer()
        self.legend_paths = self.decoder.get_legend_paths()
        self.output_dir = tools_config.get("output_dir", "ai/output")
        self.gen_dir = os.path.join(self.output_dir, "generation")
        os.makedirs(self.gen_dir, exist_ok=True)
        self.stitch_count = 0
        
        # Cost Tracking
        cost_log_path = os.path.join(self.gen_dir, "cost_details.log")
        CostTracker().set_log_path(cost_log_path)
        
        self._load_visual_context()

    def _load_visual_context(self):
        """Pre-load visual assets."""
        self.atlas_b64_list = []
        for atlas_path in self.decoder.atlas_paths:
            with open(atlas_path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
                self.atlas_b64_list.append(b64)
        
        self.legend_b64_list = []
        for lp in self.legend_paths:
            if os.path.exists(lp):
                with open(lp, 'rb') as f:
                    self.legend_b64_list.append(base64.b64encode(f.read()).decode('utf-8'))

    # --- HELPER: The "Shotgun" Resolver ---
    def _resolve_queries(self, queries: List[str]) -> List[str]:
        """
        Takes LLM 'guesses' and finds ALL matching vocabulary keys using broad search.
        Stitches everything found.
        """
        resolved = set()
        for q in queries:
            # SEARCH: Broad search to catch everything
            matches = self.vocab_index.search(q, limit=2, cutoff=0.5)
            
            if matches:
                logger.info(f"   🔍 Query '{q}' -> Found {len(matches)} matches.")
                for m in matches:
                    resolved.add(m)
            else:
                logger.warning(f"   🚫 Query '{q}' -> NO matches found.")
        
        return list(resolved)

    # --- PLANNER NODE ---
    def planner_node(self, state: ResearchState):
        logger.info("🧠 PLANNER: Generating Concept Search...")
        
        # 1. Get Full Vocabulary
        vocabulary = self.vocab_index.get_all()
        vocab_str = json.dumps(vocabulary)
        
        messages: List[BaseMessage] = [
            SystemMessage(content=ORCHESTRATOR_PROMPT),
            HumanMessage(content=[
                {"type": "text", "text": f"### USER REQUEST\n{state['topic']}\n"},
                {"type": "text", "text": f"### FULL VOCABULARY LIST\n{vocab_str}\n"},
                {"type": "text", "text": "Select the initial entry points from the list above."}
            ])
        ]
        
        # Atlas Context
        for i, b64 in enumerate(self.atlas_b64_list):
            messages.append(HumanMessage(content=[
                {"type": "text", "text": f"### ATLAS TILE {i+1}"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            ]))

        # RESTORED: Legend Context
        for i, lb64 in enumerate(self.legend_b64_list):
            suffix = f" {i+1}" if len(self.legend_b64_list) > 1 else ""
            messages.append(HumanMessage(content=[
                {"type": "text", "text": f"### VISUAL LEGEND{suffix} (Syntax Key)"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{lb64}"}}
            ]))
            
        structured_llm = self.llm.with_structured_output(ResearchPlan)
        try:
            plan = structured_llm.invoke(messages)
            
            # 1. Take LLM Choices
            raw_queries = [t.family for t in plan.targets]
            logger.info(f"🤖 Planner Selected: {raw_queries}")

            # 2. EXPLODE them into concrete files (Shotgun)
            expanded_targets = self._resolve_queries(raw_queries)
            logger.info(f"📋 Expanded into {len(expanded_targets)} concrete files.")

            return {
                "plan": plan, 
                "pending_targets": expanded_targets, 
                "visited_targets": []
            }
        except Exception as e:
            logger.error(f"Planner failed: {e}")
            return {"plan": ResearchPlan(targets=[], strategy="Planning Failed"), "pending_targets": []}

    # --- RECURSIVE INSPECTOR NODE ---

    def bulk_inspector_node(self, state: ResearchState):
        """
        The 'Shotgun' Inspector.
        """
        try:
            targets = state.get("pending_targets", [])
            already_visited = list(state.get("visited_targets", []))
            
            # 1. Deduplicate
            current_batch = list(set([t for t in targets if t not in already_visited]))
            
            if not current_batch:
                logger.info("🛑 INSPECTOR: Queue empty.")
                return {"pending_targets": []}
                
            logger.info(f"⛏️  STITCHING {len(current_batch)} FILES")
            logger.info(f"📦 BATCHES \n {current_batch} \n")
            # 2. Stitch EVERYTHING found (Now returns list of chunks)
            image_chunks, results = self.decoder.bulk_inspect(current_batch)
            if not image_chunks:
                return {"inspection_results": ["⚠️ Error reading code."], "pending_targets": []}
                
            self.stitch_count += 1
            self._save_stitch(image_chunks, self.stitch_count)

            # 3. Prepare Context
            results_json = json.dumps([dataclasses.asdict(r) for r in results], indent=2)
            
            # Get Full Vocabulary Again
            vocabulary = self.vocab_index.get_all()
            vocab_str = json.dumps(vocabulary)
            
            messages: List[BaseMessage] = [SystemMessage(content=DEEP_INSPECTOR_PROMPT)]

            # Atlas Context
            for i, atlas_b64 in enumerate(self.atlas_b64_list):
                messages.append(HumanMessage(content=[
                    {"type": "text", "text": f"### GLOBAL ATLAS {i+1}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{atlas_b64}"}}
                ]))

            # RESTORED: Legend Context
            for i, lb64 in enumerate(self.legend_b64_list):
                suffix = f" {i+1}" if len(self.legend_b64_list) > 1 else ""
                messages.append(HumanMessage(content=[
                    {"type": "text", "text": f"### VISUAL LEGEND{suffix} (Syntax Key)"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{lb64}"}}
                ]))

            analysis_prompt = f"""### TRACE STEP #{self.stitch_count}
I have stitched and provided the source code images for: {current_batch}.

**USER MISSION:** "{state['topic']}"

**INSTRUCTIONS FOR THIS STEP:**
1. **DECODE THE IMAGES:** Literally transcribe the code for schemas, connections, and logic.
2. **BE TECHNICAL:** I don't want summaries. I want variable names, logic paths, and implementation details.
3. **CROSS-REFERENCE:** Map your findings to the **VOCABULARY LIST**.
4. **QUEUE:** List the **Names** of missing internal dependencies you need to see next to complete the migration plan.
"""
            results_content: List[Dict[str, Any]] = [
                {"type": "text", "text": f"### FULL VOCABULARY LIST\n{vocab_str}\n"},
                {"type": "text", "text": analysis_prompt},
                {"type": "text", "text": f"### SEARCH RESULTS METADATA\n{results_json}"},
                {"type": "text", "text": "### SEARCH RESULTS IMAGE(S)"}
            ]

            # Append all stitched chunks
            for chunk in image_chunks:
                b64_chunk = base64.b64encode(chunk).decode('utf-8')
                results_content.append({
                    "type": "image_url", 
                    "image_url": {"url": f"data:image/png;base64,{b64_chunk}"}
                })

            messages.append(HumanMessage(content=results_content))

            # 4. Invoke LLM with Continuation Logic
            tool_llm = self.llm.bind_tools([DiscoveryResult])
            
            full_analysis = ""
            current_messages = messages.copy()
            max_continuations = 3
            
            response = None
            for i in range(max_continuations + 1):
                response = tool_llm.invoke(current_messages)
                CostTracker().track_response(response, current_messages)
                
                # Check for reasoning content (common in Together/Deepseek models via LangChain)
                reasoning = getattr(response, "reasoning_content", None)
                if reasoning:
                    full_analysis += f"\n\n<thought>\n{reasoning}\n</thought>\n\n"
                
                content = response.content if response.content else ""
                full_analysis += content
                
                # Check if we should continue (often indicated by finish_reason or open code blocks)
                # finish_reason is model-specific, but 'length' is common
                finish_reason = response.response_metadata.get("finish_reason")
                
                if finish_reason == "length" or (content.count("```") % 2 != 0):
                    logger.info(f"🔄 Truncation detected (reason: {finish_reason}). Requesting continuation...")
                    current_messages.append(AIMessage(content=content))
                    current_messages.append(HumanMessage(content="CONTINUE YOUR ANALYSIS. You were cut off. Pick up exactly where you left off, continuing any code blocks or sentences."))
                    continue
                else:
                    break

            next_targets = []
            analysis_text = full_analysis if full_analysis else "Analysis performed via tool."
            
            if response and response.tool_calls:
                args = response.tool_calls[0]['args']
                result = DiscoveryResult(**args)
                
                logger.info(f"🤖 AI STATUS: {result.status}")
                
                if result.status == "SEARCH_CONTINUE":
                    raw_queries = result.new_targets
                    logger.info(f"🤔 AI Searching for: {raw_queries}")
                    
                    # --- THE EXPLOSION STEP ---
                    # Take LLM guesses -> Search Vocab -> Queue ALL Matches
                    next_targets = self._resolve_queries(raw_queries)
                    
                elif result.status == "SEARCH_COMPLETE":
                    logger.info("✅ DONE.")
                    next_targets = []
                
                # Append status to analysis if available
                analysis_text += f"\n\n**Status:** {result.status}"
                
            self._log_analysis(self.stitch_count, current_batch, analysis_text)

            return {
                "inspection_results": [f"### Trace Layer {self.stitch_count}\n{analysis_text}"],
                "visited_targets": current_batch, # Mark these specific files as visited
                "pending_targets": next_targets   # Pass the NEW concrete files
            }
            
        except KeyboardInterrupt:
            print("\n\n🚨 USER INTERRUPT (Ctrl+C) 🚨")
            return {
                "inspection_results": [f"### INTERRUPTED AT LAYER {self.stitch_count}"],
                "pending_targets": [] 
            }

    # --- SYNTHESIZER NODE ---
    def synthesizer_node(self, state: ResearchState):
        logger.info("🔬 SYNTHESIZER: Writing Report...")
        
        results = "\n\n".join(state["inspection_results"])
        
        # 1. Get Full Vocabulary
        vocabulary = self.vocab_index.get_all()
        vocab_str = json.dumps(vocabulary)
        
        messages: List[BaseMessage] = [
            SystemMessage(content=SYNTHESIZER_PROMPT),
            HumanMessage(content=f"### USER REQUEST\n{state['topic']}"),
            HumanMessage(content=f"### FULL VOCABULARY LIST\n{vocab_str}"),
            HumanMessage(content=f"### TRACE LOGS\n{results}"),
            HumanMessage(content="Generate the Final Implementation Plan. Ground your plan strictly in the provided vocabulary and trace logs.")
        ]
        
        full_report = ""
        current_messages = messages.copy()
        max_continuations = 5 # Higher limit for the final report
        
        for i in range(max_continuations + 1):
            response = self.llm.invoke(current_messages)
            CostTracker().track_response(response, current_messages)
            
            # Check for reasoning
            reasoning = getattr(response, "reasoning_content", None)
            if reasoning:
                full_report += f"\n\n<thought>\n{reasoning}\n</thought>\n\n"
            
            content = response.content if response.content else ""
            full_report += content
            
            # Continuation check
            finish_reason = response.response_metadata.get("finish_reason")
            if finish_reason == "length" or (content.count("```") % 2 != 0):
                logger.info(f"🔄 Report truncated. Requesting continuation ({i+1})...")
                current_messages.append(AIMessage(content=content))
                current_messages.append(HumanMessage(content="CONTINUE THE IMPLEMENTATION PLAN. You were cut off. Pick up exactly where you left off, continuing any code blocks or sentences. Do not restart."))
                continue
            else:
                break
                
        self._save_plan(full_report)
        return {"final_report": full_report}

    # --- HELPERS ---
    def _save_stitch(self, list_of_bytes: List[bytes], count: int):
        for i, b_bytes in enumerate(list_of_bytes):
            suffix = f"_{i+1}" if len(list_of_bytes) > 1 else ""
            path = os.path.join(self.gen_dir, f"layer_{count}{suffix}.png")
            with open(path, "wb") as f: f.write(b_bytes)
            self.composer.add_thought(PIL.Image.open(io.BytesIO(b_bytes)), f"Layer {count}{suffix}")

    def _log_analysis(self, count, batch, text):
        log_path = os.path.join(self.gen_dir, "recursion_log.md")
        mode = "w" if count == 1 else "a"
        with open(log_path, mode, encoding="utf-8") as f:
            f.write(f"\n# LAYER {count} (Files: {len(batch)})\n\n**Files:** `{batch}`\n\n{text}\n\n---\n")
    
    def _save_plan(self, text):
        with open(os.path.join(self.gen_dir, "final_plan.md"), "w", encoding="utf-8") as f: f.write(text)
        self.composer.compose(os.path.join(self.gen_dir, "trace.png"))
        with open(os.path.join(self.gen_dir, "cost.txt"), "w", encoding="utf-8") as f: f.write(CostTracker().get_summary_string())
    
    def assign_workers(self, state): pass