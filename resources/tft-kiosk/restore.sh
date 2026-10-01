#!/bin/bash
# Restore the custom Ragnar TFT kiosk (home + wardrive + livecams, touch cal, URL).
# Run after a Ragnar update wipes web/:  sudo /usr/local/share/ragnar-kiosk/restore.sh
set -e
D=/usr/local/share/ragnar-kiosk
cp "$D/kiosk_status.html" /home/ragnar/Ragnar/web/kiosk_status.html
cp "$D/wardrive.html"     /home/ragnar/Ragnar/web/wardrive.html
cp "$D/livecams.html"     /home/ragnar/Ragnar/web/livecams.html
cp "$D/99-touch-calibration.conf" /etc/X11/xorg.conf.d/99-touch-calibration.conf
sed -i "s#http://localhost:8000/?kiosk=1#http://localhost:8000/web/kiosk_status.html#" /usr/local/bin/ragnar-tft-session.sh 2>/dev/null || true
rm -rf "/home/ragnar/.config/ragnar-tft-chromium/Default/Cache" "/home/ragnar/.config/ragnar-tft-chromium/Default/Code Cache" 2>/dev/null || true
systemctl restart ragnar-tft.service
echo "Ragnar TFT kiosk restored (home + wardrive + livecams)."
