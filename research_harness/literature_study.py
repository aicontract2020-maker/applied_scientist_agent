"""An autonomous researcher with real search and primary-paper retrieval."""
import ast
import json
from pathlib import Path

from .autonomy import AutonomousStudy, atomic_json
from .primary_literature import canonical_paper_url, fetch_primary

OLD_SOURCES = {'1712.06087', '2008.13751', '1811.12866'}


def reject_lr_residual_backprojection(source):
    """Conservative dataflow gate for the stopped cross-LR/SR residual family.

This is not a proof of semantic novelty. The agent must also explain the distinct
mechanism and its declarations/trajectory remain auditable.
"""
    tree = ast.parse(source)
    tags = {'lr': {'LR'}, 'sr': {'SR'}}
    def taint(node):
        if isinstance(node, ast.Name): return tags.get(node.id, set())
        children = []
        for child in ast.iter_child_nodes(node): children.append(taint(child))
        union = set().union(*children) if children else set()
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Sub):
            left, right = taint(node.left), taint(node.right)
            if ('LR' in left and 'SR' in right) or ('SR' in left and 'LR' in right):
                raise ValueError('Stopped LR-versus-SR residual correction family cannot be reopened')
        return union
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = taint(node.value)
            for target in node.targets:
                if isinstance(target, ast.Name): tags[target.id] = value
        elif isinstance(node, ast.Return): taint(node.value)


class LiteratureStudy(AutonomousStudy):
    def __init__(self, destination, study):
        super().__init__(destination, study)
        self.read_count = 0
        self.library = {}

    def search_records(self):
        path = self.destination/'agent-events.jsonl'
        if not path.exists(): return []
        found = {}
        for line in path.read_text().splitlines():
            try: value = json.loads(line)
            except ValueError: continue
            item = value.get('item', {})
            if item.get('type') == 'web_search': found[item.get('id', str(len(found)))] = item
        return list(found.values())

    def read_paper(self, request):
        if self.registered or self.closed: raise ValueError('Literature must be read before registration/results')
        if self.read_count >= 6: raise ValueError('Six primary-paper retrieval requests exhausted')
        self.read_count += 1
        url = canonical_paper_url(request.get('url'))
        full = request.get('full', False)
        if type(full) is not bool: raise ValueError('full must be boolean')
        folder = self.control/'primary-papers'/f'paper-{self.read_count}'
        self.log('PRIMARY_READ_REQUEST', url=url, full=full, ordinal=self.read_count)
        paper = fetch_primary(url, folder, full)
        self.library[url] = paper
        atomic_json(self.destination/'library.json', list(self.library.values()))
        self.log('PRIMARY_READ_COMPLETED', url=url, full=full, download_bytes=paper['download_bytes'], html_sha256=paper['html_sha256'])
        return paper

    def evidence_sources(self):
        return set(self.library)

    def register(self):
        if self.closed or self.registered:
            raise ValueError('Registration is single-use; a rejected route cannot be revised')
        searches = self.search_records()
        if not 1 <= len(searches) <= 6:
            raise ValueError('Use real native literature search before registration, within six calls')
        if len(self.library) < 2 or not any(x.get('full_text') for x in self.library.values()):
            raise ValueError('Read at least two primary papers, at least one with full text')
        plan = json.loads((self.actor/'research.json').read_text())
        sources = [canonical_paper_url(x.get('source')) for x in plan.get('new_evidence', [])]
        fresh = [url for url in sources if url.rsplit('/', 1)[-1].split('v')[0] not in set(getattr(self, 'policy', {}).get('excluded_evidence_ids', OLD_SOURCES))]
        if not fresh: raise ValueError('Previously supplied papers do not count as new external evidence')
        atomic_json(self.destination/'search-records.json', searches)
        compliance = plan.get('stopped_route_compliance')
        expected = getattr(self, 'policy', {}).get('stopped_route_compliance', {'uses_prediction_ensembles': False, 'uses_lr_residual_backprojection': False, 'retunes_stopped_parameters': False})
        if compliance != expected or any(type(v) is not bool for v in compliance.values()):
            return self.reject_registration('Stopped-route compliance failed; no retry')
        try:
            reject_lr_residual_backprojection((self.actor/'candidate.py').read_text())
        except ValueError as exc:
            return self.reject_registration(str(exc))
        return super().register()

    def serve_request(self, path):
        if not path.is_symlink() and path.stat().st_size <= 4096:
            request = json.loads(path.read_text())
            if request.get('operation') == 'read':
                self.log('AGENT_REQUEST', request_id=path.stem, operation='read')
                return self.read_paper(request)
        return super().serve_request(path)
