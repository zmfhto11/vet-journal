import json
import os
from pathlib import Path
path=Path('data/last_run.json')
if path.exists():
    health=json.loads(path.read_text(encoding='utf-8-sig'))
    report='## Veterinary digest run\n\n```json\n'+json.dumps(health,indent=2)+'\n```\n'
else:
    report='## Veterinary digest run\n\nNo run report was produced. Inspect the failed step.\n'
if os.getenv('GITHUB_STEP_SUMMARY'):
    with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f: f.write(report)
else:
    print(report)
