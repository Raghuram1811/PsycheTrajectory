from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import numpy as np

from .encoder import embed, fit_pca_baseline, load_encoder, pca_baseline
from .diagnostics import innovation_diagnostics
from .heads import train_ridge_heads, write_heads
from .io import read_labels, read_observations, write_observations
from .kalman import LocalTrendFilter
from .pipeline import dataset_fingerprint, feature_matrix, replay_subject, save_replay, subject_split, train_daily_encoder
from .preprocessing import aggregate_daily, causal_impute
from .synthetic import generate_observations


def main() -> None:
    parser = argparse.ArgumentParser(prog="psychetrajectory")
    commands = parser.add_subparsers(dest="command", required=True)
    synth = commands.add_parser("synthetic", help="create simulated observations; not clinical evidence")
    synth.add_argument("--output", default="data/simulated-observations.csv")
    synth.add_argument("--subjects", type=int, default=8)
    synth.add_argument("--days", type=int, default=40)
    synth.add_argument("--seed", type=int, default=17)
    ingest = commands.add_parser("ingest", help="validate and normalize a CSV/Parquet observations table")
    ingest.add_argument("input")
    ingest.add_argument("--output", required=True)
    preprocess = commands.add_parser("preprocess", help="aggregate to causal daily-v1 features")
    preprocess.add_argument("input")
    preprocess.add_argument("--output", required=True)
    train = commands.add_parser("train_encoder", help="train masked autoencoder on training participants")
    train.add_argument("input")
    train.add_argument("--output", default="artifacts/encoder.pt")
    train.add_argument("--latent-dim", type=int, default=8)
    train.add_argument("--seed", type=int, default=17)
    tune = commands.add_parser("tune_filter", help="select local-trend noise parameters on held-out participants")
    tune.add_argument("--output", default="artifacts/filter-config.json")
    tune.add_argument("--observations", help="observations CSV/Parquet; requires --encoder to tune on validation participants")
    tune.add_argument("--encoder", help="frozen encoder checkpoint")
    heads = commands.add_parser("train_heads", help="train supported independent questionnaire score heads")
    heads.add_argument("--labels", help="separate labels-v1 CSV")
    heads.add_argument("--trajectories", help="JSONL from subject-disjoint causal replay runs")
    heads.add_argument("--output", default="artifacts/symptom-heads.json")
    evaluate = commands.add_parser("evaluate", help="report held-out reconstruction and trajectory diagnostics")
    evaluate.add_argument("input")
    evaluate.add_argument("--labels")
    evaluate.add_argument("--encoder", help="frozen encoder for participant-held-out reconstruction metrics")
    evaluate.add_argument("--filter-config", help="validation-tuned filter config for trajectory diagnostics")
    evaluate.add_argument("--output", default="artifacts/evaluation.json")
    replay = commands.add_parser("replay", help="causal batch replay for one pseudonymous subject")
    replay.add_argument("input")
    replay.add_argument("--subject", required=True)
    replay.add_argument("--encoder", default="artifacts/encoder.pt")
    replay.add_argument("--config", default="backend/configs/daily-v1.json")
    replay.add_argument("--heads", help="optional trained symptom-head artifact")
    replay.add_argument("--output", default="artifacts/trajectory.jsonl")
    infer = commands.add_parser("infer", help="alias for replay over a local observation file")
    infer.add_argument("input")
    infer.add_argument("--subject", required=True)
    infer.add_argument("--encoder", default="artifacts/encoder.pt")
    infer.add_argument("--config", default="backend/configs/daily-v1.json")
    infer.add_argument("--heads", help="optional trained symptom-head artifact")
    infer.add_argument("--output", default="artifacts/trajectory.jsonl")
    args = parser.parse_args()

    if args.command == "tune_filter" and bool(args.observations) != bool(args.encoder):
        parser.error("tune_filter requires both --observations and --encoder, or neither")
    if args.command == "evaluate" and args.filter_config and not args.encoder:
        parser.error("--filter-config requires --encoder")

    if args.command == "synthetic":
        rows = generate_observations(args.subjects, args.days, args.seed)
        write_observations(args.output, rows)
        print(json.dumps({"output": args.output, "rows": len(rows), "data_status": "SIMULATED"}))
    elif args.command == "ingest":
        rows = read_observations(args.input)
        write_observations(args.output, rows)
        print(json.dumps({"rows": len(rows), "subjects": len({x.subject_id for x in rows}), "dataset_fingerprint": dataset_fingerprint(rows)}))
    elif args.command == "preprocess":
        rows = read_observations(args.input)
        daily = aggregate_daily(rows, datetime.now(timezone.utc))
        daily = causal_impute(daily)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text("\n".join(json.dumps(row.__dict__, sort_keys=True) for row in daily) + "\n", encoding="utf-8")
        print(json.dumps({"daily_rows": len(daily), "features": len(daily[0].values) if daily else 0, "output": args.output}))
    elif args.command == "train_encoder":
        metrics = train_daily_encoder(read_observations(args.input), args.output, args.seed, args.latent_dim)
        print(json.dumps({key: value for key, value in metrics.items() if key != "training_history"}, indent=2))
    elif args.command == "tune_filter":
        config = {"method": "configured starting values; no participant-disjoint validation supplied",
                  "time_unit": "days", "process_level": 0.02, "process_velocity": 0.005,
                  "observation_variance": 0.15, "quality_r_inflation_max": 4.0,
                  "initialization": "first usable embedding; covariance 10I",
                  "identifiability": "Q/R tradeoff is weakly identified on short sequences"}
        if args.observations and args.encoder:
            rows = read_observations(args.observations)
            daily = causal_impute(aggregate_daily(rows, max(item.available_at_utc for item in rows)))
            split = subject_split((row.subject_id for row in daily), seed=17)
            validation = [row for row in daily if row.subject_id in split["validation"]]
            model, mean, scale, version = load_encoder(args.encoder)
            values, masks = feature_matrix(validation)
            latents, _ = embed(model, values, masks, mean, scale)
            candidates = [(q, qv, r) for q in (0.003, 0.02, 0.1)
                          for qv in (0.0005, 0.005, 0.05) for r in (0.03, 0.15, 0.5)]
            scores = []
            for q, qv, r in candidates:
                core = LocalTrendFilter(latents.shape[1], q, qv, r, artifact_version=version)
                total, count = 0.0, 0
                state, previous_subject = None, None
                for row, latent in zip(validation, latents):
                    if row.subject_id != previous_subject:
                        state, previous_subject = None, row.subject_id
                    usable = row.coverage >= 0.25
                    if not usable:
                        if state is not None:
                            state, _ = core.step(row.subject_id, datetime.fromisoformat(row.day_utc).replace(tzinfo=timezone.utc), None, state)
                        continue
                    state, detail = core.step(row.subject_id, datetime.fromisoformat(row.day_utc).replace(tzinfo=timezone.utc), latent, state,
                                              quality=max(0.05, row.coverage))
                    if detail.get("innovation") is not None:
                        residual = np.asarray(detail["innovation"])
                        covariance = np.asarray(detail["innovation_covariance"])
                        sign, logdet = np.linalg.slogdet(covariance)
                        if sign > 0:
                            total += 0.5 * (logdet + residual @ np.linalg.solve(covariance, residual) + len(residual) * np.log(2 * np.pi))
                            count += 1
                if count:
                    scores.append((total / count, q, qv, r, count))
            if scores:
                best = min(scores)
                config.update({"method": "validation-participant one-step Gaussian innovation negative log likelihood",
                               "process_level": best[1], "process_velocity": best[2],
                               "observation_variance": best[3], "validation_mean_nll": best[0],
                               "validation_innovations": best[4], "validation_subjects": split["validation"],
                               "test_subjects_untouched": split["test"],
                               "encoder_version": version,
                               "encoder_sha256": hashlib.sha256(Path(args.encoder).read_bytes()).hexdigest()})
            else:
                config["tuning_note"] = "No usable validation innovations; retained starting values."
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(config, indent=2))
    elif args.command == "train_heads":
        if args.labels and args.trajectories:
            labels = read_labels(args.labels)
            rows = [json.loads(line) for line in Path(args.trajectories).read_text(encoding="utf-8").splitlines() if line.strip()]
            artifact = train_ridge_heads(rows, labels, seed=17)
        else:
            artifact = {"schema_version": "symptom-heads-v1", "mode": "research_labeled", "heads": {},
                        "status": "unavailable", "reason": "Supply both --labels and --trajectories; synthetic labels do not enable clinical heads.",
                        "clinical_validation": False}
        write_heads(args.output, artifact)
        print(json.dumps(artifact, indent=2))
    elif args.command == "evaluate":
        rows = read_observations(args.input)
        report = {"dataset_fingerprint": dataset_fingerprint(rows),
                  "subjects": len({row.subject_id for row in rows}), "rows": len(rows), "status": "insufficient_evidence",
                  "reconstruction": "not run; supply a trained checkpoint", "held_out_symptom_metrics": "unavailable without supported real labels",
                  "clinical_validity": "not established", "device_population_shift": "not assessed"}
        if args.labels:
            labels = read_labels(args.labels)
            report["label_counts_by_target"] = {target: sum(label.target == target for label in labels)
                                                for target in sorted({label.target for label in labels})}
        if args.encoder:
            daily = aggregate_daily(rows, max(item.available_at_utc for item in rows))
            split = subject_split((row.subject_id for row in daily), seed=17)
            training = [row for row in daily if row.subject_id in split["train"]]
            testing = [row for row in daily if row.subject_id in split["test"]]
            train_x, train_mask = feature_matrix(training)
            test_x, test_mask = feature_matrix(testing)
            model, scaler_mean, scaler_scale, encoder_version = load_encoder(args.encoder)
            _, autoencoder_error = embed(model, test_x, test_mask, scaler_mean, scaler_scale)
            pca = fit_pca_baseline(train_x, train_mask, model.latent_dim)
            pca_latents, pca_error = pca_baseline(test_x, test_mask, pca)
            autoencoder_latents, _ = embed(model, test_x, test_mask, scaler_mean, scaler_scale)
            filter_config = json.loads(Path(args.filter_config).read_text(encoding="utf-8")) if args.filter_config else {}
            encoder_hash = hashlib.sha256(Path(args.encoder).read_bytes()).hexdigest()
            if filter_config.get("encoder_sha256") not in {None, encoder_hash}:
                raise ValueError("filter configuration was tuned for a different encoder artifact")
            auto_residuals, auto_covariances, pca_residuals, pca_covariances = [], [], [], []
            raw_errors, ema_errors = [], []
            row_indices = {subject: [index for index, row in enumerate(testing) if row.subject_id == subject]
                           for subject in split["test"]}
            for subject in split["test"]:
                indices = row_indices[subject]
                subject_rows = [testing[index] for index in indices]
                z_sequence = autoencoder_latents[indices]
                p_sequence = pca_latents[indices]
                for values, residual_groups, covariance_groups, collect_baselines in (
                    (z_sequence, auto_residuals, auto_covariances, True),
                    (p_sequence, pca_residuals, pca_covariances, False),
                ):
                    core = LocalTrendFilter(values.shape[1], float(filter_config.get("process_level", 0.02)),
                                            float(filter_config.get("process_velocity", 0.005)),
                                            float(filter_config.get("observation_variance", 0.15)),
                                            float(filter_config.get("long_gap_reset_days", 30)),
                                            encoder_version, float(filter_config.get("quality_r_inflation_max", 4.0)))
                    state, residual_list, covariance_list = None, [], []
                    prior_raw = prior_ema = None
                    for row, value in zip(subject_rows, values):
                        usable = row.coverage >= 0.25
                        timestamp = datetime.fromisoformat(row.day_utc).replace(tzinfo=timezone.utc)
                        state, detail = core.step(subject, timestamp, value if usable else None, state,
                                                  quality=max(0.05, row.coverage))
                        if not usable:
                            continue
                        if detail.get("innovation") is not None:
                            residual_list.append(detail["innovation"])
                            covariance_list.append(detail["innovation_covariance"])
                        if collect_baselines and prior_raw is not None:
                            raw_errors.append(value - prior_raw)
                            ema_errors.append(value - prior_ema)
                        prior_raw = value.copy()
                        prior_ema = value.copy() if prior_ema is None else 0.25 * value + 0.75 * prior_ema
                    if residual_list:
                        residual_groups.append((np.asarray(residual_list), np.asarray(covariance_list)))
            report["trajectory_diagnostics"] = {
                "autoencoder_kalman": innovation_diagnostics(auto_residuals),
                "pca_kalman": innovation_diagnostics(pca_residuals),
                "raw_embedding_one_step_rmse": float(np.sqrt(np.mean(np.asarray(raw_errors) ** 2))) if raw_errors else None,
                "exponential_smoothing_one_step_rmse_alpha_0_25": float(np.sqrt(np.mean(np.asarray(ema_errors) ** 2))) if ema_errors else None,
                "response_lag": "not estimated; no independent known latent trajectory in this dataset",
                "comparison_note": "PCA and autoencoder coordinates are distinct; results are descriptive and do not establish a winner or clinical validity."
            }
            report.update({"status": "participant_held_out_reconstruction_only",
                           "reconstruction": {"autoencoder_observed_rmse": float(np.mean(autoencoder_error)),
                                              "pca_observed_rmse": float(np.mean(pca_error)),
                                              "test_rows": len(testing), "test_subjects": split["test"],
                                              "training_subjects": split["train"], "encoder_version": encoder_version},
                           "input_coverage_rate": float(np.mean([row.coverage >= 0.25 for row in testing])) if testing else None,
                           "simulated_data_only": all(item.context.get("simulated") for item in rows)})
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report, indent=2))
    else:
        observations = read_observations(args.input)
        config = json.loads(Path(args.config).read_text(encoding="utf-8")) if Path(args.config).exists() else {}
        head_artifact = json.loads(Path(args.heads).read_text(encoding="utf-8")) if args.heads else None
        results = replay_subject(args.subject, observations, args.encoder, config, head_artifact)
        save_replay(args.output, results)
        print(json.dumps({"output": args.output, "windows": len(results), "mode": "exploratory",
                          "symptom_heads": "null: no supported trained labels supplied"}))


if __name__ == "__main__":
    main()
