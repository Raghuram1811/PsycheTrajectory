# Contributing

Thanks for helping make PsycheTrajectory clearer, safer, and more useful. This is an early research prototype, so contributions should preserve the distinction between exploratory signals and clinical evidence.

## Before opening a pull request

- Search existing issues and open an issue first for substantial changes.
- Keep changes focused and explain the user or research problem they address.
- Include tests for behavior changes, especially timestamp handling, missing data, participant separation, and causal feature availability.
- Never commit personal, identifiable, or real health data. Use the synthetic examples and generated fixtures.
- Avoid claims of diagnosis, prediction, clinical benefit, or validation unless supported by appropriate evidence.

## Local checks

For the simulator, use Node.js `>=22.13.0`:

```sh
npm install
npm test
```

For backend setup and tests, follow [backend/README.md](backend/README.md). Its test dependencies are available through `backend[api,parquet,test]`; tests can be run with:

```sh
pytest backend/tests
```

The root build scripts target the repository's Linux Sites environment. See [development and hosting notes](docs/development.md) before running platform-specific scripts locally.

## Pull requests

Describe the problem, the behavior changed, and the checks you ran. Include screenshots for visible UI changes and note any assumptions or limitations. Keep generated datasets, model artifacts, caches, and binaries out of commits.
