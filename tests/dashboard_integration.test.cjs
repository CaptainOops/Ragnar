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
  w.HTMLElement.prototype.scrollIntoView = function () { w.scrolledTo = this; };
  const intervals = [];
  w.setInterval = (fn, ms) => { intervals.push([fn, ms]); return intervals.length; };
  w.fetch = async () => ({ok: true, json: async () => ({success: true, cams: []})});
  w.eval(cameraCode);
  w.eval(fs.readFileSync(path.join(root, 'web/scripts/toolkit_guides.js'), 'utf8'));
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
        : url.endsWith('/payloads') ? {payloads: []}
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

test('Payload IDE saves source before running and hides duplicate native launchers', async () => {
  const {dom, w} = fixture();
  try {
    const calls = [];
    w.fetch = async (url, init = {}) => {
      calls.push([url, init]);
      const data = init.body ? JSON.parse(init.body) : {};
      const value = url.endsWith('/catalog') ? {
        tools: [{id: 'internetdb', name: 'Shodan', available: true},
          {id: 'honeypot', name: 'Honeypot', available: true, port: 8088, interface: true},
          {id: 'ping', name: 'Ping', available: true, native_tab: 'network'},
          {id: 'payload', name: 'Payload', available: true}],
        interfaces: ['eth0'], capture_profiles: ['all'], honeypot_profiles: {'ftp-banner': 2121, http: 8088, 'ssh-banner': 2222}}
        : url.endsWith('/payloads') ? (init.method === 'POST' ? {...data, revision: 'abc'} : {payloads: []})
        : {jobs: [], id: 'b'.repeat(32)};
      return {ok: true, json: async () => value};
    };
    w.eval(fs.readFileSync(path.join(root, 'web/scripts/toolkit.js'), 'utf8'));
    w.document.getElementById('toolkit-tab').classList.remove('hidden'); await flush();
    assert.deepEqual([...w.document.querySelectorAll('#tk-tool option')].map(x => x.value), ['internetdb', 'honeypot']);
    w.document.getElementById('tk-tool').value = 'honeypot';
    w.document.getElementById('tk-tool').dispatchEvent(new w.Event('change'));
    assert.equal(w.document.getElementById('tk-profile').value, 'http');
    assert.equal(w.document.getElementById('tk-port').value, '8088');
    w.document.getElementById('tk-payload-name').value = 'hello';
    w.document.getElementById('tk-payload-source').value = 'print("hello")';
    w.document.getElementById('tk-payload-run').click(); await flush();
    const mutations = calls.filter(([, init]) => init.method === 'POST');
    assert.ok(mutations[0][0].endsWith('/payloads'));
    assert.equal(JSON.parse(mutations[0][1].body).source, 'print("hello")');
    assert.equal(JSON.parse(mutations[1][1].body).tool, 'payload');
    assert.equal(JSON.parse(mutations[1][1].body).params.target, 'hello');
  } finally { dom.window.close(); }
});

test('every visible Toolkit tool has a guide; switching help preserves inputs and never runs jobs', async () => {
  const {dom, w} = fixture();
  try {
    const backend = fs.readFileSync(path.join(root, 'toolkit.py'), 'utf8');
    const nativeBlock = backend.split('NATIVE_TOOLS = ')[1].split('ARTIFACTS = ')[0];
    const native = [...nativeBlock.matchAll(/'([a-z0-9_]+)':/g)].map(m => m[1]);
    const ids = [...backend.matchAll(/dict\(id='([a-z0-9_]+)'/g)].map(m => m[1]);
    for (const id of ids.filter(id => !native.includes(id))) {
      const guide = w.RagnarToolkitGuides.guides[id];
      assert.ok(guide, 'Missing guide for ' + id);
      assert.equal(guide.steps.length, 3);
    }
    const calls = [];
    w.fetch = async (url, init = {}) => {
      calls.push([url, init]);
      const value = url.endsWith('/catalog') ? {
        tools: ['internetdb', 'http_headers'].map(id => ({id, name: id, field: 'url', available: true})),
        interfaces: ['eth0'], capture_profiles: ['all'], shodan_configured: false}
        : url.endsWith('/payloads') ? {payloads: []} : {jobs: []};
      return {ok: true, json: async () => value};
    };
    w.eval(fs.readFileSync(path.join(root, 'web/scripts/toolkit.js'), 'utf8'));
    w.document.getElementById('toolkit-tab').classList.remove('hidden'); await flush();
    assert.match(w.document.getElementById('tk-guide-body').textContent, /public IPv4/);
    w.document.getElementById('tk-target').value = 'https://my-device.example';
    w.document.getElementById('tk-tool').value = 'http_headers';
    w.document.getElementById('tk-tool').dispatchEvent(new w.Event('change'));
    assert.match(w.document.getElementById('tk-guide-body').textContent, /HEAD requests/);
    assert.equal(w.document.getElementById('tk-target').value, 'https://my-device.example');
    assert.equal(w.document.getElementById('tk-target').placeholder, 'https://example.com');
    assert.equal(calls.filter(([, init]) => init.method === 'POST').length, 0);
    assert.match(w.document.getElementById('tk-payload-guide').textContent, /Check syntax/);
    assert.equal(w.document.getElementById('tk-key-settings').open, false);
    w.RagnarToolkitGuides.render(w.document.getElementById('tk-guide-body'), 'future_tool', {description: '<img src=x>'});
    assert.equal(w.document.querySelectorAll('#tk-guide-body img').length, 0);
  } finally { dom.window.close(); }
});

test('port-change and MAC previews show the interpreted result described by their guides', async () => {
  const {dom, w} = fixture();
  try {
    const requested = [];
    w.fetch = async (url) => {
      requested.push(url);
      const value = url.endsWith('/catalog') ? {tools: [{id:'internetdb', name:'Shodan', available:true}], interfaces:[], capture_profiles:[]}
        : url.endsWith('/payloads') ? {payloads:[]}
        : {jobs: ['port_watch', 'mac_presence'].map((tool, i) => ({id:String(i).repeat(32), tool, name:tool,
          created:new Date().toISOString(), status:'completed', params:{}, artifacts:['output.txt','result.json']}))};
      return {ok:true, json:async()=>value, text:async()=>'{"new_ports":[8080]}'};
    };
    w.eval(fs.readFileSync(path.join(root, 'web/scripts/toolkit.js'), 'utf8'));
    w.document.getElementById('toolkit-tab').classList.remove('hidden'); await flush();
    for (const button of w.document.querySelectorAll('#tk-jobs button')) { button.click(); await flush(); }
    assert.equal(requested.filter(url => url.endsWith('/files/result.json')).length, 2);
    assert.equal(requested.filter(url => url.endsWith('/files/output.txt')).length, 0);
    assert.equal(w.document.getElementById('tk-preview-wrap').hidden, false);
    assert.equal(w.document.activeElement.id, 'tk-preview-wrap');
    assert.equal(w.scrolledTo.id, 'tk-preview-wrap');
  } finally { dom.window.close(); }
});
