import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from research_harness.primary_literature import canonical_paper_url, fetch_primary
from research_harness.literature_study import LiteratureStudy, reject_lr_residual_backprojection

class PrimaryEvidenceTests(unittest.TestCase):
    def test_reader_rejects_nonpaper_destinations(self):
        for url in ['https://example.com/abs/1234.56789','https://arxiv.org/pdf/1234.56789','https://arxiv.org/abs/1234.56789?download=1','http://arxiv.org/abs/1234.56789']:
            with self.assertRaises(ValueError): canonical_paper_url(url)
        self.assertEqual(canonical_paper_url('https://arxiv.org/abs/1234.56789v2'),'https://arxiv.org/abs/1234.56789v2')
    def test_reader_preserves_source_identity(self):
        html=b'<meta name="citation_title" content="Primary paper"><blockquote class="abstract">Abstract: Test evidence</blockquote>'
        with tempfile.TemporaryDirectory() as tmp, patch('research_harness.primary_literature.download',return_value=html):
            result=fetch_primary('https://arxiv.org/abs/1234.56789',Path(tmp)/'paper')
            self.assertEqual(result['abstract'],'Test evidence'); self.assertEqual(len(result['html_sha256']),64)
    def test_stopped_family_rejected(self):
        with self.assertRaisesRegex(ValueError,'Stopped'):
            reject_lr_residual_backprojection('def enhance(lr,sr):\n down=resize(sr)\n residual=lr-down\n return sr+resize(residual)')
        reject_lr_residual_backprojection('def enhance(lr,sr):\n detail=sr-blur(sr)\n return sr+detail')
    def test_no_search_no_registration(self):
        study=LiteratureStudy.__new__(LiteratureStudy)
        with tempfile.TemporaryDirectory() as tmp:
            study.destination=Path(tmp)
            with self.assertRaisesRegex(ValueError,'native literature search'): study.register()
    def test_reads_close_at_registration(self):
        study=LiteratureStudy.__new__(LiteratureStudy);study.registered=True;study.closed=False
        with self.assertRaisesRegex(ValueError,'before registration'): study.read_paper({})
    def test_registration_requires_read_fulltext_and_fresh_citation(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            study=LiteratureStudy.__new__(LiteratureStudy);study.destination=Path(tmp);study.actor=Path(tmp)
            study.search_records=lambda:[{'type':'web_search'}];study.library={}
            with self.assertRaisesRegex(ValueError,'at least two'):study.register()
            study.library={'a':{'full_text':'methods'},'b':{'full_text':None}}
            (study.actor/'research.json').write_text(json.dumps({'new_evidence':[{'source':'https://arxiv.org/abs/2008.13751'}]}))
            with self.assertRaisesRegex(ValueError,'Previously supplied'):study.register()
