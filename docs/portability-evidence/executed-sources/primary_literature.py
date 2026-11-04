"""Fetch primary arXiv paper text, not arbitrary websites or benchmark media.

Search remains the real agent's responsibility through its native web search tool.
This reader records immutable source identity and returns text, never images/data.
"""
import hashlib
import re
import subprocess
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit


class AbstractParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.meta = {}; self.abstract = []; self.active = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == 'meta' and values.get('name', '').startswith('citation_'):
            self.meta.setdefault(values['name'], []).append(values.get('content', ''))
        if tag == 'blockquote' and 'abstract' in values.get('class', ''):
            self.active = True

    def handle_endtag(self, tag):
        if tag == 'blockquote': self.active = False

    def handle_data(self, value):
        if self.active: self.abstract.append(value)


def canonical_paper_url(url):
    if not isinstance(url, str): raise ValueError('Paper URL must be text')
    value = urlsplit(url)
    if value.scheme != 'https' or value.netloc != 'arxiv.org' or value.query or value.fragment:
        raise ValueError('Read only https://arxiv.org/abs/PAPER_ID primary paper pages')
    match = re.fullmatch(r'/abs/((?:\d{4}\.\d{4,5}|[a-z-]+/\d{7})(?:v\d+)?)', value.path)
    if not match: raise ValueError('Not an arXiv abstract identifier')
    return 'https://arxiv.org/abs/' + match.group(1)


def download(url, cap):
    request = urllib.request.Request(url, headers={'User-Agent': 'ResearchHarness/0.7 local scholarly research'})
    with urllib.request.urlopen(request, timeout=25) as response:
        final = urlsplit(response.geturl())
        if final.scheme != 'https' or final.hostname not in ('arxiv.org', 'export.arxiv.org'):
            raise ValueError('Primary-source redirect left arXiv')
        data = response.read(cap + 1)
    if len(data) > cap: raise ValueError('Primary paper download exceeds declared size limit')
    return data


def fetch_primary(url, folder, full=False):
    url = canonical_paper_url(url)
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=False)
    raw = download(url, 512 * 1024)
    (folder/'abstract.html').write_bytes(raw)
    parser = AbstractParser(); parser.feed(raw.decode('utf-8', errors='replace'))
    title = parser.meta.get('citation_title', [''])[0]
    abstract = ' '.join(' '.join(parser.abstract).split()).removeprefix('Abstract:').strip()
    if not title or not abstract: raise ValueError('Primary page has no verified title/abstract')
    result = {'url': url, 'title': title, 'authors': parser.meta.get('citation_author', []),
              'date': parser.meta.get('citation_date', [''])[0], 'abstract': abstract,
              'read_at': datetime.now(timezone.utc).isoformat(),
              'html_sha256': hashlib.sha256(raw).hexdigest(), 'download_bytes': len(raw),
              'full_text': None, 'full_text_truncated': False}
    if full:
        pdf_url = url.replace('/abs/', '/pdf/')
        pdf = download(pdf_url, 20 * 1024 * 1024)
        (folder/'paper.pdf').write_bytes(pdf)
        subprocess.run(['pdftotext', '-layout', str(folder/'paper.pdf'), str(folder/'paper.txt')],
                       check=True, capture_output=True, timeout=20)
        text = (folder/'paper.txt').read_text(errors='replace')
        result.update(pdf_url=pdf_url, pdf_sha256=hashlib.sha256(pdf).hexdigest(),
                      download_bytes=len(raw)+len(pdf), full_text=text[:40000],
                      full_text_truncated=len(text)>40000,
                      extraction_note='First 40000 extracted characters; includes methods where available; images are never returned.')
    return result
