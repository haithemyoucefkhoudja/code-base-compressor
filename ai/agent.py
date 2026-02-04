
import os
import logging
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

def build_graph(tiles_dir: str, config: Optional[Dict] = None):
    """
    Constructs the LangGraph for the Visual RAG Agent.
    """
    config = config or {}
    
    # 1. Initialize LLM
    model_name = config.get("model_name") or "gpt-4o"
    provider = config.get("provider") or "openai"
    
    # Initialize Cost Tracker
    from utils.cost import CostTracker
    tracker = CostTracker()
    tracker.set_model(model_name)
    
    logger.info(f"🤖 Initializing LLM: {provider}/{model_name}")
    
    llm:BaseModel = get_llm(provider, model_name, config)
    
    # 2. Initialize Nodes
    # We pass the Output Directory logic here
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"ai/output/{timestamp}"
    
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

if __name__ == "__main__":
    # If run directly as script, provide CLI
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Visual RAG Agent (LangGraph Structure)")
    parser.add_argument("--config", "-c", help="Path to config.json")
    
    args = parser.parse_args()
    
    # Config Logic
    config = {}
    if args.config:
        try:
            with open(args.config, 'r') as f: config = json.load(f)
        except: pass
    
    tiles_dir = config.get("tiles_dir")
    query = config.get("query")
    
    if not tiles_dir or not query:
        print("Usage: python -m ai.agent --config")
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
