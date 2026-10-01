#!/bin/bash
export DISPLAY=:0
xset s off 2>/dev/null; xset s noblank 2>/dev/null; xset -dpms 2>/dev/null
command -v openbox   >/dev/null 2>&1 && openbox &
command -v unclutter >/dev/null 2>&1 && unclutter -idle 0 -root &

BROWSER=""
for b in chromium chromium-browser; do command -v "$b" >/dev/null 2>&1 && { BROWSER="$b"; break; }; done

PROFILE="$HOME/.config/ragnar-tft-chromium"
mkdir -p "$PROFILE"
rm -f "$PROFILE"/SingletonLock "$PROFILE"/SingletonSocket "$PROFILE"/SingletonCookie 2>/dev/null

PWN_SCALE=1.0
RAGNAR_SCALE=0.75

ARGS=(--kiosk --noerrdialogs --disable-infobars --disable-translate \
  --disable-features=TranslateUI,Translate,CalculateNativeWinOcclusion \
  --disable-session-crashed-bubble --no-first-run \
  --check-for-update-interval=31536000 --disable-dev-shm-usage --password-store=basic \
  --disable-gpu --disable-gpu-compositing --enable-low-end-device-mode \
  --renderer-process-limit=1 --disable-smooth-scrolling \
  --user-data-dir="$PROFILE")

pick_url() {
  if   curl -fsS --max-time 2 -o /dev/null http://localhost:8000/ 2>/dev/null; then echo "http://localhost:8000/web/kiosk_status.html"
  elif curl -fsS --max-time 2 -o /dev/null http://localhost:8080/ 2>/dev/null; then echo "http://localhost:8080/"
  else echo ""; fi
}

CUR=""
while true; do
  URL="$(pick_url)"
  if [ -n "$URL" ] && [ "$URL" != "$CUR" ]; then
    case "$URL" in *:8080*) SC="$PWN_SCALE";; *) SC="$RAGNAR_SCALE";; esac
    echo "[tft] $(date -Iseconds) -> $URL (scale $SC)"
    pkill -f "user-data-dir=$PROFILE" 2>/dev/null; sleep 1
    PREFS="$PROFILE/Default/Preferences"
    [ -f "$PREFS" ] && sed -i 's/"exit_type":"[^"]*"/"exit_type":"Normal"/;s/"exited_cleanly":false/"exited_cleanly":true/' "$PREFS" 2>/dev/null
    "$BROWSER" "${ARGS[@]}" --force-device-scale-factor="$SC" --app="$URL" >/dev/null 2>&1 &
    CUR="$URL"
  fi
  sleep 5
done
