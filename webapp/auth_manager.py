from __future__ import annotations

from functools import wraps
from typing import Callable

import mysql.connector
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db_config import DB_CONFIG

USERS_TABLE = "web_users"


class AuthManager:
    def _conn(self):
        return mysql.connector.connect(**DB_CONFIG)

    def init_user_table(self) -> None:
        conn = self._conn()
        cur = conn.cursor()
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {USERS_TABLE} (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(64) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(16) NOT NULL
            )
            """
        )

        defaults = [
            ("admin", "admin123", "admin"),
            ("bacsi", "doctor123", "doctor"),
            ("doctor2", "doctor123", "doctor"),
        ]
        for username, password, role in defaults:
            cur.execute(f"SELECT id FROM {USERS_TABLE} WHERE username = %s", (username,))
            if cur.fetchone() is None:
                cur.execute(
                    f"INSERT INTO {USERS_TABLE} (username, password_hash, role) VALUES (%s, %s, %s)",
                    (username, generate_password_hash(password), role),
                )
        conn.commit()
        cur.close()
        conn.close()

    def get_user_by_username(self, username: str) -> dict | None:
        conn = self._conn()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            f"SELECT id, username, password_hash, role FROM {USERS_TABLE} WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row

    def login_required(self, fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("login"))
            return fn(*args, **kwargs)

        return wrapper

    def role_required(self, *roles: str):
        def decorator(fn: Callable):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                if "user_id" not in session:
                    return redirect(url_for("login"))
                if session.get("role") not in roles:
                    flash("Bạn không có quyền truy cập chức năng này.", "error")
                    return redirect(url_for("doctor_dashboard"))
                return fn(*args, **kwargs)

            return wrapper

        return decorator

    def register_routes(self, app: Flask) -> None:
        @app.route("/login", methods=["GET", "POST"])
        def login():
            if request.method == "POST":
                username = request.form.get("username", "").strip()
                password = request.form.get("password", "")
                user = self.get_user_by_username(username)
                if user and check_password_hash(user["password_hash"], password):
                    session["user_id"] = user["id"]
                    session["username"] = user["username"]
                    session["role"] = user["role"]
                    flash("Đăng nhập thành công.", "success")
                    return redirect(url_for("index"))
                flash("Sai tên đăng nhập hoặc mật khẩu.", "error")
            return render_template("login.html")

        @app.route("/logout")
        def logout():
            session.clear()
            flash("Bạn đã đăng xuất.", "success")
            return redirect(url_for("login"))
