from __future__ import annotations

import base64
import io
import json
import math
from pathlib import Path
from typing import Any, Callable

import matplotlib
from flask import Flask, flash, render_template, request

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

MODEL_PATH = Path("models") / "anfis_model_latest.json"
NORM_STATS_PATH = Path("models") / "normalization_stats.json"
RISK_LABELS = {
    0: "Không bệnh",
    1: "Nguy cơ rất thấp",
    2: "Nguy cơ thấp",
    3: "Nguy cơ trung bình",
    4: "Nguy cơ cao",
}
CONTINUOUS_KEYS = ("age", "trestbps", "chol", "thalach", "oldpeak")


class PredictionManager:
    def __init__(self) -> None:
        self.model = self._load_model()
        self.norm_stats = self._load_norm_stats()

    @staticmethod
    def zscore(x: float, mean: float, std: float) -> float:
        if std == 0:
            return 0.0
        return (x - mean) / std

    @staticmethod
    def gaussian_mu(x: float, a: float, b: float) -> float:
        b = max(b, 1e-9)
        return math.exp(-0.5 * ((x - a) ** 2) / (b * b))

    def _load_model(self) -> dict:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp mô hình: {MODEL_PATH}")
        with MODEL_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _load_norm_stats(self) -> dict:
        if not NORM_STATS_PATH.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp thống kê chuẩn hóa: {NORM_STATS_PATH}")
        with NORM_STATS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if data.get("method") != "zscore":
            raise ValueError("Ứng dụng web yêu cầu thống kê chuẩn hóa z-score.")
        return data

    def collect_raw_inputs(self, form_data) -> dict[str, float]:
        out: dict[str, float] = {}
        for key in CONTINUOUS_KEYS:
            text = str(form_data.get(key, "")).strip()
            if not text:
                raise ValueError(f"Thiếu giá trị: {key}")
            out[key] = float(text)
        return out

    def normalize_and_encode_inputs(self, raw: dict[str, float]) -> dict[str, float]:
        x: dict[str, float] = {}
        for key in CONTINUOUS_KEYS:
            mean_v = float(self.norm_stats["continuous"][key]["mean"])
            std_v = float(self.norm_stats["continuous"][key]["std"])
            x[key] = self.zscore(raw[key], mean_v, std_v)
        return x

    def rule_output(self, rule: dict, seg: list[float], x: dict[str, float]) -> float:
        rhs = rule["consequent_text"].split("=", maxsplit=1)[1].strip()
        terms = [t.strip() for t in rhs.split("+")]
        out = 0.0
        i = 0
        for t in terms:
            if "*" in t:
                feat = t.split("*", maxsplit=1)[1].strip()
                out += seg[i] * float(x[feat])
            else:
                out += seg[i]
            i += 1
        return out

    def infer(self, x: dict[str, float]) -> tuple[float, list[float]]:
        rules = self.model["rules"]
        theta = self.model["theta"]
        fuzzy_params = self.model["fuzzy_params"]

        segs: list[list[float]] = []
        idx = 0
        for r in rules:
            n_terms = len([t for t in r["consequent_text"].split("=", 1)[1].split("+") if t.strip()])
            segs.append(theta[idx : idx + n_terms])
            idx += n_terms

        weights: list[float] = []
        fs: list[float] = []
        for r, seg in zip(rules, segs):
            w = 1.0
            for c in r["antecedents"]:
                p = fuzzy_params[c["variable"]][c["label"]]
                w *= self.gaussian_mu(float(x[c["variable"]]), float(p["a"]), float(p["b"]))
            weights.append(w)
            fs.append(self.rule_output(r, seg, x))

        w_sum = sum(weights)
        if w_sum <= 1e-12:
            y_hat = sum(fs) / len(fs) if fs else 0.0
            norm_w = [0.0 for _ in weights]
        else:
            y_hat = sum(w * f for w, f in zip(weights, fs)) / w_sum
            norm_w = [w / w_sum for w in weights]
        contrib = [w * 100.0 for w in norm_w]
        return y_hat, contrib

    def format_consequent_with_params(self, rule: dict, seg: list[float]) -> str:
        lhs, rhs = [part.strip() for part in rule["consequent_text"].split("=", maxsplit=1)]
        terms = [t.strip() for t in rhs.split("+")]
        rendered: list[str] = []
        for i, t in enumerate(terms):
            coeff = seg[i]
            if "*" in t:
                feat = t.split("*", maxsplit=1)[1].strip()
                rendered.append(f"({coeff:.4f})*{feat}")
            else:
                rendered.append(f"({coeff:.4f})")
        return f"{lhs} = " + " + ".join(rendered)

    def build_rule_rows(self, contrib: list[float]) -> list[dict]:
        rules = self.model["rules"]
        theta = self.model["theta"]

        out: list[dict] = []
        for i, rule in enumerate(rules):
            seg_start = 0
            for j in range(i):
                n_prev = len([t for t in rules[j]["consequent_text"].split("=", 1)[1].split("+") if t.strip()])
                seg_start += n_prev
            n_terms = len([t for t in rule["consequent_text"].split("=", 1)[1].split("+") if t.strip()])
            seg = theta[seg_start : seg_start + n_terms]
            out.append(
                {
                    "rule_no": int(rule["rule_no"]),
                    "pct": float(contrib[i]),
                    "expr": self.format_consequent_with_params(rule, seg),
                }
            )
        out.sort(key=lambda r: r["pct"], reverse=True)
        return out

    def to_raw_ab(self, feature: str, a_norm: float, b_norm: float) -> tuple[float, float]:
        mean_v = float(self.norm_stats["continuous"][feature]["mean"])
        std_v = float(self.norm_stats["continuous"][feature]["std"])
        a_raw = mean_v + std_v * a_norm
        b_raw = abs(std_v * b_norm)
        return a_raw, b_raw

    def build_membership_images(self, raw_inputs: dict[str, float]) -> dict[str, str]:
        images: dict[str, str] = {}
        fuzzy_params = self.model["fuzzy_params"]
        for feature in fuzzy_params.keys():
            stats = self.norm_stats["continuous"].get(feature)
            if stats is None:
                continue
            mean_v = float(stats["mean"])
            std_v = float(stats["std"])
            mapped = []
            for label, p in fuzzy_params[feature].items():
                if feature == "age" and label not in {"young", "old"}:
                    continue
                a_raw, b_raw = self.to_raw_ab(feature, float(p["a"]), float(p["b"]))
                mapped.append((label, a_raw, b_raw))
            if not mapped:
                continue

            left = min(a - 3.0 * b for _, a, b in mapped)
            right = max(a + 3.0 * b for _, a, b in mapped)
            x_min = min(left, mean_v - 3.0 * std_v)
            x_max = max(right, mean_v + 3.0 * std_v)
            xs = [x_min + (x_max - x_min) * i / 399.0 for i in range(400)]

            fig = plt.figure(figsize=(7.5, 3.0))
            ax = fig.add_subplot(111)
            for label, a_raw, b_raw in mapped:
                ys = [self.gaussian_mu(x, a_raw, b_raw) for x in xs]
                ax.plot(xs, ys, label=f"{label}")
                ax.axvline(a_raw, linestyle="--", alpha=0.5)
                ax.annotate(
                    f"a={a_raw:.2f}",
                    xy=(a_raw, 1.06),
                    xytext=(6, -2),
                    textcoords="offset points",
                    fontsize=7,
                    va="bottom",
                    bbox={"boxstyle": "round,pad=0.15", "fc": "white", "alpha": 0.75},
                )
                ax.hlines(y=0.5, xmin=a_raw - b_raw, xmax=a_raw + b_raw, colors="gray", linestyles=":")
                ax.annotate(
                    f"b={b_raw:.2f}",
                    xy=(a_raw, 0.5),
                    xytext=(6, 4),
                    textcoords="offset points",
                    fontsize=7,
                    va="bottom",
                    bbox={"boxstyle": "round,pad=0.15", "fc": "white", "alpha": 0.75},
                )

            x_input = raw_inputs.get(feature)
            if x_input is not None:
                ax.axvline(x_input, color="red", linewidth=1.6)
                ax.annotate(
                    f"x={x_input:.2f}",
                    xy=(x_input, 0.03),
                    xytext=(4, 2),
                    textcoords="offset points",
                    fontsize=8,
                    va="bottom",
                    color="red",
                    bbox={"boxstyle": "round,pad=0.2", "fc": "white", "alpha": 0.8},
                )

            ax.set_title(f"Membership: {feature}")
            ax.set_xlabel("Giá trị gốc")
            ax.set_ylabel("μ")
            ax.set_ylim(-0.02, 1.12)
            ax.grid(alpha=0.2)
            ax.legend(loc="upper right", fontsize=8)
            fig.tight_layout()

            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=130)
            plt.close(fig)
            images[feature] = base64.b64encode(buf.getvalue()).decode("ascii")
        return images

    def register_routes(self, app: Flask, login_required: Callable, role_required: Callable) -> None:
        @app.route("/doctor", methods=["GET", "POST"])
        @login_required
        @role_required("doctor", "admin")
        def doctor_dashboard():
            prediction: dict[str, Any] | None = None
            chart_images: dict[str, str] = {}
            form_values: dict[str, str] = {
                "age": "",
                "trestbps": "",
                "chol": "",
                "thalach": "",
                "oldpeak": "",
            }

            if request.method == "POST":
                for key in form_values:
                    form_values[key] = str(request.form.get(key, form_values[key])).strip()
                try:
                    raw_inputs = self.collect_raw_inputs(request.form)
                    x = self.normalize_and_encode_inputs(raw_inputs)
                    y_hat, contrib = self.infer(x)
                    risk_score = max(0.0, y_hat)
                    level = max(0, min(4, int(round(risk_score))))
                    rule_rows = self.build_rule_rows(contrib)
                    chart_images = self.build_membership_images(raw_inputs)
                    prediction = {
                        "level": level,
                        "label": RISK_LABELS[level],
                        "risk_score": risk_score,
                        "rules": rule_rows,
                    }
                except Exception as exc:  # noqa: BLE001
                    flash(f"Lỗi xử lý dự đoán: {exc}", "error")

            return render_template(
                "doctor.html",
                prediction=prediction,
                charts=chart_images,
                form_values=form_values,
            )
