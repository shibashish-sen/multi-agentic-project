# Travel Planning Orchestrator

A multi-agentic orchestration pipeline that plans a trip end-to-end: flights, hotel, weather, and a cost estimate 

## How it works

```
TripRequest (structured input)
        |
        v
  asyncio.gather( flights, hotel, weather x2, itinerary RAG )   <- runs in parallel
        |
        v
  cost estimate 
        |
        v
 human-readable trip summary
```



## Setup

```bash
uv sync                     # or: pip install -e .
cp .env.example .env        # then fill in your keys
python orchestrator.py
```

## Roadmap: 

Planned direction for v2, using LangGraph (already a dependency):

- **Critic/review step** — an agent that checks the assembled plan against constraints (budget, dates, preferences) before the final summary is generated, and loops back if something's off.
- **RAG-backed itinerary agent** — wiring up the Supabase pgvector lookup (currently a placeholder in `get_itinerary_context`) so it can pull real attraction/meal data and reason over it.
- **Human-in-the-loop checkpoint** — surface the plan for approval/edits before booking-adjacent actions, using LangGraph's interrupt support.

