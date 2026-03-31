import os
import re
import json
import logging
import base64
import io
import dataclasses
import PIL.Image
import sys
from typing import Any, List, Dict, Set

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage

from utils.state import ResearchState, ResearchPlan, DiscoveryResult, ExplorerPlan, NoteDecision
from utils.tools import VisualDecoder, VocabularyIndex, Composer
from utils.cost import CostTracker

logger = logging.getLogger(__name__)

ORCHESTRATOR_PROMPT = """
### SYSTEM ROLE: The Codebase Architect (Visual Orchestrator)
You are the Principal Architect. You have access to a **Visual Atlas** (screenshots) and a **Vocabulary** (code element list).

### INTENTION SHIFT:
Your goal is to determine which existing patterns, behaviors, and logic are required to define a user-requested skill that will later be expressed as `skill.md`.

### CRITICAL CONSTRAINTS:
1. **STRICT PATTERN GROUNDING:** You are ONLY allowed to use information found in the Vocabulary and Visual Atlas. 
2. **NO EXTERNAL LIBRARIES:** Do NOT suggest or mention any technologies (e.g. FastAPI, Express, Tailwind, etc.) unless they are explicitly named in the Vocabulary list.
3. **FAIL IF NOT FOUND:** If the user request cannot be fulfilled using the provided code elements, state: "ERROR: Requirement not found in existing patterns."
4. **EXACT NAMES:** Use the EXACT vocabulary names.
5. **DEEP INSPECTION:** Select ALL necessary elements. Do not stop at a surface level.
"""
# Combined Inspector/Searcher Prompt
DEEP_INSPECTOR_PROMPT = """
### SYSTEM ROLE: Deep Visual Inspector & Code Auditor
You are responsible for analyzing specific code components ("Micro View") while keeping the overall system behavior ("Macro View") in mind.

### INTENTION SHIFT:
Your inspection is used to uncover **behaviors, rules, decisions, inputs, and outputs** that will later be formalized into a `skill.md`.

### YOUR TASKS:
1. **VISUAL GROUNDING:** Compare the **Specific Stitched Part** (Micro) against the **Global Atlas** (Macro). Does the behavior or logic match the visual/system intent?
2. **DEEP ANALYSIS:** Inspect the props, logic, conditions, and data flow of the stitched part.
3. **GAP DETECTION (SEARCH):** If the Stitched Part references a behavior, rule, or utility that is NOT in the current analysis, you MUST use the `DiscoveryResult` tool to search for it.

### RULES:
- Use `temperature=0.0` logic. strictly factual.
- Do not hallucinate behaviors or rules that are not visible in the code/stitch.
- If the behavioral definition is complete, output "SEARCH_COMPLETE".

### STOPPING CONDITIONS ("Enough Signal"):
You may ONLY report `status="SEARCH_COMPLETE"` if:
1. All referenced behaviors are fully defined (leaf nodes).
2. You have fully uncovered the logic required to satisfy the User Request as a skill.
3. There are NO "Unresolved Imports" or undefined behaviors.

### STRICT RULES:
- **DO NOT GUESS:** If you see a referenced behavior/component, you do not know how it works unless inspected. Queue it.
- **IGNORE STANDARD LIBS:** Do not queue generic language/runtime behavior.
- **VISUAL CHECK:** Verify the logic matches the visual snapshot provided.
"""

SYNTHESIZER_PROMPT = """
### SYSTEM ROLE: Pattern-Grounded Implementation Planner
You are finalizing the **skill.md definition** based on visual inspections.

### INTENTION SHIFT:
Your output is not executable code, but a precise, grounded `skill.md` derived from discovered patterns and behaviors.

### CRITICAL RULES:
1. **ONLY USE INSPECTION RESULTS:** Your skill definition must be strictly derived from the provided `INSPECTION RESULTS`.
2. **ZERO TOLERANCE FOR HALLUCINATION:** Do not mention behaviors, rules, or capabilities not discovered during inspection.
3. **FAIL FAST:** If the results are empty, state: "INSUFFICIENT DATA".
"""

# --- Scraper Prompts ---

EXPLORER_PROMPT = """
### SYSTEM ROLE: Senior Engineer — Codebase Explorer
You are a senior software engineer who has just been given access to a new codebase.
You have a **Visual Atlas** (screenshots of the code structure) and a **Vocabulary** (list of every code element).

### YOUR MISSION:
Identify the next **distinct skill, pattern, or convention** present in this codebase that has NOT been documented yet.

A "skill" is a cohesive, self-contained pattern such as:
- A data-fetching strategy (e.g., server actions, API routes, SWR hooks)
- A UI composition pattern (e.g., form builder, modal system, layout slots)
- An authentication/authorization flow
- A state management approach
- A styling/theming convention
- A routing or navigation pattern
- An error handling strategy
- A validation or schema pattern

### RULES:
1. **ONE SKILL AT A TIME.** Pick the single most important undocumented skill.
2. **GROUNDED ONLY.** The skill must be evident from the Vocabulary and Atlas — do not invent patterns.
3. **EXACT NAMES.** Use exact vocabulary names for entry points.
4. **NO REPEATS.** Do not pick a skill that is already in the "Documented Skills" list.
5. **BROAD ENTRY POINTS.** Select entry points that cover the full breadth of the skill (parents + key children).
"""

NOTETAKER_PROMPT = """
### SYSTEM ROLE: Codebase Note-Taker
You are writing technical notes about a specific skill/pattern discovered in a codebase.

### YOUR MISSION:
Based on the inspection trace provided, write a concise, structured skill document.

### OUTPUT FORMAT (Markdown):
```
# Skill: {Skill Name}

## Summary
One-paragraph description of what this skill/pattern does.

## Key Components
List the exact vocabulary names involved and their roles.

## Behaviors & Rules
Bullet list of specific behaviors, business rules, conditions, and edge cases discovered.

## Inputs & Outputs
What data flows in and out. Props, parameters, return types.

## Dependencies
What other skills/patterns this depends on (if any).

## Code Patterns
Literal code snippets or pseudo-code reconstructed from the inspection.
```

### CRITICAL RULES:
1. **ONLY USE INSPECTION RESULTS.** Every claim must trace back to the provided trace logs.
2. **ZERO HALLUCINATION.** Do not mention technologies, libraries, or behaviors not found in the trace.
3. **BE SPECIFIC.** Use exact names, exact props, exact conditions. No vague summaries.
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
            matches = self.vocab_index.search(q, limit=50, cutoff=0.5)
            
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
                {"type": "text", "text": "Select the initial entry points from the list above."},
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
            
            # SCOPED VISITED LOGIC:
            # We prefix visited targets with the current skill to allow re-inspection across skills.
            all_visited = state.get("visited_targets", [])
            current_skill = state.get("current_skill", "global")
            if not current_skill: current_skill = "global"
            scope_prefix = f"{current_skill}::"
            
            # Filter visited targets for THIS skill
            # (If visited target doesn't have prefix, treat as global/legacy and include it? No, ignore legacy for new skills)
            skill_visited = set()
            for t in all_visited:
                if t.startswith(scope_prefix):
                    skill_visited.add(t.replace(scope_prefix, ""))
                elif "::" not in t: # Legacy/Global items (backward compatibility)
                     if current_skill == "global":
                         skill_visited.add(t)

            # 1. Deduplicate
            current_batch = list(set([t for t in targets if t not in skill_visited]))
            
            if not current_batch:
                logger.info("🛑 INSPECTOR: Queue empty.")
                return {"pending_targets": []}
                
            logger.info(f"⛏️  STITCHING {len(current_batch)} FILES for skill '{current_skill}'")
            logger.info(f"📦 BATCHES \n {current_batch} \n")
            # 2. Stitch EVERYTHING found (Now returns list of chunks)
            image_chunks, results = self.decoder.bulk_inspect(current_batch)
            if not image_chunks:
                return {"inspection_results": ["⚠️ Error reading code."], "pending_targets": []}
                
            self.stitch_count += 1
            self._save_stitch(image_chunks, self.stitch_count)
            
            # Mark these specific files as visited (scoped)
            new_visited = [f"{scope_prefix}{t}" for t in current_batch]
            
            # 3. Prepare Context

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

I have stitched and provided the source code atlas images for the following targets:
{current_batch}
They are a **CODE ATLAS**: a visual encoding of schemas, connections, and logic.
You must decode them using the VISUAL LEGEND, GLOBAL ATLAS, SEARCH METADATA, and FULL VOCABULARY LIST.

---

## INSTRUCTIONS FOR THIS STEP

0. **DEEP DIG (MANDATORY)**
   - You must assume the atlas is a partial view of a larger repository pattern.
   - Actively look for *hidden patterns* implied by the atlas: referenced nodes, off-screen continuations, truncated labels, “…” markers, external edges, collapsed groups, repeated motifs, or any connection that leaves the current stitched region.
   - If the atlas implies ANY missing/hidden pattern that is required to reconstruct schemas, connections, or logic, you MUST trigger a search using the `DiscoveryResult` tool (see step 4).

1. **DECODE THE IMAGES:** Literally transcribe the code for schemas, connections, and logic.

2. **ATLAS → CODE (NO SUMMARIES)**
   - Treat the atlas as a compiler input.
   - Decode blocks, nodes, wires, arrows, labels, and regions into real textual code.
   - Preserve exact names, casing, structure, and ordering implied by the atlas.
   - Stitch across tiles and remove overlaps.
   - Do not invent code. If something is missing or unreadable, emit explicit placeholders.
   - If you detect a collapsed/abstracted region (group node, module box, “pipeline”, “handler”, “service”), you MUST expand it by searching for its internal definition via step 4.

3. **CROSS-REFERENCE:** Map your findings to the **VOCABULARY LIST**.
   - For every important identifier you reconstruct, link it to the closest vocabulary entry.
   - If an identifier is not in the vocabulary, mark it explicitly as `VOCAB_MISSING`.
   - If two identifiers are visually similar, resolve using Vocabulary first; otherwise mark `LOW_CONF`.

4. **QUEUE (TOOL CALL REQUIRED WHEN INCOMPLETE):** List the **Names** of missing internal code Elements you need to see next to complete the migration plan.
   - Only queue items that block full reconstruction.
   - Use concrete names exactly as referenced in the atlas and **VOCABULARY LIST**.
   - **FORCING RULE:** If ANY of the following are true, you MUST call the `DiscoveryResult` tool with `status="SEARCH_CONTINUE"` and include the missing names in `new_targets`:
     a) Any unresolved import / reference / symbol usage appears in the reconstructed code.
     b) Any edge/wire exits the stitched region to an uninspected node.
     c) Any node is a wrapper/entrypoint (router, module index, registry, container, aggregator) without its internal map visible.
     d) Any schema/type is referenced but not defined in the stitched region.
     e) Any label is truncated (ends with “…”, cut off, partial) and blocks exact reconstruction.
   - **SEARCH_COMPLETE is ONLY allowed** if there are ZERO unresolved references AND no edges leaving the region.

---

## REQUIRED OUTPUT (STRICT ORDER)

### A) RECONSTRUCTED CODE
Output literal reconstructed code artifacts derived from the atlas.
Label each artifact with its most likely unit or file name.

```<language>
<code>
```

B) NEXT (ONLY IF ELIGIBLE)

If eligible, list missing code Elements (names only, one per line).

C) TOOL OUTPUT (MANDATORY WHEN INCOMPLETE)

If any missing/hidden pattern is detected, you MUST return a DiscoveryResult tool call with:

status="SEARCH_CONTINUE"

new_targets=[...names...]

Otherwise return:

status="SEARCH_COMPLETE"
"""
            results_content: List[Dict[str, Any]] = [
                # {"type": "text", "text": f"### FULL VOCABULARY LIST\n{vocab_str}\n"},
                {"type": "text", "text": analysis_prompt},
                {"type": "text", "text": f"### SEARCH RESULTS METADATA\n{results_json}"},
                {"type": "text", "text": "### SEARCH RESULTS IMAGE(S)"}
            ]
            # logger.info(results_json)


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
            max_continuations = 5
            
            response = None
            for i in range(max_continuations + 1):
                response = tool_llm.invoke(current_messages)
                CostTracker().track_response(response, current_messages)
                
                # Check for reasoning content (common in Together/Deepseek models via LangChain)
                reasoning = getattr(response, "reasoning_content", None)
                if reasoning:
                    full_analysis += f"\n\n<thought>\n{reasoning}\n</thought>\n\n"
                
                content = self._get_content_text(response)
                full_analysis += content
                
                # Check if we should continue (often indicated by finish_reason or open code blocks)
                # finish_reason is model-specific, but 'length' is common
                finish_reason = response.response_metadata.get("finish_reason")
                
                if finish_reason == "length" or finish_reason == "MAX_TOKENS" or (content.count("```") % 2 != 0):
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
            else:
                # Fallback 1: Try to find XML Function Call (DeepSeek/Generic LLM behavior)
                # Matches <function_calls>...<invoke name="DiscoveryResult">...</invoke>...</function_calls>
                xml_match = re.search(r'<function_calls>\s*<invoke name="DiscoveryResult">(.*?)</invoke>\s*</function_calls>', analysis_text, re.DOTALL)
                parsed_xml = False
                
                if xml_match:
                    try:
                        content = xml_match.group(1)
                        status_match = re.search(r'<parameter name="status">(.*?)</parameter>', content)
                        targets_match = re.search(r'<parameter name="new_targets">(.*?)</parameter>', content, re.DOTALL)
                        
                        if status_match:
                            status = status_match.group(1).strip()
                            new_targets = []
                            if targets_match:
                                try:
                                    # Handle standard JSON list like ["a", "b"]
                                    targets_str = targets_match.group(1).strip()
                                    # Basic cleanup if it contains single quotes
                                    if targets_str.startswith("[") and "'" in targets_str:
                                        targets_str = targets_str.replace("'", '"')
                                    new_targets = json.loads(targets_str)
                                except:
                                    logger.warning(f"Failed to parse XML targets: {targets_match.group(1)}")
                            
                            result = DiscoveryResult(status=status, new_targets=new_targets)
                            logger.info(f"🤖 AI STATUS (Parsed XML): {result.status}")
                            
                            if result.status == "SEARCH_CONTINUE":
                                raw_queries = result.new_targets
                                logger.info(f"🤔 AI Searching for (Parsed XML): {raw_queries}")
                                next_targets = self._resolve_queries(raw_queries)
                            elif result.status == "SEARCH_COMPLETE":
                                logger.info("✅ DONE (Parsed XML).")
                                next_targets = []
                            
                            analysis_text += f"\n\n**Status (Parsed XML):** {result.status}"
                            parsed_xml = True
                    except Exception as e:
                        logger.warning(f"Failed to parse fallback XML: {e}")

                # Fallback 2: Try to find JSON block at the end of the text (if XML failed)
                if not parsed_xml:
                    # Look for JSON between triple backticks or just the last { ... } block
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', analysis_text, re.DOTALL | re.MULTILINE)
                    if not json_match:
                        # Try to find any curly brace block at the end of the string
                        json_match = re.search(r'(\{[\s\S]*\})\s*$', analysis_text)
                    
                    if json_match:
                        try:
                            json_str = json_match.group(1) if json_match.groups() else json_match.group(0)
                            data = json.loads(json_str)
                            if "status" in data:
                                result = DiscoveryResult(**data)
                                logger.info(f"🤖 AI STATUS (Parsed JSON): {result.status}")
                                
                                if result.status == "SEARCH_CONTINUE":
                                    raw_queries = result.new_targets
                                    logger.info(f"🤔 AI Searching for (Parsed): {raw_queries}")
                                    next_targets = self._resolve_queries(raw_queries)
                                elif result.status == "SEARCH_COMPLETE":
                                    logger.info("✅ DONE (Parsed).")
                                    next_targets = []
                                
                                analysis_text += f"\n\n**Status (Parsed JSON):** {result.status}"
                        except Exception as e:
                            logger.warning(f"Failed to parse fallback JSON: {e}")
                
            self._log_analysis(self.stitch_count, current_batch, analysis_text)

            return {
                "inspection_results": [f"### Trace Layer {self.stitch_count}\n{analysis_text}"],
                "visited_targets": new_visited, # Mark these specific files as visited (scoped)
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
            
            content = self._get_content_text(response)
            full_report += content
            
            # Continuation check
            finish_reason = response.response_metadata.get("finish_reason")
            if finish_reason == "length" or finish_reason == "MAX_TOKENS" or (content.count("```") % 2 != 0):
                logger.info(f"🔄 Report truncated. Requesting continuation ({i+1})...")
                current_messages.append(AIMessage(content=content))
                current_messages.append(HumanMessage(content="CONTINUE THE IMPLEMENTATION PLAN. You were cut off. Pick up exactly where you left off, continuing any code blocks or sentences. Do not restart."))
                continue
            else:
                break
                
        self._save_plan(full_report)
        return {"final_report": full_report}

    # --- HELPERS ---

    def _get_content_text(self, response: Any) -> str:
        """
        Robustly extract text content from an AIMessage, handling both string and list formats.
        """
        # Try response.text if it's available (common in gemini-3-pro-preview / new SDKs)
        if hasattr(response, "text") and isinstance(response.text, str):
             return response.text
             
        content = getattr(response, "content", "")
        if isinstance(content, str):
            return content
        elif isinstance(content, list):
            # Extract text from list of dicts (common in modern LangChain)
            text_parts = []
            for part in content:
                if isinstance(part, str):
                    text_parts.append(part)
                elif isinstance(part, dict) and part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
            return "".join(text_parts)
        return ""
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
        with open(os.path.join(self.gen_dir, "skill.md"), "w", encoding="utf-8") as f: f.write(text)
        self.composer.compose(os.path.join(self.gen_dir, "trace.png"))
        with open(os.path.join(self.gen_dir, "cost.txt"), "w", encoding="utf-8") as f: f.write(CostTracker().get_summary_string())

    def _save_skill(self, skill_name: str, text: str):
        """Save a single skill file to the skills/ subdirectory."""
        skills_dir = os.path.join(self.gen_dir, "skills")
        os.makedirs(skills_dir, exist_ok=True)
        safe_name = re.sub(r'[^a-z0-9_-]', '-', skill_name.lower().strip())
        safe_name = re.sub(r'-+', '-', safe_name).strip('-')
        path = os.path.join(skills_dir, f"skill-{safe_name}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        logger.info(f"📝 Saved skill: {path}")
        return path

    # --- SCRAPER: Explorer Node ---
    def explorer_node(self, state: ResearchState):
        """Autonomously identifies the next skill/pattern to investigate."""
        logger.info("🔭 EXPLORER: Scanning for next skill...")
        
        documented = list(state.get("documented_skills", []))
        skill_queue = state.get("skill_queue", [])
        
        # If we have queued skills from the NoteTaker, use the first one as a hint
        hint = ""
        if skill_queue:
            hint = f"\n\n### SUGGESTED NEXT SKILL\nThe previous analysis suggested exploring: {skill_queue[0]}"
        
        # Get Full Vocabulary
        vocabulary = self.vocab_index.get_all()
        vocab_str = json.dumps(vocabulary)
        
        documented_str = json.dumps(documented) if documented else "None yet — this is the first exploration."
        
        messages: List[BaseMessage] = [
            SystemMessage(content=EXPLORER_PROMPT),
            HumanMessage(content=[
                {"type": "text", "text": f"### FULL VOCABULARY LIST\n{vocab_str}\n"},
                {"type": "text", "text": f"### ALREADY DOCUMENTED SKILLS\n{documented_str}\n"},
                {"type": "text", "text": f"Identify the next most important skill to document.{hint}"},
                {"type":"text", "text":"Avoid these skills!!!: skill-authentication-session-management-passkeys-oauth-custom-session skill-drizzle-orm-with-sqlite-database-schema-queries skill-react-flow-xyflow-visual-node-based-workflow-editor skill-server-actions-with-zsa-type-safe-server-actions"}
            ])
        ]
        
        # Atlas Context
        for i, b64 in enumerate(self.atlas_b64_list):
            messages.append(HumanMessage(content=[
                {"type": "text", "text": f"### ATLAS TILE {i+1}"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
            ]))
        
        # Legend Context
        for i, lb64 in enumerate(self.legend_b64_list):
            suffix = f" {i+1}" if len(self.legend_b64_list) > 1 else ""
            messages.append(HumanMessage(content=[
                {"type": "text", "text": f"### VISUAL LEGEND{suffix} (Syntax Key)"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{lb64}"}}
            ]))
        
        structured_llm = self.llm.with_structured_output(ExplorerPlan)
        try:
            plan = structured_llm.invoke(messages)
            CostTracker().track_response(plan, messages) if hasattr(plan, 'response_metadata') else None
            
            logger.info(f"🎯 Explorer identified skill: '{plan.skill_name}'")
            logger.info(f"   Strategy: {plan.strategy}")
            logger.info(f"   Entry points: {plan.entry_points}")
            
            # Resolve entry points to concrete vocabulary keys
            expanded_targets = self._resolve_queries(plan.entry_points)
            logger.info(f"📋 Expanded into {len(expanded_targets)} concrete targets.")
            
            return {
                "current_skill": plan.skill_name,
                "topic": f"Skill: {plan.skill_name} — {plan.strategy}",
                "pending_targets": expanded_targets,
                "inspection_results": [],  # Reset for this skill
            }
        except Exception as e:
            logger.error(f"Explorer failed: {e}")
            return {"pending_targets": [], "current_skill": "unknown"}

    # --- SCRAPER: NoteTaker Node ---
    def notetaker_node(self, state: ResearchState):
        """Writes skill-{name}.md and decides whether to continue exploring."""
        skill_name = state.get("current_skill", "unknown")
        logger.info(f"📓 NOTETAKER: Writing notes for skill '{skill_name}'...")
        
        results = "\n\n".join(state.get("inspection_results", []))
        
        if not results.strip():
            logger.warning("No inspection results to synthesize.")
            return {
                "documented_skills": [skill_name],
                "skill_queue": [],
                "pending_targets": [],
            }
        
        # --- Phase 1: Write the skill file ---
        vocabulary = self.vocab_index.get_all()
        vocab_str = json.dumps(vocabulary)
        
        messages: List[BaseMessage] = [
            SystemMessage(content=NOTETAKER_PROMPT),
            HumanMessage(content=f"### SKILL BEING DOCUMENTED\n{skill_name}"),
            HumanMessage(content=f"### FULL VOCABULARY LIST\n{vocab_str}"),
            HumanMessage(content=f"### INSPECTION TRACE LOGS\n{results}"),
            HumanMessage(content=f"Write the skill document for '{skill_name}'. Be thorough and grounded.")
        ]
        
        full_report = ""
        current_messages = messages.copy()
        max_continuations = 5
        
        for i in range(max_continuations + 1):
            response = self.llm.invoke(current_messages)
            CostTracker().track_response(response, current_messages)
            
            reasoning = getattr(response, "reasoning_content", None)
            if reasoning:
                full_report += f"\n\n<thought>\n{reasoning}\n</thought>\n\n"
            
            content = self._get_content_text(response)
            full_report += content
            
            finish_reason = response.response_metadata.get("finish_reason")
            if finish_reason == "length" or finish_reason == "MAX_TOKENS" or (content.count("```") % 2 != 0):
                logger.info(f"🔄 Skill note truncated. Requesting continuation ({i+1})...")
                current_messages.append(AIMessage(content=content))
                current_messages.append(HumanMessage(content="CONTINUE. You were cut off. Pick up exactly where you left off."))
                continue
            else:
                break
        
        self._save_skill(skill_name, full_report)
        
        # --- Phase 2: Decide what to explore next ---
        documented = list(state.get("documented_skills", [])) + [skill_name]
        documented_str = json.dumps(documented)
        
        decide_messages: List[BaseMessage] = [
            SystemMessage(content="You are reviewing a codebase. Given the vocabulary and what has already been documented, identify if there are more important skills/patterns to explore. Be selective — only list skills that represent genuinely distinct patterns, not minor variations."),
            HumanMessage(content=f"### FULL VOCABULARY\n{vocab_str}"),
            HumanMessage(content=f"### ALREADY DOCUMENTED SKILLS\n{documented_str}"),
            HumanMessage(content="Are there more distinct skills to document? If yes, list them. If the codebase is sufficiently covered, say done.")
        ]
        
        structured_llm = self.llm.with_structured_output(NoteDecision)
        try:
            decision = structured_llm.invoke(decide_messages)
            CostTracker().track_response(decision, decide_messages) if hasattr(decision, 'response_metadata') else None
            
            if decision.is_done:
                logger.info("✅ EXPLORER: Codebase fully explored.")
            else:
                logger.info(f"🔄 EXPLORER: {len(decision.remaining_skills)} more skills to explore: {decision.remaining_skills}")
            
            return {
                "documented_skills": [skill_name],
                "skill_queue": decision.remaining_skills,
                "pending_targets": [],  # Clear for the next explorer cycle
                "inspection_results": [],  # Clear traces for next skill
            }
        except Exception as e:
            logger.error(f"NoteTaker decision failed: {e}")
            return {
                "documented_skills": [skill_name],
                "skill_queue": [],
                "pending_targets": [],
            }

    def assign_workers(self, state): pass