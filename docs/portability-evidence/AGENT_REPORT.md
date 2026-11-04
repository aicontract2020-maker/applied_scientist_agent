# Autonomous Research Report

## Decision

**STOP.** The registered experiment was valid, but fixed luminance-preserving out-of-gamut chroma compression reduced mean PSNR-Y by **0.085705 dB** versus the fixed two-pass horizontal-flip reference. The 95% paired original-image bootstrap interval was **[-0.118589, -0.056617] dB**, and all 12 observation effects were negative. Although the latency ratio passed its guard, the efficacy result did not meet the preregistered minimum gain of +0.05 dB. This fixed route is abandoned; the result is not grounds to tune its weights, boundary, strength, or spatial behavior.

## Original hypothesis and decision rules

The frozen hypothesis was that replacing independent RGB clipping of out-of-gamut plain SwinIR pixels with deterministic BT.601-luminance-preserving chroma compression would improve frozen Urban100-12 mean paired PSNR-Y by at least +0.05 dB versus the fixed two-pass reference while keeping candidate/reference latency at or below 2.5.

Before registration, outcomes were assigned these meanings:

- Pass: a valid mean gain of at least +0.05 dB and latency ratio no greater than 2.5 would support adopting the candidate.
- Valid negative: missing either threshold would stop and eliminate this fixed route, even if a smaller positive effect looked suggestive.
- Invalid measurement: stop without an efficacy conclusion, report the validity failure, and do not retry.

The experiment returned a valid negative. The success criterion was not changed after observing the result.

## Evidence and rationale

I searched for and read primary literature before proposing or coding the method. I read the full broker-provided text of Le et al., [“GamutMLP: A Lightweight MLP for Color Loss Recovery”](https://arxiv.org/abs/2304.11743), which describes color-fidelity loss from gamut clipping and discusses compression into a target gamut. I also read Milidonis et al., [“Deep chroma compression of tone-mapped images”](https://arxiv.org/abs/2409.16032), whose abstract reports that out-of-gamut tone-mapped pixels can cause chromatic distortion or color-clipping artifacts and motivates chroma compression. Both papers are outside the policy's excluded evidence list.

Those papers concern other imaging domains and do not report this SwinIR intervention. My inference was that channelwise clipping of an out-of-range SwinIR prediction can perturb evaluated luminance, so a constant-luminance gamut mapping might improve PSNR-Y. The negative experiment rejects adoption of this fixed inference on the frozen study; it does not contradict the papers' claims in their own settings.

## Candidate mechanism

For each predicted RGB pixel, the candidate computed BT.601 luminance with weights `[0.299, 0.587, 0.114]`. It expressed RGB as that neutral gray plus chroma displacement, then chose the largest scale `t` in `[0,1]` that put all three channels in `[0,1]`. Thus:

- already-in-gamut pixels were unchanged;
- out-of-gamut chroma was minimally compressed along the line toward neutral gray;
- predicted luminance was preserved whenever it lay in `[0,1]`;
- luminance outside `[0,1]` was mapped to neutral black or white.

This was deterministic, used no training or additional weights, and invoked no additional model forwards. It was distinct from all stopped routes: it used no prediction ensemble, LR/SR residual or backprojection, spatial/frequency shrinkage, or global luminance contrast change. It did not retune parameters from those routes.

## Protocol and controls

The comparator was the existing fixed two-pass horizontal-flip SwinIR-S x2 reference. The candidate received one plain fixed SwinIR-S x2 float32 prediction. Evaluation used the 12 filename-hash-frozen Urban100 x2 pairs and the policy-defined official padding, RGB/uint8 conversion, Y metric, two-pixel border crop, CPU float32 execution, and four reference threads. Constants and code were frozen before real-image inference.

One permitted synthetic shape/finiteness check passed. One candidate was registered under protocol SHA-256 `32e0ca574f2ccd52177884945f67fcbcfb33a0f33a3853c9a2b6f7c882f99087`, and exactly one registered experiment was requested. There were no retries, sweeps, post-result ablations, or changes to `candidate.py` or `research.json` after registration.

## Results

| Quantity | Result |
|---|---:|
| Measurement valid | true |
| Observation count | 12 |
| Fixed-reference mean PSNR-Y | 32.791961 dB |
| Candidate mean PSNR-Y | 32.706256 dB |
| Mean paired gain | -0.085705 dB |
| 95% paired bootstrap interval | [-0.118589, -0.056617] dB |
| Per-image effect standard deviation | 0.057585 dB |
| Images improved / worsened | 0 / 12 |
| Candidate/reference latency ratio | 0.506295 |
| Experiment wall time | 76.539 s |
| Local compute proxy | $0.021261 |
| Actual model/planner billing | unknown (`null`) |

Paired effects in frozen observation order (`img_004`, `img_006`, `img_022`, `img_026`, `img_032`, `img_040`, `img_041`, `img_068`, `img_070`, `img_077`, `img_078`, `img_087`) were:

`[-0.053472, -0.066526, -0.079274, -0.013894, -0.033220, -0.147731, -0.115798, -0.145505, -0.067402, -0.025768, -0.072934, -0.206936] dB`.

The bootstrap used 10,000 resamples, seed 20261103, and 95% confidence. Its scope is original-image sampling variability, not independent training replication or proof against dataset contamination. Seed 0, where used by the controller as an execution identifier, is not a replication.

## Interpretation and limitations

The result is strong evidence against adopting this exact postprocessing route in this fixed study: its interval is wholly below zero, every image worsened, and its mean is 0.135705 dB below the +0.05 dB adoption boundary. Runtime was inexpensive enough, so latency did not cause the failure.

The comparison changes both inference path and postprocessing: plain SwinIR plus gamut compression was compared with a two-pass ensemble. Therefore it does **not** isolate mechanism-specific causality and cannot prove that chroma compression itself caused the loss relative to an otherwise identical plain-output path. No plain-output ablation was authorized or run. The study covers only 12 frozen Urban100 x2 images, one model/configuration, PSNR-Y, and one fixed mapping; it does not establish a worldwide SOTA claim or a general scientific discovery. Relevant unpriced costs include setup time, electricity/depreciation, and long-term artifact retention; actual model billing is unknown and was not fabricated as zero.

## Decision ledger

| Item | Record |
|---|---|
| Hypothesis | Luminance-preserving gamut compression reaches at least +0.05 dB versus the fixed two-pass reference within a 2.5 latency ratio. |
| Protocol | One frozen deterministic candidate; 12 held-out Urban100 x2 pairs; paired PSNR-Y and 10,000-resample original-image bootstrap. |
| Result | Valid; -0.085705 dB, CI [-0.118589, -0.056617], 12/12 worse; latency ratio 0.506295. |
| Conclusion | The efficacy threshold failed; do not adopt or tune this fixed route. |
| Decision | **STOP** |

## Autonomy completion

The complete autonomous cycle was completed: I found and read new external evidence, proposed the falsifiable hypothesis, implemented the candidate, passed the synthetic contract check, preregistered the frozen protocol and stopping rules, requested the single experiment through the file broker, interpreted the valid negative result without changing criteria, and wrote this report. Completion is independent of whether the candidate passed; this negative result is the final research output.
