# Learning Management System

Hệ thống quản lý học tập và nộp bài trực tuyến theo khoá học, kiểu Moodle thu gọn.
Django 5.2 + PostgreSQL, chạy bằng Docker, CI/CD bằng GitHub Actions với hai môi trường dev và prod.

## Tính năng

**Học viên**
- Xem các khoá đã ghi danh, bài sắp đến hạn và lịch deadline theo tháng.
- Nộp bài bằng kéo thả, nộp lại nhiều lần; mọi lần nộp đều được giữ lại.
- Xem điểm, nhận xét và tiến độ của mình trong từng khoá.

**Giáo viên**
- Tạo bài tập với giờ mở, hạn nộp, giờ đóng (nhận bài trễ), số lần nộp, định dạng và dung lượng file.
- Tab **Thành viên**: danh sách học viên, tiến độ, điểm trung bình, lần truy cập gần nhất; ghi danh bằng username.
- Tab **Bảng điểm**: ma trận học viên × bài tập, trạng thái từng ô, xuất CSV.
- Chấm điểm và nhận xét ngay trên trang bài tập; tải bài nộp.

**Quản trị**
- Trang quản trị Django đã chỉnh giao diện cho khớp với trang chính.
- **Nhập người dùng từ Excel/CSV**: xem trước từng dòng, tự sinh mật khẩu tạm hiện một lần,
  người dùng bắt buộc đổi mật khẩu khi đăng nhập lần đầu.

## Kiến trúc

```
              Internet
                 │ 80/443
        ┌────────▼────────┐   image: lms-proxy
        │  proxy (Caddy)  │   HTTPS, giới hạn upload, phục vụ /static/ (CSS, JS, icon)
        └────────┬────────┘
     mạng "edge" │
        ┌────────▼────────┐   image: lms-web
        │  web (Django)   │   logic, giao diện (template), file nộp trong volume lms_data
        └────────┬────────┘
  mạng "backend" │ (internal: không ra Internet, không mở cổng)
        ┌────────▼────────┐   postgres:18-alpine, volume pg_data
        │  db (Postgres)  │   hoặc thay bằng cloud DB (RDS, Cloud SQL, Neon…)
        └─────────────────┘
```

- Sửa **CSS/JS/icon** (`courses/static/`) → chỉ build và deploy lại `proxy`.
- Sửa **code Python hoặc template** → test, rồi build và deploy lại `web`.
- Database tách riêng: cập nhật hay khởi động lại app không đụng vào dữ liệu.

## Bắt đầu nhanh (máy cá nhân)

Cần Docker với Docker Compose.

```bash
git clone https://github.com/huyhoanCShcmuit/learning-management-system.git
cd learning-management-system
./setup.sh
```

Lần đầu, `setup.sh` tạo `.env` (chỉ cấu hình), thư mục `secrets/` (mật khẩu database ngẫu nhiên),
build 3 container và hỏi bạn tạo tài khoản quản trị. Mở http://localhost:8000.
Đường dẫn trang quản trị nằm ở dòng `ADMIN_URL` trong `.env`.

Muốn có dữ liệu mẫu: đặt `SEED_DEMO=1` trong `.env` rồi chạy lại `./setup.sh`
(tài khoản `admin`, `gv1`, `hs1`… mật khẩu `demo1234`). **Không bật trên máy thật.**

### Lệnh thường dùng

```bash
docker compose ps                                              # trạng thái 3 container
docker compose logs -f web                                     # log backend
docker compose exec web python manage.py createsuperuser       # tạo admin
docker compose exec web python manage.py changepassword admin  # đổi mật khẩu
scripts/backup.sh                                              # sao lưu DB + file nộp vào backups/
scripts/restore.sh backups/db_XXXX.dump                        # khôi phục DB
```

`docker compose down -v` sẽ **xoá luôn toàn bộ dữ liệu**.

## Database

| Chế độ | Cấu hình |
|---|---|
| Container `db` (mặc định) | `COMPOSE_PROFILES=localdb` trong `.env`; mật khẩu ở `secrets/db_password` |
| Cloud DB | Ghi URL vào `secrets/database_url` (ví dụ `postgres://user:pass@host:5432/lms?sslmode=require`), đặt `COMPOSE_PROFILES=` (rỗng) rồi `docker compose up -d` |
| Phát triển không Docker | Không đặt gì → SQLite |

**Kéo dữ liệu cloud về container ở máy** (để thử nghiệm, debug):

```bash
echo 'postgres://user:pass@host:5432/lms?sslmode=require' > secrets/cloud_database_url
scripts/pull_cloud_db.sh      # pg_dump từ cloud → backups/cloud_*.dump → nạp vào container db
```

URL cloud chỉ nằm trong `secrets/` (không commit, không hiện trên dòng lệnh).

## Nhánh, môi trường và CI/CD

| Nhánh | Môi trường | Image | Ghi chú |
|---|---|---|---|
| `development` | **development** (máy chủ dev) | `lms-web:dev`, `lms-proxy:dev` | được bảo vệ |
| `master` | **production** (máy chủ prod) | `:prod` và `:latest` | được bảo vệ |

Cả hai nhánh **không push thẳng được**: mọi thay đổi phải qua Pull Request, CI (`Tests (PostgreSQL)`)
phải xanh mới merge được; không force-push, không xoá nhánh.

Quy trình làm việc:

```bash
git switch development && git pull
git switch -c feature/ten-tinh-nang      # làm việc trên nhánh riêng
git push -u origin feature/ten-tinh-nang # mở PR vào development → merge → tự deploy lên dev
# khi dev ổn: mở PR development → master → merge → tự deploy lên prod
```

Workflow `.github/workflows/ci-cd.yml`:

| Sự kiện | Việc chạy |
|---|---|
| PR vào `development`/`master` | Test trên PostgreSQL thật, kiểm tra migration, build thử image phần bị sửa |
| Merge vào `development` | Build và đẩy image `:dev` lên GHCR, deploy lên máy chủ dev |
| Merge vào `master` | Build và đẩy image `:prod`, deploy lên máy chủ prod |
| Chạy tay (Run workflow) | Tuỳ chọn build và deploy cả hai phần |

Chỉ phần bị sửa mới được build và khởi động lại: sửa `courses/static/**` → chỉ `proxy`;
sửa code Python/template → chỉ `web`.

### Cấu hình máy chủ cho từng môi trường

Trên mỗi máy chủ (VPS/VM có Docker), lần đầu:

```bash
git clone https://github.com/huyhoanCShcmuit/learning-management-system.git /opt/lms
cd /opt/lms && ./setup.sh
# máy dev: đặt TAG=dev trong .env; máy prod: TAG=prod
```

Trên GitHub, **Settings → Environments → `development`** (và tương tự cho **`production`**):

| Loại | Tên | Giá trị |
|---|---|---|
| Variable | `DEPLOY_ENABLED` | `true` |
| Variable | `DEPLOY_PATH` | `/opt/lms` (mặc định) |
| Secret | `DEPLOY_HOST` | địa chỉ máy chủ của môi trường đó |
| Secret | `DEPLOY_USER` | user SSH (thuộc nhóm `docker`) |
| Secret | `DEPLOY_SSH_KEY` | private key dành riêng cho deploy |
| Secret | `DEPLOY_KNOWN_HOSTS` | kết quả `ssh-keyscan <host>` |

Chưa cấu hình thì bước deploy chỉ ghi chú "Deploy skipped", build vẫn chạy bình thường.
Có thể bật "Required reviewers" cho `production` để mỗi lần lên prod phải có người duyệt.
Nếu package trên GHCR để private, máy chủ cần `docker login ghcr.io` một lần bằng token có quyền `read:packages`.

Quay lại bản cũ trên máy chủ: `TAG=<mã commit cũ> docker compose up -d web proxy`.

## Bảo mật

| Thứ | Lưu ở đâu |
|---|---|
| Mật khẩu người dùng | Database, chỉ dạng hash Argon2 |
| Mật khẩu database, URL cloud DB | `secrets/` (quyền 700, không commit), nạp vào container dạng Docker secret |
| Secret key của Django | File trong volume `lms_data`, tự sinh |
| `.env` | Chỉ cấu hình, không chứa bí mật, không commit |

Các lớp bảo vệ khác:
- Phân quyền theo vai trò trong từng khoá; học viên chỉ xem và tải bài của chính mình.
- File nộp: kiểm tra nội dung thật theo đuôi, chặn file thực thi, lưu bằng tên ngẫu nhiên, luôn tải về dạng đính kèm.
- Content-Security-Policy không cho script inline, chặn nhúng iframe, cookie `HttpOnly` và `SameSite`.
- Database ở mạng nội bộ, không mở cổng. Container chạy user không phải root, bỏ hết quyền đặc biệt,
  backend có hệ thống file chỉ đọc. Proxy giới hạn 60 MB mỗi request.
- Khi chạy với domain thật và `HTTPS=1`: chứng chỉ Let's Encrypt tự động, HSTS, cookie chỉ qua HTTPS.

## Phát triển không dùng Docker

Cần Python 3.10 trở lên.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py runserver      # http://127.0.0.1:8000, admin ở /admin/
```

## Cấu trúc thư mục

```
config/                 cấu hình Django
courses/                app chính: models, views, templates, static, tests
templates/              đăng nhập, trang lỗi, trợ giúp, nhập người dùng, override admin
docker/                 web.Dockerfile, proxy.Dockerfile, Caddyfile, entrypoint
scripts/                backup, restore, kéo dữ liệu từ cloud
.github/workflows/      CI/CD
docker-compose.yml      3 container: proxy, web, db
setup.sh                khởi tạo lần đầu
```
