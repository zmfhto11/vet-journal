from pathlib import Path
import json
from digest.sources import HTTP, Journals, EPMC, NCBI, ncbi_params, parse_europe, parse_pubmed
http=HTTP()
j=Journals()
payload=http.json(EPMC+'search',params={'query':j.europe_query()+' AND (dog OR cat OR canine OR feline) AND HAS_ABSTRACT:y sort_date:y','format':'json','resultType':'core','pageSize':8})
Path('artifacts/europe-live.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
parsed=parse_europe(payload,j)
print('Europe PMC actual records:',len(parsed))
ids=[p.pmid for p in parsed if p.pmid]
raw=http.request(NCBI+'efetch.fcgi',params=ncbi_params(db='pubmed',id=','.join(ids),retmode='xml'))
Path('artifacts/pubmed-live.xml').write_bytes(raw)
print('PubMed actual records:',len(parse_pubmed(raw,j)))
for p in parsed[:3]:
    print(p.pmid,p.title)

