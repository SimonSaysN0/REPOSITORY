/* Smoke test for the browser search core (search.js) using the real committed
   index. No browser needed: search.js is DOM-free by design.
     node tests/search_core.test.cjs                                        */
'use strict';
const assert = require('node:assert/strict');
const { existsSync, readFileSync } = require('node:fs');
const { gunzipSync } = require('node:zlib');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const SL = require(path.join(ROOT, 'search.js'));
const CABLE = 'PVC insulated copper electrical cables, 1.1 kV, suitable for industrial applications.';

let checks = 0;
function ok(label, fn) {
  fn();
  checks += 1;
  console.log('  ok -', label);
}

console.log('search core (' + SL.VERSION + ')');

ok('exports the catalog API', () => {
  for (const key of ['tokenize', 'fold', 'parseNumber', 'roleFor', 'relationshipLabel', 'createIndexSearch', 'createListSearch']) {
    assert.equal(typeof SL[key], 'function', key + ' missing');
  }
});

ok('tokenizer folds plurals and drops stop words', () => {
  const tokens = SL.tokenize(CABLE);
  assert.ok(tokens.includes('cable'), 'cables should fold to cable');
  assert.ok(!tokens.includes('suitable'), 'stop words must be dropped');
});

const gzPath = path.join(ROOT, 'data', 'search_index.json.gz');
const jsonPath = path.join(ROOT, 'data', 'search_index.json');
assert.ok(existsSync(gzPath) || existsSync(jsonPath), 'no browser index found - run scripts/build_search_index.py');

const raw = existsSync(gzPath) ? gunzipSync(readFileSync(gzPath)) : readFileSync(jsonPath);
const index = JSON.parse(raw.toString('utf8'));
const catalog = SL.createIndexSearch(index);

ok('index decodes and matches its own stats', () => {
  assert.equal(index.schema, 2, 'unexpected index schema');
  assert.equal(catalog.count, index.stats.records);
  assert.ok(catalog.count > 1000, 'index looks empty');
  assert.ok(Array.isArray(index.stopwords) && index.stopwords.length > 10, 'index must ship its stop-word list');
});

ok('identifier families resolve for a multi-part series', () => {
  const parsed = SL.parseNumber('IS 6092 (Part 6):2026');
  assert.equal(parsed.family, 'IS 6092');
  assert.equal(parsed.part, 'Part 6');
  assert.ok(index.families['IS 6092'] && index.families['IS 6092'].length > 5, 'IS 6092 series should be grouped');
});

let results = [];
ok('index search ranks the cable query and stays fast', () => {
  const started = Date.now();
  results = catalog.search(CABLE, 5);
  const elapsed = Date.now() - started;
  assert.equal(results.length, 5, 'expected five candidates');
  assert.ok(elapsed < 1000, 'search took ' + elapsed + 'ms');
  assert.ok(results[0].id.startsWith('IS'), 'top candidate should be an IS number, got ' + results[0].id);
  assert.ok(/cable|conductors|insulated/i.test(results.map((r) => r.title).join(' ')), 'no cable-related title in: ' + results.map((r) => r.title).join(' | '));
  console.log('       ' + elapsed + 'ms ->', results[0].id, '|', results[0].title.slice(0, 60));
});

ok('every candidate carries the fields app.js renders', () => {
  for (const record of results) {
    for (const key of ['id', 'title', 'scope', 'roles', 'kind', 'tagClass', 'category', 'status', 'edition', 'source_url', 'date_checked']) {
      assert.ok(key in record, key + ' missing on ' + record.id);
    }
    assert.equal(Array.isArray(record.roles), true);
    assert.ok(record.roles[0].length > 0, 'role label empty on ' + record.id);
    assert.ok(record.hits.length > 0, 'no matched terms recorded on ' + record.id);
  }
});

ok('related() returns labelled entries and excludes the record itself', () => {
  const anchor = catalog.view(index.families['IS 6092'][0], []);
  const related = catalog.related(anchor, 4);
  assert.ok(related.length > 0, 'IS 6092 series should surface siblings');
  assert.notEqual(related[0].id, anchor.id);
  assert.ok(related.every((item) => item.id && item.label && item.title !== undefined));
});

const FIXTURES = [
  { id: 'DEMO-EL-001', title: 'Illustrative product specification - low voltage power cable', scope: 'Insulated copper cables for industrial power distribution.', category: 'electrical cable', keywords: ['cable', 'copper', 'pvc'], roles: ['Primary product standard'], relations: [['DEMO-EL-002', 'Test method'], ['DEMO-EL-999', 'Safety']], edition: 'Demo edition 2025', status: 'Unverified demo record' },
  { id: 'DEMO-EL-002', title: 'Illustrative test methods - electric cables', scope: 'Electrical testing of cable constructions.', category: 'electrical cable', keywords: ['cable', 'test'], roles: ['Test method'], relations: [], edition: 'Demo edition 2024', status: 'Unverified demo record' },
  { id: 'DEMO-PPE-001', title: 'Illustrative product specification - protective work gloves', scope: 'Gloves against mechanical risks.', category: 'protective gloves', keywords: ['glove', 'ppe'], roles: ['Primary product standard'], relations: [], edition: 'Demo edition 2025', status: 'Unverified demo record' },
];
const demo = SL.createListSearch(FIXTURES, [], { label: 'demo fixtures' });

ok('fixture backend caps to the best matching group', () => {
  const found = demo.search(CABLE, 5);
  assert.equal(found.length, 2, 'cable query must not leak the glove record');
  assert.equal(found[0].id, 'DEMO-EL-001');
  assert.equal(found[1].id, 'DEMO-EL-002');
  assert.ok(found[0].roles[0] === 'Primary product standard', 'role label should survive normalization');
});

ok('fixture relationships drop dangling references', () => {
  const related = demo.related(demo.search(CABLE, 5)[0]);
  assert.deepEqual(related.map((item) => item.id), ['DEMO-EL-002']);
});

ok('empty and stop-word-only queries return nothing', () => {
  assert.deepEqual(catalog.search('', 5), []);
  assert.deepEqual(catalog.search('the and for with', 5), []);
});

console.log('\n' + checks + ' checks passed, index holds ' + catalog.count + ' records / ' + catalog.terms + ' terms.');
