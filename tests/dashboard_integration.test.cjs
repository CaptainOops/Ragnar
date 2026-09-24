const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {JSDOM} = require('jsdom');
const root = path.join(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'web/index_modern.html'), 'utf8');
const cameraScript = source.slice(source.indexOf('var REFRESH_MS = 12000;'), source.indexOf('var REFRESH_MS = 12000;') + 30000).split('</script>')[0];
const cameraCode = '(function(){' + cameraScript;
const flush = () => new Promise(resolve => setImmediate(resolve));

function fixture() {
  // Ragnar serves this file directly; template includes are never expanded.
  assert.ok(!source.includes('{% include'));
  const html = source.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, '');
  const dom = new JSDOM(html, {url: 'http://ragnar.local/', runScripts: 'dangerously'});
  const w = dom.window;
  const intervals = [];
  w.setInterval = (fn, ms) => { intervals.push([fn, ms]); return intervals.length; };
  w.fetch = async () => ({ok: true, json: async () => ({success: true, cams: []})});
  w.eval(cameraCode);
  return {dom, w, intervals};
}

test('quoted category filters, fullscreen and video-wall refresh survive Toolkit navigation', async () => {
  const {dom, w, intervals} = fixture();
  try {
    const tab = w.document.getElementById('livecams-tab');
    tab.classList.remove('hidden'); await flush();
    w.lcRender([{id: 'abc', type: 'snapshot', label: 'Surf', category: "Fisherman's Wharf", url: 'https://example.com'}]);
    const buttons = [...w.document.querySelectorAll('[data-lc-category]')];
    buttons.find(b => b.textContent === "Fisherman's Wharf").click();
    assert.equal(w._lcFilter, "Fisherman's Wharf");
    w.lcOpen('abc'); w.lcVideoWall();
    intervals.find(([, ms]) => ms === 12000)[0]();
    for (const selector of ['#livecams-grid img', '#lc-modal-body img', '#lc-wall-body img']) {
      assert.match(w.document.querySelector(selector).src, /_ts=/);
    }
    tab.classList.add('hidden'); await flush();
    assert.equal(w.document.querySelectorAll('#livecams-tab iframe, #livecams-tab img').length, 0);
  } finally { dom.window.close(); }
});

test('Toolkit loads free Shodan, submits a job, previews untrusted results as text', async () => {
  const {dom, w} = fixture();
  try {
    const calls = [];
    w.fetch = async (url, init = {}) => {
      calls.push([url, init]);
      const value = url.endsWith('/catalog') ? {tools: [{id: 'internetdb', name: 'Shodan InternetDB', field: 'public_ip', description: 'Free', available: true, reason: ''}], interfaces: ['eth0'], capture_profiles: ['all'], shodan_configured: false}
        : url.endsWith('/jobs') && init.method === 'POST' ? {id: 'a'.repeat(32)}
        : {jobs: [{id: 'a'.repeat(32), name: 'InternetDB', status: 'completed', created: new Date().toISOString(), params: {}, artifacts: ['result.json']}]};
      return {ok: true, json: async () => value, text: async () => '<img src=x onerror="alert(1)">'};
    };
    w.eval(fs.readFileSync(path.join(root, 'web/scripts/toolkit.js'), 'utf8'));
    w.document.getElementById('toolkit-tab').classList.remove('hidden'); await flush();
    assert.equal(w.document.getElementById('tk-submit').disabled, false);
    w.document.getElementById('tk-target').value = '1.1.1.1';
    w.document.getElementById('tk-run').dispatchEvent(new w.Event('submit', {cancelable: true})); await flush();
    const submitted = calls.find(([url, init]) => url.endsWith('/jobs') && init.method === 'POST');
    assert.equal(JSON.parse(submitted[1].body).params.target, '1.1.1.1');
    [...w.document.querySelectorAll('#tk-jobs button')].find(b => b.textContent === 'Preview').click(); await flush();
    assert.match(w.document.getElementById('tk-preview').textContent, /onerror/);
    assert.equal(w.document.querySelectorAll('#tk-preview img').length, 0);
    assert.equal(w.document.querySelectorAll('#toolkit-tab').length, 1);
    assert.equal(w.document.querySelectorAll('#livecams-tab').length, 1);
  } finally { dom.window.close(); }
});
