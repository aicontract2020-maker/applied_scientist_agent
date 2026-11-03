# Autonomous G2 Research Report

## Decision

**STOP.** The registered gain-0.20, one-step cubic LR-residual back-projection route produced a valid mean paired PSNR-Y effect of **-0.147327 dB** versus the fixed two-pass horizontal-flip reference. This is below the frozen **+0.05 dB** adoption threshold. Its 95% paired original-image bootstrap interval was **[-0.215344, -0.091999] dB**. Although latency passed its guard, the quality criterion failed; the exact route is abandoned without retuning.

The full autonomous workflow was completed: I proposed the hypothesis, authored the candidate and protocol, ran a synthetic contract check, preregistered both artifacts, requested the sole registered experiment through the broker, interpreted its result under the frozen rule, and wrote this report. Success of the candidate was not required for workflow completion.

## Preregistered hypothesis and decision rule

The falsifiable hypothesis was that, across all 14 frozen original Set14 x2 pairs, one conservative cubic back-projection correction with gain 0.20 applied to plain SwinIR-S would improve mean paired PSNR-Y by at least 0.05 dB versus the existing fixed two-pass horizontal-flip reference, while keeping the candidate/reference latency ratio at or below 2.5.

Adoption required the frozen quality threshold and latency guard to pass. A valid quality miss or latency violation meant STOP. No criterion was changed after seeing the result. The protocol was registered with SHA-256 `bea4075e77458cc8a345b73835eafc003252893d15b54c8d5ab1052b67b8fa5c`.

## Candidate mechanism

The candidate accepted only the LR RGB image and the plain, unensembled float32 SwinIR prediction. It:

1. Cubically resized the SR prediction to the exact LR dimensions.
2. Computed the channelwise float32 residual `LR - predicted_LR`.
3. Cubically resized this residual to the SR dimensions.
4. Added 20% of the lifted residual once, without clipping.

The causal idea was observation consistency: if cubic reduction of the externally trained model's output did not reproduce the observed LR image, a conservative signed residual correction might repair low-frequency mismatch while retaining learned high-frequency detail. Gain 0.20 was selected before evaluation as an under-relaxed step; there was no sweep, training, stochasticity, iteration, or post-outcome alternative.

This was not a G1 retry. G1 used a second horizontally transformed model forward and averaged predictions. This candidate used one plain model output, no flip or ensemble, and an explicit LR-residual correction. The rejected G1 route was used only as the required stronger comparator and was not reopened.

## External evidence and inference boundary

The supplied primary paper [Plug-and-Play Image Restoration with Deep Denoiser Prior](https://arxiv.org/abs/2008.13751) supports the general idea that learned priors can be combined with explicit observation models. The supplied primary paper [Super-Resolution via Image-Adapted Denoising CNNs](https://arxiv.org/abs/1811.12866) supports the relevance of input-image information and observation-model mismatch in SR. Both use substantially richer learned or iterative procedures. Neither paper establishes that this cheap fixed correction should improve SwinIR; the one-step postprocessing mechanism was my inference and the object of this test.

## Protocol and controls

- Evaluation set: all 14 frozen original Set14 x2 pairs (`img_001` through `img_014`), previously unscored in these runs.
- Primary metric: mean paired PSNR-Y gain in dB versus the fixed two-pass reference; higher is better.
- Minimum meaningful effect: +0.05 dB absolute.
- Uncertainty: paired bootstrap over original images, 10,000 resamples, seed 20261103, 95% interval.
- Latency guard: candidate/reference ratio no greater than 2.5.
- Execution controls: CPU float32, four reference threads, same weights, official padding, RGB/uint8 conversion, Y metric, and border crop 2.
- Prohibitions honored: no training, extra weights, candidate model forwards, sweep, repeated holdout access, or retry.

One broker synthetic check passed shape and finiteness before registration. It exposed no real-image score and was not used as evidence or for algorithm selection. The code and plan were not changed after registration.

## Results

| Measure | Result |
|---|---:|
| Measurement valid | Yes |
| Observations | 14 |
| Fixed two-pass baseline PSNR-Y | 33.937128 dB |
| Candidate PSNR-Y | 33.789800 dB |
| Mean paired gain | -0.147327 dB |
| Effect standard deviation across images | 0.123512 dB |
| 95% paired-bootstrap interval | [-0.215344, -0.091999] dB |
| Latency ratio | 0.496211 |
| Experiment wall time | 71.4077 s |
| Local compute proxy | $0.0198355 |
| Actual planner/model billing | Unknown (`null`) |

Paired effects in registered observation order were:

`[-0.047432, -0.269035, -0.037007, -0.115155, -0.150520, -0.037267, -0.174935, -0.195180, -0.084713, -0.050087, -0.251499, -0.062996, -0.481981, -0.104777] dB`.

All 14 effects were negative. The bootstrap interval describes original-image sampling variability; this single deterministic evaluation is not independent training replication and does not prove anything about dataset contamination.

## Interpretation

The measurement passed validity checks, so the negative result cannot be treated as an operational failure. The candidate was inexpensive enough: its latency ratio of 0.496 was comfortably within 2.5. Quality nevertheless failed by 0.197327 dB relative to the minimum adoption effect, and even the upper bootstrap endpoint remained negative. Under the preregistered rule, this eliminates the fixed gain-0.20, one-step cubic downsample/residual/cubic-upsample route.

A plausible retrospective explanation is that the cubic reduction used by the postprocessor was not the evaluator's exact observation operator and/or that the residual included components SwinIR had already handled more effectively; lifting it degraded the quantized Y reconstruction. This is an interpretation generated after the result, not confirmation of a preregistered causal sub-hypothesis and not grounds for a retry. I will not tune gain, interpolation, or step count on this holdout.

## Costs, limitations, and scope

The controller reported 71.4077 experiment wall-seconds and a $0.0198355 local machine-hour proxy. That proxy is not an invoice. Actual planner/model billing is unknown, and setup time, electricity, depreciation, and long-term artifact retention remain unpriced.

This is one bounded Set14 x2 comparison against a stronger existing inference reference within frozen weights. It is not an exhaustive global SR comparison, a worldwide SOTA claim, or evidence of a new scientific discovery. The sample contains 14 images, the uncertainty interval covers only paired original-image sampling, and the test addresses only the exact frozen candidate.

## Decision ledger

| Item | Record |
|---|---|
| Hypothesis | One gain-0.20 cubic LR-residual correction to plain SwinIR reaches at least +0.05 dB versus fixed two-pass flip reference with latency ratio at most 2.5. |
| Strongest baseline | Existing fixed two-pass horizontal-flip SwinIR-S x2 reference. |
| Protocol | 14 frozen Set14 pairs; paired PSNR-Y; 10,000-image bootstrap; one deterministic registered run. |
| Result | Valid -0.147327 dB; 95% CI [-0.215344, -0.091999]; latency 0.496211x. |
| Conclusion | Quality hypothesis falsified for the fixed candidate; latency alone passed. |
| Decision | **STOP** this route; no rescue, retuning, or repeat holdout access. |
