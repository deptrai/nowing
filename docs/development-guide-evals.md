# Hướng dẫn phát triển - Evals

**Ngày tạo:** 2026-07-21 16:59:34

```bash
cd surfsense_evals
uv pip install -e .
cp .env.example .env
# cấu hình SURFSENSE_API_BASE, OPENROUTER_API_KEY, auth

surfsense-evals suites list
surfsense-evals benchmarks list
surfsense-evals setup --suite medical --provider-model anthropic/claude-sonnet-4.5
surfsense-evals ingest medical medxpertqa --split test
surfsense-evals run medical medxpertqa --concurrency 4
surfsense-evals report --suite medical
```

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
