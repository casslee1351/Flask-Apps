from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

# --- SQLite Config ---
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///timer.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Database Model ---
class TimerRun(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    process = db.Column(db.String(100), nullable=False)
    machine = db.Column(db.String(100), nullable=False)
    operator = db.Column(db.String(100), nullable=False)
    notes = db.Column(db.String(500))
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Float, nullable=False)

# Create the database tables
with app.app_context():
    db.create_all()

# Global variable to store current run
current_run = {}

@app.route("/start", methods=["POST"])
def start():
    data = request.json
    current_run["process"] = data.get("process")
    current_run["machine"] = data.get("machine")
    current_run["operator"] = data.get("operator")
    current_run["notes"] = data.get("notes")
    current_run["start_time"] = datetime.now()

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

    # Ensure we have full run data
    if not current_run.get("start_time") or not current_run.get("end_time"):
        return jsonify({"status": "error", "message": "No completed run to save."}), 400

    duration = (current_run["end_time"] - current_run["start_time"]).total_seconds()

    run = TimerRun(
        process=current_run["process"],
        machine=current_run["machine"],
        operator=current_run["operator"],
        notes=data.get("notes", ""),
        start_time=current_run["start_time"],
        end_time=current_run["end_time"],
        duration=duration
    )

    db.session.add(run)
    db.session.commit()

    # Clear current run after saving
    current_run = {}

    return jsonify({"status": "saved", "duration": duration}), 200


@app.route("/runs", methods=["GET"])
def runs():
    runs = TimerRun.query.order_by(TimerRun.id.desc()).all()
    return jsonify([{
        "id": r.id,
        "process": r.process,
        "machine": r.machine,
        "operator": r.operator,
        "notes": r.notes,
        "start_time": r.start_time.isoformat(),
        "end_time": r.end_time.isoformat(),
        "duration": r.duration
    } for r in runs])
    
@app.route("/view")
def view_runs():
    runs = TimerRun.query.order_by(TimerRun.id.desc()).all()
    return render_template("view.html", runs=runs)


@app.route('/')
def hello():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)