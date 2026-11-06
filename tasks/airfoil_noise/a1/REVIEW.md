# Airfoil baseline qualification — AWAITING_REVIEW

Exact SHA-256: `ac8f7df93f688a9621038c881fa5ab312e4bc5790d7f59c134547dbbd81e2dd5`

No real model fit, prediction, validation or holdout score is authorized by preparation.

Review docs/AIRFOIL_BASELINE_REVIEW.md and the complete frozen recipe below. Approval covers 15 fixed baseline fits on training data and condition-level validation only. Any failed threshold closes this qualification; no tuning or retry. Final holdout remains sealed.

```json
{
  "source": {
    "id": "uci-airfoil-condition-v1",
    "url": "https://archive.ics.uci.edu/dataset/291/airfoil+self-noise",
    "download": "https://archive.ics.uci.edu/static/public/291/airfoil+self+noise.zip",
    "archive_sha256": "5c7767ba53ad827d3f48ba1eb9434117f4892df8f10bc4c99e118a9e8a7ae07c",
    "raw_sha256": "74c75fd71783f1e6b71f8a622b993dc592897a97cd689c5090a07147a1b097b3",
    "license": "CC BY 4.0",
    "citation": "Brooks, Pope & Marcolini (1989). Airfoil Self-Noise. UCI. DOI:10.24432/C5VW2C"
  },
  "counts": {
    "train": {
      "rows": 961,
      "groups": 67
    },
    "validation": {
      "rows": 257,
      "groups": 18
    },
    "holdout": {
      "rows": 285,
      "groups": 21
    }
  },
  "recipe": {
    "kind": "airfoil-condition-baseline",
    "version": 1,
    "seeds": [
      11,
      22,
      33
    ],
    "hypothesis": "A fixed learned reference reduces condition-macro validation MAE by >=1 dB versus train-median at every seed and has a positive group-bootstrap lower bound.",
    "decision_purpose": "Qualify the lowest mean error reference from a bounded fixed model set; not global SOTA or scientific novelty.",
    "models": [
      "median",
      "ridge",
      "svr",
      "hgb",
      "extra_trees"
    ],
    "baseline_parameters": {
      "median": "DummyRegressor(strategy=median), fitted on training rows",
      "ridge": "StandardScaler then Ridge(alpha=1, solver=svd)",
      "svr": "StandardScaler then SVR(kernel=rbf, C=10, epsilon=.1, gamma=scale, cache_size=200); no target scaling",
      "hgb": "absolute_error, learning_rate=.1, max_iter=100, max_leaf_nodes=31, min_samples_leaf=20, l2_regularization=0, max_bins=255, max_features=1.0, categorical_features=None, early_stopping=False",
      "extra_trees": "100 trees, squared_error, unlimited depth, min_samples_split=2, min_samples_leaf=1, max_features=1.0, bootstrap=False, n_jobs=1",
      "other_parameters": "Pinned scikit-learn 1.7.2 defaults; random_state=seed where supported"
    },
    "controls": [
      "Pinned raw data and fixed target-blind condition split",
      "All models train on original row-weighted training set only; scaling fitted on training rows",
      "Validation labels stay in controller; no final holdout mounted",
      "Single-thread CPU, fixed versions, no tuning/early stopping, all 15 fits charged"
    ],
    "group_rule": {
      "columns": [
        1,
        2,
        3
      ],
      "split": "airfoil-condition-v1",
      "boundaries": [
        0.6,
        0.8
      ],
      "minimum_groups": {
        "train": 20,
        "validation": 10,
        "holdout": 10
      }
    },
    "primary_metric": "Mean of per-condition mean absolute errors, in dB; every condition equal weight",
    "minimum_gain_db": 1.0,
    "threshold_reason": "Proposed engineering qualification margin, not an established business or perceptual threshold",
    "selection": "Lowest mean condition-macro MAE across 3 seeds among ridge, svr, hgb, extra_trees; ties use that order; never choose a different model to rescue a failed selected model",
    "bootstrap": {
      "resamples": 10000,
      "seed": 20261106,
      "confidence_per_model": 0.99,
      "lower_quantile": 0.005,
      "upper_quantile": 0.995
    },
    "uncertainty": "Resample complete validation condition groups with replacement on seed-averaged paired losses. Four 99% marginal percentile intervals mitigate selection (nominal Bonferroni family coverage >=96%, approximate bootstrap only). Seeds measure training variation, not independent data. Unknown campaign dependence remains.",
    "validity": [
      "Pinned source/data/environment; exact identities and finite complete outputs",
      "Actual OS isolation probe passes; every condition stays in one partition",
      "Median/Ridge/SVR/HGB cross-seed prediction range <=1e-8; Extra Trees variation is reported, not invalidated"
    ],
    "max_deterministic_prediction_range": 1e-08,
    "go": "Only draft a separate candidate protocol; no automatic candidate execution or holdout scoring",
    "stop": "Close qualification; no alternate model, changed split, tuning or automatic retry",
    "invalid": "Preserve failed measurement and reservation; no automatic retry or scientific conclusion",
    "limits": {
      "worker_seconds": 240,
      "output_bytes": 16777216,
      "threads": 1,
      "attempts": 1,
      "fits": 15
    },
    "costs": {
      "model_calls": 0,
      "paid_cloud_jobs": 0,
      "actual_local_cost_usd": null,
      "unpriced": [
        "installation/downloads",
        "electricity/depreciation",
        "retained storage",
        "human review"
      ]
    },
    "python": "3.12",
    "packages": {
      "numpy": "1.26.4",
      "scipy": "1.15.3",
      "scikit-learn": "1.7.2",
      "joblib": "1.5.2",
      "threadpoolctl": "3.6.0"
    }
  }
}
```
