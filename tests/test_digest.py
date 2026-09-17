import json
import tempfile
import unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import patch
from pydantic import ValidationError
from digest.models import Analysis,Metadata,Record,normalize_doi
from digest.sources import Journals,parse_pubmed,parse_europe,exact_date,HTTP
from digest.store import Store
from digest.analyze import Analyzer,validate_grounding,strict_schema
from digest.pipeline import process_records

ABSTRACT='This prospective study enrolled 73 client-owned dogs. Improvement occurred in 60 dogs. A control group was not included.'

def meta(**changes):
    return Metadata(title='TPLO outcome study',journal='Veterinary Surgery',journal_id='vetsurg',doi='10.1111/test',pmid='12345',abstract=ABSTRACT,source='pubmed',**changes)

def analysis(**changes):
    values=dict(clinical_relevance='direct',relevance_reason='Clinical dogs',primary_category='surgery',tags=['orthopedics'],species=['dog'],disease_or_topic='TPLO',study_design='prospective',sample_size=73,sample_size_quote='This prospective study enrolled 73 client-owned dogs.',objective='Evaluate outcomes',one_sentence_summary='Improvement occurred in treated dogs.',key_results=[{'result':'Improvement occurred in 60 dogs.','evidence_quote':'Improvement occurred in 60 dogs.'}],authors_conclusion=None,clinical_takeaway='Uncontrolled evidence does not establish comparative efficacy.',limitations=['Uncontrolled','abstract only'],recommended=False,recommendation_reason=None)
    values.update(changes)
    return Analysis(**values)

class FakeAnalyzer:
    max_calls=20
    calls=0
    model='mock'
    def analyze(self,metadata,evidence,evidence_source):
        self.calls+=1
        return analysis(),{'input_tokens':20,'output_tokens':20}

class DigestTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/'state.json')
    def tearDown(self):
        self.tmp.cleanup()
    def test_doi_normalization(self):
        self.assertEqual(normalize_doi('https://doi.org/10.1111/ABC'),'10.1111/abc')
        with self.assertRaises(ValueError): normalize_doi('not-a-doi')
    def test_duplicate_doi(self):
        self.store.upsert(meta())
        self.store.upsert(meta().model_copy(update={'pmid':None,'source':'europe_pmc'}))
        self.assertEqual(len(self.store.state.records),1)
    def test_duplicate_pmid_and_late_doi(self):
        first=self.store.upsert(meta().model_copy(update={'doi':None}))
        second=self.store.upsert(meta())
        self.assertEqual(first.id,second.id)
        self.assertIn('doi:10.1111/test',second.aliases)
    def test_bridge_doi_and_pmid(self):
        self.store.upsert(meta().model_copy(update={'pmid':None}))
        self.store.upsert(meta().model_copy(update={'doi':None}))
        self.assertEqual(len(self.store.state.records),2)
        self.store.upsert(meta())
        self.assertEqual(len(self.store.state.records),1)
    def test_no_identifiers_enrichment(self):
        self.store.upsert(meta().model_copy(update={'doi':None,'pmid':None}))
        self.store.upsert(meta())
        self.assertEqual(len(self.store.state.records),1)
    def test_conflicting_identifiers(self):
        self.store.upsert(meta())
        with self.assertRaises(ValueError):
            self.store.upsert(meta().model_copy(update={'doi':'10.1111/different'}))
    def test_journal_mapping(self):
        j=Journals()
        self.assertEqual(j.match('Vet Surg')['id'],'vetsurg')
        self.assertEqual(j.match('1939-1676')['id'],'jvim')
        self.assertIsNone(j.match('Human Surgery Journal'))
    def test_pubmed_parsing(self):
        xml='<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>12345</PMID><Article><ArticleTitle>Dog <i>TPLO</i> outcomes</ArticleTitle><Journal><Title>Veterinary Surgery</Title><JournalIssue><PubDate><Year>2026</Year><Month>Sep</Month></PubDate></JournalIssue></Journal><ArticleDate DateType="Electronic"><Year>2026</Year><Month>09</Month><Day>09</Day></ArticleDate><Abstract><AbstractText Label="RESULTS">73 dogs.</AbstractText></Abstract></Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.1111/TEST</ArticleId></ArticleIdList></PubmedData></PubmedArticle></PubmedArticleSet>'
        p=parse_pubmed(xml,Journals())[0]
        self.assertEqual(p.doi,'10.1111/test')
        self.assertEqual(p.title,'Dog TPLO outcomes')
        self.assertIsNone(p.publication_date)
        self.assertEqual(str(p.online_publication_date),'2026-09-09')
        self.assertIn('RESULTS',p.abstract)
    def test_europe_parsing(self):
        obj={'resultList':{'result':[{'title':'Dog study','id':'12345','source':'MED','doi':'10.1111/TEST','journalInfo':{'dateOfPublication':'2026 Sep','journal':{'issn':'0161-3499'}},'electronicPublicationDate':'2026-09-09','abstractText':'<p>Results: 73 dogs.</p>'}]}}
        p=parse_europe(obj,Journals())[0]
        self.assertEqual(p.pmid,'12345')
        self.assertIsNone(p.publication_date)
        self.assertEqual(str(p.online_publication_date),'2026-09-09')
        self.assertEqual(p.abstract,'Results: 73 dogs.')
    def test_malformed_sources(self):
        with self.assertRaises(Exception): parse_pubmed('not xml',Journals())
        with self.assertRaises(KeyError): parse_europe({},Journals())
    def test_invalid_schema(self):
        for change in ({'recommended':'true'},{'sample_size':'73'},{'sample_size':True},{'sample_size':-1},{'primary_category':'human'},{'tags':['unknown']}):
            with self.subTest(change=change),self.assertRaises(ValidationError): analysis(**change)
        with self.assertRaises(ValidationError): Metadata.model_validate({**meta().model_dump(),'publication_date':'2026-02-30'})
        with self.assertRaises(ValidationError): Metadata.model_validate({**meta().model_dump(),'pmid':'PMID123'})
    def test_evidence_enum(self):
        r=self.store.upsert(meta())
        with self.assertRaises(ValidationError): Record.model_validate({**r.model_dump(),'evidence_source':'pretend_full_text'})
    def test_recommendation_requires_reason(self):
        with self.assertRaises(ValidationError): analysis(recommended=True)
        self.assertTrue(analysis(recommended=True,recommendation_reason='Useful direct prospective evidence').recommended)
    def test_grounding(self):
        self.assertEqual(validate_grounding(analysis(),ABSTRACT).sample_size,73)
        with self.assertRaises(ValueError): validate_grounding(analysis(sample_size=74),ABSTRACT)
        with self.assertRaises(ValueError): validate_grounding(analysis(one_sentence_summary='99% improved'),ABSTRACT)
        with self.assertRaises(ValueError): validate_grounding(analysis(key_results=[{'result':'60 improved','evidence_quote':'fabricated evidence'}]),ABSTRACT)
    def test_missing_abstract_no_ai_call(self):
        r=self.store.upsert(meta().model_copy(update={'abstract':None}))
        a=FakeAnalyzer()
        with patch('digest.pipeline.refresh_metadata',return_value=None): process_records(self.store,a,None,Journals())
        self.assertEqual(r.status,'failed')
        self.assertEqual(r.last_error,'missing_abstract')
        self.assertEqual(a.calls,0)
    def test_failed_retry_and_processed_skip(self):
        r=self.store.upsert(meta())
        r.status='failed'
        r.last_attempt_at=datetime.now(timezone.utc)-timedelta(days=2)
        a=FakeAnalyzer()
        process_records(self.store,a,None,Journals())
        self.assertEqual(r.status,'processed')
        process_records(self.store,a,None,Journals())
        self.assertEqual(a.calls,1)
        self.store.save()
        self.assertEqual(Store(self.store.path).state.records[0].status,'processed')
    def test_failure_isolated(self):
        self.store.upsert(meta())
        self.store.upsert(meta().model_copy(update={'doi':'10.1111/other','pmid':'456','title':'Other'}))
        a=FakeAnalyzer()
        a.analyze=lambda *args: (_ for _ in ()).throw(TimeoutError())
        counts=process_records(self.store,a,None,Journals())
        self.assertEqual(counts['failed'],2)
    def test_excluded_not_exported(self):
        r=self.store.upsert(meta())
        r.status='processed'; r.analysis=analysis(clinical_relevance='exclude',species=[])
        r.evidence_source='abstract'; r.summary_generated_at=datetime.now(timezone.utc)
        dest=Path(self.tmp.name)/'papers.json'; self.store.export(dest)
        self.assertEqual(json.loads(dest.read_text())['papers'],[])
    def test_schema_all_fields_required(self):
        schema=strict_schema()
        self.assertEqual(set(schema['required']),set(schema['properties']))
        self.assertFalse(schema['additionalProperties'])
    def test_corrupt_state_not_overwritten(self):
        self.store.path.write_text('broken')
        with self.assertRaises(ValueError): Store(self.store.path)
        self.assertEqual(self.store.path.read_text(),'broken')
    def test_mock_responses_and_category_contracts(self):
        # Contract tests, NOT evidence of real model accuracy. tests.live_ai does that separately.
        cases=[('TPLO outcome study','surgery',['orthopedics']),('canine chronic enteropathy treatment','internal_medicine',['gastroenterology']),('mast cell tumor surgical margin','surgery',['oncology']),('lymphoma chemotherapy outcome','internal_medicine',['oncology']),('splenic hemangiosarcoma surgery and adjuvant chemotherapy','surgery',['oncology'])]
        for title,category,tags in cases:
            expected=analysis(primary_category=category,tags=tags)
            class FakeHTTP:
                def json(self,url,**kwargs):
                    body=json.loads(kwargs['body'])
                    self.assertion=body['text']['format']['strict']
                    return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':expected.model_dump_json()}]}],'usage':{}}
            with patch.dict('os.environ',{'OPENAI_API_KEY':'test-only'}):
                got,_=Analyzer(FakeHTTP()).analyze(meta().model_copy(update={'title':title}),ABSTRACT,'abstract')
            self.assertEqual(got.primary_category,category)
            self.assertEqual(got.tags,tags)
    def test_fulltext_failure_falls_back(self):
        r=self.store.upsert(meta().model_copy(update={'pmcid':'PMC123'}))
        with patch.dict('os.environ',{'USE_FULL_TEXT':'true'}),patch('digest.pipeline.full_text',side_effect=TimeoutError()):
            process_records(self.store,FakeAnalyzer(),None,Journals())
        self.assertEqual(r.evidence_source,'abstract')

if __name__=='__main__': unittest.main()
