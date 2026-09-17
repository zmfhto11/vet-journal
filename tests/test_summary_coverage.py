"""Regression checks for the missing principal findings reported by the user.
These protect curated references; they do not certify a live model's semantics.
"""
import json
import unittest
from pathlib import Path
from digest.analyze import validate_grounding
from tests.test_digest import analysis,ABSTRACT

class SummaryCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.papers={p['doi']:p for p in json.loads(Path('data/reference-papers.json').read_text(encoding='utf-8'))['papers']}
    def test_pyometra_covers_prognosis_antibiotic_comparison_and_susceptibility(self):
        paper=self.papers['10.2460/javma.26.05.0367']
        findings=' '.join(f['result'] for f in paper['key_results'])
        for topic in ['패혈증','크레아티닌','입원 기간','비패혈증','수술 전 또는 중','퇴원 생존','337','116','34.4%','102/116','87.9%']:
            self.assertIn(topic,findings)
        self.assertIn('전체 환자',findings) # Do not mislabel the inappropriate-prescription denominator.
        self.assertNotIn('중단을 결정해서는 안',paper['clinical_takeaway'])
    def test_other_references_contain_their_principal_outcomes(self):
        topics={
            '10.1111/vsu.70157':['완전','부분','12.5%','20.8%','쇼크'],
            '10.1111/jsap.70195':['반응','70%','90일'],
            '10.1111/vsu.70154':['좌골결절','변위','보행'],
            '10.2460/javma.26.06.0508':['종양이 확인되지','66','12','비종양성'],
            '10.1111/vco.70111':['NOD2','Cluster 1','연령','위치'],
            '10.2460/javma.26.03.0235':['더 오래','비감수성','1마리']}
        for doi,terms in topics.items():
            results=' '.join(f['result'] for f in self.papers[doi]['key_results'])
            for term in terms:
                with self.subTest(doi=doi,term=term):self.assertIn(term,results)
    def test_sample_generation_status_is_not_a_study_limitation(self):
        for paper in self.papers.values():
            self.assertFalse(any('초기 검증용' in x for x in paper['limitations']))
    def test_diet_overview_preserves_enrollment_attrition_response_and_followup(self):
        paper=self.papers['10.1111/jsap.70195']
        for fact in ['27마리','7마리','20마리','14마리(70%)','6.25','90일','비대조']:
            self.assertIn(fact,paper['one_sentence_summary'])
        for method in ['14일','30일','90일','CIBDAI','무반응']:
            # Methods explain nonresponders in normal Korean prose.
            if method=='무반응':self.assertIn('반응하지 않은',paper['study_methods'])
            else:self.assertIn(method,paper['study_methods'])
        self.assertGreaterEqual(len(paper['key_results']),5)

    def test_methods_backwards_compatible_but_numeric_claims_require_source(self):
        original=analysis().model_dump()
        original.pop('study_methods')
        from digest.models import Analysis
        self.assertIsNone(Analysis.model_validate(original).study_methods)
        with self.assertRaisesRegex(ValueError,'Unsupported number'):
            validate_grounding(analysis(study_methods='Followed for 999 days.'),ABSTRACT)

    def test_explicit_word_count_can_be_translated_but_group_total_cannot_be_invented(self):
        valid=analysis(sample_size=None,sample_size_quote=None,
            one_sentence_summary='14 dogs responded.',clinical_takeaway='Uncontrolled evidence.',
            key_results=[{'result':'14 dogs responded.','evidence_quote':'Fourteen dogs responded.'}])
        validate_grounding(valid,'Fourteen dogs responded.')
        invalid=analysis(sample_size=None,sample_size_quote=None,
            one_sentence_summary='19 animals were included.',clinical_takeaway='Uncontrolled evidence.',
            key_results=[{'result':'19 animals were included.','evidence_quote':'9 cats received A and 10 cats received B.'}])
        with self.assertRaisesRegex(ValueError,'Unsupported numeric finding'):
            validate_grounding(invalid,'9 cats received A and 10 cats received B.')

    def test_summary_cannot_use_a_source_number_omitted_from_displayed_results(self):
        with self.assertRaisesRegex(ValueError,'missing from displayed findings'):
            validate_grounding(analysis(one_sentence_summary='Follow-up lasted 90 days.'),ABSTRACT+' Follow-up lasted 90 days.')

if __name__=='__main__':unittest.main()
