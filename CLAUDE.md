# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AiBeing is an AI Being (AI companion) engine. It implements the **Genome v10 Hybrid** personality engine where character behavior emerges from an internal dynamics system (drives × neural network × Hebbian learning) rather than static prompt descriptions.

Each conversation turn flows through a 12-step lifecycle: Task Skill → EverMemOS context → Time Metabolism → Critic Perception (LLM → 8D context + 5D frustration delta) → Relationship EMA → Drive Baseline Evolution → Crystallization → Signal Computation → Thermodynamic Noise → KNN Style Retrieval → Single-Pass Actor (monologue + reply + modality) → Modality Skill Execution → Hebbian Learning → Async Memory Storage.

## Common Commands

```bash
# Start backend
uvicorn main:app --host 0.0.0.0 --port 8000

# Run tests
pytest

# Run single test
pytest tests/test_persona_engine.py -v

# Setup (first time)
bash setup.sh
# Or manually:
#   python3 -m venv .venv && source .venv/bin/activate
#   pip install -r requirements.txt
#   cp .env.example .env
#   # edit .env with API keys
```

## High-Level Architecture

### Gateway Layer (`main.py`)
- FastAPI + WebSocket (`/ws/chat`) for real-time chat
- REST APIs for persona management, status, TTS, image generation
- Session auto-cleanup with TTL (30 min)
- Proactive heartbeat loop (every 5 min) for drive-driven autonomous messages
- Global services initialized in `startup()` event handler

### Agent Layer (`agent/`)
- **`chat_agent.py`** — Core orchestrator implementing the 12-step Genome v10 lifecycle. Uses `asyncio.Lock` per turn for concurrency safety.
- **`prompt_builder.py`** — Builds the single-pass Actor prompt (persona + signals + few-shot + memory injection)
- **`evermemos_mixin.py`** — EverMemOS integration (cloud + self-hosted dual mode)
- **`proactive.py`** — Drive impulse detection and autonomous message generation
- **`skills/`** — Dual skill engine:
  - `task_skill_engine.py` — ReAct loop for user-requested tasks (weather, search)
  - `modality_skill_engine.py` — Persona-intrinsic skills (selfie, voice, silence, split message)

### Personality Engine (`engine/genome/`)
- **`genome_engine.py`** — The `Agent` class: random neural network (25D→24D→8D) with Hebbian learning, frustration-driven phase transitions, and weight decay
- **`drive_metabolism.py`** — Time-aware drive metabolism: cooling (exponential decay) + hunger (linear accumulation) + thermodynamic noise
- **`critic.py`** — LLM-based perception: converts user input to 8D context + 5D frustration delta + 3D relationship delta + 5D drive satisfaction
- **`style_memory.py`** — KNN-based style memory with gravitational mass weighting and Hawking radiation decay. Crystallization merges nearby contexts.

### Provider Layer (`providers/`)
- **`llm/`** — Unified LLM client supporting 8 providers (Gemini, Claude, Qwen3, GPT, MiniMax, Moonshot, StepFun, Ollama). Config in `api.yaml`, env var override.
- **`media/tts_engine.py`** — TTS with multiple providers (DashScope, OpenAI, MiniMax)
- **`image/`** — Image generation (Gemini Imagen)
- **`memory/evermemos/`** — Long-term memory adapter with dual-mode support (cloud `api.evermind.ai` vs self-hosted `localhost:1995`)

### Persona System (`persona/`)
- **`loader.py`** — Parses `SOUL.md` (YAML frontmatter + markdown body) and `SHELL.md` (voice/image config)
- **`personas/{id}/`** — Each persona directory contains:
  - `SOUL.md` — Identity, genome_seed (drive baseline + engine params), personality sections
  - `SHELL.md` — Voice description and image config
  - `avatar.png` — Static avatar
- Character behavior is **not described in prompts** — it emerges from the drive baseline and random neural network seed configured in `SOUL.md`'s `genome_seed` block.

### Memory Architecture (3 layers)
1. **Style Memory** (`engine/genome/style_memory.py`) — SQLite-backed KNN retrieval. Session-scoped, persists Hebbian-like behavior patterns.
2. **Local Facts** (`memory/memory_store.py`) — SQLite FTS5 for user preferences and conversation history.
3. **Long-term Memory** (`providers/memory/evermemos/`) — Cross-session persistent memory (user profile, episode narratives, foresight) via EverMemOS API.

### Skills System (`skills/`)
Skills are defined in `SKILL.md` files with YAML frontmatter:
- `trigger: tool` — Task skills (weather, search) executed via ReAct loop before the persona engine
- `trigger: modality` — Intrinsic skills (selfie, voice, silence) triggered by the Actor's modality output
- `trigger: cron` — Scheduled proactive skills

## Environment Configuration

All API keys and provider settings live in `.env` (copied from `.env.example`). Key variables:
- `DEFAULT_PROVIDER` / `DEFAULT_MODEL` — Active LLM
- `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc. — Provider keys
- `EVERMEMOS_BASE_URL` / `EVERMEMOS_API_KEY` — Long-term memory (optional)

Provider presets and defaults are also in `providers/api.yaml`. Env vars always take precedence.

## Important Design Constraints

- **No static personality prompts**: Do not add "she is gentle" or "she is sarcastic" to system prompts. Personality emerges from `genome_seed.drive_baseline` and neural network weights in the Agent class.
- **Turn lock serialization**: `ChatAgent._turn_lock` serializes `chat()`, `chat_stream()`, and `proactive_tick()`. Never bypass this lock.
- **Async fire-and-forget memory**: EverMemOS `store_turn()` and `search_relevant_memories()` are always launched via `asyncio.create_task()` to avoid blocking the conversation flow.
- **CAS state persistence**: `StateStore.save_state()` uses compare-and-swap with version numbers to prevent concurrent write conflicts.
- **Single-pass Actor**: The LLM generates monologue, reply, and modality in one call. Do not split into separate LLM calls.

## Workflow Conventions

- **Push after every change**: After any code modification (edit, create, delete), commit and push to the remote repository immediately. Do not leave uncommitted or unpushed changes.
- **Deep analysis outputs to `research/`**: Whenever a deep analysis or research task is requested, save the full output as a Markdown file in the `research/` directory. Follow the directory hierarchy below.

## Documentation Structure (`research/`)

All project-level docs live under `research/`. Do not create new docs under `docs/` (that directory is removed; all development docs are consolidated here).

```
research/
├── ROADMAP.md, ARCHITECTURE.md, PRD.md, DEVELOP.md, CHANGELOG.md   # top-level project docs
├── guides/                    # operational guides (persona creation, skill engine, TTS)
├── analysis/                  # code analysis & audits (created on demand)
│   ├── README.md              # index + naming template
│   └── YYYY-MM-{topic}.md     # naming convention for new analysis docs
├── benchmarks/                # benchmark reports (LLM comparisons, persona tests)
├── references/                # external references, quick notes, API docs
└── archive/                   # superseded analysis docs (do not delete, move here)
```

**Rules for creating new docs:**
- **Code analysis / audit** → `research/analysis/YYYY-MM-{topic}.md`, then register it in `analysis/README.md`
- **User-facing guide** (how to create a persona, how to integrate a provider) → `research/guides/{kebab-case}.md`
- **External API reference** → `research/references/{name}.md`
- **Benchmark / evaluation report** → `research/benchmarks/YYYY-MM-{topic}.md`
- **If a doc becomes outdated** → move it to `research/archive/` instead of deleting

**Internal links:** When referencing another doc, use relative paths from the doc's location (e.g., `../analysis/everos-cloud-api-audit.md` from `research/CHANGELOG.md`).
