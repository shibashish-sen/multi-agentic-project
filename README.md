# ✈️ Travel Intelligence Platform

> **From a natural-language travel request to a researched, cost-aware travel plan:  powered by multi-agent orchestration and MCP tools.**

Built to explore how **AI agents, deterministic workflows, MCP, and RAG** can work together to solve a real-world planning problem.

## 💡 What does it do?

Give it a request like:

> *"Plan a 5-day trip from Mumbai to Delhi under $500, prioritizing budget flights and accommodation."*

The system autonomously:

- ✈️ Researches flights
- 🏨 Finds and compares hotels
- 🌤️ Retrieves weather information
- 🗺️ Researches activities and destination information
- 💰 Calculates and validates the trip budget
- 📋 Produces a consolidated travel briefing

---

## How it works

                     User Request
                          │
                          ▼
                ┌─────────────────────┐
                │ Travel Orchestrator │
                │     LangGraph       │
                └─────────┬───────────┘
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
          Flight       Hotel      Activities
           Agent        Agent         Agent
              │           │           │
              └───────────┼───────────┘
                          ▼
                    MCP Tool Layer
                          │
        ┌─────────────────┐─────────────────┐─────────────────┐   
        ▼                 ▼                 ▼                 ▼                
     Flight API       Hotel API        Weather               RAG
        │                 │                 │                 │
        └─────────────────┼─────────────────┘─────────────────┘
                          ▼
                   Cost / Budget
                          │
                          ▼
                  Travel Briefing


## 🔌 MCP Tools

All external capabilities are exposed through MCP, including:

| Tool                 | Purpose                             |
| -------------------- | ----------------------------------- |
| ✈️ Flight Search     | Search and compare flights          |
| 🏨 Hotel Search      | Find accommodation and pricing      |
| 🌤️ Weather          | Retrieve destination forecasts      |
| 🗺️ Travel Knowledge | RAG-powered destination information |
| 💰 Cost Tools        | Calculate and validate trip costs   |


This allows the agents to interact with capabilities through a consistent tool interface rather than embedding API-specific logic inside each agent.


## 🛡️ Reliability

Agentic systems are easy to demo and harder to make dependable.

This project uses:

- Structured Pydantic outputs
- Explicit workflow state
- Tool failure handling and retries
- Deterministic cost calculations
- Constraint validation
- RAG for grounded information

A key design principle:

> *If a decision doesn't require an LLM, don't use one.*


## Setup

```bash
uv sync                     # or: pip install -e .
cp .env.example .env        # then fill in your keys
uv orchestrator.py
```

## 📸 Example

Mumbai <-> New Delhi · Aug 15–20, 2026 · Budget trip

![Demo](data/output/travel_example.gif)


## Roadmap: 

Planned direction for v2, using LangGraph (already a dependency):

- **Critic/review step** — an agent that checks the assembled plan against constraints (budget, dates, preferences) before the final summary is generated, and loops back if something's off.
- **Human-in-the-loop checkpoint** — surface the plan for approval/edits to have A2A communication and optimize budget according to user needs


## 🧰 Tech Stack

Python · LangGraph · MCP · LLMs · RAG · Supabase · Pydantic · FastAPI 
