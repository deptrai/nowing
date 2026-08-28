# AI Lead Generation Evaluation Framework Reference

This guide covers the **AI Lead Generation Enterprise Evaluation Suite** (`lead_generation/regression`), implemented as part of **Story 21.15 / Story 28.5**. It establishes rigorous benchmarks for multi-source lead discovery, buying intent routing, ICP firmographic qualification, entity deduplication, distractor filtering, and end-to-end response latency.

---

## 1. Lead Quality Evaluation vs. Token Extraction Accuracy

It is critical to distinguish between **Lead Quality Evaluation** and **Token Extraction Accuracy**:

| Dimension | Token Extraction Accuracy (`lead_extraction`) | Lead Generation Quality (`lead_generation`) |
|---|---|---|
| **Scope** | Story 21.4 (Single-document text extraction) | Story 21.15 / Story 28.5 (Autonomous Lead Agent) |
| **Input** | Unstructured raw HTML / Markdown page dump | High-level natural language prompt / ICP query |
| **Core Objective** | Regex & OCR fidelity (Phone, Modulo-11 Tax Code) | Multi-source intent routing, entity discovery & scoring |
| **Key Failure Modes** | Extraction hallucination, OCR distortion | Irrelevant leads, out-of-ICP distractors, scraper gaps |
| **Key Metrics** | F1 Phone, MST Modulo-11, Company Name overlap | Precision@k, Recall@Source, ICP Match Rate, Duplicate Rate |

---

## 2. The 8 Enterprise Lead Generation Evaluation Metrics

The suite evaluates 8 standardized metrics against production gate thresholds:

### 1. `precision_at_k` (Target: $\ge 0.85$)
- **Definition**: The proportion of the top-$k$ retrieved leads that accurately match ground truth entities.
- **Identity Resolution**: Evaluates candidate matches using multi-attribute identity resolution:
  1. Exact Normalized Tax ID (`tax_id` / `mst`).
  2. Exact Canonical Domain Root (`domain` / `canonical_domain`).
  3. Normalized Vietnamese Phone Number (`phone` / `primary_phone`).
  4. Normalized Vietnamese Company Name without diacritics and stripped of legal entity noise words (`công ty`, `cổ phần`, `tnhh`, `mtv`, `corp`).
- **Formula**:
  $$\text{Precision@k} = \frac{\sum_{i=1}^{\min(k, N)} \mathbb{I}(\text{lead}_i \in \text{Expected})}{k}$$

### 2. `recall_at_source` (Target: $\ge 0.80$)
- **Definition**: The fraction of targeted platform adapters/scrapers that were successfully triggered and returned valid candidate records.
- **Formula**:
  $$\text{Recall@Source} = \frac{|\text{Discovered Sources} \cap \text{Expected Sources}|}{|\text{Expected Sources}|}$$

### 3. `icp_match_rate` (Target: $\ge 0.85$)
- **Definition**: The percentage of generated leads satisfying all firmographic constraints defined in the target ICP profile (industry, company size range, geographical location, capital/revenue).
- **Formula**:
  $$\text{ICP Match Rate} = \frac{\text{Count of Leads Satisfying All ICP Rules}}{\text{Total Leads Retrieved}}$$

### 4. `intent_signal_precision` (Target: $\ge 0.80$)
- **Definition**: Accuracy and relevance of identified buying, hiring, expansion, or procurement signals attached to the lead.
- **Formula**:
  $$\text{Intent Signal Precision} = \frac{\text{Leads with Verified Expected Intent Signal}}{\text{Total Leads with Detected Intent}}$$

### 5. `contact_accuracy` (Target: $\ge 0.85$)
- **Definition**: Verification rate of actionable outreach channels. Every lead must possess at least one valid, format-compliant channel (10-digit Vietnamese phone regex `(?:0|\+84|84)(?:3|5|7|8|9)\d{8}`, RFC-compliant email, or verified Zalo account).
- **Formula**:
  $$\text{Contact Accuracy} = \frac{\text{Count of Leads with Valid Contact Channel}}{\text{Total Leads Retrieved}}$$

### 6. `duplicate_rate` (Target: $\le 0.40$)
- **Definition**: The proportion of duplicate candidate records identified and merged during cross-source deduplication.
- **Formula**:
  $$\text{Duplicate Rate} = \frac{\text{Raw Candidates} - \text{Deduplicated Leads}}{\text{Raw Candidates}}$$

### 7. `false_positive_rate` (Target: $\le 0.05$)
- **Definition**: The fraction of known negative distractor entities (disqualified companies, out-of-scope industries, out-of-region entries) mistakenly retrieved.
- **Formula**:
  $$\text{False Positive Rate} = \frac{\text{Count of Matched Negative Distractors}}{|\text{Negative Candidates}|}$$

### 8. `time_to_first_lead` (Target: $\le 2000.0\text{ ms}$)
- **Definition**: Time-to-First-Lead (TTFL) latency in milliseconds from query dispatch to the streaming of the first validated lead payload.

---

## 3. Golden Dataset Architecture

The golden dataset is stored at `src/nowing_evals/suites/lead_generation/golden_cases.jsonl` with 50+ curated cases across 5 enterprise verticals:

```jsonl
{"case_id": "saas-crm-001", "vertical": "saas", "query": "Tìm doanh nghiệp bán lẻ thời trang chuỗi tại Hà Nội đang tìm giải pháp quản lý bán hàng đa kênh omnichannel", "expected_leads": [{"tax_id": "0108923412", "canonical_domain": "may10-retail.vn", "name": "Công ty Cổ phần Thời trang May 10"}], "expected_sources": ["masothue", "linkedin", "facebook_groups"], "false_positives": [{"tax_id": "0109999999", "name": "Công ty Phần mềm B2B Tech"}], "icp_criteria": {"industry": "Bán lẻ", "location": "Hà Nội", "company_size": {"min": 50, "max": 500}}, "expected_intents": ["tìm phần mềm POS", "quản lý bán lẻ"], "tags": ["omnichannel", "retail", "north_vn"]}
```

### Supported Verticals
1. **`saas`** (10 cases): B2B SaaS, CRM, HRM, ERP, and AI tool procurement.
2. **`real_estate`** (10 cases): Industrial parks, office leasing, retail expansion, and logistics hubs.
3. **`recruitment`** (10 cases): IT staffing, executive search, mass manufacturing hiring, and call center scaling.
4. **`procurement`** (10 cases): Office supplies, IT hardware, cleanroom contractors, and solar installation.
5. **`ecommerce`** (10 cases): Fulfillment, 3PL logistics, cross-border payments, and livestream enablers.

---

## 4. Running the Benchmark

### CLI Commands

```bash
# Run lead generation evaluation in replay mode (default)
python -m nowing_evals run lead_generation regression

# Filter evaluation by specific vertical
python -m nowing_evals run lead_generation regression --vertical saas

# Run live against a local backend instance
python -m nowing_evals run lead_generation regression --mode live --nowing-api-base http://localhost:8000

# Generate Markdown and JSON evaluation reports
python -m nowing_evals report --suite lead_generation --benchmark regression
```

### Running Unit & Regression Tests

```bash
cd nowing_evals
PYTHONPATH=src pytest tests/suites/test_lead_generation_eval.py -v
```

---

## 5. Production Gate Policy (`gate.yaml`)

Production deployments are governed by `gate.yaml`:

```yaml
baseline_ratified: true
thresholds:
  min_precision_at_k: 0.85
  min_recall_at_source: 0.80
  min_icp_match_rate: 0.85
  min_intent_signal_precision: 0.80
  min_contact_accuracy: 0.85
  max_duplicate_rate: 0.40
  max_false_positive_rate: 0.05
  max_time_to_first_lead_ms: 2000.0
  min_cases: 50
baseline_source: "Story 21.15 / Story 28.5 AI Lead Generation Enterprise Benchmark Baseline"
```

If any metric fails to satisfy its threshold when `baseline_ratified: true`, the evaluation runner exits with non-zero exit code `1`, halting the CI/CD deployment pipeline.

---

## 6. Extending the Dataset

When adding new evaluation test cases to `golden_cases.jsonl`:

1. **Provide Multi-Attribute Identity**: Ensure each expected lead includes at least one high-confidence anchor (`tax_id`, `canonical_domain`, or `phone`).
2. **Include Negative Distractors**: Add at least one entry to `false_positives` (e.g. competitor vendors, out-of-territory businesses) to test noise filtering.
3. **Define Granular ICP Criteria**: Use range dictionaries (`{"min": 10, "max": 100}`) or explicit string values (`"industry": "..."`).
4. **Validate Schema**: Run `pytest tests/suites/test_lead_generation_eval.py` to confirm case integrity and gate compliance.
