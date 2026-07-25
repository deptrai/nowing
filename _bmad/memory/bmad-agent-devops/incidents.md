# Incident Ledger

Mỗi lần chẩn đoán, tra file này TRƯỚC khi đoán. Một lỗi đã ở đây thì không được chẩn đoán lại từ đầu.

Cột "Nguồn": `kế thừa` = học từ thế hệ trước trên hạ tầng Dokploy tương tự, chưa tự thấy trên nowing.
`tự thấy` = tôi quan sát trực tiếp trên nowing, có bằng chứng.

---

## [I-01] `application-saveBuildType` trả 400
**Nguồn:** kế thừa
**Triệu chứng:** gọi `application-saveBuildType` để đổi build config → HTTP 400.
**Nguyên nhân:** tool này không dùng được trên Dokploy instance này.
**Cách xử lý:** dùng `application-update` — đó là tool config duy nhất tin được. Truyền cả `buildType` qua đó.

## [I-02] `NEXT_PUBLIC_*` không có tác dụng khi set ở runtime env
**Nguồn:** kế thừa — và **rủi ro sống trên nowing frontend**
**Triệu chứng:** sửa `NEXT_PUBLIC_*` trong tab Environment, redeploy, frontend vẫn dùng giá trị cũ.
**Nguyên nhân:** Next.js bake `NEXT_PUBLIC_*` vào bundle **lúc build**. Runtime env không ghi đè được.
**Cách xử lý:** phải là Docker `ARG` + `ENV` trong builder stage của Dockerfile, hoặc truyền qua `buildArgs`. Sau khi sửa phải rebuild, không phải restart.
**Liên quan nowing:** frontend (`Z3MYiB0npy5zJf0Q4MHT`) có 6 biến `NEXT_PUBLIC_*` gồm `NEXT_PUBLIC_FASTAPI_BACKEND_URL`, `NEXT_PUBLIC_ZERO_CACHE_URL`. Nếu owner nhờ đổi URL backend/zero, đây là cái bẫy đầu tiên.

## [I-03] Traefik im lặng trên VPS mới
**Nguồn:** kế thừa
**Triệu chứng:** domain trỏ đúng DNS, cert không cấp được, hoặc 502/không phản hồi từ ngoài. Nội bộ curl vẫn ổn.
**Nguyên nhân:** Traefik không chạy, thường vì nginx hệ thống đang giữ port 80/443.
**Cách xử lý:** kiểm tra Traefik có sống không và ai đang giữ 80/443 trước khi nghi cert hay DNS.

## [I-04] nginx chết cứng vì Docker DNS động
**Nguồn:** kế thừa
**Triệu chứng:** nginx trả 502 sau khi container upstream được recreate, dù container đó khoẻ.
**Nguyên nhân:** `upstream` block của nginx resolve DNS **một lần lúc load** và cache vĩnh viễn. IP container Docker thay đổi mỗi lần recreate.
**Cách xử lý:** `resolver 127.0.0.11 valid=10s;` + đặt host vào biến (`set $upstream ...`) rồi `proxy_pass $upstream`. Không dùng static upstream block.

## [I-05] env production để `null` thay vì placeholder
**Nguồn:** kế thừa
**Triệu chứng:** service khởi động rồi chết, hoặc chạy với config rỗng một cách âm thầm.
**Nguyên nhân:** biến bắt buộc bị để trống/null, không ai nhận ra là thiếu.
**Cách xử lý:** biến bắt buộc chưa có giá trị thì đặt `CHANGE_ME`, không bao giờ để null/rỗng — nó phải gây lỗi ồn ào, không im lặng.

## [I-06] Verify sai thứ tự khiến chẩn đoán lệch
**Nguồn:** kế thừa
**Nguyên nhân:** nhảy vào đoán DNS/cert khi thực ra app đã chết từ trong.
**Cách xử lý:** luôn theo thứ tự — curl **nội bộ** trước (container còn sống không), rồi mới curl **ngoài qua DNS** (đường vào có thông không). Thứ tự này tách bạch lỗi app với lỗi routing.

---

## [I-07] Postgres production không có backup — RỦI RO ĐANG MỞ
**Nguồn:** tự thấy — `postgres-one` ngày 2026-07-25 trả `backups: []`
**Trạng thái:** CHƯA XỬ LÝ
**Vì sao nghiêm trọng:** postgres `95TnauTU0vCLJsBWLsoF` giữ toàn bộ dữ liệu nowing trên volume `nowing-postgres-data`. Không có backup nào trong Dokploy, không có cron chạy `scripts/backup/pg_backup.sh`, không có bằng chứng từng restore thử. Một lần volume hỏng hoặc một câu DELETE sai là mất trắng.
**Việc cần làm:** cấu hình backup định kỳ trong Dokploy, rồi **thử restore thật** — backup chưa restore thử là backup trên giấy.

## [I-08] Một môi trường duy nhất, không có staging
**Nguồn:** tự thấy — `project-all` cho thấy nowing chỉ có env `production` (`v9OCYwAqJSpDHuyf4DoGf`)
**Hệ quả:** không có nơi nào để thử deploy trước. Mọi push vào branch `production` là đi thẳng vào thật, `autoDeploy=true`.
**Cách xử lý:** vì không có lưới an toàn, verify sau deploy không phải tuỳ chọn — luôn curl golden path ngay sau mỗi lần deploy.
