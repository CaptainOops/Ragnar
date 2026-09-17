# Dashboard Toolkit

The Toolkit tab adds headless utilities inspired by RaspyJack to Ragnar's web
dashboard. This branch builds on `feat/live-cams-panel`, preserving manual camera
sources, embeds and Camera Recon. It does not run RaspyJack's LCD/GPIO scripts.

## Included

| Capability | Ragnar integration |
| --- | --- |
| Shodan host lookup, search, account | Toolkit; configure your key in the tab |
| DNS and WHOIS | Toolkit; domain/IP input and saved output |
| Ping and traceroute | Toolkit; bounded probes |
| Ethernet addresses, routes, ARP/IPv6 neighbors | Toolkit; interface selection |
| Service discovery | Toolkit; one host, top 100 TCP ports, light Nmap detection |
| Packet capture | Toolkit; 5–120 seconds, 10,000 packets, 512-byte snapshots |
| Capture filters | All, DNS, DHCP, LLDP/CDP, mDNS/SSDP |
| PCAP inspection | Toolkit; first 200 packets from a saved capture |
| CCTV and public live feeds | Existing Live Cams tab, linked from Toolkit |
| Broader network/switch reconnaissance | Existing Network tab, linked from Toolkit |
| Traffic analysis | Existing Traffic Analysis tab, linked from Toolkit |

This is a curated integration, not a claim that every RaspyJack payload has been
ported. Existing Ragnar Wi-Fi, Bluetooth, SDR and vulnerability features remain
their own modules. No new credential interception or automatic exploitation is
added by Toolkit.

## Pi setup

On Raspberry Pi OS / Debian, install whichever optional utilities you need:

```sh
sudo apt install dnsutils whois iputils-ping traceroute iproute2 nmap tcpdump
```

The dashboard reports missing commands. Capture needs the service account to
already have packet-capture privileges; Toolkit does not invoke sudo or change
privileges. Ethernet utilities work with the selected interface (for example,
`eth0`). Switch ports ordinarily expose the Pi's own traffic and broadcast traffic;
seeing other ports requires an appropriately configured mirror port.

Set the Shodan key in Toolkit or `RAGNAR_SHODAN_API_KEY` in `.env`. The dashboard
never returns the key. API requests use indexed Shodan data, not its scan API.
Search access and query credits depend on your plan. Results can be older than
the host's current state. A private LAN IP cannot be used for Shodan host lookup.

## Jobs and loot

Two jobs can run at once. Commands use fixed argument lists without a shell.
Each job freezes the active network's `datastolendir` at submission and writes:

```
toolkit/<job-id>/report.json
toolkit/<job-id>/result.json       # successful structured result
toolkit/<job-id>/output.txt        # command output, when applicable
toolkit/<job-id>/capture.pcap      # packet capture, when applicable
```

Ragnar's existing Files/loot traversal picks these files up automatically. The
Toolkit lists the newest 100 jobs in the current network; older files remain in
loot. After switching networks, return to the originating network to find that
job's finished artifacts. Jobs are not resumed after service restart and appear
as interrupted. Stop requests terminate command processes; a pending Shodan
connection may take up to its HTTP timeout to notice cancellation.

PCAPs use truncated packet snapshots to keep captures small. Failed/cancelled
captures may still have a partial PCAP. Downloads are attachments; previews
render output as plain text. Routes inherit Ragnar's global authentication and
reject cross-origin browser mutations.

## Validation

```sh
python -m pytest tests/test_toolkit.py
node --check web/scripts/toolkit.js
```

Pi hardware, real Shodan credentials and actual capture permissions must be
verified on the target deployment. No keys or private camera URLs are bundled.
