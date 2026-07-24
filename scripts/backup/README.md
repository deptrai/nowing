# Nowing Prod Postgres Backup

Prod Postgres là container tự quản trên VPS (Dokploy), **hiện KHÔNG có backup định kỳ / không PITR**. Đây là rủi ro data-safety lớn nhất, độc lập với memory. Thiết lập backup tự động NGAY.

## Lựa chọn (ưu tiên A nếu có object storage)

### A. Dokploy built-in scheduled backup (khuyến nghị nếu có S3/B2)
Dokploy → service `nowing-postgres` → tab **Backups** → thêm scheduled backup (cron `0 3 * * *`) tới một S3-compatible destination. Đây là cách ít bảo trì nhất; `pg_backup.sh` bên dưới là phương án bổ sung/thay thế khi không có object storage.

### B. Cron + `pg_backup.sh` (self-contained, có rotation + integrity check)
1. Copy `scripts/backup/pg_backup.sh` lên VPS (vd `/opt/nowing/pg_backup.sh`), `chmod +x`.
2. Cấu hình kết nối DB (một trong hai):
   - **TCP:** đặt `PGHOST/PGPORT/PGUSER/PGDATABASE` + `PGPASSWORD` (hoặc `~/.pgpass`).
   - **Dokploy container (không expose port):** đặt `DOCKER_CONTAINER=<tên container postgres>` + `PGUSER`/`PGDATABASE`/`PGPASSWORD` → script tự `docker exec ... pg_dump`.
3. Test chạy tay: `sudo BACKUP_DIR=/opt/nowing-remediation-backups DOCKER_CONTAINER=<pg> PGUSER=postgres PGDATABASE=nowing PGPASSWORD=*** /opt/nowing/pg_backup.sh` → kiểm log + file `.dump` + dòng "OK verified".
4. Cron hằng ngày 3:00 (host crontab, `sudo crontab -e`):
   ```
   0 3 * * * DOCKER_CONTAINER=<pg> PGUSER=postgres PGDATABASE=nowing PGPASSWORD=*** BACKUP_DIR=/opt/nowing-remediation-backups /opt/nowing/pg_backup.sh >> /opt/nowing-remediation-backups/cron.log 2>&1
   ```
   (Bí mật nên đặt qua `/etc/nowing-backup.env` + `EnvironmentFile` nếu dùng systemd timer thay cron.)
5. **Off-site (rất nên):** đặt `RCLONE_REMOTE=b2:nowing-backups` (đã `rclone config` một remote S3/B2). Backup nằm cùng VPS = mất VPS mất luôn backup.

## Restore test (làm 1 lần khi setup + hằng tháng)
```
# vào một DB/instance TẠM (KHÔNG phải prod)
createdb nowing_restore_test
pg_restore -d nowing_restore_test --no-owner /opt/nowing-remediation-backups/nowing-<ts>.dump
psql -d nowing_restore_test -c "SELECT count(*) FROM \"user\";"
```
Backup chưa test-restore = chưa phải backup.

## Nâng cấp sau (tùy chọn): PITR
Nếu cần recovery điểm-thời-gian: bật `archive_mode=on` + `archive_command` (WAL archiving) hoặc chuyển sang managed Postgres. Ngoài phạm vi bước này; cron `pg_dump` ở trên đã đủ chặn rủi ro "mất sạch".

---

## Prompt cho ops agent (dán để triển khai an toàn)
```text
Triển khai backup tự động cho prod Postgres của Nowing (VPS Dokploy, hiện KHÔNG có backup).
Ràng buộc: read-only với DB; KHÔNG đổi cấu hình prod ngoài việc thêm cron/backup; bí mật qua env/.pgpass, không hardcode/không in ra log.
Bước:
1. Xác định cách kết nối DB prod: tên container postgres (Dokploy) HOẶC host:port + credentials (từ Dokploy env). Ưu tiên `docker exec` nếu port không expose.
2. Nếu Dokploy có tab Backups + có sẵn S3/B2 → cấu hình scheduled backup 03:00 hằng ngày tới đó. Báo lại destination + retention.
3. Nếu không có object storage → cài `scripts/backup/pg_backup.sh`: copy lên /opt/nowing/, chmod +x, cấu hình env (DOCKER_CONTAINER hoặc PG*), chạy thử 1 lần, xác minh log "OK verified" + file .dump hợp lệ (`pg_restore --list`).
4. Thêm cron 03:00 hằng ngày; nếu có remote off-site (rclone) thì set RCLONE_REMOTE.
5. Chạy 1 lần restore-test vào DB tạm (KHÔNG prod), xác nhận count bảng "user".
Deliverable: xác nhận backup đầu tiên chạy thành công + vị trí lưu + retention + có off-site hay chưa + kết quả restore-test.
```
