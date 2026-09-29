/* StandardLens search core: pure logic, no DOM, so it can be unit tested in Node.
   The browser loads a pre-built index (scripts/build_search_index.py). The
   tokenizer below is a faithful transcription of standardlens/tokenizer.py; the
   authoritative stop-word list ships inside the index itself. */
(function (global) {
  'use strict';

  const TOKEN_PATTERN = /[a-z0-9][a-z0-9.\-]*/g;
  const MIN_TOKEN_LEN = 2;
  const MAX_TOKEN_LEN = 40;
  const NO_FOLD = new Set(['gas', 'bias', 'status', 'canvas', 'atlas', 'corpus', 'genus', 'bus', 'plus', 'iris', 'lens']);
  // Only used when an index carries no stop-word list of its own (demo fixtures).
  const DEFAULT_STOPWORDS = ('a an and are as at be been by for from has have if in into is it its of on or per that the this to with '
    + 'without used using use shall should may must can could will would not no nor any all other others such their they which who what when where '
    + 'procurement purchase supply tender suitable required requirement requirements indian india standard standards method methods tests test '
    + 'code practice practices guideline guidelines general terms term definition section sections part parts revision edition').split(/\s+/);

  function fold(term) {
    if (term.length > 4 && term.endsWith('s') && !term.endsWith('ss') && !NO_FOLD.has(term)) return term.slice(0, -1);
    return term;
  }

  function tokenize(text, stopwords) {
    const stop = stopwords instanceof Set ? stopwords : new Set(stopwords || DEFAULT_STOPWORDS);
    const out = [];
    const matches = String(text == null ? '' : text).toLowerCase().match(TOKEN_PATTERN) || [];
    for (const raw of matches) {
      const token = raw.replace(/^[.\-]+|[.\-]+$/g, '');
      if (token.length < MIN_TOKEN_LEN || token.length > MAX_TOKEN_LEN) continue;
      if (/^\d+$/.test(token) && token.length < 3) continue;
      const term = fold(token);
      if (stop.has(term)) continue;
      out.push(term);
    }
    return out;
  }

  /* BIS identifier shapes: prefix, base number, part label, edition year. */
  const NUMBER_RE = /^([A-Z]{2,12}(?:[ ]*\/[ ]*[A-Z]{2,12})*)[ .-]*(\d{1,9}[A-Z]?)([\s\S]*)$/i;
  const PART_RE = /\(\s*([^()]*?)\s*\)/;
  const YEAR_RE = /:\s*(\d{4})/;

  function parseNumber(value) {
    const text = String(value || '').replace(/\s+/g, ' ').trim().replace('IEC IEEE', 'IEC/IEEE');
    const match = text.match(NUMBER_RE);
    if (!match) return { family: '', part: '', year: '' };
    const prefix = match[1].replace(/\s*\/\s*/g, '/').toUpperCase();
    const number = match[2].toUpperCase();
    const rest = match[3] || '';
    const part = (rest.match(PART_RE) || [])[1] || '';
    const year = (rest.match(YEAR_RE) || [])[1] || '';
    return { family: prefix + ' ' + number, part: part.trim(), year };
  }

  /* BIS type_of_standard -> UI role. Unknown values keep their own label. */
  const TYPE_ROLES = {
    'product specification': { label: 'Primary product standard', kind: 'primary', tag: 'type-primary' },
    'service specification': { label: 'Service specification', kind: 'primary', tag: 'type-primary' },
    'process specification': { label: 'Process specification', kind: 'primary', tag: 'type-primary' },
    'methods of tests': { label: 'Test method', kind: 'test', tag: 'type-test' },
    'method of test': { label: 'Test method', kind: 'test', tag: 'type-test' },
    'test method': { label: 'Test method', kind: 'test', tag: 'type-test' },
    'safety standard': { label: 'Safety', kind: 'safety', tag: 'type-safety' },
    'safety': { label: 'Safety', kind: 'safety', tag: 'type-safety' },
    'primary product standard': { label: 'Primary product standard', kind: 'primary', tag: 'type-primary' },
    'material': { label: 'Material', kind: 'reference', tag: 'type-ref' },
    'installation': { label: 'Installation', kind: 'reference', tag: 'type-ref' },
    'code of practice': { label: 'Code of practice', kind: 'practice', tag: 'type-practice' },
    'terminology': { label: 'Terminology', kind: 'reference', tag: 'type-ref' },
    'dimensions': { label: 'Dimensions', kind: 'reference', tag: 'type-ref' },
    'system standard': { label: 'System standard', kind: 'reference', tag: 'type-ref' },
    'others': { label: 'Standard', kind: 'reference', tag: 'type-ref' },
  };
  const RELATIONSHIP_LABELS = {
    referred_standard: 'Referred standard',
    referred: 'Referred standard',
    normative_reference: 'Normative reference',
    superseding_standard: 'Supersedes',
    superseded_by: 'Superseded by',
    test_method_for: 'Test method for',
    series_member: 'Same number series (derived)',
  };

  function roleFor(type) {
    const key = String(type || '').trim().toLowerCase();
    if (TYPE_ROLES[key]) return TYPE_ROLES[key];
    if (!key) return { label: 'Standard', kind: 'reference', tag: 'type-ref' };
    return { label: key.replace(/\b\w/g, (c) => c.toUpperCase()), kind: 'reference', tag: 'type-ref' };
  }

  function relationshipLabel(kind) {
    const key = String(kind || '').trim().toLowerCase();
    if (RELATIONSHIP_LABELS[key]) return RELATIONSHIP_LABELS[key];
    return key ? key.replace(/[_-]/g, ' ').replace(/\b\w/, (c) => c.toUpperCase()) : 'Related standard';
  }

  /* ------------------------------------------------------------------ *
   * Catalog access.
   *
   * Two backends share one result shape so app.js can render either one
   * without knowing which produced a row:
   *   createIndexSearch(index)      -> pre-built search index (schema 2)
   *   createListSearch(rows, edges) -> plain record array (demo fixtures or
   *                                    the data/standards.json fallback)
   * ------------------------------------------------------------------ */

  function text(value) {
    return String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
  }

  /* One view model for both backends; app.js renders exactly these fields. */
  function viewModel(base, role, hits) {
    return {
      id: text(base.id),
      title: text(base.title),
      scope: text(base.scope),
      roles: [role.label],
      kind: role.kind,
      tagClass: role.tag,
      category: text(base.category),
      status: text(base.status),
      edition: text(base.edition),
      publication_date: text(base.publication_date),
      equivalence: text(base.equivalence),
      certification: text(base.certification),
      number_of_amendments: text(base.number_of_amendments),
      amendment_year: text(base.amendment_year),
      source_url: text(base.source_url),
      date_checked: text(base.date_checked),
      hits: hits || [],
      score: base.score || 0,
      ref: base.ref === undefined ? null : base.ref,
    };
  }

  /* Recorded edges plus identifier-family siblings, deduped and capped. */
  function relatedFrom(edges, siblings, excludeId, cap) {
    const seen = new Set([String(excludeId || '').toLowerCase()]);
    const out = [];
    for (const item of edges.concat(siblings)) {
      const id = text(item.id);
      if (!id || seen.has(id.toLowerCase())) continue;
      seen.add(id.toLowerCase());
      out.push({
        id,
        title: text(item.title),
        status: text(item.status) || 'linked',
        label: text(item.label) || 'Related standard',
      });
      if (out.length >= cap) break;
    }
    return out;
  }


  /* Query engine over the pre-built index. Search cost is proportional to the
     postings of the query terms, not to the 23,866-record catalogue, and only
     the handful of winning rows are ever expanded into full view models. */
  function createIndexSearch(index) {
    const columns = index.columns || [];
    const rows = index.records || [];
    const indexAt = {};
    columns.forEach((name, position) => { indexAt[name] = position; });
    const cell = (row, name) => {
      const position = indexAt[name];
      return position === undefined ? '' : text(row[position]);
    };
    const stopwords = new Set(index.stopwords || DEFAULT_STOPWORDS);
    const postings = new Map();
    for (const term of Object.keys(index.postings || {})) {
      postings.set(term, Int32Array.from(index.postings[term]));
    }
    const total = rows.length;
    const idfCache = new Map();
    function idf(term) {
      if (idfCache.has(term)) return idfCache.get(term);
      const list = postings.get(term);
      const docFreq = list ? list.length / 2 : 0;
      const value = docFreq ? Math.log(1 + total / docFreq) : 0;
      idfCache.set(term, value);
      return value;
    }

    /* Edges arrive as {s: sourceRow, r: kind, t: targetRow | tid: targetId}. */
    let edgeMap = null;
    function edgeIndex() {
      if (edgeMap) return edgeMap;
      edgeMap = new Map();
      for (const edge of index.relationships || []) {
        const source = edge.s;
        if (source === undefined) continue;
        if (!edgeMap.has(source)) edgeMap.set(source, []);
        edgeMap.get(source).push(edge);
      }
      return edgeMap;
    }

    function view(row, hits) {
      const role = roleFor(cell(rows[row] || [], 'type'));
      return viewModel({
        ref: row,
        id: cell(rows[row] || [], 'id'),
        title: cell(rows[row] || [], 'title'),
        scope: cell(rows[row] || [], 'scope'),
        category: cell(rows[row] || [], 'category') || cell(rows[row] || [], 'sector'),
        status: cell(rows[row] || [], 'status') || 'Not provided',
        edition: cell(rows[row] || [], 'year') || 'Edition unknown',
        publication_date: cell(rows[row] || [], 'pub'),
        equivalence: cell(rows[row] || [], 'equiv'),
        certification: cell(rows[row] || [], 'certification'),
        number_of_amendments: cell(rows[row] || [], 'amendments'),
        amendment_year: cell(rows[row] || [], 'amendment_year'),
        source_url: cell(rows[row] || [], 'url'),
        date_checked: cell(rows[row] || [], 'checked'),
        score: 0,
      }, role, hits);
    }

    function related(record, cap) {
      const limit = cap || 6;
      const row = rows[record.ref] || [];
      const edges = (edgeIndex().get(record.ref) || []).map((edge) => {
        const target = edge.t === undefined ? null : rows[edge.t];
        return {
          id: target ? cell(target, 'id') : text(edge.tid),
          title: target ? cell(target, 'title') : 'Not in the loaded export',
          status: target ? (cell(target, 'status') || 'linked') : 'unresolved',
          label: relationshipLabel(edge.r),
        };
      });
      const family = text(cell(row, 'fam'));
      const siblings = [];
      if (family && index.families && index.families[family]) {
        for (const member of index.families[family]) {
          if (member === record.ref) continue;
          const target = rows[member] || [];
          siblings.push({
            id: cell(target, 'id'),
            title: cell(target, 'title'),
            status: cell(target, 'status') || 'linked',
            label: 'Same number series (derived)',
          });
        }
      }
      return relatedFrom(edges, siblings, record.id, limit);
    }

    /* Relevance = tf-idf over the inverted index, averaged across the query
       terms, so a rare matched word outranks a common one. Results are the top
       `limit` rows only; allied records are pulled in by related(). */
    function search(query, limit) {
      const wanted = limit || 5;
      const terms = [...new Set(tokenize(query, stopwords))];
      if (!terms.length) return [];
      const scores = new Map();
      const matches = new Map();
      for (const term of terms) {
        const list = postings.get(term);
        if (!list) continue;
        const weight = idf(term);
        for (let i = 0; i < list.length; i += 2) {
          const row = list[i];
          const freq = list[i + 1] || 1;
          scores.set(row, (scores.get(row) || 0) + (1 + Math.log(freq)) * weight);
          let found = matches.get(row);
          if (!found) { found = []; matches.set(row, found); }
          found.push(term);
        }
      }
      const scored = [...scores].map(([row, score]) => ({
        row, score: score / terms.length, hits: matches.get(row),
      }));
      scored.sort((a, b) => (b.score - a.score) || (a.row - b.row));
      return scored.slice(0, wanted).map((item) => {
        const record = view(item.row, item.hits);
        record.score = item.score;
        return record;
      });
    }

    return {
      kind: 'index',
      demo: false,
      count: total,
      terms: postings.size,
      label: String((index.source && index.source.kind) || '') === 'bis_incremental_crawl' ? 'detail crawl' : 'catalogue',
      source: index.source || {},
      stats: index.stats || {},
      coverage: index.coverage || {},
      generatedAt: index.generated_at || '',
      pipeline: index.pipeline || '',
      search,
      view,
      related,
    };
  }


  /* Fallback / fixtures backend: a plain record array with recorded edges.
     Used for the demo fixtures and for data/standards.json when the index is
     unavailable. Tokenizing happens once, at load. */
  function normalizeRow(row) {
    const type = text(row.type_of_standard) || (Array.isArray(row.roles) ? text(row.roles[0]) : '');
    return {
      id: text(row.is_number || row.id),
      title: text(row.title),
      scope: text(row.scope),
      type,
      role: roleFor(type),
      category: text(row.product_category || row.category || row.sector),
      status: text(row.status) || 'Not provided',
      edition: text(row.edition_year || row.edition) || 'Edition unknown',
      publication_date: text(row.publication_date),
      equivalence: text(row.degree_of_equivalence),
      certification: text(row.certification),
      number_of_amendments: text(row.number_of_amendments),
      amendment_year: text(row.amendment_year),
      source_url: text(row.source_url),
      date_checked: text(row.date_checked || row.last_checked),
      keywords: Array.isArray(row.keywords) ? row.keywords.map((word) => text(word).toLowerCase()) : [],
      quoted: Array.isArray(row.relations) ? row.relations : [],
    };
  }

  function createListSearch(rows, edges, options) {
    const opts = options || {};
    const stopwords = new Set(opts.stopwords || DEFAULT_STOPWORDS);
    const list = (rows || []).map(normalizeRow);
    const byId = new Map();
    list.forEach((item, position) => { if (item.id) byId.set(item.id.toLowerCase(), position); });
    const edgeMap = new Map();
    for (const edge of edges || []) {
      const source = text(edge.source_is || edge.s);
      const target = text(edge.target_is || edge.t);
      const kind = text(edge.relationship || edge.relationship_type || edge.r) || 'related standard';
      if (!source || !target) continue;
      if (!edgeMap.has(source.toLowerCase())) edgeMap.set(source.toLowerCase(), []);
      edgeMap.get(source.toLowerCase()).push({
        id: target,
        title: byId.has(target.toLowerCase()) ? list[byId.get(target.toLowerCase())].title : 'Not in the loaded export',
        status: byId.has(target.toLowerCase()) ? (list[byId.get(target.toLowerCase())].status || 'linked') : 'unresolved',
        label: relationshipLabel(kind),
      });
    }
    list.forEach((item) => {
      const bag = new Set(item.keywords);
      for (const word of tokenize([item.title, item.scope, item.category, item.status].filter(Boolean).join(' '), stopwords)) bag.add(word);
      item.terms = bag;
      item.relationIds = (edgeMap.get(item.id.toLowerCase()) || []).map((edge) => edge.id)
        .concat(item.quoted.filter((pair) => byId.has(text(pair[0]).toLowerCase())).map((pair) => text(pair[0])))
        .filter(Boolean);
    });

    function view(position, hits) {
      const item = list[position];
      const record = viewModel(item, item.role, hits);
      record.ref = position;
      return record;
    }

    function search(query, limit) {
      const wanted = limit || 5;
      const terms = [...new Set(tokenize(query, stopwords))];
      if (!terms.length) return [];
      const scored = [];
      for (let position = 0; position < list.length; position++) {
        const terms2 = list[position].terms;
        const found = terms.filter((term) => terms2.has(term));
        if (!found.length) continue;
        let score = found.length / Math.sqrt(terms.length * Math.max(1, terms2.size));
        if (list[position].role.kind === 'primary') score += 0.09;
        scored.push({ position, score, hits: found });
      }
      scored.sort((a, b) => b.score - a.score);
      /* Cap to the best matching group while keeping its allied records. */
      const anchor = scored.find((item) => list[item.position].role.kind === 'primary');
      let picked = scored;
      if (anchor) {
        const linked = new Set(list[anchor.position].relationIds.map((id) => id.toLowerCase()));
        picked = scored.filter((item) => item.position === anchor.position
          || linked.has(list[item.position].id.toLowerCase()));
        for (let position = 0; position < list.length && picked.length < wanted; position++) {
          const id = list[position].id.toLowerCase();
          if (linked.has(id) && !picked.some((item) => list[item.position].id.toLowerCase() === id)) {
            picked.push({ position, score: 0, hits: [] });
          }
        }
      }
      return picked.slice(0, wanted).map((item) => {
        const record = view(item.position, item.hits);
        record.score = item.score;
        return record;
      });
    }

    function related(record, cap) {
      const item = list[record.ref] || {};
      const quoted = (item.quoted || []).filter((pair) => byId.has(text(pair[0]).toLowerCase()))
        .map((pair) => {
          const target = list[byId.get(text(pair[0]).toLowerCase())];
          return { id: target.id, title: target.title, status: target.status || 'linked', label: text(pair[1]) || 'Related standard' };
        });
      return relatedFrom((edgeMap.get(item.id ? item.id.toLowerCase() : '') || []), quoted, item.id, cap || 6);
    }

    return {
      kind: 'list',
      demo: !!opts.demo,
      count: list.length,
      label: opts.label || 'records',
      source: opts.source || {},
      stats: { records: list.length },
      coverage: {},
      generatedAt: '',
      pipeline: 'inline',
      search,
      view,
      related,
    };
  }

  const api = {
    VERSION: '0.2.0',
    DEFAULT_STOPWORDS,
    fold,
    tokenize,
    parseNumber,
    roleFor,
    relationshipLabel,
    createIndexSearch,
    createListSearch,
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else global.StandardLens = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);

