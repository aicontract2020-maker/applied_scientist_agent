# Draft inquiry to the Delft dataset authors — NOT SENT

This draft is for user review. No email, form submission or other outbound
contact has occurred. Recipient: the corresponding author/data contact listed
in the official dataset/publication record; verify a current contact address
before sending. Do not send private research artifacts with this inquiry.

Subject: Metadata and intended-use permission for independent replication using DOI 10.4121/20940646.v1

Dear Dr Luesutthiviboon and Dr Lima Pereira,

We are developing ResearchHarness, an open-source workflow for preregistered,
auditable research, with potential future commercial applications. We are
considering your NACA 633–018 dataset (10.4121/20940646.v1) for an independent
test of a fixed feature: appending frequency × suction-side displacement
thickness / freestream velocity to a fixed Extra Trees regression model.

An initial study on the UCI Airfoil Self-Noise dataset passed its preregistered
criteria. For an external test, we would retain the original training data,
model parameters and thresholds; we have not fitted models to your data or
downloaded/scored the acoustic spectra. We first need to establish measurement
compatibility and appropriate permission:

1. In LRM_Master.txt and HRM_Master.txt, does `delta* (mm)` refer to the suction
   side at each condition, to one fixed measurement side, or an average? Could
   you point us to the exact measurement locations and side conventions,
   including zero incidence? Are additional measured values available for
   straight-edge cases currently marked N/A? We would not interpolate or
   substitute a boundary-layer model.
2. Could you clarify the geometric/effective angle signs in the LRM table,
   the freestream velocities for the HRM cases, and the distinction from the
   local edge velocity `u_e`? We would also need the geometry, transition and
   acquisition identifiers necessary to keep related spectra in the same
   statistical group.
3. What is the exact definition and normalization of the distributed
   narrowband SPL: bin bandwidth, pressure reference, observer distance,
   integrated source span, directivity and propagation/beamforming corrections?
   We will separately verify the UCI scaled-SPL definition. We do not want to
   use a fitted offset or calibration to force agreement between datasets.
4. We noted the correction DOI 10.2514/1.J061630.c1 and the signal-to-noise
   limitations. Is there a machine-readable, per-case valid frequency mask or
   background/source-map information that fixes admissible bins independently
   of our model predictions? Please identify the current corrected version
   and any required changes to the version 1 files.
5. The repository lists CC BY-NC 4.0. Would you permit this specific research
   use in an open-source project that may support a future commercial research
   platform? We would initially publish only methods, aggregate results and
   file checksums, not your raw spectra or trained model artifacts. Please
   specify any required permission, attribution or restrictions. We do not
   assume the existing license already authorizes this intended use.

We would freeze the eligible cases, conversions, quality mask and statistical
protocol before any model evaluation. If the definitions cannot be aligned,
we will report the dataset as unsuitable for this direct replication rather
than reinterpret a prediction failure or change the feature.

Thank you for your guidance.

ResearchHarness project
https://github.com/aicontract2020-maker/applied_scientist_agent
