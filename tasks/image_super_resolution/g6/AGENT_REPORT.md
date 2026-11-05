# Autonomous Research Report: Valid-RGB Box Projection

## Decision

**STOP.** The registered measurement was valid, but the fixed candidate failed two of the three conjunctive adoption gates. Adoption required mean paired PSNR-Y gain **>= 0.05 dB AND** paired-bootstrap 95% lower confidence bound **> 0 AND** candidate/reference latency **<= 2.5**. The observed mean gain was -0.069621 dB, the lower bound was -0.107382 dB, and the latency ratio was 0.494207. Thus the latency gate passed, while the minimum-effect and positive-lower-bound gates failed. Per preregistration, failure of any gate means STOP without tuning or retry.

## Original hypothesis

Projecting every channel of the plain SwinIR float32 prediction onto the closed valid RGB interval [0,1] would improve frozen Urban100-12 mean paired PSNR-Y by at least 0.05 dB versus the fixed two-pass horizontal-flip reference while keeping candidate/reference latency at or below 2.5 times.

## Evidence and rationale fixed before the run

Takeyama, Ono, and Kumazawa, [A Constrained Convex Optimization Approach to Hyperspectral Image Restoration with Hybrid Spatio-Spectral Regularization](https://arxiv.org/abs/1907.13357), formulate restoration with a hard image-dynamic-range constraint and explicitly realize its metric projection by componentwise clipping. This was newly read primary evidence outside the policy's excluded evidence IDs. The paper studies hyperspectral restoration, not this SwinIR comparison; transferring its feasible-set idea to RGB SISR was my inference.

Lim et al., [Enhanced Deep Residual Networks for Single Image Super-Resolution](https://arxiv.org/abs/1707.02921), provide primary evidence for direct RGB residual-network reconstruction in the relevant SISR setting. They do not claim that post-hoc clipping beats prediction ensembling; that hypothesis was my inference.

The candidate's mechanism was Euclidean projection onto the normalized RGB cube. When the unknown RGB target is in `[0,1]^3`, projecting an out-of-range prediction to that box cannot increase continuous RGB squared distance to that target, while leaving in-range values unchanged. This geometric statement did not guarantee improvement after RGB-to-Y conversion and uint8 quantization, nor did it guarantee superiority to the stronger two-pass reference.

## Implementation

`candidate.py` used one deterministic operation:

```python
return np.clip(sr, np.float32(0.0), np.float32(1.0)).astype(np.float32, copy=False)
```

The LR input was unused. There was no training, stochasticity, parameter fitting, file access, extra model forward, ensemble, LR residual/backprojection, spatial filtering, contrast adjustment, luminance-preserving chroma gamut compression, phase correction, or RGB lattice selection. One broker synthetic check passed shape and finiteness before registration. The candidate and plan were frozen under protocol SHA-256 `a78fe5808860e854be63368e830f18bd00c6950f86ca6879ffe22e1bd9a41876`.

## Results

The controller reported a valid measurement on all 12 frozen observations:

| Quantity | Result |
|---|---:|
| Reference mean PSNR-Y | 31.130634 dB |
| Candidate mean PSNR-Y | 31.061012 dB |
| Mean paired gain | -0.069621 dB |
| Paired-effect standard deviation | 0.071219 dB |
| 95% paired-bootstrap interval | [-0.107382, -0.028826] dB |
| Images improved / worsened | 1 / 11 |
| Candidate/reference latency | 0.494207 |
| Experiment wall time | 58.374112 s |
| Local compute proxy | $0.016215 |

Paired effects in frozen observation order (`img_012`, `img_016`, `img_024`, `img_029`, `img_030`, `img_034`, `img_039`, `img_053`, `img_061`, `img_073`, `img_074`, `img_082`) were:

`[-0.053843, -0.074739, +0.090884, -0.084331, -0.211393, -0.028806, -0.096386, -0.087079, -0.109898, -0.003583, -0.081654, -0.094629]` dB.

The bootstrap interval describes original-image sampling variability. Seed 0 was not treated as an independent training replication. Actual model/planner billing is unknown (`null`), not zero. The local proxy excludes setup time, electricity, depreciation, and long-term artifact retention.

## Interpretation and scope

This valid negative abandons the registered route: fixed componentwise projection of plain SwinIR output onto `[0,1]` as a way to beat the fixed two-pass reference under the frozen gates. It does not justify changing the bounds, soft or adaptive clipping, or adding rescue complexity.

The experiment does **not** isolate clipping's causal effect. The candidate used one plain forward while the comparator used two flip-related forwards, and there was no plain-output ablation. Therefore the negative difference cannot be attributed specifically to projection; it supports only the preregistered end-to-end decision. It is also one 12-image Urban100 x2 study under fixed SwinIR-S weights and one evaluator, not a worldwide SOTA claim or a new general discovery. PSNR-Y after quantization differs from the continuous RGB geometry used to motivate the candidate.

## Workflow completion

The autonomous research cycle was completed: I searched and read primary literature through the broker, proposed one distinct hypothesis, implemented it, passed the allowed synthetic check, preregistered the frozen plan and code, requested exactly one experiment, interpreted its valid result against all three frozen gates, and wrote this report. No human coding or execution, holdout inspection, benchmark-label access, retry, sweep, or post-result modification was used. A negative outcome is still a completed scientific decision: **STOP**.
