import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from digest.sources import HTTP, APIRequestError, Journals, parse_europe
from digest.pipeline import process_records, publication_order
from digest.store import Store
from tests.test_digest import meta, FakeAnalyzer


class DiagnosticsTests(unittest.TestCase):
    def test_error_never_exposes_response_or_key(self):
        for code, expected in [('insufficient_quota','insufficient_quota'), ('secret-key-value','unknown')]:
            body=json.dumps({'error':{'code':code,'message':'secret-key-value'}}).encode()
            failure=urllib.error.HTTPError('https://api.openai.com/v1/responses',429,'private message',{},io.BytesIO(body))
            with patch('urllib.request.urlopen',side_effect=failure), self.assertRaises(APIRequestError) as caught:
                HTTP().request('https://api.openai.com/v1/responses',attempts=3)
            self.assertEqual(str(caught.exception),'openai_http_429_'+expected)
            self.assertNotIn('secret-key-value',str(caught.exception))

    def test_api_failure_stops_batch_and_checkpoints(self):
        with tempfile.TemporaryDirectory() as d, patch.dict('os.environ',{'USE_FULL_TEXT':'false'}):
            store=Store(Path(d)/'state.json')
            store.upsert(meta())
            store.upsert(meta().model_copy(update={'doi':'10.1111/next','pmid':'456','title':'Next'}))
            analyzer=FakeAnalyzer()
            with patch.object(analyzer,'analyze',side_effect=APIRequestError(401,'invalid_api_key')) as call:
                counts=process_records(store,analyzer,None,Journals())
            self.assertEqual(call.call_count,1)
            self.assertEqual(counts['deferred'],1)
            self.assertEqual(counts['api_error'],'openai_http_401_invalid_api_key')
            self.assertEqual(Store(store.path).state.ai_budget_used,1)

    def test_conflicting_issn_cannot_override_journal_title(self):
        payload={'resultList':{'result':[{'title':'Human correction','id':'42360590','source':'MED',
            'journalInfo':{'journal':{'title':'Dermatology and therapy','essn':'1476-5829'}}}]}}
        self.assertEqual(parse_europe(payload,Journals()),[])
        self.assertEqual(Journals().match_source(['Vet Comp Oncol'],['1476-5829'])['id'],'vco')

    def test_legacy_wrong_journal_never_reaches_ai(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'state.json')
            record=store.upsert(meta().model_copy(update={'source':'europe_pmc'}))
            analyzer=FakeAnalyzer()
            with patch('digest.pipeline.refresh_metadata',return_value=None):
                process_records(store,analyzer,None,Journals())
            self.assertEqual(analyzer.calls,0)
            self.assertEqual(record.last_error,'journal_unverified')

    def test_old_partial_date_is_not_ranked_as_new(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'state.json')
            record=store.upsert(meta(publication_date_raw='2010-Sep'))
            self.assertEqual(publication_order(record),'2010-09-00')
            self.assertIsNone(record.metadata.publication_date)


if __name__=='__main__':
    unittest.main()
