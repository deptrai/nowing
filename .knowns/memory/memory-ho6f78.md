---
id: ho6f78
title: nginx chết cứng vì Docker DNS động
layer: project
category: failure
status: active
tags:
  - nginx
  - docker
  - dns
  - network
  - failure
createdAt: '2026-07-28T13:40:22.775Z'
updatedAt: '2026-07-28T13:40:22.775Z'
---

nginx trả 502 sau khi container upstream recreate, dù container khoẻ. upstream block resolve DNS một lần lúc load và cache vĩnh viễn, IP container thay đổi mỗi lần recreate. Fix: resolver 127.0.0.11 valid=10s; set $upstream ...; proxy_pass $upstream. Không dùng static upstream block.
