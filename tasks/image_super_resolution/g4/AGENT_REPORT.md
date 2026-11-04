# Autonomous G4 Research Report

## Outcome

**STOP.** The registered image-global luminance contrast expansion produced a valid mean paired PSNR-Y gain of **-0.11954 dB** versus the fixed two-pass horizontal-flip reference. Its 95% paired original-image bootstrap interval was **[-0.15018, -0.09225] dB**. All 12 observation effects were negative. Although the latency ratio of **0.5131** satisfied the frozen maximum of 2.5, the quality effect did not reach the preregistered minimum of +0.05 dB.

The complete autonomous workflow was completed: external evidence search and broker reading, hypothesis selection, implementation, synthetic checking, preregistration, the single registered experiment request, result interpretation, and this report. Completion does not depend on a positive result.

## Original hypothesis and decision rule

The frozen hypothesis was that expanding plain SwinIR's image-global luminance deviations about its predicted mean by 0.5% would counter conditional-mean contrast attenuation and improve the frozen Urban100-12 mean paired PSNR-Y by at least +0.05 dB versus the fixed two-pass horizontal-flip reference, while keeping candidate/reference latency at or below 2.5.

Before registration, the outcomes were assigned these meanings:

- Pass: adopt/CONTINUE only if the valid mean gain was at least +0.05 dB and latency ratio was at most 2.5.
- Valid negative: STOP the route if either threshold failed, even for a smaller positive gain.
- Invalid measurement: make no efficacy inference and stop without retry, tuning, or a replacement candidate.

The observed result is a valid negative. The criterion was not changed after seeing it.

## Evidence and rationale

Two primary papers were read through the file broker before proposing or coding the candidate. The full text of Dahl, Norouzi, and Shlens, [*Pixel Recursive Super Resolution*](https://arxiv.org/abs/1702.00783), describes pixel-independent Gaussian/MSE SR as conditional-mean prediction and analyzes how averaging multimodal outcomes yields blurry results. Sajjadi, Schölkopf, and Hirsch, [*EnhanceNet*](https://arxiv.org/abs/1612.07919), reports that optimizing pixel-wise reconstruction measures tends to produce over-smoothed SR images lacking high-frequency texture. Both IDs are outside the policy's excluded evidence list.

Those papers did **not** claim that a global contrast expansion improves SwinIR or PSNR. The tested mechanism was my inference: if conditional averaging mildly attenuates luminance amplitude, a small global point transform might correct it. The experiment falsified the adoption-level engineering claim on this frozen study; it does not refute the papers.

## Candidate mechanism

For the one plain, unensembled SwinIR float32 prediction, the candidate:

1. computed luma as `0.299 R + 0.587 G + 0.114 B`;
2. computed one arithmetic mean luma over the full prediction;
3. added `0.005 * (luma - mean_luma)` equally to R, G, and B; and
4. returned float32 without candidate-side clipping, leaving quantization to the trusted adapter.

Equal-channel adjustment preserves RGB channel differences. The fixed gain was chosen as a deliberately mild calibration for an already strong distortion-trained model, not from holdout measurements. The operation did not use the LR array, spatial filtering, parameter search, training, extra weights, randomness, or another model forward.

This mechanism is distinct from all stopped routes. It uses no prediction ensemble or transformed forward (G1), no LR-versus-downsampled-SR residual or backprojection (G2), and no blur, local high-frequency gate, or attenuation (G3). Therefore it neither reopens nor retunes those routes. Because the candidate and comparator differ in several respects, this result also does not isolate a mechanism-specific causal effect relative to plain SwinIR.

## Protocol and results

The comparator was the existing fixed two-pass horizontal-flip SwinIR-S x2 reference. The candidate was one plain fixed SwinIR-S x2 prediction plus the registered deterministic function. Evaluation used the 12 frozen, fresh Urban100 x2 observation IDs, the fixed CPU/threading, padding, RGB/uint8, Y-metric, and border-crop controls, and 10,000 paired original-image bootstrap resamples with seed 20261103 at 95% confidence.

| Quantity | Result |
|---|---:|
| Measurement valid | yes |
| Observations | 12 |
| Reference mean PSNR-Y | 31.91894 dB |
| Candidate mean PSNR-Y | 31.79940 dB |
| Mean paired gain | -0.11954 dB |
| Effect standard deviation across images | 0.05377 dB |
| 95% paired bootstrap interval | [-0.15018, -0.09225] dB |
| Candidate/reference latency ratio | 0.51310 |
| Experiment wall time | 54.8813 s |

Paired effects in frozen observation order (`img_001`, `img_002`, `img_021`, `img_028`, `img_037`, `img_057`, `img_062`, `img_067`, `img_084`, `img_088`, `img_089`, `img_099`) were:

`[-0.11182, -0.13068, -0.07065, -0.21453, -0.07530, -0.13184, -0.07456, -0.22056, -0.10611, -0.05690, -0.09109, -0.15048] dB`.

The bootstrap interval represents original-image sampling variability, not independent training replication and not proof against dataset contamination. Seed 0, where used by execution, is an execution identifier rather than an independent stochastic replicate; the candidate itself is deterministic.

## Costs and limitations

The controller reported a local compute proxy of **$0.0152448** at the policy's $1 per machine-hour proxy. This is not an invoice. Actual planner/model billing is **unknown** (`null`), not zero. Setup time, electricity and depreciation, and long-term artifact retention remain unpriced. Candidate latency excludes any broader human or planning cost.

The study has only 12 frozen Urban100 images and one architecture/scale/protocol, so it does not establish a universal statement about global contrast transformations. The reference is a stronger existing inference configuration within fixed weights, not an exhaustive global SR SOTA comparison. PSNR-Y does not by itself establish perceptual quality. No HR images or hidden repository data were inspected by the agent, and no benchmark labels were fetched. There was no post-result ablation, parameter tuning, or retry.

## Decision ledger

| Item | Record |
|---|---|
| Hypothesis | Fixed 0.5% global luma-deviation expansion beats the fixed two-pass reference by at least +0.05 dB within 2.5× latency. |
| Protocol | One preregistered deterministic candidate; frozen Urban100-12 paired PSNR-Y; 10,000-image bootstrap; fixed controls. |
| Result | -0.11954 dB, 95% CI [-0.15018, -0.09225]; latency 0.5131×; valid measurement; 12/12 effects negative. |
| Conclusion | The fixed candidate fails the quality threshold despite passing latency. |
| Decision | **STOP** image-global luminance contrast expansion as a route under this protocol. Do not rescue it by tuning the gain or adding adaptive/local contrast complexity. |

