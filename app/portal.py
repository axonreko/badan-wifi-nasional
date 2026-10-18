#!/usr/bin/env python3
"""Captive portal Badan Wifi Nasional: voucher + panel admin."""
import subprocess, json, os, datetime, re, base64, secrets, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

BIND = "192.168.50.1"
PORT = 8080
VF = "/opt/portal/vouchers.json"
SESF = "/opt/portal/sessions.json"
PASSF = "/opt/portal/admin_pass.txt"

# preset durasi akses (detik): label -> detik. 0 = tanpa batas waktu
DURATIONS = [
    ("Tanpa batas waktu", 0),
    ("30 menit", 1800),
    ("1 jam", 3600),
    ("2 jam", 7200),
    ("3 jam", 10800),
    ("6 jam", 21600),
    ("12 jam", 43200),
    ("1 hari", 86400),
    ("3 hari", 259200),
    ("7 hari", 604800),
]
DUR_LABEL = {s: l for l, s in DURATIONS}

# Logo: file /opt/portal/logo.webp diserve via route /logo.webp
LOGO_IMG = '<img class="logo-img" src="/logo.webp" alt="Badan Wifi Nasional">'
LOGO_FILE = "/opt/portal/logo.webp"

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
background:#f1f5f9;color:#0f172a;min-height:100vh;display:flex;align-items:center;
justify-content:center;padding:24px}
body.admin{align-items:flex-start}
.card{background:#fff;border-radius:12px;padding:40px 36px;width:100%;max-width:380px;
box-shadow:0 1px 3px rgba(15,23,42,.08),0 4px 12px rgba(15,23,42,.05)}
.card.wide{max-width:860px}
.brand{width:46px;height:46px;border-radius:11px;background:#1e40af;color:#fff;
display:flex;align-items:center;justify-content:center;font-weight:700;font-size:19px;
letter-spacing:.5px;margin-bottom:22px}
.logo{width:118px;height:118px;margin:0 auto 22px;display:block}
.logo.sm{width:44px;height:44px;margin:0}
.logo.xs{width:36px;height:36px;margin:0;flex:none}
.logo-img{width:118px;height:118px;margin:0 auto 22px;display:block;border-radius:50%;
box-shadow:0 4px 14px rgba(15,23,42,.18)}
.logo-img.sm{width:64px;height:64px;margin:0 auto 18px}
.logo-img.xs{width:36px;height:36px;margin:0;flex:none;border-radius:50%}
.adm-head{display:flex;align-items:center;gap:12px}
.adm-head h1{margin:0}
h1{font-size:20px;font-weight:650;margin-bottom:6px;letter-spacing:-.2px}
h2{font-size:15px;font-weight:650;margin:28px 0 12px;padding-bottom:8px;border-bottom:1px solid #e2e8f0}
p.sub{color:#64748b;font-size:14px;line-height:1.55;margin-bottom:26px}
label{display:block;font-size:13px;font-weight:600;margin-bottom:8px;color:#334155}
input.code{width:100%;padding:13px 14px;font-size:17px;border:1px solid #cbd5e1;
border-radius:8px;letter-spacing:3px;text-transform:uppercase;text-align:center;
font-family:ui-monospace,SFMono-Regular,Menlo,monospace;color:#0f172a}
input.code:focus{outline:none;border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,.13)}
input.txt,select.txt{padding:10px 12px;font-size:14px;border:1px solid #cbd5e1;border-radius:8px;width:100%}
button{width:100%;margin-top:16px;padding:13px;font-size:15px;font-weight:600;color:#fff;
background:#1e40af;border:none;border-radius:8px;cursor:pointer}
button:hover{background:#1e3a8a}
.btn-sm{width:auto;margin:0;padding:7px 14px;font-size:13px;border-radius:7px;display:inline-block;text-decoration:none;color:#fff}
.btn-red{background:#dc2626}.btn-red:hover{background:#b91c1c}
.btn-gray{background:#64748b}.btn-gray:hover{background:#475569}
.err{background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;padding:11px 14px;
border-radius:8px;font-size:13px;margin-bottom:18px;line-height:1.5}
.ok{background:#f0fdf4;color:#15803d;border:1px solid #bbf7d0;padding:11px 14px;
border-radius:8px;font-size:13px;margin-bottom:18px}
.ok-icon{width:52px;height:52px;border-radius:50%;background:#dcfce7;color:#15803d;
display:flex;align-items:center;justify-content:center;font-size:26px;margin-bottom:20px}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th{text-align:left;padding:10px 12px;color:#64748b;font-weight:600;font-size:12px;
text-transform:uppercase;letter-spacing:.4px;border-bottom:1px solid #e2e8f0}
td{padding:11px 12px;border-bottom:1px solid #f1f5f9;vertical-align:middle}
tr:last-child td{border-bottom:none}
.mono{font-family:ui-monospace,Menlo,monospace;font-size:12.5px}
.badge{display:inline-block;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:600}
.b-green{background:#dcfce7;color:#15803d}.b-amber{background:#fef3c7;color:#b45309}
.b-gray{background:#f1f5f9;color:#64748b}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.foot{margin-top:26px;font-size:12px;color:#94a3b8;text-align:center;line-height:1.6}
.meta{margin-top:18px;padding-top:18px;border-top:1px solid #f1f5f9;font-size:12.5px;color:#64748b}
.meta b{color:#334155}
.topbar{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;gap:12px;flex-wrap:wrap}
.topbar h1{margin:0}
@media(max-width:640px){.grid2{grid-template-columns:1fr}.card{padding:28px 22px}}
"""

def page(title, body, wide=False, admin=False):
    cls = "card wide" if wide else "card"
    ab = ' class="admin"' if admin else ""
    return ("<!DOCTYPE html><html lang=\"id\"><head><meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
            "<title>" + title + "</title><style>" + CSS + "</style></head>\n"
            "<body" + ab + "><div class=\"" + cls + "\">" + body +
            "\n<div class=\"foot\">Badan Wifi Nasional &middot; Akses internet nirkabel</div>\n"
            "</div></body></html>")

def load():
    return json.load(open(VF)) if os.path.exists(VF) else {}

def save(d):
    json.dump(d, open(VF, "w"), indent=1)

def load_ses():
    try:
        return json.load(open(SESF)) if os.path.exists(SESF) else {}
    except Exception:
        return {}

def save_ses(s):
    json.dump(s, open(SESF, "w"), indent=1)

def kick_ip(ip):
    """Putuskan akses 1 IP: hapus dari ipset + sesi."""
    subprocess.run(["ipset", "del", "portal_allow", ip], capture_output=True)
    s = load_ses()
    if ip in s:
        del s[ip]
        save_ses(s)

def sweep():
    """Hapus sesi yang waktunya habis. Jalan tiap 30 detik di thread terpisah."""
    while True:
        try:
            now = datetime.datetime.now().timestamp()
            s = load_ses()
            changed = False
            for ip, ses in list(s.items()):
                if ses.get("end") and now >= ses["end"]:
                    subprocess.run(["ipset", "del", "portal_allow", ip],
                                   capture_output=True)
                    del s[ip]
                    changed = True
            if changed:
                save_ses(s)
        except Exception:
            pass
        time.sleep(30)

def fmt_sisa(end_ts):
    """Format sisa waktu jadi teks Indonesia, mis. '2 jam 15 mnt'."""
    sisa = int(end_ts - datetime.datetime.now().timestamp())
    if sisa <= 0:
        return "habis"
    hari, sisa = divmod(sisa, 86400)
    jam, sisa = divmod(sisa, 3600)
    mnt, _ = divmod(sisa, 60)
    parts = []
    if hari:
        parts.append(str(hari) + " hari")
    if jam:
        parts.append(str(jam) + " jam")
    if mnt and not hari:
        parts.append(str(mnt) + " mnt")
    return " ".join(parts) if parts else "< 1 mnt"

def cek_voucher(norm):
    d = load()
    hit = {re.sub(r"[^A-Z0-9]", "", k.upper()): k for k in d}
    code = hit.get(norm)
    v = d.get(code) if code else None
    if not v:
        return None, "Kode voucher tidak dikenali. Periksa kembali penulisan kode.", None
    if v["uses"] >= v["max_uses"]:
        return None, "Voucher ini sudah habis digunakan.", None
    if v["expires"] and datetime.datetime.now().isoformat() > v["expires"]:
        return None, "Voucher ini sudah kedaluwarsa.", None
    return d, None, code

def form(err=""):
    e = "<div class=\"err\">" + err + "</div>" if err else ""
    return page("Badan Wifi Nasional - Masukkan Voucher",
        LOGO_IMG + "<h1 style=\"text-align:center\">Selamat datang</h1>\n"
        "<p class=\"sub\" style=\"text-align:center\">Masukkan kode voucher untuk terhubung ke internet.</p>" + e + "\n"
        "<form method=\"POST\" action=\"/connect\">\n"
        "<label for=\"v\">Kode voucher</label>\n"
        "<input class=\"code\" id=\"v\" name=\"voucher\" placeholder=\"XXXX-XXXX\"\n"
        "maxlength=\"12\" autocomplete=\"off\" autofocus required>\n"
        "<button type=\"submit\">Hubungkan</button></form>")

def success(code, dur_sec=0):
    info = ""
    if dur_sec > 0:
        info = ("<div class=\"meta\">Masa aktif: <b>" + DUR_LABEL.get(dur_sec, "") +
                "</b> sejak sekarang.</div>")
    return page("Badan Wifi Nasional - Terhubung",
        LOGO_IMG.replace('logo-img', 'logo-img sm') +
        "<div class=\"ok-icon\">&#10003;</div><h1>Terhubung</h1>\n"
        "<p class=\"sub\">Perangkat ini sekarang memiliki akses internet.</p>\n"
        "<div class=\"meta\">Voucher <b>" + code + "</b> telah digunakan.</div>" + info)

def admin_pass():
    try:
        return open(PASSF).read().strip()
    except Exception:
        return ""

def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=8).stdout
    except Exception:
        return ""

def leases():
    out = []
    for line in sh(["cat", "/var/lib/misc/dnsmasq.leases"]).splitlines():
        p = line.split()
        if len(p) >= 4:
            out.append({"mac": p[1], "ip": p[2], "name": p[3]})
    return out

def allowed_ips():
    return set(re.findall(r"^(\d+\.\d+\.\d+\.\d+)", sh(["ipset", "list", "portal_allow"]), re.M))

def signals():
    sig = {}
    cur = None
    for line in sh(["iw", "dev", "wlan1", "station", "dump"]).splitlines():
        m = re.match(r"Station ([0-9a-f:]+)", line)
        if m:
            cur = m.group(1).lower()
        m = re.search(r"signal:\s*(-?\d+)", line)
        if m and cur:
            sig[cur] = m.group(1) + " dBm"
    return sig

def admin_dashboard(msg=""):
    allowed = allowed_ips()
    sig = signals()
    devs = leases()
    rows = ""
    for dvc in devs:
        on = dvc["ip"] in allowed
        badge = ('<span class="badge b-green">Online</span>' if on
                 else '<span class="badge b-amber">Di portal</span>')
        if on:
            kick = ("<a class=\"btn-sm btn-red\" href=\"/admin/kick?ip=" + dvc["ip"] +
                    "\">Putuskan</a>")
        else:
            kick = "<span style=\"color:#94a3b8\">-</span>"
        rows += ("<tr><td><b>" + dvc["name"] + "</b><br>"
                 "<span class=\"mono\" style=\"color:#64748b\">" + dvc["ip"] + "</span></td>"
                 "<td class=\"mono\">" + dvc["mac"] + "</td>"
                 "<td>" + sig.get(dvc["mac"].lower(), "-") + "</td>"
                 "<td>" + badge + "</td><td>" + kick + "</td></tr>")
    if not rows:
        rows = ("<tr><td colspan=\"5\" style=\"text-align:center;color:#94a3b8\">"
                "Belum ada perangkat terhubung</td></tr>")
    vrows = ""
    for code, v in sorted(load().items()):
        left = v["max_uses"] - v["uses"]
        st = ('<span class="badge b-gray">Habis</span>' if left <= 0
              else '<span class="badge b-green">Sisa ' + str(left) + "x</span>")
        exp = v["expires"][:10] if v["expires"] else "-"
        dur_txt = DUR_LABEL.get(int(v.get("duration", 0) or 0), "-")
        vrows += ("<tr><td class=\"mono\"><b>" + code + "</b></td>"
                  "<td>" + str(v["uses"]) + "/" + str(v["max_uses"]) + "</td>"
                  "<td>" + dur_txt + "</td>"
                  "<td>" + exp + "</td><td>" + st + "</td>"
                  "<td><a class=\"btn-sm btn-gray\" href=\"/admin/delv?code=" + code +
                  "\">Hapus</a></td></tr>")
    if not vrows:
        vrows = ("<tr><td colspan=\"6\" style=\"text-align:center;color:#94a3b8\">"
                 "Belum ada voucher</td></tr>")
    # --- tabel sesi aktif (berdurasi) ---
    ses = load_ses()
    srows = ""
    for ip, s in sorted(ses.items(), key=lambda kv: kv[1].get("end", 0)):
        end = s.get("end")
        if not end:
            continue
        sisa = fmt_sisa(end)
        nama = next((dvc["name"] for dvc in devs if dvc["ip"] == ip), "-")
        srows += ("<tr><td><b>" + nama + "</b><br>"
                  "<span class=\"mono\" style=\"color:#64748b\">" + ip + "</span></td>"
                  "<td class=\"mono\">" + s.get("code", "-") + "</td>"
                  "<td><span class=\"badge b-green\">" + sisa + " lagi</span></td>"
                  "<td><a class=\"btn-sm btn-red\" href=\"/admin/kick?ip=" + ip +
                  "\">Putuskan</a></td></tr>")
    ses_block = ""
    if srows:
        ses_block = ("<h2>Sesi aktif berdurasi (" + str(len([1 for s in ses.values() if s.get("end")])) +
                     ")</h2>\n<table><tr><th>Perangkat</th><th>Voucher</th>"
                     "<th>Sisa waktu</th><th>Aksi</th></tr>" + srows + "</table>\n")
    # --- dropdown durasi ---
    dur_opts = "".join(
        "<option value=\"" + str(s) + "\">" + l + "</option>" for l, s in DURATIONS)
    m = "<div class=\"ok\">" + msg + "</div>" if msg else ""
    return page("Admin - Badan Wifi Nasional",
        "<div class=\"topbar\"><div class=\"adm-head\">" + LOGO_IMG.replace('logo-img', 'logo-img xs') +
        "<h1>Panel Admin</h1></div>"
        "<a class=\"btn-sm btn-gray\" href=\"/admin/reset\" "
        "onclick=\"return confirm('Reset semua login? Semua perangkat harus login ulang.')\">"
        "Reset semua login</a></div>\n"
        "<p class=\"sub\">Kelola voucher dan perangkat yang terhubung.</p>" + m +
        "<h2>Perangkat terhubung (" + str(len(devs)) + ")</h2>\n"
        "<table><tr><th>Perangkat</th><th>MAC</th><th>Sinyal</th><th>Status</th><th>Aksi</th></tr>"
        + rows + "</table>\n"
        + ses_block +
        "<h2>Buat voucher baru</h2>\n"
        "<form method=\"POST\" action=\"/admin/gen\"><div class=\"grid2\">\n"
        "<div><label>Jumlah</label>"
        "<input class=\"txt\" type=\"number\" name=\"n\" value=\"5\" min=\"1\" max=\"100\"></div>\n"
        "<div><label>Maks. dipakai</label>"
        "<input class=\"txt\" type=\"number\" name=\"uses\" value=\"1\" min=\"1\" max=\"50\"></div>\n"
        "<div><label>Durasi akses sekali pakai</label>"
        "<select class=\"txt\" name=\"duration\">" + dur_opts + "</select></div>\n"
        "<div><label>Voucher berlaku (hari, 0 = selamanya)</label>"
        "<input class=\"txt\" type=\"number\" name=\"hari\" value=\"0\" min=\"0\" max=\"365\"></div>\n"
        "</div><button type=\"submit\">Buat voucher</button></form>\n"
        "<h2>Daftar voucher</h2>\n"
        "<table><tr><th>Kode</th><th>Terpakai</th><th>Durasi</th><th>Expired</th><th>Status</th><th>Aksi</th></tr>"
        + vrows + "</table>\n",
        wide=True, admin=True)

ALPH = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

def gen_code():
    return "-".join("".join(secrets.choice(ALPH) for _ in range(4)) for _ in range(2))

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, html, code=200):
        b = html.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _need_auth(self):
        auth = self.headers.get("Authorization", "")
        want = "Basic " + base64.b64encode(("admin:" + admin_pass()).encode()).decode()
        if not admin_pass() or auth != want:
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Admin Badan Wifi Nasional"')
            self.send_header("Content-Length", "0")
            self.end_headers()
            return True
        return False

    def _redir(self, loc):
        self.send_response(303)
        self.send_header("Location", loc)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/logo.webp":
            try:
                data = open(LOGO_FILE, "rb").read()
                self.send_response(200)
                self.send_header("Content-Type", "image/webp")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "max-age=86400")
                self.end_headers()
                self.wfile.write(data)
            except Exception:
                self.send_response(404)
                self.end_headers()
            return
        if u.path.startswith("/admin"):
            if self._need_auth():
                return
            q = parse_qs(u.query)
            if u.path == "/admin/kick":
                kick_ip(q.get("ip", [""])[0])
                self._redir("/admin/?msg=Perangkat+diputus")
            elif u.path == "/admin/reset":
                subprocess.run(["ipset", "flush", "portal_allow"], capture_output=True)
                save_ses({})
                self._redir("/admin/?msg=Semua+login+direset")
            elif u.path == "/admin/delv":
                d = load()
                d.pop(q.get("code", [""])[0], None)
                save(d)
                self._redir("/admin/?msg=Voucher+dihapus")
            else:
                msg = q.get("msg", [""])[0].replace("+", " ")
                self._send(admin_dashboard(msg))
            return
        self._send(form())

    def do_POST(self):
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length", 0))
        q = parse_qs(self.rfile.read(n).decode())
        if u.path == "/admin/gen":
            if self._need_auth():
                return
            try:
                cnt = max(1, min(100, int(q.get("n", ["5"])[0] or 5)))
            except ValueError:
                cnt = 5
            try:
                uses = max(1, min(50, int(q.get("uses", ["1"])[0] or 1)))
            except ValueError:
                uses = 1
            try:
                hari = max(0, min(365, int(q.get("hari", ["0"])[0] or 0)))
            except ValueError:
                hari = 0
            try:
                duration = int(q.get("duration", ["0"])[0] or 0)
            except ValueError:
                duration = 0
            if duration not in DUR_LABEL:
                duration = 0
            d = load()
            now = datetime.datetime.now().isoformat(timespec="seconds")
            exp = ((datetime.datetime.now() + datetime.timedelta(days=hari))
                   .isoformat(timespec="seconds") if hari else None)
            for _ in range(cnt):
                c = gen_code()
                while c in d:
                    c = gen_code()
                d[c] = {"created": now, "max_uses": uses, "uses": 0,
                        "expires": exp, "duration": duration}
            save(d)
            self._redir("/admin/?msg=" + str(cnt) + "+voucher+baru+dibuat")
            return
        if u.path.startswith("/connect"):
            raw = q.get("voucher", [""])[0] or ""
            norm = re.sub(r"[^A-Z0-9]", "", raw.strip().upper())
            d, err, code = cek_voucher(norm)
            if err:
                self._send(form(err))
                return
            v = d[code]
            dur = int(v.get("duration", 0) or 0)
            v["uses"] += 1
            v["last_used"] = datetime.datetime.now().isoformat(timespec="seconds")
            v["last_ip"] = self.client_address[0]
            save(d)
            ip = self.client_address[0]
            if dur > 0:
                # sesi berdurasi: catat akhir masa aktif + timeout ipset mengikuti
                end = datetime.datetime.now().timestamp() + dur
                s = load_ses()
                s[ip] = {"code": code, "start": datetime.datetime.now().isoformat(timespec="seconds"),
                         "end": end, "duration": dur}
                save_ses(s)
                subprocess.run(["ipset", "add", "portal_allow", ip,
                                "timeout", str(dur)], capture_output=True)
            else:
                subprocess.run(["ipset", "add", "portal_allow", ip], capture_output=True)
            self._send(success(code, dur))
            return
        self.send_response(404)
        self.end_headers()

# bersihkan sesi kadaluarsa tiap 30 detik (background)
threading.Thread(target=sweep, daemon=True).start()

HTTPServer((BIND, PORT), H).serve_forever()
