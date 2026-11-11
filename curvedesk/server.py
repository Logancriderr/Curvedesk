"""Loopback-only local HTTP interface. No cloud, CDN, telemetry or order execution."""
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import date
import json
import secrets
import threading
from .data import load_snapshot, fetch_treasury, import_curve_csv
from .service import calculation

WEB = Path(__file__).resolve().parent.parent/'web'

def make_server(port=8765, data_dir='data'):
    token = secrets.token_urlsafe(24)
    lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # Do not log portfolio requests.

        def reply(self, status, data, kind='application/json'):
            body = json.dumps(data,allow_nan=False).encode() if kind == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type',kind+'; charset=utf-8')
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(body)

        def host_ok(self):
            return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}')

        def do_GET(self):
            if not self.host_ok():
                return self.reply(403,{'error':'Local host required'})
            url = urlparse(self.path)
            try:
                if url.path == '/api/health':
                    return self.reply(200,{'status':'ok'})
                if url.path == '/api/config':
                    return self.reply(200,{'token':token,'today':date.today().isoformat()})
                if url.path == '/api/curves':
                    source = parse_qs(url.query).get('source',['demo'])[0]
                    return self.reply(200,load_snapshot(source,data_dir))
                files = {'/':('index.html','text/html'),'/app.js':('app.js','text/javascript'),'/style.css':('style.css','text/css')}
                if url.path not in files:
                    return self.reply(404,{'error':'Not found'})
                name, kind = files[url.path]
                return self.reply(200,(WEB/name).read_bytes(),kind)
            except (ValueError,OSError,KeyError) as e:
                return self.reply(400,{'error':str(e)})

        def do_POST(self):
            if not self.host_ok() or self.headers.get('X-CurveDesk-Token') != token:
                return self.reply(403,{'error':'Reload the local page to establish a valid session'})
            origin = self.headers.get('Origin')
            if origin and origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'):
                return self.reply(403,{'error':'Cross-origin request rejected'})
            try:
                n = int(self.headers.get('Content-Length','0'))
                if not 0 < n <= 1_000_000 or self.headers.get('Content-Type','').split(';')[0] != 'application/json':
                    raise ValueError('Send application/json, maximum 1 MB')
                def bad_constant(value):
                    raise ValueError('Nonfinite JSON is not allowed')
                payload = json.loads(self.rfile.read(n),parse_constant=bad_constant)
                if not isinstance(payload,dict):
                    raise ValueError('JSON body must be an object')
                if self.path == '/api/calculate':
                    result = calculation(payload,data_dir)
                elif self.path == '/api/refresh':
                    with lock:
                        result = fetch_treasury(data_dir)
                elif self.path == '/api/import-curve':
                    with lock:
                        result = import_curve_csv(payload['csv'],data_dir)
                else:
                    return self.reply(404,{'error':'Not found'})
                return self.reply(200,result)
            except (ValueError,TypeError,KeyError,OSError,OverflowError) as e:
                return self.reply(400,{'error':str(e)})
            except Exception:
                return self.reply(500,{'error':'Unexpected server error; inspect the inputs and rerun the tests'})
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)
