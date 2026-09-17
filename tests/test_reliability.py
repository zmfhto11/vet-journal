import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from digest.models import Metadata,Analysis
from digest.sources import Journals,HTTP,full_text
from digest.store import Store
from digest.pipeline import process_records,run
from digest.analyze import Analyzer,validate_grounding
from tests.test_digest import meta,analysis,FakeAnalyzer

class ReliabilityTests(unittest.TestCase):
    def test_daily_budget_survives_new_process(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'state.json');s.upsert(meta())
            a=FakeAnalyzer();a.max_calls=1
            process_records(s,a,None,Journals())
            self.assertEqual(s.state.ai_budget_used,1)
            fresh=Store(s.path)
            pending=fresh.upsert(meta().model_copy(update={'doi':'10.1111/new','pmid':'777','title':'New dog paper'}))
            a=FakeAnalyzer();a.max_calls=1
            counts=process_records(fresh,a,None,Journals())
            self.assertEqual(pending.status,'pending')
            self.assertEqual(counts['deferred'],1)
    def test_same_day_failure_not_retried(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'state.json');r=s.upsert(meta());r.status='failed';r.last_attempt_at=datetime.now(timezone.utc)
            a=FakeAnalyzer();process_records(s,a,None,Journals())
            self.assertEqual(a.calls,0)
    def test_fulltext_label_only_when_complete_body_supplied(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'state.json');r=s.upsert(meta().model_copy(update={'pmcid':'PMC123'}))
            with patch.dict('os.environ',{'USE_FULL_TEXT':'true'}),patch('digest.pipeline.full_text',return_value='Full article methods and results. '*10):
                process_records(s,FakeAnalyzer(),None,Journals())
            self.assertEqual(r.evidence_source,'full_text')
            self.assertTrue(r.evidence_sha256)
    def test_oversized_fulltext_fallback(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'state.json');r=s.upsert(meta().model_copy(update={'pmcid':'PMC123'}))
            with patch.dict('os.environ',{'USE_FULL_TEXT':'true','MAX_INPUT_CHARS':'500'}),patch('digest.pipeline.full_text',return_value='x'*501):
                process_records(s,FakeAnalyzer(),None,Journals())
            self.assertEqual(r.evidence_source,'abstract')
    def test_english_count_is_not_treated_as_missing(self):
        a=analysis(sample_size=27,sample_size_quote='Twenty-seven client-owned dogs were enrolled.',key_results=[],one_sentence_summary='Dogs were enrolled.')
        validate_grounding(a,'Twenty-seven client-owned dogs were enrolled.')
    def test_invalid_ai_response(self):
        for result in [{'status':'incomplete'},{'status':'completed','output':[]},{'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'not json'}]}]}]:
            class FakeHTTP:
                def json(self,*args,**kwargs): return result
            with patch.dict('os.environ',{'OPENAI_API_KEY':'test-only'}),self.assertRaises(ValueError):
                Analyzer(FakeHTTP()).analyze(meta(),meta().abstract,'abstract')
    def test_failure_keeps_other_source_and_prior_state(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('digest.pipeline.collect_pubmed',side_effect=TimeoutError()),patch('digest.pipeline.collect_europe',return_value=iter([meta()])):
                health=run(d,collect_only=True,days=1)
            self.assertEqual(health['status'],'partial')
            self.assertEqual(len(Store(Path(d)/'state.json').state.records),1)
            with patch('digest.pipeline.collect_pubmed',side_effect=TimeoutError()),patch('digest.pipeline.collect_europe',side_effect=ValueError()):
                health=run(d,collect_only=True,days=1)
            self.assertEqual(health['status'],'failed')
            self.assertEqual(len(Store(Path(d)/'state.json').state.records),1)
    def test_refresh_bridge_never_reanalyzes_processed_paper(self):
        with tempfile.TemporaryDirectory() as d:
            s=Store(Path(d)/'state.json')
            done=s.upsert(meta().model_copy(update={'pmid':None,'title':'Published title'}))
            done.status='processed';done.analysis=analysis();done.evidence_source='abstract';done.summary_generated_at=datetime.now(timezone.utc)
            pending=s.upsert(meta().model_copy(update={'doi':None,'title':'Early title','abstract':None}))
            pending.status='failed'
            a=FakeAnalyzer()
            with patch('digest.pipeline.refresh_metadata',return_value=meta()):
                process_records(s,a,None,Journals())
            self.assertEqual(a.calls,0)
            self.assertEqual(len(s.state.records),1)
            self.assertEqual(s.state.records[0].status,'processed')

    def test_actual_reference_fixture_through_processing(self):
        values=json.loads(Path('tests/fixtures/real-papers.json').read_text(encoding='utf-8'))
        references=json.loads(Path('data/reference-papers.json').read_text(encoding='utf-8-sig'))['papers']
        bydoi={p['doi']:p for p in references}
        class ReferenceAnalyzer(FakeAnalyzer):
            def analyze(self,m,evidence,kind):
                self.calls+=1
                a=Analysis.model_validate({k:bydoi[m.doi][k] for k in Analysis.model_fields})
                return validate_grounding(a,evidence),{}
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'state.json')
            for v in values:
                if v['doi'] in bydoi: store.upsert(Metadata.model_validate(v))
            counts=process_records(store,ReferenceAnalyzer(),None,Journals())
            self.assertEqual(counts['processed'],7)
            store.export(Path(d)/'papers.json')
            output=json.loads((Path(d)/'papers.json').read_text(encoding='utf-8'))
            self.assertEqual(len(output['papers']),7)
            self.assertNotIn('abstract',output['papers'][0])
            self.assertEqual(len(Store(store.path).state.records),7)

if __name__=='__main__': unittest.main()
