"""Passive Ethernet enrichment uses only bounded reads of an existing PCAP."""
import network_diagnostics as nd


def test_pcap_ethernet_counts_vlan_tags_and_keeps_os_hints_tentative(monkeypatch):
    calls = []
    def run(argv, timeout=30):
        calls.append(argv)
        if 'vlan.id' in argv:
            return {'rc': 0, 'out': '10\n10,20\n20,20\n4095\nbad\n', 'err': ''}
        return {'rc': 0, 'out': (
            '192.168.1.4\t\t63\t\t64240\t1460\t1\n'
            '192.168.1.4\t\t63\t\t64240\t1460\t1\n'
            '\t2001:db8::2\t\t127\t65535\t1440\t\n'
            'not-an-ip\t\t64\t\t1234\t1460\t1\n'), 'err': ''}
    monkeypatch.setattr(nd, '_run', run)

    result = nd._pcap_ethernet('/tmp/existing.pcap')

    assert result['vlan_frames'] == 3
    assert result['vlan_available'] and result['syn_available']
    assert result['vlans'] == [{'id': 10, 'frames': 2}, {'id': 20, 'frames': 2}]
    assert result['os_hints'][0]['ip'] == '192.168.1.4'
    assert result['os_hints'][0]['hint'] == 'Unix-like or appliance'
    assert result['os_hints'][0]['syns'] == 2
    assert result['os_hints'][1]['hint'] == 'Windows-like'
    assert len(calls) == 2
    assert all(argv[:5] == ['tshark', '-r', '/tmp/existing.pcap', '-c', '20000'] for argv in calls)


def test_pcap_ethernet_degrades_when_tshark_fields_fail(monkeypatch):
    monkeypatch.setattr(nd, '_run', lambda *args, **kwargs: {'rc': 2, 'out': '', 'err': 'field unavailable'})
    result = nd._pcap_ethernet('/tmp/existing.pcap')
    assert not result['vlan_available'] and not result['syn_available']
    assert result['vlans'] == [] and result['os_hints'] == []
