# AGENTS.md

Repo-specific notes for working in Athenaeum. Read this before editing code; the
project has cross-version path dependencies and a layered layout that is not
obvious from the directory tree.

## Frontend regression rule

**任何对 `v0.7/client/src/types/api.ts` 或 `v0.7/server/server.py` 中 `/world/state` 端点的改动,完成后必须跑 `cd v0.7/client && npm run test:scan`** — 该测试覆盖 9 个 tab、采集 console errors 和网络失败,会捕捉 schema 严格度问题(如 `mood: null` / `active_goal: dict` 渲染崩 React)和状态形状不匹配。

## Project shape

Athenaeum is an **AI character social simulation platform** (FastAPI + React +
Ollama, see `README.md`, `SPEC.md`, `athenaeum.md`).

Layout is a sequence of self-contained subprojects, one per milestone. **The
current / canonical version is `v0.7/`** (灵魂增强版 / "Soul"). Earlier versions
are kept on disk for reference; they are not parallel packages.

```
v0.1  Python CLI, single agent                    (legacy)
v0.2  Two agents, async dialogue                  (legacy)
v0.3  Two agents + React dashboard (Vite)         (legacy)
v0.4  Worldsmith UI for world/character gen       (legacy)
v0.5  Memory: archiver + retriever + forgetting   (shared base)
v0.6  — referenced in README but NOT on disk —
v0.7  Soul: inner conflict, subconscious, story   (current)
```

## Cross-version import gotcha (read this first)

Versions are **layered, not isolated**. `v0.7/server/server.py:22` injects
`v0.5/server` into `sys.path`, and `v0.5/server/server.py:27-32` injects
`v0.4` and `v0.3/server` similarly. Concretely:

- `v0.7/server` reuses `v0.5/server/core/{world_engine, dialogue_engine, agent, ...}`.
- `v0.5/server` reuses `v0.4/{worldsmith, world_models}` and
  `v0.3/server/{core, utils}`.

Implications:
- Don't "clean up" by deleting an older version — its `core/` modules are
  imported at runtime by newer servers.
- Imports like `from utils.ollama_client import ...` only resolve from
  whichever version's `server/` you launched. If you see `ModuleNotFoundError`
  for a name that clearly exists somewhere in the tree, check that the running
  server's `sys.path` includes the right older version.
- The `v0.5/server/v0.7/server` symlink-style directory was a stub (now deleted); do not recreate.

## Running the current version (v0.7)

Two paths; the shell script is the documented one.

```bash
# 1. Shell script (creates venv, pip installs, prompts for LLM mode):
./v0.7/start_v0.7.sh
# Default: local Ollama only. Option 2 sets MINIMAX_API_KEY / ANTHROPIC_API_KEY
# for cloud-backed world/summarisation while dialogue stays local.

# 2. Manual (if venv at v0.7/server/venv already exists):
cd v0.7/server && source venv/bin/activate && python server.py
# API: http://localhost:8000  Health: http://localhost:8000/health
```

The shell script only pip-installs `fastapi uvicorn pydantic httpx anthropic
numpy`; it omits `chromadb` (in `requirements.txt`). Chroma is optional — the
archiver falls back to disk at `v0.7/server/archiver_fallback/`. If you want
semantic memory, `pip install chromadb` and run Chroma separately.

**Frontend must be built before the root URL serves UI** — `server.py:140-144`
only returns `index.html` if `v0.7/client/dist/index.html` exists. Build it:

```bash
cd v0.7/client && npm install && npm run build
# Dev mode: npm run dev (separate port; e2e tests target :8000)
```

## LLM configuration

Read by `v0.7/server/server.py:56-71`:

| Env var | Default | Purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama endpoint |
| `USE_OLLAMA` | `1` | `1` = try local first, `0` = cloud only |
| `ANTHROPIC_API_KEY` / `MINIMAX_API_KEY` | unset | Cloud key (base URL hardcoded to `https://api.minimaxi.com/anthropic`) |

Models used (see `v0.5/pull_models.sh`):
- Chat: `qwen3.5:4b`  → `ollama pull qwen3.5:4b`
- Embeddings: `bge-m3`  → `ollama pull bge-m3`

ADR-006 (LLM gateway / budget) lives in `Athenaeum 架构核心决策记录.txt`. All
LLM calls must go through `LLMGateway`; do not call `httpx` directly from
feature code.

## Tests

No pytest config — tests are run as plain scripts.

```bash
# v0.7 soul unit tests — must be run from the v0.7/ directory
# (the test does `sys.path.insert(0, '.')` then imports `server.core.*`).
cd v0.7 && python tests/test_v07_soul_system.py

# v0.7 e2e (Playwright) — needs the FastAPI server up on :8000 and the
# frontend built (npm run build) so / serves the React app.
cd v0.7/client && npx playwright test
# Config: playwright.config.ts (chromium only, 30s timeout, html report).
```

Other ad-hoc test files that you may trip over:
- `test_character_gen.py` at repo root — hardcoded absolute paths
  (`/Volumes/Ollama-Models/Athenaeum/v0.3/server`, `v0.4`). It is a one-off
  script, not a real test, and is **not portable** off this machine.
- `v0.7/server/core/test_goal_manager.py`, `test_v07_agent.py` — module-level
  scripts inside `core/`. Run with `python v0.7/server/core/test_*.py`.

## Docker

`v0.5/docker-compose.yml` is the only compose file. Despite living under v0.5,
its comments and `pull_models.sh` reference v0.7 — that is intentional (v0.5
composes the v0.7-era stack). Services:

- `ollama` (`:11434`) — local LLM
- `chroma` (`:8001`) — vector DB
- `backend` (`:8000`) — built from `v0.5/Dockerfile`
- `frontend` (`:3000`) — built from `v0.7/Dockerfile.frontend`

The compose file's `pull_models.sh` lives in `v0.5/` (header says "V0.7" —
keep it where compose expects it).

## Hardcoded constraints (from ADRs — do not change without ADR amendment)

Source: `Athenaeum 架构核心决策记录.txt`.

- **ADR-001** — Agents use `decide() → arbitrate() → express()`. Structured
  intent is `{intent_type, target, reasoning, urgency, emotion}`.
- **ADR-002** — Inter-module messages use fixed NATS topics
  (`world.tick.{tick_id}`, `agent.intent.{agent_id}`,
  `agent.dialogue.{from}.{to}`, `system.event.{event_id}`). Don't invent new
  topic shapes.
- **ADR-003** — Desire state is a need queue
  (`Need{name, level, target}` → `DesireState{TR, CS, SA}`), not static floats.
- **ADR-004** — `_infer_state()` is cached and only refreshed on
  interaction/significant events; agents cannot read each other's internal
  state directly.
- **Interface definitions are hardcoded from V0.1** for forward compatibility
  (see `v0.7/server/core/interfaces.py`). New modules implement `ILLMClient`,
  `IDecisionEngine`, etc. — don't bypass them.

## World rules (game time)

```
1 real minute = 1 game hour
1 real hour  = 1 game day
```

`v0.5/server/core/world_engine.py` is the source of truth for tick scheduling
and time-of-day. Default `tick_interval_seconds=2.0` (set in
`v0.7/server/server.py:73`).

## Documentation map

| File | Use it for |
|---|---|
| `README.md` | Project pitch, version history, quick start |
| `SPEC.md` | Full system spec (v2.0) |
| `athenaeum.md` | High-level overview + integration strategy |
| `Athenaeum V1.0版本开发计划.txt` | v1.0 dev plan (roadmap) |
| `Athenaeum 分阶段开发路线图.txt` | Phased delivery roadmap |
| `Athenaeum 架构核心决策记录.txt` | ADRs (immutable constraints) |
| `Athenaeum评估报告0524.txt` | Internal evaluation report |
| `WorldAgent.txt` | Reference narrative for the world |
| `v0.7/README.md`, `v0.7/TEST_FEATURES.md` | v0.7-specific behaviour + test checklist |
| `CLAUDE.md` | Behavioral guidelines for Claude (general, not repo-specific) |

## Style / workflow notes

- No linter, no formatter, no typecheck script is configured at the repo root
  or in `v0.7/`. Python: PEP 8 by convention. TS/React: project uses React 18
  + Vite 5 + TS 5; match the patterns in `v0.7/client/src/components/`.
- Comments and identifiers mix Chinese and English; preserve the surrounding
  file's language rather than translating. New user-facing strings in the
  frontend follow the existing Chinese labels (e.g. tab names
  `仪表盘 角色 对话 灵魂 工坊 日记 时间线 地图 附身`).
- No CI workflows under `.github/` — verification is manual
  (`python tests/...py`, `npx playwright test`, `curl /health`).
- `.gitignore` is minimal. `__pycache__/`, `node_modules/`, and the
  per-server `venv/` are ignored; per-version `dist/`, `playwright-report/`,
  `test-results/`, `chroma_data/`, and `archiver_fallback/` are **not** ignored
  — do not commit generated artefacts from those paths.
