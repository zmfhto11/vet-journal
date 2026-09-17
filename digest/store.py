from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path
from datetime import datetime, timezone
from .models import Metadata, Record, State, utcnow

log = logging.getLogger(__name__)

def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temp = path.with_name(path.name+'.tmp')
    with temp.open('w',encoding='utf-8',newline='\n') as f:
        json.dump(payload,f,ensure_ascii=False,indent=2)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(temp,path)

def identifiers(m):
    return [key for key in [f'doi:{m.doi}' if m.doi else None, f'pmid:{m.pmid}' if m.pmid else None] if key]

def fallback(m):
    title = re.sub(r'[^\w]','',m.title.casefold())
    return 'title:'+hashlib.sha256((m.journal_id+'|'+title).encode()).hexdigest()[:24]

def merge_metadata(old,new):
    # Prefer PubMed metadata but keep richer abstracts and separate online/print dates.
    values = old.model_dump()
    for key,value in new.model_dump().items():
        if value is not None and (not values.get(key) or (new.source=='pubmed' and key not in ('abstract',))):
            values[key] = value
    if len(new.abstract or '') > len(old.abstract or ''):
        values['abstract'] = new.abstract
    return Metadata.model_validate(values)

class Store:
    def __init__(self,path='data/state.json'):
        self.path=Path(path)
        self.state=State.model_validate_json(self.path.read_text(encoding='utf-8-sig')) if self.path.exists() else State()
        self.reindex()

    def reindex(self):
        self.aliases={alias:r for r in self.state.records for alias in r.aliases}

    def save(self):
        # Revalidate state before atomic persistence, including mutated records.
        checked=State.model_validate(self.state.model_dump())
        atomic_json(self.path,checked.model_dump(mode='json'))

    def upsert(self,m):
        keys=identifiers(m)
        matches=[]
        for key in keys:
            hit=self.aliases.get(key)
            if hit is not None and all(hit.id!=r.id for r in matches):
                matches.append(hit)
        if not matches:
            for r in self.state.records:
                if fallback(r.metadata)==fallback(m) and (not identifiers(r.metadata) or not keys):
                    matches.append(r)
                    break
        now=datetime.now(timezone.utc)
        if not matches:
            record=Record(id=keys[0] if keys else fallback(m),metadata=m,aliases=keys or [fallback(m)],discovered_at=now,updated_at=now)
            self.state.records.append(record)
        else:
            # A new source can bridge previously separate DOI-only and PMID-only entries.
            dois={r.metadata.doi for r in matches if r.metadata.doi} | ({m.doi} if m.doi else set())
            pmids={r.metadata.pmid for r in matches if r.metadata.pmid} | ({m.pmid} if m.pmid else set())
            if len(dois)>1 or len(pmids)>1:
                raise ValueError('Conflicting identifiers; manual review required')
            matches.sort(key=lambda r:(r.status!='processed',r.discovered_at))
            record=matches[0]
            for duplicate in matches[1:]:
                record.metadata=merge_metadata(record.metadata,duplicate.metadata)
                record.aliases=list(set(record.aliases+duplicate.aliases))
                record.discovered_at=min(record.discovered_at,duplicate.discovered_at)
                self.state.records.remove(duplicate)
            record.metadata=merge_metadata(record.metadata,m)
            record.updated_at=now
            record.aliases=sorted(set(record.aliases+keys+identifiers(record.metadata)))
        self.reindex()
        return record

    def export(self,path='data/papers.json',health=None):
        papers=[]
        for r in self.state.records:
            if r.status!='processed' or r.analysis is None or r.analysis.clinical_relevance=='exclude':
                continue
            meta=r.metadata.model_dump(mode='json',exclude={'abstract','source_id'})
            papers.append({**meta,**r.analysis.model_dump(mode='json'),'id':r.id,'discovered_at':str(r.discovered_at),'evidence_source':r.evidence_source,'evidence_url':r.evidence_url,'summary_generated_at':str(r.summary_generated_at),'analysis_model':r.model})
        papers.sort(key=lambda p:(p['online_publication_date'] or p['publication_date'] or '',p['discovered_at']),reverse=True)
        atomic_json(path,{'version':1,'generated_at':utcnow(),'last_successful_collection':self.state.model_dump(mode='json')['last_successful_collection'],'mode':'live','papers':papers,'health':health or {}})
