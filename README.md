# Learning Management System – hệ thống nộp bài theo khoá học

Django 5.2 + SQLite. Có: khoá học, ghi danh (giáo viên/học sinh), bài tập có hạn nộp,
nộp file nhiều lần, đánh dấu trễ, chấm điểm, bảng điểm, xuất CSV, lịch deadline,
nhập người dùng từ Excel/CSV (mật khẩu tạm, bắt buộc đổi ở lần đăng nhập đầu).

## Chạy bằng Docker (1 lệnh)

```bash
cd ~/Documents/LMS
./setup.sh
```

Lần đầu, script tạo `.env` (không chứa mật khẩu hay khoá bí mật) và hỏi bạn tạo tài khoản
quản trị ngay trong terminal. Mở http://localhost:8000.

### Mật khẩu và bí mật được lưu ở đâu

| Thứ | Lưu ở | Ghi chú |
|---|---|---|
| Mật khẩu người dùng, kể cả admin | Database, dạng hash Argon2 | Không file nào chứa mật khẩu thật |
| Secret key của Django | `/data/secret_key` trong volume `lms_data` | Tự sinh, quyền 600 |
| `.env` | Thư mục dự án | Chỉ cấu hình: domain, cổng, đường dẫn admin |

Quản lý tài khoản admin (gõ mật khẩu trực tiếp, không lưu ra file):

```bash
docker compose exec web python manage.py createsuperuser          # tạo admin mới
docker compose exec web python manage.py changepassword admin     # đổi mật khẩu
```

- Xem log: `docker compose logs -f`
- Dừng: `docker compose down` (thêm `-v` sẽ **xoá luôn dữ liệu**)
- Không bật `SEED_DEMO=1` trên máy thật (tài khoản mẫu có mật khẩu yếu).

## Chạy để phát triển (không Docker)

```bash
cd ~/Documents/LMS
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # lần đầu
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo        # dữ liệu mẫu
.venv/bin/python manage.py runserver
```

Mở http://127.0.0.1:8000. Tài khoản mẫu (mật khẩu `demo1234`):
`admin` (quản trị), `gv1` (giáo viên), `hs1`, `hs2`, `hs3` (học sinh).

Tạo khoá và ghi danh: vào `/admin/` → Khoá học → thêm thành viên ngay trong trang khoá.

## Cấu trúc

- `courses/models.py`: Course, Enrollment, Assignment, Submission
- `courses/views.py`: phân quyền theo vai trò trong khoá, nộp bài, chấm, tải file, CSV
- `uploads/`: file nộp (lưu tên UUID, chỉ tải qua view có kiểm tra quyền)

## Quy tắc nộp bài

- Chỉ học sinh đã ghi danh mới nộp được.
- Nộp được từ `open_at` đến `cutoff_at` (hoặc `due_at` nếu không có cutoff).
- Thời gian lấy theo server; nộp sau `due_at` thì bị đánh dấu trễ.
- Mỗi lần nộp là một bản ghi mới, không ghi đè; giới hạn `max_attempts`.
