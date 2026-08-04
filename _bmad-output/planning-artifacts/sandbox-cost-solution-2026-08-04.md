---
title: "Giải bài toán chi phí sandbox: Kortix vs SurfSense cho vertical BĐS"
status: "khuyến nghị kiến trúc"
created: "2026-08-04"
research: "Kortix/Suna docs (Daytona sandbox), E2B/Modal/Daytona pricing (2026-08)"
one_line: "Chi phí per-user sandbox cao KHÔNG phải lỗi hạ tầng — nó là dấu hiệu bạn over-scope một kiến trúc AGENT TỔNG QUÁT cho một vertical HẸP. Đừng làm sandbox rẻ hơn; đừng dùng sandbox per-user cho BĐS."
---

# Giải bài toán chi phí sandbox

## 1. Dữ kiện đã verify

**Kortix/Suna** cho mỗi session một **VM Linux đầy đủ** (Daytona/Platinum microVM/E2B): Chrome + VNC + sudo + LaTeX + LibreOffice + Python data stack + Playwright + opencode. **Rất nặng.** Nó *đã* tối ưu idle: `auto_stop 15 phút` (dừng → không tính compute), `auto_archive 30 phút` (snapshot, phí lưu tối thiểu). Nên vấn đề **không phải idle** — mà là:
1. **Ảnh nặng** → RAM/disk lớn → giá/giây cao + cold-start từ archive chậm.
2. **Chi phí = compute-giây ACTIVE × số user active** + headroom warm-pool cho spike.
3. **Sàn phí cố định** ($150/mo E2B Pro, $250/mo Modal Team) + lưu snapshot cho N user.
4. **Căng thẳng cold-start vs cost**: archive mạnh = rẻ nhưng resume chậm; giữ warm = nhanh nhưng đốt tiền.

**Giá thị trường (2026-08, đã verify):**
| Provider | Cold start | Pause/resume | Giá | Sàn phí |
|---|---|---|---|---|
| **E2B** (Firecracker microVM) | 80-150ms | resume cùng sandbox ~1s | ~**$0.05/vCPU-giờ** (chỉ tính khi chạy) | $150/mo Pro (Hobby free + $100 credit) |
| **Modal** (gVisor) | sub-giây | snapshot → sandbox mới | $0.0000394/core/s, **scale-to-zero** | $0 Starter / $250 Team |
| **Daytona** (Kortix mặc định) | tạo nhanh | persistent-workspace | per-vCPU-giờ | free credit |

## 2. Khung lại: bạn KHÔNG over-pay hạ tầng — bạn OVER-SCOPE kiến trúc

Kortix cho **mọi** session một máy tính Linux đầy đủ vì nó là platform **agent tổng quát** ("làm được mọi việc"). Agent BĐS của bạn làm một **tập việc HẸP, CỐ ĐỊNH**: theo dõi tin, lọc rác, dedup, match, viết mô tả, thông báo. **Không việc nào cần một VM Linux per-user có Chrome + VNC + sudo.**

⇒ Chi phí per-user sandbox cao chính là **triệu chứng của việc dùng agent tổng quát cho một vertical**. Cách sửa **không phải** "làm sandbox rẻ hơn" — mà là **không dùng sandbox per-user cho BĐS**. Bạn chuyển sang SurfSense/Nowing-light **không sai** — đó mới là fit đúng cho vertical; quay lại per-user Linux VM mới là sai.

**"Kortix tốt hơn & dễ scale hơn"** — đúng cho **agent tổng quát**. Với **vertical hẹp**, kiến trúc đúng là NGƯỢC LẠI: compute chung tối thiểu + đẩy phần nặng (browser) về máy user.

## 3. Giải pháp (3 tầng, tăng dần độ nặng)

**Tầng A — Mặc định 99% việc BĐS: KHÔNG sandbox per-user.**
- Tác vụ BĐS = toolset cố định → chạy trên **worker pool chia sẻ, stateless** (function/container chung), không phải VM per-user. Rẻ hơn 10-100× vì không trả tiền cô lập-nhàn-rỗi theo từng user.
- **Browser → đẩy về máy user (extension ở phiên trước).** Đây là đòn giảm chi phí lớn nhất: phần đắt nhất của Kortix là Chrome+VNC cloud per-session; extension đưa browser sang máy user → **chi phí browser phía server ≈ $0**.

**Tầng B — Tác vụ nặng HIẾM (thật sự cần code-exec/máy ảo): ephemeral, per-second, gated.**
- Chỉ spin sandbox khi user bấm "chạy việc nặng"; dùng **E2B (resume ~1s, ~$0.05/vCPU-giờ)** hoặc **Modal (scale-to-zero, sàn $0)** — **trả theo giây chạy thật**, không nuôi VM per-user.
- Free tier: **không** sandbox riêng mặc định; quota chặt (N phút agent/ngày); nếu chạy nặng thì box **tối thiểu hoá ảnh** + auto-stop 2-5 phút (không phải 15).
- Paid tier: sandbox riêng, idle dài hơn, warm-pool ưu tiên.

**Tầng C — Nếu vẫn muốn năng lực Kortix generalist về sau:** giữ nó như **một tool sau paywall**, chạy trên E2B/Modal per-second, **không** làm default cho freemium.

## 4. Sửa nhầm lẫn mấu chốt về chi phí freemium
**Chi phí phải bám THEO CONCURRENCY, không theo số đăng ký.** 10.000 user free nhưng 50 session active đồng thời = **50 box warm, không phải 10.000**. Và:
- User free **nhàn rỗi → ~$0** (không có VM per-user để nuôi).
- Chi phí co giãn theo **usage thật** (giây sandbox + token LLM), tức theo doanh thu, không theo signup.
- **Token LLM**: cap bằng story 8.7 (spend cap) bạn đã có → freemium không cháy túi.
- Xoá snapshot của user free bất hoạt sau X ngày (đừng lưu N-user mãi).

## 5. Mô hình chi phí minh hoạ (free user điển hình)
- **Kiểu Kortix (per-user VM):** mỗi free-user-active nuôi 1-2 vCPU + ảnh nặng + headroom warm + sàn phí → chi phí **không map với doanh thu**, phình theo signup + spike.
- **Kiểu light + extension (khuyến nghị):** duyệt tin chạy trên **máy user** (browser); server chỉ vài call LLM/dedup (vài cent, có cap). **Chi phí biên/free user ≈ ~$0.** Chỉ trả ephemeral sandbox khi có việc nặng thật.

## 6. Về ổn định freemium
"Giữ ổn định ở freemium tốn kém" là vì bạn đang cố **giữ VM per-user warm/ổn định**. Nếu free = **worker chung stateless + ephemeral sandbox on-demand**, **không có VM per-user để giữ ổn định** → ổn định trở thành bài toán autoscale pool (chuẩn, rẻ), không phải nuôi máy theo user.

## 7. Khuyến nghị dứt điểm
1. **BĐS: theo Nowing-light + extension (Tầng A).** Không dùng per-user sandbox. Đây là fit đúng cho vertical — bạn đã đi đúng khi rời Kortix.
2. **Giữ Kortix/generalist làm "chế độ nặng" sau paywall (Tầng B/C)** trên E2B/Modal per-second, nếu về sau có nhu cầu — không phải nền freemium.
3. **Chi phí theo concurrency + token (có cap), không theo signup.** Free idle = $0.
4. Đừng tốn công "làm per-user sandbox rẻ hơn cho freemium" — đó là tối ưu sai bài toán.

## Tóm tắt một dòng
**Đừng làm sandbox per-user rẻ hơn — hãy bỏ nó khỏi đường freemium của vertical BĐS. Compute chung tối thiểu + browser chạy ở máy user (extension) + ephemeral E2B/Modal per-second cho việc nặng hiếm, gated sau paywall. Chi phí bám concurrency & token (có cap), không bám signup → free user nhàn rỗi tốn ~$0. Kortix tốt hơn cho agent TỔNG QUÁT; với vertical HẸP, light-architecture của bạn mới là đúng.**
