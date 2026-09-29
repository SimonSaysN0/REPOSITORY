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
    'safety standard': { label: 'Safety', kind: 'safety', tag: 'type-safety' },
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
