# Complete one autonomous research cycle

You are the research agent. The human explicitly asked you to propose your own
research hypothesis, write the implementation, and execute a complete experiment.
Do all three yourself using the broker. The orchestrator has NOT provided a candidate
algorithm or a menu. A negative result is a valid completed cycle. Do not ask the human
to write your candidate or run your commands.

Read policy.json and literature.json. Write candidate.py and research.json yourself.
You have a 15-minute session, including at most ONE registered experiment. Aim to
finish planning/code within 5 minutes, so enough time remains for execution and reporting.

## Scientific context

G0 reproduced the fixed official SwinIR-S x2 pipeline. G1 tested two-pass horizontal
flip averaging on BSD100 and stopped because +0.01472 dB did not reach the predefined
+0.05 dB adoption threshold; latency was 2.00x. That candidate route stays STOP.
Do not retune flips, add more ensemble transforms, add complexity atop its candidate,
or relabel this as a retry. Newly consulted primary references are in literature.json.
Use them as external evidence for a genuinely distinct hypothesis and document the
causal mechanism and why the new route differs before registering.

Propose ONE deterministic, inexpensive postprocessing method operating on a low-res
RGB image and the plain (unensembled) SwinIR float32 prediction. There is no prescribed
algorithm. No training, additional weights, sweeps, stochastic methods, parameter search,
or alternative candidates after outcomes. Choose constants from reasoning before the run.
You can conclude that the hypothesis is false after a valid negative experiment.

The stronger comparison is the existing fixed two-pass flip-ensemble reference, NOT
bicubic or plain SwinIR. G1's failed adoption decision remains final; using an existing
method as a comparator does not reopen its optimization. Your candidate receives only
plain SwinIR output, so it must not extend the rejected ensemble route.

Held-out evaluation: all 14 original Set14 x2 pairs, never scored in our prior runs.
You cannot read HR/reference images or the research repository. Do not try to find
or fetch public labels. No network use from tools; the supplied literature is sufficient
background for this bounded pilot. Do not inspect other directories or credentials.
Do not claim a worldwide SOTA result or a new scientific discovery from this test.

## Candidate code contract

One file candidate.py, <=100 KB, imports limited to numpy, cv2, math. No file IO, dynamic
imports, networking, randomization or subprocesses. Define:

    def enhance(lr, sr):
        # lr: float32 HxWx3 RGB, roughly [0,1]
        # sr: float32 (2H)x(2W)x3 RGB, plain fixed SwinIR output BEFORE clamping/rounding
        # return a finite floating NumPy array of the same shape as sr

The trusted adapter supplies arrays, owns output filenames and quantization, and runs
your code under an OS profile with no network, user-file access or HR access. You may
not import the model, modify its weights, call additional forwards, alter the evaluator,
change data identity, or alter the stopping criteria. Your code and plan are snapshotted
at registration, before any real-image inference or metric is returned.

Use /usr/bin/python3 to run labctl.py. It sends operations to an independent controller:

1. Optional: `python3 labctl.py check` runs only two synthetic array shape/finiteness
   checks. At most 3 calls BEFORE registration. These are implementation checks,
   not measurements for choosing an algorithm. You can fix syntax/shape failures.
2. `python3 labctl.py register` freezes research.json and candidate.py.
3. `python3 labctl.py run` triggers the sole registered experiment and waits for the
   result. This is how YOU execute it; do not run hidden evaluator code directly.
4. `python3 labctl.py status` can read the existing result but cannot rerun it.
5. Write REPORT.md with the original hypothesis, code mechanism, all results and
   costs/unknowns, limitations, and STOP/CONTINUE. Explain whether a full autonomous
   workflow was completed independently of whether the method achieved its threshold.

After register, do NOT change candidate.py or research.json. After results, do not
call check/register/run again. No retries on a negative or operational failure.
If execution validity fails, report the precise cause and stop; do not rescue it.

## research.json required fields

- hypothesis: one falsifiable scientific/engineering claim.
- mechanism: your own reasoning for the candidate, not just an algorithm name.
- baseline: describe the fixed two-pass SwinIR flip reference and the candidate's
  distinct plain-SwinIR-plus-postprocess path.
- why_not_g1_retry: explicitly explain the different mechanism.
- new_evidence: nonempty list of {source, claim, why_distinct}, citing supplied primary
  source URLs; distinguish external paper results from your inference.
- controls: copy policy.json controls exactly.
- minimum_effect, max_latency_ratio, bootstrap, observation_ids: copy policy.json exactly.
- stop_route: what route a valid negative outcome eliminates.
- parameters: all constants and steps chosen before seeing outcomes, with a short rationale.

The policy uses absolute dB effect, paired original-image bootstrap, and a latency guard.
Seed 0 is an execution identifier, not independent training replication. This single
study must change the decision to adopt or abandon your fixed candidate. Keep the
original criterion even if a smaller effect looks promising. Dollar model billing
may remain unknown; do not fabricate zero. The local machine-hour proxy is not an invoice.
