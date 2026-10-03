# Model Card: PsycheTrajectory Daily Latent Trajectory

## Intended Use

Research prototyping of causal data preparation, masked dimensionality reduction, and latent physiological trajectory estimation. The default mode reports feature coverage, latent level/velocity, prior-baseline deviation after sufficient history, quality flags, and model covariance.

## Out of Scope

Diagnosis, screening, treatment selection, emergency alerts, or claims that physiology identifies depression, anxiety, ADHD, hormones, or any other condition. Latent dimensions have no inherent clinical meaning. Questionnaire outputs are symptom score estimates, not diagnoses.

## Training Data

The included generator creates simulated subject differences, gradual changes, nuisance effects, missing channels, and artifacts. It creates no diagnosed people and no symptom labels. Therefore the generated encoder is a software demonstration only. There is no evidence here for a relationship between its representation and clinical outcomes.

## Evaluation

The synthetic workflow can check code execution and reconstruction behavior. It cannot establish held-out clinical accuracy, population coverage, calibration, fairness, clinical utility, or device invariance. Real evaluation requires subject-disjoint partitions, independent external validation, and uncertainty intervals computed at participant level. A forward-time personalization assessment must also purge overlapping recall windows.

## Known Limitations

- Daily UTC aggregation loses within-day timing and circadian structure.
- Supported feature units and artifact rules are intentionally conservative and require validation against each source/device.
- The autoencoder may encode device or missingness structure. Device/missingness probes and simple PCA/direct-feature baselines remain required before interpreting its utility.
- The configured Kalman `Q` and `R` are starting assumptions. Identifiability, residual autocorrelation, innovation coverage, response lag, and oversmoothing have not been established by the synthetic smoke workflow.
- The local API stores filter state transactionally in SQLite but has no production identity, access-control, retention, or operational design.
- Out-of-distribution, unsupported-device, and unsupported-population gates are not clinically validated. Coverage checks alone do not detect a distribution shift.
- PHQ/GAD/age-specific ADHD heads are not trained or enabled. Suitable labels, usage rights, population evidence, task horizons, and independent evaluation are absent.

## Evidence Needed Next

Versioned, consented observations with device/source and availability metadata; documented signal semantics; separately sourced questionnaire/clinical labels with instrument/version, recall interval, age/population, and provenance; enough participants for grouped training, tuning, and external testing; prespecified tasks; missingness/device probes; and independent validation. Data handling and deployment would need a separately reviewed privacy/security design.
