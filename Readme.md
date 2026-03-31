Code Base Compressor — Codebase Pattern Analyzer & Tile Visualizer
A two-stage pipeline that analyzes JavaScript/TypeScript repositories, extracts structural usage patterns, and renders them as deterministic pixel-tile images for visual inspection and downstream processing.

---

Overview
The pipeline consists of two main components:
File Role
main.py Stage 1 — Scans a repo, extracts patterns, and outputs a structured JSON file
tiles.py Stage 2 — Consumes the JSON, tokenizes patterns via AST, and renders tile images

---

How It Works
Stage 1 — main.py: Pattern Extraction
Scans all .js, .ts, .jsx, .tsx source files (excluding build files) in a target repository and extracts the following pattern types:

- Call patterns — function/method call chains (e.g. api.getData(...))
- JSX patterns — component usage (e.g. ``)
- Constant patterns — named constant definitions
- Component definitions — React component definitions with props and return types
- Type definitions — TypeScript type/interface declarations
- Reference patterns — named identifier references
  After extraction, patterns are grouped, filtered, deduplicated, and cleaned. The final output is a single JSON file containing all pattern categories plus a vocabulary set and a summary.
  Token counting via tiktoken is also performed on the scanned files.
  Usage
  python main.py --path ./my-repo
  Arguments:
  Flag Default Description
  --path repo Path to the repository to analyze
  --output \_patterns.json Output JSON file path
  --exclude-dts false Exclude TypeScript declaration files
  Output: A \_patterns.json file consumed by Stage 2.

---

Stage 2 — tiles.py: Tile Image Rendering
Reads the JSON produced by Stage 1 and renders a visual tile map where each unique pattern family (component, call chain, constant, etc.) becomes a colored block of deterministic pixel tiles.
How Tiles Work

- Each token family (e.g. Button::JSX, api.get::CALL) gets a unique, deterministic color and texture glyph derived from a SHA-256 hash of its name.
- Tokens are laid out as 16×16 pixel tiles in rows within labeled blocks.
- Blocks are shelf-packed onto a canvas. If the canvas exceeds max_dimension (default 10000px), it is automatically split into multiple numbered image files.
- A legend image is generated alongside the main tiles, mapping glyph visuals to family names.
  Glyph Patterns
  Each family's glyph has:
- A base RGB color (derived from hash bytes 0–2)
- One of 6 texture patterns (stripes, checkerboard, diagonals, border frame, etc.) selected from hash byte 3
- An optional 2×2 corner checksum marker for disambiguation
  Special families:
- PAD → solid white tile (padding)
- SEP → solid black tile (row separator)
  Usage
  python tiles.py
  Output directory: \_tiles/
  File Description
  tiles.png (or tiles_1.png, tiles_2.png, ...) Main tile image(s)
  tiles_legend.png Visual legend of all rendered families
  tiles.vocab.json List of all unique families in the output
  tiles.coords.json Bounding box coordinates for every rendered block
  tiles.manifest.json Per-image breakdown of families and image paths
  tiles.analysis.json Parent/child relationship analysis between families
  map.json Full registry mapping disambiguated names to source metadata

---

Architecture
main.py
├── analyzer.config — File glob patterns
├── analyzer.extractors — Per-file AST extraction (tree-sitter)
├── analyzer.processing — Grouping, filtering, cleaning
└── → \_patterns.json
tiles.py
├── TileConfig — Rendering configuration (tile size, max dimension, etc.)
├── glyph_for_family() — Deterministic glyph generation from SHA-256 hash
├── encode_rows_to_image() — Core layout engine (shelf packing + canvas rendering)
├── generate_legend() — Legend image generation
└── → \_tiles/

---

Requirements
Pillow
numpy
tiktoken
tree-sitter (via analyzer.core.languages)
Install dependencies:
pip install pillow numpy tiktoken
Tree-sitter language parsers must be available via the analyzer.core.languages module (used internally for AST tokenization in tiles.py).

---

Configuration
TileConfig (in tiles.py) controls rendering behavior:
Parameter Default Description
tile_size 16 Width and height of each tile in pixels
pad_family "PAD" Token name used for padding tiles
sep_family "SEP" Token name used for separator tiles
background (30, 30, 30) Canvas background color
use_checksum_corner True Adds a 2×2 corner marker to each glyph
max_dimension 10000 Maximum canvas size before image splitting

---

Token Disambiguation
Identifiers extracted from the codebase are disambiguated by kind using the :: notation:
Suffix Meaning
::JSX JSX component usage
::CALL Function/method call chain
::CONST Constant definition
::DEF Component definition
::BORDER Internal glyph variant for block borders

---

Example Pipeline

# Step 1: Extract patterns from a repository

python main.py --path ./my-react-app --exclude-dts

# Step 2: Render tile images from extracted patterns

python tiles.py my-react-app_patterns.json
Output images will be in my-react-app_tiles/.

---

Stage 3 — AI Layer: Visual RAG & Code Generation
The ai/ directory adds an intelligence layer on top of the tile pipeline. It uses the rendered tile images as a visual knowledge base (an "Atlas") and drives two LLM-powered workflows: a structured query agent and an autonomous scraper agent.

---

ai/agent.py — LangGraph Orchestration
Builds and runs two distinct LangGraph state machines that share the same node infrastructure.
Graph 1: Query Mode (build_graph)
A directed graph for answering a specific query about the codebase.
START → planner → bulk_inspector (loop) → synthesizer → END
Node Role
planner Decomposes the user query into inspection targets
bulk_inspector Inspects tile families, loops until all targets are resolved
synthesizer Aggregates inspection results into a final report
Graph 2: Scraper Mode (build_scraper_graph)
An autonomous graph that explores the codebase without a predefined query.
START → explorer → inspector (loop) → notetaker → (explorer or END)
Node Role
explorer Selects the next family or skill to explore
inspector Inspects targets, loops until the queue is empty
notetaker Records findings; re-queues explorer if more skills remain
Recursion depth is controlled by max_skills (default: 10), with a safety limit of max_skills \* 10 graph steps.
Usage
Requires a config.json file:
{
"dir": "my-react-app",
"model_name": "gpt-4o",
"provider": "openai",
"query": "How is authentication handled?",
"max_skills": 10,
"input": 2.5,
"output": 10.0
}

# Query mode

python -m ./ai.agent --config config.json

# Autonomous scraper mode

python -m ai.agent --config config.json --scrape
The dir field in config should be the base name of the repo (without \_tiles). The agent appends \_tiles automatically.

---

ai/worker.py — Pattern-Matching Code Generator
A single-task agent that generates source code by visually studying tile references. It runs on Gemini 2.5 Flash with tool-calling and extended thinking enabled.
Workflow
The worker enforces a strict explore-before-generate protocol:
Task Input
│
▼
[Context Assembly]

- WORKER_PROMPT (system role)
- Target filename + description
- Full vocabulary list
- Legend image (decode key)
- Reference visual crop + analysis data
  │
  ▼
  [Exploration Loop] (max 3 rounds)
  │
  ├── explore_reference(families)
  │ Queries the Atlas decoder for visual + structural data
  │ Returns: family props, neighbors, stitched tile image
  │
  └── generate_code(code, confidence) ← rejected until ≥1 exploration done
  Returns: final source code
  │
  ▼
  TaskResult
  Exploration Enforcement
  The agent rejects any generate_code call made before at least one explore_reference call. If the model attempts to generate prematurely, it receives an explicit rejection response and must explore first.
  TaskResult
  Field
  task_id
  filename
  success
  code
  explorations
  prompt_tokens
  output_tokens
  total_tokens
  Worker Tools
  Tool
  explore_reference(families)
  generate_code(code, confidence)

---

Full Pipeline Overview
Repository Source Code
│
▼
main.py ← Pattern extraction (tree-sitter AST)
│
▼
\_patterns.json
│
▼
tiles.py ← Visual encoding → tile images
│
▼
\_tiles/
├── tiles.png ← Visual Atlas
├── tiles_legend.png ← Decode key
├── tiles.coords.json
├── tiles.vocab.json
└── tiles.manifest.json
│
▼
ai/agent.py ← LangGraph orchestration (query or scraper)
│
▼
ai/worker.py ← Per-task code generator (Gemini 2.5 Flash)
│
▼
ai/output//
├── agent.log
├── worker.log
└──

---

AI Dependencies
google-genai
langgraph
langchain-openai
python-dotenv
pillow
pip install google-genai langgraph langchain-openai python-dotenv pillow
Environment variables required (.env):
OPENAI_API_KEY=...
GOOGLE_API_KEY=...
