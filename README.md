# PsycheTrajectory

**See the pattern. Hear the person.**

PsycheTrajectory explores how people and psychologists might build shared context about changes between sessions. The repository contains an interactive concept simulator and a separate experimental Python research pipeline for exploring physiological trajectories.

The central design question is not simply whether signals changed, but whether an interpretation fits the person's experience. Try **Signal without meaning** to see a routine shift corrected by context, or **Flat physiology, hard week** to see how passive signals can miss a person's own report.

> **Research prototype:** The simulator uses illustrative scenarios, and the backend's included data is synthetic. Neither is a clinical tool or evidence of clinical validity. Outputs are not diagnoses, and must not guide care.

## Try the simulator

Requirements: Node.js `>=22.13.0`.

```sh
npm install
npm run dev
```

Open the local URL printed by Vite. The simulator runs in the browser; its scenario sliders are illustrative and do not send personal data to the research backend.

## Explore the research backend

The Python pipeline covers observation validation, causal daily features, masked autoencoder and baseline representations, local-trend Kalman filtering, optional questionnaire score heads, evaluation, and a local inference API. Start with the [backend quickstart](backend/README.md) and [model card](backend/MODEL_CARD.md).

The site and backend are separate applications. The backend is experimental: simulated results are software plumbing checks, not validation. Do not use real health data with this prototype.

## Project status

This is an early research and interaction prototype, not a deployed product. The simulator demonstrates interaction concepts; it is not connected to the Python pipeline. There is no supported clinical workflow, production data service, or validated model.

See the [research and product roadmap](docs/roadmap.md) for staged scope, evidence gates, and the proposed W-JEPA experiments. W-JEPA is a research direction, not an implemented capability.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for local checks and project principles. Useful contributions include reproducible bug reports, clearer limitations, accessible interaction improvements, and tests for data validation or causal behavior. Please open an issue to discuss substantial changes before starting work.

## Development notes

This repository also retains Cloudflare Sites and Vinext hosting configuration. Its lifecycle scripts target a Linux environment; see [development and hosting notes](docs/development.md) before using them. Those deployment details are infrastructure, not a prerequisite for exploring the simulator or backend.
