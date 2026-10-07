# PreCog-2nd-Brain

PreCog-2nd-Brain is a provenance-first, temporal, continuously consolidating memory substrate for agentic systems.

Core model:
Experience -> Consolidation -> Knowledge -> Capability -> Behavior -> Experience

PreCog is the persistent cognitive substrate. XP.2Flow is the declarative architecture that composes the transformations.

Design law: preserve experience as evidence; derive memory and knowledge from it; never make a lossy summary the sole source of truth.

Layers:
- Experience: immutable events and trajectories.
- Memory: episodic, semantic, entity, procedural and observational representations.
- Retrieval: lexical, semantic, entity, temporal and relation-aware retrieval.
- Consolidation: RCA, reflection, abstraction, deduplication, contradiction handling and validation.
- Behavior: future BehaviorID, TrajectoryID, PreCog and BestNextAction integration.
- Capability: future skills, code, policies and model evolution.

Repository status: specification-first. The normative contract is in PRE-CORD.md.

Initial baseline: TypeScript + PostgreSQL + JSONB + pgvector + filesystem/Markdown + Git, with provider-neutral adapters.

Non-goals: vector DB as source of truth, blind prompt injection of memories, provider lock-in, fine-tuning as the first memory mechanism, or destructive replacement of experience.