# Dashboard Toolkit

The Toolkit tab adds headless utilities inspired by RaspyJack to Ragnar's web
dashboard. This branch builds on `feat/live-cams-panel`, preserving manual camera
sources, embeds and Camera Recon. It does not run RaspyJack's LCD/GPIO scripts.

## Included

| Capability | Ragnar integration |
| --- | --- |
| Shodan InternetDB | Free IPv4 lookup; no API key required |
| Shodan host lookup, search, account | Toolkit; configure your key in the tab |
| Shodan result count | Count matches without query credits |
| HTTP headers / TLS certificate | Toolkit; bounded curl / OpenSSL inspection |
| mDNS / Bonjour discovery | Toolkit; interface-scoped Avahi service listing |
| SMB share listing | Toolkit; anonymous listing without downloading files |
| DNS and WHOIS | Toolkit; domain/IP input and saved output |
| Ping and traceroute | Toolkit; bounded probes |
| Ethernet addresses, routes, ARP/IPv6 neighbors | Toolkit; interface selection |
| Service discovery | Toolkit; one host, top 100 TCP ports, light Nmap detection |
| Quiet service scan | Existing Service inventory job can pace probes for one host without changing interface settings |
| New-port check | Toolkit; compare one host's top 100 TCP ports against the prior per-network baseline |
| MS17-010 check | Toolkit; Nmap's targeted SMB detection script on one host |
| LDAP root discovery | Toolkit; anonymous RootDSE query on one host |
| SMB share crawl | Toolkit; anonymous listings of up to three shares, without downloading files |
| TCP latency / jitter | Toolkit; eight bounded connection samples to one host and port |
| MAC presence | Toolkit; read the selected interface's neighbor table for one MAC |
| USB insertion watch | Toolkit; timed watch for new HID and storage devices, without collecting serials or keystrokes |
| Packet capture | Toolkit; 5–120 seconds, 10,000 packets, 512-byte snapshots |
| Capture filters | All, DNS, DHCP, LLDP/CDP, mDNS/SSDP |
| PCAP inspection | Toolkit; first 200 packets from a saved capture |
| Packet replay | Toolkit; up to 200 packets from a saved Toolkit capture, 10 packets/second, connected wired interface only |
| Responder | Toolkit; selected wired interface, 5–120 seconds, passive analyze or explicit active mode |
| CCTV and public live feeds | Existing Live Cams tab |
| Broader network/switch reconnaissance | Existing Network tab |
| Traffic analysis | Existing Traffic Analysis tab |

This is a curated integration, not a claim that every RaspyJack payload has been
ported. Existing Ragnar Wi-Fi, Bluetooth, SDR and vulnerability features remain
their own modules. Responder defaults to analyze; active mode is an explicit
operator action. Nothing in Toolkit starts automatically.

## Integrated workspace (2026-09-24)

Every visible tool has a local quick guide alongside its controls: what it does,
three steps, an example when useful, result interpretation and a practical caveat.
The Payload IDE has its own expandable getting-started guide. Shodan key settings
are collapsible below the tool form. Guides never fill or submit targets; their
examples appear only as hints, and switching tools preserves typed input.
Content lives in `web/scripts/toolkit_guides.js`; the dashboard test checks guide
coverage against the backend catalog. Shodan entries link to its official API
reference. The guide UI makes no additional API requests.

Live Cameras retains existing saved feeds, categories, video wall and snapshot
storage. Shodan uses Ragnar's EnvManager for its key. No separate dashboard,
authentication system, network database or task queue is introduced.

The Toolkit launcher omits tools already owned by Network, Discovered, Advanced
Scan or Traffic: ping, traceroute, WHOIS, DNS, interface/neighbor inventory,
service scanning, TLS inspection, MS17 checks and capture/summary. Their old API
IDs remain compatible with saved jobs. Ethernet VLAN and tentative OS observations
extend the existing PCAP analyzer and its report, instead of adding another one.

**Honeypot:** select a local interface, port, profile and 5–3600-second duration.
HTTP returns a small 503 decoy page; SSH/FTP profiles send banners only (they do
not emulate full authenticated sessions). Ports default to 8088/2222/2121. A
busy port fails without touching its existing service. Up to 32 concurrent
connections and 1000 metadata events are retained per session; no request bodies
or passwords are collected. Results remain in `events.jsonl` and `result.json`.
First contact from each source in a session also writes a low-severity record
to `toolkit_honeypot.jsonl` in the configured Watchtower directory, using its
existing aggregation and notification settings. It does not enable Watchtower
or change those settings. Like other Watchtower sources, the first discovery of
the log starts tailing from its end; the job's full event history is always kept.

**Payload IDE:** save, load, delete, syntax-check and run Python scripts. Each
network has its own library (100 scripts, 64 KiB each). Revisions prevent silently
overwriting another editor's changes. A run freezes its source and network context
before the worker starts. `payload.py`, `context.json` and `output.txt` are job
artifacts, and custom files written to the job directory appear in Ragnar Files.
The environment supplies `RAGNAR_CONTEXT`, `RAGNAR_JOB_DIR`, `RAGNAR_LOOT_DIR`.
Payloads run as the Ragnar service user: this is trusted administrator code,
not a sandbox. Runs have a 5–120-second timeout, capped standard output and Stop;
Linux process groups are terminated to clean up normal child processes.

Both features use the existing two-job limit and per-network loot. Timed listeners
are stopped on restart and recorded as interrupted, rather than restarting
unexpectedly. Wired-only replay and Responder still require Ethernet carrier.

Build a version-specific deployment bundle with
`python scripts/package_toolkit_update.py --base INSTALLED_COMMIT --output toolkit.zip`.
Extract it on the Pi, run `python3 deploy_toolkit_bundle.py` to check, then add
`--apply` to back up/install/restart. Every destination is checked against the
base hash; conflicting local edits stop the entire update. Failed health checks
restore the previous files. Configuration, camera lists, network data and Wi-Fi
drivers are not replaced.

## Pi setup

On Raspberry Pi OS / Debian, install whichever optional utilities you need:

```sh
sudo apt install dnsutils whois iputils-ping traceroute iproute2 nmap tcpdump curl openssl avahi-utils smbclient ldap-utils
```

The dashboard reports missing commands. Capture needs the service account to
already have packet-capture privileges; Toolkit does not invoke sudo or change
privileges. Ethernet utilities work with the selected interface (for example,
`eth0`). Switch ports ordinarily expose the Pi's own traffic and broadcast traffic;
seeing other ports requires an appropriately configured mirror port.

Responder is an optional external dependency. Install the upstream
`lgandx/Responder` source at `/opt/ragnar-responder` (or set
`RAGNAR_RESPONDER_DIR` for the service), including `Responder.py`,
`Responder.conf`, and `settings.py`. Toolkit copies it to a temporary job
directory so each run's logs can be kept in that network's loot, then stops the
process at the selected duration. Analyze mode is the default. Both modes
require a connected wired interface; Toolkit will not run them over `wlan0`.

InternetDB works immediately without a key. For full Shodan access, set the key
in Toolkit or `RAGNAR_SHODAN_API_KEY` in `.env`. Saving through Toolkit verifies
the key against `/api-info` before replacing a previous key. The dashboard
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
python -m pytest tests/test_toolkit.py tests/test_livecams_integration.py
npm install
npm run test:dashboard
node --check web/scripts/toolkit.js
python scripts/toolkit_smoke.py --live
```

The smoke test uses a temporary directory and never imports Ragnar's hardware
stack or changes its running configuration. Full Shodan credentials and actual
capture permissions still need verification on the target deployment.

## Camera compatibility review (2026-09-17)

Integrated camera commits through `1e474c0` (YouTube channel resolution), including
category filters, fullscreen, video wall, drag reordering and snapshot-to-loot.
Fixed category buttons containing quotes, refreshing expanded/wall snapshots,
hidden-tab stream cleanup, duplicate reorder IDs, snapshot filename collisions,
PNG/WebP/GIF extensions and freezing snapshot storage before network changes.
Camera configuration and its existing scan-results directory are preserved.

Source mapping reviewed against RaspyJack `6208a982`:
`shodan_query.py` → InternetDB; `curly.py` → HTTP headers (HEAD only);
`cert_scanner.py` → one-host TLS inspection; `mdns_scanner.py` → Avahi discovery;
`smb_probe.py` → anonymous share listing; `whois_lookup.py` → WHOIS;
`pcap_analyzer.py` → bounded PCAP summary. These are native integrations of the
underlying utilities, not full copies of every upstream payload mode.

Validation completed for this integration: 26 Python tests (including real
authentication-hook coverage), two DOM interaction tests, Python compilation
and JavaScript syntax checks. On the Pi 5, isolated smoke jobs completed for
InternetDB, DNS, HTTP headers, TLS certificates, loopback ping and interface
inventory. Full Shodan search remains unverified with a live key; none was
configured. Avahi and smbclient were not installed, and privileged PCAP capture
was not run. The running Pi checkout contains local changes and was not updated
or restarted during this review; deployment must preserve those changes.

## Deployment verification

Deployed the targeted integration over the Pi's local edits with backups under
`/home/ragnar/ragnar-backups/toolkit-20260917T231942Z`. The live dashboard is served
as static HTML, so Toolkit markup is embedded directly in `index_modern.html`.
DOM tests now use that file without expanding any template directives.

Verified the live Toolkit tab in a browser, all 18 existing camera records,
InternetDB lookup, a five-second DNS-only loopback PCAP, its summary, and artifact
downloads through the running service. Full Shodan access awaits a user-supplied
API key. Optional Avahi/SMB utilities need `avahi-utils` and `smbclient`.
