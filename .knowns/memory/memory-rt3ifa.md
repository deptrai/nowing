---
id: rt3ifa
title: Traefik im lặng khi nginx giữ port 80/443
layer: project
category: failure
status: active
tags:
  - dokploy
  - traefik
  - nginx
  - network
  - failure
createdAt: '2026-07-28T13:40:22.698Z'
updatedAt: '2026-07-28T13:40:22.698Z'
---

Domain trỏ đúng, cert không cấp hoặc 502/không phản hồi từ ngoài, nội bộ curl vẫn ổn. Nguyên nhân: Traefik không chạy do nginx hệ thống giữ port 80/443. Kiểm tra Traefik và ai giữ port trước khi nghi DNS/cert.
