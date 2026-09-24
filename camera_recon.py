#!/usr/bin/env python3
"""
camera_recon.py -- headless CCTV / IP-camera discovery for Ragnar.

Adapted from RaspyJack's ``cctv_scanner`` payload (author 7h30th3r0n3), stripped
of the LCD/button UI and rebuilt to run headless behind the Ragnar web dashboard,
filing its findings into the per-network loot tree.

Scope: the operator's own / authorized network. It only scans targets the
operator explicitly gives it -- the local subnet (from the ARP/neighbour table),
a single IP, a CIDR, or an IP list -- never the internet at large. This is the
same class of internal-network assessment as an nmap sweep + default-credential
check, packaged for camera devices.

Per-host pipeline: TCP port scan -> web-port HTTP fingerprint (brand) -> login
discovery -> default-credential check -> MJPEG endpoint probe -> RTSP DESCRIBE
stream detection. Any live MJPEG/RTSP URLs found can be handed to the Live Cams
panel for viewing.
"""

import os
import re
import json
import socket
import threading
import subprocess
import ipaddress
from datetime import datetime

try:
    import requests
    try:
        requests.packages.urllib3.disable_warnings()  # self-signed camera certs
    except Exception:
        pass
except Exception:  # pragma: no cover
    requests = None

CAMERA_PORTS = [80, 443, 554, 8080, 8081, 8082, 8083, 8088, 8090, 8443, 8554, 3702]
DEFAULT_CREDS = [
    ("admin", "admin"), ("admin", "12345"), ("admin", "password"),
    ("root", "root"), ("admin", ""), ("admin", "888888"),
    ("admin", "666666"), ("admin", "1234"), ("root", "pass"),
]
RTSP_PATHS = ["/Streaming/Channels/1", "/live", "/cam/realmonitor",
              "/h264", "/live/ch00_0", "/ch0_0.264"]
MJPEG_PATHS = ["/", "/video", "/stream", "/mjpg/video.mjpg",
               "/axis-cgi/mjpg/video.cgi", "/cgi-bin/snapshot.cgi",
               "/video.mjpg", "/snap.jpg", "/videostream.cgi",
               "/live", "/cam", "/feed", "/mjpeg", "/video.cgi",
               "/image", "/shot.jpg", "/cgi-bin/mjpeg",
               "/Streaming/channels/1/preview"]
BRAND_SIGS = {
    "Hikvision": ["/ISAPI/", "hikvision", "DNVRS-Webs"],
    "Dahua":     ["/cgi-bin/magicBox.cgi", "dahua", "DH_"],
    "Axis":      ["/axis-cgi/", "AXIS"],
    "CPPlus":    ["/cgi-bin/snapshot.cgi", "cpplus", "CP-"],
}
LOGIN_PATHS = ["/", "/login", "/admin", "/cgi-bin/", "/login.htm"]

_IPRE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")


def _tcp_open(ip, port, timeout=0.8):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((ip, port)) == 0
    except Exception:
        return False
    finally:
        s.close()


def _http_get(url, timeout=4, auth=None):
    """Return (status_code, headers_dict, body_text[:2000]); (0, {}, '') on error."""
    if requests is None:
        return 0, {}, ""
    try:
        r = requests.get(url, timeout=timeout, auth=auth, verify=False,
                         allow_redirects=True)
        return r.status_code, dict(r.headers), (r.text or "")[:2000]
    except Exception:
        return 0, {}, ""


def _rtsp_describe(ip, port, path, timeout=3):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        req = ("DESCRIBE rtsp://%s:%d%s RTSP/1.0\r\nCSeq: 1\r\n"
               "Accept: application/sdp\r\n\r\n" % (ip, port, path))
        s.sendall(req.encode())
        return "200 OK" in s.recv(1024).decode("utf-8", "replace")
    except Exception:
        return False
    finally:
        s.close()


def _arp_hosts():
    """IPs currently in the ARP/neighbour table (fast LAN target list)."""
    hosts = set()
    try:
        out = subprocess.run(["ip", "neigh", "show"], capture_output=True,
                             text=True, timeout=5)
        for line in out.stdout.splitlines():
            parts = line.split()
            if parts and _IPRE.match(parts[0]):
                ip = parts[0]
                if not ip.endswith(".255") and not ip.endswith(".0"):
                    hosts.add(ip)
    except Exception:
        pass
    try:
        out = subprocess.run(["arp", "-an"], capture_output=True, text=True, timeout=5)
        for line in out.stdout.splitlines():
            m = re.search(r"\((\d+\.\d+\.\d+\.\d+)\)", line)
            if m and not m.group(1).endswith((".255", ".0")):
                hosts.add(m.group(1))
    except Exception:
        pass
    return sorted(hosts)


def expand_targets(mode, target):
    """Turn a (mode, target) request into a validated, de-duplicated IP list."""
    mode = (mode or "lan").lower()
    ips = []
    if mode == "single":
        ips = [(target or "").strip()]
    elif mode == "subnet":
        try:
            net = ipaddress.ip_network((target or "").strip(), strict=False)
            ips = [str(h) for h in net.hosts()]
        except Exception:
            ips = []
    elif mode == "list":
        ips = [x.strip() for x in re.split(r"[\s,]+", target or "") if x.strip()]
    else:  # lan
        ips = _arp_hosts()
    out, seen = [], set()
    for ip in ips:
        try:
            ipaddress.ip_address(ip)
        except Exception:
            continue
        if ip not in seen:
            seen.add(ip)
            out.append(ip)
    return out[:512]  # hard cap


def _scan_host(ip, should_stop):
    """Run the discovery pipeline on one host. Returns a cam dict or None."""
    cam = {"ip": ip, "brand": "Unknown", "open_ports": [], "login_url": "",
           "creds": None, "streams": [], "mjpeg_urls": []}

    for port in CAMERA_PORTS:
        if should_stop():
            return None
        if _tcp_open(ip, port):
            cam["open_ports"].append(port)
    if not cam["open_ports"]:
        return None

    web_port = next((p for p in (80, 8080, 8081, 8088, 443, 8443)
                     if p in cam["open_ports"]), None)
    if web_port:
        scheme = "https" if web_port in (443, 8443) else "http"
        base = "%s://%s:%d" % (scheme, ip, web_port)
        code, hdrs, body = _http_get(base)
        if code > 0:
            combined = (body + str(hdrs)).lower()
            for brand, sigs in BRAND_SIGS.items():
                if any(sig.lower() in combined for sig in sigs):
                    cam["brand"] = brand
                    break
            for lpath in LOGIN_PATHS:
                if should_stop():
                    return None
                lcode, _, _ = _http_get(base + lpath, timeout=3)
                if lcode in (200, 401, 403):
                    cam["login_url"] = base + lpath
                    if lcode in (401, 403):
                        for user, passwd in DEFAULT_CREDS:
                            if should_stop():
                                return None
                            cc, _, _ = _http_get(cam["login_url"], timeout=3,
                                                 auth=(user, passwd))
                            if cc == 200:
                                cam["creds"] = [user, passwd]
                                break
                    break
        for mjpath in MJPEG_PATHS:
            if should_stop():
                return None
            mc, mh, _ = _http_get(base + mjpath, timeout=3,
                                  auth=tuple(cam["creds"]) if cam["creds"] else None)
            if mc == 200:
                ct = str(mh.get("Content-Type", "")).lower()
                if "image" in ct or "multipart" in ct or "jpeg" in ct:
                    cam["mjpeg_urls"].append(base + mjpath)

    rtsp_port = 554 if 554 in cam["open_ports"] else (
        8554 if 8554 in cam["open_ports"] else None)
    if rtsp_port:
        for rpath in RTSP_PATHS:
            if should_stop():
                return None
            if _rtsp_describe(ip, rtsp_port, rpath):
                cam["streams"].append("rtsp://%s:%d%s" % (ip, rtsp_port, rpath))
    return cam


class CameraRecon:
    """Singleton scan runner: one scan at a time, polled via snapshot()."""

    def __init__(self):
        self._lock = threading.Lock()
        self._reset()

    def _reset(self):
        self._st = {"scanning": False, "stop": False, "status": "idle",
                    "scanned": 0, "total": 0, "cameras": [], "target": "",
                    "started": None, "finished": None, "loot_file": None}

    def snapshot(self):
        with self._lock:
            s = dict(self._st)
            s["cameras"] = [dict(c) for c in self._st["cameras"]]
            return s

    def _should_stop(self):
        with self._lock:
            return self._st["stop"]

    def stop(self):
        with self._lock:
            self._st["stop"] = True

    def start(self, mode, target, out_dir=None):
        targets = expand_targets(mode, target)
        with self._lock:
            if self._st["scanning"]:
                return False, "A scan is already running", 0
            self._reset()
            self._st.update({"scanning": True, "status": "scanning",
                             "total": len(targets),
                             "target": "%s: %s" % (mode, target or "local subnet"),
                             "started": datetime.utcnow().isoformat() + "Z"})
        if not targets:
            with self._lock:
                self._st.update({"scanning": False, "status": "done",
                                 "finished": datetime.utcnow().isoformat() + "Z"})
            return True, "No valid targets", 0
        t = threading.Thread(target=self._run, args=(targets, out_dir),
                             name="camera-recon", daemon=True)
        t.start()
        return True, "started", len(targets)

    def _run(self, targets, out_dir):
        import concurrent.futures as cf
        def worker(ip):
            if self._should_stop():
                return None
            cam = _scan_host(ip, self._should_stop)
            with self._lock:
                self._st["scanned"] += 1
                if cam:
                    self._st["cameras"] = list(self._st["cameras"]) + [cam]
            return cam
        try:
            with cf.ThreadPoolExecutor(max_workers=16) as ex:
                list(ex.map(worker, targets))
        except Exception:
            pass
        loot_file = None
        if out_dir:
            try:
                loot_file = self._write_loot(out_dir, self.snapshot())
            except Exception:
                loot_file = None
        with self._lock:
            self._st.update({"scanning": False,
                             "status": "stopped" if self._st["stop"] else "done",
                             "finished": datetime.utcnow().isoformat() + "Z",
                             "loot_file": loot_file})

    @staticmethod
    def _write_loot(out_dir, snap):
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        report = os.path.join(out_dir, "camera_recon_%s.json" % ts)
        with open(report, "w") as f:
            json.dump(snap, f, indent=2)
        creds = [c for c in snap["cameras"] if c.get("creds")]
        if creds:
            with open(os.path.join(out_dir, "camera_creds_%s.txt" % ts), "w") as f:
                for c in creds:
                    f.write("%s\t%s:%s\n" % (c["ip"], c["creds"][0], c["creds"][1]))
        streams = []
        for c in snap["cameras"]:
            streams += c.get("streams", []) + c.get("mjpeg_urls", [])
        if streams:
            with open(os.path.join(out_dir, "camera_streams_%s.txt" % ts), "w") as f:
                for u in streams:
                    f.write(u + "\n")
        return report


# module-level singleton used by the web app
scanner = CameraRecon()
