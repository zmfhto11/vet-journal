from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from .analyze import Analyzer, BudgetExceeded
from .models import utcnow
from .sources import HTTP,APIRequestError,Journals,collect_pubmed,collect_europe,collect_feed,refresh_metadata,full_text,resolve_pmcid
from .store import Store,atomic_json

log=logging.getLogger(__name__)
KST=ZoneInfo('Asia/Seoul')

def publication_order(record):
    m=record.metadata
    known=m.online_publication_date or m.publication_date
    if known:
        return known.isoformat()
    raw=m.publication_date_raw or ''
    year=re.match(r'^(\d{4})',raw)
    # This is only a queue key; never manufacture an exact publication date.
    if year:
        month=re.search(r'^\d{4}[- ](\d{1,2}|[A-Za-z]{3})',raw)
        part=month.group(1) if month else ''
        if part.isdigit():
            number=int(part)
        else:
            names=['jan','feb','mar','apr','may','jun','jul','aug','sep','oct','nov','dec']
            number=names.index(part.lower())+1 if part.lower() in names else 0
        return f'{year.group(1)}-{number:02d}-00'
    return '0000-00-00'

def process_records(store,analyzer,http,journals,collect_only=False):
    counts={'processed':0,'failed':0,'deferred':0}
    if collect_only:
        return counts
    today=datetime.now(KST).date()
    if store.state.ai_budget_date != today:
        store.state.ai_budget_date=today
        store.state.ai_budget_used=0
    analyzer.calls=store.state.ai_budget_used
    # Reserve alternating retry opportunities; recent new papers should not wait behind a backfill.
    pending=sorted([r for r in store.state.records if r.status=='pending'],key=publication_order,reverse=True)
    failed=sorted([r for r in store.state.records if r.status=='failed'],key=lambda r:r.last_attempt_at or r.discovered_at)
    queue=[]
    while pending or failed:
        queue.extend(pending[:3]); del pending[:3]
        if failed: queue.append(failed.pop(0))
    for index,r in enumerate(queue):
        if r.status=='processed' or r not in store.state.records:
            continue
        if r.last_attempt_at and r.last_attempt_at.astimezone(KST).date()==today:
            counts['deferred']+=1
            continue
        if analyzer.calls>=analyzer.max_calls:
            counts['deferred']+=1
            continue
        r.last_attempt_at=datetime.now(timezone.utc)
        r.attempts+=1
        try:
            # Revalidate legacy Europe PMC records against the corrected journal
            # matcher before spending money; old checkpoints lost the source title.
            if r.metadata.source=='europe_pmc':
                refreshed=refresh_metadata(http,r.metadata,journals)
                if not refreshed:
                    raise ValueError('journal_unverified')
                r=store.upsert(refreshed)
                if r.status=='processed':
                    store.save()
                    continue
            if not r.metadata.abstract:
                try:
                    refreshed=refresh_metadata(http,r.metadata,journals)
                except Exception as exc:
                    # A missing/failed abstract endpoint must not block a known
                    # publicly available full-text source.
                    log.warning('stage=metadata id=%s error=%s',r.id,type(exc).__name__)
                    refreshed=None
                if refreshed:
                    r=store.upsert(refreshed)
                    if r.status=='processed':
                        store.save()
                        continue
            evidence=r.metadata.abstract
            kind='abstract'
            url=r.metadata.pubmed_url or r.metadata.publisher_url
            if os.getenv('USE_FULL_TEXT','true').lower()=='true':
                try:
                    r.metadata.pmcid=resolve_pmcid(http,r.metadata)
                    body=full_text(http,r.metadata.pmcid)
                    combined=(evidence or '')+'\n\n'+(body or '')
                    if body and len(combined)<=int(os.getenv('MAX_INPUT_CHARS','120000')):
                        evidence=combined
                        kind='full_text'
                        url='https://europepmc.org/articles/'+r.metadata.pmcid
                    elif body:
                        log.warning('stage=fulltext id=%s fallback=abstract reason=input_limit',r.id)
                except Exception as exc:
                    log.warning('stage=fulltext id=%s fallback=abstract error=%s',r.id,type(exc).__name__)
            if not evidence or len(evidence.strip())<80:
                raise ValueError('missing_abstract')
            if len(evidence)>int(os.getenv('MAX_INPUT_CHARS','120000')):
                raise ValueError('evidence_too_long')
            # Reserve budget and checkpoint BEFORE the paid request (also survives crashes).
            store.state.ai_budget_used+=1
            store.save()
            analysis,usage=analyzer.analyze(r.metadata,evidence,kind)
            r.analysis=analysis
            r.evidence_source=kind
            r.evidence_url=url
            r.evidence_sha256=hashlib.sha256(evidence.encode()).hexdigest()
            r.summary_generated_at=datetime.now(timezone.utc)
            r.model=analyzer.model
            r.input_tokens=usage.get('input_tokens',0)
            r.output_tokens=usage.get('output_tokens',0)
            r.status='processed'
            r.last_error=None
            counts['processed']+=1
            log.info('stage=analyze id=%s status=processed recommended=%s',r.id,analysis.recommended)
        except BudgetExceeded:
            r.last_attempt_at=None
            r.attempts-=1
            counts['deferred']+=1
            break
        except APIRequestError as exc:
            r.status='failed'
            r.last_error=exc.safe_reason
            counts['failed']+=1
            counts['api_error']=exc.safe_reason
            counts['deferred']+=len(queue)-index-1
            log.error('stage=analyze status=blocked error=%s remaining_requests_stopped=true',exc.safe_reason)
            store.save()
            break
        except Exception as exc:
            r.status='failed'
            # Exceptions may include request details; never persist raw exception strings.
            safe_validation_errors = {
                'missing_abstract', 'evidence_too_long', 'journal_unverified',
                'Finding quotation is not in evidence', 'Unsupported numeric finding',
                'Unsupported sample size', 'Unsupported number in summary prose',
                'Summary number missing from displayed findings',
                'AI response incomplete', 'AI response refused or missing structured content',
            }
            reason=str(exc) if isinstance(exc,ValueError) and str(exc) in safe_validation_errors else type(exc).__name__
            r.last_error=reason
            counts['failed']+=1
            log.warning('stage=analyze id=%s status=failed error=%s',r.id,reason)
        store.save()
    return counts

def run(data_dir='data',collect_only=False,days=None):
    directory=Path(data_dir)
    store=Store(directory/'state.json')
    http=HTTP()
    journals=Journals()
    now=datetime.now(timezone.utc)
    since=now.date()-timedelta(days=days or int(os.getenv('LOOKBACK_DAYS','45')))
    if store.state.last_successful_collection and not days:
        since=min(since,(store.state.last_successful_collection-timedelta(days=3)).date())
    store.state.last_attempt=now
    health={'status':'ok','sources':{},'started_at':utcnow(),'since':since.isoformat()}
    for name,collector in [('pubmed',collect_pubmed),('europe_pmc',collect_europe)]:
        count=0
        try:
            for metadata in collector(http,journals,since):
                try:
                    store.upsert(metadata)
                    count+=1
                except ValueError:
                    log.warning('stage=deduplicate source=%s identifier_conflict',name)
            health['sources'][name]={'status':'ok','received':count}
        except Exception as exc:
            health['sources'][name]={'status':'failed','received':count,'error':type(exc).__name__}
            log.error('stage=collect source=%s error=%s',name,type(exc).__name__)
        store.save()
    for journal in journals.items:
        for feed in journal.get('feeds',[]):
            name='feed:'+journal['id']+':'+str(journal['feeds'].index(feed))
            try:
                count=0
                for metadata in collect_feed(http,journal,feed):
                    store.upsert(metadata)
                    count+=1
                health['sources'][name]={'status':'ok','received':count}
            except Exception as exc:
                health['sources'][name]={'status':'failed','error':type(exc).__name__}
    successes=sum(s['status']=='ok' for k,s in health['sources'].items() if k in ('pubmed','europe_pmc'))
    if successes==2 and all(s['status']=='ok' for s in health['sources'].values()):
        store.state.last_successful_collection=now
    elif successes==0:
        health['status']='failed'
    else:
        health['status']='partial'
    if not collect_only and not os.getenv('OPENAI_API_KEY'):
        log.error('stage=configuration missing=OPENAI_API_KEY analysis_skipped=true')
        health['status']='setup_required'
        counts={'processed':0,'failed':0,'deferred':sum(r.status!='processed' for r in store.state.records)}
    else:
        analyzer=Analyzer(http,max(0,int(os.getenv('MAX_AI_PAPERS','12'))))
        counts=process_records(store,analyzer,http,journals,collect_only)
    health.update(counts)
    if counts.get('api_error'):
        health['status']='setup_required'
    if counts['failed'] and health['status']=='ok':
        health['status']='partial'
    health['finished_at']=utcnow()
    store.save()
    store.export(directory/'papers.json',health)
    atomic_json(directory/'last_run.json',health)
    log.info('stage=complete status=%s records=%s processed=%s failed=%s',health['status'],len(store.state.records),counts['processed'],counts['failed'])
    return health

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',default='data')
    parser.add_argument('--collect-only',action='store_true')
    parser.add_argument('--days',type=int)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    health=run(args.data_dir,args.collect_only,args.days)
    raise SystemExit(1 if health['status'] in ('failed','setup_required') else 0)

if __name__=='__main__':
    main()
