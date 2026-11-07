# A2 Strouhal candidate — AWAITING_RESEARCH_REVIEW

Exact SHA-256: `de0f852d0bfb7a832604aef4f2fb5c82944176bda4a354deadb573ed726ea5de`

No real candidate training, prediction or final scoring performed.

Read docs/AIRFOIL_CANDIDATE_REVIEW.md. Approval would consume all 285 final rows in 21 conditions once. Six paired Extra Trees fits; gain >=0.2 dB at every seed; group 95% lower bound >0; latency <=1.1. Any valid failed gate STOP; invalid attempts retain reservation. No tuning or retry.

```json
{
  "proposal": {
    "id": "airfoil-a2-strouhal",
    "hypothesis": "Appending the suction-side displacement-thickness Strouhal coordinate f*delta*/U to the original five inputs improves the qualified fixed Extra Trees reference by at least 0.2 dB condition-macro MAE at every paired seed, with positive group-bootstrap lower bound and <=1.1 prediction latency ratio on the untouched final holdout.",
    "mechanism": "airfoil-suction-strouhal-v1",
    "why_new": "This is an Airfoil spectral-coordinate interaction, not the stopped Abalone T1 residual offset or T2 shell-mass composition ratio, and not an image-super-resolution postprocessor. A1 selected a reference without engineered features. This proposal changes a multivariate split coordinate, not constants, model capacity, labels, data splits or success thresholds after a failed Airfoil result. It is an application hypothesis, not a claim that Strouhal scaling is scientifically novel.",
    "limitations": [
      "The literature motivates a coordinate, not a guarantee that appending it improves Extra Trees. Original variables already contain the information.",
      "Additional features alter randomized tree split selection; any benefit cannot be uniquely attributed to acoustic physics without a separate preregistered study.",
      "NASA reports dependence on Reynolds number, Mach number and noise mechanism. One suction-side coordinate is not the complete BPM model or a universal spectral collapse.",
      "Twenty-one proxy condition groups share an apparatus and airfoil family; unknown campaign dependence remains. Public historical data are not contamination-proof.",
      "A1 validation has already selected the reference. It is used only to verify baseline reproduction, never to screen this candidate.",
      "The 0.2 dB adoption margin and 1.1 latency cap are prospective engineering criteria, not established business thresholds. Local monetary costs remain unknown.",
      "One failed or interrupted execution reserves all final holdout groups. No changed constants, log transform, additional features or parameter tuning may rescue this route."
    ],
    "candidate_source": "def augment(row):\n    return row + [row[0] * row[4] / row[3]]\n",
    "evidence": [
      {
        "url": "https://ntrs.nasa.gov/citations/19890016302",
        "title": "Brooks, Pope and Marcolini (1989), Airfoil Self-Noise and Prediction, NASA RP-1218",
        "locator": "Section 5.1.1, printed page 51 / PDF page 59: displacement-thickness peak Strouhal coordinate; original PDF SHA-256 0c22690c6216c4355c0da7e09ce0d1a1dd96a2b88d3d8abda30e293b3db76006, visually checked 2026-11-07",
        "claim": "Frequency scaling uses f*delta*/U, including suction-side displacement thickness; the page also cautions that peak position and spectral shape vary. Using this coordinate as one Extra Trees input is our proposed inference, not a result of the paper."
      },
      {
        "url": "https://scikit-learn.org/1.7/modules/ensemble.html",
        "title": "scikit-learn 1.7.2 user guide: Extremely Randomized Trees",
        "locator": "Section 1.11.2.2, retrieved 2026-11-07",
        "claim": "Extra Trees considers random thresholds for candidate features. A new multivariate coordinate changes available partitions and random split selection; it is not a guaranteed improvement or an implementation of the complete acoustic model."
      }
    ]
  },
  "recipe": {
    "kind": "airfoil-strouhal-trial",
    "version": 1,
    "mechanism": "airfoil-suction-strouhal-v1",
    "seeds": [
      11,
      22,
      33
    ],
    "minimum_effect": 0.2,
    "max_latency_ratio": 1.1,
    "hypothesis": "Append f*delta_suction/U to the five original inputs of qualified Extra Trees; every paired seed gains >=0.2 dB condition-macro MAE on unused holdout, group-bootstrap lower bound >0, latency ratio <=1.1.",
    "controls": [
      "Original A1 training rows only; no validation refit or new split",
      "Exact A1 Extra Trees parameters; 100 trees, seeds 11/22/33, single thread",
      "Only one fixed interaction appended; no scaling, offset, logs, clipping, new objective or tuning",
      "Baseline validation predictions must reproduce saved A1 Extra Trees per seed within 1e-8 before scoring",
      "All 21 real holdout condition groups scored once; labels in controller only"
    ],
    "metric": "Mean per-condition MAE in dB, equal condition weight; report all seeds and variability",
    "bootstrap": {
      "resamples": 10000,
      "seed": 20261107,
      "confidence": 0.95
    },
    "uncertainty": "Bootstrap complete condition groups on seed-averaged paired losses; conditional on fixed training and three paired seeds, not independent campaigns or a proof of generalization",
    "timing": "Five whole-holdout-batch passes per fit, median; candidate includes augmentation and array conversion; seed 22 candidate-first, other seeds baseline-first",
    "minimum_effect_reason": "Prospective engineering adoption margin; not a calibrated business or acoustic perceptual threshold",
    "go": "All seed gains >=0.2 AND group bootstrap lower >0 AND total median batch latency ratio <=1.1; permit a separately reviewed external replication only",
    "stop": "Any valid failed gate closes this mechanism. Do not alter the feature, constants, seeds, model, thresholds or split to rescue it",
    "invalid": "Keep full holdout reservation after worker launch or failure; no automatic retry and no scientific conclusion",
    "limits": {
      "attempts": 1,
      "fits": 6,
      "threads": 1,
      "worker_seconds": 240,
      "output_bytes": 16777216
    },
    "costs": "Record all six fits, train transform, 30 timing passes, wall time, RSS and retained bytes; actual money unknown; no model API calls"
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
  }
}
```
