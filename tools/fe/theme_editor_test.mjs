// Test of theme_editor.html in headless Chromium (CDP over the WebSocket of node >= 22):
// replays THEME_GUIDE.txt and GUIDA_TEMA_ita.txt (delete, add, "Make 4:3", "Make detail"
// with the blocks of keys of the guides) and checks that the result is themes/citypop;
// then checks "Import .ini".
// Usage: node tools/fe/theme_editor_test.mjs      (CHROME=<path> if not found)
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const FE = path.dirname(new URL(import.meta.url).pathname);
const SD = path.join(FE, 'sd', 'frontier');
const THEMES = path.join(SD, 'themes');
const pw = path.join(process.env.HOME || '', '.cache', 'ms-playwright');
const CHROME = process.env.CHROME || (fs.existsSync(pw) ? fs.readdirSync(pw).filter(d => /^chromium-\d+$/.test(d)).sort().reverse()
  .map(d => path.join(pw, d, 'chrome-linux64', 'chrome')).find(f => fs.existsSync(f)) : null);
if (!CHROME) { console.log('Chromium not found: CHROME=<path to chrome>'); process.exit(2); }

const sleep = ms => new Promise(r => setTimeout(r, ms));
const port = 9300 + Math.floor(Math.random() * 600);
const ch = spawn(CHROME, ['--headless=new', '--no-sandbox', `--remote-debugging-port=${port}`, 'about:blank'], { stdio: 'ignore' });
let targets = [];
for (let i = 0; i < 50 && !targets.length; i++) {
  try { targets = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).filter(t => t.type === 'page'); } catch {}
  await sleep(200);
}
const ws = new WebSocket(targets[0].webSocketDebuggerUrl);
await new Promise(r => { ws.onopen = r; });
let id = 0;
const pending = new Map(), logs = [];
ws.onmessage = m => {
  const d = JSON.parse(m.data);
  if (d.id && pending.has(d.id)) { pending.get(d.id)(d); pending.delete(d.id); }
  if (d.method === 'Runtime.exceptionThrown') logs.push('exception: ' + (d.params.exceptionDetails.exception?.description || d.params.exceptionDetails.text));
};
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const ev = async expr => {
  const r = await send('Runtime.evaluate', { expression: expr, awaitPromise: true, returnByValue: true });
  if (r.result.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || r.result.exceptionDetails.text);
  return r.result.result.value;
};
await send('Runtime.enable');
await send('Page.navigate', { url: 'file://' + path.join(FE, 'theme_editor.html') });
await sleep(1500);
await ev(`window.alert = m => console.log(m); window.confirm = () => true; 1`);

// "  [name]" (+ "  delete") and "    key=value" ("   (empty)" = key to empty) blocks of a step
function blocks(txt) {
  const out = [];
  for (const l of txt.split('\n')) {
    let m = /^  \[([^\]]+)\](\s+delete)?\s*$/.exec(l);
    if (m) { out.push({ name: m[1], del: !!m[2], props: {} }); continue; }
    m = /^    ([a-z_]+)=(.*)$/.exec(l);
    if (m && out.length) out[out.length - 1].props[m[1]] = m[2] === '   (empty)' ? null : m[2];
  }
  return out;
}

// sections and keys of an ini file, fonts of default as in the guides
function canon(txt) {
  const t = [];
  for (let l of txt.split('\n')) {
    l = l.trim();
    if (!l || l[0] === ';') continue;
    if (l[0] === '[') { t.push([l, []]); continue; }
    t[t.length - 1][1].push(l.replace('../simple/fonts/', 'fonts/'));
  }
  return JSON.stringify(t.map(([n, k]) => [n, k.sort()]));
}

let failed = 0;
const check = (ok, what) => { console.log((ok ? 'ok    ' : 'FAIL  ') + what); if (!ok) failed++; };

for (const guide of ['THEME_GUIDE.txt', 'GUIDA_TEMA_ita.txt']) {
  const g = fs.readFileSync(path.join(SD, guide), 'utf8').replace(/\nPASSO /g, '\nSTEP ');
  const step = n => g.split('\nSTEP ').find(x => x.startsWith(n + ' ')) || '';
  const B = { s3: blocks(step(3)), s4: blocks(step(4)), s5: blocks(step(5)), s6: blocks(step(6)) };
  // the steps of the guide, done as a user would with the functions of the buttons
  const r = await ev(`(async B => {
    const log = [];
    const setAll = (obj, props) => { for (const k of Object.keys(obj)) delete obj[k]; Object.assign(obj, props); };
    const applyDiff = (t, bl) => { for (const b of bl) {
      if (b.name === 'theme') { for (const [k, v] of Object.entries(b.props)) if (v === null) delete t.global[k]; else t.global[k] = v; continue; }
      const i = t.elements.findIndex(e => e.name === b.name);
      if (i < 0) { log.push('missing ' + b.name); continue; }
      if (b.del) { t.elements.splice(i, 1); continue; }
      for (const [k, v] of Object.entries(b.props)) if (v === null) delete t.elements[i].props[k]; else t.elements[i].props[k] = v;
    } };
    const add = (after, b) => {
      select(after); document.getElementById('addType').value = b.props.type; addElement();
      const el = selected(); el.name = b.name; setAll(el.props, b.props); return S.sel;
    };
    newTheme(false);                                             // STEP 2-3
    while (theme().elements.length) { select(theme().elements.length - 1); remove(); }
    setAll(theme().global, B.s3[0].props);
    let last = -1;
    for (const b of B.s3.slice(1)) last = add(last, b);
    S.cur = 'theme.ini'; make43(); applyDiff(theme(), B.s4);     // STEP 4
    S.cur = 'theme.ini'; makeDetail();                           // STEP 5
    for (const n of ['position', 'list', 'text_system', 'text_desc', 'letter_shadow', 'letter_back', 'letter', 'name']) {
      const i = theme().elements.findIndex(e => e.name === n);
      if (i < 0) log.push('no ' + n + ' to delete'); else { select(i); remove(); }
    }
    const blk = n => B.s5.find(b => b.name === n);
    setAll(theme().global, B.s5[0].props);
    for (const el of theme().elements) { if (blk(el.name)) setAll(el.props, blk(el.name).props); else log.push('no block for ' + el.name); }
    const after = { video: 'image', players: 'genre', description: 'stars', text_desc: 'description', versions_title: 'text_desc', versions_pos: 'versions_title', versions: 'versions_pos' };
    for (const [n, a] of Object.entries(after)) add(theme().elements.findIndex(e => e.name === a), blk(n));
    S.cur = 'detail.ini'; make43(); applyDiff(theme(), B.s6);    // STEP 6
    const out = {};
    for (const v of VARIANTS) out[v] = S.variants[v] ? serializeIni(S.variants[v], '') : '';
    return { log, out };
  })(${JSON.stringify(B)})`);
  check(!r.log.length, `${guide}: steps done${r.log.length ? ' (' + r.log.join('; ') + ')' : ''}`);
  for (const v of ['theme.ini', 'theme_43.ini', 'detail.ini', 'detail_43.ini'])
    check(canon(r.out[v]) === canon(fs.readFileSync(path.join(THEMES, 'citypop', v), 'utf8')), `${guide}: ${v} = themes/citypop/${v}`);
}

// Import .ini: by name into its variant, another name into the current one
const file = (name, f) => `new File([${JSON.stringify(fs.readFileSync(f, 'utf8'))}], ${JSON.stringify(name)})`;
await ev(`(newTheme(false), S.dirty = false, 1)`);
await ev(`importIni([${file('theme.ini', path.join(THEMES, 'citypop', 'theme.ini'))}, ${file('detail.ini', path.join(THEMES, 'citypop', 'detail.ini'))}]).then(() => 1)`);
check(await ev(`S.variants['theme.ini'].global.name === 'City Pop' && S.variants['detail.ini'].elements.length === 18 && S.cur === 'theme.ini'`), 'Import .ini: theme.ini and detail.ini into their variants');
await ev(`(S.cur = 'detail.ini', 1)`);
await ev(`importIni([${file('blue.ini', path.join(THEMES, 'citypop_blue', 'theme_43.ini'))}]).then(() => 1)`);
check(await ev(`S.variants['detail.ini'].global.name === 'City Pop Blue' && S.cur === 'detail.ini'`), 'Import .ini: another name into the current variant');
check(await ev(`(undo(), S.variants['detail.ini'].global.name === 'City Pop')`), 'Import .ini: Undo');

// Make screensaver: detail.ini without the versions
await ev(`(S.cur = 'detail.ini', makeSaver(), 1)`);
check(await ev(`S.cur === 'screensaver.ini' && S.variants['screensaver.ini'].elements.length === S.variants['detail.ini'].elements.length - 3 && !S.variants['screensaver.ini'].elements.some(e => e.name.startsWith('versions'))`), 'Make screensaver: detail.ini without the versions');
check(!logs.length, 'no JavaScript errors' + (logs.length ? ': ' + logs.join('; ') : ''));

ws.close();
ch.kill();
console.log(failed ? `${failed} FAILED` : 'all ok');
process.exit(failed ? 1 : 0);
