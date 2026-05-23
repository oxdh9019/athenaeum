# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Athenaeum is an **AI character social simulation platform** — a group of AI characters with independent personalities live autonomously in a dynamic world, interacting and forming relationships. Users can observe as bystanders or "possess" any character to drive storylines.

**Current state**: Pre-implementation. Only specification documents exist. Codebase is empty.

## Architecture

The system integrates four core components:

| Component | Role |
|-----------|------|
| **WorldX** | World engine — space, time, relationships, event broadcasting |
| **Zyantine** | Personality engine — desires, memory, decision logic per agent |
| **Agent Mesh** | Social network — inter-agent communication via NATS, relationship evolution |
| **User Portal** | User interface — observation mode, possession mode, world editing |

### Agent Decision Flow (ADR-001)

Agents use a **structured intent + arbitration** two-layer model (non-negotiable):

```
decide() → arbitrate() → express()
```

Each agent generates structured intent `{intent_type, target, reasoning, urgency, emotion}` before any action. The arbitration layer enforces core instincts before expression.

### Message Contracts (ADR-002)

All inter-module communication uses fixed NATS topics:

| Topic | Direction | Content |
|-------|-----------|---------|
| `world.tick.{tick_id}` | WorldX → Agent | Tick start, world state |
| `agent.intent.{agent_id}` | Agent → WorldX | Agent action intent |
| `agent.dialogue.{from}.{to}` | Agent → Agent | Inter-agent dialogue |
| `system.event.{event_id}` | System → All | Narrative injection |

### Desire State Model (ADR-003)

Desire state is driven by a **need queue**, not static floats:

```
Need: {name, level (0.0-1.0), target}
DesireState: {TR, CS, SA} — computed from need queue + environment
```

### Perception Tiering (ADR-004)

Agents cannot read other agents' internal state. `_infer_state()` is cached and only refreshed on interaction or significant events. Cache decay is proportional to relationship distance.

## Development Roadmap

Implementation follows phased milestones — each is independently deliverable and verifiable:

| Phase | Name | Goal |
|-------|------|------|
| **V0.1** | Soul Spark | Single agent with YAML config, CLI dialogue, memory |
| **V0.2** | You & Me | Two agents, async dialogue, relationship evolution, possession prototype |
| **V0.3** | World Pulse | 4+ location world, tick scheduling, environment influence, web dashboard |
| **V0.1** | Emergent Tales | Full world generation, narrative injection, plugin architecture |

**Key principle**: Interface definitions (e.g., `IDecisionEngine`) are hardcoded from V0.1 to ensure forward compatibility.

## Cost Control (ADR-006)

All LLM calls must route through `LLMGateway` with:
- Daily token/price budget
- Per-tick per-agent call limits
- Degradation strategies (cache/rule fallback when budget exhausted)

## Key Spec Files

| File | Purpose |
|------|---------|
| `SPEC.md` | Complete system specification (v2.0) |
| `Athenaeum 分阶段开发路线图.txt` | Phased delivery roadmap |
| `Athenaeum 架构核心决策记录.txt` | Architecture Decision Records (ADRs) — immutable constraints |
| `athenaeum.md` | Project overview and integration strategy |

## Time System

```
1 real minute = 1 game hour
1 real hour = 1 game day
```

## Configuration

Agent behaviors are driven by YAML config files with:
- Big Five personality (openness, conscientiousness, extraversion, agreeableness, neuroticism)
- Emergence parameters (level, creativity_bias, randomness_factor, social_sensitivity, stubbornness)
- Initial location, backstory, relationships
