# Research Basis

## Foundational papers

1. CoALA — Cognitive Architectures for Language Agents (Sumers et al., 2023). Modular cognitive architecture and memory/action separation.
2. Generative Agents — Interactive Simulacra of Human Behavior (Park et al., 2023). Memory stream, retrieval and reflection.
3. Reflexion (Shinn et al., 2023). Verbal feedback and episodic self-improvement.
4. MemGPT — Towards LLMs as Operating Systems (Packer et al., 2023). Hierarchical external memory and virtual context.
5. HippoRAG (Gutiérrez et al., 2024). Graph-assisted associative long-term retrieval.
6. A-MEM — Agentic Memory for LLM Agents (Xu et al., 2025). Self-organizing memory units and links.
7. HippoRAG 2 (Gutiérrez et al., 2025). Non-parametric continual learning through retrieval.
8. Rethinking Memory in AI (Du et al., 2025). Taxonomy of memory operations including acquisition, consolidation, retrieval, update and forgetting.
9. MemoryOS (Kang et al., 2025). OS-like tiered memory.
10. Memory in the Age of AI Agents (Hu et al., 2025/2026). Factual, experiential and skill-memory taxonomy.
11. APEX-MEM (Banerjee et al., ACL 2026). Temporal property graph, append-only storage and retrieval-time conflict resolution.
12. From Storage to Experience: A Survey on the Evolution of LLM Agent Memory Mechanisms (Findings ACL 2026). Storage -> Reflection -> Experience evolution.

## Engineering references

Letta/MemGPT: git-backed memory filesystem, memory blocks and background dreaming.
COG / AI Second Brain: Markdown + Git + agent skills and human-auditable knowledge.
Mem0: production memory extraction, structured memory and hybrid retrieval.
Graphiti/Zep: temporal knowledge graph, entity-centric facts and hybrid retrieval.
WikiSkill: Raw -> Wiki -> Skill evolution pipeline.
A-MEM: atomic memory units and dynamic relations.
HippoRAG: graph-assisted associative recall.
APEX-MEM: append-only temporal memory and query-time conflict resolution.

## Benchmarks
LOCOMO and LongMemEval should be used for long-term memory evaluation. Retrieval precision/recall, temporal consistency and provenance completeness must also be measured independently.

PreCog-specific metric: Memory-to-Behavior Gain, comparing downstream behavior with and without selected memory.

## Research boundary
Adopt established storage, reflection, retrieval, temporal and consolidation mechanisms where possible. Treat provenance-first trajectory memory, BehaviorID-aware retrieval, Memory-to-Behavior Gain, PreCog prediction and XP.2Flow-driven evolution as experimental contributions.