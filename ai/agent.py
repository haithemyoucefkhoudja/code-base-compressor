
import workflow
import os
import json
import logging
from typing import List, Dict, Any, Optional
import time
import uuid
from datetime import datetime
import io

try:
    from google import genai
    from google.genai import types, errors
    from PIL import Image
    import PIL.Image
except ImportError:
    raise ImportError("CRITICAL: 'google-genai' library is required.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Increase PIL limit
PIL.Image.MAX_IMAGE_PIXELS = None

# --- 1. Tool Logic (Executors) ---

class VisualAgentExecutor:
    """
    Executes tool logic.
    """
    def __init__(self):
        self.eyes = workflow.VisualDecoder()
        self.artist = workflow.Composer()
        
        # Load Vocab
        vocab_path = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_patterns_tiles.vocab.json"
        try:
            with open(vocab_path, 'r') as f:
                raw = json.load(f)
                self.vocab = list(raw.keys()) if isinstance(raw, dict) else raw
            logger.info(f"✅ Vocabulary Loaded: {len(self.vocab)} items.")
        except Exception as e:
            logger.warning(f"Failed to load vocab: {e}")
            self.vocab = []

        # Configure Output
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.base_dir = f"ai/output/{timestamp}"
        self.gen_dir = f"{self.base_dir}/generation"
        self.log_dir = f"{self.base_dir}/logs"
        os.makedirs(self.gen_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        
        file_handler = logging.FileHandler(f"{self.log_dir}/session.log", encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        logger.addHandler(file_handler)
        logger.info(f"📂 Session: {self.base_dir}")

    def execute_search(self, concept: str) -> List[str]:
        """Exact substring search."""
        concept = concept.strip()
        logger.info(f"🔎 Searching for '{concept}'...")
        
        matches = [k for k in self.vocab if concept.lower() in k.lower()]
        matches.sort(key=len)
        return matches[:5]

    def execute_inspect(self, family: str) -> tuple[bytes, List[str], str]:
        logger.info(f"👁️ Inspecting '{family}'...")
        
        crop, neighbors = self.eyes.crop_and_decode(family)
        if crop:
            self.artist.add_thought(crop, family)
            img_byte_arr = io.BytesIO()
            crop.save(img_byte_arr, format='PNG')
            return img_byte_arr.getvalue(), neighbors, f"{family}.png"
        return b"", [], ""

    def save_plan(self, content: str) -> str:
        path = os.path.join(self.gen_dir, "implementation_plan.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        trace_path = os.path.join(self.gen_dir, "feature_trace.png")
        self.artist.compose(trace_path)
        return path

# --- 2. The Agent ---

class BatchAgent:
    def __init__(self):
        # Updated Key from User
        self.api_key = "AIzaSyBvvlaZaKCY9RWYwOa_f1jlOJkO0p6mV2Q" 
        if not self.api_key: raise ValueError("FATAL: Key missing")
        self.client = genai.Client(api_key=self.api_key)
        self.executor = VisualAgentExecutor()

    def run(self, user_query: str):
        logger.info(f"🚀 Batch Mission: {user_query}")
        
        # --- 1. Load Images as BYTES (User Requested Method) ---
        atlas_path = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_patterns_tiles.png"
        legend_path = r"c:\Users\haithem-yk\Desktop\Projects\reposoul-python-job\repo_patterns_tiles_legend.png"
        
        atlas_bytes = None
        legend_bytes = None

        try:
            logger.info(f"🖼️ Reading Atlas Bytes: {atlas_path}...")
            with open(atlas_path, 'rb') as f:
                atlas_bytes = f.read()
            logger.info(f"✅ Atlas Loaded: {len(atlas_bytes)} bytes")
            
            logger.info(f"🖼️ Reading Legend Bytes: {legend_path}...")
            with open(legend_path, 'rb') as f:
                legend_bytes = f.read()
            logger.info(f"✅ Legend Loaded: {len(legend_bytes)} bytes")
            
        except Exception as e:
            logger.error(f"❌ File read failure: {e}")

        # --- 2. Define Tools ---
        def search_codebase(concept: str): 
            """
            Search for a component name in the Vocabulary.
            IMPORTANT: Input 'concept' MUST be a string from the Available Vocabulary list.
            """
            return self.executor.execute_search(concept)
            
        def inspect_component(family: str): 
             """
             Inspect a component's visual structure.
             IMPORTANT: Input 'family' MUST be an exact string from the Available Vocabulary.
             """
             # We return metadata here. The Agent gets the bytes in the visual channel below.
             _, neighbors, fname = self.executor.execute_inspect(family)
             return {"neighbors": neighbors, "filename": fname, "status": "inspected"}
            
        def save_implementation_plan(content: str): 
            """Save the final markdown plan."""
            return self.executor.save_plan(content)
        
        tools_list = [search_codebase, inspect_component, save_implementation_plan]

        # --- 3. Construct Prompt with Inline Bytes ---
        
        sys_instructions = """
        You are a Specialized Codebase Navigator.
        
        CRITICAL INSTRUCTION:
        You have access to a specific 'Available Vocabulary' of component names.
        Select relevant components from that list that match the user request.
        When using 'search_codebase' or 'inspect_component', you MUST use EXACT names from this vocabulary.
        
        GOAL: Plan the implementation of the REQUEST.
        
        PROCESS:
        1. READ the 'Available Vocabulary' list provided below.
        2. SELECT relevant components from that list that match the user request.
        3. CALL 'search_codebase' with these exact names.
        4. CALL 'inspect_component' with these exact names.
        5. Save the plan.
        
        USE BATCH CALLS: Call multiple tools in one turn.
        """
        
        # FULL VOCABULARY INJECTION
        vocab_text = f"AVAILABLE VOCABULARY (SELECT FROM THIS LIST): {json.dumps(self.executor.vocab)}"
        
        prompt_parts = [
            sys_instructions,
            f"REQUEST: {user_query}",
            vocab_text,
            "VISUAL CONTEXT 1: FULL CODEBASE ATLAS (See below)",
        ]
        
        if atlas_bytes:
            prompt_parts.append(types.Part.from_bytes(data=atlas_bytes, mime_type="image/png"))
        
        prompt_parts.append("VISUAL CONTEXT 2: TILE LEGEND (See below)")
        
        if legend_bytes:
            prompt_parts.append(types.Part.from_bytes(data=legend_bytes, mime_type="image/png"))
        
        # --- Retry Logic ---
        def retry_call(func, *args, **kwargs):
            for attempt in range(5):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if "503" in str(e) or "429" in str(e):
                        logger.warning(f"API Error {e}, retrying {attempt}...")
                        time.sleep((attempt + 1) * 10)
                    else:
                        raise e

        # --- Turn 1 ---
        logger.info("🧠 Thinking (With Inline Image Bytes)...")
        
        config_1 = types.GenerateContentConfig(
            tools=tools_list,
            thinking_config=types.ThinkingConfig(include_thoughts=True),
            temperature=0.4
        )
        
        response_1 = None
        try:
             response_1 = retry_call(
                 self.client.models.generate_content,
                 model="gemini-3-flash-preview",
                 contents=prompt_parts, 
                 config=config_1
             )
        except Exception as e:
             logger.warning(f"Thinking failed ({e}). Retrying standard.")
             response_1 = retry_call(
                 self.client.models.generate_content,
                 model="gemini-3-flash-preview",
                 contents=prompt_parts,
                 config=types.GenerateContentConfig(tools=tools_list)
             )

        if not response_1: raise RuntimeError("No response from Turn 1")

        # --- Execution ---
        if not response_1.function_calls:
            logger.info("No calls. Output: " + str(response_1.text)[:200])
            return

        logger.info(f"⚡ Executing {len(response_1.function_calls)} calls...")
        
        # Reconstruct history manually for Turn 2 to include the inline bytes correctly
        # The prompt_parts list already contains the Part objects we need.
        history_content = types.Content(role="user", parts=[])
        
        for p in prompt_parts:
            if isinstance(p, str):
                history_content.parts.append(types.Part(text=p))
            elif isinstance(p, types.Part):
                history_content.parts.append(p)
                
        history = [history_content]
        
        if response_1.candidates and response_1.candidates[0].content:
            history.append(response_1.candidates[0].content)

        tool_outputs = []

        for call in response_1.function_calls:
            args = dict(call.args) if call.args else {}
            fname = call.name
            
            try:
                if fname == "search_codebase":
                    res = self.executor.execute_search(str(args.get("concept","")))
                    tool_outputs.append(types.Part.from_function_response(name=fname, response={"result": res}))
                    
                elif fname == "inspect_component":
                    img_bytes, neighbors, filename = self.executor.execute_inspect(str(args.get("family","")))
                    
                    # Multimodal Function Response - Embed image directly
                    if img_bytes:
                         logger.info(f"   📸 Embedding {len(img_bytes)} bytes in function response.")
                         
                         # Create the multimodal part
                         multimodal_part = types.FunctionResponsePart(
                             inline_data=types.FunctionResponseBlob(
                                 mime_type="image/png",
                                 display_name=filename,
                                 data=img_bytes,
                             )
                         )
                         
                         # Include image reference in response
                         tool_outputs.append(types.Part.from_function_response(
                             name=fname,
                             response={
                                 "neighbors": neighbors,
                                 "visual": {"$ref": filename}
                             },
                             parts=[multimodal_part]
                         ))
                    else:
                         # No image found
                         tool_outputs.append(types.Part.from_function_response(
                             name=fname,
                             response={"neighbors": neighbors, "status": "not_found"}
                         ))

                elif fname == "save_implementation_plan":
                    path = self.executor.save_plan(str(args.get("content","")))
                    logger.info("✅ Plan Saved.")
                    tool_outputs.append(types.Part.from_function_response(name=fname, response={"path": path}))
                    return # Done
            except Exception as e:
                logger.error(f"Call {fname} failed: {e}")
                tool_outputs.append(types.Part.from_function_response(name=fname, response={"error": str(e)}))

        # --- Turn 2 ---
        logger.info("📤 Sending Function Responses with Embedded Images...")
        history.append(types.Content(role="tool", parts=tool_outputs))

        response_2 = retry_call(
            self.client.models.generate_content,
            model="gemini-3-flash-preview",
            contents=history,
            config=types.GenerateContentConfig(tools=tools_list)
        )
        
        if not response_2: raise RuntimeError("No response Turn 2")
        
        if response_2.function_calls:
             for call in response_2.function_calls:
                 if call.name == "save_implementation_plan":
                      args = dict(call.args)
                      self.executor.save_plan(str(args.get("content","")))
                      logger.info("✅ Final Plan Saved.")

        if response_2.text:
             print(response_2.text)

if __name__ == "__main__":
    BatchAgent().run("I need a dashboard with a transaction table. Full implementation.")
