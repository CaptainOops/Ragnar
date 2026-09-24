#!/bin/bash
# reset_monitor_radio.sh — reload the kernel driver of USB Wi-Fi adapters so a
# Ragnar <-> Pwnagotchi mode swap starts monitor mode from a clean firmware
# state.
#
# Why: some USB Wi-Fi drivers (notably rtw88_8812au / RTL8812AU) wedge after
# repeated managed<->monitor transitions without a reboot — the adapter stops
# reporting access points and throws USB "-71" errors, which starves bettercap
# and makes Pwnagotchi restart-loop ("5 epochs without visible access points").
# Reloading the driver between mode changes gives the adapter a fresh init.
#
# Safety: only USB radios are touched. The onboard Pi Wi-Fi (SDIO brcmfmac),
# which is the SSH/uplink interface, is on a different bus and a different
# module, so it is never reloaded and connectivity is preserved.
set -u

# Collect the drivers of USB wlan interfaces (skip onboard/SDIO).
drivers=""
for net in /sys/class/net/wlan*; do
    [ -e "$net/device" ] || continue
    devpath="$(readlink -f "$net/device" 2>/dev/null)" || continue
    case "$devpath" in
        *usb*) : ;;          # USB radio — eligible for reset
        *)     continue ;;   # onboard / SDIO — never touch
    esac
    drv="$(basename "$(readlink -f "$net/device/driver" 2>/dev/null)" 2>/dev/null)"
    [ -n "$drv" ] && [ "$drv" != "." ] && drivers="$drivers $drv"
done

# De-duplicate.
drivers="$(printf '%s\n' $drivers | sort -u | tr '\n' ' ')"

if [ -z "${drivers// /}" ]; then
    echo "[reset_monitor_radio] no USB Wi-Fi adapter found — nothing to reset"
    exit 0
fi

for drv in $drivers; do
    echo "[reset_monitor_radio] unloading $drv"
    modprobe -r "$drv" 2>/dev/null || true
done

sleep 2

for drv in $drivers; do
    echo "[reset_monitor_radio] loading $drv"
    modprobe "$drv" 2>/dev/null || true
done

# Wait up to ~10s for a USB wlan interface to re-enumerate.
for _ in $(seq 1 20); do
    for net in /sys/class/net/wlan*; do
        [ -e "$net/device" ] || continue
        case "$(readlink -f "$net/device" 2>/dev/null)" in
            *usb*) echo "[reset_monitor_radio] USB radio back up"; exit 0 ;;
        esac
    done
    sleep 0.5
done

echo "[reset_monitor_radio] warning: USB radio did not re-enumerate in time"
exit 0
