from flask import Flask, render_template, request, jsonify
from datetime import datetime

from models.timer_run import db, TimerRun
from metrics.cycle_time import median_cycle_time


app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///timer.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# Create the database tables
with app.app_context():
    db.create_all()

# Global variable to store current run
current_run = {}

@app.route("/start", methods=["POST"])
def start():
    global current_run
    data = request.json

    current_run = {
        "process": data["process"],
        "machine": data["machine"],
        "operator": data["operator"],
        "notes": data.get("notes", ""),
        "time_type": data.get("time_type"),
        "start_time": datetime.now()
    }

    return jsonify({"status": "started"}), 200

@app.route("/stop", methods=["POST"])
def stop():
    global current_run

    data = request.json
    duration = data.get("duration")

    if duration is None:
        return jsonify({"status": "error", "message": "Duration missing"}), 400

    current_run["end_time"] = datetime.now()
    current_run["duration"] = duration

    return jsonify({"status": "stopped", "duration": duration}), 200


@app.route("/save", methods=["POST"])
def save():
    global current_run
    data = request.json

    # Ensure we have a completed run
    if not current_run.get("start_time") or not current_run.get("end_time"):
        return jsonify({"status": "error", "message": "No completed run to save."}), 400

    # Set laps to empty if not present
    laps = data.get("laps") or None

    run = TimerRun(
        process=current_run["process"],
        machine=current_run["machine"],
        operator=current_run["operator"],
        notes=data.get("notes", ""),
        time_type=current_run.get("time_type"),  # must exist
        start_time=current_run["start_time"],
        end_time=current_run["end_time"],
        duration=(current_run["end_time"] - current_run["start_time"]).total_seconds(),
        laps=None
    )

    db.session.add(run)
    db.session.commit()

    # Clear current_run
    current_run = {}

    return jsonify({"status": "saved", "duration": run.duration}), 200



### --------------- Views -----------------
@app.route('/')
def hello():
    return render_template('index.html')
    
@app.route("/view")
def view_runs():
    runs = TimerRun.query.order_by(TimerRun.id.desc()).all()
    return render_template("view.html", runs=runs)

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

# =============================
# Dashboard API
# =============================

@app.route("/api/dashboard/runs")
def dashboard_runs():
    query = TimerRun.query.order_by(TimerRun.start_time.desc()).limit(10)

    runs = query.all()
    return jsonify([r.to_dict() for r in runs])


@app.route("/api/dashboard/summary")
def dashboard_summary():

    runs = TimerRun.query.all()
    total_runs = len(runs)
    durations = [r.duration for r in runs]

    if not durations:
        return jsonify({
            "total_runs": 0,
            "avg_duration": 0,
            "median_duration": 0,
            "min_duration": 0,
            "max_duration": 0
        })

    return jsonify({
        "total_runs": total_runs,
        "avg_duration": sum(durations) / len(durations),
        "median_duration": median_cycle_time(runs),
        "min_duration": min(durations),
        "max_duration": max(durations)
    })


if __name__ == '__main__':
    app.run(debug=True)