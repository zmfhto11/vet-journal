import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {matches,todayPicks,kstDate,sorted,escapeHTML,safeURL} from '../web/core.mjs';
const {papers}=JSON.parse(readFileSync(new URL('../data/reference-papers.json',import.meta.url),'utf8').replace(/^\uFEFF/,''));
test('KST date crosses UTC midnight correctly',()=>{assert.equal(kstDate('2026-09-15T23:17:00Z'),'2026-09-16');assert.equal(kstDate('2026-09-15T14:59:00Z'),'2026-09-15');});
test('Picks max three, same KST discovery date, no recycled picks',()=>{const today=kstDate(papers[0].discovered_at);assert.equal(todayPicks(papers,today).length,3);assert.equal(todayPicks(papers,'2000-01-01').length,0);assert.equal(todayPicks(papers.slice(0,1),today).length,1);});
test('Multiple category tags include surgery/oncology overlap',()=>{const p=papers.find(p=>p.tags.includes('surgery')&&p.primary_category==='oncology');assert.ok(matches(p,{category:'surgery'}));assert.ok(matches(p,{category:'oncology'}));});
test('Search title, journal, disease, tag, clinical takeaway and results',()=>{const p=papers[0];for(const search of [p.title.split(' ')[0],p.journal,p.disease_or_topic.split(' · ')[0],p.tags[0],p.clinical_takeaway.split(' ')[0],p.key_results[0].result.split(' ')[0]])assert.ok(matches(p,{search}));assert.ok(!matches(p,{search:'impossible-query'}));});
test('Filters combine, multiple species are OR',()=>{const p=papers.find(p=>p.species.includes('cat'));assert.ok(matches(p,{species:['dog','cat'],evidence:['abstract']}));assert.ok(!matches(p,{species:['dog']}));assert.ok(!matches(p,{evidence:['full_text']}));assert.ok(!matches(p,{journal:'not-a-journal'}));assert.ok(matches(p,{design:p.study_design,journal:p.journal_id}));});
test('Recommended filter honors explicit boolean',()=>{assert.equal(papers.filter(p=>matches(p,{category:'recommended'})).length,3);});
test('Untrusted strings escaped and script URLs rejected',()=>{assert.equal(escapeHTML('<script>'), '&lt;script&gt;');assert.equal(safeURL('javascript:alert(1)'),'');assert.equal(safeURL('https://pubmed.ncbi.nlm.nih.gov/123/'),'https://pubmed.ncbi.nlm.nih.gov/123/');});
test('Sort uses online publication before print date',()=>{const list=sorted([{...papers[0],id:'a',online_publication_date:'2026-08-01',publication_date:'2027-01-01'},{...papers[0],id:'b',online_publication_date:'2026-09-01'}]);assert.equal(list[0].id,'b');});

import {createReadState,READ_STORAGE_KEY} from '../web/read-state.mjs';
function memoryStorage(){const values=new Map();return {getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};}
test('Read marker survives reload and can be undone without affecting another paper',()=>{
  const storage=memoryStorage();let state=createReadState(()=>storage);
  assert.equal(state.isRead(papers[0]),false);
  assert.deepEqual(state.toggle(papers[0]),{read:true,persisted:true});
  state=createReadState(()=>storage);
  assert.equal(state.isRead(papers[0]),true);
  assert.equal(state.isRead(papers[1]),false);
  assert.equal(state.toggle(papers[0]).read,false);
  assert.equal(createReadState(()=>storage).isRead(papers[0]),false);
});
test('Read marker follows PMID when DOI or internal identifier becomes available',()=>{
  const storage=memoryStorage();const state=createReadState(()=>storage);
  state.toggle({id:'pmid:123',pmid:'123'});
  const enriched={id:'doi:10.1111/test',pmid:'123',doi:'10.1111/test'};
  assert.equal(createReadState(()=>storage).isRead(enriched),true);
  state.toggle(enriched);
  assert.equal(createReadState(()=>storage).isRead(enriched),false);
});
test('Blocked storage keeps session read state and reports non-persistence',()=>{
  const state=createReadState(()=>{throw new Error('Storage blocked');});
  assert.deepEqual(state.toggle(papers[0]),{read:true,persisted:false});
  assert.equal(state.isRead(papers[0]),true);
  assert.deepEqual(state.toggle(papers[0]),{read:false,persisted:false});
});
test('Invalid stored JSON is recoverable and separate tabs merge the latest markers',()=>{
  const storage=memoryStorage();storage.setItem(READ_STORAGE_KEY,'{invalid');
  const first=createReadState(()=>storage),second=createReadState(()=>storage);
  assert.equal(first.isRead(papers[0]),false);
  first.toggle(papers[0]);second.toggle(papers[1]);first.reload();
  assert.equal(first.isRead(papers[0]),true);assert.equal(first.isRead(papers[1]),true);
});
