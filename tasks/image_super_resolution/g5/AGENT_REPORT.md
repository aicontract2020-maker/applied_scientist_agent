# Autonomous Research Report: BT.601-Aware RGB Lattice Selection

## Decision

**STOP.** The registered experiment was valid, but the fixed candidate failed the preregistered effect criterion. Mean paired PSNR-Y gain versus the fixed two-pass horizontal-flip reference was **−0.100211 dB**, below the required **+0.05 dB**. The 95% paired original-image bootstrap interval was **[−0.128332, −0.075891] dB**. All 12 image-level effects were negative. Latency passed its separate guard at **0.507459×** the reference, but low latency cannot compensate for the failed quality gate.

This valid negative eliminates the preregistered route: fixed per-pixel selection among the eight enclosing 8-bit RGB lattice corners by minimum BT.601-luminance displacement, with RGB-distance tie-breaking. It does not justify changing weights, enlarging the lattice neighborhood, adding adaptive logic, or retrying on this holdout.

## Original hypothesis and rationale

The frozen hypothesis was that choosing, for every plain SwinIR pixel, the corner of its enclosing 8-bit RGB lattice cell whose BT.601 luminance is closest to the continuous prediction would improve frozen Urban100-12 mean paired PSNR-Y by at least 0.05 dB versus the fixed two-pass reference, while remaining at or below 2.5× reference latency.

The engineering premise was that ordinary independent channel rounding need not choose the nearby RGB lattice point that best preserves the continuous model's luminance. If the continuous prediction were locally informative about target luminance, reducing its displacement during quantization might preserve useful information. This premise was an inference, not a claim made by the cited papers.

Two primary papers were read through the broker before the proposal. Mei et al., [*Improving Image Restoration with Soft-Rounding*](https://arxiv.org/abs/1508.05046), treat digital pixel values as discrete and report restoration gains from a soft-rounding prior, while warning that naive post-rounding can destroy recovered structure. Li et al., [*PAMS: Quantized Super-Resolution via Parameterized Max Scale*](https://arxiv.org/abs/2011.04212), report that quantization handling affects SR quality in trained quantized networks. Neither paper tests this postprocessor, SwinIR output lattice selection, or this benchmark; their results were only motivation for testing quantization sensitivity.

## Frozen implementation

For each clipped plain-SwinIR RGB pixel, `candidate.py`:

1. Scaled the float pixel to the 8-bit domain.
2. Enumerated the eight Cartesian combinations of each channel's floor and ceiling.
3. Selected the corner minimizing absolute luminance displacement from the continuous pixel, using fixed BT.601 weights `(0.299, 0.587, 0.114)`.
4. Broke luminance-error ties by minimum squared RGB displacement, then by fixed enumeration order.
5. Returned the selected RGB point as float32 in `[0,1]`.

The function was deterministic, used no training or additional weights, made no model calls, and passed the permitted synthetic shape/finiteness check. It used only the plain prediction; the LR argument was not used.

The candidate is mechanistically distinct from all stopped routes. It does not ensemble predictions, backproject an LR/SR residual, attenuate or amplify spatial frequencies, alter global or local contrast, perform luminance-preserving gamut compression, or estimate/remove a phase-locked bias. It does not retune any stopped parameter or reuse the local Linux-validation route.

## Preregistered interpretation

- **Pass:** mean paired gain at least +0.05 dB and latency no more than 2.5× the reference; adopt this fixed candidate.
- **Valid negative:** a valid experiment misses either gate; stop this exact route without tuning or retry.
- **Invalid:** controller/evaluator validity failure; make no scientific decision, report the failure, and do not rescue or rerun.

One candidate was registered under protocol SHA-256 `7ff0a4af4d1cbc32868b310399a87d2e81f74293ea0003a09a73c7837ce92c85`. No candidate or plan files were changed after registration, and only one registered run was requested.

## Results

| Quantity | Result |
|---|---:|
| Measurement valid | Yes |
| Observation count | 12 |
| Fixed-reference PSNR-Y | 32.155222 dB |
| Candidate PSNR-Y | 32.055011 dB |
| Mean paired gain | −0.100211 dB |
| 95% paired bootstrap CI | [−0.128332, −0.075891] dB |
| Across-image effect SD | 0.048821 dB |
| Images improved / worsened | 0 / 12 |
| Candidate/reference latency ratio | 0.507459× |
| Experiment wall time | 46.4685 s |
| Local compute proxy | $0.012908 |
| Actual model/planner billing | Unknown (`null`) |

Paired effects in frozen observation order (`img_005`, `img_017`, `img_019`, `img_031`, `img_033`, `img_036`, `img_042`, `img_046`, `img_058`, `img_091`, `img_094`, `img_095`) were:

`−0.211012, −0.117418, −0.146312, −0.066794, −0.086442, −0.106662, −0.044311, −0.117450, −0.134037, −0.062537, −0.049364, −0.060194 dB`.

The bootstrap used 10,000 resamples, seed 20261103, and paired original-image sampling. Seed 0, where applicable in execution, is not an independent training replication.

## Interpretation and limitations

The candidate was faster because it used one model forward plus inexpensive array operations, while the comparator used the fixed two-pass reference. Nevertheless, it produced substantially lower PSNR-Y on every evaluated image. Under the frozen decision rule, the hypothesis is false for this candidate and evaluation.

The comparison changes both inference count and postprocessing: plain single-pass plus lattice selection is compared with a two-pass flip reference. Therefore, the observed −0.100211 dB must **not** be interpreted as the isolated causal harm of lattice selection. It could include the single-versus-double-forward difference, the postprocessor's effect, and their interaction. No post-result plain-output ablation was permitted or performed.

This is one frozen 12-image Urban100 x2 study with one model/configuration. The confidence interval describes original-image sampling variability under the specified bootstrap; it is not training replication, a contamination audit, or evidence about all datasets and SR systems. Dollar billing was unavailable and was not fabricated. The local proxy excludes setup time, electricity/depreciation, and long-term artifact retention. No worldwide SOTA or novel-discovery claim is made.

## Workflow completion

The autonomous cycle was completed end to end: primary evidence was searched and broker-read; one distinct hypothesis was proposed; `candidate.py` and `research.json` were authored; the implementation passed the allowed synthetic check; pass/negative/invalid meanings were stated; the candidate was preregistered; the sole experiment was requested through `labctl.py`; its valid result was interpreted against the frozen gates; and this report records the final STOP decision. A negative outcome is still a completed autonomous research cycle.
