# Autonomous Research Report — linux-g7-20261104

## Decision

**STOP.** The registered measurement was valid, but the fixed candidate failed the frozen adoption rule. This is a valid negative result, not an operational failure, and there will be no tuning, retry, or post-result ablation.

PASS required all three conjunctive gates: **mean paired PSNR-Y gain >= 0.05 dB AND paired-bootstrap 95% lower confidence bound > 0 AND candidate/reference latency <= 2.5**. A valid failure of any gate means STOP. An invalid measurement would not be scientific evidence.

The observed mean gain was -0.082260 dB, and the lower confidence bound was -0.167954 dB, so the effect and interval gates failed. The latency ratio was 0.491264, so the latency gate passed.

## Original hypothesis

Analytically registering a plain SwinIR prediction to its LR observation by one bounded global subpixel translation would improve frozen Urban100-12 mean paired PSNR-Y by at least 0.05 dB versus the fixed two-pass horizontal-flip reference while keeping candidate/reference latency at or below 2.5 times.

The proposed causal reasoning was that a small global geometric displacement creates first-order luminance error along many architectural edges. This was a falsifiable engineering inference, not a claim made by the cited papers.

## Evidence reviewed before implementation

- Ma et al., [Structure-Preserving Image Super-Resolution](https://arxiv.org/abs/2109.12530), report structural distortions in SR outputs and improvements from explicit gradient/structure guidance in their trained systems. The full broker-provided text was read. This supported examining geometry, but did not establish that the present postprocessor would work.
- Song et al., [Guided Linear Upsampling](https://arxiv.org/abs/2307.09582), report that LR-guided upsampling can preserve detail effects and suppress bleeding/blurring for their tested operators. This supported using LR structure as guidance, but their method and task differ from this experiment.

Both were primary arXiv papers actually read through the broker and both were outside the policy's excluded evidence IDs.

## Registered mechanism

The deterministic candidate:

1. converted LR and plain-SR RGB to BT.601 luminance;
2. reduced SR luminance to LR dimensions with area interpolation;
3. estimated one global translation by Hann-windowed phase correlation;
4. converted that estimate to HR units, bounded each axis to 0.5 HR pixel, and set it to zero when correlation response was below 0.10; and
5. applied the accepted translation jointly to RGB with bilinear interpolation and reflected borders.

This was not a prediction ensemble, LR-residual backprojection, frequency shrinkage or sharpening, luminance contrast expansion, gamut/chroma compression, additive 2x2 phase-bias removal, RGB lattice selection, or clip-only operation. It did not retune a stopped route. It can observably change final uint8 output because subpixel interpolation changes edge samples across quantization thresholds.

The comparator remained the stronger existing fixed two-pass horizontal-flip SwinIR-S x2 reference. The candidate received only the single plain SwinIR output. Because the compared paths also differ in one versus two model forwards, this experiment does **not** isolate translation-specific causality.

## Results

| Quantity | Result |
|---|---:|
| Measurement valid | true |
| Observation count | 12 |
| Reference mean PSNR-Y | 33.019171 dB |
| Candidate mean PSNR-Y | 32.936911 dB |
| Mean paired gain | -0.082260 dB |
| Paired effect standard deviation | 0.142545 dB |
| Paired-bootstrap 95% interval | [-0.167954, -0.013797] dB |
| Candidate/reference latency ratio | 0.491264 |
| Experiment wall time | 54.455813 s |
| Local machine-hour proxy | $0.015127 |
| Actual model billing | unknown / not reported |

Paired effects in frozen observation order were:

`[-0.034280, -0.049554, 0.018927, -0.051263, -0.132252, -0.460078, -0.182843, 0.049248, -0.060900, 0.096608, -0.133375, -0.047359]` dB.

Three of twelve paired effects were positive and nine were negative. The bootstrap interval describes original-image sampling variability; seed 0 is not an independent training replication.

## Interpretation and route decision

The hypothesis was false under the frozen test. The negative mean and wholly negative 95% interval provide evidence against this exact one-shot global phase-correlation registration route, despite its acceptable latency.

The stopped route is: image-global phase-correlation registration of plain SR to area-reduced LR luminance using the registered Hann window, 0.10 response guard, 0.5-HR-pixel per-axis bound, bilinear warp, and reflected border. This result does not justify changing the guard, displacement cap, window, interpolation, estimator, or adding local/adaptive registration complexity.

## Limitations and unknowns

- The study contains twelve frozen Urban100 x2 images; it is not evidence of worldwide SOTA performance or universal failure on other datasets, scales, models, or degradations.
- The comparison changes both postprocessing and the number of model forwards, so it cannot attribute the loss solely to the geometric warp.
- No plain-output ablation was permitted after the result.
- The confidence interval captures original-image sampling variability, not training replication or proof against dataset contamination.
- Dollar model billing was not supplied. The local compute amount is a proxy, not an invoice, and setup time, electricity, depreciation, and long-term artifact retention remain unpriced.

## Workflow completion

The autonomous cycle was completed without human coding or execution: external evidence was searched and read through the broker; one hypothesis and one distinct candidate were authored; the code passed a single synthetic shape/finiteness check; the candidate and plan were preregistered and frozen; the sole allowed experiment was requested through `labctl.py`; its valid result was interpreted under the unchanged three-gate rule; and this report was written. Scientific success was not required for workflow completion; the valid negative changed the decision from proposed adoption to abandonment of the registered route.
