"""Parse and validate a user list from .xlsx or .csv for bulk import."""
import csv
import io
import re
import unicodedata

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from .models import Course, Enrollment

MAX_ROWS = 500
MAX_BYTES = 5 * 1024 * 1024
USERNAME_RE = re.compile(r'^[\w.@+-]{3,150}$')

# Column name (normalised) -> field. Vietnamese and English headers both work.
HEADERS = {
    'username': 'username', 'tendangnhap': 'username', 'taikhoan': 'username', 'mssv': 'username',
    'ho': 'last_name', 'hovatendem': 'last_name', 'lastname': 'last_name', 'hodem': 'last_name',
    'ten': 'first_name', 'firstname': 'first_name',
    'email': 'email', 'mail': 'email',
    'vaitro': 'role', 'role': 'role',
    'makhoa': 'courses', 'khoahoc': 'courses', 'course': 'courses', 'courses': 'courses', 'mamon': 'courses',
}
ROLE_WORDS = {
    '': Enrollment.STUDENT, 'student': Enrollment.STUDENT, 'hocvien': Enrollment.STUDENT,
    'hocsinh': Enrollment.STUDENT, 'sinhvien': Enrollment.STUDENT, 'sv': Enrollment.STUDENT,
    'teacher': Enrollment.TEACHER, 'giaovien': Enrollment.TEACHER, 'gv': Enrollment.TEACHER,
    'giangvien': Enrollment.TEACHER,
}
TEMPLATE_COLUMNS = ['Tên đăng nhập', 'Họ', 'Tên', 'Email', 'Vai trò', 'Mã khoá']


class ImportError_(Exception):
    """File-level problem (bad format, no header, too many rows)."""


def _norm(text):
    text = unicodedata.normalize('NFD', str(text or '')).replace('đ', 'd').replace('Đ', 'D')
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9]', '', text.lower())


def _cell(v):
    if v is None:
        return ''
    if isinstance(v, float) and v.is_integer():
        v = int(v)  # Excel stores numeric IDs as floats
    return str(v).strip()


def _read_rows(upload):
    name = upload.name.lower()
    if upload.size > MAX_BYTES:
        raise ImportError_('File lớn hơn 5 MB.')
    data = upload.read()
    if name.endswith('.xlsx'):
        if not data.startswith(b'PK\x03\x04'):
            raise ImportError_('File .xlsx không hợp lệ.')
        from openpyxl import load_workbook  # uses defusedxml when installed
        try:
            wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        except Exception:
            raise ImportError_('Không đọc được file Excel.')
        ws = wb.worksheets[0]
        rows = [[_cell(c) for c in r] for r in ws.iter_rows(values_only=True, max_row=MAX_ROWS + 2)]
        wb.close()
        return rows
    if name.endswith('.csv'):
        for enc in ('utf-8-sig', 'cp1258', 'latin-1'):
            try:
                text = data.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        dialect = csv.excel
        try:
            dialect = csv.Sniffer().sniff(text[:2048], delimiters=',;\t')
        except csv.Error:
            pass
        return [[_cell(c) for c in r] for r in csv.reader(io.StringIO(text), dialect)]
    raise ImportError_('Chỉ nhận file .xlsx hoặc .csv.')


def parse(upload):
    """Return a list of row dicts: {line, username, first_name, last_name, email, role, courses}."""
    rows = [r for r in _read_rows(upload) if any(r)]
    if not rows:
        raise ImportError_('File trống.')
    header = [HEADERS.get(_norm(h)) for h in rows[0]]
    if 'username' not in header:
        raise ImportError_('Không thấy cột "Tên đăng nhập" ở dòng đầu tiên. Hãy dùng file mẫu.')
    body = rows[1:]
    if len(body) > MAX_ROWS:
        raise ImportError_(f'Tối đa {MAX_ROWS} người mỗi lần nhập.')
    out = []
    for i, r in enumerate(body, start=2):
        item = {'line': i, 'username': '', 'first_name': '', 'last_name': '', 'email': '', 'role': '', 'courses': ''}
        for field, value in zip(header, r):
            if field:
                item[field] = value
        out.append(item)
    return out


def validate(items, default_course=None, default_role=Enrollment.STUDENT):
    """Annotate each row with status ('new' | 'existing' | 'error'), errors and resolved courses."""
    User = get_user_model()
    wanted = {i['username'].lower() for i in items if i['username']}
    existing, emails_taken = {}, set()
    for u in User.objects.only('id', 'username', 'email').iterator():
        if u.username.lower() in wanted:
            existing[u.username.lower()] = u
        if u.email:
            emails_taken.add(u.email.lower())
    courses = {c.code.lower(): c for c in Course.objects.all()}
    seen, seen_emails = set(), set()

    for it in items:
        errs = []
        name = it['username']
        if not name:
            errs.append('Thiếu tên đăng nhập')
        elif not USERNAME_RE.match(name):
            errs.append('Tên đăng nhập chỉ gồm chữ, số và . @ + - _ (3–150 ký tự)')
        elif name.lower() in seen:
            errs.append('Trùng tên đăng nhập trong file')
        seen.add(name.lower())

        email = it['email'].lower()
        if email:
            try:
                validate_email(email)
            except ValidationError:
                errs.append('Email không hợp lệ')
            else:
                user = existing.get(name.lower())
                if email in seen_emails or (email in emails_taken and not (user and user.email.lower() == email)):
                    errs.append('Email đã được dùng')
            seen_emails.add(email)
        it['email'] = email

        if not it['role']:
            it['role'] = default_role
        else:
            role = ROLE_WORDS.get(_norm(it['role']))
            if role is None:
                errs.append('Vai trò phải là "học viên" hoặc "giáo viên"')
            it['role'] = role or default_role

        codes = [c.strip() for c in re.split(r'[,;]', it['courses']) if c.strip()]
        found = []
        for code in codes:
            c = courses.get(code.lower())
            if c:
                found.append(c)
            else:
                errs.append(f'Không có khoá "{code}"')
        if default_course and default_course not in found:
            found.append(default_course)
        it['course_objs'] = found
        it['course_codes'] = [c.code for c in found]

        for f, n in (('first_name', 150), ('last_name', 150)):
            if len(it[f]) > n:
                errs.append('Họ tên quá dài')

        it['errors'] = errs
        user = existing.get(name.lower())
        it['status'] = 'error' if errs else ('existing' if user else 'new')
        it['user_id'] = user.pk if user else None
    return items


def template_bytes():
    """An .xlsx template with headers and two example rows."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook()
    ws = wb.active
    ws.title = 'Danh sách'
    ws.append(TEMPLATE_COLUMNS)
    ws.append(['22520001', 'Nguyễn Văn', 'An', 'an.nv@example.edu.vn', 'học viên', 'WEB101'])
    ws.append(['gv.binh', 'Trần Thị', 'Bình', 'binh.tt@example.edu.vn', 'giáo viên', 'WEB101, AI201'])
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = PatternFill('solid', fgColor='1D4F91')
    for col, width in zip('ABCDEF', (18, 20, 12, 30, 12, 20)):
        ws.column_dimensions[col].width = width
    ws.freeze_panes = 'A2'
    note = wb.create_sheet('Hướng dẫn')
    for line in [
        'Chỉ cột "Tên đăng nhập" là bắt buộc.',
        'Vai trò: "học viên" (mặc định) hoặc "giáo viên".',
        'Mã khoá: một hoặc nhiều mã, cách nhau bằng dấu phẩy. Khoá phải có sẵn trong hệ thống.',
        'Không ghi mật khẩu vào file. Hệ thống tự tạo mật khẩu tạm, người dùng phải đổi khi đăng nhập lần đầu.',
        'Tối đa 500 dòng mỗi lần nhập.',
    ]:
        note.append([line])
    note.column_dimensions['A'].width = 100
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def safe_cell(value):
    """Neutralise spreadsheet formula injection in exported text."""
    s = str(value)
    return "'" + s if s[:1] in ('=', '+', '-', '@', '\t', '\r') else s
