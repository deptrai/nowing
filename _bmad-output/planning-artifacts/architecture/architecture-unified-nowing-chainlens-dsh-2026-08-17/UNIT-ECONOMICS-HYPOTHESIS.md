# Epic 26 Unit Economics Hypothesis

> This is a **business hypothesis**, not an architecture invariant. It does not belong in `ARCHITECTURE-SPINE.md` and must be validated before any pricing, subscription, or gross-margin commitments.

## Working COGS model (per 1,000 leads)

| Task Type / Cost Center | Primary Model | COGS / 1,000 Leads (baseline) | Notes |
| :--- | :--- | :--- | :--- |
| **HTML Parsing & Initial Filtering** | **Google Gemini Flash (Free Tier)** | **$0.00–$0.05** | Only for non-PII parsing. PII/sensitive data routes to Tier 2/3. |
| **Local Offline / Fallback** | **Qwen 3.8-27B (vLLM)** | **$50.00–$150.00 GPU infra** | Allocated per 1,000 leads at 10–30% GPU utilization; marginal token cost is $0. |
| **Residential Proxies & CAPTCHA** | VN Residential Pool + Solvers | **$7.80 [UNVERIFIED]** | Cost must come from a live pilot or vendor quote. |
| **High-Volume Burst Extraction** | **deepseek-v4-flash** | **$1.20–$4.00** | Off-peak $0.22/$0.66; peak $0.44/$1.32 per 1M tokens; depends on cache hit rate. |
| **Deep Reasoning & ICP Scoring** | **deepseek-v4-pro** | **$3.50–$10.00** | Off-peak $0.66/$1.98; peak $1.32/$3.96 per 1M tokens with Thinking: High. |
| **Telco HLR / Zalo Lookup** | 15% Verification Sample | **$1.50 [UNVERIFIED]** | Cost must come from a live pilot or vendor contract. |
| **TỔNG GIÁ VỐN (COGS) / 1.000 LEADS** | **Multi-Tier Architecture** | **$17.00–$35.00 (working range)** | **$150.00 revenue (1.5k credits)** is a placeholder until FR-69 pricing is finalized. |

**Gross margin working range: 76.7%–88.7%** (not the previously claimed 89.8%).

## What must be validated

1. DeepSeek peak/off-peak pricing at target request volume (including cache hit rate).
2. GPU utilization and cost on the target Dokploy host or cloud GPU instance.
3. Residential proxy and CAPTCHA solver cost from the actual vendor contract.
4. Telco HLR / Zalo lookup cost per successful verification.
5. Customer revenue per 1,000 leads under FR-69 outcome-based pricing.

## Owner

- Business/Product: responsible for validation and pricing decision.
- Engineering: responsible for measuring actual token spend and emitting it to `TokenUsage` so the model can be updated with real data.
