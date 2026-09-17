import json
from pathlib import Path
from digest.sources import HTTP,EPMC,full_text
from digest.store import atomic_json
papers=json.loads(Path('data/reference-papers.json').read_text(encoding='utf-8'))['papers']
http=HTTP();result=[]
for p in papers:
    payload=http.json(EPMC+'search',params={'query':'DOI:"'+p['doi']+'"','format':'json','resultType':'core'})
    entries=payload.get('resultList',{}).get('result',[])
    hits=[x for x in entries if x.get('doi','').lower()==p['doi'].lower()]
    x=hits[0] if hits else {}
    row={'doi':p['doi'],'pmcid':x.get('pmcid'),'isOpenAccess':x.get('isOpenAccess'),'fullTextUrlList':x.get('fullTextUrlList',{})}
    result.append(row)
    print(json.dumps(row,ensure_ascii=False))
atomic_json('artifacts/fulltext-availability.json',result)
payload=http.json(EPMC+'search',params={'query':'EXT_ID:PMC13549437 OR PMCID:PMC13549437','format':'json','resultType':'core'})
atomic_json('artifacts/renal-fulltext-metadata.json',payload)
body=full_text(http,'PMC13549437')
Path('artifacts/renal-fulltext.txt').write_text(body or '',encoding='utf-8')
print('Renal full text characters:',len(body or ''))
