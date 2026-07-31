"""
墨水屏 2.66-B — 仪表盘 + 待办勾选
Pico只与 api.php 通信
"""

import network, socket, uos, utime, json, gc
from epaper_2in66_b import EPD_2in66_B
from dashboard import render

# ═══ 配置 ═══
WIFI_SSID = "YOUR_WIFI_SSID"
WIFI_PASS = "YOUR_WIFI_PASSWORD"
API_HOST  = "YOUR_SERVER_IP"
API_PORT  = 80
API_BASE  = "/api.php"
PORT      = 80
IMG_DIR   = "/images"
STATE_FILE = "/state.json"
INTERVAL  = 300

epd = None
mode = "dashboard"
last_act = 0

# ═══ 网络 ═══
def http_get(path):
    try:
        addr = socket.getaddrinfo(API_HOST, API_PORT)[0][-1]
        s = socket.socket(); s.settimeout(8); s.connect(addr)
        s.send("GET {} HTTP/1.0\r\nHost: {}\r\n\r\n".format(path, API_HOST).encode())
        resp = b""
        while True:
            chunk = s.recv(1024)
            if not chunk: break
            resp += chunk
        s.close()
        _, _, body = resp.partition(b"\r\n\r\n")
        return json.loads(body.decode())
    except Exception as e:
        print("[GET] err:", e)
        return None

def http_post(path, data):
    try:
        body = json.dumps(data).encode()
        addr = socket.getaddrinfo(API_HOST, API_PORT)[0][-1]
        s = socket.socket(); s.settimeout(8); s.connect(addr)
        s.send("POST {} HTTP/1.0\r\nHost: {}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n".format(path, API_HOST, len(body)).encode())
        s.send(body)
        resp = b""
        while True:
            chunk = s.recv(1024)
            if not chunk: break
            resp += chunk
        s.close()
        _, _, bd = resp.partition(b"\r\n\r\n")
        return json.loads(bd.decode())
    except Exception as e:
        print("[POST] err:", e)
        return None

# ═══ 图片 ═══
def ensure_dir():
    try: uos.stat(IMG_DIR)
    except OSError: uos.mkdir(IMG_DIR)

def list_images():
    try: return sorted([f for f in uos.listdir(IMG_DIR) if f.endswith(".bin")])
    except OSError: return []

def show_image(idx):
    imgs = list_images()
    if not imgs: epd.clear(); return
    idx = idx % len(imgs)
    try:
        with open(IMG_DIR + "/" + imgs[idx], "rb") as f:
            data = f.read(5624 * 2)
        epd.load_raw(data); epd.show_raw()
        with open(STATE_FILE, "w") as f: json.dump({"index": idx, "mode": "photos"}, f)
    except Exception as e: print("[Img] err:", e)

def show_next():
    s = {}
    try:
        with open(STATE_FILE) as f: s = json.load(f)
    except: pass
    idx = (s.get("index", -1) + 1) % max(len(list_images()), 1)
    show_image(idx)

# ═══ 仪表盘 ═══
def dash_update():
    data = http_get(API_BASE + "?action=all")
    if data is None:
        data = {"ds_balance": 0, "ds_total": 0, "todos": [], "error": "offline"}
    render(epd, data)

# ═══ HTTP ═══
def respond(code, ct, body=""):
    b = body.encode() if isinstance(body, str) else body
    return (b"HTTP/1.1 " + code.encode() +
            b"\r\nContent-Type: " + ct.encode() +
            b"\r\nContent-Length: " + str(len(b)).encode() +
            b"\r\nConnection: close\r\n\r\n" + b)

def parse_request(raw):
    try:
        hdr, _, bd = raw.partition(b"\r\n\r\n")
        parts = hdr.split(b"\r\n")[0].split(b" ")
        if len(parts) < 2: return None, "", b""
        return parts[0].decode(), parts[1].decode(), bd
    except: return None, "", b""

HTML = """<!DOCTYPE html>
<html lang=zh>
<head>
<meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1,user-scalable=no">
<title>仪表盘</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font:16px/1.5 system-ui;background:#111;color:#eee;max-width:480px;margin:0 auto;padding:16px}
h1{font-size:18px;margin-bottom:6px}
.meta{font-size:13px;color:#888;margin-bottom:10px}
h3{font-size:14px;color:#ccc;margin:12px 0 6px}
input[type=text]{width:calc(100% - 54px);padding:8px;background:#1a1a1a;color:#fff;border:1px solid #333;border-radius:4px;font-size:15px;margin-right:8px}
.btn{display:block;width:100%;padding:10px;margin:6px 0;background:#2563eb;color:#fff;border:none;border-radius:5px;font-size:15px;cursor:pointer}
.btn:active{background:#1d4ed8}
.btn-sm{display:inline-block;width:auto;padding:5px 12px;font-size:13px;margin:2px;border-radius:4px}
.btn-r{background:#dc2626}
.btn-g{background:#16a34a}
.btn-o{background:#6b7280}
#st{font-size:13px;color:#888;margin:6px 0;min-height:18px}
hr{border:none;border-top:1px solid #333;margin:12px 0}
.todo-item{display:flex;align-items:center;padding:6px 0;border-bottom:1px solid #1a1a1a}
.todo-item .done{text-decoration:line-through;color:#555}
.todo-text{flex:1;word-break:break-all;font-size:14px;padding-right:8px}
.add-row{display:flex;align-items:center}
</style>
</head>
<body>
<h1>仪表盘 2.66"</h1>
<div class=meta id=meta>loading...</div>

<h3>待办</h3>
<div id=list></div>

<div class=add-row>
  <input type=text id=newtodo placeholder="新事项...">
  <button class="btn-sm btn-g" onclick=addTodo() style="width:48px">+</button>
</div>

<div style="margin:8px 0">
  <button class="btn-sm btn-o" onclick=clearDone()>清除已完成</button>
  <button class="btn btn-sm" onclick=refresh()>刷新</button>
  <button class="btn btn-sm btn-r" onclick=mode('photos')>相框</button>
</div>
<div id=st></div>

<hr>
<input type=file id=f accept="image/*" style="color:#fff;margin:6px 0" onchange=up(this)>
<button class="btn btn-sm" onclick=mode('dashboard')">仪表盘</button>

<script>
var TODOS=[];
function renderList(){
  var h='';
  if(TODOS.length===0){h='<div style="color:#555;padding:8px 0">(empty)</div>';}
  TODOS.forEach(function(t,i){
    var d=t.d||false;
    var td=d?' class="todo-item done"':' class="todo-item"';
    h+='<div'+td+'><span class="todo-text">'+esc(t.t||'')+'</span>';
    h+='<button class="btn-sm '+(d?'btn-o':'btn-g')+'" onclick=toggle('+i+')>'+(d?'X':'V')+'</button>';
    h+='</div>';
  });
  document.getElementById('list').innerHTML=h;
}
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;');}

async function loadData(){
  try{
    var r=await fetch('/data');
    var d=await r.json();
    TODOS=(d.todos||[]).map(function(t){
      if(typeof t==='string')return {t:t,d:false};
      return {t:t.t||'',d:t.d||false};
    });
    document.getElementById('meta').textContent='DS Y'+d.ds_balance+'/'+d.ds_total+' | '+TODOS.length+' items';
    renderList();
  }catch(e){document.getElementById('meta').textContent='error: '+e}
}

async function addTodo(){
  var inp=document.getElementById('newtodo');
  var t=inp.value.trim();if(!t)return;
  TODOS.push({t:t,d:false});await saveAll();inp.value='';
}

async function toggle(i){
  TODOS[i].d=!TODOS[i].d;await saveAll();
}

async function saveAll(){
  try{
    var r=await fetch('/save2',{method:'POST',body:JSON.stringify({items:TODOS})});
    document.getElementById('st').textContent=await r.text();renderList();
  }catch(e){document.getElementById('st').textContent='err: '+e}
}

async function clearDone(){
  TODOS=TODOS.filter(function(t){return !t.d});await saveAll();
}

async function refresh(){
  var r=await fetch('/refresh',{method:'POST'});
  document.getElementById('st').textContent=await r.text();
}
async function mode(m){
  var r=await fetch('/mode/'+m,{method:'POST'});
  document.getElementById('st').textContent=await r.text();
}
async function up(i){
  var f=i.files[0];if(!f)return;
  document.getElementById('st').textContent='uploading...';
  var r=await fetch('/upload',{method:'POST',body:await f.arrayBuffer()});
  document.getElementById('st').textContent=await r.text();
}
loadData();
</script>
</body>
</html>"""

# ═══ 主入口 ═══
def main():
    global epd, mode, last_act
    print("="*30); print("仪表盘 2.66\""); print("="*30)

    epd = EPD_2in66_B(); epd.clear()

    wlan = network.WLAN(network.STA_IF); wlan.active(True)
    if not wlan.isconnected():
        print("[WiFi] {}...".format(WIFI_SSID))
        wlan.connect(WIFI_SSID, WIFI_PASS)
        for _ in range(20):
            if wlan.isconnected(): break
            utime.sleep(1)
    if not wlan.isconnected():
        epd.imageblack.fill(1); epd.imagered.fill(1)
        epd.imageblack.text("WiFi err", 2, 2, 0); epd.display(); return
    ip = wlan.ifconfig()[0]; print("[WiFi] {}".format(ip))

    try:
        with open(STATE_FILE) as f: s = json.load(f); mode = s.get("mode", "dashboard")
    except: mode = "dashboard"

    if mode == "dashboard": dash_update()
    else:
        imgs = list_images()
        if imgs: show_image(0)
        else: dash_update()
    last_act = utime.time()

    ensure_dir()
    addr = socket.getaddrinfo("0.0.0.0", PORT)[0][-1]
    srv = socket.socket(); srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(addr); srv.listen(2); srv.settimeout(3)
    print("[Ready] http://{}:{}".format(ip, PORT))

    while True:
        now = utime.time()
        if mode == "dashboard" and now - last_act > INTERVAL: dash_update(); last_act = now
        elif mode == "photos" and now - last_act > INTERVAL:
            if list_images(): show_next()
            last_act = now
        try: cl, _ = srv.accept()
        except OSError: continue

        try:
            cl.settimeout(5); raw = b""
            while b"\r\n\r\n" not in raw:
                chunk = cl.recv(1024)
                if not chunk: break
                raw += chunk
            if not raw: cl.close(); continue
            method, path, body = parse_request(raw)

            clen = 0
            for line in raw.split(b"\r\n"):
                if line.lower().startswith(b"content-length:"):
                    try: clen = int(line.split(b":")[1].strip())
                    except: pass
                    break
            if clen > 0 and len(body) < clen:
                while len(body) < clen:
                    chunk = cl.recv(min(clen - len(body), 2048))
                    if not chunk: break
                    body += chunk
            if method is None: cl.close(); continue

            # ─── 路由 ───
            if method == "GET" and path in ("/", "/index.html"):
                cl.sendall(respond("200 OK", "text/html; charset=utf-8", HTML))

            elif method == "GET" and path == "/data":
                d = http_get(API_BASE + "?action=all")
                if d: cl.sendall(respond("200 OK", "application/json", json.dumps(d)))
                else: cl.sendall(respond("502", "text/plain", "API unreachable"))

            elif method == "POST" and path == "/save2":
                # 新格式: {items:[{t,d},...]}
                try:
                    req = json.loads(body.decode())
                    items = req.get("items", [])
                    http_post(API_BASE + "?action=todos", {"todos": items})
                    cl.sendall(respond("200 OK", "text/plain", "Saved"))
                    dash_update(); last_act = now
                except Exception as e:
                    cl.sendall(respond("400", "text/plain", str(e)))

            elif method == "POST" and path == "/refresh":
                dash_update(); last_act = now
                cl.sendall(respond("200 OK", "text/plain", "Refreshed"))

            elif method == "POST" and path.startswith("/mode/"):
                nm = path.split("/")[-1]
                if nm in ("dashboard", "photos"):
                    mode = nm
                    try:
                        with open(STATE_FILE, "w") as f: json.dump({"mode": mode}, f)
                    except: pass
                    if mode == "dashboard": dash_update()
                    else:
                        imgs = list_images()
                        if imgs: show_image(0)
                    last_act = now
                    cl.sendall(respond("200 OK", "text/plain", "Mode: {}".format(mode)))
                else: cl.sendall(respond("400", "text/plain", "Bad"))

            elif method == "POST" and path == "/upload":
                if len(body) == 5624 * 2:
                    try:
                        ensure_dir(); n = len(list_images())
                        with open("{}/{:04d}.bin".format(IMG_DIR, n), "wb") as f: f.write(body)
                        gc.collect()
                        if mode == "photos": show_image(n); last_act = now
                        cl.sendall(respond("200 OK", "text/plain", "OK ({})".format(n + 1)))
                    except Exception as e: cl.sendall(respond("500", "text/plain", str(e)))
                else: cl.sendall(respond("400", "text/plain", "Size: {}".format(len(body))))
            else: cl.sendall(respond("404", "text/plain", "404"))
        except Exception as e: print("[HTTP] err:", e)
        finally:
            try: cl.close()
            except: pass

main()
