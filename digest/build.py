import argparse
import json
import shutil
from pathlib import Path
from .models import Analysis,Metadata

def build(output='dist'):
    out=Path(output)
    out.mkdir(parents=True,exist_ok=True)
    for name in ('index.html','styles.css','app.mjs','core.mjs','read-state.mjs'):
        shutil.copyfile(Path('web')/name,out/name)
    (out/'data').mkdir(exist_ok=True)
    for name in ('papers.json','reference-papers.json'):
        source=Path('data')/name
        data=json.loads(source.read_text(encoding='utf-8-sig'))
        for p in data['papers']:
            Analysis.model_validate({k:p[k] for k in Analysis.model_fields if k in p})
            meta={k:p[k] for k in Metadata.model_fields if k in p}
            Metadata.model_validate(meta)
            if p['evidence_source'] not in ('abstract','full_text'):
                raise ValueError('Invalid evidence source')
        (out/'data'/name).write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    (out/'.nojekyll').touch()
    print('Validated static site:',out.resolve())

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='dist')
    build(parser.parse_args().output)
