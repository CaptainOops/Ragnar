"""Tests for issue #818: every host flapping Degraded/Offline on a dual-homed box.

With wired Ethernet AND a Wi-Fi adapter up on the same LAN, multi-interface
mode made two scan jobs: Ethernet filed under 'LAN', Wi-Fi under the real SSID.
The orchestrator runs each inside ``context_registry.activate(job.ssid)``, which
rewrites ``shared_data.active_network_ssid`` for the whole scan. Meanwhile the
Wi-Fi monitor loop reports the real SSID every tick, compared it against that
overridden value, saw 'LAN' != SSID, and once the 30s debounce ran out called
set_active_network() -> mark_all_hosts_degraded() on the live database. Once
per scan cycle, every host went Degraded, and came back on the next scan.

These drive the REAL NetworkContextRegistry, NetworkStorageManager,
SharedData.set_active_network and WiFiManager._set_current_ssid.

Covers:
- the scan override never changes the durable storage network
- the Wi-Fi loop reads the durable SSID, so a long 'LAN' scan is not a switch
- set_active_network for the network already active never degrades hosts,
  even mid-override
- a genuine network change still switches and degrades the outgoing store
- nested overrides unwind correctly and end on the durable network
- same-subnet jobs collapse to one scan over the preferred interface, stored
  under the Wi-Fi SSID; different subnets are left alone
"""

from unittest.mock import MagicMock, patch

import pytest

import shared as shared_mod
from multi_interface import MultiInterfaceState, NetworkContextRegistry, ScanJob
from network_storage import NetworkStorageManager


class FakeShared:
    """The slice of SharedData the context switch touches, with real storage."""

    def __init__(self, data_dir):
        self._pager_mode = False
        self.network_intelligence = None
        self.threat_intelligence = None
        self.currentdir = str(data_dir)
        self.storage_manager = NetworkStorageManager(str(data_dir))
        self.active_network_ssid = None
        self.active_network_slug = None
        self._apply_network_context(self.storage_manager.get_active_context())
        self.context_registry = NetworkContextRegistry(self)

    def _apply_network_context(self, context, configure_db=True):
        if not context:
            return
        self.active_network_ssid = context.get('ssid')
        self.active_network_slug = context.get('slug')

    def _refresh_network_components(self):
        pass

    # The real method, bound onto the fake.
    set_active_network = shared_mod.SharedData.set_active_network


@pytest.fixture
def db():
    db = MagicMock()
    with patch.object(shared_mod, 'get_db', return_value=db):
        yield db


@pytest.fixture
def box(tmp_path, db):
    s = FakeShared(tmp_path)
    s.set_active_network('HomeNet')     # the box is on Wi-Fi 'HomeNet'
    db.reset_mock()
    return s


@pytest.fixture
def wifi(box):
    from wifi_manager import WiFiManager
    box.config = {'wifi_ssid_change_debounce_seconds': 30,
                  'wifi_ap_ssid': 'Ragnar', 'wifi_ap_password': 'x',
                  'wifi_default_interface': 'auto'}
    with patch('wifi_manager.detect_wifi_interface', return_value='wlan1'), \
         patch('wifi_manager.get_db', return_value=None), \
         patch.object(WiFiManager, 'setup_ap_logger'), \
         patch.object(WiFiManager, 'load_wifi_config'):
        wm = WiFiManager(box)
    wm.ssid_change_debounce_s = 0      # a scan outlasts any debounce in reality
    return wm


# ---------------------------------------------------------------------------
# the #818 sequence
# ---------------------------------------------------------------------------

def test_ethernet_scan_override_is_not_a_network_switch(box, wifi, db):
    """The Wi-Fi loop ticking during a 'LAN' scan must not degrade anything."""
    with box.context_registry.activate('LAN'):
        assert box.active_network_ssid == 'LAN'          # the scan's context
        for _ in range(3):                               # loop keeps ticking
            wifi._set_current_ssid('HomeNet')

    db.mark_all_hosts_degraded.assert_not_called()
    assert box.active_network_ssid == 'HomeNet'


def test_override_never_touches_the_durable_network(box):
    with box.context_registry.activate('LAN'):
        assert box.storage_manager.active_ssid == 'HomeNet'
    assert box.storage_manager.active_ssid == 'HomeNet'


def test_wifi_loop_reads_the_durable_ssid_mid_override(box, wifi):
    with box.context_registry.activate('LAN'):
        assert wifi._durable_active_ssid() == 'HomeNet'


def test_reasserting_the_active_network_mid_override_never_degrades(box, db):
    with box.context_registry.activate('LAN'):
        box.set_active_network('HomeNet')
        # …and doesn't yank the running scan out of its context either.
        assert box.active_network_ssid == 'LAN'

    db.mark_all_hosts_degraded.assert_not_called()


def test_reasserting_the_active_network_never_degrades(box, db):
    box.set_active_network('HomeNet')

    db.mark_all_hosts_degraded.assert_not_called()


# ---------------------------------------------------------------------------
# genuine switches still work
# ---------------------------------------------------------------------------

def test_genuine_network_change_still_switches_and_degrades(box, db):
    box.set_active_network('CafeWifi')

    db.mark_all_hosts_degraded.assert_called_once()
    assert box.storage_manager.active_ssid == 'CafeWifi'
    assert box.active_network_ssid == 'CafeWifi'


def test_genuine_change_during_a_scan_lands_on_the_new_network(box, db):
    """The old code restored a pre-scan snapshot — the stale network."""
    with box.context_registry.activate('LAN'):
        box.set_active_network('CafeWifi')

    assert box.active_network_ssid == 'CafeWifi'


# ---------------------------------------------------------------------------
# override bookkeeping
# ---------------------------------------------------------------------------

def test_nested_overrides_unwind_to_the_enclosing_then_durable(box):
    reg = box.context_registry
    with reg.activate('LAN'):
        with reg.activate('Guest'):
            assert box.active_network_ssid == 'Guest'
        assert box.active_network_ssid == 'LAN'
        assert reg.is_overridden()
    assert box.active_network_ssid == 'HomeNet'
    assert not reg.is_overridden()


def test_override_unwinds_even_when_the_scan_raises(box):
    with pytest.raises(RuntimeError):
        with box.context_registry.activate('LAN'):
            raise RuntimeError('nmap died')
    assert box.active_network_ssid == 'HomeNet'
    assert not box.context_registry.is_overridden()


# ---------------------------------------------------------------------------
# same-subnet job merge
# ---------------------------------------------------------------------------

def _eth(net='192.168.1.0/24'):
    return ScanJob(interface='eth0', ssid='LAN', role='ethernet',
                   network_cidr=net, interface_type='ethernet')


def _wlan(net='192.168.1.0/24', ssid='HomeNet'):
    return ScanJob(interface='wlan1', ssid=ssid, role='external',
                   network_cidr=net, interface_type='wifi')


def test_same_subnet_collapses_to_one_wired_scan_under_the_wifi_ssid():
    jobs = MultiInterfaceState._merge_same_network_jobs([_eth(), _wlan()])

    assert len(jobs) == 1
    assert jobs[0].interface == 'eth0'          # the faster, reliable port
    assert jobs[0].ssid == 'HomeNet'            # the network's real identity


def test_wifi_first_same_subnet_keeps_wifi_and_drops_the_duplicate():
    jobs = MultiInterfaceState._merge_same_network_jobs([_wlan(), _eth()])

    assert [(j.interface, j.ssid) for j in jobs] == [('wlan1', 'HomeNet')]


def test_different_subnets_are_both_scanned():
    jobs = MultiInterfaceState._merge_same_network_jobs(
        [_eth('10.0.0.0/24'), _wlan('192.168.1.0/24')])

    assert [(j.interface, j.ssid) for j in jobs] == [('eth0', 'LAN'),
                                                     ('wlan1', 'HomeNet')]


def test_jobs_without_a_known_subnet_are_left_alone():
    jobs = MultiInterfaceState._merge_same_network_jobs(
        [_eth(None), _wlan(None)])

    assert len(jobs) == 2
