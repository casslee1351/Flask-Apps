from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class TimerRun(db.Model):
    __tablename__ = "timer_run"

    id = db.Column(db.Integer, primary_key=True)

    # Core process dimensions
    process = db.Column(db.String(100), nullable=False)
    machine = db.Column(db.String(100), nullable=False)
    operator = db.Column(db.String(100), nullable=False)

    # Optional metadata
    notes = db.Column(db.String(500))

    # Classification (cycle, setup, downtime, etc.)
    time_type = db.Column(db.String(50), nullable=False)

    # Timing
    start_time = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Float, nullable=False)
    laps = db.Column(db.Integer, default=0)

    def to_dict(self):
        """Serialize for API responses."""
        return {
            "id": self.id,
            "process": self.process,
            "machine": self.machine,
            "operator": self.operator,
            "notes": self.notes,
            "time_type": self.time_type,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration": self.duration,
            "laps": self.laps
        }
