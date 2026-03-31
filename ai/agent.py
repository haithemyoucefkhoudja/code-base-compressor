
import os
import logging
import json
from datetime import datetime
from typing import Dict, Optional

from langgraph.graph.state import BaseModel
from dotenv import load_dotenv

load_dotenv()

# try:
    
# except ImportError:
#     raise ImportError("Dependencies missing. Install: langgraph langchain-openai pydantic pillow")

from langgraph.graph import StateGraph, START, END
from utils.state import ResearchState
from utils.nodes import Nodes
from utils.llm import get_llm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def should_continue(state: ResearchState):
    """Decide whether to continue inspection or synthesize."""
    pending = state.get("pending_targets", [])
    if pending and len(pending) > 0:
        return "continue"
    return "done"

def should_explore_more(state: ResearchState):
    """Decide whether the scraper should continue exploring or finish."""
    skill_queue = state.get("skill_queue", [])
    if skill_queue and len(skill_queue) > 0:
        return "explore"
    return "done"

def build_graph(tiles_dir: str, config: Optional[Dict] = None):
    """
    Constructs the LangGraph for the Visual RAG Agent.
    """
    config = config or {}
    
    # 1. Initialize LLM
    model_name = config.get("model_name") or "gpt-4o"
    provider = config.get("provider") or "openai"
    pricing = config.get("pricing") or {
        "input": config.get("input", 1.0),
        "output": config.get("output", 1.0)
    }
    
    # Initialize Cost Tracker
    from utils.cost import CostTracker
    tracker = CostTracker()
    tracker.set_model(model_name)
    tracker.set_pricing(pricing)
    
    logger.info(f"🤖 Initializing LLM: {provider}/{model_name}")
    
    llm:BaseModel = get_llm(provider, model_name, config)

    logger.info(f"🧬 LLM Entity Schema:\n{llm.model_dump_json(indent=2)}")
    # 2. Initialize Nodes
    # We pass the Output Directory logic here
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"ai/output/{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Configure File Logging
    log_file = os.path.join(output_dir, "agent.log")
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(file_handler)
    logger.info(f"📝 Logging to: {log_file}")
    
    tools_config = {
        "tiles_dir": tiles_dir,
        "output_dir": output_dir
    }
    
    nodes = Nodes(llm, tools_config)
    
    # 3. Build StateGraph
    builder = StateGraph(ResearchState)
    
    builder.add_node("planner", nodes.planner_node)
    builder.add_node("bulk_inspector", nodes.bulk_inspector_node)
    builder.add_node("synthesizer", nodes.synthesizer_node)
    
    builder.add_edge(START, "planner")
    builder.add_edge("planner", "bulk_inspector")
    
    # Conditional Edge for Recursion
    builder.add_conditional_edges(
        "bulk_inspector",
        should_continue,
        {
            "continue": "bulk_inspector", 
            "done": "synthesizer"
        }
    )

    builder.add_edge("synthesizer", END)
    
    return builder.compile(), output_dir

def build_scraper_graph(tiles_dir: str, config: Optional[Dict] = None):
    """
    Constructs the autonomous Scraper LangGraph.
    Explorer -> Inspector -> NoteTaker -> (loop or END)
    """
    config = config or {}
    max_skills = config.get("max_skills", 10)
    
    # 1. Initialize LLM (shared setup)
    model_name = config.get("model_name") or "gpt-4o"
    provider = config.get("provider") or "openai"
    pricing = config.get("pricing") or {
        "input": config.get("input", 1.0),
        "output": config.get("output", 1.0)
    }
    
    from utils.cost import CostTracker
    tracker = CostTracker()
    tracker.set_model(model_name)
    tracker.set_pricing(pricing)
    
    logger.info(f"🤖 Initializing Scraper LLM: {provider}/{model_name}")
    
    llm: BaseModel = get_llm(provider, model_name, config)
    
    # 2. Output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"ai/output/scrape_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    log_file = os.path.join(output_dir, "agent.log")
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger().addHandler(file_handler)
    logger.info(f"📝 Scraper logging to: {log_file}")
    
    tools_config = {
        "tiles_dir": tiles_dir,
        "output_dir": output_dir
    }
    
    nodes = Nodes(llm, tools_config)
    
    # 3. Build the scraper graph
    builder = StateGraph(ResearchState)
    
    builder.add_node("explorer", nodes.explorer_node)
    builder.add_node("inspector", nodes.bulk_inspector_node)
    builder.add_node("notetaker", nodes.notetaker_node)
    
    builder.add_edge(START, "explorer")
    builder.add_edge("explorer", "inspector")
    
    # Inspector loops until done
    builder.add_conditional_edges(
        "inspector",
        should_continue,
        {
            "continue": "inspector",
            "done": "notetaker"
        }
    )
    
    # NoteTaker decides: explore more or finish
    builder.add_conditional_edges(
        "notetaker",
        should_explore_more,
        {
            "explore": "explorer",
            "done": END
        }
    )
    
    return builder.compile(), output_dir, max_skills

if __name__ == "__main__":
    # If run directly as script, provide CLI
    import argparse
    import json
    import traceback
    
    parser = argparse.ArgumentParser(description="Visual RAG Agent (LangGraph Structure)")
    parser.add_argument("--config", "-c", help="Path to config.json")
    parser.add_argument("--scrape", action="store_true", help="Run autonomous codebase scraper (no query needed)")
    
    args = parser.parse_args()
    
    # Config Logic
    config = {}
    if args.config:
        try:
            with open(args.config, 'r') as f: config = json.load(f)
        except: pass
    
    tiles_dir = config.get("dir")
    
    if not tiles_dir:
        print("Usage: python -m ai.agent --config config.json [--scrape]")
        exit(1)
    
    tiles_dir = tiles_dir + "_tiles"
    
    if args.scrape:
        # --- Autonomous Scraper Mode ---
        app, out_dir, max_skills = build_scraper_graph(tiles_dir, config)
        print(f"🔬 Running Codebase Scraper. Output: {out_dir} (max_skills: {max_skills})")
        try:
            app.invoke({
                "topic": "Autonomous codebase exploration",
                "current_skill": "",
                "documented_skills": [],
                "skill_queue": [],
                "inspection_results": [],
                "pending_targets": [],
                "visited_targets": [],
                "plan": None,
                "final_report": "",
            }, {"recursion_limit": max_skills * 10})  # Safety: ~10 graph steps per skill
        except Exception as e:
            print(f"\n❌ Scraper failed: {e}")
            traceback.print_exc()
        finally:
            from utils.cost import CostTracker
            CostTracker().print_summary()
    else:
        # --- Original Query Mode ---
        query = config.get("query")
        if not query:
            print("Usage: python -m ai.agent --config config.json (with 'query' in config)")
            exit(1)
        
        app, out_dir = build_graph(tiles_dir, config)
        print(f"🚀 Running Graph. Output: {out_dir}")
        try:
            app.invoke({
                "topic": query,
                "inspection_results": [],
                "plan": None,
                "final_report": "",
            })
        finally:
            from utils.cost import CostTracker
            CostTracker().print_summary()
