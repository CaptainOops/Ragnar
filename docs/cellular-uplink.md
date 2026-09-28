# Cellular Uplink Fallback

Plug a cellular hotspot, a phone or an LTE modem into a Ragnar's USB port and
it becomes a **backup internet path**. It carries traffic only when Ethernet and
Wi-Fi are down, and it is never scanned. A leave-behind unit therefore stays
reachable (Ragnar Mesh / Tailscale works through carrier NAT) and keeps sending
push alerts after the site network goes away.

Find it under **Network → Interfaces → Cellular Uplink Fallback**.

## Supported devices

No drivers need to be added. The stock Raspberry Pi OS kernel ships every USB
host driver these devices use:

| Device | Presents as | Kernel driver |
|---|---|---|
| Orbic Speed, Netgear Nighthawk/MiFi, Inseego, most hotspots | RNDIS or CDC-Ethernet | `rndis_host` / `cdc_ether` |
| Android phone (USB tethering) | RNDIS (older) or CDC-NCM (Android 11+) | `rndis_host` / `cdc_ncm` |
| iPhone (Personal Hotspot over USB) | Apple tethering | `ipheth` |
| QMI / MBIM LTE modem (Quectel, Sierra, Telit…) | WWAN | `qmi_wwan` / `cdc_mbim` |
| Huawei HiLink / E3372 | NCM | `huawei_cdc_ncm` / `cdc_ether` |

On the hotspot, turn on **USB tethering** in its settings or web UI (on many
hotspots it is off by default). Plug it into a **USB-A host port**:

- **Pi 5 / Pi 4**: the USB-A ports work as-is. Ragnar's USB-gadget link
  (`usb0`, for plugging Ragnar into a laptop) sits on the USB-C port only and
  does not conflict.
- **Pi Zero 2 W**: the one data port is also the gadget port. Use a micro-USB
  OTG adapter; its ID pin puts the port in host mode.

The hotspot shows up as `enx<mac>` (or `wwan0` for a modem), gets an address by
DHCP, and appears in the card within about 10 s.

If the device instead shows up as a CD-ROM (`lsusb` lists it, but no network
interface appears), it needs a mode switch. `usb_modeswitch` is installed and
usually handles this automatically; `dmesg | tail -30` shows what happened.

## What Ragnar does with it

**It stays a fallback.** On their own, dhcpcd gives a USB network adapter
metric `1000+ifindex` and NetworkManager gives it `100`. Both beat Wi-Fi
(`600`/`3000+`), so a plugged-in hotspot would silently become the *primary*
uplink and use cellular data even while Wi-Fi works. Ragnar pins every cellular
interface's default route (IPv4 and IPv6) to metric **20000**, in three ways:

1. `/etc/NetworkManager/conf.d/90-ragnar-cellular.conf`: NetworkManager's
   connection defaults, matched by driver.
2. `/lib/dhcpcd/dhcpcd-hooks/90-ragnar-cellular`: re-pins the metric right
   after every dhcpcd lease or router advertisement.
3. The web server's monitor re-checks every 10 s. This is the only path for
   `cdc_ether`/`cdc_ncm` devices, which are detected by USB vendor (see below).

The kernel always uses the lowest-metric default route. As long as Ethernet or
Wi-Fi has one, cellular is on **standby**. When they drop, the cellular route is
the only one left and traffic moves over within seconds; when they come back,
traffic moves back.

**It is never scanned.** The network scanner, ARP liveness sweeps, the
Ethernet lists, the passive-capture interface pickers (L2/L3 watchers, vendor
guards) and the e-Paper/LCD Auto interface all skip cellular interfaces.
Scanning over the hotspot would only find the hotspot and would spend metered
data. When cellular is the *only* uplink, the network scan is skipped
("No LAN (cellular only)"). If a LAN leg without a default route still has an
address, such as a SPAN/monitor cable, that leg is scanned instead. To opt back
in, enable **Allow network scans over cellular**.

In the Interfaces table a cellular interface is labelled **📶 cellular**. On the
HAT's IFACE card it is last in Auto order, but you can still pin it to
speed-test the cellular link itself.

**Failover alerts.** With push notifications enabled, **Config → Push
Notifications → Cellular Failover** sends one message when the uplink moves to
cellular and one when it moves back. The failover message goes out over
cellular, so you still receive it after the site network is gone.

## Detection

| Rule | Treated as cellular |
|---|---|
| Driver `rndis_host`, `ipheth`, `qmi_wwan`, `cdc_mbim`, `huawei_cdc_ncm` | always |
| Interface name `wwan*` | always |
| Driver `cdc_ether` / `cdc_ncm` | only when the USB vendor is a phone/hotspot/modem maker (Qualcomm, Samsung, Google, Apple, Huawei, ZTE, Netgear, Inseego, Sierra, Quectel, …) or the USB product string says hotspot / modem / LTE / 5G / phone |
| Listed in **Always treat as cellular** | always |
| Listed in **Never treat as cellular** | never |

`cdc_ether`/`cdc_ncm` also drive some ordinary USB Ethernet adapters (for
example RTL8156 2.5 GbE dongles), which is why those drivers need a vendor
match. If a hotspot is missed, or a real Ethernet dongle is flagged by mistake,
add it to the matching override list.

## Settings

| Key (`shared_config.json`) | Default | Meaning |
|---|---|---|
| `cellular_fallback_enabled` | `true` | Pin the metric. Turning it off removes the NM/dhcpcd hooks; routes already pinned keep their metric until the link reconnects. |
| `cellular_route_metric` | `20000` | Fallback metric (1000–65535). Must stay above every Wi-Fi/Ethernet metric. |
| `cellular_allow_scan` | `false` | Allow the network scanner to target a cellular LAN. |
| `cellular_force_ifaces` / `cellular_exclude_ifaces` | `""` | Space/comma-separated interface names. |
| `pushover_notify_cellular` | `true` | Failover / restore push notifications. |

## API & CLI

- `GET /api/cellular/status`: settings, the active uplink, `on_cellular`, and
  per-interface role (`active` / `standby` / `no route`), driver, USB device,
  IPv4, gateway, metric and rx/tx byte counters. Also returns the last monitor
  events.
- `POST /api/cellular/settings`: `{enabled, metric, allow_scan, force_ifaces,
  exclude_ifaces}`. Saves, re-installs the hooks and enforces immediately.

```bash
sudo python3 cellular_uplink.py status            # same JSON as the API
sudo python3 cellular_uplink.py is-cellular enx0a1b2c3d4e5f
sudo python3 cellular_uplink.py enforce           # pin metrics now
sudo python3 cellular_uplink.py install           # (re)write NM + dhcpcd hooks
```

`install_ragnar.sh`, `update_ragnar.sh` (Step 6.97) and the web updater
(`scripts/post_update.sh`) all run `install`, and the service re-runs it at
start, so existing units pick it up on their next update.

## Notes

- **Subnet clash.** Many hotspots use `192.168.1.0/24` (and Orbic may default
  to that as well), which is also a very common home/office LAN. While the
  hotspot is on standby this is harmless: routes to the LAN still go out the
  LAN interface. If both are up and you see odd routing, change the hotspot's
  LAN subnet in its web UI.
- **Data use.** On cellular, Ragnar still does its non-scan internet work:
  mesh polling, push alerts, update checks, and Nuclei template fetches if you
  run Adv Scan. The rx/tx counters in the card show what the link has carried
  since it came up.
- **Cell-tower capture is different.** Logging cell towers while wardriving
  needs a ModemManager modem (QMI/MBIM/serial). A tethered hotspot can't do
  that; see [Cellular modem](cell.md). A QMI/MBIM modem can do both at once.
