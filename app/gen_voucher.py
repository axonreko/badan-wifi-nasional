#!/usr/bin/env python3
"""Generate voucher: python3 gen_voucher.py JUMLAH [--uses N] [--hari D] [--durasi DETIK|1jam|3jam|1hari]"""
import json, secrets, sys, datetime, os
F = "/opt/portal/vouchers.json"
ALPH = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # tanpa 0/O, 1/I/L biar jelas
DUR_ALIAS = {"30mnt": 1800, "1jam": 3600, "2jam": 7200, "3jam": 10800,
             "6jam": 21600, "12jam": 43200, "1hari": 86400, "3hari": 259200,
             "7hari": 604800}
def code():
    return "-".join("".join(secrets.choice(ALPH) for _ in range(4)) for _ in range(2))
def load():
    return json.load(open(F)) if os.path.exists(F) else {}
def save(d):
    json.dump(d, open(F, "w"), indent=1)
def opt(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default
n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
uses = int(opt("--uses", 1))
hari = int(opt("--hari", 0))
dur_raw = str(opt("--durasi", 0))
duration = DUR_ALIAS.get(dur_raw.lower(), int(dur_raw) if dur_raw.isdigit() else 0)
d = load()
now = datetime.datetime.now().isoformat(timespec="seconds")
exp = (datetime.datetime.now() + datetime.timedelta(days=hari)).isoformat(timespec="seconds") if hari else None
for _ in range(n):
    c = code()
    while c in d:
        c = code()
    d[c] = {"created": now, "max_uses": uses, "uses": 0, "expires": exp, "duration": duration}
    print(c)
save(d)
print(f"-- {n} voucher tersimpan (max {uses}x pakai"
      + (f", durasi {duration}s" if duration else "")
      + (f", expired {hari} hari" if hari else "") + ")", file=sys.stderr)
