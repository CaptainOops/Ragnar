/* Short operator guides for Ragnar's curated Toolkit. No network requests. */
(() => {
  'use strict';
  const guides = {
    ping: {
      mode: "Sends ICMP probes",
      what: "Five ping probes to one host with round-trip timing and packet-loss stats. The fastest way to confirm a host is reachable from the Pi.",
      steps: ["Enter a hostname or IP (LAN or public).", "Run the tool.", "Read output.txt for replies, timing and 0% vs 100% loss."],
      example: "192.168.86.1",
      result: "Steady low times mean a healthy path. Rising times or loss suggest congestion or a flaky link.",
      tip: "No reply does NOT mean the host is down \u2014 many devices (and most Windows hosts) firewall or drop ICMP. Confirm with a port or service check before concluding it is offline."
    },
    trace: {
      mode: "Traces the network path",
      what: "A numeric, bounded route trace (up to 16 hops) showing each router between the Pi and a target. Useful for locating where a path slows or stops.",
      steps: ["Enter a hostname or IP.", "Run the tool.", "Read the hop list \u2014 each line is one router toward the target."],
      example: "1.1.1.1",
      result: "Hops that answer show their IP and timing. The trace ends at the target or the last router that replies.",
      tip: "Lines of * * * are normal \u2014 many routers hide from traceroute. A trace that stalls partway usually means a firewall ahead, not a broken network."
    },
    dns: {
      mode: "Queries DNS records",
      what: "Looks up A, AAAA, MX, NS, TXT and CAA records for a hostname in one shot \u2014 how a name resolves and who runs its mail and DNS.",
      steps: ["Enter a domain name (not an IP).", "Run the tool.", "Read output.txt for each record type."],
      example: "example.com",
      result: "A and AAAA are addresses, MX is mail, NS is the authoritative servers, TXT often holds SPF or verification strings.",
      tip: "Empty sections just mean that record type is not set \u2014 not an error. Enter a name, not an IP; use WHOIS for ownership of an IP."
    },
    whois: {
      mode: "Looks up registration data",
      what: "Registration and allocation details for a domain or IP \u2014 registrar, org, dates, and the network block an IP belongs to.",
      steps: ["Enter a domain or public IP.", "Run the tool.", "Read output.txt for registrar or org and dates."],
      example: "example.com",
      result: "Domains show registrar and expiry; IPs show the owning organization and network range.",
      tip: "Private LAN IPs (192.168.x.x) and reserved ranges have no public WHOIS. Many registrars redact personal contacts by privacy policy."
    },
    interfaces: {
      mode: "Reads local configuration",
      what: "The Pi\u2019s own network picture: interface addresses, link state (up, down, no-carrier) and routes. Your first stop for choosing which interface to point a tool at.",
      steps: ["Run the tool (no target needed).", "See which interfaces are UP and carry an IP.", "Note the interface that sits on your target LAN."],
      result: "Each interface shows its addresses and state; the default route shows which one reaches the internet.",
      tip: "An interface showing NO-CARRIER has nothing plugged in (common on eth0). Point tools at the interface actually on the LAN you want \u2014 the uplink is not always it."
    },
    neighbors: {
      mode: "Reads the neighbor table",
      what: "The ARP and IPv6 neighbor table for a chosen interface \u2014 devices the Pi has recently talked to on that link. A passive, no-probe view of nearby hosts.",
      steps: ["Pick the interface on your target LAN.", "Run the tool.", "Read the IP-to-MAC entries and their state."],
      result: "Each entry pairs an IP with a MAC and a state (REACHABLE, STALE and so on). It reflects recent traffic, not a full scan.",
      tip: "A sparse table is normal right after boot or on a quiet link \u2014 it only lists hosts the Pi has actually contacted. Run a ping or service scan first to populate it, and pick the LAN interface, not the uplink."
    },
    services: {
      mode: "Scans TCP ports",
      what: "A focused Nmap scan of the top 100 TCP ports on one host with light service and version detection. The go-to for what a device is running.",
      steps: ["Enter one host IP on your LAN.", "Run the tool (quiet pacing is available).", "Preview output for open ports and detected services."],
      example: "192.168.86.1",
      result: "Open ports list the service Nmap detected. Closed or filtered ports are omitted.",
      tip: "All-filtered results usually mean a host firewall (common on Windows and phones), not an empty host. Scan one host at a time, and make sure you targeted a LAN IP, not the Pi itself."
    },
    tls_certificate: {
      mode: "Inspects a TLS certificate",
      what: "Opens a TLS handshake to one host and port and shows the certificate chain \u2014 issuer, subject, validity dates and SANs. Great for spotting expiring or mismatched certs.",
      steps: ["Enter a hostname (port defaults to 443).", "Run the tool.", "Preview output for the certificate dates and issuer."],
      example: "example.com",
      result: "The chain shows each certificate\u2019s subject and issuer and its notBefore and notAfter dates. A self-signed or expired cert shows in the handshake text.",
      tip: "Use the hostname, not the IP, so SNI presents the right cert. If it hangs or fails, the host may not speak TLS on that port \u2014 try the real port (8443, 993 and so on)."
    },
    ms17_check: {
      mode: "Runs one detection script",
      what: "Checks a host for the MS17-010 (EternalBlue) SMB flaw with Nmap\u2019s detection script. Detection only \u2014 it never exploits.",
      steps: ["Enter one host IP that has SMB (port 445).", "Run the tool.", "Preview output for the script\u2019s verdict."],
      example: "192.168.86.50",
      result: "Reports VULNERABLE, patched, or could-not-determine \u2014 the last is common and not a clean bill of health.",
      tip: "No result usually means port 445 is closed or filtered, or the host is not Windows SMB. Confirm 445 is open first with Service inventory. Only run against hosts in your own lab."
    },
    capture: {
      mode: "Captures packets",
      what: "A bounded packet capture on one interface \u2014 all traffic or a filter (DNS, DHCP, LLDP/CDP, mDNS/SSDP). Saves a PCAP to this network\u2019s loot.",
      steps: ["Pick the interface on the LAN you want to observe.", "Choose a filter and duration, then Run.", "When it finishes, use Capture summary or download the PCAP."],
      result: "A PCAP plus packet counts. Filtered captures such as DHCP stay quiet unless that traffic occurs during the window.",
      tip: "Nothing captured is usually the wrong interface or a quiet window \u2014 pick the LAN interface (not a down eth0), lengthen the duration, or generate the traffic you filtered for. A monitor-mode radio will not see normal LAN traffic."
    },
    capture_summary: {
      mode: "Reads a saved capture",
      what: "Summarizes the first 200 packets of a previous Toolkit capture \u2014 protocols, talkers and services \u2014 without touching the network.",
      steps: ["Run a Packet capture first.", "Select that completed capture job here.", "Run and Preview the protocol and host breakdown."],
      result: "A readable rollup of who talked to whom and which protocols appeared in the sampled packets.",
      tip: "It needs an existing capture job to read \u2014 run Packet capture first. It samples only the first 200 packets, so a large capture is summarized from its opening, not its entirety."
    },
    internetdb: {
      mode: 'Looks up indexed data',
      what: 'A quick first look at what Shodan has already observed about a public IPv4 address. Useful for checking your internet-facing address without running a scan from the Pi.',
      steps: ['Enter one public IPv4 address. No API key is needed.', 'Choose Run & save to loot.', 'Open Preview on the completed job to see ports, names and reported vulnerabilities.'],
      example: '1.1.1.1',
      result: 'Ports and hostnames are past observations. A reported CVE is a lead to verify, not proof that a device is vulnerable.',
      tip: 'A home address such as 192.168.x.x is private and will not work here. No indexed result does not mean a host is secure.'
    },
    shodan_host: {
      mode: 'Looks up indexed data',
      what: 'A more detailed view of one public IP, including service banners and observation dates. Use it when the free lookup needs more context.',
      steps: ['Open Shodan API key below and verify your key once.', 'Enter one public IP address and run the lookup.', 'Preview the saved response; check timestamps before treating a service as current.'],
      example: '1.1.1.1',
      result: 'Service records describe what Shodan observed on each port. Different services can have different observation dates.',
      tip: 'Use Network or Discovered for devices on your private LAN.'
    },
    shodan_search: {
      mode: 'Searches indexed data',
      what: 'Finds records using Shodan filters instead of looking up one IP. Use it to investigate your organization’s public exposure.',
      steps: ['Verify your key in Shodan API key below.', 'Enter a Shodan query and start with page 1.', 'Run, then Preview. Look up IP opens a matching address in the host-lookup form.'],
      example: 'hostname:example.com',
      result: 'Each match is an indexed service record; the same IP can appear more than once.',
      tip: 'Replace example.com with your domain. Filters and extra pages may use query credits. Try Shodan result count first to gauge a query.'
    },
    shodan_count: {
      mode: 'Counts indexed records',
      what: 'Checks how many records match a Shodan query before retrieving the full results.',
      steps: ['Verify your Shodan key below.', 'Enter the same filter query you would use in Shodan search.', 'Run and Preview the total; narrow your query if the scope is too broad.'],
      example: 'hostname:example.com',
      result: 'The total counts matching service records, not necessarily unique devices.',
      tip: 'This endpoint does not use query credits, but still needs an API key. Replace the example domain with your own.'
    },
    shodan_account: {
      mode: 'Reads account information',
      what: 'Shows the plan and credits associated with the configured Shodan key. Use this to troubleshoot search access.',
      steps: ['Verify your API key in the section below.', 'Run this tool; no target is needed.', 'Preview the plan and query-credit values.'],
      result: 'The result describes the configured account. It does not buy credits or change your plan.',
      tip: 'A verified key can still lack access to a particular search feature.'
    },
    http_headers: {
      mode: 'Sends one HTTP request',
      what: 'Reads a website’s response headers: status, server hints, redirects and security-related settings. Useful for a quick check of your web service.',
      steps: ['Enter the complete URL, including http:// or https://.', 'Run the tool.', 'Preview output.txt and look at the HTTP status and named header lines.'],
      example: 'https://example.com',
      result: '200 usually means the request succeeded. A 3xx response includes a redirect location; this tool does not follow it.',
      tip: 'Some servers reject HEAD requests with 405 even though their normal pages work. Headers alone do not prove a site is safe or vulnerable.'
    },
    mdns: {
      mode: 'Queries the local network',
      what: 'Finds services that nearby devices advertise through mDNS/Bonjour, such as printers or media players.',
      steps: ['Select the interface connected to the network you want to inspect: usually eth0 or wlan0.', 'Run the discovery.', 'Preview output.txt for service names, resolved addresses and ports.'],
      result: 'A resolved service tells you what a device advertises, rather than every service it runs.',
      tip: 'Avahi browses all active interfaces; results are filtered to your selection. No results may mean devices are quiet or multicast is filtered.'
    },
    smb_shares: {
      mode: 'Queries one file server',
      what: 'Lists SMB shares that a server reveals to an anonymous connection. Start here before checking directory listings.',
      steps: ['Enter your NAS or file server’s hostname or IP.', 'Run the tool; no username or password is supplied.', 'Preview output.txt for share names, types and comments.'],
      example: 'Your NAS IP or hostname',
      result: 'A listed share is not proof its files are readable. Anonymous SMB share crawl checks listings separately.',
      tip: 'Access denied often means the server requires authentication, rather than a broken Toolkit tool.'
    },
    smb_crawl: {
      mode: 'Reads remote directory listings',
      what: 'Checks whether an anonymous connection can list files in up to three SMB disk shares. It does not download the files.',
      steps: ['Enter your file server’s hostname or IP.', 'Run and allow time for share discovery and directory listing.', 'Preview output.txt; result.json records the selected shares.'],
      example: 'Your NAS IP or hostname',
      result: 'Visible file and folder names show listing access. A denial can stop the job; partial output is still useful.',
      tip: 'Output and time limits keep large shares bounded, so this is not a complete audit of every directory.'
    },
    port_watch: {
      mode: 'Scans one host',
      what: 'Compares a host’s top 100 TCP ports with its previous check on this network. Useful after changing a device’s services or firewall.',
      steps: ['Enter one device IP or hostname.', 'Run once to create its baseline.', 'Run again later with the same target spelling, then Preview result.json to see changes.'],
      example: 'One device’s IP or hostname',
      result: 'new_ports were not open last time; closed_ports were open but are no longer reported open. Each successful run becomes the next baseline.',
      tip: 'Only the top 100 TCP ports are checked. A sleeping host or filtering change can look like closed ports.'
    },
    ldap_rootdse: {
      mode: 'Queries one directory server',
      what: 'Reads the directory server’s public starting information, such as naming contexts and LDAP versions. It does not enumerate user accounts.',
      steps: ['Enter your LDAP server’s IP or hostname.', 'Use port 389 for LDAP or 636 for LDAPS.', 'Run, then Preview output.txt for namingContexts and defaultNamingContext.'],
      example: 'Your directory server’s hostname',
      result: 'Naming contexts identify the directory roots a later authorized query would use.',
      tip: 'No result may reflect authentication requirements, encryption policy or connectivity. A nonstandard port uses plain LDAP in this tool.'
    },
    tcp_jitter: {
      mode: 'Makes eight TCP connections',
      what: 'Measures how consistently a specific TCP service accepts connections. Useful when a web page or other service feels intermittently slow.',
      steps: ['Enter the service’s hostname or IP.', 'Set its listening TCP port, such as 443 for HTTPS.', 'Run and Preview the timing samples, median and failed-sample count.'],
      example: 'Your service’s hostname',
      result: 'median_ms is the typical connection time. mean_jitter_ms is the average change between successful samples.',
      tip: 'This measures connection setup, not bandwidth or page-load time. A closed port or firewall can cause failed samples.'
    },
    mac_presence: {
      mode: 'Reads local neighbor state',
      what: 'Looks for one MAC address in the Pi’s neighbor table. Useful when you know a device’s MAC and want to see a recently learned IP.',
      steps: ['Select the interface attached to that device’s network.', 'Enter six hex pairs separated by colons.', 'Run and Preview result.json for matching IP addresses and neighbor states.'],
      example: 'aa:bb:cc:dd:ee:ff',
      result: 'found means the address is in the cache, not necessarily online right now.',
      tip: 'This sends no discovery probes. An empty match may simply mean the Pi has not learned the device recently.'
    },
    usb_watch: {
      mode: 'Watches local USB changes',
      what: 'Records USB arrivals during a short observation window and identifies keyboard/mouse-class and storage-class interfaces.',
      steps: ['Choose a duration from 5 to 120 seconds.', 'Start the job before connecting the device you want to observe.', 'After it finishes, Preview result.json for inserted devices and HID/storage counts.'],
      result: 'Device IDs and reported classes describe how a USB device presents itself. Devices already connected at start are the baseline.',
      tip: 'HID means a keyboard/mouse-style interface, not proof of a malicious device. The tool does not collect keystrokes or block devices.'
    },
    packet_replay: {
      mode: 'Sends saved packets',
      what: 'Replays a small sample from a capture saved by Toolkit. Useful for reproducing traffic in a controlled test network.',
      steps: ['Find a Packet capture job in Saved jobs that has capture.pcap, and copy its Job ID.', 'Paste that ID and select a connected Ethernet interface.', 'Run once, then inspect output.txt for what tcpreplay sent.'],
      example: '32-character Toolkit capture Job ID',
      result: 'The job sends up to 200 packets at 10 packets per second. It does not rewrite destinations or guarantee application responses.',
      tip: 'Use an isolated test LAN: replay transmits the saved traffic. Traffic-tab captures and arbitrary file paths are not accepted by this adapter.'
    },
    responder: {
      mode: 'Listens; active mode also responds',
      what: 'Examines name-resolution activity on a wired network. Analyze mode is the starting point for observing requests without answering them.',
      steps: ['Connect Ethernet and select that wired interface.', 'Keep Analyze selected and choose a 5–120-second window.', 'Run, then inspect the saved output. Stop ends the session early.'],
      result: 'Output depends on traffic seen during the session. Quiet output does not establish that a network is protected.',
      tip: 'Active mode answers name queries and may collect authentication material. Use it only in an explicitly authorized lab; it is not needed for an initial observation.'
    },
    honeypot: {
      mode: 'Opens a temporary listener',
      what: 'Places a small decoy service on the Pi and records connections to it. Use it to notice devices or scanners reaching an otherwise unused service.',
      steps: ['Choose the listening interface; lo is local-only, eth0 is the wired LAN, and wlan0 is Wi-Fi.', 'Choose HTTP, SSH banner or FTP banner, an unused port, and a duration.', 'Start it, connect to that Pi address and port from your test device, then inspect the job’s events.'],
      result: 'events.jsonl records connection metadata. Completed runs include totals in result.json. First contact from a source also feeds the existing Watchtower log.',
      tip: 'HTTP returns a decoy 503 response; SSH/FTP only send banners. Connections are observations, not proof of an attack. Stop closes the listener; no passwords are collected.'
    },
    payload: {
      mode: 'Runs your Python code',
      what: 'Saves and runs a small Python script using Ragnar’s existing jobs and per-network results. Start with the supplied context-report example.',
      steps: ['Choose a saved payload or New payload, then enter a name and edit the source.', 'Use Check syntax, set a timeout, and Save. Save & run saves before starting.', 'Find the run in Saved jobs: Preview shows output, Stop ends a running job, and Files contains its artifacts.'],
      result: 'output.txt contains printed output and errors. Each run also keeps its source and context, so later edits do not alter the historical run.',
      tip: 'Scripts run with Ragnar’s service permissions. Syntax checking checks Python structure, not safety. Save generated files in RAGNAR_JOB_DIR; network libraries are separate.'
    }
  };

  function render(container, id, tool = {}) {
    const guide = guides[id];
    container.replaceChildren();
    if (!guide) {
      const p = document.createElement('p'); p.textContent = tool.description || 'Choose a tool to see its guide.';
      container.append(p); return;
    }
    const badge = document.createElement('span'); badge.className = 'tk-guide-mode'; badge.textContent = guide.mode; container.append(badge);
    const section = (heading, text) => {
      const h = document.createElement('h3'); h.textContent = heading;
      const p = document.createElement('p'); p.textContent = text;
      container.append(h, p);
    };
    section('What it does', guide.what);
    const h = document.createElement('h3'); h.textContent = 'How to use it';
    const list = document.createElement('ol');
    for (const step of guide.steps) { const li = document.createElement('li'); li.textContent = step; list.append(li); }
    container.append(h, list);
    if (guide.example) section('Example input', guide.example);
    section('Reading the result', guide.result);
    section('Keep in mind', guide.tip);
    if (id.startsWith('shodan_') || id === 'internetdb') {
      const link = document.createElement('a');
      link.href = id === 'internetdb' ? 'https://internetdb.shodan.io/' : 'https://developer.shodan.io/api';
      link.target = '_blank'; link.rel = 'noopener noreferrer'; link.textContent = 'Official Shodan reference';
      container.append(link);
    }
  }
  window.RagnarToolkitGuides = Object.freeze({render, guides: Object.freeze(guides)});
})();
