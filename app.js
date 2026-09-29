/* StandardLens MVP: all records below are illustrative fixtures, not BIS records. */
const demoRecords = [
 {id:'DEMO-EL-001',title:'Illustrative product specification — low voltage power cable',scope:'Example record for insulated copper cables used in industrial power distribution.',category:'electrical cable',keywords:['cable','wire','copper','pvc','insulated','voltage','industrial'],roles:['Primary product standard'],relations:[['DEMO-EL-002','Test method'],['DEMO-EL-003','Safety'],['DEMO-EL-004','Installation']],edition:'Demo edition 2025',status:'Unverified demo record'},
 {id:'DEMO-EL-002',title:'Illustrative test methods — electric cables',scope:'Example record for electrical and mechanical testing of cable constructions.',category:'electrical cable',keywords:['cable','wire','test','testing','electrical','conductor'],roles:['Test method'],relations:[],edition:'Demo edition 2024',status:'Unverified demo record'},
 {id:'DEMO-EL-003',title:'Illustrative safety requirements — electrical installations',scope:'Example record for protection and safety requirements for electrical installations.',category:'electrical cable',keywords:['cable','electrical','safety','installation','voltage','protection'],roles:['Safety'],relations:[],edition:'Demo edition 2023',status:'Unverified demo record'},
 {id:'DEMO-PPE-001',title:'Illustrative product specification — protective work gloves',scope:'Example record for protective gloves used against mechanical risks in workplaces.',category:'protective gloves',keywords:['glove','gloves','ppe','protective','hand','safety','mechanical','worker'],roles:['Primary product standard'],relations:[['DEMO-PPE-002','Test method'],['DEMO-PPE-003','Safety']],edition:'Demo edition 2025',status:'Unverified demo record'},
 {id:'DEMO-PPE-002',title:'Illustrative test methods — protective gloves',scope:'Example record for performance and durability testing of protective gloves.',category:'protective gloves',keywords:['glove','gloves','test','testing','protective','mechanical'],roles:['Test method'],relations:[],edition:'Demo edition 2024',status:'Unverified demo record'},
 {id:'DEMO-PPE-003',title:'Illustrative safety requirements — personal protective equipment',scope:'Example record for general workplace PPE safety and selection.',category:'protective gloves',keywords:['ppe','protective','safety','glove','gloves','worker','hazard'],roles:['Safety'],relations:[],edition:'Demo edition 2023',status:'Unverified demo record'},
 {id:'DEMO-CIV-001',title:'Illustrative product specification — structural steel sections',scope:'Example record for steel sections used in building and civil construction.',category:'structural steel',keywords:['steel','structural','section','building','construction','metal'],roles:['Primary product standard'],relations:[['DEMO-CIV-002','Test method'],['DEMO-CIV-003','Material']],edition:'Demo edition 2025',status:'Unverified demo record'},
 {id:'DEMO-CIV-002',title:'Illustrative test methods — mechanical testing of steel',scope:'Example record for mechanical property testing of steel products.',category:'structural steel',keywords:['steel','test','testing','mechanical','strength','material'],roles:['Test method'],relations:[],edition:'Demo edition 2024',status:'Unverified demo record'},
 {id:'DEMO-CIV-003',title:'Illustrative material requirements — steel products',scope:'Example record for material characteristics and quality checks for steel.',category:'structural steel',keywords:['steel','material','construction','metal','quality'],roles:['Material'],relations:[],edition:'Demo edition 2023',status:'Unverified demo record'}
];
/* Ranking and record access live in search.js (DOM-free, unit tested in Node)
   on top of the pre-built index produced by scripts/build_search_index.py.
   This file only renders. */
const SL=window.StandardLens;
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const query=$('#query'), resultsEl=$('#results'), requirementsEl=$('#requirements'), relationsEl=$('#relationships');
let lastResults=[];
let source=null;                       // active catalog: index-backed or fixtures
const fixtureSource=()=>SL?SL.createListSearch(demoRecords,[],{label:'demo fixtures',demo:true}):null;
source=fixtureSource();               // render the fixtures until real data arrives
function requirements(s){const t=s.toLowerCase();const found={Product:'',Material:'',Performance:'',Application:'',Hazards:''};
 if(/cable|wire/.test(t))found.Product='Electrical cable';else if(/glove|ppe|protective/.test(t))found.Product=/glove/.test(t)?'Protective gloves':'Personal protective equipment';else if(/steel|construction|building/.test(t))found.Product='Structural steel';
 if(/copper/.test(t))found.Material='Copper';else if(/steel/.test(t))found.Material='Steel';else if(/pvc/.test(t))found.Material='PVC';
 const volt=t.match(/\b\d+(?:\.\d+)?\s*(?:kv|v)\b/i);if(volt)found.Performance=volt[0].replace(/\s+/g,' ').toUpperCase();else if(/mechanical/.test(t))found.Performance='Mechanical protection';
 if(/industrial/.test(t))found.Application='Industrial';else if(/building|construction/.test(t))found.Application='Building / construction';else if(/worker|workplace/.test(t))found.Application='Workplace';
 if(/safety|hazard|protect/.test(t))found.Hazards='Safety / protection';return found}
function rank(s){return source?source.search(s,5):[]}
function labelFor(r){return r.roles[0]||'Related standard'}
function renderRequirements(s){const req=requirements(s);requirementsEl.innerHTML=Object.entries(req).filter(([k])=>k!=='Hazards'||req[k]).map(([k,v])=>`<div class="req-item"><div class="req-label">${k.toUpperCase()}</div><div class="req-value ${v?'':'req-empty'}">${escapeHtml(v||'Not detected')}</div></div>`).join('')}
function escapeHtml(v){return String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function safeSourceUrl(value){try{const url=new URL(String(value||''),window.location.href);return url.protocol==='https:'||url.protocol==='http:'?url.href:''}catch{return''}}
function renderResults(found){lastResults=found;$('#resultCount').textContent=found.length?`${found.length} recommendation${found.length===1?'':'s'}`:'No matches';const candidateMetric=$('#candidateMetric');if(candidateMetric)candidateMetric.textContent=String(found.length);const recommendationNavCount=$('#recommendationNavCount');if(recommendationNavCount)recommendationNavCount.textContent=String(found.length);
 if(!found.length){resultsEl.innerHTML=`<div class="empty-state"><b>No matching records</b>${source&&source.demo?'Try a product description for electrical cable, protective gloves, or structural steel. Add your verified standards data to support other categories.':'Try product nouns, materials, or test verbs, for example "PVC insulated copper cable 1.1 kV" or "fertilizer sampling moisture determination". Search covers the titles, categories and scopes of every loaded record.'}</div>`;relationsEl.innerHTML='<div class="empty-state">No recorded relationships for this query.</div>';return}
 resultsEl.innerHTML=found.map((r,i)=>{const type=r.roles[0].toLowerCase();const tagClass=r.tagClass|| (type.includes('test')?'type-test':type.includes('safety')?'type-safety':'type-primary');const why=r.hits.length?`Matched terms: ${r.hits.join(', ')}. Candidate scope: ${r.scope||'No scope supplied in the source export.'}`:`Related to the primary product candidate. ${r.scope||'No scope supplied in the source export.'}`;const href=safeSourceUrl(r.source_url);const source=href?`<a class="record-source" href="${escapeHtml(href)}" target="_blank" rel="noopener">Source ↗</a>`:'';const extra=[r.publication_date?`Published ${r.publication_date}`:'',r.equivalence?`Equivalence: ${r.equivalence}`:'',r.amendment_year?`Amendment year ${r.amendment_year}`:'',r.number_of_amendments?`${r.number_of_amendments} amendment(s)`:'' ,r.certification?`Certification: ${r.certification}`:'',r.date_checked?`Checked ${r.date_checked}`:''].filter(Boolean).map(v=>`<span class="tag">${escapeHtml(v)}</span>`).join('');return `<article class="result-card"><div class="result-top"><span class="rank">${String(i+1).padStart(2,'0')}</span><div class="result-main"><div class="standard-title">${escapeHtml(r.id)}</div><div class="standard-sub">${escapeHtml(r.title)}</div></div><span class="match-pill">CANDIDATE</span></div><div class="result-tags"><span class="tag ${tagClass}">${escapeHtml(labelFor(r))}</span><span class="tag">${escapeHtml(r.category||'Unclassified')}</span><span class="tag">${escapeHtml(r.status||'Unverified')}</span><span class="tag">${escapeHtml(r.edition||'Edition unknown')}</span>${extra}</div>${source}<button class="why-toggle">Why this match? <span>⌄</span></button><div class="why-text">${escapeHtml(why)}. This prototype ranks by keyword overlap and recorded relationships; it does not perform semantic AI retrieval. Review source and applicability before use.</div></article>`}).join('');
 $$('.why-toggle').forEach(b=>b.addEventListener('click',()=>b.closest('.result-card').classList.toggle('expanded')));renderRelations(found)}
function relationEntries(found){if(!source)return[];const anchor=found.find(r=>r.kind==='primary')||found[0];if(!anchor)return[];return source.related(anchor,6).map(item=>({target:{id:escapeHtml(item.id),title:escapeHtml(item.title||''),status:escapeHtml(item.status||'linked')},type:escapeHtml(item.label)}))}
function renderRelations(found){const rel=relationEntries(found);if(!rel.length){relationsEl.innerHTML='<div class="empty-state">No recorded relationships for this query.</div>';return}relationsEl.innerHTML=rel.map(({target,type})=>`<div class="relation-item"><span class="relation-icon ${type==='Safety'?'safety':type==='Normative reference'?'normative':''}">${type==='Test method'?'⌁':type==='Safety'?'△':'↗'}</span><div class="relation-info"><div class="relation-type">${type}</div><div class="relation-name">${target.id} · ${target.title.replace('Illustrative ','')}</div></div><span class="relation-count">${target.status||'linked'}</span></div>`).join('')}
function analyze(){const s=query.value.trim();$('#errorMessage').style.display='none';if(s.length<8){$('#errorMessage').textContent='Enter a little more detail (at least 8 characters).';$('#errorMessage').style.display='block';query.focus();return}renderRequirements(s);renderResults(rank(s));$('#resultSub').textContent=source&&!source.demo?`Candidates from ${source.count.toLocaleString()} imported ${source.label} records`:'Candidates from the illustrative demo knowledge base';$('#requirementsPanel').scrollIntoView({behavior:'smooth',block:'nearest'})}
function toast(s){const t=$('#toast');t.textContent=s;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2600)}
$('#analyzeBtn').addEventListener('click',analyze);$('#editQuery').addEventListener('click',()=>query.focus());query.addEventListener('input',()=>$('#charCount').textContent=`${query.value.length.toLocaleString()} / 5,000`);query.addEventListener('input',()=>{if(query.value.length>5000)query.value=query.value.slice(0,5000)});query.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();analyze()}});
$$('.chip').forEach(b=>b.addEventListener('click',()=>{query.value=b.dataset.example;$('#charCount').textContent=`${query.value.length} / 5,000`;analyze()}));
$('#fileInput').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;$('#fileLabel').textContent=f.name;if(f.name.toLowerCase().endsWith('.txt')){query.value=(await f.text()).slice(0,5000);$('#charCount').textContent=`${query.value.length} / 5,000`;toast('Text loaded. Select Analyze to review it.')}else toast('This prototype accepts TXT files. Paste text extracted from PDF/DOCX for now.')});
$('#exportBtn').addEventListener('click',()=>{if(!lastResults.length){toast('Run an analysis before exporting.');return}const rows=[['is_number','title','role','category','edition_year','status','matched_terms','scope','source_url','date_checked'],...lastResults.map(r=>[r.id,r.title,labelFor(r),r.category,r.edition,r.status,(r.hits||[]).join('; '),r.scope,r.source_url||'',r.date_checked||''])];const csv=rows.map(row=>row.map(x=>'"'+String(x??'').replaceAll('"','""')+'"').join(',')).join('\r\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='standardlens-recommendations.csv';a.click();URL.revokeObjectURL(a.href);toast('Recommendations exported as CSV.')});
$('#howBtn').addEventListener('click',()=>$('#infoDialog').showModal());$('#closeDialog').addEventListener('click',()=>$('#infoDialog').close());$('#infoDialog').addEventListener('click',e=>{if(e.target.id==='infoDialog')e.target.close()});$('#libraryNav').addEventListener('click',()=>toast(`${(source?source.count:0).toLocaleString()} catalogue records loaded.`));$('#historyNav').addEventListener('click',()=>toast('Catalogue update history is not available in this MVP.'));$('#viewAll').addEventListener('click',()=>toast('Only relationships recorded in the loaded dataset are shown.'));
$('#dashboardNav').addEventListener('click',()=>window.scrollTo({top:0,behavior:'smooth'}));$('#analyzeNav').addEventListener('click',()=>{document.querySelector('#analyzeSection').scrollIntoView({behavior:'smooth'});query.focus({preventScroll:true})});$('#recommendationsNav').addEventListener('click',()=>$('#resultsPanel').scrollIntoView({behavior:'smooth'}));$('#relationshipsNav').addEventListener('click',()=>$('#relationshipsPanel').scrollIntoView({behavior:'smooth'}));$$('.future-nav').forEach(button=>button.addEventListener('click',()=>toast('This section is not part of the current MVP.')));
/* ---------- data: load the smallest artifact that answers, in this order ---- */
const DATASETS=[
 {url:'data/search_index.json.gz',kind:'index',gzip:true},
 {url:'data/search_index.json',kind:'index'},
 {url:'data/bis_crawl/search_index.json.gz',kind:'index',gzip:true},
 {url:'data/bis_crawl/search_index.json',kind:'index'},
 {url:'data/bis_crawl/standards.json',kind:'records'},
 {url:'data/standards.json',kind:'records'}
];
function setEnv(html){const chip=$('.env');if(chip)chip.innerHTML=html}
function activate(catalog){
 if(!catalog||!catalog.count){renderResults([]);return}
 source=catalog;
 const crawled=catalog.label==='detail crawl';
 const checked=String((catalog.source&&catalog.source.date_checked)||'');
 const total=catalog.count.toLocaleString();
 setEnv(catalog.demo?'<i></i> DEMO DATA':(crawled?'<i></i> CRAWL DB':'<i></i> BIS EXPORT'));
 $('#resultCount').textContent=`${total} records available`;
 const catalogMetric=$('#catalogMetric');if(catalogMetric)catalogMetric.textContent=total;
 $('#resultSub').textContent=catalog.demo?'Based on your procurement requirements':`${total} BIS ${catalog.label} records loaded · verify each source`;
 $('#sourceNote').innerHTML=catalog.demo
   ?'<b>Demo records only.</b> Standard identifiers and metadata below are illustrative placeholders, not official BIS recommendations. Load a reviewed BIS catalogue export to replace these fixtures.'
   :`<b>${total} BIS ${catalog.label} records loaded.</b>${checked?` Data checked ${escapeHtml(checked)}.`:''} Matches are ranked by keyword relevance over the loaded export, not semantic AI. An identified record is only a candidate; verify source fields and applicability with an expert.`;
 const footer=$('#footerStatus');
 if(footer)footer.textContent=catalog.demo?'BIS data not connected':`${total} BIS records · ${catalog.pipeline||'browser index'}`;
 renderResults(rank(query.value));renderRequirements(query.value);
}
async function inflate(buffer){
 if(typeof DecompressionStream!=='function')throw Error('this browser cannot inflate the gzip index');
 return new Response(new Blob([buffer]).stream().pipeThrough(new DecompressionStream('gzip'))).text();
}
async function readMaybeGzip(buffer){
 const bytes=new Uint8Array(buffer);
 // The CDN may already have decoded it, or the file may have been rebuilt with
 // --no-gzip: sniff the magic number instead of trusting the extension.
 const compressed=bytes[0]===0x1f&&bytes[1]===0x8b;
 return compressed?await inflate(buffer):new TextDecoder().decode(buffer);
}
async function firstCatalog(){
 for(const item of DATASETS){
  let response;
  try{response=await fetch(item.url)}catch(error){continue}
  if(!response.ok)continue;
  let payload;
  try{payload=item.gzip?JSON.parse(await readMaybeGzip(await response.arrayBuffer())):await response.json()}catch(error){continue}
  if(!Array.isArray(payload.records)||!payload.records.length)continue;
  const crawled=item.url.includes('bis_crawl');
  return item.kind==='index'
   ?SL.createIndexSearch(payload)
   :SL.createListSearch(payload.records,payload.relationships||[],{label:crawled?'detail crawl':'catalogue',source:{date_checked:(payload.source&&payload.source.date_checked)||''}});
 }
 return null;
}
async function loadData(){
 if(!SL){setEnv('<i></i> CORE MISSING');resultsEl.innerHTML='<div class="empty-state"><b>Search core unavailable</b>search.js failed to load, so records cannot be ranked. Reload the page.</div>';return}
 setEnv('<i></i> LOADING DATA');
 try{activate(await firstCatalog()||fixtureSource())}
 catch(error){activate(fixtureSource());toast('Catalogue data unavailable, showing demo records.')}
}
loadData();
renderRequirements(query.value);renderResults(rank(query.value));$('#charCount').textContent=`${query.value.length} / 5,000`;
