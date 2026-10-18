# Badan Wifi Nasional — Captive Portal Voucher (STB Armbian)

Sistem captive portal + voucher WiFi berjalan di STB (Armbian Ubuntu 24.04).
User connect WiFi → otomatis diarahkan ke halaman portal → masukkan kode voucher →
dapat internet. Mendukung **voucher berdurasi** (30 mnt – 7 hari, otomatis diputus
saat waktu habis) dan **panel admin** web.

## Arsitektur

| Komponen | Fungsi |
|---|---|
| `hostapd` | Access point WiFi (SSID: `BADAN WIFI NASIONAL`) |
| `dnsmasq` | DHCP + DNS untuk client portal |
| `iptables` + `ipset` | Redirect HTTP client belum login ke portal; blokir internet |
| `app/portal.py` | Web server portal (halaman voucher + panel admin) |
| `app/gen_voucher.py` | CLI generate kode voucher |
| `vouchers.json` | Database voucher (tidak di-commit, lihat `.gitignore`) |
| `sessions.json` | Sesi aktif berdurasi (tidak di-commit) |

Alur: HP connect → dapat IP via DHCP → buka web → iptables redirect ke portal
(port 8080) → voucher valid → IP masuk `ipset portal_allow` → internet jalan.
Voucher berdurasi dicatat di `sessions.json`; thread sweeper tiap 30 detik
menendang sesi yang kedaluwarsa.

## Struktur repo

```
app/        portal.py, gen_voucher.py, logo.webp
config/     hostapd.conf, dnsmasq-portal.conf, unmanaged-wlan1.conf, 99-portal.conf
systemd/    portal-net.service, portal-fw.service, portal-web.service
scripts/    portal-fw-restore  (restore ipset + iptables saat boot)
docs/
```

## Instalasi satu perintah (STB baru)

```bash
git clone <repo-url> badan-wifi-nasional
cd badan-wifi-nasional
sudo ./install.sh
```

Kustomisasi via variabel environment:

```bash
SSID="WIFI-KU" AP_IFACE=wlan1 UPLINK_IFACE=wlan0 PORTAL_IP=192.168.50.1 \
  sudo -E ./install.sh
```

| Variabel | Default | Keterangan |
|---|---|---|
| `SSID` | `BADAN WIFI NASIONAL` | Nama WiFi |
| `AP_IFACE` | `wlan1` | Interface access point |
| `UPLINK_IFACE` | `wlan0` | Interface ke internet |
| `PORTAL_IP` | `192.168.50.1` | IP portal |
| `PORTAL_PORT` | `8080` | Port web portal |
| `CHANNEL` | `6` | Channel WiFi |

Script `install.sh` idempoten (aman dijalankan ulang): install paket,
copy file + konfigurasi, setup ipset/iptables, generate password admin,
enable & start semua service, lalu verifikasi.

## Instalasi manual

```bash
# 1. Paket yang dibutuhkan
apt-get update && apt-get install -y hostapd dnsmasq ipset nftables python3

# 2. Copy file aplikasi
mkdir -p /opt/portal
cp app/portal.py app/gen_voucher.py app/logo.webp /opt/portal/
chmod +x /opt/portal/gen_voucher.py

# 3. Copy konfigurasi
cp config/hostapd.conf /etc/hostapd/hostapd.conf
cp config/dnsmasq-portal.conf /etc/dnsmasq.d/portal.conf
cp config/unmanaged-wlan1.conf /etc/NetworkManager/conf.d/unmanaged-wlan1.conf
cp config/99-portal.conf /etc/sysctl.d/99-portal.conf
cp scripts/portal-fw-restore /usr/local/bin/portal-fw-restore
chmod +x /usr/local/bin/portal-fw-restore

# 4. Systemd services
cp systemd/*.service /etc/systemd/system/
systemctl unmask hostapd
systemctl daemon-reload
systemctl enable --now portal-net portal-fw hostapd dnsmasq portal-web

# 5. Buat password admin (disimpan di /opt/portal/admin_pass.txt, JANGAN di-commit)
head -c 12 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 12 > /opt/portal/admin_pass.txt
chmod 600 /opt/portal/admin_pass.txt

# 6. Aturan firewall awal (sekali saja, lalu disimpan)
sysctl -w net.ipv4.ip_forward=1
ipset create portal_allow hash:ip timeout 86400
iptables -t nat -A PREROUTING -i wlan1 -p tcp --dport 80 \
  -m set ! --match-set portal_allow src -j REDIRECT --to-port 8080
iptables -I FORWARD 1 -i wlan1 -m set --match-set portal_allow src -o wlan0 -j ACCEPT
iptables -I INPUT 1 -i wlan1 -p tcp --dport 8080 -j ACCEPT
iptables -t nat -A POSTROUTING -o wlan0 -j MASQUERADE
iptables -P FORWARD DROP
ipset save > /etc/iptables/ipset.rules
iptables-save > /etc/iptables/rules.v4
```

> Catatan: `portal-fw.service` me-restore ipset + iptables tiap boot, dan
> `portal-net.service` memasang IP statis 192.168.50.1/24 di `wlan1`.

## Penggunaan

**Panel admin:** buka `http://192.168.50.1:8080/admin/` dari perangkat yang
terhubung ke WiFi portal. Login dengan user `admin` + password di
`/opt/portal/admin_pass.txt`.

Fitur admin:
- Lihat perangkat terhubung (nama, IP, MAC, sinyal, status)
- Buat voucher: jumlah, maks. pemakaian, **durasi akses** (30 mnt–7 hari),
  masa berlaku voucher
- Hapus voucher, putuskan perangkat, reset semua login
- Tabel sesi aktif berdurasi + sisa waktu

**Generate voucher via CLI (di STB):**
```bash
python3 /opt/portal/gen_voucher.py 10                  # 10 voucher, 1x pakai
python3 /opt/portal/gen_voucher.py 5 --uses 3          # bisa dipakai 3x
python3 /opt/portal/gen_voucher.py 5 --durasi 1jam      # akses 1 jam
python3 /opt/portal/gen_voucher.py 5 --durasi 1jam --hari 7  # + expired 7 hari
```

## Rencana: pembayaran QRIS otomatis (Mayar)

Rencana integrasi: halaman pilih paket durasi → bayar via QRIS (Mayar API,
mode sandbox dulu) → webhook/polling → voucher aktif otomatis.
Belum diimplementasikan.

## Keamanan

- Jangan commit `admin_pass.txt`, `vouchers.json`, `sessions.json`
  (sudah di `.gitignore`).
- Ganti password admin default setelah instalasi.
- Panel admin dilindungi HTTP Basic Auth.
