"""
Finding-code registry for DNS Doctor's PASSIVE tier.

Single source of truth for codes, names, severities and confidence
tiers. Every detector constructs findings through finding() rather
than hand-rolling a dict, so severity and confidence cannot drift
between call sites. readme_verify.py asserts the README's tables
stay in sync with this dict.

WHY A SEPARATE CODE PREFIX (DNSD- not DNS-): DNS Doctor's existing
ACTIVE tier owns DNS-001..DNS-102 -- probe-based checks that generate
their own queries. This tier is capture-based and transmits nothing.
Sharing a prefix would make "DNS-0xx" ambiguous about whether the
module spoke on the wire to produce it, which is exactly the property
an operator needs to know at a glance. Separate prefix, separate
registry, no collisions.

Code ranges by detector class:
  001-009  structural record analysis (KeyTrap, NXNSAttack, MaginotDNS, TuDoor)
  010-019  parameter / posture checks (NSEC3 iterations, algorithm downgrade)
  020-029  behavioural flood detection (DNSBomb, NSEC3 encloser, water torture)
  030-039  response integrity (SAD DNS)

CONFIDENCE is separate from SEVERITY on purpose (LESSON T): severity
says how bad it would be if real, confidence says how sure the wire
evidence is. A LOW-confidence finding is never allowed to carry a
critical severity.
"""

# confidence -> the highest severity that confidence tier may carry.
# Enforced by _validate() at import time.
CONFIDENCE_SEVERITY_CAP = {
    "high":   "critical",
    "medium": "warning",
    "low":    "notice",
}

_SEVERITY_ORDER = {"notice": 0, "warning": 1, "critical": 2}

FINDINGS = {
    # --- structural record analysis -------------------------------
    "DNSD-001": {
        "name": "KEYTRAP_DNSKEY_COLLISION", "severity": "critical", "confidence": "high",
        "cve": "CVE-2023-50387", "klass": "structural", "stateful": False,
        "desc": "Multiple DNSKEY records share one key tag -- the KeyTrap colliding-key-tag signature, which forces a validator into quadratic signature verification",
    },
    "DNSD-002": {
        "name": "KEYTRAP_RRSIG_BURST", "severity": "critical", "confidence": "high",
        "cve": "CVE-2023-50387", "klass": "structural", "stateful": False,
        "desc": "One RRset carries an abnormal number of RRSIGs -- the other half of the KeyTrap work-amplification pair",
    },
    "DNSD-003": {
        "name": "KEYTRAP_CRYPTO_FAILURES", "severity": "critical", "confidence": "high",
        "cve": "CVE-2023-50387", "klass": "structural", "stateful": False,
        "desc": "DNSKEY and RRSIG counts together imply a validator must attempt an excessive number of signature verifications for one response",
    },
    "DNSD-004": {
        "name": "NXNSATTACK_DELEGATION_OVERFLOW", "severity": "warning", "confidence": "medium",
        "cve": "CVE-2020-8616", "klass": "structural", "stateful": False,
        "desc": "Referral carries many NS records with no glue, and the NS targets are out of bailiwick -- the NXNSAttack referral-amplification shape",
    },
    "DNSD-005": {
        "name": "NXNSATTACK_BURST_CORRELATION", "severity": "critical", "confidence": "high",
        "cve": "CVE-2020-8616", "klass": "structural", "stateful": True,
        "desc": "Several glueless out-of-bailiwick referrals for one zone inside a short window -- referral amplification in progress, not a single odd response",
    },
    "DNSD-006": {
        "name": "MAGINOTDNS_OUT_OF_BAILIWICK", "severity": "critical", "confidence": "high",
        "cve": "CVE-2021-25220", "klass": "structural", "stateful": False,
        "desc": "Response carries an authority or additional record outside the queried zone's bailiwick -- cache-poisoning record injection",
    },
    "DNSD-007": {
        "name": "TUDOOR_MALFORMED_PACKET", "severity": "notice", "confidence": "low",
        "cve": "TuDoor (CVE-2024 cluster)", "klass": "structural", "stateful": False,
        "desc": "DNS response is structurally malformed (truncated record, bad rdlength, illegal name encoding) -- informational; malformed responses are common on real networks",
    },

    # --- parameter / posture --------------------------------------
    "DNSD-010": {
        "name": "NSEC3_ITERATION_RFC_VIOLATION", "severity": "warning", "confidence": "high",
        "cve": "CVE-2023-50868", "klass": "posture", "stateful": False,
        "desc": "NSEC3 iteration count is above the RFC 9276 ceiling of 0 -- extra iterations are pure validator CPU cost with no security benefit",
    },
    "DNSD-011": {
        "name": "DNSSEC_ALGO_UNSUPPORTED", "severity": "warning", "confidence": "medium",
        "cve": None, "klass": "posture", "stateful": False,
        "desc": "Response is signed with a DNSSEC algorithm the validator cannot verify, AD is clear, and no SERVFAIL was returned -- a silent validation downgrade",
    },

    # --- behavioural flood (baseline-dependent) -------------------
    "DNSD-020": {
        "name": "DNSBOMB_SHORT_TTL_BURST", "severity": "warning", "confidence": "medium",
        "cve": "CVE-2024-33655", "klass": "behavioural", "stateful": True,
        "desc": "Short-TTL answers for one zone arriving far above that zone's learned rate -- the DNSBomb pulsing-amplification accumulation phase",
    },
    "DNSD-021": {
        "name": "NSEC3_ENCLOSER_ATTACK", "severity": "warning", "confidence": "medium",
        "cve": "CVE-2023-50868", "klass": "behavioural", "stateful": True,
        "desc": "High NSEC3 iteration count combined with many NSEC3 RRs per response and a random-subdomain query flood -- the closest-encloser CPU-exhaustion pattern",
    },
    "DNSD-022": {
        "name": "WATER_TORTURE_FLOOD", "severity": "warning", "confidence": "medium",
        "cve": None, "klass": "behavioural", "stateful": True,
        "desc": "Random-subdomain NXDOMAIN rate for one zone far above its learned baseline -- pseudo-random subdomain (water torture) attack",
    },

    # --- response integrity ---------------------------------------
    "DNSD-030": {
        "name": "SAD_DNS_DUPLICATE_CONFLICT", "severity": "critical", "confidence": "high",
        "cve": "CVE-2020-25705", "klass": "integrity", "stateful": True,
        "desc": "Two responses to one outstanding query carry conflicting answers -- a forged response raced the legitimate one",
    },
    "DNSD-031": {
        "name": "SAD_DNS_SOURCE_PORT_ENTROPY_LOW", "severity": "notice", "confidence": "low",
        "cve": "CVE-2020-25705", "klass": "integrity", "stateful": True,
        "desc": "Outbound query source ports show low entropy -- port prediction is easier than it should be; posture only, not evidence of an attack",
    },
}

# Codes whose detector needs a LEARNED per-zone baseline before it can
# say anything. Gated at runtime (see state.py / detect.py) because
# Ragnar's grab-and-go deployment model cannot assume warmup time.
BASELINE_DEPENDENT = {"DNSD-020", "DNSD-021", "DNSD-022"}


def _validate():
    """Import-time structural guard. A registry that contradicts its
    own confidence/severity contract is a bug that should never reach
    a test tier, let alone the wire."""
    seen_names = set()
    for code, m in FINDINGS.items():
        assert m["severity"] in _SEVERITY_ORDER, f"{code}: bad severity"
        assert m["confidence"] in CONFIDENCE_SEVERITY_CAP, f"{code}: bad confidence"
        cap = CONFIDENCE_SEVERITY_CAP[m["confidence"]]
        assert _SEVERITY_ORDER[m["severity"]] <= _SEVERITY_ORDER[cap], (
            f"{code}: confidence '{m['confidence']}' caps severity at '{cap}' "
            f"but the registry says '{m['severity']}' (LESSON T)"
        )
        assert m["name"] not in seen_names, f"{code}: duplicate name {m['name']}"
        seen_names.add(m["name"])
        assert m["klass"] in ("structural", "posture", "behavioural", "integrity")
    assert BASELINE_DEPENDENT <= set(FINDINGS), "BASELINE_DEPENDENT names an unknown code"


_validate()


def finding(code, zone, detail, evidence=None):
    """Build a standard finding. `evidence` carries the raw numbers an
    operator needs to judge it (DNSKEY count, iteration value, baseline
    ratio) -- the FP-mitigation strategy is that every MEDIUM/HIGH
    finding is reviewable without going back to the pcap."""
    if code not in FINDINGS:
        raise KeyError(f"unknown finding code: {code}")
    m = FINDINGS[code]
    return {
        "code": code,
        "name": m["name"],
        "severity": m["severity"],
        "confidence": m["confidence"],
        "klass": m["klass"],
        "cve": m["cve"],
        "zone": zone,
        "detail": detail,
        "evidence": evidence or {},
    }
