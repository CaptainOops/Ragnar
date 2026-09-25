# Toolkit verification — 24 September 2026

Verified on the user's Raspberry Pi 5. These results distinguish a successful
command path from checks requiring another server, hardware, or an account.

| Tool | Result and scope |
| --- | --- |
| Honeypot | HTTP loopback response, recorded connection, port-conflict handling and shutdown passed. Dashboard result preview verified. SSH and FTP banner responses and shutdown also passed live loopback checks. |
| Payload IDE / saved payload | Python validation, saved execution and output artifact passed. UI save-before-run regression passed. |
| Shodan InternetDB | Public 1.1.1.1 lookup completed. |
| Shodan host, search, account, count | Not live-verified: no configured API key. Setup gating remains enabled. |
| HTTP headers | Temporary loopback HTTP server returned the expected custom header. Existing user's result visibly previewed in browser. |
| TLS certificate (native Network tool) | Temporary loopback TLS server handshake and PEM certificate artifact passed. |
| mDNS | Fixed unsupported Avahi interface flag. Real wlan0 discovery completed both through the runner and dashboard. Returned records are filtered by interface; Avahi itself browses all active interfaces. |
| SMB share listing / anonymous crawl | Client installed; no known anonymous SMB server fixture available. Successful server interaction is unverified. |
| LDAP RootDSE | Client installed; no known LDAP server fixture available. Successful server interaction is unverified. |
| DNS / WHOIS | Public example.com queries completed. |
| Reachability / route trace | Loopback command paths completed. |
| Interface inventory / neighbors | Actual host inventory and wlan0 neighbor reads completed. |
| Service inventory / new-port check | Loopback Nmap commands and parsing completed; baseline changes also have automated tests. |
| MS17-010 check | Detection script command completed against loopback. No vulnerable SMB server was used; positive detection is unverified. |
| TCP latency / jitter | Eight samples against a temporary loopback HTTP listener completed. |
| MAC presence | Loopback neighbor-table lookup completed with absent MAC; positive matching has automated coverage. |
| USB insertion watch | Timed live sysfs watch completed. Physical insertion was not exercised. |
| Capture / capture summary | Bounded loopback DNS capture and subsequent PCAP read completed. This verifies an empty capture path, not packet contents. |
| Packet replay | Not transmitted: requires connected Ethernet and an isolated destination. Wired-interface/limits regression checks passed. |
| Responder | Not launched: Ethernet disconnected. Wi-Fi is now rejected before creating a failed job, with an explanation in the launcher. |

The standard display pipeline (including this Pi's configured ILI9486 panel)
shows transient Toolkit activity in the existing screen frame and web mirror.
The generated physical frames were inspected during a running loopback honeypot and after a USB watch completed.
The strip expires 20 seconds after the last job finishes and preserves native
orchestrator state. Concurrent jobs, terminal states and expiry have unit coverage.
Dedicated OLED/round-display loops are outside this display change.

Preview now focuses and scrolls to the result, identifies the tool and artifact,
and displays loading/fetch errors in place. Output remains plain text. Older
failed jobs stay in history; rerunning mDNS creates a new successful record.

Reproduce the passive/loopback audit with `sudo python3 scripts/audit_toolkit.py`.
The honeypot smoke check is `python3 scripts/toolkit_native_smoke.py`.
Audit scripts use temporary loot and do not replace the user's job history.
