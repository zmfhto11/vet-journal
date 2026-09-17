"""Live metadata-to-storage regression. No paid API call."""
import json
import tempfile
from pathlib import Path
from digest.sources import Journals,parse_pubmed,parse_europe
from digest.store import Store

def main():
    j=Journals()
    a=Path('artifacts/europe-live.json'); b=Path('artifacts/pubmed-live.xml')
    if not a.exists() or not b.exists():
        raise SystemExit('Run python -m tests.live_sources first.')
    european=parse_europe(json.loads(a.read_text(encoding='utf-8')),j)
    pubmed=parse_pubmed(b.read_bytes(),j)
    with tempfile.TemporaryDirectory() as d:
        store=Store(Path(d)/'state.json')
        for p in european+pubmed: store.upsert(p)
        store.save()
        restored=Store(store.path)
        assert len(restored.state.records)==len(european)>0
        assert all(r.status=='pending' for r in restored.state.records)
        restored.export(Path(d)/'papers.json')
        assert json.loads((Path(d)/'papers.json').read_text(encoding='utf-8'))['papers']==[]
        print(f'PASS: {len(european)+len(pubmed)} real source records -> {len(restored.state.records)} unique pending papers; no unreviewed output leaked.')
if __name__=='__main__': main()
