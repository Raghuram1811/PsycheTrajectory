# PsycheTrajectory

PsycheTrajectory is a prototype for helping people and clinicians make sense of changing wellbeing patterns between sessions. Instead of treating raw data as a diagnosis, the app frames it as shared context for reflection and conversation.

This repository contains both:

- a front-end concept app in `app/` that demonstrates the experience and simulator
- a Python research backend in `backend/` that generates, validates, and models simulated physiological observation data

The project is designed for exploration and prototyping, not clinical decision-making.

## What the app is for

PsycheTrajectory is meant to support a human-centered workflow:

- capture signals such as sleep, movement, social connection, and mood
- compare them against each person's baseline and recent pattern
- surface uncertainty and missing context rather than pretending the signal is definitive
- invite the person and therapist to agree, disagree, or refine the interpretation together

The core idea is simple: a model should help start the conversation, not replace it.

## Intended usage

Use PsycheTrajectory as:

- a research or concept prototype for understanding how trajectory-style summaries can support therapy sessions
- a demonstration tool for exploring how different patterns might look under different life events, stressors, or daily routines
- a starting point for future clinical or product work that requires consent, human review, and clear guardrails

Do not use it as:

- a medical device
- a diagnostic instrument
- a real-time crisis monitoring system
- a source of treatment decisions without human oversight

All example data in the repo is synthetic and intentionally non-clinical. The backend README calls this out explicitly: these are simulated trajectories used to exercise software, not actual patient data.

## Repository structure

- `app/`: Next.js/Vinext app containing the interactive simulator, concept walkthrough, and user experience prototype
- `backend/`: Python package for the research pipeline and simulated observation workflows
- `db/`, `drizzle/`, `scripts/`: supporting project data and automation
- `examples/`: sample data and example usage
- `tests/`: validation and rendering checks

## Local app usage

From the repository root:

```bash
npm install
npm run dev
```

Then open the local app in the browser and explore the simulator scenarios and narrative walkthrough.

## Backend usage

The backend is intended for generating and testing the research pipeline. The project includes a CLI workflow for synthetic data generation, validation, feature extraction, model training, and evaluation.

See `backend/README.md` for the full setup and command flow. In short, the backend is used to:

- generate synthetic observation data
- validate and normalize it
- preprocess time-series features
- train and evaluate latent-space models
- generate trajectory-style outputs for exploration

A typical workflow looks like this:

```bash
python3.11 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e 'backend[api,parquet,test]'
source backend/.venv/bin/activate
psychetrajectory synthetic --output backend/data/simulated-observations.csv --subjects 8 --days 40 --seed 17
psychetrajectory ingest backend/data/simulated-observations.csv --output backend/data/validated-observations.csv
psychetrajectory preprocess backend/data/validated-observations.csv --output backend/artifacts/daily-features.jsonl
```

## Design principles

PsycheTrajectory is built around a few clear principles:

- personal baseline matters more than population averages
- uncertainty should remain visible
- interpretation should be reviewed by a person and, when relevant, a clinician
- context and disagreement are part of the signal, not noise
- the model should support reflection and treatment conversations, not automate judgment

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for the full terms.

## Important note

This repository is a prototype and concept demonstrator. It is useful for exploring product concepts, research workflows, and interaction design, but it should not be treated as a production mental-health system or clinical platform.

For implementation details and backend-only documentation, please see:

- `backend/README.md`
- `LOCAL_SETUP.md`
- `MODEL_CARD.md` (when present in the backend research package)
