"""Opt-in paid semantic model evaluation; synthetic cases never enter production data."""
import json
import os
from pathlib import Path
from digest.models import Metadata
from digest.sources import HTTP
from digest.analyze import Analyzer

CASES=[
('TPLO outcome study','A retrospective clinical study evaluated client-owned dogs undergoing tibial plateau leveling osteotomy for cranial cruciate ligament rupture. The objectives were postoperative limb function and surgical complications. Records and follow-up examinations were assessed. Most dogs returned to functional ambulation. This is a clinical surgical study; there was no comparison group.','surgery',['orthopedics']),
('canine chronic enteropathy treatment','A prospective clinical trial enrolled client-owned dogs with chronic enteropathy. Dogs received a dietary intervention as sole treatment. Gastrointestinal clinical signs improved during follow-up in some dogs. No surgery was performed. The uncontrolled study cannot establish superiority over alternative diets.','internal_medicine',['gastroenterology']),
('mast cell tumor surgical margin','A retrospective cohort of client-owned dogs with cutaneous mast cell tumours assessed surgical margin width and local recurrence after tumour excision. Histopathology and clinical follow-up were reviewed. Local recurrence varied with margin status. Surgical planning was the primary research question.','surgery',['oncology']),
('lymphoma chemotherapy outcome','A prospective study of client-owned dogs with multicentric lymphoma evaluated a multi-agent chemotherapy protocol. Remission and treatment-associated adverse events were assessed. The objective was medical cancer treatment. There was no surgical intervention and no randomized comparison.','internal_medicine',['oncology']),
('splenic hemangiosarcoma surgery and adjuvant chemotherapy','Client-owned dogs with splenic hemangiosarcoma underwent splenectomy, followed by adjuvant chemotherapy. This retrospective study focused on perioperative outcomes and operative decision-making. Records described complications and postoperative survival. Confounding by chemotherapy and stage limits causal interpretation.','surgery',['oncology'])
]
def main():
    if not os.getenv('OPENAI_API_KEY'):
        raise SystemExit('OPENAI_API_KEY required. This optional evaluation makes paid calls.')
    analyzer=Analyzer(HTTP(),max_calls=len(CASES)+3)
    for title,abstract,category,tags in CASES:
        m=Metadata(title=title,journal='Synthetic evaluation only',journal_id='eval',abstract=abstract,source='synthetic_eval')
        a,_=analyzer.analyze(m,abstract,'abstract')
        assert a.primary_category==category,(title,a.primary_category)
        assert all(t in a.tags for t in tags),(title,a.tags)
        print('PASS synthetic:',title)
    real=json.loads(Path('tests/fixtures/real-papers.json').read_text(encoding='utf-8'))
    for index in [0,2,7]:
        m=Metadata.model_validate(real[index]); a,_=analyzer.analyze(m,m.abstract,'abstract')
        if index==0: assert a.clinical_relevance=='exclude','Cell-line-only paper must be excluded'
        if index==2: assert a.primary_category=='surgery'
        if index==7: assert 'oncology' in a.tags or a.primary_category=='oncology'
        print('PASS actual paper:',m.pmid)
if __name__=='__main__': main()
