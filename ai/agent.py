"""
Visual RAG Agent - Orchestrator with Recurrent Explore/Exploit Loop
====================================================================
Principal Architect that uses visual codebase analysis with recursive sub-task exploration.
"""
from orchestrator import OrchestratorAgent
from google.genai.types import Part
import workflow
import os
import json
import logging
import argparse
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import time
from datetime import datetime
import io
from worker import TaskResult,WorkerAgent
try:
    from google import genai
    from google.genai import types
    from PIL import Image
    import PIL.Image
except ImportError:
    raise ImportError("CRITICAL: 'google-genai' library is required.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
PIL.Image.MAX_IMAGE_PIXELS = None




class VisualRAGPipeline:
    """
    Full pipeline: Orchestrator -> Worker Agents
    Production-level implementation with result tracking.
    """
    
    def __init__(self, tiles_dir: str):
        self.tiles_dir = tiles_dir
        self.api_key = "AIzaSyBvvlaZaKCY9RWYwOa_f1jlOJkO0p6mV2Q"
        self.client = genai.Client(api_key=self.api_key)
        self.decoder = workflow.VisualDecoder(tiles_dir)
        self.vocab_index = workflow.VocabularyIndex(tiles_dir)
        self.orchestrator = OrchestratorAgent(tiles_dir)
        self.results: List[TaskResult] = []
    
    def run(self, query: str):
        """Run the full pipeline."""
        logger.info("=" * 60)
        logger.info("🚀 VISUAL RAG PIPELINE")
        logger.info("=" * 60)
        
        # Phase 1: Orchestrator generates plan
        logger.info("\n📐 PHASE 1: ORCHESTRATOR")
        self.orchestrator.run(query)
        
        # Load the generated plan
        plan_path = os.path.join(self.orchestrator.gen_dir, "implementation_plan.md")
        if not os.path.exists(plan_path):
            logger.error("No plan generated!")
            return
        
        # # Parse tasks from plan
        # tasks = self._extract_tasks_from_plan(plan_path)
        
        # if not tasks:
        #     logger.warning("No tasks found in plan")
        #     return
        
        # logger.info(f"\n🔧 PHASE 2: WORKER AGENTS ({len(tasks)} tasks)")
        
        # # Phase 2: Worker agents execute each task
        # worker = WorkerAgent(
        #     client=self.client,
        #     decoder=self.decoder,
        #     vocab_index=self.vocab_index,
        #     output_dir=self.orchestrator.output_dir,
        #     legend_path=self.decoder.get_legend_path()
        # )
        
        # for i, task in enumerate(tasks):
        #     logger.info(f"\n--- Task {i+1}/{len(tasks)} ---")
        #     result = worker.execute_task(task)
        #     self.results.append(result)
            
        #     if result.success:
        #         logger.info(f"   ✅ SUCCESS: {result.filename}")
        #     else:
        #         logger.warning(f"   ❌ FAILED: {result.error}")
            
        #     time.sleep(2)  # Rate limiting
        
        # # Summary
        # successful = sum(1 for r in self.results if r.success)
        # logger.info("\n" + "=" * 60)
        # logger.info("✅ PIPELINE COMPLETE")
        # logger.info(f"   Output: {self.orchestrator.output_dir}")
        # logger.info(f"   Success: {successful}/{len(self.results)} tasks")
        # logger.info("=" * 60)
        
        # # Save cookbook
        # self._save_cookbook()
    
    def _extract_tasks_from_plan(self, plan_path: str) -> List[Dict]:
        """Extract tasks from the markdown plan."""
        tasks = []
        
        with open(plan_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Simple parsing - look for Task sections
        import re
        task_pattern = r'### Task \d+:.*?\n(.*?)(?=### Task|\Z)'
        matches = re.findall(task_pattern, content, re.DOTALL)
        
        for match in matches:
            task = {}
            
            # Extract fields
            file_match = re.search(r'\*\*File\*\*:\s*`([^`]+)`', match)
            if file_match:
                task['filename'] = file_match.group(1)
            
            ref_match = re.search(r'\*\*Reference\*\*:\s*`([^`]+)`', match)
            if ref_match:
                task['reference_family'] = ref_match.group(1)
            
            desc_match = re.search(r'\*\*Description\*\*:\s*(.+?)(?=\n\n|\Z)', match, re.DOTALL)
            if desc_match:
                task['description'] = desc_match.group(1).strip()
            
            role_match = re.search(r'\*\*Role\*\*:\s*(\w+)', match)
            if role_match:
                task['role'] = role_match.group(1)
            
            if task.get('filename'):
                task['id'] = f"task_{len(tasks)+1}"
                tasks.append(task)
        
        return tasks
    
    def _save_cookbook(self):
        """Save all generated code as a single cookbook markdown file."""
        cookbook_path = os.path.join(self.orchestrator.gen_dir, "cookbook.md")
        
        lines = [
            "# Implementation Cookbook\n\n",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n",
            "---\n\n",
        ]
        
        # Table of contents
        lines.append("## Table of Contents\n\n")
        for i, r in enumerate(self.results):
            if r.success:
                anchor = r.filename.replace("/", "_").replace("\\", "_").replace(".", "_")
                lines.append(f"{i+1}. [{r.filename}](#{anchor})\n")
        lines.append("\n---\n\n")
        
        # Code sections
        for r in self.results:
            if r.success and r.code:
                anchor = r.filename.replace("/", "_").replace("\\", "_").replace(".", "_")
                ext = r.filename.split(".")[-1] if "." in r.filename else "tsx"
                
                lines.append(f"## {r.filename} {{#{anchor}}}\n\n")
                if r.description:
                    lines.append(f"**Description:** {r.description}\n\n")
                lines.append(f"```{ext}\n{r.code}\n```\n\n")
                lines.append("---\n\n")
        
        # Statistics
        total_prompt = sum(r.prompt_tokens for r in self.results)
        total_output = sum(r.output_tokens for r in self.results)
        total_all = sum(r.total_tokens for r in self.results)
        
        lines.append("## Summary\n\n")
        lines.append(f"- **Total Tasks:** {len(self.results)}\n")
        lines.append(f"- **Successful:** {sum(1 for r in self.results if r.success)}\n")
        lines.append(f"- **Failed:** {sum(1 for r in self.results if not r.success)}\n")
        lines.append(f"- **Total Explorations:** {sum(r.explorations for r in self.results)}\n\n")
        
        # Token usage table
        lines.append("### Token Usage (Workers)\n\n")
        lines.append("| Task | File | Prompt | Output | Total |\n")
        lines.append("|------|------|--------|--------|-------|\n")
        for r in self.results:
            lines.append(f"| {r.task_id} | `{r.filename}` | {r.prompt_tokens:,} | {r.output_tokens:,} | {r.total_tokens:,} |\n")
        lines.append(f"| **TOTAL** | | **{total_prompt:,}** | **{total_output:,}** | **{total_all:,}** |\n\n")
        
        if any(not r.success for r in self.results):
            lines.append("### Failed Tasks\n\n")
            for r in self.results:
                if not r.success:
                    lines.append(f"- `{r.filename}`: {r.error}\n")
        
        with open(cookbook_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        logger.info(f"📚 Cookbook saved: {cookbook_path}")
        logger.info(f"📊 Worker Tokens: {total_prompt:,} prompt + {total_output:,} output = {total_all:,} total")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Visual RAG Agent - Analyze codebase and generate implementation plans.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agent.py --tiles ./repo_blimpt_tiles --query "Add user authentication"
  python agent.py -t ./my_project_tiles -q "Implement MCP integration"
"""
    )
    parser.add_argument(
        "--tiles", "-t",
        required=True,
        help="Path to the tiles directory (e.g., repo_name_tiles/)"
    )
    parser.add_argument(
        "--query", "-q",
        required=True,
        help="The implementation query/request"
    )
    
    args = parser.parse_args()
    
    # Validate tiles directory
    if not os.path.isdir(args.tiles):
        print(f"Error: Tiles directory not found: {args.tiles}")
        exit(1)
    
    # Run pipeline
    pipeline = VisualRAGPipeline(args.tiles)
    pipeline.run(args.query)
