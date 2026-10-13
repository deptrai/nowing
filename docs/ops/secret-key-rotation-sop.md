# Quy Trình Vận Hành Tiêu Chuẩn (SOP): Xoay Vòng SECRET_KEY Không Gián Đoạn (Zero-Downtime Secret Key Rotation)

**Mã tài liệu:** `SOP-SECOPS-33-01`  
**Phiên bản:** `1.0.0`  
**Áp dụng cho:** Nowing Backend & Celery Workers (Dokploy / Staging / Production)  
**Tác giả:** SecOps & Core Backend Team  
**Cập nhật lần cuối:** 2026-10-13  

---

## 1. Bối Cảnh & Cơ Chế Hoạt Động (Architecture & Mechanism)

### 1.1. PII Vault & Mã Hóa Dữ Liệu Tại Tầng Nghỉ (Encryption at Rest)
Theo kiến trúc bảo mật AD-42 / AD-49 và đặc tả Story 21.3 / Story 33.1, toàn bộ thông tin định danh cá nhân (PII) gồm `name`, `title`, `email`, `phone` trong bảng `verified_contacts` được mã hóa tại tầng nghỉ (encryption at rest). Dữ liệu này chỉ được giải mã khi trả về phản hồi cho các yêu cầu có quyền `CONTACTS_READ`.

Hệ thống mã hóa sử dụng `TokenEncryption` (`app/utils/oauth_security.py`):
- Thuật toán: **Fernet** (AES-128-CBC + HMAC-SHA256).
- Khóa Fernet được phái sinh từ khóa bí mật qua hàm băm SHA-256 (`base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode()).digest())`).

### 1.2. Cơ Chế Dự Phòng Kép (Dual-Key Fallback)
Để thực hiện xoay vòng khóa bí mật mà không gây gián đoạn dịch vụ (zero-downtime), `VerifiedContactEncryption` (`app/services/pii/verified_contact_encryption.py`) và cấu hình `app/config/auth.py` hỗ trợ cơ chế giải mã kép:
- **`SECRET_KEY` (Primary Key):** Khóa chính hiện hành. Luôn được dùng để mã hóa toàn bộ dữ liệu mới ghi vào cơ sở dữ liệu (`encrypt()`), và là lựa chọn đầu tiên khi giải mã (`decrypt()`).
- **`SECONDARY_SECRET_KEY` (Secondary / Fallback Key):** Khóa phụ (khóa cũ trước khi xoay vòng, trong tài liệu SecOps thường gọi là `OLD_SECRET_KEY`). Biến môi trường tương ứng trong code là `SECONDARY_SECRET_KEY`.
- **Luồng giải mã dự phòng (`decrypt`):**
  1. Thử giải mã ciphertext bằng `SECRET_KEY` (Primary).
  2. Nếu giải mã thất bại (do bản ghi cũ được mã hóa bằng khóa trước đó) và `SECONDARY_SECRET_KEY` đang được cấu hình:
     - Giải mã dự phòng bằng `SECONDARY_SECRET_KEY`.
     - Ghi nhận log cảnh báo: `"Decrypted PII with secondary key; will re-encrypt with primary on next write"`.
  3. Nếu không có `SECONDARY_SECRET_KEY` hoặc cả 2 khóa đều không giải mã được: ném ngoại lệ `ValueError`.
- **Hàm tái mã hóa (`rotate_encryption`):**  
  `rotate_encryption(contact: VerifiedContactDict)` tại `verified_contact_encryption.py:131` kiểm tra từng trường PII. Nếu bản ghi vẫn dùng khóa cũ, hàm giải mã bằng secondary cipher và mã hóa lại ngay lập tức bằng primary cipher.

---

## 2. Ma Trận Rủi Ro & Nguyên Tắc An Toàn (Critical Risk Policy)

> [!CAUTION]
> **RỦI RO MẤT DỮ LIỆU VĨNH VIỄN (DATA LOSS HAZARD):**  
> Tuyệt đối **KHÔNG ĐƯỢC PHÉP** gỡ bỏ biến môi trường `SECONDARY_SECRET_KEY` khi tác vụ quét và tái mã hóa toàn bộ cơ sở dữ liệu (`rotate_encryption`) chưa hoàn tất 100%.  
> Nếu gỡ bỏ sớm, mọi bản ghi PII cũ chưa được tái mã hóa sẽ ném ngoại lệ `ValueError: Token decryption failed with primary key`, dẫn đến việc không thể phục hồi dữ liệu gốc nếu không có bản sao lưu khóa cũ.

### Nguyên Tắc Bất Biến:
1. **Lưu trữ khóa cũ an toàn:** Luôn lưu trữ `SECRET_KEY` cũ vào password manager/vault nội bộ trước khi bắt đầu.
2. **Snapshot DB trước khi chạy:** Thực hiện sao lưu snapshot PostgreSQL trước khi kích hoạt lệnh batch re-encryption.
3. **Chỉ gỡ khóa sau khi verify:** Chỉ xóa `SECONDARY_SECRET_KEY` khi script xác minh (Gate 3) trả về `0` bản ghi lỗi.

---

## 3. Quy Trình Chuẩn 4 Bước (Step-by-Step Procedure)

```text
[BƯỚC 0: CHUẨN BỊ]
       │  - Lưu trữ khóa hiện tại vào Vault
       │  - Sinh khóa mới (64 ký tự hex)
       │  - Snapshot Database PostgreSQL
       ▼
[BƯỚC 1: DUAL-KEY CUTOVER]
       │  - Set SECONDARY_SECRET_KEY = <old_key>
       │  - Set SECRET_KEY = <new_key>
       │  - Deploy / Restart Dokploy containers
       ▼
[BƯỚC 2: BATCH RE-ENCRYPTION MIGRATION]
       │  - Chạy script migrateVerifiedContacts theo batch 500
       │  - Giám sát tiến độ & transaction logs
       ▼
[BƯỚC 3: VERIFICATION GATES]
       │  - Chạy verification probe (decrypt thử 100% rows với primary key only)
       │  - Kiểm tra log: không còn log "Decrypted PII with secondary key"
       ▼
[BƯỚC 4: KEY RETIREMENT]
          - Xóa biến SECONDARY_SECRET_KEY khỏi Dokploy/Env
          - Restart Backend & Workers
          - Hoàn tất xoay vòng khóa
```

---

### Bước 0: Chuẩn Bị & Sao Lưu (Preparation & Pre-flight)

1. **Lấy `SECRET_KEY` hiện hành:**
   ```bash
   # Kiểm tra giá trị khóa đang chạy trong container/production
   CURRENT_KEY=$(dokploy env get --app nowing-backend SECRET_KEY)
   echo "Current key hash: $(echo -n "$CURRENT_KEY" | sha256sum | cut -d' ' -f1)"
   ```
   *Lưu chuỗi `CURRENT_KEY` này vào Bitwarden / 1Password / Vault bí mật của SecOps.*

2. **Sinh khóa bí mật mới (`NEW_SECRET_KEY`):**
   Khóa phải có độ ngẫu nhiên cao (entropy tối thiểu 256 bits):
   ```bash
   NEW_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
   echo "New key generated."
   ```

3. **Sao lưu cơ sở dữ liệu (PostgreSQL Snapshot):**
   ```bash
   # Tạo bản dump bảng verified_contacts hoặc snapshot toàn bộ database
   docker exec -t postgres-db pg_dump -U nowing_user -d nowing_prod \
       -t verified_contacts -F c -f /backups/verified_contacts_pre_rotation_$(date +%Y%m%d_%H%M%S).dump
   ```

4. **Kiểm tra số lượng bản ghi cần xoay khóa:**
   ```sql
   SELECT count(*) FROM verified_contacts;
   ```

---

### Bước 1: Thiết Lập Cấu Hình Dual-Key & Khởi Động Lại (Dual-Key Deployment)

Mục tiêu: Đưa hệ thống vào trạng thái vừa nhận khóa mới (để mã hóa các bản ghi mới phát sinh), vừa giữ khóa cũ làm fallback để đọc các bản ghi cũ mà không gây gián đoạn.

1. **Cập nhật biến môi trường trên Dokploy / `.env`:**
   ```bash
   SECONDARY_SECRET_KEY="<CURRENT_SECRET_KEY>"
   SECRET_KEY="<NEW_SECRET_KEY>"
   ```
   *(Lưu ý: Nếu dùng cả bí danh `OLD_SECRET_KEY` trong script ops, có thể đặt đồng thời `OLD_SECRET_KEY="$SECONDARY_SECRET_KEY"`).*

2. **Áp dụng cấu hình và khởi động lại dịch vụ:**
   - Redeploy Backend API container (`nowing-backend`).
   - Redeploy Celery Worker / Beat containers (`nowing-worker`).
   - Kiểm tra healthcheck:
     ```bash
     curl -f https://api.nowing.net/health || curl -f http://localhost:8000/health
     ```

3. **Kiểm tra trạng thái cấu hình trong log khởi động:**
   - Kiểm tra log container đảm bảo không có lỗi `ValueError: secret_key is required`.
   - Lúc này, người dùng vẫn có thể đọc/ghi contact bình thường. Mọi thao tác ghi mới sẽ dùng `NEW_SECRET_KEY`.

---

### Bước 2: Chạy Tác Vụ Tái Mã Hóa Toàn Bộ Bản Ghi (Batch Re-encryption)

Chạy lệnh bảo trì để quét qua toàn bộ các dòng trong bảng `verified_contacts`, giải mã bằng khóa phụ và ghi đè lại bằng khóa chính.

**Lệnh thực thi trong backend container (sử dụng Python CLI / Script runner):**

```bash
uv run python - << 'EOF'
import sys
import logging
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.leads.enrichment import VerifiedContact
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("secret_key_rotation")

BATCH_SIZE = 500

def run_rotation():
    enc = VerifiedContactEncryption()
    if not enc._secondary_cipher:
        logger.error("FATAL: SECONDARY_SECRET_KEY is not configured! Aborting.")
        sys.exit(1)

    db = SessionLocal()
    total_migrated = 0
    total_skipped = 0
    errors = 0

    try:
        last_id = None
        while True:
            query = select(VerifiedContact).order_by(VerifiedContact.id).limit(BATCH_SIZE)
            if last_id is not None:
                query = query.where(VerifiedContact.id > last_id)
            
            records = db.execute(query).scalars().all()
            if not records:
                break

            for contact in records:
                last_id = contact.id
                contact_dict = {
                    "name": contact.name,
                    "title": contact.title,
                    "email": contact.email,
                    "phone": contact.phone,
                }
                try:
                    rotated = enc.rotate_encryption(contact_dict)
                    contact.name = rotated.get("name")
                    contact.title = rotated.get("title")
                    contact.email = rotated.get("email")
                    contact.phone = rotated.get("phone")
                    total_migrated += 1
                except Exception as ex:
                    logger.error(f"Error rotating contact {contact.id}: {ex}")
                    errors += 1

            db.commit()
            logger.info(f"Progress: processed batch, total_migrated={total_migrated}, errors={errors}")

        logger.info(f"COMPLETED: total_migrated={total_migrated}, errors={errors}")
        if errors > 0:
            logger.error("Rotation completed with errors! DO NOT REMOVE SECONDARY_SECRET_KEY.")
            sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_rotation()
EOF
```

---

### Bước 3: Xác Minh Hoàn Tất (Verification Gates)

Trước khi gỡ bỏ `SECONDARY_SECRET_KEY`, bắt buộc phải vượt qua cả 3 cổng kiểm tra sau:

#### Cổng 1: Kiểm Tra Toàn Bộ Dữ Liệu Giải Mã Được Chỉ Bằng Khóa Mới
Chạy probe kiểm tra độc lập, khởi tạo cipher **không có** `secondary_secret_key` để đảm bảo 100% bản ghi mở khóa thành công bằng `SECRET_KEY` mới:

```bash
uv run python - << 'EOF'
import sys
import logging
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.leads.enrichment import VerifiedContact
from app.services.pii.verified_contact_encryption import VerifiedContactEncryption

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_gate")

def verify_all_decodable():
    # Khởi tạo encryption instance CHỈ CÓ primary key (secondary = None)
    verifier = VerifiedContactEncryption(secondary_secret_key=None)
    db = SessionLocal()
    failed = 0
    total = 0

    try:
        records = db.execute(select(VerifiedContact)).scalars().all()
        for c in records:
            total += 1
            contact_dict = {"name": c.name, "title": c.title, "email": c.email, "phone": c.phone}
            try:
                verifier.decrypt_contact(contact_dict)
            except Exception as e:
                logger.error(f"Failed decoding contact {c.id} with new SECRET_KEY: {e}")
                failed += 1

        logger.info(f"Verification Summary: Total checked = {total}, Failures = {failed}")
        if failed > 0:
            sys.exit(1)
        print(">>> GATE 1 PASSED: 100% records successfully decryptable with new primary key.")
    finally:
        db.close()

if __name__ == "__main__":
    verify_all_decodable()
EOF
```

#### Cổng 2: Kiểm Tra Log Runtime
Theo dõi log của ứng dụng trong vòng 15-30 phút sau khi chạy migration:
```bash
docker logs --tail 2000 -f nowing-backend | grep "Decrypted PII with secondary key"
```
*Điều kiện đạt:* Không xuất hiện thêm bất kỳ log nào chứa dòng `"Decrypted PII with secondary key"`.

#### Cổng 3: Kiểm Tra Thử Nghiệm API
Thực hiện gọi API lấy thông tin contact từ client hoặc curl để xác nhận tính toàn vẹn PII:
```bash
curl -H "Authorization: Bearer <TOKEN>" https://api.nowing.net/api/v1/workspaces/<WID>/contacts
```
*Điều kiện đạt:* Dữ liệu trả về đầy đủ plaintext `email`, `phone`, không bị mã hóa hay lỗi 500.

---

### Bước 4: Thu Hồi & Gỡ Bỏ Khóa Cũ (Key Retirement)

Sau khi Bước 3 xác nhận thành công 100%:

1. **Gỡ bỏ biến môi trường:**
   Xóa `SECONDARY_SECRET_KEY` (và `OLD_SECRET_KEY` nếu có) khỏi cấu hình môi trường Dokploy.
   ```bash
   dokploy env unset --app nowing-backend SECONDARY_SECRET_KEY
   dokploy env unset --app nowing-worker SECONDARY_SECRET_KEY
   ```

2. **Khởi động lại toàn bộ dịch vụ:**
   Restart lại API và Celery workers để áp dụng cấu hình chỉ còn 1 khóa duy nhất.

3. **Kiểm tra xác nhận lần cuối:**
   Kiểm tra endpoint `/health` và đọc thử dữ liệu. Ghi nhận thời điểm hoàn thành vào nhật ký SecOps.

---

## 4. Kế Hoạch Phục Hồi Khi Có Sự Cố (Rollback Plan)

Trong trường hợp phát sinh lỗi nghiêm trọng ở bất kỳ giai đoạn nào:

### Kịch Bản A: Lỗi Ngay Tại Bước 1 (Sau Khi Deploy Khóa Mới)
- **Triệu chứng:** API không khởi động được, hoặc gặp lỗi xác thực JWT.
- **Hành động:**
  1. Đổi `SECRET_KEY` trở lại giá trị cũ (`CURRENT_SECRET_KEY`).
  2. Gỡ bỏ `SECONDARY_SECRET_KEY`.
  3. Redeploy containers.

### Kịch Bản B: Lỗi Trong Quá Trình Chạy Batch Migration (Bước 2)
- **Triệu chứng:** Script migration gặp lỗi gián đoạn mạng, crash hoặc timeout.
- **Đặc điểm:** Hệ thống vẫn an toàn vì cơ chế dual-key đang hoạt động song song.
- **Hành động:**
  1. Không gỡ `SECONDARY_SECRET_KEY`.
  2. Khắc phục nguyên nhân lỗi (DB load, resource) và chạy lại script migration. Script sử dụng keyset pagination (`WHERE id > last_id`) nên có thể tiếp tục xử lý an toàn mà không làm hỏng dữ liệu.

### Kịch Bản C: Lỗi Sau Khi Đã Gỡ `SECONDARY_SECRET_KEY` (Bước 4)
- **Triệu chứng:** Xuất hiện lỗi `ValueError: Token decryption failed with primary key` khi người dùng truy cập một số contact cũ.
- **Hành động khẩn cấp:**
  1. Khôi phục ngay lập tức `SECONDARY_SECRET_KEY=<khoá_cũ_đã_lưu_ở_bước_0>`.
  2. Restart container khẩn cấp để khôi phục khả năng giải mã fallback.
  3. Quay lại thực hiện lại Bước 2 và Bước 3.

---

## 5. Checklist Kiểm Tra Dành Cho Kỹ Sư Vận Hành

- [ ] **[Pha 0]** Đã lưu `CURRENT_SECRET_KEY` vào Vault an toàn.
- [ ] **[Pha 0]** Đã sinh `NEW_SECRET_KEY` chuẩn 256-bit entropy.
- [ ] **[Pha 0]** Đã hoàn tất snapshot/dump bảng `verified_contacts`.
- [ ] **[Pha 1]** Đã cấu hình `SECONDARY_SECRET_KEY=<old>` và `SECRET_KEY=<new>` trên Dokploy.
- [ ] **[Pha 1]** Đã deploy và kiểm tra `/health` thành công.
- [ ] **[Pha 2]** Đã chạy script `run_rotation()` xử lý hết 100% bản ghi với `errors = 0`.
- [ ] **[Pha 3]** Script kiểm tra độc lập (Gate 1) báo `100% records successfully decryptable`.
- [ ] **[Pha 3]** Log hệ thống không còn cảnh báo `"Decrypted PII with secondary key"`.
- [ ] **[Pha 4]** Đã gỡ `SECONDARY_SECRET_KEY` khỏi biến môi trường và restart container.
- [ ] **[Pha 4]** Kiểm tra sanity check sau khi gỡ khóa hoàn tất.
