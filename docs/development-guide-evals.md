# Hướng dẫn phát triển - Evals

**Ngày tạo:** 2026-07-21 16:59:34

```bash
cd nowing_evals
uv pip install -e .
cp .env.example .env
# cấu hình NOWING_API_BASE, OPENROUTER_API_KEY, auth

nowing-evals suites list
nowing-evals benchmarks list
nowing-evals setup --suite medical --provider-model anthropic/claude-sonnet-4.5
nowing-evals ingest medical medxpertqa --split test
nowing-evals run medical medxpertqa --concurrency 4
nowing-evals report --suite medical
```

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
