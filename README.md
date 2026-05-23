# Athenaeum

AI character social simulation platform — a group of AI characters with independent personalities live autonomously in a dynamic world, interacting and forming relationships.

## Overview

Athenaeum 是一个AI角色社交模拟平台，多个具有独立个性的AI角色在动态世界中自主生活、互动并形成关系。用户可以旁观或"附身"任何角色来驱动故事情节。

## Architecture

Four core components:

| Component | Role |
|-----------|------|
| **WorldX** | World engine — space, time, relationships, event broadcasting |
| **Zyantine** | Personality engine — desires, memory, decision logic per agent |
| **Agent Mesh** | Social network — inter-agent communication via NATS |
| **User Portal** | User interface — observation mode, possession mode |

## Quick Start

See individual version folders (v0.1 - v0.5) for phased implementation.

## Documentation

- `SPEC.md` — Complete system specification
- `athenaeum.md` — Project overview
- `Athenaeum 分阶段开发路线图.txt` — Phased roadmap
- `Athenaeum 架构核心决策记录.txt` — Architecture Decision Records

## License

MIT