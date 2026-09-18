from __future__ import annotations

import html
import json
import logging
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from .models import Metadata, normalize_doi

log = logging.getLogger(__name__)
NCBI = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
EPMC = 'https://www.ebi.ac.uk/europepmc/webservices/rest/'

class APIRequestError(RuntimeError):
    """Only allowlisted diagnostics, never a response message or request headers."""
    def __init__(self, status, code=None):
        allowed = {'insufficient_quota','invalid_api_key','model_not_found',
                   'account_deactivated','rate_limit_exceeded','invalid_json_schema',
                   'invalid_request_error','billing_hard_limit_reached'}
        self.status = int(status)
        self.code = code if isinstance(code,str) and code in allowed else 'unknown'
        self.safe_reason = f'openai_http_{self.status}_{self.code}'
        super().__init__(self.safe_reason)

class HTTP:
    def __init__(self):
        self.last_ncbi = 0.0

    def request(self, url, params=None, body=None, headers=None, attempts=3):
        if params:
            url += '?' + urllib.parse.urlencode(params)
        host = urllib.parse.urlparse(url).hostname
        if not url.startswith('https://'):
            raise ValueError('Only HTTPS sources are accepted')
        for attempt in range(attempts):
            if host == 'eutils.ncbi.nlm.nih.gov':
                time.sleep(max(0, 0.36 - (time.monotonic() - self.last_ncbi)))
                self.last_ncbi = time.monotonic()
            request = urllib.request.Request(url, data=body, headers={'User-Agent':'VetDigest/1.0', **(headers or {})})
            try:
                with urllib.request.urlopen(request, timeout=40) as response:
                    raw = response.read(12_000_001)
                    if len(raw) > 12_000_000:
                        raise ValueError('Source response too large')
                    return raw
            except urllib.error.HTTPError as exc:
                if host == 'api.openai.com':
                    try:
                        error = json.loads(exc.read(16384)).get('error', {})
                        code = error.get('code') or error.get('type')
                    except (ValueError,AttributeError,TypeError,OSError):
                        code = None
                    raise APIRequestError(exc.code, code) from None
                if exc.code not in (408,429,500,502,503,504) or attempt == attempts - 1:
                    raise RuntimeError(f'HTTP {exc.code} at {host}') from None
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == attempts - 1:
                    raise RuntimeError(f'Network timeout/failure at {host}') from None
            time.sleep(2 ** attempt)
        raise RuntimeError('HTTP request exhausted')

    def json(self, url, **kwargs):
        return json.loads(self.request(url, **kwargs))

def clean_text(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value or ''))).strip()

def node_text(node):
    # XML has already decoded markup/entities. Treating inequalities as HTML
    # would delete everything between a literal '<' and a later '>'.
    return re.sub(r'\s+', ' ', ''.join(node.itertext())).strip() if node is not None else ''

def exact_date(value):
    if value and re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(value)):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    return None

def xml_date(node):
    if node is None:
        return None, None
    parts = [node.findtext(k) for k in ('Year','Month','Day')]
    raw = '-'.join(p for p in parts if p) or node.findtext('MedlineDate')
    if not all(parts):
        return None, raw
    try:
        month = int(parts[1]) if parts[1].isdigit() else datetime.strptime(parts[1][:3], '%b').month
        return date(int(parts[0]), month, int(parts[2])), raw
    except ValueError:
        return None, raw

class Journals:
    def __init__(self, path='config/journals.json'):
        self.items = [j for j in json.loads(Path(path).read_text(encoding='utf-8-sig'))['journals'] if j['enabled']]
        self.lookup = {}
        for j in self.items:
            for name in [j['name'],j['short'], *j['aliases'], *j['issns']]:
                self.lookup[self.key(name)] = j

    @staticmethod
    def key(name):
        return re.sub(r'[^a-z0-9]', '', (name or '').lower())

    def match(self, *names):
        return next((self.lookup[self.key(n)] for n in names if self.key(n) in self.lookup), None)

    def match_source(self, names, issns):
        # An erroneous ISSN must not override a supplied, unrelated journal title.
        named = [n for n in names if n and n.strip()]
        return self.match(*named) if named else self.match(*issns)

    def pubmed_query(self):
        return '(' + ' OR '.join(f'"{j["issns"][0]}"[ISSN]' for j in self.items) + ')'

    def europe_query(self):
        return '(' + ' OR '.join(f'ISSN:{s}' for j in self.items for s in j['issns']) + ')'

def maybe_doi(value):
    try:
        return normalize_doi(value)
    except ValueError:
        log.warning('stage=parse invalid_doi ignored')
        return None

def parse_pubmed(raw, journals):
    root = ET.fromstring(raw)
    if root.tag != 'PubmedArticleSet':
        raise ValueError('Unexpected PubMed document')
    if root.find('.//ERROR') is not None:
        raise ValueError('PubMed error response')
    output = []
    for item in root.findall('.//PubmedArticle'):
        try:
            article = item.find('./MedlineCitation/Article')
            if article is None:
                continue
            j = journals.match_source([article.findtext('./Journal/Title'),article.findtext('./Journal/ISOAbbreviation')], [article.findtext('./Journal/ISSN')])
            if not j:
                continue
            ids = {n.attrib.get('IdType'):n.text for n in item.findall('./PubmedData/ArticleIdList/ArticleId')}
            doi = maybe_doi(ids.get('doi') or next((n.text for n in article.findall('ELocationID') if n.attrib.get('EIdType')=='doi'),None))
            pmid = item.findtext('./MedlineCitation/PMID')
            pubdate, rawdate = xml_date(article.find('./Journal/JournalIssue/PubDate'))
            online, _ = xml_date(article.find('./ArticleDate[@DateType="Electronic"]'))
            if online is None:
                online, _ = xml_date(item.find('./PubmedData/History/PubMedPubDate[@PubStatus="epublish"]'))
            abstract = ' '.join(((n.attrib.get('Label','') + ': ') if n.attrib.get('Label') else '') + node_text(n) for n in article.findall('./Abstract/AbstractText'))
            output.append(Metadata(title=node_text(article.find('ArticleTitle')), journal=j['name'], journal_id=j['id'], publication_date=pubdate, online_publication_date=online, publication_date_raw=rawdate, doi=doi, pmid=pmid, pmcid=ids.get('pmc'), publisher_url=f'https://doi.org/{doi}' if doi else None, pubmed_url=f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/' if pmid else None, abstract=abstract or None, source='pubmed', source_id=pmid))
        except (ValueError, TypeError) as exc:
            log.warning('stage=parse source=pubmed error=%s',type(exc).__name__)
    return output

def parse_europe(payload, journals):
    results = payload['resultList']['result']
    if not isinstance(results,list):
        raise ValueError('Unexpected Europe PMC result list')
    output = []
    for item in results:
        try:
            info = item.get('journalInfo',{})
            journal = info.get('journal',{})
            j = journals.match_source([journal.get('title'),journal.get('medlineAbbreviation'),item.get('journalTitle')], [journal.get('issn'),journal.get('essn')])
            if not j:
                continue
            doi = maybe_doi(item.get('doi'))
            pmid = item.get('pmid') or (item.get('id') if item.get('source')=='MED' else None)
            output.append(Metadata(title=clean_text(item.get('title')),journal=j['name'],journal_id=j['id'],doi=doi,pmid=pmid,pmcid=item.get('pmcid'),publication_date=exact_date(info.get('dateOfPublication')),online_publication_date=exact_date(item.get('electronicPublicationDate')),publication_date_raw=info.get('dateOfPublication') or item.get('firstPublicationDate') or item.get('pubYear'),publisher_url=f'https://doi.org/{doi}' if doi else None,pubmed_url=f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/' if pmid else None,abstract=clean_text(item.get('abstractText')) or None,source='europe_pmc',source_id=item.get('id')))
        except (ValueError,TypeError) as exc:
            log.warning('stage=parse source=europe_pmc error=%s',type(exc).__name__)
    return output

def ncbi_params(**kwargs):
    return {**kwargs, 'tool':'vet_clinical_digest', **({'email':os.environ['NCBI_EMAIL']} if os.getenv('NCBI_EMAIL') else {}), **({'api_key':os.environ['NCBI_API_KEY']} if os.getenv('NCBI_API_KEY') else {})}

def collect_pubmed(http, journals, since, until=None):
    until = until or date.today()
    window = f'"{since:%Y/%m/%d}":"{until:%Y/%m/%d}"'
    query = journals.pubmed_query() + f' AND ({window}[EDAT] OR {window}[MDAT] OR {window}[PDAT])'
    ids, start = [], 0
    while True:
        result = http.json(NCBI+'esearch.fcgi',params=ncbi_params(db='pubmed',term=query,retmode='json',retmax=500,retstart=start))['esearchresult']
        if 'ERROR' in result or 'error' in result:
            raise ValueError('PubMed query failed')
        count = int(result['count'])
        if count > 9999:
            raise ValueError('PubMed window exceeds 9999; use a smaller backfill window')
        ids.extend(result['idlist'])
        start += 500
        if start >= count:
            break
    for pos in range(0,len(ids),100):
        raw = http.request(NCBI+'efetch.fcgi',params=ncbi_params(db='pubmed',id=','.join(ids[pos:pos+100]),retmode='xml'))
        yield from parse_pubmed(raw,journals)

def collect_europe(http,journals,since,until=None):
    until = until or date.today()
    window = f'[{since.isoformat()} TO {until.isoformat()}]'
    query = journals.europe_query() + f' AND (FIRST_IDATE:{window} OR UPDATE_DATE:{window} OR FIRST_PDATE:{window})'
    cursor = '*'
    while True:
        result = http.json(EPMC+'search',params={'query':query,'format':'json','resultType':'core','pageSize':100,'cursorMark':cursor})
        yield from parse_europe(result,journals)
        nxt = result.get('nextCursorMark')
        if not result['resultList']['result'] or not nxt or nxt == cursor:
            break
        cursor = nxt

def refresh_metadata(http, metadata, journals):
    if metadata.pmid:
        items = parse_pubmed(http.request(NCBI+'efetch.fcgi',params=ncbi_params(db='pubmed',id=metadata.pmid,retmode='xml')),journals)
    elif metadata.doi:
        items = parse_europe(http.json(EPMC+'search',params={'query':f'DOI:"{metadata.doi}"','format':'json','resultType':'core'}),journals)
    else:
        items = []
    return items[0] if items else None

def collect_feed(http, journal, url):
    # Only explicitly configured publisher feeds; no guessed URLs or HTML scraping.
    root = ET.fromstring(http.request(url))
    entries = root.findall('.//item') or root.findall('{http://www.w3.org/2005/Atom}entry')
    for entry in entries:
        fields = {n.tag.split('}')[-1]:n for n in entry}
        title = node_text(fields.get('title'))
        if not title:
            continue
        link_node = fields.get('link')
        link = (link_node.attrib.get('href') or link_node.text) if link_node is not None else None
        raw_id = node_text(fields.get('identifier')) or node_text(fields.get('guid')) or link or ''
        match = re.search(r'10\.\d{4,9}/[^\s<>]+',raw_id)
        doi = maybe_doi(match.group(0)) if match else None
        # Feed descriptions can be teasers, so never pass them off as complete abstracts.
        yield Metadata(title=title,journal=journal['name'],journal_id=journal['id'],doi=doi,publisher_url=link if link and link.startswith('https://') else None,source='publisher_feed',source_id=raw_id or title)

def resolve_pmcid(http, metadata):
    if metadata.pmcid:
        return metadata.pmcid
    if not metadata.doi and not metadata.pmid:
        return None
    query = f'DOI:"{metadata.doi}"' if metadata.doi else f'EXT_ID:{metadata.pmid} AND SRC:MED'
    payload = http.json(EPMC+'search', params={'query':query,'format':'json','resultType':'core'})
    for item in payload.get('resultList',{}).get('result',[]):
        matches = (metadata.doi and maybe_doi(item.get('doi')) == metadata.doi) or (metadata.pmid and item.get('pmid') == metadata.pmid)
        pmcid = item.get('pmcid')
        if matches and pmcid and re.fullmatch(r'PMC\d+',pmcid):
            return pmcid
    return None


def extract_full_text(raw):
    root = ET.fromstring(raw)
    body = root.find('./body')
    if root.tag != 'article' or body is None or not node_text(body):
        return None
    # Preserve paragraph/section/table boundaries, including inline appendices.
    blocks = {'sec','title','p','table-wrap','tr','fig','list-item','app','caption'}
    def render(node):
        text = node.text or ''
        for child in node:
            value = render(child)
            if child.tag in {'td','th'}:
                value = ' | '+value+' | '
            text += ('\n'+value+'\n' if child.tag in blocks else value) + (child.tail or '')
        return text
    parts = [render(body)]
    for node in root.findall('./floats-group') + root.findall('./back/app-group'):
        parts.append(render(node))
    return '\n'.join(re.sub(r'[ \t]+',' ',line).strip() for line in '\n'.join(parts).splitlines() if line.strip())


def full_text(http,pmcid):
    if not pmcid or not re.fullmatch(r'PMC\d+',pmcid):
        return None
    return extract_full_text(http.request(EPMC+pmcid+'/fullTextXML'))
