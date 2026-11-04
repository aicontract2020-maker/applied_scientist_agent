# Autonomous G3 research report

## Decision

**STOP.** The measurement was valid, but the frozen candidate reduced mean paired PSNR-Y by **0.09781 dB** relative to the stronger fixed two-pass horizontal-flip SwinIR reference. Its 95% paired original-image bootstrap interval was **[-0.13719, -0.06009] dB**, wholly below zero and far below the predeclared **+0.05 dB** minimum effect. The latency ratio, **0.50303x**, passed the **2.5x** guard but cannot rescue the failed accuracy criterion.

This valid negative result eliminates the fixed weak-luminance-high-pass shrinkage route tested here (3x3 Gaussian sigma 0.55, threshold 1/255, maximum shrinkage 25%, exponential gate). I will not tune its threshold, strength, kernel, scale, or gate using this holdout.

## Original hypothesis and decision rule

Before registration, I hypothesized that smoothly attenuating by 25% only plain SwinIR luminance high-pass coefficients below approximately one 8-bit code value would improve frozen Urban100-12 mean paired PSNR-Y by at least +0.05 dB versus the fixed two-pass flip reference, while keeping latency no greater than 2.5x reference.

The primary metric, observations, controls, minimum effect, latency guard, and 10,000-resample paired-image bootstrap (seed 20261103, 95% confidence) were copied from `policy.json` into `research.json`. Plausible outcomes were mapped in advance:

- Effect meeting +0.05 dB, supported by the paired bootstrap and passing the latency guard: CONTINUE/adopt exactly the frozen candidate.
- Effect or interval failing the accuracy threshold, or latency exceeding 2.5x: STOP the exact route without tuning.
- Invalid execution: stop without a scientific conclusion or retry.

## Evidence and mechanism

I performed native web search and read two primary papers through the broker before proposing or coding:

- Liang et al., [SwinIR: Image Restoration Using Swin Transformer](https://arxiv.org/abs/2108.10257), full-text read (broker returned the declared first 40,000 extracted characters and marked it truncated). The authors describe shallow features as mainly carrying low frequencies and deep features as recovering lost high frequencies. They also distinguish self-ensemble as SwinIR+. This is the paper's claim; the postprocessing hypothesis was my inference.
- Fritsche, Gu, and Timofte, [Frequency Separation for Real-World Super-Resolution](https://arxiv.org/abs/1911.07850), abstract read. The authors report treating low and high frequency components differently in a trained real-world SR pipeline. Their setting and method differ from this study; using band separation to motivate weak-coefficient shrinkage was my inference.

The candidate converted the plain SR output to Rec.601 luminance, computed a 3x3 Gaussian low-pass with sigma 0.55, and formed a luminance high-pass. It subtracted `0.25 * high * exp(-(high/(1/255))^2)` equally from all RGB channels. The smooth gate was intended to attenuate sub-code-value fluctuations while leaving strong edges nearly unchanged and avoiding hue shifts.

This mechanism is genuinely distinct from both stopped routes. It used one plain SwinIR prediction, not G1's multiple transformed predictions or any prediction average. It did not retune flip transforms. It did not downsample SR, compare LR against SR, or inject an LR discrepancy, so it is not G2's stopped LR-versus-SR residual-backprojection family and retunes none of its gains, kernels, or iterations. The `lr` argument was deliberately unused.

## Protocol and implementation checks

`candidate.py` and `research.json` were authored before any held-out inference. One allowed synthetic `labctl.py check` passed array shape and finiteness; it returned no real-image score and was not used to choose parameters. Registration then froze both files under protocol SHA-256:

`6bbcb1bd2ae8e70174ec3e811c23c0b0facc5c91c3e360e1a4d2c76f30d1cf74`

Exactly one registered experiment was requested. No code or protocol file was changed after registration, and there was no retry.

## Results

| Quantity | Result |
|---|---:|
| Measurement validity | true |
| Observation count | 12 |
| Fixed flip-reference PSNR-Y | 32.75534 dB |
| Candidate PSNR-Y | 32.65753 dB |
| Mean paired gain | -0.09781 dB |
| Across-image effect standard deviation | 0.07198 dB |
| 95% paired bootstrap interval | [-0.13719, -0.06009] dB |
| Candidate/reference latency ratio | 0.50303x |
| Experiment wall time | 52.98460 s |
| Local compute proxy | $0.01472 |

Per-image paired effects in frozen observation order (`img_010`, `img_014`, `img_020`, `img_047`, `img_048`, `img_052`, `img_065`, `img_076`, `img_080`, `img_090`, `img_093`, `img_098`) were:

`[-0.09684, -0.04640, -0.06972, -0.16661, -0.19494, -0.10861, -0.03745, -0.04058, -0.20580, -0.17349, +0.01334, -0.04662] dB`.

Eleven of twelve images worsened. The sole positive effect was +0.01334 dB, itself below the aggregate adoption threshold and not a basis for post-hoc subgroup selection.

## Interpretation

The causal prediction was falsified in this setting. Weak luminance high-pass coefficients from the fixed SwinIR-S x2 output were not, on average, disposable noise relative to the stronger flip reference. Attenuating them harmed PSNR-Y consistently despite preserving larger edges. Because both the mean and the full paired-bootstrap interval are negative, this is not a near-threshold result. The candidate is computationally cheap, but lower latency alone has no adoption value under the frozen conjunctive rule.

The bootstrap measures sampling variability across the 12 original images; it is not training replication, an independent model seed, or proof against dataset contamination. Seed 0, if used by execution infrastructure, is only an execution identifier. This deterministic candidate involved no stochastic training or inference.

## Costs, unknowns, and limitations

- The controller reported $0.01472 as the local machine-hour proxy for the experiment. This is not an invoice.
- Actual planner/model billing is unknown (`null`), not zero. Setup time, electricity, depreciation, and long-term artifact retention remain unpriced.
- Only 12 hash-frozen Urban100 x2 images, one fixed SwinIR-S model, one scale, and PSNR-Y were evaluated. Generalization to other datasets, scales, models, perceptual metrics, or subjective quality was not tested.
- The comparison is the fixed two-pass flip reference within frozen weights, not an exhaustive global SR state-of-the-art comparison.
- The experiment cannot separately identify whether harm arose from suppressing true detail, the luminance/high-pass definition, or interactions with final quantization. The preregistered decision nevertheless stops the tested route rather than adding complexity after failure.
- Two attempted broker full-text reads of other primary papers failed the broker's declared download-size limit. They supplied no usable evidence and did not alter the hypothesis. The successful SwinIR full-text read satisfied the mandatory full-read requirement.

## Decision ledger

| Item | Record |
|---|---|
| Hypothesis | Weak, sub-code-value luminance high-pass shrinkage beats fixed flip-reference PSNR-Y by at least +0.05 dB within 2.5x latency. |
| Protocol | One deterministic plain-SwinIR postprocessor; frozen Urban100-12; paired 10,000-resample bootstrap; one registered run. |
| Result | -0.09781 dB mean; 95% CI [-0.13719, -0.06009]; 0.50303x latency; valid measurement. |
| Conclusion | Accuracy hypothesis false for this fixed candidate; latency guard passed but adoption rule failed. |
| Decision | **STOP** the fixed weak-high-pass shrinkage route; no rescue tuning or holdout reuse. |

The requested autonomous cycle was completed end to end: I found and read evidence, proposed the falsifiable hypothesis, implemented the candidate, performed the synthetic contract check, preregistered the protocol and stopping rule, requested the sole broker experiment, interpreted the valid negative result without changing criteria, and wrote this report. Completion is independent of the candidate's failure to meet the adoption threshold.
