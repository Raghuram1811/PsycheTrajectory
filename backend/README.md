# PsycheTrajectory Research Backend

This Python package implements a causal research pipeline for physiological observations. Its exploratory output describes latent physiological patterns and deviation from an individual's prior baseline. Latent coordinates do not identify disorders. Symptom estimates stay null unless a separately trained, supported questionnaire head is supplied.

All included data is simulated and exists only to exercise the software. Simulated trajectories are not people, diagnoses, or evidence of clinical performance.

## Setup and Demo

Use Python 3.11, 3.12, or 3.13 (PyTorch wheels are not available for every newer Python runtime). From the repository root:

```sh
python3.11 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e 'backend[api,parquet,test]'
source backend/.venv/bin/activate
psychetrajectory synthetic --output backend/data/simulated-observations.csv --subjects 8 --days 40 --seed 17
psychetrajectory ingest backend/data/simulated-observations.csv --output backend/data/validated-observations.csv
psychetrajectory preprocess backend/data/validated-observations.csv --output backend/artifacts/daily-features.jsonl
psychetrajectory train_encoder backend/data/validated-observations.csv --output backend/artifacts/encoder.pt --latent-dim 8 --seed 17
psychetrajectory tune_filter --observations backend/data/validated-observations.csv --encoder backend/artifacts/encoder.pt --output backend/artifacts/filter-config.json
psychetrajectory train_heads --output backend/artifacts/symptom-heads.json
psychetrajectory evaluate backend/data/validated-observations.csv --encoder backend/artifacts/encoder.pt --filter-config backend/artifacts/filter-config.json --output backend/artifacts/evaluation.json
psychetrajectory replay backend/data/validated-observations.csv --subject sim-001 --encoder backend/artifacts/encoder.pt --config backend/configs/daily-v1.json --output backend/artifacts/trajectory.jsonl
```

The final JSONL is a simulated exploratory trajectory. Model artifacts and generated health-like data are ignored by Git. Run the optional API with:

```sh
uvicorn psychetrajectory.api:app --app-dir backend/src --host 127.0.0.1 --port 8000
```

`POST /v1/infer` accepts one causal embedding window and returns level, velocity, covariance, stale/prediction-only status, and null symptom outputs. Filter state is transactionally stored in `backend/artifacts/api-state.sqlite3`; this local API is an integration example, not a production storage service.

## Data

Observation tables use `observations-v1`; see `examples/observations.csv`. Required identifiers are pseudonymous. Event and availability timestamps must include a timezone and are normalized to UTC. Supported signals are heart rate, beat intervals, documented device HRV, EDA, skin temperature, respiration, steps, and sleep duration. Unknown channels and units fail validation. Daily features are aggregated in UTC and delayed summaries enter only on their availability date. Device/context metadata is retained at observation level; unavailable values remain missing.

Questionnaire labels are separate in `examples/labels-v1.csv` and follow `labels-v1`. A label must specify instrument/version, target, population/age band, assessment time, recall interval, and provenance. Optional ridge score heads accept `--labels labels.csv --trajectories replay.jsonl` and require at least five training participants per supported head. PHQ-9 and GAD-7 target heads are independent; ADHD remains unsupported. Each assessment pairs once with the latest filtered state available by that time. Insufficient training data leaves that head null.

Parquet support is optional (`.[parquet]`). The package uses PyTorch and NumPy; the web API and tests are optional extras. The top-level Next.js/Vinext site remains a separate application.

## Modeling Notes

- Encoder scaling is fitted from the training participant partition only. The masked denoising autoencoder reconstructs observed values, receives an observation mask, and uses small explicitly documented scaled-feature noise. Ten daily features include variability summaries; an 8D latent code is therefore a reduction. The package exposes PCA and direct-feature baselines.
- Daily feature quality and missingness remain visible. Bounded one-day carry-forward imputation is available; longer gaps stay missing. HRV RMSSD is calculated only from at least three usable beat intervals, never from sparse heart-rate summaries.
- The local-trend filter state is `[level, velocity]` per latent coordinate. Time is measured in days. The continuous white-acceleration covariance is discretized with `dt`, and state updates use a linear solve and Joseph covariance update. `Q` and `R` are configured starting values, not clinically calibrated quantities.
- A 30-day gap resets the filter. Duplicate/out-of-order timestamps and cross-subject or cross-artifact state reuse are rejected. Covariance is model-based uncertainty, not clinical confidence.
- `tune_filter` selects from a small Q/R grid using one-step Gaussian innovation likelihood on validation participants. A short smoke corpus does not establish residual independence, calibrated intervals, device/population transport, response lag, or clinical benefit.

See [MODEL_CARD.md](MODEL_CARD.md) for intended use, known limitations, and required evidence.
