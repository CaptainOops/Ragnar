# Ragnar TFT status + control kiosk (AIO Pi5)

A lightweight, touch-driven kiosk UI for the on-board SPI TFT (480×320, ILI9486 +
ADS7846) of an all-in-one Ragnar/Pwnagotchi Pi 5. Replaces the heavy live
dashboard on the little screen (which pegged a core and cooked the fan) with
purpose-built pages served **same-origin** from Ragnar's `web/` folder
(`static_folder='web'` → served at `/web/<file>`; localhost bypasses the auth).

Dark "Ragnar Cyberviking" theme (slate `#0f172a`, cyan `#7dd3fc`, green
`#22c55e`, monospace), inline-SVG icons (no emoji font on the panel), big touch
targets, and **no continuous CSS animations** (they spike CPU under the panel's
software rendering — motion is driven by the data poll instead; the only
animated element is the mascot GIF).

## Pages (`web/`)

- **`kiosk_status.html`** — home. Animated viking mascot + speech bubble
  (`ragnar_says`), an activity line (`ragnar_status` → `ragnar_status2`) with a
  **time-estimate scan progress bar** shown only while a user scan runs, system
  stats (temp/CPU/mem/uptime/disk from `/api/system/status`), game chips
  (targets / open ports / vulns / creds from `/api/status`), LAN + Tailscale IPs,
  and four tap buttons: **WARDRIVE** (→ wardrive page), **LIVE CAMS** (→ cams
  page), **SCAN** (start/stop toggle: `/api/manual/scan/network` ↔
  `/api/manual/orchestrator/stop`), **AP MODE** (2-tap confirm,
  `/api/wifi/ap/start` — drops the LAN, road-only).
- **`wardrive.html`** — GPS (`/api/wardriving/status` gps.*), WiFi nets,
  **Bands** (2.4/5/6 GHz) + **Security** (Open-WEP/WPA2/WPA3) tallied from
  `/api/wardriving/networks`, Radios, BLE, START/STOP, and the blocker reason
  from `/api/wardriving/diagnostics`.
- **`livecams.html`** — list of configured cams (`/api/livecams`), tap to view
  one fullscreen (CLOSE stops the stream), plus **⌕ SCAN LAN** to discover
  cameras (`/api/camera-recon/scan` / `/status` / `/stop`).

## On-box setup (not in the repo; see `resources/tft-kiosk/`)

- **Kiosk runner**: `ragnar-tft-session.sh` points Chromium at
  `http://localhost:8000/web/kiosk_status.html` in Ragnar mode (and `:8080` in
  pwn mode). `ragnar-tft.service` runs it on vt7.
- **Touch**: `99-touch-calibration.conf` →
  `/etc/X11/xorg.conf.d/` (libinput `TransformationMatrix "0 -1 1 1 0 0 0 0 1"`
  for landscape rotate=90).
- **Backup / update-safety**: Ragnar updates wipe `web/`, so all three pages +
  the touch conf are copied to `/usr/local/share/ragnar-kiosk/` with a
  one-command restore: `restore.sh` (re-copies pages, re-points the kiosk URL,
  clears the Chromium cache, restarts `ragnar-tft`).

## Deploy (manual, until an installer lands)

```bash
cp web/kiosk_status.html web/wardrive.html web/livecams.html /home/ragnar/Ragnar/web/
sudo install -m0644 resources/tft-kiosk/99-touch-calibration.conf /etc/X11/xorg.conf.d/
sudo sed -i 's#http://localhost:8000/?kiosk=1#http://localhost:8000/web/kiosk_status.html#' /usr/local/bin/ragnar-tft-session.sh
sudo mkdir -p /usr/local/share/ragnar-kiosk && sudo cp web/kiosk_status.html web/wardrive.html web/livecams.html resources/tft-kiosk/99-touch-calibration.conf resources/tft-kiosk/restore.sh /usr/local/share/ragnar-kiosk/
rm -rf ~/.config/ragnar-tft-chromium/Default/{Cache,"Code Cache"}
sudo systemctl restart ragnar-tft.service
```

## TODO (next session)
- Wrap the above into `scripts/install_tft_status_kiosk.sh` for a clean PR.
- Real scan % needs a Ragnar progress endpoint (currently a time estimate).
- Optional: wire camera-recon results into the cams list; AP-on-wlan0 road flow.
