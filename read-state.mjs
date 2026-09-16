// Read markers stay on this browser/device; DOI/PMID aliases survive metadata enrichment.
export const READ_STORAGE_KEY='vet-journal:read-papers:v1';
export function paperKeys(paper){
  return [...new Set([paper.id,paper.doi&&`doi:${paper.doi.toLowerCase()}`,paper.pmid&&`pmid:${paper.pmid}`].filter(Boolean))];
}
export function createReadState(getStorage){
  let values=new Set();
  let sessionOnly=false;
  function reload(){
    if(sessionOnly)return;
    try{
      const saved=JSON.parse(getStorage().getItem(READ_STORAGE_KEY)||'[]');
      values=new Set(Array.isArray(saved)?saved.filter(x=>typeof x==='string'):[]);
    }catch{/* Corrupt or unavailable storage must not break the paper list. */}
  }
  reload();
  return {
    reload,
    isRead(paper){return paperKeys(paper).some(key=>values.has(key));},
    toggle(paper){
      reload();
      const keys=paperKeys(paper);
      const read=!keys.some(key=>values.has(key));
      keys.forEach(key=>read?values.add(key):values.delete(key));
      try{getStorage().setItem(READ_STORAGE_KEY,JSON.stringify([...values]));sessionOnly=false;}
      catch{sessionOnly=true;}
      return {read,persisted:!sessionOnly};
    }
  };
}
