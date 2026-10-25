"""Static first-party UI. Tokens stay in browser memory; source text is escaped."""
import re
from pathlib import Path
from urllib.parse import urlsplit


def serve(handler):
    path=urlsplit(handler.path).path
    files={'/ui/':('index.html','text/html; charset=utf-8'),'/ui/callback':('index.html','text/html; charset=utf-8'),
           '/ui/app.js':('app.js','text/javascript; charset=utf-8'),'/ui/styles.css':('styles.css','text/css; charset=utf-8')}
    if re.fullmatch(r'/snapshots/[0-9a-f-]{36}',path): files[path]=('index.html','text/html; charset=utf-8')
    if path not in files: return False
    name,mime=files[path];data=(Path(__file__).parent/'ui'/name).read_bytes()
    handler.send_response(200)
    for key,value in {'Content-Type':mime,'Content-Length':str(len(data)),'Cache-Control':'no-store',
        'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
        'Content-Security-Policy':"default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self' http://localhost:8180; base-uri 'none'; object-src 'none'; frame-ancestors 'none'"}.items(): handler.send_header(key,value)
    handler.end_headers();handler.wfile.write(data);return True
