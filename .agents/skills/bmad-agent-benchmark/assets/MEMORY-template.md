# Curated Memory

## Ratified Baselines Matrix

| Suite | Metric | Ratified Baseline | Gate Threshold | Ratified Date | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Lead Extraction (DSH)** | F1 Phone | 99.2% | $\ge 98.0\%$ | 2026-08-21 | 130 cases (Batdongsan, Chotot, TopCV, Masothue, Hotline filter) |
| **Lead Extraction (DSH)** | Hallucination Rate | 0.0% | $\le 0.1\%$ | 2026-08-21 | Zero false lead generation & CSKH hotline suppression |
| **Lead Extraction (DSH)** | MST Modulo-11 | 99.8% | $\ge 99.5\%$ | 2026-08-21 | Vietnamese Tax ID checksum (10/13 digit branches) |
| **Chat Regression** | Speed Mode Latency | 3.2s | $\le 15.0\text{s}$ | 2026-08-21 | Short query speed mode |
| **Chat Regression** | Finish Rate | 100% | $100\%$ | 2026-08-21 | Zero dropped SSE streams across modes |
| **Chat Regression** | Wide Table Extraction | 100% Schema Valid | $100\%$ | 2026-08-21 | Epic 52 / Story 26.9a wide research table matrix |
| **Memory Recall** | Precision@5 | 0.86 | $\ge 0.80$ | 2026-08-18 | Story 3.9 / SM-10 |
| **Memory Recall** | Noise Rate | 0.04 | $\le 0.10$ | 2026-08-18 | Top-5 memory recall |
| **Canonical Dedup** | Deduplication Precision | 99.4% | $\ge 99.0\%$ | 2026-08-20 | Story 10.4 / 12.4b BĐS & Jobs multi-source overlap |

## Latest Benchmark Runs

| Date | Suite | Mode | Sample Size ($N$) | Result / Key Metric | Gate Status | Run Artifact / Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| 2026-08-21 | `lead_extraction/regression` | `replay` | 130 cases | F1=100%, Hallucination=0.0%, MST=100% | 🟢 PASSED | Golden Cassettes replay ($0 API cost) |

## Active Quality & Drift Alerts
- _No active drift alerts._

## Environment & Run Notes
- Local backend: `http://localhost:8000` (Postgres on `:5434`, Redis on `:6380`).
- Replay artifacts directory: `nowing_evals/data/`.
