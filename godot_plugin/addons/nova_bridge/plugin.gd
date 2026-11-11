@tool
extends EditorPlugin

const PORT := 47821
const TOKEN := "nova-dev-token"

var server: TCPServer
var peers: Array = []

func _enter_tree():
    server = TCPServer.new()
    var err = server.listen(PORT, "127.0.0.1")
    if err != OK:
        push_error("NOVA bridge failed to bind 127.0.0.1:%d" % PORT)
        return
    print("NOVA bridge listening on 127.0.0.1:%d" % PORT)

func _process(_delta):
    if server == null:
        return
    if server.is_connection_available():
        var peer = server.take_connection()
        peers.append(peer)
    for peer in peers.duplicate():
        if peer.get_available_bytes() > 0:
            var data = peer.get_utf8_string(peer.get_available_bytes())
            var response = _handle_http(data)
            peer.put_data(response.to_utf8_buffer())
            peers.erase(peer)
            peer.disconnect_from_host()

func _handle_http(raw: String) -> String:
    # Minimal HTTP/1.1 handler: parse request line + headers + body.
    var lines = raw.split("\r\n")
    if lines.size() == 0:
        return _http(400, {"ok": false, "error": "bad request"})
    var parts = lines[0].split(" ")
    if parts.size() < 2:
        return _http(400, {"ok": false, "error": "bad request line"})
    var method = parts[0]
    var path = parts[1]
    if TOKEN == "nova-dev-token" or TOKEN == "" or TOKEN.length() < 16:
        return _http(403, {"ok": false, "error": "weak or default token configured"})
    # auth check
    var authed = false
    for l in lines:
        if l.to_lower().begins_with("authorization:"):
            var v = l.substr(len("authorization:")).strip()
            if v == "Bearer " + TOKEN:
                authed = true
    if not authed:
        return _http(401, {"ok": false, "error": "unauthorized"})
    # find body
    var body = ""
    var idx = lines.find("")
    if idx != -1 and idx + 1 < lines.size():
        body = "\r\n".join(lines.slice(idx + 1))
    var payload = {}
    if body != "":
        var p = JSON.parse_string(body)
        if typeof(p) == TYPE_DICTIONARY:
            payload = p

    if method == "GET" and path == "/health":
        return _http(200, {"ok": true, "status": "running"})
    if method == "GET" and path == "/project":
        var proj = get_editor_interface().get_edited_scene_root()
        var root_path = ""
        if proj != null:
            root_path = proj.scene_file_path
        return _http(200, {"ok": true, "name": ProjectSettings.get_setting("application/config/name"), "root": root_path})
    if method == "GET" and path == "/scene":
        var scene = get_editor_interface().get_edited_scene_root()
        return _http(200, {"ok": true, "scene": (scene.name if scene != null else "")})
    if method == "GET" and path == "/scene_tree":
        var root = get_editor_interface().get_edited_scene_root()
        var nodes = []
        if root != null:
            _collect(root, nodes)
        return _http(200, {"ok": true, "nodes": nodes})
    if method == "GET" and path == "/selected_node":
        var sel = get_editor_interface().get_selection().get_selected_nodes()
        if sel.size() > 0:
            var n = sel[0]
            return _http(200, {"ok": true, "name": n.name, "type": n.get_class(), "path": str(n.get_path())})
        return _http(200, {"ok": true, "name": "", "type": "", "path": ""})
    if method == "POST" and path == "/script/read":
        var pth = str(payload.get("path", ""))
        if pth == "":
            return _http(400, {"ok": false, "error": "missing path"})
        var f = FileAccess.open(pth, FileAccess.READ)
        if f == null:
            return _http(404, {"ok": false, "error": "not found"})
        var content = f.get_as_text()
        f.close()
        return _http(200, {"ok": true, "content": content})
    if method == "POST" and path == "/script/write":
        var pth2 = str(payload.get("path", ""))
        var content2 = str(payload.get("content", ""))
        if pth2 == "":
            return _http(400, {"ok": false, "error": "missing path"})
        var f2 = FileAccess.open(pth2, FileAccess.WRITE)
        if f2 == null:
            return _http(500, {"ok": false, "error": "cannot open"})
        f2.store_string(content2)
        f2.close()
        return _http(200, {"ok": true})
    if method == "POST" and path == "/run":
        get_editor_interface().play_main_scene()
        return _http(200, {"ok": true})
    if method == "POST" and path == "/stop":
        get_editor_interface().stop_playing_scene()
        return _http(200, {"ok": true})
    return _http(404, {"ok": false, "error": "unknown endpoint"})

func _collect(node, out):
    out.append({"name": node.name, "type": node.get_class(), "path": str(node.get_path())})
    for c in node.get_children():
        _collect(c, out)

func _http(status: int, body: Dictionary) -> String:
    var code = "200 OK"
    if status == 400:
        code = "400 Bad Request"
    elif status == 401:
        code = "401 Unauthorized"
    elif status == 404:
        code = "404 Not Found"
    elif status == 500:
        code = "500 Internal Server Error"
    var json_str = JSON.stringify(body)
    return "HTTP/1.1 %s\r\nContent-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%s" % [code, json_str.length(), json_str]

func _exit_tree():
    if server:
        server.stop()
        server = null