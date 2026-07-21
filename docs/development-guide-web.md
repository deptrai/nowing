# Hướng dẫn phát triển - Nowing Web

**Ngày tạo:** 2026-07-21 16:59:34

## Yêu cầu

- Node.js 20+
- pnpm 10.26.0

## Cài đặt

```bash
cd nowing_web
pnpm install
```

## Môi trường

```bash
cp .env.example .env.local
# chỉnh sửa NEXT_PUBLIC_BACKEND_URL, BACKEND_URL, các khóa OAuth/Turnstile
```

## Chạy dev

```bash
pnpm dev        # Next.js dev với turbopack
```

## Build

```bash
pnpm build
pnpm start      # production server
```

## Database (Drizzle)

```bash
pnpm db:generate
pnpm db:migrate
pnpm db:push
pnpm db:studio
```

## Test E2E

```bash
pnpm test:e2e
pnpm test:e2e:ui
```

## Format/Lint

```bash
pnpm lint
pnpm format
```

---

_Tài liệu được tạo bởi BMAD Method `document-project` workflow_
