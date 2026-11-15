import os

# Scripts only from our own origin (no inline JS), so injected <script> tags
# cannot run even if some HTML escaping were missed.
CSP = '; '.join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data:",
    "connect-src 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "base-uri 'none'",
    "object-src 'none'",
])


class ContentSecurityPolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault('Content-Security-Policy', CSP)
        response.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        return response


# First bytes each file type must start with. A renamed .exe will not pass.
_ZIP = [b'PK\x03\x04', b'PK\x05\x06']
_OLE = [b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1']  # old .doc/.xls/.ppt
MAGIC = {
    'pdf': [b'%PDF-'],
    'zip': _ZIP, 'docx': _ZIP, 'xlsx': _ZIP, 'pptx': _ZIP, 'odt': _ZIP, 'ods': _ZIP, 'odp': _ZIP,
    'doc': _OLE, 'xls': _OLE, 'ppt': _OLE,
    'rar': [b'Rar!\x1a\x07'], '7z': [b"7z\xbc\xaf'\x1c"], 'gz': [b'\x1f\x8b'], 'tgz': [b'\x1f\x8b'],
    'png': [b'\x89PNG\r\n\x1a\n'], 'jpg': [b'\xff\xd8\xff'], 'jpeg': [b'\xff\xd8\xff'],
    'gif': [b'GIF87a', b'GIF89a'], 'webp': [b'RIFF'], 'bmp': [b'BM'],
    'mp3': [b'ID3', b'\xff\xfb', b'\xff\xf3', b'\xff\xf2'], 'wav': [b'RIFF'], 'avi': [b'RIFF'],
}
# Containers whose signature sits at offset 4 (ftyp box).
FTYP_EXT = {'mp4', 'm4a', 'mov', 'heic'}
TEXT_EXT = {
    'txt', 'md', 'csv', 'tsv', 'json', 'xml', 'yaml', 'yml', 'tex', 'bib', 'ipynb', 'sql', 'log',
    'py', 'c', 'cc', 'cpp', 'h', 'hpp', 'java', 'kt', 'cs', 'go', 'rs', 'swift', 'm', 'r', 'rb', 'php',
    'js', 'jsx', 'ts', 'tsx', 'vue', 'html', 'htm', 'css', 'scss', 'svg', 'dart', 'lua', 'pl', 'scala',
}
# Never accept these, whatever the teacher configured: they run when opened.
BLOCKED_EXT = {'exe', 'bat', 'cmd', 'com', 'msi', 'msp', 'scr', 'pif', 'cpl', 'dll', 'sys', 'vbs', 'vbe',
               'wsf', 'wsh', 'ps1', 'psm1', 'lnk', 'reg', 'hta', 'app', 'dmg', 'pkg', 'apk', 'deb', 'rpm',
               'jar', 'sh', 'command', 'iso', 'img'}


def content_matches(f, ext):
    """True if the uploaded file's content fits its extension."""
    head = f.read(2048)
    f.seek(0)
    if ext in MAGIC:
        return any(head.startswith(m) for m in MAGIC[ext])
    if ext in FTYP_EXT:
        return head[4:8] == b'ftyp'
    if ext in TEXT_EXT:
        if b'\x00' in head:
            return False
        try:
            head.decode('utf-8')
        except UnicodeDecodeError as e:
            # A multi-byte char may be cut at the 2048-byte boundary.
            return e.start >= len(head) - 4
        return True
    # Unknown types: allowed only if the teacher listed them; still stored
    # under a random name and always downloaded as an attachment.
    return True


def safe_display_name(name):
    """Keep only the base name, strip control chars."""
    name = os.path.basename(name.replace('\\', '/'))
    name = ''.join(ch for ch in name if ch.isprintable() and ch not in '"<>')
    return name[:200] or 'file'


class ForcePasswordChangeMiddleware:
    """Users created with a temporary password must set their own first."""
    ALLOWED = ('password_change', 'password_change_done', 'logout', 'help', 'privacy')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            flags = AccountFlag_for(user)
            if flags and flags.must_change_password:
                from django.urls import resolve, reverse, Resolver404
                try:
                    name = resolve(request.path_info).url_name
                except Resolver404:
                    name = None
                if name not in self.ALLOWED and not request.path_info.startswith('/static/'):
                    from django.shortcuts import redirect
                    return redirect(reverse('password_change'))
        return self.get_response(request)


def AccountFlag_for(user):
    from .models import AccountFlag
    try:
        return user.flags
    except AccountFlag.DoesNotExist:
        return None
