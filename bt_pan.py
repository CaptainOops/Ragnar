"""
Bluetooth PAN (NAP) — a direct Bluetooth link to the box.

Turns the box into a Bluetooth **network access point** so a phone can reach it
over Bluetooth when Tailscale or Wi-Fi can't (no internet, a locked-down
network, out in the field). The box runs a NAP server (`bt-network -s nap`)
bridged to a private ``pan0`` bridge on 192.168.44.0/24, with a scoped dnsmasq
handing the phone an address and a `bt-agent` accepting "just works" pairing.

On the phone (Android only — iOS does not support Bluetooth PAN to a device like
this): pair the box in the system Bluetooth settings, turn on tethering /
"Internet access" for it, then open the Ragnar Mobile app and connect to
``192.168.44.1:8000`` (its default Bluetooth address). The app itself speaks no
Bluetooth — the phone's OS provides the IP link and the app just talks HTTP.

Everything here is **opt-in** (``bt_pan_enabled``) and **fully reversible**:
:meth:`stop` removes the NAP server, the pairing agent, dnsmasq, and the bridge,
leaving networking exactly as it was. The link carries **no default route**, so
turning it on never hijacks the phone's own internet — the phone reaches only
the box on 192.168.44.0/24.

    ┌─────────┐  Bluetooth   ┌──────── box ────────┐
    │  phone  │  PAN/bnep    │  pan0 bridge         │
    │ .44.x   │─────────────▶│  192.168.44.1  :8000 │
    └─────────┘              │  dnsmasq (DHCP only) │
                             │  bt-network -s nap   │
                             └──────────────────────┘

This is receive-only from a networking standpoint (no forwarding/NAT), so it can
never bridge the phone's traffic onto the box's other networks.

NOTE: needs on-device validation with a real Android phone — the pairing +
tethering handshake is the one part that cannot be exercised without hardware.
"""
from __future__ import annotations

import logging
import os
import subprocess
import threading
import time

logger = logging.getLogger(__name__)

# --- Fixed, self-contained topology -----------------------------------------
BRIDGE = "pan0"
GATEWAY = "192.168.44.1"
CIDR = "192.168.44.1/24"
DHCP_LO = "192.168.44.10"
DHCP_HI = "192.168.44.50"
DNSMASQ_CONF = "/tmp/ragnar/btpan-dnsmasq.conf"
DNSMASQ_PID = "/tmp/ragnar/btpan-dnsmasq.pid"

# What the phone sees when it scans for the box. Set as the adapter Alias while
# the NAP is up; cleared (reverts to the hostname) when it comes down.
ADAPTER_ALIAS = "Ragnar"

_CMD_TIMEOUT = 8.0
_DBUS_TIMEOUT = 5.0

# Which apt package provides each runtime tool the NAP needs. `ip` comes from
# iproute2, which is always present, so it is not part of the installable set.
_TOOL_PKG = {
    "bt-network": "bluez-tools",
    "bt-agent": "bluez-tools",
    "dnsmasq": "dnsmasq",
}
# bridge-utils is not strictly required (we bring the bridge up with `ip link`),
# but installing it alongside is harmless and matches what other setups expect.
_INSTALL_PACKAGES = ["bluez-tools", "dnsmasq", "bridge-utils"]


def _priv(cmd: list[str]) -> list[str]:
    """Prefix ``sudo -n`` unless we are already root (ragnar.service runs as
    root; a dev shell may not). Mirrors the rest of the codebase."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return cmd
    return ["sudo", "-n"] + cmd


def _run(cmd: list[str], timeout: float = _CMD_TIMEOUT) -> subprocess.CompletedProcess:
    return subprocess.run(_priv(cmd), capture_output=True, text=True, timeout=timeout)


def _ok(cmd: list[str], timeout: float = _CMD_TIMEOUT) -> bool:
    try:
        return _run(cmd, timeout).returncode == 0
    except Exception as exc:  # noqa: BLE001 - never let a shell-out raise
        logger.debug("[btpan] %s failed: %s", cmd, exc)
        return False


def _tool(name: str) -> bool:
    from shutil import which
    return which(name) is not None


class BtPanServer:
    """Orchestrates the NAP server, pairing agent, dnsmasq and the bridge."""

    def __init__(self, hci: str = "hci0"):
        self.hci = hci
        self._lock = threading.Lock()
        self._procs: dict[str, subprocess.Popen] = {}
        self._error: str | None = None
        self._started_at: float | None = None

    # -- lifecycle -----------------------------------------------------------
    def start(self) -> dict:
        with self._lock:
            missing = [t for t in ("bt-network", "bt-agent", "dnsmasq", "ip") if not _tool(t)]
            if missing:
                self._error = f"missing tools: {', '.join(missing)}"
                return self._status_locked()

            try:
                self._bring_up_adapter()
                self._bring_up_bridge()
                self._start_dnsmasq()
                self._start_agent()
                self._start_nap()
                self._configure_adapters(True)
                self._error = None
                self._started_at = time.time()
                logger.info("[btpan] NAP up on %s (%s)", BRIDGE, GATEWAY)
            except Exception as exc:  # noqa: BLE001
                self._error = str(exc)
                logger.error("[btpan] start failed: %s", exc)
                self._teardown_locked()
            return self._status_locked()

    def stop(self) -> dict:
        with self._lock:
            self._teardown_locked()
            self._started_at = None
            logger.info("[btpan] NAP down")
            return self._status_locked()

    # -- steps ---------------------------------------------------------------
    def _bring_up_adapter(self) -> None:
        # New BT dongles can boot rfkill-blocked; unblock before touching them.
        # Powering + naming + discoverability are done over D-Bus in
        # _configure_adapters (bluetoothctl hangs on a busy stack here).
        _ok(["rfkill", "unblock", "bluetooth"])

    def _bring_up_bridge(self) -> None:
        # Idempotent: leave an existing bridge in place, just ensure addr + up.
        exists = _ok(["ip", "link", "show", BRIDGE])
        if not exists and not _ok(["ip", "link", "add", "name", BRIDGE, "type", "bridge"]):
            raise RuntimeError(f"could not create bridge {BRIDGE}")
        # Adding an address that already exists returns non-zero; ignore that.
        _run(["ip", "addr", "add", CIDR, "dev", BRIDGE])
        if not _ok(["ip", "link", "set", BRIDGE, "up"]):
            raise RuntimeError(f"could not bring up {BRIDGE}")

    def _start_dnsmasq(self) -> None:
        os.makedirs("/tmp/ragnar", exist_ok=True)
        # A stale instance from a crash/restart would hold the pan0 address; kill
        # it by its pid file first (targets only OUR dnsmasq, never the AP one).
        self._kill_dnsmasq()
        # DHCP only (port=0 = no DNS), bound to pan0 alone so it can never touch
        # another network, and NO default route advertised (option 3 empty) so
        # the link never hijacks the phone's own internet.
        conf = (
            f"interface={BRIDGE}\n"
            "bind-interfaces\n"
            "except-interface=lo\n"
            "port=0\n"
            f"dhcp-range={DHCP_LO},{DHCP_HI},255.255.255.0,1h\n"
            "dhcp-option=3\n"
        )
        with open(DNSMASQ_CONF, "w") as fh:
            fh.write(conf)
        # Daemonised with its own pid file, so it is managed by pid (no fragile
        # pattern matching that could hit the AP-mode dnsmasq or a sudo wrapper).
        res = _run(["dnsmasq", "-C", DNSMASQ_CONF, f"--pid-file={DNSMASQ_PID}"])
        if res.returncode != 0:
            raise RuntimeError(f"dnsmasq failed: {res.stderr.strip() or res.returncode}")

    def _kill_dnsmasq(self) -> None:
        try:
            with open(DNSMASQ_PID) as fh:
                pid = int(fh.read().strip())
            _ok(["kill", str(pid)])
        except Exception:  # noqa: BLE001 - stale/missing pid file is fine
            pass
        try:
            os.remove(DNSMASQ_PID)
        except OSError:
            pass

    def _start_agent(self) -> None:
        # "Just works" pairing so a headless box needs no PIN entry.
        self._procs["agent"] = subprocess.Popen(
            _priv(["bt-agent", "-c", "NoInputNoOutput"]),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def _start_nap(self) -> None:
        # bt-network registers the BlueZ NAP server and enslaves each incoming
        # bnep link to the bridge for us.
        self._procs["nap"] = subprocess.Popen(
            _priv(["bt-network", "-s", "nap", BRIDGE]),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(0.4)
        if self._procs["nap"].poll() is not None:
            raise RuntimeError("bt-network exited immediately (NAP registration failed)")

    def _configure_adapters(self, on: bool) -> None:
        """Power, name and (un)advertise every BlueZ adapter — over D-Bus.

        bluetoothctl is unreliable on a busy stack (it can block indefinitely and
        silently no-op, which is exactly why the box never showed up), so drive
        the adapter properties directly with bounded calls. Setting ``on`` names
        the box "Ragnar", makes it discoverable with no timeout, and pairable;
        clearing it reverts the name to the hostname and hides the box again.
        Never raises — a missing dbus or a wedged bluetoothd degrades to a log
        line, not a failed start.
        """
        try:
            import dbus
        except Exception:
            logger.warning("[btpan] python3-dbus unavailable; cannot set discoverable/name")
            return
        try:
            bus = dbus.SystemBus()
            om = dbus.Interface(bus.get_object("org.bluez", "/"),
                                "org.freedesktop.DBus.ObjectManager")
            objs = om.GetManagedObjects(timeout=_DBUS_TIMEOUT)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[btpan] could not reach bluetoothd over D-Bus: %s", exc)
            return
        found = False
        for path, ifaces in objs.items():
            if "org.bluez.Adapter1" not in ifaces:
                continue
            found = True
            try:
                props = dbus.Interface(bus.get_object("org.bluez", path),
                                       "org.freedesktop.DBus.Properties")
                props.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(True), timeout=_DBUS_TIMEOUT)
                props.Set("org.bluez.Adapter1", "Alias",
                          dbus.String(ADAPTER_ALIAS if on else ""), timeout=_DBUS_TIMEOUT)
                props.Set("org.bluez.Adapter1", "DiscoverableTimeout", dbus.UInt32(0), timeout=_DBUS_TIMEOUT)
                props.Set("org.bluez.Adapter1", "PairableTimeout", dbus.UInt32(0), timeout=_DBUS_TIMEOUT)
                props.Set("org.bluez.Adapter1", "Pairable", dbus.Boolean(on), timeout=_DBUS_TIMEOUT)
                props.Set("org.bluez.Adapter1", "Discoverable", dbus.Boolean(on), timeout=_DBUS_TIMEOUT)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[btpan] adapter %s config failed: %s", path, exc)
        if on and not found:
            logger.warning("[btpan] bluetoothd exposes no adapters — is a controller present?")

    def _teardown_locked(self) -> None:
        self._configure_adapters(False)
        for name in ("nap", "agent"):
            proc = self._procs.pop(name, None)
            if not proc:
                continue
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:  # noqa: BLE001
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass
        # Orphans from a previous crash/restart. Match the process NAME exactly
        # (-x), never an arg pattern with -f — under `sudo -n pkill -f "…"` the
        # pattern also matches the sudo wrapper's own command line. Only our own
        # bt-network / bt-agent run, so an exact-name kill is safe here.
        _ok(["pkill", "-x", "bt-network"], timeout=4)
        _ok(["pkill", "-x", "bt-agent"], timeout=4)
        self._kill_dnsmasq()
        # Remove the bridge so networking returns exactly to its prior state.
        _ok(["ip", "link", "set", BRIDGE, "down"])
        _ok(["ip", "link", "del", BRIDGE])

    # -- status --------------------------------------------------------------
    def _bridge_present(self) -> bool:
        return _ok(["ip", "link", "show", BRIDGE], timeout=4)

    def _connected_devices(self) -> int:
        """Count bnep links enslaved to the bridge — i.e. connected phones."""
        try:
            out = _run(["ip", "-o", "link", "show", "master", BRIDGE], timeout=4)
            if out.returncode != 0:
                return 0
            return sum(1 for line in out.stdout.splitlines() if "bnep" in line)
        except Exception:  # noqa: BLE001
            return 0

    def _running(self) -> bool:
        proc = self._procs.get("nap")
        if proc and proc.poll() is None:
            return True
        # Survive a webapp restart: detect an orphaned server too. Match the
        # process NAME exactly (-x), never the arg string with -f — under
        # `sudo -n pgrep -f "bt-network …"` the pattern also appears in the sudo
        # wrapper's own command line, so -f would always match itself.
        return _ok(["pgrep", "-x", "bt-network"], timeout=4)

    def _status_locked(self) -> dict:
        running = self._running()
        missing = missing_tools()
        return {
            "success": True,
            "running": running,
            # Available only when every runtime tool is present; the UI shows an
            # "Install dependencies" action from `missing_packages` otherwise.
            "available": not missing,
            "missing_tools": missing,
            "missing_packages": missing_packages(),
            "bridge": BRIDGE if self._bridge_present() else None,
            "address": GATEWAY if running else None,
            "port": 8000,
            "connected_devices": self._connected_devices() if running else 0,
            "discoverable": running,
            "uptime_s": (time.time() - self._started_at) if (running and self._started_at) else 0,
            "error": self._error,
            "platform_note": "Android only — iOS does not support Bluetooth PAN.",
        }

    def status(self) -> dict:
        with self._lock:
            return self._status_locked()


# --- module-level singleton the web routes drive ----------------------------
_server: BtPanServer | None = None


def _instance() -> BtPanServer:
    global _server
    if _server is None:
        _server = BtPanServer()
    return _server


def start() -> dict:
    return _instance().start()


def stop() -> dict:
    return _instance().stop()


def status() -> dict:
    return _instance().status()


# --- On-demand dependency install -------------------------------------------
# The NAP needs bluez-tools (bt-network, bt-agent) + dnsmasq, which a lean image
# may not ship. Rather than fail with a raw package error, the UI offers an
# "Install dependencies" action that drives this — apt in the background, with a
# streamed log the page polls, exactly like the other on-demand installers.


def missing_tools() -> list[str]:
    """Runtime tools the NAP needs that are not on PATH."""
    return [t for t in _TOOL_PKG if not _tool(t)]


def missing_packages() -> list[str]:
    """apt packages to install to satisfy the missing tools."""
    return sorted({_TOOL_PKG[t] for t in missing_tools()})


_install_lock = threading.Lock()
_install_state = {"running": False, "log": "", "done": False, "ok": None, "error": None}


def _install_append(text: str) -> None:
    with _install_lock:
        # Keep the tail bounded — the page only shows the last lines.
        _install_state["log"] = (_install_state["log"] + text)[-8000:]


def install_status() -> dict:
    with _install_lock:
        snap = dict(_install_state)
    snap["missing_tools"] = missing_tools()
    snap["missing_packages"] = missing_packages()
    return snap


def install_deps() -> dict:
    """Kick off (once) a background apt install of the missing packages."""
    with _install_lock:
        if _install_state["running"]:
            already = True
        else:
            already = False
            _install_state.update(running=True, log="", done=False, ok=None, error=None)
    if not already:
        threading.Thread(target=_do_install, daemon=True, name="btpan-install").start()
    return install_status()


def _do_install() -> None:
    env = dict(os.environ, DEBIAN_FRONTEND="noninteractive")
    try:
        _install_append("Updating package lists…\n")
        up = subprocess.run(_priv(["apt-get", "update"]), capture_output=True, text=True,
                            timeout=180, env=env)
        _install_append((up.stdout or "")[-1500:] + (up.stderr or "")[-1500:])
        _install_append(f"\nInstalling: {' '.join(_INSTALL_PACKAGES)}\n")
        proc = subprocess.Popen(
            _priv(["apt-get", "install", "-y", "--no-install-recommends"] + _INSTALL_PACKAGES),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env,
        )
        if proc.stdout:
            for line in proc.stdout:
                _install_append(line)
        proc.wait(timeout=600)
        ok = proc.returncode == 0 and not missing_tools()
        with _install_lock:
            _install_state.update(done=True, ok=ok,
                                  error=None if ok else "Install finished but some tools are still missing.")
        _install_append("\nDone — dependencies installed.\n" if ok
                        else "\nInstall did not complete cleanly.\n")
    except Exception as exc:  # noqa: BLE001
        logger.error("[btpan] dependency install failed: %s", exc)
        with _install_lock:
            _install_state.update(done=True, ok=False, error=str(exc))
        _install_append(f"\nError: {exc}\n")
    finally:
        with _install_lock:
            _install_state["running"] = False
