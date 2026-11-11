import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from curvedesk.server import make_server

class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.server=make_server(0,cls.tmp.name)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base=f'http://127.0.0.1:{cls.server.server_port}'
        cls.token=json.load(urlopen(cls.base+'/api/config'))['token']
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def post(self,path,data,token=True):
        headers={'Content-Type':'application/json'}
        if token:headers['X-CurveDesk-Token']=self.token
        return urlopen(Request(self.base+path,data=json.dumps(data).encode(),headers=headers))
    def test_static_ui(self):
        with urlopen(self.base) as r:
            self.assertIn(b'CurveDesk',r.read());self.assertIn('frame-ancestors',r.headers['Content-Security-Policy'])
    def test_calculate_api(self):
        p=json.loads((Path(__file__).resolve().parent.parent/'examples/request.json').read_text())
        with self.post('/api/calculate',p) as r:self.assertEqual(json.load(r)['source'],'demo')
    def test_token_required(self):
        with self.assertRaises(HTTPError) as c:self.post('/api/refresh',{},False)
        self.assertEqual(c.exception.code,403)
    def test_host_rebinding_rejected(self):
        with self.assertRaises(HTTPError) as c:urlopen(Request(self.base+'/api/config',headers={'Host':'attacker.example'}))
        self.assertEqual(c.exception.code,403)
    def test_traversal_rejected(self):
        with self.assertRaises(HTTPError) as c:urlopen(self.base+'/../curvedesk/data.py')
        self.assertEqual(c.exception.code,404)
