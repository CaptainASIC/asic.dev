"""SEEDED VULNERABLE FIXTURE — do not fix, do not import, do not run.

Intentionally insecure code used only by evals/run_evals.py and the Snyk gate
eval to prove the gate flags a HIGH-severity finding. Untrusted HTTP request
input (a high-trust-risk taint source for Snyk Code) flows into injection sinks,
which Snyk Code rates HIGH — unlike the same sinks fed from argv, which rate
MEDIUM.
"""

import os
import sqlite3

from flask import Flask, request

app = Flask(__name__)


@app.route("/run")
def run_expr() -> str:
    """Code injection: untrusted HTTP input evaluated as Python (CWE-94)."""
    # Reason: eval of attacker-controlled request data is a textbook high sink.
    return str(eval(request.args.get("expr", "")))  # noqa: S307


@app.route("/ping")
def ping_host() -> str:
    """OS command injection: untrusted HTTP input into a shell command (CWE-78)."""
    host = request.args.get("host", "")
    return str(os.system("ping -c 1 " + host))  # noqa: S605


@app.route("/user")
def find_user() -> list:
    """SQL injection: untrusted HTTP input concatenated into a query (CWE-89)."""
    user_id = request.args.get("id", "")
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = '" + user_id + "'")  # noqa: S608
    return cur.fetchall()
