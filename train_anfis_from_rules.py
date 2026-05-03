"""Hybrid-learning ANFIS with Gaussian membership + k-fold CV + early stopping."""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import mysql.connector
import numpy as np

from db_config import DB_CONFIG

DATA_TABLE = "processed_heart_disease_normalized"
RULES_TABLE = "anfis_rules"
PARAMS_TABLE = "anfis_consequents"
MODELS_DIR = Path("models")
METRICS_DIR = Path("metrics")

EPOCHS = 80
LEARNING_RATE = 0.01
MIN_SIGMA = 1e-4
EPS = 1e-12
K_FOLDS = 5
RANDOM_SEED = 42
EARLY_STOP_MIN_DELTA = 1e-6
EARLY_STOP_PATIENCE = 12

FuzzyLabel = Literal["young", "old", "low", "high"]


@dataclass
class Condition:
    variable: str
    label: str


@dataclass
class Rule:
    rule_no: int
    antecedents: list[Condition]
    consequent_vars: list[str]
    has_bias: bool
    consequent_text: str


@dataclass
class FoldTrainResult:
    fold_idx: int
    best_epoch: int
    best_val_mse: float
    best_train_mse: float
    theta: np.ndarray
    fuzzy_params: dict[str, dict[FuzzyLabel, dict[str, float]]]
    mse_history: list[tuple[int, float, float]]


def mu_gaussian(x: float, center: float, sigma: float) -> tuple[float, float, float]:
    """Return mu, dmu/dcenter, dmu/dsigma for Gaussian membership."""
    sigma = max(sigma, MIN_SIGMA)
    diff = x - center
    inv_sigma2 = 1.0 / (sigma * sigma)
    mu = float(np.exp(-0.5 * diff * diff * inv_sigma2))
    dmu_dc = mu * (diff * inv_sigma2)
    dmu_dsigma = mu * ((diff * diff) / (sigma**3))
    return mu, dmu_dc, dmu_dsigma


def parse_consequent(consequent_text: str) -> tuple[list[str], bool]:
    consequent_vars: list[str] = []
    has_bias = False
    rhs = consequent_text.split("=", maxsplit=1)[1].strip()
    for term in [t.strip() for t in rhs.split("+")]:
        if "*" in term:
            consequent_vars.append(term.split("*", maxsplit=1)[1].strip())
        else:
            has_bias = True
    return consequent_vars, has_bias


def load_rules_from_db() -> list[Rule]:
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)
    cur.execute(
        f"""
        SELECT rule_no, age, trestbps, chol, thalach, oldpeak, consequent_text
        FROM {RULES_TABLE}
        ORDER BY rule_no
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    rules: list[Rule] = []
    for rr in rows:
        ants: list[Condition] = []
        for var in ("age", "trestbps", "chol", "thalach", "oldpeak"):
            val = str(rr[var]).strip()
            if val != "Not used":
                ants.append(Condition(variable=var, label=val.lower()))

        consequent_text = str(rr["consequent_text"])
        cvars, has_bias = parse_consequent(consequent_text)
        rules.append(
            Rule(
                rule_no=int(rr["rule_no"]),
                antecedents=ants,
                consequent_vars=cvars,
                has_bias=has_bias,
                consequent_text=consequent_text,
            )
        )
    return rules


def fetch_dataset() -> list[dict]:
    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor(dictionary=True)
    cur.execute(
        f"""
        SELECT id, age, trestbps, chol, thalach, oldpeak, num
        FROM {DATA_TABLE}
        ORDER BY id
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def init_fuzzy_params(rows: list[dict]) -> dict[str, dict[FuzzyLabel, dict[str, float]]]:
    def vals(col: str) -> np.ndarray:
        return np.asarray([float(r[col]) for r in rows], dtype=float)

    params: dict[str, dict[FuzzyLabel, dict[str, float]]] = {}
    age = vals("age")
    a20, a80 = np.percentile(age, [20, 80])
    a_std = max(float(np.std(age)), 0.05)
    params["age"] = {
        "young": {"a": float(a20), "b": a_std},
        "old": {"a": float(a80), "b": a_std},
    }

    for col in ("trestbps", "chol", "thalach", "oldpeak"):
        v = vals(col)
        q30, q70 = np.percentile(v, [30, 70])
        std = max(float(np.std(v)), 0.05)
        params[col] = {
            "low": {"a": float(q30), "b": std},
            "high": {"a": float(q70), "b": std},
        }
    return params


def compute_rule_strengths(
    row: dict,
    rules: list[Rule],
    fuzzy_params: dict[str, dict[FuzzyLabel, dict[str, float]]],
) -> tuple[list[float], list[list[tuple[str, str, float, float, float]]]]:
    strengths: list[float] = []
    fuzzy_cache: list[list[tuple[str, str, float, float, float]]] = []
    for rule in rules:
        w = 1.0
        cache: list[tuple[str, str, float, float, float]] = []
        for cond in rule.antecedents:
            p = fuzzy_params[cond.variable][cond.label]  # type: ignore[index]
            mu, dmu_da, dmu_db = mu_gaussian(float(row[cond.variable]), p["a"], p["b"])
            w *= mu
            cache.append((cond.variable, cond.label, mu, dmu_da, dmu_db))
        strengths.append(w)
        fuzzy_cache.append(cache)
    return strengths, fuzzy_cache


def normalized_weights(ws: list[float]) -> list[float]:
    s = sum(ws)
    if s <= EPS:
        return [0.0 for _ in ws]
    return [w / s for w in ws]


def consequent_segments(rules: list[Rule], theta: np.ndarray) -> list[np.ndarray]:
    segs: list[np.ndarray] = []
    idx = 0
    for r in rules:
        n = len(r.consequent_vars) + (1 if r.has_bias else 0)
        segs.append(theta[idx : idx + n])
        idx += n
    return segs


def rule_output(row: dict, rule: Rule, seg: np.ndarray) -> float:
    k = 0
    out = 0.0
    for v in rule.consequent_vars:
        out += float(seg[k]) * float(row[v])
        k += 1
    if rule.has_bias:
        out += float(seg[k])
    return out


def build_design_matrix(
    rows: list[dict],
    rules: list[Rule],
    fuzzy_params: dict[str, dict[FuzzyLabel, dict[str, float]]],
) -> tuple[np.ndarray, np.ndarray]:
    a_rows: list[list[float]] = []
    y_rows: list[float] = []
    for row in rows:
        ws, _ = compute_rule_strengths(row, rules, fuzzy_params)
        nws = normalized_weights(ws)
        feat: list[float] = []
        for i, rule in enumerate(rules):
            w = nws[i]
            for var in rule.consequent_vars:
                feat.append(w * float(row[var]))
            if rule.has_bias:
                feat.append(w)
        a_rows.append(feat)
        y_rows.append(float(row["num"]))
    return np.asarray(a_rows, dtype=float), np.asarray(y_rows, dtype=float)


def fit_lse(a: np.ndarray, y: np.ndarray) -> np.ndarray:
    return np.linalg.pinv(a) @ y


def predict_rows(
    rows: list[dict],
    rules: list[Rule],
    fuzzy_params: dict[str, dict[FuzzyLabel, dict[str, float]]],
    theta: np.ndarray,
) -> np.ndarray:
    segs = consequent_segments(rules, theta)
    preds: list[float] = []
    for row in rows:
        ws, _ = compute_rule_strengths(row, rules, fuzzy_params)
        wsum = sum(ws)
        fs = [rule_output(row, rules[i], segs[i]) for i in range(len(rules))]
        if wsum <= EPS:
            preds.append(float(np.mean(fs)) if fs else 0.0)
        else:
            preds.append(sum(ws[i] * fs[i] for i in range(len(rules))) / wsum)
    return np.asarray(preds, dtype=float)


def mse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean((y_true - y_pred) ** 2))


def update_premise_params(
    rows: list[dict],
    rules: list[Rule],
    fuzzy_params: dict[str, dict[FuzzyLabel, dict[str, float]]],
    theta: np.ndarray,
    lr: float,
) -> None:
    segs = consequent_segments(rules, theta)
    grads: dict[tuple[str, str, str], float] = {}

    for row in rows:
        target = float(row["num"])
        ws, fuzzy_cache = compute_rule_strengths(row, rules, fuzzy_params)
        wsum = sum(ws)
        if wsum <= EPS:
            continue
        fs = [rule_output(row, rules[i], segs[i]) for i in range(len(rules))]
        yhat = sum(ws[i] * fs[i] for i in range(len(rules))) / wsum
        dL_dy = yhat - target

        for i in range(len(rules)):
            wi = ws[i]
            dy_dwi = (fs[i] - yhat) / wsum
            if abs(dy_dwi) <= EPS:
                continue
            for (var, label, mu, dmu_da, dmu_db) in fuzzy_cache[i]:
                if mu <= EPS:
                    continue
                dwi_dmu = wi / mu
                common = dL_dy * dy_dwi * dwi_dmu
                grads[(var, label, "a")] = grads.get((var, label, "a"), 0.0) + common * dmu_da
                grads[(var, label, "b")] = grads.get((var, label, "b"), 0.0) + common * dmu_db

    n = max(len(rows), 1)
    for var in fuzzy_params:
        for label in fuzzy_params[var]:
            ga = grads.get((var, label, "a"), 0.0) / n
            gb = grads.get((var, label, "b"), 0.0) / n
            fuzzy_params[var][label]["a"] -= lr * ga
            fuzzy_params[var][label]["b"] = max(MIN_SIGMA, fuzzy_params[var][label]["b"] - lr * gb)


def kfold_indices(n_samples: int, k: int, seed: int) -> list[tuple[np.ndarray, np.ndarray]]:
    rng = np.random.default_rng(seed)
    idx = np.arange(n_samples)
    rng.shuffle(idx)
    folds = np.array_split(idx, k)
    out: list[tuple[np.ndarray, np.ndarray]] = []
    for i in range(k):
        val_idx = folds[i]
        train_idx = np.concatenate([folds[j] for j in range(k) if j != i])
        out.append((train_idx, val_idx))
    return out


def train_one_fold(
    fold_idx: int,
    train_rows: list[dict],
    val_rows: list[dict],
    rules: list[Rule],
) -> FoldTrainResult:
    fuzzy_params = init_fuzzy_params(train_rows)
    n_params = sum(len(r.consequent_vars) + (1 if r.has_bias else 0) for r in rules)
    theta = np.zeros(n_params, dtype=float)

    best_val = float("inf")
    best_epoch = 0
    best_train = float("inf")
    wait = 0
    best_theta = theta.copy()
    best_fuzzy = copy.deepcopy(fuzzy_params)
    history: list[tuple[int, float, float]] = []

    for epoch in range(1, EPOCHS + 1):
        a_train, y_train = build_design_matrix(train_rows, rules, fuzzy_params)
        theta = fit_lse(a_train, y_train)
        train_pred = predict_rows(train_rows, rules, fuzzy_params, theta)
        val_pred = predict_rows(val_rows, rules, fuzzy_params, theta)
        train_m = mse(y_train, train_pred)
        val_m = mse(np.asarray([float(r["num"]) for r in val_rows]), val_pred)
        history.append((epoch, train_m, val_m))

        if val_m < best_val - EARLY_STOP_MIN_DELTA:
            best_val = val_m
            best_train = train_m
            best_epoch = epoch
            wait = 0
            best_theta = theta.copy()
            best_fuzzy = copy.deepcopy(fuzzy_params)
        else:
            wait += 1

        print(
            f"Fold {fold_idx+1}/{K_FOLDS} | Epoch {epoch:02d}/{EPOCHS} | "
            f"train_mse={train_m:.6f} | val_mse={val_m:.6f}"
        )

        if wait >= EARLY_STOP_PATIENCE:
            print(
                f"Fold {fold_idx+1}: early stop at epoch {epoch}, "
                f"best epoch {best_epoch} (val_mse={best_val:.6f})"
            )
            break

        update_premise_params(train_rows, rules, fuzzy_params, theta, LEARNING_RATE)

    return FoldTrainResult(
        fold_idx=fold_idx,
        best_epoch=best_epoch,
        best_val_mse=best_val,
        best_train_mse=best_train,
        theta=best_theta,
        fuzzy_params=best_fuzzy,
        mse_history=history,
    )


def save_params_to_db_and_file(
    rules: list[Rule],
    best_result: FoldTrainResult,
    cv_mean_val_mse: float,
    cv_std_val_mse: float,
) -> None:
    theta = best_result.theta
    fuzzy_params = best_result.fuzzy_params

    conn = mysql.connector.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(f"DROP TABLE IF EXISTS {PARAMS_TABLE}")
    cur.execute(
        f"""
        CREATE TABLE {PARAMS_TABLE} (
            rule_no INT NOT NULL,
            param_order INT NOT NULL,
            param_name VARCHAR(64) NOT NULL,
            feature_name VARCHAR(64) NOT NULL,
            value DOUBLE NOT NULL
        )
        """
    )

    rows_to_insert: list[tuple] = []
    idx = 0
    for rule in rules:
        rhs = rule.consequent_text.split("=", maxsplit=1)[1].strip()
        terms = [t.strip() for t in rhs.split("+")]
        ordered: list[tuple[str, str]] = []
        for t in terms:
            if "*" in t:
                p_name, feat = t.split("*", maxsplit=1)
                ordered.append((p_name.strip(), feat.strip()))
            else:
                ordered.append((t.strip(), "bias"))
        for p_order, (p_name, feat) in enumerate(ordered, start=1):
            rows_to_insert.append((rule.rule_no, p_order, p_name, feat, float(theta[idx])))
            idx += 1

    cur.executemany(
        f"""
        INSERT INTO {PARAMS_TABLE} (rule_no, param_order, param_name, feature_name, value)
        VALUES (%s, %s, %s, %s, %s)
        """,
        rows_to_insert,
    )
    conn.commit()
    cur.close()
    conn.close()

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    model = {
        "data_table": DATA_TABLE,
        "membership": "gaussian",
        "cv": {
            "k_folds": K_FOLDS,
            "mean_val_mse": cv_mean_val_mse,
            "std_val_mse": cv_std_val_mse,
            "best_fold": best_result.fold_idx + 1,
            "best_epoch": best_result.best_epoch,
            "best_val_mse": best_result.best_val_mse,
        },
        "fuzzy_params": {
            var: {label: {"a": float(p["a"]), "b": float(p["b"])} for label, p in labels.items()}
            for var, labels in fuzzy_params.items()
        },
        "rules": [
            {
                "rule_no": r.rule_no,
                "antecedents": [{"variable": c.variable, "label": c.label} for c in r.antecedents],
                "consequent_text": r.consequent_text,
            }
            for r in rules
        ],
        "theta": [float(v) for v in theta.tolist()],
    }
    (MODELS_DIR / "anfis_model_latest.json").write_text(
        json.dumps(model, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_cv_metrics(results: list[FoldTrainResult]) -> None:
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    lines = ["fold,best_epoch,best_train_mse,best_val_mse"]
    for r in results:
        lines.append(f"{r.fold_idx+1},{r.best_epoch},{r.best_train_mse:.10f},{r.best_val_mse:.10f}")
    (METRICS_DIR / "anfis_kfold_summary.csv").write_text("\n".join(lines), encoding="utf-8")

    for r in results:
        lines_hist = ["epoch,train_mse,val_mse"] + [
            f"{ep},{tr:.10f},{va:.10f}" for ep, tr, va in r.mse_history
        ]
        (METRICS_DIR / f"anfis_fold_{r.fold_idx+1}_history.csv").write_text(
            "\n".join(lines_hist),
            encoding="utf-8",
        )


def main() -> None:
    rules = load_rules_from_db()
    if not rules:
        raise ValueError("Khong tim thay luat trong bang anfis_rules. Hay chay manage_anfis_rules.py truoc.")
    rows = fetch_dataset()
    if len(rows) < K_FOLDS:
        raise ValueError(f"So mau ({len(rows)}) nho hon K_FOLDS ({K_FOLDS}).")

    splits = kfold_indices(len(rows), K_FOLDS, RANDOM_SEED)
    results: list[FoldTrainResult] = []
    for fold_idx, (train_idx, val_idx) in enumerate(splits):
        train_rows = [rows[int(i)] for i in train_idx]
        val_rows = [rows[int(i)] for i in val_idx]
        result = train_one_fold(fold_idx, train_rows, val_rows, rules)
        results.append(result)

    val_mses = np.asarray([r.best_val_mse for r in results], dtype=float)
    cv_mean = float(np.mean(val_mses))
    cv_std = float(np.std(val_mses))
    best_result = min(results, key=lambda r: r.best_val_mse)

    save_params_to_db_and_file(rules, best_result, cv_mean, cv_std)
    save_cv_metrics(results)

    print(f"Loaded rules: {len(rules)}")
    print(f"Total rows: {len(rows)}")
    print(f"CV val MSE mean/std: {cv_mean:.6f} / {cv_std:.6f}")
    print(
        f"Selected best fold: {best_result.fold_idx+1} "
        f"(epoch {best_result.best_epoch}, val_mse={best_result.best_val_mse:.6f})"
    )
    print(f"Saved DB table: {PARAMS_TABLE} (best fold model)")
    print("Saved model file: models/anfis_model_latest.json")
    print("Saved metrics: metrics/anfis_kfold_summary.csv and metrics/anfis_fold_<k>_history.csv")


if __name__ == "__main__":
    main()
