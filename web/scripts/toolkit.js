/* Native Toolkit tab. Untrusted tool output is always rendered as text. */
(() => {
  'use strict';
  const el = id => document.getElementById('tk-' + id);
  let catalog = null, busy = false, polling = false, lastTool = null;
  const paceWrap = document.createElement('div'); paceWrap.id = 'tk-pace-wrap'; paceWrap.hidden = true;
  const paceLabel = document.createElement('label'); paceLabel.htmlFor = 'tk-pace'; paceLabel.textContent = 'Scan pace';
  const paceSelect = document.createElement('select'); paceSelect.id = 'tk-pace';
  for (const [value, label] of [['normal', 'Normal'], ['quiet', 'Quiet (slower, fewer probes)']]) {
    const option = document.createElement('option'); option.value = value; option.textContent = label; paceSelect.append(option);
  }
  paceWrap.append(paceLabel, paceSelect); el('port-wrap').after(paceWrap);
  const modeWrap = document.createElement('div'); modeWrap.id = 'tk-mode-wrap'; modeWrap.hidden = true;
  const modeLabel = document.createElement('label'); modeLabel.htmlFor = 'tk-mode'; modeLabel.textContent = 'Responder mode';
  const modeSelect = document.createElement('select'); modeSelect.id = 'tk-mode';
  for (const [value, label] of [['analyze', 'Analyze (listen only)'], ['active', 'Active (answer name queries)']]) {
    const option = document.createElement('option'); option.value = value; option.textContent = label; modeSelect.append(option);
  }
  modeWrap.append(modeLabel, modeSelect); paceWrap.after(modeWrap);
  const visible = () => !document.getElementById('toolkit-tab').classList.contains('hidden');
  async function api(path, method = 'GET', data) {
    const response = await fetch('/api/toolkit' + path, {method, headers: {'Content-Type': 'application/json'},
      ...(data !== undefined ? {body: JSON.stringify(data)} : {})});
    const value = await response.json();
    if (!response.ok) throw new Error(value.error || 'Request failed. Check your session and retry.');
    return value;
  }
  function options(node, values) {
    node.replaceChildren(...values.map(([value, text]) => { const o = document.createElement('option'); o.value = value; o.textContent = text; return o; }));
  }
  function selected() { return catalog && catalog.tools.find(t => t.id === el('tool').value); }
  function fields() {
    const tool = selected(); if (!tool) return;
    if (window.RagnarToolkitGuides && el('guide-body')) {
      el('guide-title').textContent = tool.name + ' · Quick guide';
      window.RagnarToolkitGuides.render(el('guide-body'), tool.id, tool);
      el('target').placeholder = window.RagnarToolkitGuides.guides[tool.id]?.example || '';
    }
    el('description').textContent = tool.description;
    el('dependency').textContent = tool.reason;
    el('submit').disabled = busy || !tool.available;
    el('target-wrap').hidden = !tool.field;
    el('target').required = !!tool.field;
    el('target-label').textContent = ({public_ip: 'Public IP address', host: 'Hostname or IP address', url: 'HTTP(S) URL', query: 'Shodan search query', capture_job: 'Capture job ID', mac: 'MAC address'})[tool.field] || 'Target';
    el('target').maxLength = tool.field === 'url' ? 2048 : 500;
    el('port-wrap').hidden = !tool.port;
    if (lastTool !== tool.id) { if (tool.port) el('port').value = tool.port; if (tool.id === 'responder') el('duration').value = 30; lastTool = tool.id; }
    el('port-wrap').querySelector('label').textContent = tool.id === 'tls_certificate' ? 'TLS port' : tool.id === 'ldap_rootdse' ? 'LDAP port' : 'TCP port';
    el('interface-wrap').hidden = !tool.interface;
    el('capture-wrap').hidden = !['capture', 'usb_watch', 'responder', 'honeypot'].includes(tool.id);
    const hasProfile = ['capture', 'honeypot'].includes(tool.id);
    el('profile').parentElement.querySelector('label').hidden = !hasProfile;
    el('profile').hidden = !hasProfile;
    el('profile').parentElement.querySelector('label').textContent = tool.id === 'honeypot' ? 'Decoy service' : 'Capture profile';
    const profileValues = tool.id === 'honeypot' ? Object.keys(catalog.honeypot_profiles || {http: 8088}) : catalog.capture_profiles;
    if (el('profile').dataset.tool !== tool.id) {
      options(el('profile'), profileValues.map(i => [i, i])); el('profile').dataset.tool = tool.id;
      if (tool.id === 'honeypot') el('profile').value = 'http';
    }
    el('duration').max = tool.id === 'honeypot' ? 3600 : 120;
    el('duration').previousElementSibling.textContent = tool.id === 'honeypot' ? 'Seconds (5–3600)' : 'Seconds (5–120)';
    el('page-wrap').hidden = tool.id !== 'shodan_search';
    el('pace-wrap').hidden = tool.id !== 'services';
    el('mode-wrap').hidden = tool.id !== 'responder';
  }
  async function configure() {
    const prior = el('tool').value;
    catalog = await api('/catalog');
    options(el('tool'), catalog.tools.filter(t => !t.native_tab && t.id !== 'payload').map(t => [t.id, t.name + (t.available ? '' : ' — setup needed')]));
    if (prior) el('tool').value = prior;
    else el('tool').value = 'internetdb';
    const priorInterface = el('interface').value;
    options(el('interface'), catalog.interfaces.map(i => [i, i]));
    if (catalog.interfaces.includes(priorInterface)) el('interface').value = priorInterface;
    else if (catalog.interfaces.includes('eth0')) el('interface').value = 'eth0';
    el('key-status').textContent = catalog.shodan_configured ? 'API key configured. Run Shodan account to check your plan.' : 'Add your API key to enable Shodan.';
    fields();
  }
  function message(id, error) { el(id).textContent = error.message || String(error); }
  function summarize(job, text) {
    el('summary').replaceChildren();
    if (!(job.tool === 'internetdb' || String(job.tool).startsWith('shodan_'))) return;
    let result; try { result = JSON.parse(text); } catch { return; }
    const line = text => { const p = document.createElement('p'); p.textContent = text; el('summary').append(p); };
    if (result.ip || result.ip_str) line('IP: ' + (result.ip || result.ip_str));
    if (result.ports) line('Indexed ports: ' + result.ports.join(', '));
    if (result.hostnames) line('Hostnames: ' + result.hostnames.join(', '));
    if (result.vulns) line('Reported CVEs (not independently verified): ' + (Array.isArray(result.vulns) ? result.vulns : Object.keys(result.vulns)).join(', '));
    if (result.total !== undefined) line('Matching records: ' + result.total);
    if (result.plan !== undefined) line('Plan: ' + result.plan + ' · Query credits: ' + result.query_credits);
    for (const match of (result.matches || []).slice(0, 100)) {
      const p = document.createElement('p');
      p.textContent = (match.ip_str || '') + ':' + match.port + ' · ' + (match.product || match.org || '') + ' · Observed ' + (match.timestamp || 'unknown');
      if (match.ip_str) {
        const b = document.createElement('button'); b.textContent = 'Look up IP';
        b.onclick = () => { el('tool').value = 'shodan_host'; el('target').value = match.ip_str; fields(); el('run').scrollIntoView({behavior: 'smooth'}); };
        p.append(b);
      }
      el('summary').append(p);
    }
    line('These are Shodan’s indexed observations. The full response is below and saved in loot.');
  }
  async function jobs() {
    const result = await api('/jobs');
    const nodes = result.jobs.map(job => {
      const row = document.createElement('div'); row.className = 'tk-job';
      const title = document.createElement('strong'); title.textContent = job.name + ' · ' + job.status;
      const detail = document.createElement('p'); detail.textContent = new Date(job.created).toLocaleString() + ' · ' + JSON.stringify(job.params);
      const id = document.createElement('p'); id.className = 'tk-muted'; id.textContent = 'Job ID: ' + job.id;
      row.append(title, detail, id);
      if (job.error) { const p = document.createElement('p'); p.className = 'tk-error'; p.textContent = job.error; row.append(p); }
      for (const name of ['report.json', ...job.artifacts]) {
        const url = '/api/toolkit/jobs/' + encodeURIComponent(job.id) + '/files/' + encodeURIComponent(name);
        const a = document.createElement('a'); a.href = url; a.textContent = name; a.download = name; row.append(a);
      }
      if (job.status === 'running') {
        const b = document.createElement('button'); b.textContent = 'Stop'; b.onclick = async () => {
          try { await api('/jobs/' + encodeURIComponent(job.id) + '/cancel', 'POST', {}); await jobs(); }
          catch (e) { message('message', e); }
        }; row.append(b);
      } else if (job.artifacts.length) {
        const structured = ['port_watch', 'mac_presence'].includes(job.tool) && job.artifacts.includes('result.json');
        const name = structured ? 'result.json' : job.artifacts.includes('output.txt') ? 'output.txt' : job.artifacts.includes('result.json') ? 'result.json' : 'events.jsonl';
        if (job.artifacts.includes(name)) {
          const b = document.createElement('button'); b.textContent = 'Preview'; b.title = 'Preview ' + name; b.onclick = async () => {
            try {
              const response = await fetch('/api/toolkit/jobs/' + encodeURIComponent(job.id) + '/files/' + name);
              if (!response.ok) throw new Error('Could not load artifact.');
              const text = await response.text();
              summarize(job, text);
              el('preview').textContent = text.slice(0, 150000) + (text.length > 150000 ? '\n… Download the file for the full result.' : '');
              el('preview-wrap').hidden = false;
            } catch (e) { message('message', e); }
          }; row.append(b);
        }
      }
      return row;
    });
    el('jobs').replaceChildren(...nodes);
    if (!nodes.length) el('jobs').textContent = 'No Toolkit jobs saved for this network yet.';
  }
  el('tool').addEventListener('change', fields);
  el('profile').addEventListener('change', () => {
    if (selected()?.id === 'honeypot') el('port').value = catalog.honeypot_profiles[el('profile').value];
  });

  // One payload library and job runner, sharing this network's history and loot.
  let payloadLibrary = [], payloadRevision = null, payloadName = null;
  const starter = 'import json\nimport os\nfrom pathlib import Path\n\ncontext = json.loads(Path(os.environ["RAGNAR_CONTEXT"]).read_text())\nprint(json.dumps(context, indent=2))\n# Save results in RAGNAR_JOB_DIR; the run is listed in Ragnar Files.\n';
  function loadPayload(payload) {
    payloadName = payload?.name || null; payloadRevision = payload?.revision || null;
    el('payload-name').value = payloadName || 'network-report';
    el('payload-source').value = payload?.source || starter;
    el('payload-message').textContent = payload ? 'Loaded ' + payload.name : 'New payload. Save before running.';
  }
  async function library() {
    const result = await api('/payloads'); payloadLibrary = result.payloads;
    options(el('payload-list'), [['', 'Choose a saved payload'], ...payloadLibrary.map(p => [p.name, p.name])]);
    if (payloadName) el('payload-list').value = payloadName;
  }
  el('payload-list').onchange = () => {
    const payload = payloadLibrary.find(p => p.name === el('payload-list').value);
    if (payload && (el('payload-source').value === starter || confirm('Load this payload and replace the editor contents?'))) loadPayload(payload);
  };
  el('payload-new').onclick = () => { if (confirm('Start a new payload and replace the editor contents?')) loadPayload(null); };
  el('payload-check').onclick = async () => {
    try { await api('/payloads/check', 'POST', {source: el('payload-source').value}); message('payload-message', 'Python syntax is valid.'); }
    catch (e) { message('payload-message', e); }
  };
  async function savePayload() {
    const name = el('payload-name').value.trim();
    const payload = await api('/payloads', 'POST', {name, source: el('payload-source').value, revision: name === payloadName ? payloadRevision : null});
    payloadName = payload.name; payloadRevision = payload.revision; await library(); return payload;
  }
  el('payload-save').onclick = async () => {
    try { await savePayload(); message('payload-message', 'Saved in this network’s payload library.'); }
    catch (e) { message('payload-message', e); }
  };
  el('payload-run').onclick = async () => {
    el('payload-run').disabled = true;
    try {
      const payload = await savePayload();
      await api('/jobs', 'POST', {tool: 'payload', params: {target: payload.name, duration: el('payload-duration').value}});
      message('payload-message', 'Started. Output and Stop are in Saved jobs.'); await jobs();
    } catch (e) { message('payload-message', e); }
    finally { el('payload-run').disabled = false; }
  };
  el('payload-delete').onclick = async () => {
    if (!payloadName || !confirm('Delete saved payload ' + payloadName + '? Previous runs are kept.')) return;
    try { await api('/payloads/' + encodeURIComponent(payloadName), 'DELETE', {revision: payloadRevision}); loadPayload(null); await library(); }
    catch (e) { message('payload-message', e); }
  };
  loadPayload(null);
  if (window.RagnarToolkitGuides && el('payload-guide')) window.RagnarToolkitGuides.render(el('payload-guide'), 'payload');
  el('run').addEventListener('submit', async event => {
    event.preventDefault(); busy = true; fields();
    try {
      await api('/jobs', 'POST', {tool: el('tool').value, params: {target: el('target').value, interface: el('interface').value, profile: el('profile').value, duration: el('duration').value, page: el('page').value, port: el('port').value, pace: el('pace').value, mode: el('mode').value}});
      message('message', 'Job started. Results will appear below and in loot.'); await jobs();
    } catch (e) { message('message', e); }
    finally { busy = false; fields(); }
  });
  el('key-form').addEventListener('submit', async event => {
    event.preventDefault(); el('save-key').disabled = true;
    message('key-message', 'Verifying with Shodan…');
    try { const account = await api('/shodan-key', 'POST', {key: el('key').value.trim()}); el('key').value = ''; await configure(); message('key-message', 'Verified and saved. Plan: ' + (account.plan || 'unknown') + ' · Query credits: ' + (account.query_credits ?? 'unknown')); }
    catch (e) { message('key-message', e); }
    finally { el('save-key').disabled = false; }
  });
  el('remove-key').onclick = async () => {
    try { await api('/shodan-key', 'DELETE', {}); el('key').value = ''; await configure(); message('key-message', 'Key removed.'); }
    catch (e) { message('key-message', e); }
  };
  async function refresh() {
    if (polling) return; polling = true;
    try { await configure(); await jobs(); await library(); } catch (e) { message('message', e); }
    finally { polling = false; }
  }
  el('refresh').onclick = refresh;
  new MutationObserver(() => { if (visible()) refresh(); }).observe(document.getElementById('toolkit-tab'), {attributes: true, attributeFilter: ['class']});
  setInterval(async () => { if (visible() && !polling) { polling = true; try { await jobs(); } catch (e) { message('message', e); } finally { polling = false; } } }, 3000);
})();
