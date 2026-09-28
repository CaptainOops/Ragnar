#!/usr/bin/env python3
"""Cellular uplink fallback — USB-tethered hotspots, phones and LTE modems.

A leave-behind Ragnar can plug a cellular hotspot (Orbic Speed, Netgear
Nighthawk, Inseego MiFi...), a phone in USB-tethering mode, or a QMI/MBIM
modem into a USB port and use it as a *backup* internet path. The host
drivers (rndis_host, cdc_ether, cdc_ncm, ipheth, qmi_wwan, cdc_mbim) ship in
the stock Raspberry Pi kernel; nothing extra is needed for the link to come
up. What this module fixes is everything that happens after it does:

  * Route priority. dhcpcd gives a wired interface metric 1000+ifindex and
    NetworkManager gives it 100 — both beat Wi-Fi, so without intervention
    the hotspot silently becomes the PRIMARY uplink. Cellular interfaces are
    pinned to a high metric (default 20000) so they carry traffic only when
    Ethernet and Wi-Fi have no default route.
  * Scan target. A tethered hotspot is named enx<mac> and looks like wired
    Ethernet, so Ragnar would happily nmap the hotspot's private LAN (just the
    hotspot and itself) over metered data. is_cellular() lets the scanner,
    the passive-capture pickers and the Ethernet lists skip it.

Detection is by kernel driver: rndis_host / ipheth / qmi_wwan / cdc_mbim /
huawei_cdc_ncm are phones and modems. cdc_ether / cdc_ncm are ambiguous (some
2.5 GbE dongles bind cdc_ncm), so those count only when the USB vendor or
product string looks like a phone/hotspot/modem. `cellular_force_ifaces` and
`cellular_exclude_ifaces` in shared_config.json override either way.

The route metric is enforced three ways, each idempotent:
  1. /etc/NetworkManager/conf.d/90-ragnar-cellular.conf — NM connection
     defaults matched by driver (covers the unambiguous drivers at DHCP time).
  2. /lib/dhcpcd/dhcpcd-hooks/90-ragnar-cellular — re-pins the metric right
     after every dhcpcd lease/RA event (dhcpcd also runs on Ragnar images).
  3. enforce() — called every few seconds by the web server's monitor loop as
     a backstop, and the only path for vendor-matched cdc_ether/cdc_ncm.

CLI (root):  cellular_uplink.py status | enforce [--iface IF] | install
             | is-cellular IF   (exit 0 when IF is cellular)
"""

import json
import os
import re
import subprocess
import sys
import time

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(REPO_DIR, 'config', 'shared_config.json')

DEFAULT_METRIC = 20000

# Drivers that only ever front a phone, hotspot or cellular modem.
CELLULAR_DRIVERS = ('rndis_host', 'ipheth', 'qmi_wwan', 'cdc_mbim', 'huawei_cdc_ncm')
# Drivers shared with ordinary USB Ethernet adapters; need a vendor/product hint.
AMBIGUOUS_DRIVERS = ('cdc_ether', 'cdc_ncm')

# USB vendor IDs of phone / hotspot / modem makers.
CELLULAR_USB_VENDORS = {
    '05c6': 'Qualcomm', '04e8': 'Samsung', '18d1': 'Google', '12d1': 'Huawei',
    '19d2': 'ZTE', '0846': 'Netgear', '1410': 'Novatel/Inseego', '1199': 'Sierra Wireless',
    '2c7c': 'Quectel', '05ac': 'Apple', '22b8': 'Motorola', '2717': 'Xiaomi',
    '2a70': 'OnePlus', '1bbb': 'Alcatel/TCL', '2cb7': 'Fibocom', '1bc7': 'Telit',
    '0bb4': 'HTC', '1004': 'LG', '0fce': 'Sony', '22d9': 'Oppo', '1e0e': 'SIMCom',
}
_CELLULAR_NAME_RE = re.compile(
    r'hotspot|mifi|modem|\blte\b|\b[45]g\b|mobile|phone|android|orbic|inseego|'
    r'franklin|nighthawk|jetpack|huawei|zte|pixel|galaxy|iphone|quectel|sierra|'
    r'telit|fibocom|simcom|tether', re.I)

NM_CONF_PATH = '/etc/NetworkManager/conf.d/90-ragnar-cellular.conf'
DHCPCD_HOOK_DIR = '/lib/dhcpcd/dhcpcd-hooks'
DHCPCD_HOOK_PATH = os.path.join(DHCPCD_HOOK_DIR, '90-ragnar-cellular')

_IFACE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,14}$')

_cfg_cache = {'mtime': None, 'data': {}}


# --------------------------------------------------------------------------
# config
# --------------------------------------------------------------------------
def _load_config():
    """shared_config.json, cached on mtime (the dhcpcd hook runs us without
    SharedData, so we read the file directly)."""
    try:
        mtime = os.path.getmtime(CONFIG_PATH)
    except OSError:
        return {}
    if _cfg_cache['mtime'] != mtime:
        try:
            with open(CONFIG_PATH) as f:
                data = json.load(f)
            _cfg_cache.update(mtime=mtime, data=data if isinstance(data, dict) else {})
        except (OSError, ValueError):
            return _cfg_cache['data']
    return _cfg_cache['data']


def _split_list(value):
    if isinstance(value, (list, tuple)):
        items = value
    else:
        items = re.split(r'[\s,]+', str(value or ''))
    return {i.strip() for i in items if i and _IFACE_RE.match(i.strip())}


def settings(cfg=None):
    cfg = cfg if cfg is not None else _load_config()
    try:
        metric = int(cfg.get('cellular_route_metric', DEFAULT_METRIC))
    except (TypeError, ValueError):
        metric = DEFAULT_METRIC
    return {
        'enabled': bool(cfg.get('cellular_fallback_enabled', True)),
        'metric': max(1, min(metric, 65535)),
        'force': _split_list(cfg.get('cellular_force_ifaces', '')),
        'exclude': _split_list(cfg.get('cellular_exclude_ifaces', '')),
        'allow_scan': bool(cfg.get('cellular_allow_scan', False)),
    }


# --------------------------------------------------------------------------
# detection
# --------------------------------------------------------------------------
def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ''


def _usb_info(iface):
    """Driver + USB descriptor strings for a network interface ({} if not USB)."""
    dev = f'/sys/class/net/{iface}/device'
    if not os.path.exists(dev):
        return {}
    info = {'driver': os.path.basename(os.path.realpath(os.path.join(dev, 'driver')))
            if os.path.exists(os.path.join(dev, 'driver')) else ''}
    # device -> USB interface (1-1:1.0); its parent is the USB device with the
    # idVendor/manufacturer/product attributes. A gadget (g_ether usb0) has none.
    node = os.path.realpath(dev)
    for _ in range(3):
        if os.path.exists(os.path.join(node, 'idVendor')):
            info.update(
                vendor_id=_read(os.path.join(node, 'idVendor')).lower(),
                product_id=_read(os.path.join(node, 'idProduct')).lower(),
                manufacturer=_read(os.path.join(node, 'manufacturer')),
                product=_read(os.path.join(node, 'product')),
            )
            break
        node = os.path.dirname(node)
    return info


def classify(iface, cfg=None):
    """{'cellular': bool, 'reason': str, driver/vendor/product fields}."""
    s = settings(cfg)
    if not iface or not _IFACE_RE.match(iface) or not os.path.exists(f'/sys/class/net/{iface}'):
        return {'cellular': False, 'reason': 'no such interface'}
    info = _usb_info(iface)
    if iface in s['exclude']:
        return {**info, 'cellular': False, 'reason': 'excluded in settings'}
    if iface in s['force']:
        return {**info, 'cellular': True, 'reason': 'forced in settings'}
    if iface.startswith('wwan'):
        return {**info, 'cellular': True, 'reason': 'WWAN modem interface'}
    driver = info.get('driver', '')
    if driver in CELLULAR_DRIVERS:
        return {**info, 'cellular': True, 'reason': f'{driver} driver'}
    if driver in AMBIGUOUS_DRIVERS and info.get('vendor_id'):
        vendor = CELLULAR_USB_VENDORS.get(info['vendor_id'])
        if vendor:
            return {**info, 'cellular': True, 'reason': f'{driver} + {vendor} USB vendor'}
        label = f"{info.get('manufacturer', '')} {info.get('product', '')}"
        if _CELLULAR_NAME_RE.search(label):
            return {**info, 'cellular': True, 'reason': f'{driver} + "{label.strip()}"'}
    return {**info, 'cellular': False, 'reason': 'not a cellular driver'}


def is_cellular(iface, cfg=None):
    """True when `iface` is a USB-tethered hotspot/phone or cellular modem.
    Never raises — callers use it inside interface pickers."""
    try:
        return bool(classify(iface, cfg).get('cellular'))
    except Exception:
        return False


def cellular_ifaces(cfg=None):
    try:
        names = sorted(os.listdir('/sys/class/net'))
    except OSError:
        return []
    return [n for n in names if is_cellular(n, cfg)]


# --------------------------------------------------------------------------
# routes
# --------------------------------------------------------------------------
def _run(cmd, timeout=6):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.SubprocessError) as e:
        return 1, '', str(e)


def default_routes(family=4):
    """[{'dev', 'via', 'metric', 'proto'}] for the IPv4/IPv6 default routes,
    in kernel order (lowest metric first)."""
    rc, out, _ = _run(['ip', f'-{family}', '-o', 'route', 'show', 'default'])
    routes = []
    if rc != 0:
        return routes
    for line in out.splitlines():
        parts = line.split()
        if not parts or parts[0] != 'default':
            continue
        r = {'dev': None, 'via': None, 'metric': 0, 'proto': None}
        for key in ('dev', 'via', 'proto'):
            if key in parts and parts.index(key) + 1 < len(parts):
                r[key] = parts[parts.index(key) + 1]
        if 'metric' in parts:
            try:
                r['metric'] = int(parts[parts.index('metric') + 1])
            except (ValueError, IndexError):
                pass
        if r['dev']:
            routes.append(r)
    routes.sort(key=lambda x: x['metric'])
    return routes


def active_uplink(family=4):
    """Interface the kernel uses for internet traffic (lowest-metric default)."""
    routes = default_routes(family)
    return routes[0]['dev'] if routes else None


def _nm_managed(iface):
    rc, out, _ = _run(['nmcli', '-t', '-g', 'GENERAL.STATE', 'device', 'show', iface])
    # 'connected (externally)' means NM is only observing — a device modify
    # would make it take the link over and drop the address someone else set.
    return rc == 0 and out.strip().endswith('(connected)')


def enforce(cfg=None, iface=None):
    """Pin every cellular interface's default routes to the fallback metric.
    Returns a list of human-readable actions taken (empty when compliant)."""
    s = settings(cfg)
    if not s['enabled']:
        return []
    targets = [iface] if iface else cellular_ifaces(cfg)
    targets = [t for t in targets if t and is_cellular(t, cfg)]
    actions = []
    metric = s['metric']
    for dev in targets:
        bad = [r for fam in (4, 6) for r in default_routes(fam)
               if r['dev'] == dev and r['metric'] != metric]
        if not bad:
            continue
        # NetworkManager: change the device's applied metric so NM itself
        # re-adds the route correctly on every DHCP renew (not persisted).
        if _nm_managed(dev):
            rc, _, err = _run(['nmcli', 'device', 'modify', dev,
                               'ipv4.route-metric', str(metric),
                               'ipv6.route-metric', str(metric)], timeout=15)
            actions.append(f'nmcli device modify {dev} metric {metric}'
                           + ('' if rc == 0 else f' failed: {err.strip()[:120]}'))
        # Anything still wrong (dhcpcd, kernel RA routes, NM stragglers):
        # add the pinned route first, then drop the old one — no gap.
        for fam in (4, 6):
            for r in default_routes(fam):
                if r['dev'] != dev or r['metric'] == metric:
                    continue
                base = ['ip', f'-{fam}', 'route']
                spec = ['default'] + (['via', r['via']] if r['via'] else []) + ['dev', dev]
                _run(base + ['replace'] + spec + ['metric', str(metric)]
                     + (['proto', r['proto']] if r['proto'] else []))
                _run(base + ['del'] + spec + ['metric', str(r['metric'])])
                actions.append(f'IPv{fam} default via {dev}: metric {r["metric"]} -> {metric}')
    return actions


# --------------------------------------------------------------------------
# status
# --------------------------------------------------------------------------
def _iface_ipv4(iface):
    rc, out, _ = _run(['ip', '-4', '-o', 'addr', 'show', 'dev', iface])
    return [p[p.index('inet') + 1] for p in (l.split() for l in out.splitlines())
            if 'inet' in p] if rc == 0 else []


def status(cfg=None):
    s = settings(cfg)
    routes4 = default_routes(4)
    active = routes4[0]['dev'] if routes4 else None
    ifaces = []
    for name in cellular_ifaces(cfg):
        c = classify(name, cfg)
        route = next((r for r in routes4 if r['dev'] == name), None)
        ifaces.append({
            'name': name,
            'reason': c.get('reason'),
            'driver': c.get('driver'),
            'vendor_id': c.get('vendor_id'),
            'product_id': c.get('product_id'),
            'device': ' '.join(x for x in (c.get('manufacturer'), c.get('product')) if x) or None,
            'carrier': _read(f'/sys/class/net/{name}/carrier') == '1',
            'operstate': _read(f'/sys/class/net/{name}/operstate'),
            'ipv4': _iface_ipv4(name),
            'gateway': route['via'] if route else None,
            'metric': route['metric'] if route else None,
            'role': 'active' if name == active else ('standby' if route else 'no route'),
            'rx_bytes': int(_read(f'/sys/class/net/{name}/statistics/rx_bytes') or 0),
            'tx_bytes': int(_read(f'/sys/class/net/{name}/statistics/tx_bytes') or 0),
        })
    return {
        'success': True,
        'enabled': s['enabled'],
        'metric': s['metric'],
        'allow_scan': s['allow_scan'],
        'force_ifaces': sorted(s['force']),
        'exclude_ifaces': sorted(s['exclude']),
        'active_uplink': active,
        'on_cellular': bool(active and any(i['name'] == active for i in ifaces)),
        'primary_routes': [r for r in routes4 if not any(i['name'] == r['dev'] for i in ifaces)],
        'interfaces': ifaces,
        'nm_conf_installed': os.path.exists(NM_CONF_PATH),
        'dhcpcd_hook_installed': os.path.exists(DHCPCD_HOOK_PATH),
    }


# --------------------------------------------------------------------------
# system hooks (root)
# --------------------------------------------------------------------------
def _nm_conf_text(metric):
    drivers = ','.join(f'driver:{d}' for d in CELLULAR_DRIVERS)
    return ('# Managed by Ragnar (cellular_uplink.py) — USB hotspot/phone/modem\n'
            '# uplinks are a FALLBACK: high route metric so Ethernet and Wi-Fi win.\n'
            '[connection-ragnar-cellular]\n'
            f'match-device={drivers}\n'
            f'ipv4.route-metric={metric}\n'
            f'ipv6.route-metric={metric}\n')


def _dhcpcd_hook_text():
    drivers = '|'.join(CELLULAR_DRIVERS + AMBIGUOUS_DRIVERS)
    return f'''# Managed by Ragnar (cellular_uplink.py). Sourced by dhcpcd-run-hooks.
# dhcpcd gives a USB-tethered hotspot metric 1000+ifindex, which beats Wi-Fi;
# re-pin cellular interfaces to the fallback metric after every lease/RA event.
case "$reason" in
BOUND|RENEW|REBIND|REBOOT|STATIC|ROUTERADVERT|BOUND6|RENEW6|REBIND6|REBOOT6|INFORM6)
    _rg_drv=$(basename "$(readlink -f "/sys/class/net/$interface/device/driver" 2>/dev/null)" 2>/dev/null)
    case "$_rg_drv:$interface" in
    {drivers.replace('|', ':*|')}:*|*:wwan*)
        if [ -f "{REPO_DIR}/cellular_uplink.py" ]; then
            /usr/bin/python3 "{REPO_DIR}/cellular_uplink.py" enforce --iface "$interface" >/dev/null 2>&1 &
        fi
        ;;
    esac
    ;;
esac
'''


def _write_if_changed(path, text, mode=0o644):
    try:
        with open(path) as f:
            if f.read() == text:
                return False
    except OSError:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        f.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)
    return True


def install(cfg=None):
    """Write the NetworkManager + dhcpcd hooks (idempotent; root only).
    Returns a list of what changed."""
    s = settings(cfg)
    changed = []
    if os.geteuid() != 0:
        return ['skipped: not root']
    if os.path.isdir('/etc/NetworkManager'):
        if s['enabled']:
            if _write_if_changed(NM_CONF_PATH, _nm_conf_text(s['metric'])):
                changed.append(NM_CONF_PATH)
        elif os.path.exists(NM_CONF_PATH):
            os.remove(NM_CONF_PATH)
            changed.append(f'removed {NM_CONF_PATH}')
        if changed:
            _run(['nmcli', 'general', 'reload', 'conf'], timeout=15)
    if os.path.isdir(DHCPCD_HOOK_DIR):
        if s['enabled']:
            if _write_if_changed(DHCPCD_HOOK_PATH, _dhcpcd_hook_text()):
                changed.append(DHCPCD_HOOK_PATH)
        elif os.path.exists(DHCPCD_HOOK_PATH):
            os.remove(DHCPCD_HOOK_PATH)
            changed.append(f'removed {DHCPCD_HOOK_PATH}')
    return changed


# --------------------------------------------------------------------------
# monitor
# --------------------------------------------------------------------------
class Monitor:
    """Backstop enforcer + change log, driven by the web server's loop."""

    def __init__(self, log=None):
        self.log = log
        self.last_active = None
        self.events = []          # [{'ts', 'msg'}], newest last, capped

    def _event(self, msg):
        self.events.append({'ts': time.time(), 'msg': msg})
        del self.events[:-50]
        if self.log:
            self.log.info(f'[cellular] {msg}')

    def tick(self, cfg=None):
        """Enforce metrics and detect failover. Returns the transition messages
        (failover / restore) raised this tick so the caller can push them."""
        for action in enforce(cfg):
            self._event(action)
        transitions = []
        active = active_uplink(4)
        if active != self.last_active:
            now_cell = bool(active and is_cellular(active, cfg))
            was_cell = bool(self.last_active and is_cellular(self.last_active, cfg))
            if now_cell and not was_cell:
                transitions.append(f'Uplink failed over to cellular ({active}) — '
                                   f'{self.last_active or "no other uplink"} is down')
            elif was_cell and not now_cell:
                transitions.append(f'Uplink restored to {active or "none"} — '
                                   'cellular back on standby')
            for msg in transitions:
                self._event(msg)
            self.last_active = active
        return transitions


def main(argv):
    if len(argv) < 2 or argv[1] in ('-h', '--help'):
        print(__doc__.split('CLI (root):')[1].strip() if 'CLI (root):' in __doc__ else '')
        return 2
    cmd = argv[1]
    if cmd == 'status':
        print(json.dumps(status(), indent=2))
        return 0
    if cmd == 'is-cellular' and len(argv) > 2:
        c = classify(argv[2])
        print(json.dumps(c))
        return 0 if c.get('cellular') else 1
    if cmd == 'enforce':
        iface = argv[argv.index('--iface') + 1] if '--iface' in argv and \
            argv.index('--iface') + 1 < len(argv) else None
        for a in enforce(iface=iface):
            print(a)
        return 0
    if cmd == 'install':
        for c in install():
            print(c)
        return 0
    print(f'unknown command: {cmd}', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
