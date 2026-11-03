# ResearchHarness

This repository is a research workflow scaffold. Keep the initial implementation small,
provider-independent, and reproducible. Never describe synthetic fixture results as evidence
for scientific performance or commercial viability.

## Empirical research: falsification and stopping rules

Apply these rules by default to every empirical research or exploratory project, unless the user explicitly overrides them.

1. Before running an experiment, record the hypothesis, strongest relevant baseline, controlled variables, primary metric, minimum meaningful effect, uncertainty or replication plan, and a concrete stop/go threshold.
2. Every experiment must change a research decision. State in advance what each plausible outcome means and which hypothesis or route it can eliminate. Do not run experiments whose only purpose is to produce an interesting-looking result.
3. Prefer the smallest decisive experiment. Do not add architecture, data, objectives, or tuning merely to rescue a failed hypothesis.
4. Treat a result below the predeclared threshold as evidence to stop the current route. Continue only when the measurement itself failed a predeclared validity check, or genuinely new external evidence motivates a new hypothesis. Record that reason explicitly.
5. Do not reinterpret the success criterion after seeing results. Exploratory findings may generate a new preregistered experiment, but are not confirmation of the original hypothesis.
6. For stochastic experiments, require replication and report effect size and variability, not only the best seed. Charge all relevant storage, compute, latency, data, and tuning costs.
7. Keep a decision ledger containing the hypothesis, protocol, result, conclusion, and STOP / CONTINUE decision. Negative results are final outputs, not prompts to increase complexity.

## Development checks

Run `python3 -m unittest discover -s tests -v`. Software unit tests and synthetic CLI
smoke checks validate implementation only; they are not empirical research experiments.
Do not execute arbitrary experiment code or spend external compute without a registered
protocol and an explicitly scoped execution environment.
