# Revenue Intelligence Platform

## Project
Enterprise Revenue Intelligence Platform — natural language revenue analytics for CXOs.
Stack: FastAPI + PostgreSQL + React + Celery + Redis + Python MCP SDK.
Phase 1 — (Core Schema + Excel Import ONLY).
Phase 2 — Revenue Analytics Engine
Phase 3 — MCP Natural Language Interface
Phase 4 — HubSpot Integration
Phase 5 — Enterprise Intelligence Expansion

## Active Phase
CURRENT_PHASE=1
Do not build features from a future phase unless explicitly told to switch phases.
When switching phases, I will say: "Switch to Phase X"

## Team Skills Available
You have role-based skill rules. Reference them by name when needed:
- @product-owner      → scope, user stories, acceptance criteria, prioritization
- @technical-architect → schema, DB design, architecture decisions, performance
- @tech-lead           → writing code, file structure, API, React components
- @ux-ui-designer      → UI design, component specs, user flows, design system
- @quality-analyst     → test cases, validation, bug reports, release checklist

## Always Follow
- Never change the DB schema without consulting @technical-architect first
- Never mark a feature done without @quality-analyst sign-off
- Never build Phase 2 while Phase 1 is incomplete
- All primary keys are UUIDs, all amounts are NUMERIC(18,4), never FLOAT

## Stack
FastAPI + PostgreSQL + React + Celery + Redis + OpenAI API (model from .env)
Never hardcode model names. Always read from settings.OPENAI_MODEL.
Never hardcode API keys. Always read from settings.OPENAI_API_KEY.
Always implement complete functionality, no todos or future implementations.
Always use production ready code and follow the high standards and optimization techniques.