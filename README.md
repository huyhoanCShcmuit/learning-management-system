# Learning Management System

Hệ thống quản lý học tập và nộp bài trực tuyến theo khoá học, kiểu Moodle thu gọn.
Viết bằng Django 5.2, chạy bằng Docker sau reverse proxy Caddy.

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
- **Nhập người dùng từ Excel/CSV**: xem trước từng dòng (tạo mới / đã có / lỗi), tự sinh mật khẩu tạm hiện một lần,
  người dùng bắt buộc đổi mật khẩu khi đăng nhập lần đầu.

**Chung**
- Trang cá nhân, cài đặt tài khoản, đổi mật khẩu, trang trợ giúp và quyền riêng tư.
- Giao diện tiếng Việt, hỗ trợ chế độ tối và điện thoại.

## Bắt đầu nhanh (Docker)

Cần [Docker](https://docs.docker.com/get-docker/) với Docker Compose.

```bash
git clone https://github.com/huyhoanCShcmuit/learning-management-system.git
cd learning-management-system
./setup.sh
```

Lần chạy đầu, `setup.sh` sẽ:
1. tạo file `.env` (chỉ chứa cấu hình, không có mật khẩu hay khoá bí mật);
2. build và chạy các container;
3. hỏi bạn tạo tài khoản quản trị ngay trong terminal.

Sau đó mở http://localhost:8000. Đường dẫn trang quản trị nằm ở dòng `ADMIN_URL` trong `.env`.

Muốn có dữ liệu mẫu để thử, đặt `SEED_DEMO=1` trong `.env` rồi chạy lại `./setup.sh`.
Các tài khoản mẫu `admin`, `gv1`, `hs1`, `hs2`, `hs3` dùng mật khẩu `demo1234`. **Không bật trên máy thật.**

### Lệnh thường dùng

```bash
docker compose logs -f                                         # xem log
docker compose down                                            # dừng (giữ dữ liệu)
docker compose exec web python manage.py createsuperuser       # tạo thêm admin
docker compose exec web python manage.py changepassword admin  # đổi mật khẩu admin
docker compose run --rm --no-deps web python manage.py test courses   # chạy test
```

`docker compose down -v` sẽ **xoá luôn toàn bộ dữ liệu** (database và file nộp).

### Chạy với domain thật (HTTPS)

Trong `.env`, đặt:

```
SITE_ADDRESS=lms.example.com
DJANGO_ALLOWED_HOSTS=lms.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://lms.example.com
HTTPS=1
HTTP_PORT=80
HTTPS_PORT=443
```

Caddy sẽ tự lấy chứng chỉ Let's Encrypt. Khi `HTTPS=1`, Django bật HSTS và cookie chỉ gửi qua HTTPS.

## Phát triển không dùng Docker

Cần Python 3.10 trở lên.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo      # dữ liệu mẫu
.venv/bin/python manage.py runserver
```

Mở http://127.0.0.1:8000. Ở chế độ này trang quản trị nằm ở `/admin/`.

## Bảo mật

| Thứ | Lưu ở đâu |
|---|---|
| Mật khẩu người dùng | Database, chỉ dạng hash Argon2 |
| Secret key của Django | File `/data/secret_key` trong volume dữ liệu, tự sinh, quyền 600 |
| `.env` | Chỉ cấu hình: domain, cổng, đường dẫn admin. Không commit lên git |

Các lớp bảo vệ khác:
- Phân quyền theo vai trò trong từng khoá; học viên chỉ xem và tải bài của chính mình.
- File nộp: kiểm tra nội dung thật theo đuôi (đổi tên `.exe` thành `.pdf` sẽ bị từ chối), chặn file thực thi,
  lưu bằng tên ngẫu nhiên, luôn tải về dạng đính kèm.
- Content-Security-Policy không cho script inline, chặn nhúng iframe, cookie `HttpOnly` và `SameSite`.
- Đường dẫn trang quản trị khó đoán; mật khẩu tối thiểu 10 ký tự.
- Container chạy với user không phải root, hệ thống file chỉ đọc, bỏ hết quyền đặc biệt;
  app không mở cổng ra ngoài, chỉ Caddy nhận request (giới hạn 60 MB mỗi request).

## Cấu trúc thư mục

```
config/              cấu hình Django (settings, urls)
courses/
  models.py          Course, Enrollment, Assignment, Submission, AccountFlag
  views.py           trang chủ, lịch, khoá học, bài tập, nộp bài, chấm điểm
  views_course.py    thành viên, bảng điểm, tiến độ học viên
  views_account.py   trang cá nhân, cài đặt
  views_manage.py    nhập người dùng
  importer.py        đọc và kiểm tra file Excel/CSV
  security.py        CSP, kiểm tra nội dung file, bắt buộc đổi mật khẩu
  templates/         giao diện các trang
  static/courses/    CSS, JS, favicon
  tests.py           test tự động
templates/           trang đăng nhập, lỗi 403/404/500, trợ giúp, admin
docker/              Caddyfile, entrypoint
Dockerfile, docker-compose.yml, setup.sh
```

## Quy tắc nộp bài

- Chỉ học viên đã ghi danh vào khoá mới nộp được.
- Nộp được từ giờ mở đến giờ đóng (nếu không đặt giờ đóng thì là hạn nộp).
- Nộp sau hạn nhưng trước giờ đóng bị đánh dấu **trễ**. Thời gian lấy theo đồng hồ máy chủ.
- Mỗi lần nộp là một bản ghi mới, không ghi đè; tối đa theo số lần giáo viên đặt.
