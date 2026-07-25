# Capabilities

## Built-in

| Code | Name | Description | Source |
|------|------|-------------|--------|
| [BK] | backup-dr | Bảo đảm dữ liệu nowing có bản sao còn sống và đã được kiểm chứng phục hồi được | `references/backup-dr.md` |
| [DP] | deploy | Đưa một thay đổi lên production Dokploy và chứng minh nó còn sống | `references/deploy.md` |
| [DM] | domain | Gắn domain, HTTPS và routing cho app trên Dokploy | `references/domain.md` |
| [EV] | env | Quản lý biến môi trường production mà không làm vỡ build | `references/env.md` |
| [IN] | infra | Dựng và sửa hạ tầng nền — VPS, Docker, reverse proxy, network | `references/infra.md` |
| [PG] | postgres-pgvector | Vận hành Postgres/pgvector self-hosted của nowing trên Dokploy | `references/postgres-pgvector.md` |
| [ST] | status | Ảnh chụp sức khoẻ toàn stack nowing, đọc được trong một phút | `references/status.md` |
| [TS] | troubleshoot | Chẩn đoán sự cố production, có tra ký ức sự cố cũ trước khi đoán | `references/troubleshoot.md` |

## Learned

_Capabilities added by the owner over time. Prompts live in `capabilities/`._

| Code | Name | Description | Source | Added |
|------|------|-------------|--------|-------|

## How to Add a Capability

Tell me "I want you to be able to do X" and we'll create it together.
I'll write the prompt, save it to `capabilities/`, and register it here.
Next session, I'll know how.
Load `references/capability-authoring.md` for the full creation framework.

## Tools

Prefer crafting your own tools over depending on external ones. A script you wrote and saved is more reliable than an external API. Use the file system creatively.

### User-Provided Tools

_MCP servers, APIs, or services the owner has made available. Document them here._
