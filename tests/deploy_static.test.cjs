/* Deploy smoke test: serve the repository root exactly as Vercel serves a
   framework-less static project, then verify that every asset app.js asks for
   is reachable and decodable, and that the static config is sound.
     node tests/deploy_static.test.cjs                                       */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const { gunzipSync } = require('node:zlib');

const ROOT = path.join(__dirname, '..');
const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.gz': 'application/gzip',
};

let checks = 0;
function ok(label, condition, extra) {
  assert.ok(condition, label + (extra ? ' -> ' + extra : ''));
  checks += 1;
  console.log('  ok -', label);
}

const server = http.createServer((req, res) => {
  const clean = decodeURIComponent(req.url.split('?')[0]);
  const file = path.join(ROOT, clean === '/' ? 'index.html' : clean.replace(/^\/+/, ''));
  if (!file.startsWith(ROOT) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404).end('not found');
    return;
  }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});

const ignored = fs.existsSync(path.join(ROOT, '.vercelignore'))
  ? fs.readFileSync(path.join(ROOT, '.vercelignore'), 'utf8').split('\n').map((l) => l.trim()).filter((l) => l && !l.startsWith('#'))
  : [];

function isIgnored(target) {
  return ignored.some((rule) => {
    const normalized = rule.replace(/\/$/, '');
    if (normalized.includes('*')) {
      const pattern = '^' + normalized.split('*').map((part) => part.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('.*') + '(?:/.*)?$';
      return new RegExp(pattern).test(target);
    }
    return target === normalized || target.startsWith(normalized + '/');
  });
}

async function main() {
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const base = 'http://127.0.0.1:' + server.address().port;

  console.log('vercel.json');
  const config = JSON.parse(fs.readFileSync(path.join(ROOT, 'vercel.json'), 'utf8'));
  ok('framework detection is disabled (no FastHTML/FastAPI build)', config.framework === null);
  ok('the build step is skipped', config.buildCommand === '');
  ok('index.html sits in the project root (Root Directory ./)', fs.existsSync(path.join(ROOT, 'index.html')));
  ok('no outputDirectory is demanded', config.outputDirectory === null || config.outputDirectory === undefined);
  ok('cache headers cover /data', JSON.stringify(config.headers || []).includes('stale-while-revalidate'));

  console.log('served pages');
  const page = await fetch(base + '/');
  const html = await page.text();
  ok('GET / returns the app shell', page.status === 200 && html.includes('id="query"'), 'status ' + page.status);
  ok('the shell loads the search core before app.js', html.indexOf('search.js') > 0 && html.indexOf('search.js') < html.indexOf('app.js'));

  for (const asset of ['/app.js', '/search.js', '/styles.css']) {
    const response = await fetch(base + asset);
    ok('GET ' + asset, response.status === 200 && (await response.text()).length > 100, 'status ' + response.status);
  }

  console.log('data assets referenced by app.js');
  const sources = [...fs.readFileSync(path.join(ROOT, 'app.js'), 'utf8').matchAll(/url:'([^']+)'/g)].map((m) => m[1]);
  ok('app.js declares a data fallback chain', sources.length >= 2, sources.join(', '));
  const primary = sources[0];
  ok('the first asset exists and is deployable', fs.existsSync(path.join(ROOT, primary)) && !isIgnored(primary), primary);

  const gz = await fetch(base + '/' + primary);
  ok('GET /' + primary, gz.status === 200, 'status ' + gz.status);
  const bytes = new Uint8Array(await gz.arrayBuffer());
  const sniffed = bytes[0] === 0x1f && bytes[1] === 0x8b;
  ok('magic-number sniffing agrees with the .gz suffix', sniffed === primary.endsWith('.gz'));
  const payload = JSON.parse(sniffed ? gunzipSync(bytes).toString('utf8') : Buffer.from(bytes).toString('utf8'));
  ok('payload decodes into a usable index', payload.schema === 2 && payload.records.length > 1000, payload.records.length + ' records');

  console.log('deployment hygiene');
  for (const junk of ['logs', '__pycache__', '_tmp_index.json', '_probe.py', 'bis_scraper', 'scripts', 'standardlens', 'tests', 'data/bis_crawl/standards.json', 'data/bis_metadata.sqlite3']) {
    ok(junk + ' is ignored, not deployed', isIgnored(junk) || !fs.existsSync(path.join(ROOT, junk)), 'still tracked');
  }
  ok('the offline catalogue dump is not shipped to the browser', isIgnored('data/standards.json'));
  ok('the 6 MB reviewed CSV is not shipped to the browser', ignored.includes('data/*.csv'));

  server.close();
  console.log('\n' + checks + ' checks passed.');
}

main().catch((error) => {
  server.close();
  console.error('\nFAILED:', error.message);
  process.exit(1);
});
