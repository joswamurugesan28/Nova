import json, threading, http.server, socketserver, time, unittest
from nova.apps.godot.bridge import GodotBridge, GodotBridgeError

TOKEN = "tok"

class MockHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self._resp(401, {"ok": False, "error": "unauthorized"}); return
        if self.path == "/health":
            self._resp(200, {"ok": True, "status": "running"})
        elif self.path == "/project":
            self._resp(200, {"ok": True, "name": "demo", "root": "/tmp/demo"})
        else:
            self._resp(404, {"ok": False, "error": "unknown"})
    def do_POST(self):
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            self._resp(401, {"ok": False, "error": "unauthorized"}); return
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw) if raw else {}
        except Exception:
            self._resp(400, {"ok": False, "error": "invalid payload"}); return
        if self.path == "/script/read":
            if not payload.get("path"):
                self._resp(400, {"ok": False, "error": "missing path"}); return
            self._resp(200, {"ok": True, "content": "extends Node"})
        elif self.path == "/script/write":
            if not payload.get("path"):
                self._resp(400, {"ok": False, "error": "missing path"}); return
            self._resp(200, {"ok": True})
        else:
            self._resp(404, {"ok": False, "error": "unknown"})
    def _resp(self, code, body):
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)
    def log_message(self, *a):
        pass

class TestBridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = socketserver.TCPServer(("127.0.0.1", 0), MockHandler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        time.sleep(0.2)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def test_health_auth(self):
        b = GodotBridge(port=self.port, token=TOKEN)
        self.assertTrue(b.health()["ok"])

    def test_unauth(self):
        b = GodotBridge(port=self.port, token="wrong")
        with self.assertRaises(GodotBridgeError):
            b.health()

    def test_invalid_payload(self):
        # client sends missing path -> 400 -> error
        b = GodotBridge(port=self.port, token=TOKEN)
        with self.assertRaises(GodotBridgeError):
            b.read_script("")

    def test_read_script(self):
        b = GodotBridge(port=self.port, token=TOKEN)
        self.assertEqual(b.read_script("main.gd")["content"], "extends Node")

    def test_write_script(self):
        b = GodotBridge(port=self.port, token=TOKEN)
        self.assertTrue(b.write_script("main.gd", "x")["ok"])