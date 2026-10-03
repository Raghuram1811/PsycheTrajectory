# Research and Product Roadmap

PsycheTrajectory is a staged research programme, not a committed clinical product plan. This roadmap adapts the technical direction in `03_W-JEPA_Application_Technical_Approach_Roadmap.pdf` (revised August 2026) to the state of this repository. Stages are ordered by evidence and dependency, not calendar date. Later stages proceed only if earlier results justify them.

## North star

Investigate whether sustained, person-relative changes in noisy wearable signals can provide useful context between care visits, while keeping a person's account and professional assessment authoritative. The research claim is deliberately narrow: observed signal deviations may carry information about change for people to interpret. The project does not assume those deviations measure wellbeing, symptoms, or a mental health condition.

## Current baseline

The repository currently contains a browser-based interaction simulator and a separate Python research pipeline. The backend supports validated observations, causal daily features, a masked autoencoder, PCA and direct-feature baselines, local-trend Kalman filtering, optional questionnaire heads, evaluation, and synthetic demos. The simulator is not connected to the backend.

W-JEPA, a wearable-adapted joint-embedding predictive architecture, is a proposed experiment. It is **not implemented**, and no model results or clinical utility are claimed. The first research task is to establish whether this objective adds value over the existing baselines.

## Staged scope

### 0. Reproducible, bounded prototype

**Focus:** Keep the current simulator and research pipeline understandable, reproducible, and safe to explore.

- Maintain versioned schemas, causal availability rules, participant-level separation, synthetic fixtures, and explicit model limitations.
- Keep simulator scenarios clearly illustrative and separate from model inference.
- Improve tests and documentation before adding user data collection or deployment features.

**Exit evidence:** A new contributor can run the synthetic pipeline and tests, inspect inputs and outputs, and understand what the prototype does not establish.

### 1. Evaluation design and data readiness

**Focus:** Define credible comparisons before introducing a new architecture.

- Specify participant-disjoint train, validation, and test protocols and leakage checks.
- Establish a small set of falsifiable outcomes: representation quality against AR and MAE baselines, graceful degradation under missingness and artefact, label efficiency, and false flags per participant-week.
- Document modality availability, timestamp/causality assumptions, device characteristics, and subgroup reporting requirements.
- Assess dataset permissions, consent, provenance, and channel coverage before using any external or prospective data.

**Exit evidence:** A reviewed evaluation protocol, suitable data access, and reproducible baseline metrics. Synthetic data alone cannot satisfy this gate.

### 2. W-JEPA method experiment

**Focus:** Test the proposed method as an isolated research comparison.

- Implement context and target windows, an online context encoder, an exponential-moving-average target encoder, and a predictor trained on latent-space targets.
- Compare against the existing masked autoencoder and simpler forecasting/direct-feature baselines on the same participant splits and compute budget.
- Test for representation collapse and sensitivity to window length, modality dropout, artefact, and sampling frequency.
- Keep self-report and validated assessment targets out of model inputs when they are used for evaluation.

**Exit evidence:** Replicated gains on held-out participants for predeclared metrics, or a documented negative result. A negative result is a valid outcome; it is not a reason to move the goalposts.

### 3. Personalised trajectories and robustness

**Focus:** Determine whether learned representations support stable, interpretable within-person change.

- Evaluate baseline-relative deviations and trajectory estimates against population-level and non-JEPA baselines.
- Stress-test confounds including travel, illness, caregiving, seasonal change, device changes, missingness, and irregular schedules.
- Report performance by relevant device and participant groups where data supports it; identify unsupported populations rather than implying universal performance.
- Calibrate persistence and alert burden using false flags per participant-week, alongside sensitivity and lead time.

**Exit evidence:** Reliable held-out performance, transparent uncertainty and subgroup limitations, and evidence that false flags are not overwhelming. If the signal is dominated by confounds or varies substantially across groups, narrow or stop the claim.

### 4. Grounded interpretation and prospective evaluation

**Focus:** Test whether detected changes correspond to changes people themselves consider relevant.

- Pursue research partnerships and prospective data collection with appropriate consent, governance, privacy protections, and ethics review.
- Triangulate held-out self-report, session narrative, and validated instruments at fixed intervals; do not treat any single source as complete ground truth.
- Preserve disagreement: participant correction should be visible and should not be silently converted into model confirmation.
- Keep any generated summary closed-world: it may use only structured, traceable evidence, must not invent causes, and must surface uncertainty and disagreement.

**Exit evidence:** Prospective evidence that the outputs are understandable, acceptable, and useful as conversation context, with limitations and failure cases published. This is not evidence of diagnosis or treatment benefit.

### 5. Carefully bounded translation

**Focus:** Consider whether research outputs merit a participant-professional workflow at all.

- Only explore a human-facing workflow after earlier evidence gates and appropriate safety, privacy, accessibility, and governance review.
- Show interpretable signal deviations, the personal baseline used, data quality, uncertainty, and participant-provided context; do not expose latent coordinates as explanations.
- Keep participant agency central: meaningful opt-in, correction, deletion, and control over what is shared.
- Do not build automated triage, crisis detection, diagnosis, treatment recommendations, or clinician decision automation into this scope.

**Exit evidence:** Independent review supports a narrowly described, non-diagnostic use and an operational plan for privacy, safety, monitoring, and redress. Otherwise remain a research prototype.

## Cross-cutting principles

- **Person-relative, not population-normal:** Individual baselines are the unit of comparison, with explicit handling or stated limits for shift work, caregiving, travel, and irregular routines.
- **Causal and traceable:** Respect when data became available. Every summary should be traceable through signals, features, latent state, trajectory, and any significance rule.
- **Evidence before expansion:** No stage is promised by a date. Missing data access, failed baselines, collapse, poor subgroup performance, or excessive false flags are valid reasons to pause or change direction.
- **No construct leap:** A deviation in observed signals is not itself a measure of psychological wellbeing or a condition.
- **Privacy by design:** Do not commit real or identifiable health data. Future collection requires explicit governance and consent before implementation.

## Out of scope

This roadmap does not commit the project to a medical device, clinical decision support, diagnosis, crisis service, treatment recommendation, population screening, or production health-data platform. It does not claim that W-JEPA will outperform existing methods. Any future change to these boundaries requires new evidence and review, not just an implementation milestone.
