"""Trusted fixed HGB comparison; the candidate is interpreted arithmetic, not Python."""
import argparse
import json
from pathlib import Path
import resource
import statistics
import sys
import time

# Only controller-staged trusted sources are placed here; no candidate imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from tabular_features import parse, evaluate


def fit_predict(request):
    import numpy as np
    from sklearn.ensemble import HistGradientBoostingRegressor
    from threadpoolctl import threadpool_limits
    train, validation, holdout = (request[key] for key in ('train','validation','holdout'))
    expressions = parse(request['candidate'])
    start = time.monotonic()
    cx = np.asarray([evaluate(expressions,r['features']) for r in train])
    transform_train_seconds = time.monotonic()-start
    x = np.asarray([r['features'] for r in train]); y = np.asarray([r['target'] for r in train])
    z = np.asarray([r['features'] for r in validation]); h = np.asarray([r['features'] for r in holdout])
    results = []
    with threadpool_limits(limits=1):
        for seed in (11,22,33):
            for kind, features in (('baseline',x),('candidate',cx)):
                model = HistGradientBoostingRegressor(loss='absolute_error', learning_rate=.1,
                    max_iter=100, max_leaf_nodes=31, min_samples_leaf=20, l2_regularization=0,
                    max_bins=255, max_features=1.0, categorical_features=None,
                    early_stopping=False, random_state=seed)
                start=time.monotonic(); model.fit(features,y); fit_seconds=time.monotonic()-start
                validation_predictions = model.predict(z).tolist() if kind=='baseline' else None
                # Five frozen whole-batch timing repetitions, not scientific replicates.
                times=[]; predictions=None
                for repeat in range(5):
                    start=time.monotonic()
                    inputs = h if kind=='baseline' else np.asarray([evaluate(expressions,r['features']) for r in holdout])
                    current=model.predict(inputs).tolist(); times.append(time.monotonic()-start)
                    if predictions is not None and current!=predictions: raise ValueError('Timing repetitions changed predictions')
                    predictions=current
                results.append({'kind':kind,'seed':seed,'fit_seconds':fit_seconds,
                    'batch_seconds':statistics.median(times),'timing_seconds':times,
                    'validation_predictions':validation_predictions,
                    'predictions':[{'id':r['id'],'prediction':float(p)} for r,p in zip(holdout,predictions)]})
    return {'results':results,'transform_train_seconds':transform_train_seconds,
            'peak_rss_native':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--input',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args()
    with Path(args.output).open('x') as handle:
        json.dump(fit_predict(json.loads(Path(args.input).read_text())),handle,allow_nan=False)
