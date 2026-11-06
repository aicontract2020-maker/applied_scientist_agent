"""Closed fixed-model worker. No validation labels, holdout, plugins or network."""
import argparse
import json
from pathlib import Path
import resource
import time


def fit_predict(request):
    import numpy as np
    from sklearn.dummy import DummyRegressor
    from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVR
    from threadpoolctl import threadpool_limits

    train, validation = request['train'], request['validation']
    x=np.asarray([r['features'] for r in train],dtype=np.float64)
    y=np.asarray([r['target'] for r in train],dtype=np.float64)
    z=np.asarray([r['features'] for r in validation],dtype=np.float64)
    results=[]
    with threadpool_limits(limits=1):
        for seed in (11,22,33):
            models={
                'median':DummyRegressor(strategy='median'),
                'ridge':make_pipeline(StandardScaler(),Ridge(alpha=1,solver='svd')),
                'svr':make_pipeline(StandardScaler(),SVR(kernel='rbf',C=10,epsilon=.1,gamma='scale',cache_size=200)),
                'hgb':HistGradientBoostingRegressor(loss='absolute_error',learning_rate=.1,max_iter=100,
                    max_leaf_nodes=31,min_samples_leaf=20,l2_regularization=0,max_bins=255,
                    max_features=1.0,categorical_features=None,early_stopping=False,random_state=seed),
                'extra_trees':ExtraTreesRegressor(n_estimators=100,criterion='squared_error',max_depth=None,
                    min_samples_split=2,min_samples_leaf=1,max_features=1.0,bootstrap=False,n_jobs=1,random_state=seed),
            }
            for name,model in models.items():
                start=time.monotonic(); model.fit(x,y); fit_seconds=time.monotonic()-start
                start=time.monotonic(); predictions=model.predict(z); predict_seconds=time.monotonic()-start
                if not np.isfinite(predictions).all(): raise ValueError('Nonfinite predictions')
                results.append({'model':name,'seed':seed,'fit_seconds':fit_seconds,'predict_seconds':predict_seconds,
                    'predictions':[{'id':r['id'],'prediction':float(v)} for r,v in zip(validation,predictions)]})
    return {'results':results,'peak_rss_native':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--input',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args()
    with Path(args.output).open('x') as handle:
        json.dump(fit_predict(json.loads(Path(args.input).read_text())),handle,allow_nan=False)
