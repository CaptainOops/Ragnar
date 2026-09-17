# Credits & Attribution

Ragnar is supported by people's work. This file records, in more detail than the
[README credits table](../README.md#-credits--attribution), the people whose research and
engineering make Ragnar possible.

## Solarflere — the CVE research behind the passive detection suite

Every CVE that Ragnar's passive watchers and vendor guards can detect was identified,
researched and curated by **[Solarflere](https://www.instagram.com/solarflere)**, who
co-authors the [Authority Verification](nettools.md) suite (Diagnostics, Switch &
L2/L3, Interfaces). Ragnar turns that research into detectors — the vulnerability corpus
behind them is Solarflere's work.

### By the numbers

- **~145 CVEs actively detected.** 147 distinct CVE IDs are named across the detector code;
  145 are actively detected.
- **24 years of coverage** — from **CVE-2002-1623** to **CVE-2026-7668**.
- Weighted to the current threat wave: **29 CVEs from 2023, 37 from 2024, 22 from 2025, and
  7 already from 2026.**
- Spanning **~40 passive detectors** from L2 to L7 plus the timing- and forwarding-plane
  watchers (BFD, PTP, SR-MPLS) and the **IPsec/IKE** key-exchange posture detector, **six
  in-app vendor CVE guards** (Cisco, Juniper, Arista, Comware, MikroTik, Aruba) and **Dell
  Guard** as a standalone daemon.
- **Cross-protocol crypto-attack coverage** — the same cryptographic weaknesses are named
  everywhere they appear: **SWEET32** (CVE-2016-2183) in TLS, SSH and IKE; **D(HE)at**
  (CVE-2002-20001 / CVE-2022-40735 / CVE-2024-41996) across TLS, SSH and IPsec; and
  **Logjam / weak-DH** (CVE-2015-4000) in IKE.
- **DNS / DNSSEC** — a passive DNS-response detector for **KeyTrap** (CVE-2023-50387),
  **NSEC3** DoS (CVE-2023-50868), **NXNSAttack** (CVE-2020-8616), **MaginotDNS**
  cache-poisoning (CVE-2021-25220), **DNSBomb** (CVE-2024-33655) and **SAD DNS**
  (CVE-2020-25705), plus KeyTrap/NSEC3 posture folded into the active DNS Doctor.

_(Counts reflect the detector code as of September 2026 and grow as new modules land.)_

### What makes these detections different

- **100% passive — detection-only.** Ragnar never transmits, probes, scans or authenticates.
  Every CVE above is caught by observing traffic that is already on the wire. In the
  standalone daemons this is enforced twice over: an AST guard that rejects any
  transmit-shaped call in the module itself, and the kernel
  (`RestrictAddressFamilies` + `IPAddressDeny=any`), so the process cannot open an IP socket
  even if the code were changed.
- **Structural anomaly bounds, not exploit signatures.** Thresholds are measured against real
  traffic rather than copied from a published proof-of-concept, so variants and evasion
  attempts are still caught — and several detections are zero-false-positive by construction
  (a labelled MPLS frame on a customer port simply should not exist).
- **Three honest evidence classes.** Every finding is *posture* (a version/platform
  fingerprint screened against the catalog — always "verify **this** device," never a
  vulnerable/not-vulnerable verdict), *exposure* (an enabling condition visible on the wire)
  or *attack* (an exploitation primitive observed in transit).
- **Runs on a Raspberry Pi Zero 2 W.** Everything is built to a resource floor that cheap,
  low-power hardware can sustain.
- **Privacy by design.** Credential material is never logged — for example, RADIUS
  Proxy-State is compared by digest and the values are discarded.

Every classifier is validated offline by the 42-suite **Detector Self-Test**, which runs each
detector against crafted attack captures with no root and no live traffic.

Thank you, Solarflere. 🙏
