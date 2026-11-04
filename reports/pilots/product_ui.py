"""First-party Reports UI: the React build from ui/dist. Tokens stay in browser memory.

Every /ui/... route returns index.html (the client router decides); /ui/assets/<file>
returns a hashed build file. The CSP forbids inline scripts and styles.
"""
import re
from pathlib import Path
from urllib.parse import urlsplit

DIST = Path(__file__).parent/'ui'/'dist'
TYPES = {'.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml'}
HEADERS = {'X-Content-Type-Options': 'nosniff', 'Referrer-Policy': 'no-referrer',
           'Content-Security-Policy': "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self' http://localhost:8180; "
                                      "base-uri 'none'; object-src 'none'; frame-ancestors 'none'; form-action 'none'"}


def serve(handler):
    path = urlsplit(handler.path).path
    asset = re.fullmatch(r'/ui/assets/([A-Za-z0-9_.-]+)', path)
    if asset:
        target = DIST/'assets'/asset.group(1)
        if target.suffix not in TYPES or not target.is_file(): return False
        name, mime, cache = target, TYPES[target.suffix], 'public, max-age=31536000, immutable'
    elif path == '/ui' or path.startswith('/ui/') or re.fullmatch(r'/snapshots/[0-9a-f-]{36}', path):
        name, mime, cache = DIST/'index.html', 'text/html; charset=utf-8', 'no-store'
    else:
        return False
    if not name.is_file(): return False
    data = name.read_bytes()
    handler.send_response(200)
    for key, value in {'Content-Type': mime, 'Content-Length': str(len(data)), 'Cache-Control': cache, **HEADERS}.items():
        handler.send_header(key, value)
    handler.end_headers(); handler.wfile.write(data)
    return True
