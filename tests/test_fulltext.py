import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from digest.sources import extract_full_text,resolve_pmcid,Journals
from digest.models import Analysis
from digest.analyze import validate_grounding
from digest.pipeline import process_records
from digest.store import Store
from tests.test_digest import meta,FakeAnalyzer

class FullTextTests(unittest.TestCase):
    def test_inequalities_inline_text_tables_and_appendix_survive(self):
        xml=b'<article><body><sec><title>Methods</title><p>Exclude age &lt;7 years; creatinine &gt;1.4.</p></sec><sec><title>Results</title><p>P &lt; .05; <italic>important</italic> result.</p><table-wrap><table><tr><td>15</td><td>21</td><td>7</td></tr></table></table-wrap></sec></body><back><app-group><app><p>Operator not blinded.</p></app></app-group></back></article>'
        result=extract_full_text(xml)
        for value in ['age <7 years; creatinine >1.4.','Results','P < .05; important result.','| 15 |','| 21 |','| 7 |','Operator not blinded.']:
            self.assertIn(value,result)
        self.assertNotIn('15217',result)

    def test_missing_or_empty_body_is_not_fulltext(self):
        for raw in [b'<article><front><abstract>Abstract only</abstract></front></article>',b'<article><body/></article>',b'<error><body>Not available</body></error>']:
            self.assertIsNone(extract_full_text(raw))

    def test_lookup_rejects_unrelated_article_and_resolves_exact_identifier(self):
        class HTTP:
            def json(self,*args,**kwargs):
                return {'resultList':{'result':[{'doi':'10.1111/wrong','pmcid':'PMC999'},{'doi':meta().doi,'pmcid':'PMC123'}]}}
        self.assertEqual(resolve_pmcid(HTTP(),meta()),'PMC123')
        self.assertIsNone(resolve_pmcid(HTTP(),meta().model_copy(update={'doi':'10.1111/missing','pmid':None})))

    def test_default_resolves_pmcid_and_passes_entire_body_to_analyzer(self):
        body='Methods of a complete study. '+('Detailed results. '*5000)+' Final limitations.'
        class Capture(FakeAnalyzer):
            def analyze(inner,m,evidence,kind):
                self.assertEqual(kind,'full_text')
                self.assertTrue(evidence.endswith(' Final limitations.'))
                return super().analyze(m,evidence,kind)
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{},clear=True),patch('digest.pipeline.resolve_pmcid',return_value='PMC123'),patch('digest.pipeline.full_text',return_value=body):
            store=Store(Path(d)/'state.json');record=store.upsert(meta())
            process_records(store,Capture(),None,Journals())
            self.assertEqual(record.status,'processed')
            self.assertEqual(record.metadata.pmcid,'PMC123')
            self.assertEqual(record.evidence_source,'full_text')

    def test_fulltext_reference_quotes_and_figures_are_grounded(self):
        papers=json.loads(Path('data/reference-papers.json').read_text(encoding='utf-8'))['papers']
        p=next(p for p in papers if p['pmcid']=='PMC13549437')
        evidence=Path('tests/fixtures/renal-fulltext.txt').read_text(encoding='utf-8')
        validate_grounding(Analysis.model_validate({k:p[k] for k in Analysis.model_fields}),evidence)
        self.assertEqual(p['evidence_source'],'full_text')
        self.assertIn('임상 상태를 알고', ' '.join(p['limitations']))
        self.assertIn('>1.4',p['study_methods'])

    def test_fulltext_can_be_used_when_abstract_refresh_fails(self):
        with tempfile.TemporaryDirectory() as d,patch.dict('os.environ',{'USE_FULL_TEXT':'true'}),patch('digest.pipeline.refresh_metadata',side_effect=TimeoutError()),patch('digest.pipeline.full_text',return_value='Complete article evidence. '*20):
            store=Store(Path(d)/'state.json')
            record=store.upsert(meta().model_copy(update={'abstract':None,'pmcid':'PMC123'}))
            process_records(store,FakeAnalyzer(),None,Journals())
            self.assertEqual(record.status,'processed')
            self.assertEqual(record.evidence_source,'full_text')

if __name__=='__main__':unittest.main()
