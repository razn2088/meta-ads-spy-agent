import json
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, redirect, render_template, request, url_for

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import CLIENTS_CONFIG_PATH, HISTORY_DIR
from modules.config_loader import load_clients

app = Flask(__name__)

# Track agent run status
agent_status = {
    "running": False,
    "last_run": None,
    "last_result": None,
}


def _read_config() -> list[dict]:
    if not CLIENTS_CONFIG_PATH.exists():
        return []
    with open(CLIENTS_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_config(data: list[dict]) -> None:
    CLIENTS_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CLIENTS_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _get_run_history(client_id: str) -> list[dict]:
    """Get scrape run history from SQLite for a client."""
    import sqlite3

    db_path = HISTORY_DIR / client_id / "ads.db"
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    cursor = conn.execute(
        "SELECT run_date, competitor_name, ads_found, status FROM scrape_runs ORDER BY run_date DESC LIMIT 20"
    )
    runs = [
        {"date": r[0], "competitor": r[1], "ads_found": r[2], "status": r[3]}
        for r in cursor.fetchall()
    ]
    conn.close()
    return runs


# ── Routes ──


@app.route("/")
def index():
    clients = _read_config()
    return render_template("index.html", clients=clients, agent_status=agent_status)


@app.route("/client/add", methods=["POST"])
def add_client():
    clients = _read_config()
    new_client = {
        "client_id": f"client_{int(datetime.now().timestamp())}",
        "client_name": request.form["client_name"].strip(),
        "whatsapp_group_name": request.form["whatsapp_group_name"].strip(),
        "competitors": [],
    }
    clients.append(new_client)
    _write_config(clients)
    return redirect(url_for("edit_client", client_id=new_client["client_id"]))


@app.route("/client/<client_id>")
def edit_client(client_id):
    clients = _read_config()
    client = next((c for c in clients if c["client_id"] == client_id), None)
    if not client:
        return redirect(url_for("index"))
    history = _get_run_history(client_id)
    return render_template("client.html", client=client, history=history)


@app.route("/client/<client_id>/update", methods=["POST"])
def update_client(client_id):
    clients = _read_config()
    client = next((c for c in clients if c["client_id"] == client_id), None)
    if not client:
        return redirect(url_for("index"))
    client["client_name"] = request.form["client_name"].strip()
    client["whatsapp_group_name"] = request.form["whatsapp_group_name"].strip()
    _write_config(clients)
    return redirect(url_for("edit_client", client_id=client_id))


@app.route("/client/<client_id>/delete", methods=["POST"])
def delete_client(client_id):
    clients = _read_config()
    clients = [c for c in clients if c["client_id"] != client_id]
    _write_config(clients)
    return redirect(url_for("index"))


@app.route("/client/<client_id>/competitor/add", methods=["POST"])
def add_competitor(client_id):
    clients = _read_config()
    client = next((c for c in clients if c["client_id"] == client_id), None)
    if not client:
        return redirect(url_for("index"))
    competitor = {
        "name": request.form["competitor_name"].strip(),
        "url": request.form["competitor_url"].strip(),
    }
    client.setdefault("competitors", []).append(competitor)
    _write_config(clients)
    return redirect(url_for("edit_client", client_id=client_id))


@app.route("/client/<client_id>/competitor/<int:comp_index>/delete", methods=["POST"])
def delete_competitor(client_id, comp_index):
    clients = _read_config()
    client = next((c for c in clients if c["client_id"] == client_id), None)
    if not client:
        return redirect(url_for("index"))
    if 0 <= comp_index < len(client.get("competitors", [])):
        client["competitors"].pop(comp_index)
    _write_config(clients)
    return redirect(url_for("edit_client", client_id=client_id))


@app.route("/run-agent", methods=["POST"])
def run_agent():
    """Trigger the agent in a background thread."""
    if agent_status["running"]:
        return jsonify({"status": "already_running"}), 409

    def _run():
        agent_status["running"] = True
        agent_status["last_run"] = datetime.now().isoformat()
        try:
            result = subprocess.run(
                [sys.executable, "main.py"],
                cwd=str(Path(__file__).resolve().parent),
                capture_output=True,
                text=True,
                timeout=1800,
            )
            agent_status["last_result"] = (
                "success" if result.returncode == 0 else f"error: {result.stderr[-500:]}"
            )
        except subprocess.TimeoutExpired:
            agent_status["last_result"] = "error: timeout (30 min)"
        except Exception as e:
            agent_status["last_result"] = f"error: {e}"
        finally:
            agent_status["running"] = False

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return redirect(url_for("index"))


@app.route("/api/status")
def api_status():
    return jsonify(agent_status)


if __name__ == "__main__":
    app.run(debug=True, port=5050)
