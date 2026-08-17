# UX Contract — Fit Score Badge

**Ngày:** 2026-08-10
**Phạm vi:** Epic 21 — Lead Scoring visualization
**Bám vào:** FR-64, AD-38
**Loại tài liệu:** *contract*

---

## Badge States

| Score | Color | Label | Usage |
|-------|-------|-------|-------|
| 80-100 | 🟢 Green | "High Fit" | Table cell, card header |
| 50-79 | 🟡 Yellow | "Medium Fit" | Table cell, card header |
| 0-49 | 🔴 Red | "Low Fit" | Table cell, card header |

## Score Breakdown Tooltip

Hover badge → tooltip:

```
Fit Score: 85/100
├── Company Size: 20/20
├── Industry Match: 18/20
├── Location: 15/20
├── Intent Signals: 17/20
└── Tech Stack: 15/20
```

## Trend Indicator

| Trend | Icon | Meaning |
|-------|------|---------|
| Improving | ↗️ | Score increased in last 7 days |
| Stable | → | Score unchanged |
| Declining | ↘️ | Score decreased in last 7 days |

---

_Trace: epic21-lead-intelligence-ux.md → AD-38 → FR-64_
