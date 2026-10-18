#!/usr/bin/env bash
#
# install.sh — Instalasi satu perintah Captive Portal "Badan Wifi Nasional"
#
# Cara pakai di STB baru (Armbian/Debian/Ubuntu):
#   git clone <repo-url> badan-wifi-nasional
#   cd badan-wifi-nasional
#   sudo ./install.sh
#
# Variabel opsional (contoh):
#   SSID="WIFI-KU" AP_IFACE=wlan1 UPLINK_IFACE=wlan0 PORTAL_IP=192.168.50.1 sudo -E ./install.sh
#
set -e

# ---------- konfigurasi ----------
SSID="${SSID:-BADAN WIFI NASIONAL}"
AP_IFACE="${AP_IFACE:-wlan1}"          # interface jadi access point
UPLINK_IFACE="${UPLINK_IFACE:-wlan0}"   # interface ke internet
PORTAL_IP="${PORTAL_IP:-192.168.50.1}" # IP portal di jaringan AP
PORTAL_PORT="${PORTAL_PORT:-8080}"
NETMASK="24"
DHCP_FROM="${DHCP_FROM:-192.168.50.10}"
DHCP_TO="${DHCP_TO:-192.168.50.100}"
CHANNEL="${CHANNEL:-6}"

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

# ---------- cek root ----------
if [ "$(id -u)" -ne 0 ]; then
  echo "Jalankan sebagai root: sudo ./install.sh" >&2
  exit 1
fi

echo "== 1/8 Paket sistem =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq hostapd dnsmasq ipset nftables python3 iptables

echo "== 2/8 File aplikasi -> /opt/portal =="
mkdir -p /opt/portal
cp "$REPO_DIR/app/portal.py" "$REPO_DIR/app/gen_voucher.py" /opt/portal/
if [ -f "$REPO_DIR/app/logo.webp.b64" ]; then
  base64 -d "$REPO_DIR/app/logo.webp.b64" > /opt/portal/logo.webp
elif [ -f "$REPO_DIR/app/logo.webp" ]; then
  cp "$REPO_DIR/app/logo.webp" /opt/portal/
fi
chmod +x /opt/portal/gen_voucher.py

echo "== 3/8 Konfigurasi =="
# hostapd (SSID dari variabel)
sed "s/^ssid=.*/ssid=$SSID/" "$REPO_DIR/config/hostapd.conf" \
  | sed "s/^interface=.*/interface=$AP_IFACE/" \
  | sed "s/^channel=.*/channel=$CHANNEL/" > /etc/hostapd/hostapd.conf
# dnsmasq
sed -e "s/^interface=.*/interface=$AP_IFACE/" \
    -e "s|^dhcp-range=.*|dhcp-range=$DHCP_FROM,$DHCP_TO,255.255.255.0,12h|" \
    -e "s/^dhcp-option=3,.*/dhcp-option=3,$PORTAL_IP/" \
    -e "s/^dhcp-option=6,.*/dhcp-option=6,$PORTAL_IP/" \
    "$REPO_DIR/config/dnsmasq-portal.conf" > /etc/dnsmasq.d/portal.conf
# NetworkManager: jangan pegang interface AP
sed "s/wlan1/$AP_IFACE/g" "$REPO_DIR/config/unmanaged-wlan1.conf" \
  > /etc/NetworkManager/conf.d/unmanaged-wlan1.conf
nmcli device set "$AP_IFACE" managed no 2>/dev/null || true
# IP forwarding
cp "$REPO_DIR/config/99-portal.conf" /etc/sysctl.d/99-portal.conf
sysctl -w net.ipv4.ip_forward=1 >/dev/null

echo "== 4/8 IP statis $PORTAL_IP di $AP_IFACE =="
# service portal-net dengan IP + interface dari variabel
sed -e "s|192.168.50.1/24|$PORTAL_IP/$NETMASK|g" -e "s/wlan1/$AP_IFACE/g" \
  "$REPO_DIR/systemd/portal-net.service" > /etc/systemd/system/portal-net.service
# portal-web dengan bind IP + port dari variabel
sed -e "s/^BIND = .*/BIND = \"$PORTAL_IP\"/" -e "s/^PORT = .*/PORT = $PORTAL_PORT/" \
  /opt/portal/portal.py > /opt/portal/portal.py.tmp && mv /opt/portal/portal.py.tmp /opt/portal/portal.py
cp "$REPO_DIR/systemd/portal-fw.service" "$REPO_DIR/systemd/portal-web.service" \
  /etc/systemd/system/
cp "$REPO_DIR/scripts/portal-fw-restore" /usr/local/bin/portal-fw-restore
chmod +x /usr/local/bin/portal-fw-restore

echo "== 5/8 Firewall (ipset + iptables) =="
ipset create portal_allow hash:ip timeout 86400 2>/dev/null || true
iptables -t nat -C PREROUTING -i "$AP_IFACE" -p tcp --dport 80 \
  -m set ! --match-set portal_allow src -j REDIRECT --to-port "$PORTAL_PORT" 2>/dev/null \
  || iptables -t nat -A PREROUTING -i "$AP_IFACE" -p tcp --dport 80 \
  -m set ! --match-set portal_allow src -j REDIRECT --to-port "$PORTAL_PORT"
iptables -C FORWARD -i "$AP_IFACE" -m set --match-set portal_allow src \
  -o "$UPLINK_IFACE" -j ACCEPT 2>/dev/null \
  || iptables -I FORWARD 1 -i "$AP_IFACE" -m set --match-set portal_allow src \
  -o "$UPLINK_IFACE" -j ACCEPT
iptables -C INPUT -i "$AP_IFACE" -p tcp --dport "$PORTAL_PORT" -j ACCEPT 2>/dev/null \
  || iptables -I INPUT 1 -i "$AP_IFACE" -p tcp --dport "$PORTAL_PORT" -j ACCEPT
iptables -t nat -C POSTROUTING -o "$UPLINK_IFACE" -j MASQUERADE 2>/dev/null \
  || iptables -t nat -A POSTROUTING -o "$UPLINK_IFACE" -j MASQUERADE
iptables -P FORWARD DROP
mkdir -p /etc/iptables
ipset save > /etc/iptables/ipset.rules
iptables-save > /etc/iptables/rules.v4

echo "== 6/8 Password admin =="
if [ ! -f /opt/portal/admin_pass.txt ]; then
  tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c 12 > /opt/portal/admin_pass.txt
  chmod 600 /opt/portal/admin_pass.txt
fi

echo "== 7/8 Enable & start services =="
systemctl unmask hostapd 2>/dev/null || true
systemctl daemon-reload
systemctl enable --now portal-net portal-fw hostapd dnsmasq portal-web

echo "== 8/8 Verifikasi =="
sleep 3
for s in portal-net hostapd dnsmasq portal-web; do
  printf "  %-12s %s\n" "$s" "$(systemctl is-active $s)"
done
curl -s -o /dev/null -w "  portal web: HTTP %{http_code}\n" "http://$PORTAL_IP:$PORTAL_PORT/" || true

echo ""
echo "=============================================="
echo " Instalasi selesai!"
echo "  WiFi SSID : $SSID"
echo "  Portal    : http://$PORTAL_IP:$PORTAL_PORT/"
echo "  Admin     : http://$PORTAL_IP:$PORTAL_PORT/admin/"
echo "  User      : admin"
echo "  Password  : $(cat /opt/portal/admin_pass.txt)"
echo "=============================================="
echo "Catat password admin di atas, lalu hapus baris ini dari histori shell."
