# Raspyjack payload integration audit

## Current integration, 2026-09-24

The older deployment notes below describe prior sessions, not the current Pi.
The Pi inspection found upstream `cf03b8a` with no Toolkit or Live Cameras panel;
the fork's `main` retains those features. This integration builds from that fork.

| Feature family | Current treatment |
| --- | --- |
| Live Cameras and Shodan | Restore existing fork implementations, preserving camera configuration and EnvManager key storage |
| Network scans, DNS, ping, TLS, interfaces, vulnerability checks, traffic captures | Keep Ragnar's native UI; hide duplicate Toolkit launchers, retain API compatibility |
| Passive Ethernet VLAN/OS observations | Extend the existing PCAP analysis and export |
| Port changes, LDAP/SMB listings, TCP jitter, MAC presence, USB insertion watch | Reuse the existing Toolkit job system |
| Honeypot | Add bounded HTTP and SSH/FTP banner decoys; events enter per-network loot and existing Watchtower |
| Payload IDE | Native Python editor, revision-checked library, validation, timed execution and cancellation; shared jobs/Files |
| Responder and replay | Preserve optional adapters with dependency checks and Ethernet-carrier gating; do not start them automatically |
| Wi-Fi, Bluetooth, SDR, vulnerability scans, directory enumeration | Keep existing Ragnar modules |
| HID/USB gadget, NFC, CC1101-specific payloads | Require hardware/configuration; not fabricated as working Pi 5 features |
| MAC spoofing, traffic shaping, stealth/log cleaning | Not imported: would alter management connectivity or Ragnar's retained history |
| BloodHound/AD collection and full 18-service RaspyJack honeypot | Not included in this integration; require separate dependency and credential/service designs |

## Historical audit

Reference: `7h30th3r0n3/Raspyjack`, local commit `6208a98` (2026-09-01).
The reference checkout was initially sparse: only `reconnaissance` and
`utilities` were present. The `usb`, `evasion`, `network`, `credentials`, and
other category trees were fetched on 2026-09-18. Earlier coverage estimates
that omitted those trees are incomplete.

| Raspyjack family | Ragnar status | Integration direction |
| --- | --- | --- |
| ARP host discovery, service scans, VLAN observation, PCAP analysis | Existing Network/Traffic/Toolkit plus the Pi 5 observation patch | Keep existing controls; no parallel scanners |
| Port-change checks, MS17-010 check, anonymous LDAP and SMB, TCP jitter, MAC lookup | Deployed to Pi 5 Toolkit | Use current Toolkit jobs and per-network loot |
| Gobuster directory enumeration | Existing `recon_engine.py` content discovery via `ffuf` | No second directory scanner |
| USB inventory and power draw | Existing `wardrive_diagnostics.py` | Keep existing diagnostics |
| BadUSB detector | USB insertion watch deployed | Timed HID/storage arrival detection; no keystroke collection |
| USB gadget HID, mass storage, Ethernet | Hardware unavailable in current setup | USB-C supplies Pi power and no UDC is present; requires a data-capable host connection and gadget setup |
| Responder | Deployed; upstream source installed | Selected wired interface, bounded analyze or explicit active job; `eth0` needs carrier before a live session |
| MAC randomization and fingerprint spoofing | Missing | Require interface state snapshot and automatic rollback; do not change management interface blindly |
| Timing evasion | Quiet pacing deployed in existing Service inventory | Per-job pacing avoids persistent `tc` changes |
| Traffic shaping | Missing | Needs reversible interface-specific `tc` state handling |
| Log cleaner / all-in-one stealth mode | Missing | Do not remove Ragnar logs or alter hostname while preserving live Pi state |
| Packet replay | Deployed; `tcpreplay` installed | Up to 200 packets from Toolkit-owned captures, 10 packets/second, connected wired interface only |
| Honeypot | Missing | Separate service with explicit ports, persistence, and conflict checks |
| Authenticated AD/BloodHound collection | Missing | Needs a credential input and storage design that does not put secrets in job reports |

The Pi 5 USB-C port supports device mode on current Raspberry Pi OS; USB-A
ports are host-only. Gadget setup may change the role of the USB-C port and
must be hardware-gated. See [Raspberry Pi's OTG mode documentation](https://pip-assets.raspberrypi.com/categories/685-app-notes-guides-whitepapers/documents/RP-009276-WP/Using-OTG-mode-on-Raspberry-Pi-SBCs).
