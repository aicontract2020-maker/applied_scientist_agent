"""Six fixed Extra Trees fits, exact A1 validation reproduction, no hidden labels."""
import argparse
import json
from pathlib import Path
import resource
import statistics
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parent))
from airfoil_candidate import augment


def fit_predict(request):
    import numpy as np
    from sklearn.ensemble import ExtraTreesRegressor
    from threadpoolctl import threadpool_limits
    train,validation,holdout=(request[k] for k in ('train','validation','holdout'))
    x=np.asarray([r['features'] for r in train]); y=np.asarray([r['target'] for r in train])
    z=np.asarray([r['features'] for r in validation]); h=np.asarray([r['features'] for r in holdout])
    start=time.monotonic(); cx=np.asarray([augment(r['features']) for r in train]); transform=time.monotonic()-start
    results=[]
    with threadpool_limits(limits=1):
        for seed in (11,22,33):
            for kind in (('candidate','baseline') if seed==22 else ('baseline','candidate')):
                model=ExtraTreesRegressor(n_estimators=100,criterion='squared_error',max_depth=None,
                    min_samples_split=2,min_samples_leaf=1,max_features=1.0,bootstrap=False,n_jobs=1,random_state=seed)
                start=time.monotonic(); model.fit(x if kind=='baseline' else cx,y); fit=time.monotonic()-start
                vp=model.predict(z).tolist() if kind=='baseline' else None
                times=[]; predictions=None
                for _ in range(5):
                    start=time.monotonic()
                    inputs=h if kind=='baseline' else np.asarray([augment(r['features']) for r in holdout])
                    current=model.predict(inputs).tolist(); times.append(time.monotonic()-start)
                    if predictions is not None and predictions!=current: raise ValueError('Timing repetitions changed prediction')
                    predictions=current
                results.append({'kind':kind,'seed':seed,'fit_seconds':fit,'timing_seconds':times,
                    'batch_seconds':statistics.median(times),'validation_predictions':vp,
                    'predictions':[{'id':r['id'],'prediction':v} for r,v in zip(holdout,predictions)]})
    return {'results':results,'transform_train_seconds':transform,
            'peak_rss_native':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--input',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args()
    with Path(args.output).open('x') as handle:
        json.dump(fit_predict(json.loads(Path(args.input).read_text())),handle,allow_nan=False)
