# Autonomous research report: 2×2 phase-bias correction

## Decision

**STOP.** The one registered experiment was valid, but the fixed candidate reduced mean PSNR-Y by **0.121580 dB** relative to the fixed two-pass horizontal-flip reference. Its 95% paired original-image bootstrap interval was **[-0.169112, -0.082569] dB**, and all 12 observations were negative. Although the latency ratio of **0.5031×** passed the preregistered maximum of 2.5×, the quality result did not meet the required **+0.05 dB** effect.

This eliminates the preregistered route: fixed image-global median estimation and full removal of a zero-sum additive 2×2 luminance phase bias from plain SwinIR output. There will be no tuning, retry, post-result ablation, alternative estimator, strength change, alignment change, or adaptive extension in this cycle.

## Original hypothesis and rationale

The frozen hypothesis was that removing a robustly estimated constant 2×2 phase-locked luminance bias from each plain SwinIR prediction would improve frozen Urban100-12 mean paired PSNR-Y by at least 0.05 dB versus the fixed two-pass reference while keeping latency at or below 2.5× reference.

The external evidence supported the possibility of a distinct artifact mechanism, not this candidate's effectiveness:

- Aitken et al., [Checkerboard artifact free sub-pixel convolution](https://arxiv.org/abs/1707.02937), describe sub-pixel convolution as independently filtered low-resolution output groups periodically shuffled into high-resolution phases and show that phase filter differences can produce checkerboard artifacts in SR.
- Sugawara et al., [Super-Resolution using Convolutional Neural Networks without Any Checkerboard Artifacts](https://arxiv.org/abs/1806.02658), report checkerboard artifacts in CNN super-resolution and derive architectural conditions intended to avoid them.

My inference was that a trained plain SwinIR prediction might retain a small image-wide additive phase component that could be estimated without HR access. Neither paper tested this postprocessor or established that SwinIR has such a correctable bias.

## Frozen method

`candidate.py` computed BT.601 luminance from the plain float32 SwinIR output, divided the output into origin-aligned non-overlapping 2×2 cells, and calculated each phase's median luminance residual from its cell mean. It centered the four phase estimates to zero sum and subtracted each full phase offset equally from R, G, and B. The shared RGB correction targeted luminance while preserving channel differences. The ×2 period, origin, luminance weights, median estimator, zero-sum centering, and gain 1.0 were frozen before held-out inference.

The candidate did not use the LR image in its calculation, prediction ensembles, additional model forwards, LR residual backprojection, weak high-frequency shrinkage, global luminance contrast expansion, or luminance-preserving gamut compression. It did not retune any historical stopped route.

## Protocol and result

The stronger comparator was the existing fixed two-pass horizontal-flip SwinIR-S ×2 reference; the candidate path was one plain SwinIR-S prediction followed by the deterministic array function. Evaluation used the 12 frozen Urban100 ×2 observations and the policy's fixed CPU, conversion, Y-metric, crop, bootstrap, and no-retry controls.

| Quantity | Result |
|---|---:|
| Measurement valid | Yes |
| Observations | 12 |
| Reference mean PSNR-Y | 33.628299 dB |
| Candidate mean PSNR-Y | 33.506719 dB |
| Mean paired gain | -0.121580 dB |
| 95% paired bootstrap CI | [-0.169112, -0.082569] dB |
| Per-image wins / losses | 0 / 12 |
| Effect standard deviation | 0.081866 dB |
| Latency ratio | 0.503138× |
| Experiment wall time | 51.585 s |
| Local compute proxy | $0.014329 |

Paired effects in frozen observation order were: -0.081028, -0.112681, -0.056159, -0.078386, -0.082305, -0.068136, -0.051381, -0.099708, -0.321218, -0.212739, -0.204738, and -0.090482 dB.

The bootstrap interval represents original-image sampling variability. Seed 0 is only an execution identifier, not a training replication.

## Interpretation and limitations

The observed candidate pipeline is worse than the fixed two-pass reference on every held-out image, and the interval lies wholly below zero. The inexpensive correction therefore offers no adoption case under the frozen criterion.

This comparison changes two things at once: the candidate uses a single forward plus postprocessing, whereas the reference uses two forwards with flip averaging. Consequently, it does **not** isolate the causal effect of phase correction from the single-versus-double-forward difference. In particular, the result does not prove that subtracting phase offsets would harm the same plain output relative to an unprocessed plain-output ablation, nor does it estimate whether a phase artifact exists. It only supports the operational STOP decision for the complete frozen candidate against the required stronger reference. The 12-image result is narrow, dataset-specific evidence and is neither a worldwide SOTA claim nor a new scientific discovery.

Actual model-service billing remains unknown (`null`). The local machine-hour proxy is not an invoice and excludes setup time, electricity, depreciation, and long-term artifact retention.

## Workflow completion

The autonomous cycle was completed end to end: external primary literature was searched and read through the broker (two papers, one in full); one distinct hypothesis and implementation were authored; the candidate passed the allowed synthetic shape/finiteness check; decision meanings and all constants were preregistered; exactly one experiment was registered and requested; its valid result was interpreted against the frozen thresholds; and this report was written. The negative result changes the decision from test to abandonment of the exact registered route, so the scientific cycle is complete despite non-adoption.
