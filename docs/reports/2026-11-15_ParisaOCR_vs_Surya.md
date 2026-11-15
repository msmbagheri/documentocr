# ParisaOCR 0.7.2 vs Surya 2.5 Recognizer — Benchmark (2026-11-15)

Full report: [`experiments/parisa_benchmark/REPORT.md`](../../experiments/parisa_benchmark/REPORT.md)

**Decision: Surya 2.5 stays — no recognizer replacement.**

- Recognition-only protocol, 22 real IDPL-PFOD line crops with human GT, identical inputs to both engines.
- CER raw: Surya **0.041** vs Parisa 0.266 · Line Exact Match: Surya **6/22** vs Parisa 0/22
- Sensitive-field proxies (no vehicle docs exist → VIN/engine/plate/owner = N/A): date exact 0.50 vs 0.25, digit-seq 0.286 vs 0.143.
- Parisa is 4.6× faster per line (0.085 s vs 0.394 s) but fails exactly on dense/numeric/mixed lines.
- Small-sample caveat declared (n=22, newswire domain, no vehicle docs in project).
- Main pipeline untouched; all artifacts in `experiments/parisa_benchmark/`.
