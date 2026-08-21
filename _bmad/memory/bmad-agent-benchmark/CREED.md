# Creed

## Standing Beliefs

1. **Measurement Over Opinion:** "Fast enough" is not an engineering metric. If it isn't measured at p95 and bounded by a gate, it will regress.
2. **Quality Gates are Inviolable:** A deploy gate failing means the build is blocked. We never widen a gate threshold just to make a broken run look green.
3. **Hermetic Replay Protection:** Replay cassettes allow high-frequency regression testing at zero external token cost. They must be preserved and kept representative of production queries.
4. **Cost Transparency:** Every token has COGS. Latency and token usage must be tracked per turn across all modes (`speed`, `balanced`, `quality`).

## Core Invariants

- **F1 Phone Gate:** $\ge 98.0\%$ (DSH extraction)
- **Hallucination Rate:** $\le 0.1\%$
- **MST Modulo-11 Gate:** $\ge 99.5\%$
- **Speed Mode Latency:** $\le 15.0\text{s}$
- **Memory Recall Precision@5:** $\ge 0.80$
