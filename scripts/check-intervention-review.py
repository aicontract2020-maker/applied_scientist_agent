"""Actual OS-isolated software fixtures; never reserve or read benchmark images."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from research_harness.autonomy import AutonomousStudy, ROOT
from research_harness.intervention_review import catalog


def main():
    fixtures={
        'identity':'import numpy as np\ndef enhance(lr,sr): return sr.copy()\n',
        'clip-variant':'import numpy as np\ndef enhance(lr,sr): return np.clip(np.clip(sr,0,1),0,1)\n',
        'rounding-noop':'import numpy as np\ndef enhance(lr,sr): return np.round(np.clip(sr,0,1)*255)/255\n',
        'g6-original':(ROOT/'tasks/image_super_resolution/g6/candidate.py').read_text(),
        'g4-retuned-renamed':(ROOT/'tasks/image_super_resolution/g4/candidate.py').read_text().replace('0.005','0.02').replace('delta','correction'),
    }
    for route in catalog(ROOT,[]):
        if route.get('source') and route['id']!='G1': fixtures['stopped-'+route['id']]=route['source']
    results=[]
    for name,source in fixtures.items():
        with tempfile.TemporaryDirectory(prefix='review-software-fixture-') as tmp:
            base=Path(tmp);study=base/'study';study.mkdir()
            policy={'controls':['synthetic fixture only'],'minimum_effect':.05,'max_latency_ratio':2.5,
                    'bootstrap':{'seed':20261103},'observation_ids':[],
                    'limits':{'agent_session_seconds':1200},'intervention_review':{'required':True,'reviewer_seconds':120}}
            (study/'policy.json').write_text(json.dumps(policy))
            (study/'inputs.lock.json').write_text('{"files":{}}')
            (study/'literature.json').write_text('[{"url":"https://example.test/software-fixture"}]')
            (study/'intervention-catalog.json').write_text(json.dumps(catalog(ROOT,[])))
            controller=AutonomousStudy(base/'result',study)
            (controller.actor/'candidate.py').write_text(source)
            plan={**policy,'hypothesis':'Software gate fixture, not a scientific hypothesis','mechanism':name,'baseline':'synthetic input',
                  'why_not_g1_retry':'fixture','stop_route':'fixture',
                  'new_evidence':[{'source':'https://example.test/software-fixture','claim':'fixture','why_distinct':'fixture'}]}
            (controller.actor/'research.json').write_text(json.dumps(plan))
            result=controller.register()
            assert result['status']=='REJECTED' and controller.closed and controller.registered is None, result
            assert not (controller.destination/'registered.json').exists()
            assert not (controller.control/'reference-logs').exists()
            assert not (controller.session/'reviewer').exists(), 'known fixtures must not spend model tokens'
            try: controller.run_experiment()
            except ValueError: pass
            else: raise AssertionError('Rejected fixture could run')
            review=json.loads((controller.destination/'intervention-review.json').read_text())
            assert 'Stopped implementation fingerprint' in result['reason'] or 'No observable intervention' in result['reason'], result
            if review.get('probe_execution'): assert review['probe_execution']['error'] is None, review
            results.append({'fixture':name,'decision':'REJECTED','reason':result['reason'],
                            'probe':review.get('probe'),'probe_execution':review.get('probe_execution'),
                            'registered':False,'reference_started':False,'model_called':False})
    print(json.dumps({'scope':'OS-isolated software fixtures, not scientific evidence','platform':sys.platform,'results':results},indent=2))

if __name__=='__main__':main()
