from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import mysql.connector
from flask import Flask, flash, redirect, render_template, request, url_for

from db_config import DB_CONFIG

RULES_TABLE = "anfis_rules"
CONTINUOUS_KEYS = ("age", "trestbps", "chol", "thalach", "oldpeak")
FIELD_LABELS = {
    "age": "Tuổi (age)",
    "trestbps": "Huyết áp lúc nghỉ (trestbps)",
    "chol": "Cholesterol (chol)",
    "thalach": "Nhịp tim tối đa (thalach)",
    "oldpeak": "ST depression (oldpeak)",
}


@dataclass
class RuleView:
    rule_no: int
    age: str
    trestbps: str
    chol: str
    thalach: str
    oldpeak: str
    consequent_text: str


class RuleManager:
    def _conn(self):
        return mysql.connector.connect(**DB_CONFIG)

    def fetch_rules(self) -> list[RuleView]:
        conn = self._conn()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            f"""
            SELECT rule_no, age, trestbps, chol, thalach, oldpeak, consequent_text
            FROM {RULES_TABLE}
            ORDER BY rule_no
            """
        )
        rows = [RuleView(**row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return rows

    def rule_form_options(self) -> dict[str, list[tuple[str, str]]]:
        return {
            "age": [("Not used", "Không dùng"), ("young", "young"), ("old", "old")],
            "trestbps": [("Not used", "Không dùng"), ("low", "low"), ("high", "high")],
            "chol": [("Not used", "Không dùng"), ("low", "low"), ("high", "high")],
            "thalach": [("Not used", "Không dùng"), ("low", "low"), ("high", "high")],
            "oldpeak": [("Not used", "Không dùng"), ("low", "low"), ("high", "high")],
        }

    def consequent_feature_choices(self) -> list[tuple[str, str]]:
        return [
            ("age", "Tuổi (age)"),
            ("trestbps", "Huyết áp lúc nghỉ (trestbps)"),
            ("chol", "Cholesterol (chol)"),
            ("thalach", "Nhịp tim tối đa (thalach)"),
            ("oldpeak", "ST depression (oldpeak)"),
        ]

    def next_rule_no(self) -> int:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(f"SELECT COALESCE(MAX(rule_no), 0) FROM {RULES_TABLE}")
        max_no = int(cur.fetchone()[0])
        cur.close()
        conn.close()
        return max_no + 1

    def extract_consequent_vars(self, consequent_text: str) -> list[str]:
        rhs = consequent_text.split("=", maxsplit=1)[1].strip() if "=" in consequent_text else consequent_text
        vars_used: list[str] = []
        for term in [t.strip() for t in rhs.split("+")]:
            if "*" in term:
                feat = term.split("*", maxsplit=1)[1].strip()
                if feat in CONTINUOUS_KEYS and feat not in vars_used:
                    vars_used.append(feat)
        return vars_used

    def get_consequent_vars_for_rule(self, rule_no: int) -> list[str]:
        conn = self._conn()
        cur = conn.cursor(dictionary=True)
        cur.execute(f"SELECT consequent_text FROM {RULES_TABLE} WHERE rule_no=%s", (rule_no,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row:
            return []
        return self.extract_consequent_vars(str(row["consequent_text"]))

    def parse_rule_form(self, form_data, rule_no: int | None = None) -> dict[str, Any]:
        fields = ("age", "trestbps", "chol", "thalach", "oldpeak")
        payload: dict[str, Any] = {f: str(form_data.get(f, "Not used")).strip() or "Not used" for f in fields}
        selected_vars = [v for v in form_data.getlist("consequent_vars") if v in CONTINUOUS_KEYS]
        selected_vars = list(dict.fromkeys(selected_vars))
        if rule_no is None:
            payload["rule_no"] = self.next_rule_no()
        else:
            payload["rule_no"] = int(rule_no)
            if not selected_vars:
                selected_vars = self.get_consequent_vars_for_rule(payload["rule_no"])

        payload["consequent_text"] = self.auto_build_consequent(payload["rule_no"], selected_vars)
        return payload

    def auto_build_consequent(self, rule_no: int, vars_used: list[str]) -> str:
        param_names = ["p", "q", "r", "s", "t", "u", "v"]
        terms: list[str] = []
        for i, var in enumerate(vars_used):
            pname = param_names[i] if i < len(param_names) else f"p{i + 1}"
            terms.append(f"{pname}{rule_no}*{var}")
        terms.append(f"s{rule_no}")
        return f"f{rule_no} = " + " + ".join(terms)

    def insert_rule(self, payload: dict[str, Any]) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            f"""
            INSERT INTO {RULES_TABLE} (
                rule_no, age, trestbps, chol, thalach, oldpeak, consequent_text
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                payload["rule_no"],
                payload["age"],
                payload["trestbps"],
                payload["chol"],
                payload["thalach"],
                payload["oldpeak"],
                payload["consequent_text"],
            ),
        )
        conn.commit()
        cur.close()
        conn.close()

    def update_rule(self, rule_no: int, payload: dict[str, Any]) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            f"""
            UPDATE {RULES_TABLE}
            SET age=%s, trestbps=%s, chol=%s, thalach=%s, oldpeak=%s, consequent_text=%s
            WHERE rule_no=%s
            """,
            (
                payload["age"],
                payload["trestbps"],
                payload["chol"],
                payload["thalach"],
                payload["oldpeak"],
                payload["consequent_text"],
                rule_no,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()

    def delete_rule(self, rule_no: int) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {RULES_TABLE} WHERE rule_no=%s", (rule_no,))
        conn.commit()
        cur.close()
        conn.close()

    def register_routes(self, app: Flask, login_required: Callable, role_required: Callable) -> None:
        @app.route("/admin/rules")
        @login_required
        @role_required("admin")
        def admin_rules():
            rows = self.fetch_rules()
            return render_template(
                "admin_rules.html",
                rules=rows,
                options=self.rule_form_options(),
                field_labels=FIELD_LABELS,
                consequent_choices=self.consequent_feature_choices(),
                next_rule_no=self.next_rule_no(),
            )

        @app.route("/admin/rules/add", methods=["POST"])
        @login_required
        @role_required("admin")
        def admin_rules_add():
            try:
                payload = self.parse_rule_form(request.form)
                self.insert_rule(payload)
                flash("Thêm luật thành công.", "success")
            except Exception as exc:  # noqa: BLE001
                flash(f"Thêm luật thất bại: {exc}", "error")
            return redirect(url_for("admin_rules"))

        @app.route("/admin/rules/<int:rule_no>/edit", methods=["POST"])
        @login_required
        @role_required("admin")
        def admin_rules_edit(rule_no: int):
            try:
                payload = self.parse_rule_form(request.form, rule_no=rule_no)
                self.update_rule(rule_no, payload)
                flash("Cập nhật luật thành công.", "success")
            except Exception as exc:  # noqa: BLE001
                flash(f"Cập nhật luật thất bại: {exc}", "error")
            return redirect(url_for("admin_rules"))

        @app.route("/admin/rules/<int:rule_no>/delete", methods=["POST"])
        @login_required
        @role_required("admin")
        def admin_rules_delete(rule_no: int):
            try:
                self.delete_rule(rule_no)
                flash("Xóa luật thành công.", "success")
            except Exception as exc:  # noqa: BLE001
                flash(f"Xóa luật thất bại: {exc}", "error")
            return redirect(url_for("admin_rules"))
