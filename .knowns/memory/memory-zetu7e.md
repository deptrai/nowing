---
id: zetu7e
title: 'NEXT_PUBLIC_* cần buildArgs hoặc Dockerfile ARG'
layer: project
category: failure
status: active
tags:
  - nextjs
  - frontend
  - env
  - dokploy
  - failure
createdAt: '2026-07-28T13:40:22.614Z'
updatedAt: '2026-07-28T13:40:22.614Z'
---

Next.js bake NEXT_PUBLIC_* vào bundle lúc build. Runtime env không ghi đè. Frontend nowing có 6 biến NEXT_PUBLIC_*. Muốn đổi URL phải là Docker ARG + ENV trong builder stage hoặc truyền qua buildArgs, sau đó rebuild.
