"""
The fourteen detectors, grouped by class.

Every detector is a PURE function of (message, context) -> list of
findings. No I/O, no sockets, no clock reads except the `now` passed
in. That is what lets conformance.py drive all of them exhaustively
offline, and it is why the stateful ones take their state object as
an argument rather than reaching for a global.

Split by cost, because the Pi Zero 2W runs these at line rate:
  - STRUCTURAL / POSTURE / INTEGRITY-per-packet run on the critical
    path. All are O(records in the message).
  - BEHAVIOURAL update ring buffers and read EMAs. Also O(1) amortised,
    but gated behind baseline warmth (see state.py).
"""
from collections import Counter, defaultdict

import parse
from bailiwick import in_bailiwick, normalize, out_of_bailiwick_rrs
from findings import finding, BASELINE_DEPENDENT


def _question(msg):
    return msg.questions[0] if msg.questions else None


def _qname_text(msg):
    q = _question(msg)
    return q["name"].text() if q else "."


# ======================================================================
# STRUCTURAL
# ======================================================================

def detect_keytrap(msg, cfg, zone):
    """
    CVE-2023-50387. Three independent signatures, three codes.

    The attack makes a validator do O(keys x signatures) crypto for one
    response. All three inputs are visible in the record counts, so
    this needs no state and no baseline -- which is why it survives
    the grab-and-go constraint that kills the behavioural detectors.
    """
    out = []
    dnskeys = [r for r in msg.all_rrs() if r.rtype == parse.T_DNSKEY]
    rrsigs = [r for r in msg.all_rrs() if r.rtype == parse.T_RRSIG]

    # DNSD-001: colliding key tags.
    # Key tags are a 16-bit checksum over the key, so among a handful
    # of legitimately-rotated keys a collision is genuinely rare.
    # Deliberately counts DISTINCT keys per tag, not records per tag:
    # the same key appearing twice is a duplicate record, not a
    # collision, and must not fire.
    if dnskeys:
        by_tag = defaultdict(set)
        for r in dnskeys:
            tag = r.parsed.get("key_tag")
            if tag is not None:
                by_tag[tag].add(bytes(r.rdata))
        for tag, keys in by_tag.items():
            if len(keys) >= cfg.keytrap_dnskey_collisions:
                out.append(finding(
                    "DNSD-001", zone,
                    f"{len(keys)} distinct DNSKEYs share key tag {tag} -- a validator "
                    f"must try every one of them against each signature",
                    {"key_tag": tag, "colliding_keys": len(keys),
                     "dnskey_count": len(dnskeys), "qname": _qname_text(msg)},
                ))

    # DNSD-002: many RRSIGs over ONE RRset.
    # Grouped by (owner, type covered) because a response legitimately
    # carries several RRSIGs across DIFFERENT RRsets during a rollover;
    # what is not legitimate is many signatures over the same RRset.
    if rrsigs:
        groups = Counter()
        for r in rrsigs:
            groups[(tuple(normalize(r.name)), r.parsed.get("type_covered"))] += 1
        for (owner, covered), n in groups.items():
            if n >= cfg.keytrap_rrsig_per_rrset:
                oname = b".".join(owner).decode("ascii", "replace") or "."
                out.append(finding(
                    "DNSD-002", zone,
                    f"{n} RRSIGs cover one RRset ({oname} type {covered}) -- "
                    f"each one forces another verification attempt",
                    {"rrsig_count": n, "owner": oname, "type_covered": covered,
                     "qname": _qname_text(msg)},
                ))

    # DNSD-003: the work PRODUCT, which is the actual KeyTrap primitive.
    # Either factor alone can look ordinary; their product is the cost.
    if dnskeys and rrsigs:
        product = len(dnskeys) * len(rrsigs)
        if product >= cfg.keytrap_crypto_product:
            out.append(finding(
                "DNSD-003", zone,
                f"{len(dnskeys)} DNSKEYs x {len(rrsigs)} RRSIGs = up to {product} "
                f"signature verifications for a single response",
                {"dnskey_count": len(dnskeys), "rrsig_count": len(rrsigs),
                 "verifications": product, "qname": _qname_text(msg)},
            ))
    return out


def _referral_shape(msg, cfg):
    """
    Returns (is_glueless_referral, ns_records, glue_count, oob_targets)
    for NXNSAttack analysis.

    A referral is: no answer records, NS records in authority.
    """
    if msg.answers:
        return (False, [], 0, [])
    ns = [r for r in msg.authority if r.rtype == parse.T_NS]
    if not ns:
        return (False, [], 0, [])

    q = _question(msg)
    zone_name = q["name"] if q else None

    targets = []
    for r in ns:
        t = r.parsed.get("target")
        if t is not None:
            targets.append(t)

    # Glue = an address record in additional whose owner is one of the
    # NS targets.
    target_set = {tuple(normalize(t)) for t in targets}
    glue = 0
    for r in msg.additional:
        if r.rtype in (parse.T_A, parse.T_AAAA):
            if tuple(normalize(r.name)) in target_set:
                glue += 1

    # Out-of-bailiwick TARGETS are what the victim resolver must chase.
    oob = []
    if zone_name is not None:
        for t in targets:
            if not in_bailiwick(t, zone_name):
                oob.append(t)
    return (True, ns, glue, oob)


def detect_nxnsattack(msg, cfg, zone, zstate=None, now=None):
    """
    CVE-2020-8616 family. Referral amplification: a malicious
    authoritative returns many NS records, all out of bailiwick, none
    with glue, so the victim resolver fires one lookup per name.

    THE FALSE-POSITIVE CONTROL THAT MATTERS: delegating to a
    third-party DNS provider produces out-of-bailiwick NS targets with
    no glue, and that is completely normal -- it describes most of the
    internet (Cloudflare, Route 53, any managed DNS). What is NOT
    normal is the COUNT. Ordinary delegations carry 2-6 NS records.
    The threshold, not the shape, is the discriminator.
    """
    is_referral, ns, glue, oob = _referral_shape(msg, cfg)
    if not is_referral:
        return []

    out = []
    if (len(ns) >= cfg.nxns_min_ns and glue == 0 and len(oob) >= cfg.nxns_min_ns):
        out.append(finding(
            "DNSD-004", zone,
            f"referral carries {len(ns)} NS records, {len(oob)} of them out of "
            f"bailiwick, with zero glue -- each one costs the resolver a fresh lookup",
            {"ns_count": len(ns), "out_of_bailiwick": len(oob), "glue_count": glue,
             "qname": _qname_text(msg)},
        ))

        # DNSD-005: the same shape repeating for one zone inside a
        # short window. This is the HIGH-confidence leg: one odd
        # referral is a curiosity, several in 100 ms is an attack in
        # progress. Window-based, NOT baseline-learned, so it is
        # grab-and-go safe.
        if zstate is not None and now is not None:
            zstate.push("referral_times", now, cfg.ring_size)
            n = zstate.rate_in_window(zstate.ring("referral_times", cfg.ring_size, create=False),
                                      cfg.nxns_window_seconds)
            if n >= cfg.nxns_min_referrals:
                out.append(finding(
                    "DNSD-005", zone,
                    f"{n} glueless out-of-bailiwick referrals for this zone within "
                    f"{cfg.nxns_window_seconds * 1000:.0f} ms -- referral amplification in progress",
                    {"referrals_in_window": n,
                     "window_ms": cfg.nxns_window_seconds * 1000,
                     "ns_count": len(ns), "qname": _qname_text(msg)},
                ))
    return out


def detect_maginotdns(msg, cfg, zone):
    """
    CVE-2021-25220 family. Cache-poisoning by smuggling records for a
    zone the responder has no authority over.

    THE FALSE-POSITIVE CONTROL: an out-of-bailiwick record in the
    ADDITIONAL section is usually legitimate glue for a third-party
    nameserver, which is everywhere. So additional-section records are
    only reported when they are NOT plausible glue -- i.e. their owner
    is not the target of any NS record in the authority section.
    Authority-section records outside the zone have no such excuse and
    are reported directly.
    """
    q = _question(msg)
    if q is None:
        return []
    zone_name = q["name"]

    ns_targets = set()
    for r in msg.authority:
        if r.rtype == parse.T_NS:
            t = r.parsed.get("target")
            if t is not None:
                ns_targets.add(tuple(normalize(t)))

    suspicious = []
    for rr in out_of_bailiwick_rrs(msg, zone_name):
        if rr.section == "additional":
            if tuple(normalize(rr.name)) in ns_targets:
                continue  # plausible glue for a delegation in this response
            if rr.rtype not in (parse.T_A, parse.T_AAAA, parse.T_CNAME,
                                parse.T_NS, parse.T_DNSKEY, parse.T_RRSIG):
                continue  # only report record types that can poison a cache
        suspicious.append(rr)

    if not suspicious:
        return []
    names = sorted({r.name.text() for r in suspicious})[:5]
    return [finding(
        "DNSD-006", zone,
        f"{len(suspicious)} record(s) outside the queried zone's bailiwick and not "
        f"explainable as delegation glue: {', '.join(names)}",
        {"count": len(suspicious), "names": names, "qzone": zone_name.text(),
         "sections": sorted({r.section for r in suspicious})},
    )]


def detect_tudoor(msg, cfg, zone):
    """
    The TuDoor CVE cluster is ~33 CVEs across many resolvers, all
    reached through malformed or unexpected response packets. Passive
    detection cannot tell which one (or whether the target resolver is
    even vulnerable), so this is ONE generic informational code rather
    than 33 codes claiming precision that isn't there -- the same
    reasoning that caps sshwatch's regreSSHion posture at notice.
    """
    if not msg.malformed:
        return []
    return [finding(
        "DNSD-007", zone,
        f"malformed DNS message: {msg.malformed_reason}",
        {"reason": msg.malformed_reason, "txid": msg.txid,
         "qname": _qname_text(msg)},
    )]


# ======================================================================
# POSTURE
# ======================================================================

def detect_nsec3_iterations(msg, cfg, zone):
    """
    CVE-2023-50868 / RFC 9276. Iterations above 0 buy no security and
    cost the validator a hash chain per lookup. This is a POSTURE
    finding about the zone being served, not an attack in progress.
    """
    out = []
    worst = None
    for rr in msg.all_rrs():
        if rr.rtype != parse.T_NSEC3:
            continue
        it = rr.parsed.get("iterations")
        if it is None:
            continue
        if it > cfg.nsec3_max_iterations and (worst is None or it > worst):
            worst = it
    if worst is not None:
        out.append(finding(
            "DNSD-010", zone,
            f"NSEC3 iteration count {worst} exceeds the RFC 9276 ceiling of "
            f"{cfg.nsec3_max_iterations} -- pure validator CPU cost, no added security",
            {"iterations": worst, "rfc9276_max": cfg.nsec3_max_iterations,
             "qname": _qname_text(msg)},
        ))
    return out


def detect_algo_downgrade(msg, cfg, zone):
    """
    A signed response using an algorithm the validator cannot verify,
    where AD is clear and the resolver did NOT SERVFAIL, means
    validation was silently skipped rather than failed.

    FP control: an UNSIGNED delegation looks similar from the outside,
    so this requires an actual RRSIG or DNSKEY carrying the unsupported
    algorithm -- absence of signatures is not evidence of downgrade.
    """
    algos = set()
    for rr in msg.all_rrs():
        if rr.rtype in (parse.T_RRSIG, parse.T_DNSKEY):
            a = rr.parsed.get("algorithm")
            if a is not None:
                algos.add(a)
    if not algos:
        return []
    unsupported = {a for a in algos
                   if a not in parse.SUPPORTED_ALGOS}
    if not unsupported:
        return []
    if msg.ad:
        return []      # validator says it authenticated -- nothing skipped
    if msg.rcode == 2:
        return []      # SERVFAIL: it failed loudly, which is correct behaviour

    deprecated = sorted(unsupported & parse.DEPRECATED_ALGOS)
    unknown = sorted(unsupported - parse.DEPRECATED_ALGOS)
    return [finding(
        "DNSD-011", zone,
        f"signed with algorithm(s) {sorted(unsupported)} that a modern validator "
        f"cannot verify, AD is clear and the response is not SERVFAIL -- validation "
        f"was skipped rather than failed",
        {"algorithms": sorted(unsupported), "deprecated": deprecated,
         "unknown": unknown, "ad": msg.ad, "rcode": msg.rcode,
         "qname": _qname_text(msg)},
    )]


# ======================================================================
# BEHAVIOURAL (baseline-dependent -- gated, see state.py)
# ======================================================================

def _baseline_gate(cfg, zstate, baseline_name, now):
    """
    THE grab-and-go gate. Returns the baseline only if behavioural
    detection is enabled AND this zone's baseline is warm. Every
    behavioural detector goes through here; none can emit without it.
    """
    if not cfg.enable_baseline_detectors:
        return None
    b = zstate.baseline(baseline_name)
    if not b.is_warm(cfg, now):
        return None
    return b


def _random_subdomain_ratio(zstate, cfg):
    """
    Fraction of recently-seen first labels for this zone that are
    distinct. A pseudo-random subdomain flood approaches 1.0; ordinary
    traffic to a real site repeats www/mail/api and sits far lower.
    Uses hashes, never the labels themselves -- a passive sensor has
    no business retaining queried hostnames.
    """
    ring = zstate.ring("subdomain_hashes", cfg.ring_size, create=False)
    if len(ring) < 8:
        return 0.0
    return len(set(ring)) / float(len(ring))


def detect_dnsbomb(msg, cfg, zone, zstate, now):
    """
    CVE-2024-33655. DNSBomb accumulates short-TTL queries and releases
    them as a pulse. The accumulation phase is what is visible
    passively: short-TTL answers for one zone far above its norm.
    """
    ttls = [rr.ttl for rr in msg.answers]
    if not ttls:
        return []
    short = [t for t in ttls if t <= cfg.short_ttl_seconds]
    if not short:
        return []

    zstate.push("short_ttl_times", now, cfg.ring_size)
    rate = zstate.rate_in_window(
        zstate.ring("short_ttl_times", cfg.ring_size, create=False), 1.0)

    b = _baseline_gate(cfg, zstate, "bl_short_ttl_ratio", now)
    if b is None:
        # Not warm (or disabled): still LEARN, never EMIT.
        zstate.baseline("bl_short_ttl_ratio").update(rate, now, cfg)
        return []
    exceeded = b.exceeds(rate, cfg)
    baseline_value = b.value
    if not exceeded:
        b.update(rate, now, cfg)
        return []
    # DELIBERATELY do NOT fold an anomalous sample back into the
    # baseline. Updating unconditionally lets the baseline CHASE the
    # attack: a ramping flood raises the threshold as fast as it raises
    # the signal and never trips. Caught by conformance -- the warm
    # 5x-burst case silently produced nothing, because by the time the
    # rate reached 40/s the baseline it was compared against had been
    # dragged up by the same 40 samples. Freeze while anomalous.
    return [finding(
        "DNSD-020", zone,
        f"short-TTL answer rate {rate}/s is {rate / max(baseline_value, 1e-9):.1f}x this "
        f"zone's learned baseline of {baseline_value:.2f}/s",
        {"rate": rate, "baseline": round(baseline_value, 3),
         "factor": cfg.baseline_deviation_factor, "min_ttl": min(short),
         "qname": _qname_text(msg)},
    )]


def detect_nsec3_encloser(msg, cfg, zone, zstate, now):
    """
    CVE-2023-50868, behavioural leg. The closest-encloser attack needs
    THREE things together: a high iteration count, many NSEC3 records
    per response, and a random-subdomain flood driving them. Any one
    alone is ordinary; the conjunction is the attack.
    """
    nsec3 = [rr for rr in msg.all_rrs() if rr.rtype == parse.T_NSEC3]
    if len(nsec3) < cfg.nsec3_encloser_min_rrs:
        return []
    iters = max((r.parsed.get("iterations") or 0) for r in nsec3)
    if iters <= cfg.nsec3_max_iterations:
        return []

    ratio = _random_subdomain_ratio(zstate, cfg)
    b = _baseline_gate(cfg, zstate, "bl_nxdomain_ratio", now)
    if b is None:
        return []
    if ratio < 0.9:
        return []
    return [finding(
        "DNSD-021", zone,
        f"{len(nsec3)} NSEC3 records at {iters} iterations, against a "
        f"{ratio:.0%} distinct-subdomain query mix -- closest-encloser CPU exhaustion",
        {"nsec3_count": len(nsec3), "iterations": iters,
         "distinct_subdomain_ratio": round(ratio, 3), "qname": _qname_text(msg)},
    )]


def detect_water_torture(msg, cfg, zone, zstate, now):
    """
    Pseudo-random subdomain flood. Highest false-positive risk in the
    tier by a wide margin -- typo traffic, antivirus/telemetry domain
    enumeration and CDN health checks all produce NXDOMAIN bursts with
    high subdomain entropy.

    Three controls: the zone exclusion list, the learned baseline, and
    a requirement that the subdomain mix actually be near-unique.
    """
    if zone in cfg.excluded_zones:
        return []
    if msg.rcode != 3:      # NXDOMAIN only
        return []

    zstate.push("nxdomain_times", now, cfg.ring_size)
    q = _question(msg)
    if q is not None:
        labels = normalize(q["name"])
        if labels:
            zstate.push("subdomain_hashes", hash(labels[0]) & 0xFFFFFFFF, cfg.ring_size)

    rate = zstate.rate_in_window(
        zstate.ring("nxdomain_times", cfg.ring_size, create=False), 1.0)

    b = _baseline_gate(cfg, zstate, "bl_nxdomain_ratio", now)
    if b is None:
        zstate.baseline("bl_nxdomain_ratio").update(rate, now, cfg)
        return []

    ratio = _random_subdomain_ratio(zstate, cfg)
    exceeded = b.exceeds(rate, cfg)
    baseline_value = b.value
    if not exceeded:
        # Same baseline-chasing guard as DNSBomb above: only quiet
        # traffic teaches the baseline what quiet looks like.
        b.update(rate, now, cfg)
        return []
    if ratio < 0.9:
        return []
    return [finding(
        "DNSD-022", zone,
        f"NXDOMAIN rate {rate}/s is {rate / max(baseline_value, 1e-9):.1f}x this zone's "
        f"baseline of {baseline_value:.2f}/s, with {ratio:.0%} distinct subdomains",
        {"rate": rate, "baseline": round(baseline_value, 3),
         "distinct_subdomain_ratio": round(ratio, 3), "qname": _qname_text(msg)},
    )]


# ======================================================================
# RESPONSE INTEGRITY (SAD DNS)
# ======================================================================

def answer_signature(msg):
    """
    Canonical signature of a response's answer set, for detecting two
    DIFFERENT answers to one query.

    Built from decoded record fields, never from raw wire bytes: the
    same answer legitimately differs byte-for-byte between two
    responses through name compression alone, and comparing raw bytes
    would make every retransmission look like a forgery.
    """
    parts = []
    for rr in msg.answers:
        parts.append((tuple(normalize(rr.name)), rr.rtype, rr.rclass, bytes(rr.rdata)))
    return tuple(sorted(parts))


def detect_sad_dns_conflict(msg, cfg, zone, inflight, key, now):
    """
    CVE-2020-25705. Two responses to one outstanding query carrying
    different answers means one of them is forged -- there is no benign
    reading, which is why this is HIGH confidence despite being cheap.

    TTL is deliberately excluded from the signature: a legitimate
    retransmission or a second cached copy can carry a decremented TTL
    for the same data, and treating that as a conflict would fire on
    ordinary traffic.
    """
    sig = answer_signature(msg)
    prev = inflight.note_response(key, sig, now)
    if prev is None:
        return []
    return [finding(
        "DNSD-030", zone,
        f"two responses to one outstanding query (txid {msg.txid}) carry different "
        f"answer sets -- one of them is forged",
        {"txid": msg.txid, "qname": _qname_text(msg),
         "first_answer_records": len(prev), "second_answer_records": len(sig)},
    )]


def detect_source_port_entropy(cfg, zone, zstate, sport, now):
    """
    Posture only. Low source-port entropy makes off-path spoofing
    practical; it is not evidence that spoofing happened, which is why
    it is capped at notice/low (LESSON T).
    """
    zstate.push("src_ports", sport, cfg.ring_size)
    ring = zstate.ring("src_ports", cfg.ring_size, create=False)
    if len(ring) < cfg.port_entropy_min_samples:
        return []
    distinct = len(set(ring))
    ratio = distinct / float(len(ring))
    if ratio >= cfg.port_entropy_min_distinct_ratio:
        return []
    return [finding(
        "DNSD-031", zone,
        f"only {distinct} distinct source ports across {len(ring)} queries "
        f"({ratio:.0%}) -- port prediction is easier than it should be",
        {"distinct_ports": distinct, "samples": len(ring),
         "distinct_ratio": round(ratio, 3)},
    )]
