from flask import Flask, render_template, request, jsonify
from datetime import datetime

from models.timer_run import db, TimerRun
from metrics.cycle_time import median_cycle_time, std_cycle_time, coefficient_of_variation
from metrics.variability import stability_class
from models.metrics import aggregate_cycle_times
from metrics.throughput import throughput_per_day
from metrics.bottleneck import detect_process_bottleneck



app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///timer.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

from models.graph import ProcessGraph, GraphNode, GraphEdge, ProcessEvent

# Create the database tables
with app.app_context():
    db.create_all()

# Global variable to store current run
current_run = {}

@app.route("/start", methods=["POST"])
def start():
    """
    Start timer - supports both graph mode and legacy mode
    """
    global current_run
    data = request.json
    
    # Check if this is graph mode (has edge_id) or legacy mode
    if 'edge_id' in data:
        # GRAPH MODE: User selected a specific edge in the process graph
        edge_id = data['edge_id']
        edge = GraphEdge.query.get(edge_id)
        
        if not edge:
            return jsonify({"status": "error", "message": "Edge not found"}), 404
        
        current_run = {
            "mode": "graph",
            "edge_id": edge.id,
            "process": edge.process_name,
            "machine": edge.target_node.machine_name,
            "operator": data["operator"],
            "batch_id": data.get("batch_id"),
            "start_time": datetime.now()
        }
    else:
        # LEGACY MODE: Simple process/machine/operator input
        current_run = {
            "mode": "legacy",
            "process": data["process"],
            "machine": data["machine"],
            "operator": data["operator"],
            "notes": data.get("notes", ""),
            "time_type": data.get("time_type"),
            "start_time": datetime.now()
        }
    
    return jsonify({"status": "started", "run": current_run}), 200

@app.route("/stop", methods=["POST"])
def stop():
    """
    Stop timer - works for both modes
    """
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
    """
    Save timer run - saves as ProcessEvent (graph mode) or TimerRun (legacy mode)
    """
    global current_run
    data = request.json
    
    # Ensure we have a completed run
    if not current_run.get("start_time") or not current_run.get("end_time"):
        return jsonify({"status": "error", "message": "No completed run to save."}), 400
    
    try:
        if current_run.get("mode") == "graph":
            # SAVE AS PROCESS EVENT (new graph-based system)
            event = ProcessEvent(
                edge_id=current_run["edge_id"],
                operator=current_run["operator"],
                start_time=current_run["start_time"],
                end_time=current_run["end_time"],
                duration=current_run["duration"],
                batch_id=current_run.get("batch_id"),
                notes=data.get("notes", ""),
                quality_flag=True  # Could make this user-selectable
            )
            db.session.add(event)
            db.session.commit()
            
            return jsonify({
                "status": "saved",
                "duration": event.duration,
                "mode": "graph",
                "event_id": event.id
            }), 200
            
        else:
            # SAVE AS TIMER RUN (legacy system - backward compatible)
            run = TimerRun(
                process=current_run["process"],
                machine=current_run["machine"],
                operator=current_run["operator"],
                notes=data.get("notes", ""),
                time_type=current_run.get("time_type"),
                start_time=current_run["start_time"],
                end_time=current_run["end_time"],
                duration=current_run["duration"],
                laps=None
            )
            db.session.add(run)
            db.session.commit()
            
            return jsonify({
                "status": "saved",
                "duration": run.duration,
                "mode": "legacy",
                "run_id": run.id
            }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    
    finally:
        # Clear current_run
        current_run = {}



### --------------- Views -----------------
@app.route('/')
def hello():
    return render_template('index.html')

@app.route("/graph-builder")
def graph_builder():
    return render_template("graph-builder.html")
    
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
    query = TimerRun.query

    process = request.args.get("process")
    machine = request.args.get("machine")
    operator = request.args.get("operator")

    if process:
        query = query.filter_by(process=process)
    if machine:
        query = query.filter_by(machine=machine)
    if operator:
        query = query.filter_by(operator=operator)

    runs = query.order_by(TimerRun.start_time.desc()).limit(10).all()
    return jsonify([r.to_dict() for r in runs])



@app.route("/api/dashboard/summary")
def dashboard_summary():
    query = TimerRun.query

    process = request.args.get("process")
    machine = request.args.get("machine")
    operator = request.args.get("operator")

    if process:
        query = query.filter(TimerRun.process == process)
    if machine:
        query = query.filter(TimerRun.machine == machine)
    if operator:
        query = query.filter(TimerRun.operator == operator)

    runs = query.all()
    durations = [r.duration for r in runs]
    
    throughput = throughput_per_day([r.to_dict() for r in runs])
    bottleneck = detect_process_bottleneck(runs)


    if not durations:
        return jsonify({
            "total_runs": 0,
            "avg_duration": 0,
            "median_duration": 0,
            "std_duration": 0,
            "min_duration": 0,
            "max_duration": 0,
            "coefficient_of_variation": 0,
            "stability_class": "N/A",
            "throughput_per_day": 0,
            "bottleneck": "None"
        })
        

    avg = sum(durations) / len(durations)
    variance = sum((d - avg) ** 2 for d in durations) / len(durations)
    std = variance ** 0.5

    sorted_durations = sorted(durations)
    mid = len(sorted_durations) // 2
    median = (
        sorted_durations[mid]
        if len(sorted_durations) % 2
        else (sorted_durations[mid - 1] + sorted_durations[mid]) / 2
    )
    
    return jsonify({
        "total_runs": len(durations),
        "avg_duration": avg,
        "median_duration": median,
        "std_duration": std,
        "min_duration": min(durations),
        "max_duration": max(durations),
        "coefficient_of_variation": coefficient_of_variation(runs),
        "stability_class": stability_class(coefficient_of_variation(runs)),
        "throughput_per_day": round(throughput, 2) if throughput else 0,
        "bottleneck": bottleneck
    })


@app.route("/api/dashboard/filters")
def dashboard_filters():
    processes = [r[0] for r in db.session.query(TimerRun.process).distinct().all()]
    machines  = [r[0] for r in db.session.query(TimerRun.machine).distinct().all()]
    operators = [r[0] for r in db.session.query(TimerRun.operator).distinct().all()]

    return jsonify({
        "processes": processes,
        "machines": machines,
        "operators": operators
    })

@app.route("/api/dashboard/aggregates")
def dashboard_aggregates():
    process = request.args.get("process")
    machine = request.args.get("machine")
    operator = request.args.get("operator")

    query = TimerRun.query

    if process:
        query = query.filter_by(process=process)
    if machine:
        query = query.filter_by(machine=machine)
    if operator:
        query = query.filter_by(operator=operator)

    runs = query.all()

    return jsonify({
        "by_process": aggregate_cycle_times(runs, "process"),
        "by_machine": aggregate_cycle_times(runs, "machine"),
        "by_operator": aggregate_cycle_times(runs, "operator")
    })

##############################################################
################ Graph API Endpoints #########################
#############################################################

@app.route("/api/graph/list", methods=["GET"])
def list_graphs():
    """List all process graphs"""
    graphs = ProcessGraph.query.filter_by(is_active=True).all()
    return jsonify([g.to_dict() for g in graphs])


@app.route("/api/graph/create", methods=["POST"])
def create_graph():
    """Create a new process graph"""
    data = request.json
    
    graph = ProcessGraph(
        name=data['name'],
        description=data.get('description', '')
    )
    
    db.session.add(graph)
    db.session.commit()
    
    return jsonify(graph.to_dict()), 201


@app.route("/api/graph/<int:graph_id>", methods=["GET"])
def get_graph(graph_id):
    """Get full graph definition including nodes and edges"""
    graph = ProcessGraph.query.get_or_404(graph_id)
    
    nodes = [n.to_dict() for n in graph.nodes]
    edges = [e.to_dict() for e in graph.edges]
    
    return jsonify({
        'graph': graph.to_dict(),
        'nodes': nodes,
        'edges': edges
    })


@app.route("/api/graph/<int:graph_id>/node", methods=["POST"])
def add_node(graph_id):
    """Add a machine (node) to the graph"""
    data = request.json
    
    node = GraphNode(
        graph_id=graph_id,
        machine_name=data['machine_name'],
        machine_type=data.get('machine_type'),
        theoretical_capacity=data.get('theoretical_capacity')
    )
    
    db.session.add(node)
    db.session.commit()
    
    return jsonify(node.to_dict()), 201


@app.route("/api/graph/node/<int:node_id>", methods=["DELETE"])
def delete_node(node_id):
    """Delete a node (and its connected edges)"""
    node = GraphNode.query.get_or_404(node_id)
    db.session.delete(node)
    db.session.commit()
    
    return jsonify({'status': 'deleted', 'node_id': node_id})


@app.route("/api/graph/<int:graph_id>/edge", methods=["POST"])
def add_edge(graph_id):
    """Add a process flow (edge) between two machines"""
    data = request.json
    
    edge = GraphEdge(
        graph_id=graph_id,
        source_node_id=data['source_node_id'],
        target_node_id=data['target_node_id'],
        process_name=data['process_name'],
        expected_duration=data.get('expected_duration')
    )
    
    db.session.add(edge)
    db.session.commit()
    
    return jsonify(edge.to_dict()), 201


@app.route("/api/graph/edge/<int:edge_id>", methods=["DELETE"])
def delete_edge(edge_id):
    """Delete an edge"""
    edge = GraphEdge.query.get_or_404(edge_id)
    db.session.delete(edge)
    db.session.commit()
    
    return jsonify({'status': 'deleted', 'edge_id': edge_id})

@app.route("/api/events/recent", methods=["GET"])
def recent_events():
    """Get recent process events for monitoring"""
    graph_id = request.args.get('graph_id', type=int)
    limit = request.args.get('limit', 20, type=int)
    
    query = ProcessEvent.query.join(ProcessEvent.edge)
    
    if graph_id:
        query = query.filter(GraphEdge.graph_id == graph_id)
    
    events = query.order_by(ProcessEvent.start_time.desc()).limit(limit).all()
    
    return jsonify([e.to_dict() for e in events])

if __name__ == '__main__':
    app.run(debug=True)