/* Native Toolkit tab. Untrusted tool output is always rendered as text. */
(() => {
  'use strict';
  const el = id => document.getElementById('tk-' + id);
  let catalog = null, busy = false, polling = false;
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
    el('description').textContent = tool.description;
    el('dependency').textContent = tool.reason;
    el('submit').disabled = busy || !tool.available;
    el('target-wrap').hidden = !tool.field;
    el('target').required = !!tool.field;
    el('target-label').textContent = ({public_ip: 'Public IP address', host: 'Hostname or IP address', url: 'HTTP(S) URL', query: 'Shodan search query', capture_job: 'Capture job ID'})[tool.field] || 'Target';
    el('target').maxLength = tool.field === 'url' ? 2048 : 500;
    el('port-wrap').hidden = !tool.port;
    el('interface-wrap').hidden = !tool.interface;
    el('capture-wrap').hidden = tool.id !== 'capture';
    el('page-wrap').hidden = tool.id !== 'shodan_search';
  }
  async function configure() {
    const prior = el('tool').value;
    catalog = await api('/catalog');
    options(el('tool'), catalog.tools.map(t => [t.id, t.name + (t.available ? '' : ' — setup needed')]));
    if (prior) el('tool').value = prior;
    options(el('interface'), catalog.interfaces.map(i => [i, i]));
    options(el('profile'), catalog.capture_profiles.map(i => [i, i]));
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
        const name = job.artifacts.includes('output.txt') ? 'output.txt' : 'result.json';
        if (job.artifacts.includes(name)) {
          const b = document.createElement('button'); b.textContent = 'Preview'; b.onclick = async () => {
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
  el('run').addEventListener('submit', async event => {
    event.preventDefault(); busy = true; fields();
    try {
      await api('/jobs', 'POST', {tool: el('tool').value, params: {target: el('target').value, interface: el('interface').value, profile: el('profile').value, duration: el('duration').value, page: el('page').value, port: el('port').value}});
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
    try { await configure(); await jobs(); } catch (e) { message('message', e); }
    finally { polling = false; }
  }
  el('refresh').onclick = refresh;
  new MutationObserver(() => { if (visible()) refresh(); }).observe(document.getElementById('toolkit-tab'), {attributes: true, attributeFilter: ['class']});
  setInterval(async () => { if (visible() && !polling) { polling = true; try { await jobs(); } catch (e) { message('message', e); } finally { polling = false; } } }, 3000);
})();
