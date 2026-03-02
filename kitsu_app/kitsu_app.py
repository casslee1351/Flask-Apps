from flask import Flask, render_template, request, jsonify
from datetime import datetime

from models.timer_run import db, TimerRun
from metrics.cycle_time import median_cycle_time, std_cycle_time, coefficient_of_variation
from metrics.variability import stability_class
from models.metrics import aggregate_cycle_times
from metrics.throughput import throughput_per_day
from metrics.bottleneck import detect_process_bottleneck
from analysis.topology import ProcessGraphAnalyzer
from analysis.timeseries import TimeSeriesAnalyzer, get_bottleneck_time_series, get_bottleneck_predictions
from analysis.scenarios import ScenarioModeler, run_scenario


app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///timer.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

from models.graph import ProcessGraph, GraphNode, GraphEdge, ProcessEvent

# Create the database tables
with app.app_context():
    db.create_all()

### --------------- Save/Start/Stop Endpoints ----------------- ##########
# Global variable to store current run
current_run = {}

@app.route("/start", methods=["POST"])
def start():
    """
    Start timer - GRAPH MODE with lap support
    """
    global current_run
    data = request.json
    
    # Validate edge_id is present
    if 'edge_id' not in data:
        return jsonify({
            "status": "error", 
            "message": "edge_id is required. Please select a process flow."
        }), 400
    
    # Get the edge
    edge_id = data['edge_id']
    edge = GraphEdge.query.get(edge_id)
    
    if not edge:
        return jsonify({
            "status": "error", 
            "message": "Invalid process flow selected"
        }), 404
    
    # Store current run info
    current_run = {
        "edge_id": edge.id,
        "process": edge.process_name,
        "machine": edge.target_node.machine_name,
        "operator": data["operator"],
        "batch_id": data.get("batch_id"),
        "start_time": datetime.now(),
        "laps": []
    }
    
    return jsonify({"status": "started"}), 200


@app.route("/stop", methods=["POST"])
def stop():
    """
    Stop timer - now accepts optional laps data
    """
    global current_run
    data = request.json
    duration = data.get("duration")
    laps = data.get("laps")
    
    if duration is None:
        return jsonify({
            "status": "error", 
            "message": "Duration missing"
        }), 400
    
    current_run["end_time"] = datetime.now()
    current_run["duration"] = duration
    
    # Store laps if provided
    if laps:
        current_run["laps"] = laps
    
    return jsonify({
        "status": "stopped", 
        "duration": duration,
        "laps_count": len(laps) if laps else 0
    }), 200


@app.route("/save", methods=["POST"])
def save():
    """
    Save timer run as ProcessEvent with optional lap data
    """
    global current_run
    data = request.json
    
    # Ensure we have a completed run
    if not current_run.get("start_time") or not current_run.get("end_time"):
        return jsonify({
            "status": "error", 
            "message": "No completed run to save."
        }), 400
    
    try:
        # Prepare laps data for storage
        laps_data = data.get("laps") or current_run.get("laps")
        
        # Convert laps to JSON string for storage in custom_metadata
        metadata = {}
        if laps_data and len(laps_data) > 0:
            metadata['laps'] = laps_data
            metadata['lap_count'] = len(laps_data)
            
            # Calculate lap statistics
            lap_times = [lap['lapTime'] for lap in laps_data]
            metadata['fastest_lap'] = min(lap_times)
            metadata['slowest_lap'] = max(lap_times)
            metadata['average_lap'] = sum(lap_times) / len(lap_times)
        
        # Create ProcessEvent
        event = ProcessEvent(
            edge_id=current_run["edge_id"],
            operator=current_run["operator"],
            start_time=current_run["start_time"],
            end_time=current_run["end_time"],
            duration=current_run["duration"],
            batch_id=current_run.get("batch_id"),
            notes=data.get("notes", ""),
            quality_flag=True,
            custom_metadata=metadata if metadata else None
        )
        
        db.session.add(event)
        db.session.commit()
        
        # Clear current_run
        current_run = {}
        
        return jsonify({
            "status": "saved",
            "duration": event.duration,
            "event_id": event.id,
            "laps_count": metadata.get('lap_count', 0) if metadata else 0
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    

### --------------- Views ----------------- ###############
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

@app.route("/analysis-dashboard")
def analysis_dashboard():
    return render_template("analysis-dashboard.html")

@app.route("/graph-view")
def graph_view():
    return render_template("graph-view.html")

@app.route("/advanced-analytics")
def advanced_analytics():
    return render_template("advanced-analytics.html")


############### Dashboard API ------------- ################3


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

################ Graph API Endpoints #########################

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


@app.route("/api/graph/<int:graph_id>/analyze", methods=["GET"])
def analyze_graph(graph_id):
    """
    Comprehensive bottleneck analysis for a graph
    
    Query params:
        - hours: Time window in hours (default 24)
        - top_n: Number of bottlenecks to return (default 5)
    
    Returns bottleneck scores, critical path, and graph summary
    """
    hours = request.args.get('hours', 24, type=int)
    top_n = request.args.get('top_n', 5, type=int)
    
    try:
        analyzer = ProcessGraphAnalyzer(graph_id, db.session)
        
        # Run all analyses
        bottlenecks = analyzer.detect_bottlenecks(
            time_window_hours=hours,
            top_n=top_n
        )
        
        critical_path = analyzer.calculate_critical_path()
        summary = analyzer.get_graph_summary()
        
        return jsonify({
            'summary': summary,
            'bottlenecks': bottlenecks,
            'critical_path': critical_path,
            'analysis_window_hours': hours,
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error analyzing graph'
        }), 500
    
@app.route("/api/graph/node/<int:node_id>/metrics", methods=["GET"])
def node_metrics(node_id):
    """
    Get detailed metrics for a specific machine/node
    
    Query params:
        - hours: Time window in hours (default 24)
    """
    hours = request.args.get('hours', 24, type=int)
    
    try:
        node = GraphNode.query.get_or_404(node_id)
        analyzer = ProcessGraphAnalyzer(node.graph_id, db.session)
        
        metrics = analyzer.calculate_node_metrics(node_id, time_window_hours=hours)
        
        return jsonify(metrics)
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error calculating node metrics'
        }), 500
    
@app.route("/api/graph/edge/<int:edge_id>/metrics", methods=["GET"])
def edge_metrics(edge_id):
    """
    Get detailed metrics for a specific process flow/edge
    
    Query params:
        - hours: Time window in hours (default 24)
    """
    hours = request.args.get('hours', 24, type=int)
    
    try:
        edge = GraphEdge.query.get_or_404(edge_id)
        analyzer = ProcessGraphAnalyzer(edge.graph_id, db.session)
        
        metrics = analyzer.calculate_edge_metrics(edge_id, time_window_hours=hours)
        
        return jsonify(metrics)
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error calculating edge metrics'
        }), 500
    
@app.route("/api/graph/<int:graph_id>/events/summary", methods=["GET"])
def graph_events_summary(graph_id):
    """
    Get summary of events for a graph
    
    Query params:
        - hours: Time window in hours (default 24)
    """
    from datetime import timedelta
    
    hours = request.args.get('hours', 24, type=int)
    cutoff = datetime.now() - timedelta(hours=hours)
    
    try:
        # Count events by machine
        from sqlalchemy import func
        
        machine_counts = db.session.query(
            GraphNode.machine_name,
            func.count(ProcessEvent.id).label('count'),
            func.avg(ProcessEvent.duration).label('avg_duration'),
            func.min(ProcessEvent.duration).label('min_duration'),
            func.max(ProcessEvent.duration).label('max_duration')
        ).join(
            GraphEdge, GraphNode.id == GraphEdge.target_node_id
        ).join(
            ProcessEvent, GraphEdge.id == ProcessEvent.edge_id
        ).filter(
            GraphEdge.graph_id == graph_id,
            ProcessEvent.start_time >= cutoff
        ).group_by(
            GraphNode.machine_name
        ).all()
        
        # Count events by process
        process_counts = db.session.query(
            GraphEdge.process_name,
            func.count(ProcessEvent.id).label('count'),
            func.avg(ProcessEvent.duration).label('avg_duration')
        ).join(
            ProcessEvent, GraphEdge.id == ProcessEvent.edge_id
        ).filter(
            GraphEdge.graph_id == graph_id,
            ProcessEvent.start_time >= cutoff
        ).group_by(
            GraphEdge.process_name
        ).all()
        
        return jsonify({
            'by_machine': [
                {
                    'machine': m[0],
                    'count': m[1],
                    'avg_duration': round(m[2], 2) if m[2] else 0,
                    'min_duration': round(m[3], 2) if m[3] else 0,
                    'max_duration': round(m[4], 2) if m[4] else 0
                }
                for m in machine_counts
            ],
            'by_process': [
                {
                    'process': p[0],
                    'count': p[1],
                    'avg_duration': round(p[2], 2) if p[2] else 0
                }
                for p in process_counts
            ],
            'time_window_hours': hours
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error getting event summary'
        }), 500
    
##################### Events API ########################
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

@app.route("/api/events/stats", methods=["GET"])
def get_events_stats():
    """
    Get statistics about all events
    """
    try:
        from sqlalchemy import func
        
        # Count events
        total_count = ProcessEvent.query.count()
        
        # Get duration stats
        stats = db.session.query(
            func.avg(ProcessEvent.duration).label('avg'),
            func.min(ProcessEvent.duration).label('min'),
            func.max(ProcessEvent.duration).label('max')
        ).first()
        
        # Get unique operators
        unique_operators = db.session.query(
            func.count(func.distinct(ProcessEvent.operator))
        ).scalar()
        
        # Get unique batches
        unique_batches = db.session.query(
            func.count(func.distinct(ProcessEvent.batch_id))
        ).filter(ProcessEvent.batch_id.isnot(None)).scalar()
        
        return jsonify({
            'total_events': total_count,
            'unique_operators': unique_operators,
            'unique_batches': unique_batches or 0,
            'duration_stats': {
                'avg': round(stats.avg, 2) if stats.avg else 0,
                'min': round(stats.min, 2) if stats.min else 0,
                'max': round(stats.max, 2) if stats.max else 0
            }
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error calculating stats'
        }), 500
    
@app.route("/api/events/all", methods=["GET"])
def get_all_process_events():
    """
    Get all ProcessEvent records including lap data
    """
    try:
        events = ProcessEvent.query.order_by(ProcessEvent.start_time.desc()).all()
        
        # Enhanced to_dict that includes lap info
        result = []
        for event in events:
            event_dict = event.to_dict()
            
            # Add lap summary if laps exist
            if event.custom_metadata and 'laps' in event.custom_metadata:
                event_dict['has_laps'] = True
                event_dict['lap_count'] = event.custom_metadata.get('lap_count', 0)
                event_dict['fastest_lap'] = event.custom_metadata.get('fastest_lap')
                event_dict['average_lap'] = event.custom_metadata.get('average_lap')
            else:
                event_dict['has_laps'] = False
                event_dict['lap_count'] = 0
            
            result.append(event_dict)
        
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error fetching process events'
        }), 500


################# Dashboard Graph Summary API ########################
    
@app.route("/api/dashboard/graph-summary", methods=["GET"])
def dashboard_graph_summary():
    """
    Enhanced dashboard data including graph analysis
    Use this instead of or in addition to your existing /api/dashboard/summary
    """
    graph_id = request.args.get("graph_id", type=int)
    hours = request.args.get("hours", 24, type=int)
    
    if not graph_id:
        return jsonify({"error": "graph_id required"}), 400
    
    try:
        analyzer = ProcessGraphAnalyzer(graph_id, db.session)
        
        # Get bottlenecks
        bottlenecks = analyzer.detect_bottlenecks(time_window_hours=hours, top_n=3)
        
        # Get graph summary
        summary = analyzer.get_graph_summary()
        
        # Get total events
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=hours)
        
        total_events = ProcessEvent.query.join(ProcessEvent.edge).filter(
            GraphEdge.graph_id == graph_id,
            ProcessEvent.start_time >= cutoff
        ).count()
        
        # Critical path
        critical_path = analyzer.calculate_critical_path()
        
        return jsonify({
            'graph': summary,
            'total_events': total_events,
            'time_window_hours': hours,
            'top_bottleneck': bottlenecks[0] if bottlenecks else None,
            'bottlenecks': bottlenecks,
            'critical_path': critical_path,
            'timestamp': datetime.now().isoformat()
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error generating dashboard summary'
        }), 500

####################### Time-Series Analysis API ##################

@app.route("/api/graph/<int:graph_id>/timeseries", methods=["GET"])
def graph_timeseries(graph_id):
    """
    Get bottleneck scores over time
    
    Query params:
        - days: Number of days to analyze (default 7)
        - interval: Hours per data point (default 4)
    """
    days = request.args.get('days', 7, type=int)
    interval = request.args.get('interval', 4, type=int)
    
    try:
        data = get_bottleneck_time_series(graph_id, db.session, days=days, interval_hours=interval)
        return jsonify(data)
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error analyzing time series'
        }), 500


@app.route("/api/graph/<int:graph_id>/predictions", methods=["GET"])
def graph_predictions(graph_id):
    """
    Predict future bottlenecks based on trends
    
    Query params:
        - hours: Hours ahead to predict (default 24)
    """
    hours = request.args.get('hours', 24, type=int)
    
    try:
        predictions = get_bottleneck_predictions(graph_id, db.session, hours_ahead=hours)
        return jsonify(predictions)
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error generating predictions'
        }), 500


@app.route("/api/graph/<int:graph_id>/pattern-shifts", methods=["GET"])
def pattern_shifts(graph_id):
    """
    Detect when primary bottleneck shifts between machines
    
    Query params:
        - hours: Time window (default 24)
    """
    hours = request.args.get('hours', 24, type=int)
    
    try:
        analyzer = TimeSeriesAnalyzer(graph_id, db.session)
        shifts = analyzer.detect_pattern_shifts(hours=hours)
        return jsonify(shifts)
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error detecting pattern shifts'
        }), 500


#################### What-If Scenario Analysis API ####################

@app.route("/api/graph/<int:graph_id>/scenario/baseline", methods=["GET"])
def scenario_baseline(graph_id):
    """
    Get baseline metrics for scenario comparison
    
    Query params:
        - hours: Time window (default 24)
    """
    hours = request.args.get('hours', 24, type=int)
    
    try:
        modeler = ScenarioModeler(graph_id, db.session)
        baseline = modeler.get_baseline_metrics(hours=hours)
        return jsonify(baseline)
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error getting baseline'
        }), 500


@app.route("/api/graph/<int:graph_id>/scenario/capacity-increase", methods=["POST"])
def scenario_capacity_increase(graph_id):
    """
    Simulate increasing machine capacity
    
    Body: {
        "node_id": 1,
        "new_capacity": 100,
        "hours": 24
    }
    """
    data = request.json
    
    try:
        result = run_scenario(graph_id, db.session, 'capacity_increase', {
            'node_id': data['node_id'],
            'new_capacity': data['new_capacity'],
            'hours': data.get('hours', 24)
        })
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error running capacity increase scenario'
        }), 500


@app.route("/api/graph/<int:graph_id>/scenario/add-machine", methods=["POST"])
def scenario_add_machine(graph_id):
    """
    Simulate adding a new machine
    
    Body: {
        "machine_name": "New CNC",
        "machine_type": "CNC",
        "capacity": 80,
        "hours": 24
    }
    """
    data = request.json
    
    try:
        result = run_scenario(graph_id, db.session, 'add_machine', {
            'machine_name': data['machine_name'],
            'machine_type': data['machine_type'],
            'capacity': data['capacity'],
            'hours': data.get('hours', 24)
        })
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error running add machine scenario'
        }), 500


@app.route("/api/graph/<int:graph_id>/scenario/remove-step", methods=["POST"])
def scenario_remove_step(graph_id):
    """
    Simulate removing a process step
    
    Body: {
        "edge_id": 1,
        "hours": 24
    }
    """
    data = request.json
    
    try:
        result = run_scenario(graph_id, db.session, 'remove_step', {
            'edge_id': data['edge_id'],
            'hours': data.get('hours', 24)
        })
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error running remove step scenario'
        }), 500


######################### Anomaly Detection API ########################

@app.route("/api/graph/<int:graph_id>/anomalies", methods=["GET"])
def detect_anomalies(graph_id):
    """
    Detect unusual patterns in process events
    
    Query params:
        - hours: Time window (default 24)
        - sensitivity: 'low', 'medium', 'high' (default 'medium')
    """
    hours = request.args.get('hours', 24, type=int)
    sensitivity = request.args.get('sensitivity', 'medium')
    
    from datetime import timedelta
    cutoff = datetime.now() - timedelta(hours=hours)
    
    try:
        # Get all events in time window
        events = ProcessEvent.query.join(ProcessEvent.edge).filter(
            GraphEdge.graph_id == graph_id,
            ProcessEvent.start_time >= cutoff
        ).all()
        
        if not events:
            return jsonify({'anomalies': [], 'message': 'No data available'})
        
        # Group by edge
        from collections import defaultdict
        import numpy as np
        
        edge_events = defaultdict(list)
        for event in events:
            if event.duration:
                edge_events[event.edge_id].append(event.duration)
        
        anomalies = []
        
        # Set threshold based on sensitivity
        thresholds = {'low': 3, 'medium': 2.5, 'high': 2}
        threshold = thresholds.get(sensitivity, 2.5)
        
        for edge_id, durations in edge_events.items():
            if len(durations) < 5:
                continue
            
            mean = np.mean(durations)
            std = np.std(durations)
            
            # Find outliers (values beyond threshold standard deviations)
            for event in events:
                if event.edge_id == edge_id and event.duration:
                    z_score = abs((event.duration - mean) / std) if std > 0 else 0
                    
                    if z_score > threshold:
                        edge = GraphEdge.query.get(edge_id)
                        anomalies.append({
                            'event_id': event.id,
                            'process': edge.process_name if edge else 'Unknown',
                            'machine': edge.target_node.machine_name if edge and edge.target_node else 'Unknown',
                            'duration': round(event.duration, 2),
                            'expected_duration': round(mean, 2),
                            'deviation': round(z_score, 2),
                            'timestamp': event.start_time.isoformat(),
                            'operator': event.operator,
                            'severity': 'high' if z_score > 3 else 'medium'
                        })
        
        # Sort by severity and deviation
        anomalies.sort(key=lambda x: x['deviation'], reverse=True)
        
        return jsonify({
            'anomalies': anomalies[:20],  # Top 20
            'total_anomalies': len(anomalies),
            'sensitivity': sensitivity,
            'time_window_hours': hours
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error detecting anomalies'
        }), 500


##################### Capacity Planning API ########################

@app.route("/api/graph/<int:graph_id>/capacity-plan", methods=["POST"])
def capacity_planning(graph_id):
    """
    Generate capacity planning recommendations
    
    Body: {
        "target_throughput": 100,  // units per day
        "budget": 50000,            // optional
        "hours": 24
    }
    """
    data = request.json
    target_throughput = data.get('target_throughput')
    budget = data.get('budget')
    hours = data.get('hours', 24)
    
    if not target_throughput:
        return jsonify({'error': 'target_throughput required'}), 400
    
    try:
        # Get current state
        modeler = ScenarioModeler(graph_id, db.session)
        baseline = modeler.get_baseline_metrics(hours=hours)
        
        # Find bottlenecks
        bottlenecks = [b for b in baseline['bottlenecks'] if b['event_count'] > 0]
        
        if not bottlenecks:
            return jsonify({
                'message': 'No bottleneck data available',
                'recommendation': 'Collect more data first'
            })
        
        top_bottleneck = bottlenecks[0]
        
        # Calculate capacity gap
        current_throughput = top_bottleneck['actual_throughput'] * 24  # per day
        gap = target_throughput - current_throughput
        gap_percent = (gap / current_throughput) * 100 if current_throughput > 0 else 0
        
        # Generate recommendations
        recommendations = []
        
        if gap > 0:
            # Need more capacity
            if gap_percent > 50:
                recommendations.append({
                    'action': 'add_machine',
                    'description': f'Add parallel machine to {top_bottleneck["machine_name"]}',
                    'impact': f'Could increase throughput by ~{gap_percent:.0f}%',
                    'priority': 'high',
                    'estimated_cost': 'Depends on equipment type'
                })
            
            # Increase capacity of existing machine
            required_capacity_increase = (target_throughput / current_throughput) * 100
            recommendations.append({
                'action': 'increase_capacity',
                'description': f'Upgrade {top_bottleneck["machine_name"]} capacity by {gap_percent:.0f}%',
                'impact': f'Would meet target throughput',
                'priority': 'medium',
                'estimated_cost': 'Automation or operator training'
            })
            
            # Optimize process
            recommendations.append({
                'action': 'optimize_process',
                'description': 'Reduce cycle time variability',
                'impact': f'Current CV: {top_bottleneck["cv"]:.3f} - reduce to <0.2',
                'priority': 'medium',
                'estimated_cost': 'Low - process improvements'
            })
        
        else:
            recommendations.append({
                'action': 'maintain',
                'description': 'Current capacity exceeds target',
                'impact': 'No action needed',
                'priority': 'low'
            })
        
        return jsonify({
            'current_state': {
                'throughput_per_day': round(current_throughput, 2),
                'top_bottleneck': top_bottleneck['machine_name'],
                'bottleneck_score': top_bottleneck['total_score']
            },
            'target': {
                'throughput_per_day': target_throughput,
                'gap': round(gap, 2),
                'gap_percent': round(gap_percent, 1)
            },
            'recommendations': recommendations,
            'budget': budget,
            'analysis_hours': hours
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error generating capacity plan'
        }), 500

#################### Lap Analysis API ########################

@app.route("/api/events/<int:event_id>/laps", methods=["GET"])
def get_event_laps(event_id):
    """
    Get detailed lap data for a specific event
    """
    try:
        event = ProcessEvent.query.get_or_404(event_id)
        
        if not event.custom_metadata or 'laps' not in event.custom_metadata:
            return jsonify({
                'event_id': event_id,
                'has_laps': False,
                'laps': []
            })
        
        return jsonify({
            'event_id': event_id,
            'has_laps': True,
            'lap_count': event.custom_metadata.get('lap_count', 0),
            'laps': event.custom_metadata['laps'],
            'statistics': {
                'fastest': event.custom_metadata.get('fastest_lap'),
                'slowest': event.custom_metadata.get('slowest_lap'),
                'average': event.custom_metadata.get('average_lap')
            }
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error fetching lap data'
        }), 500

@app.route("/api/graph/<int:graph_id>/lap-analysis", methods=["GET"])
def analyze_laps(graph_id):
    """
    Analyze lap consistency across all events in a graph
    
    Returns insights about lap time consistency
    """
    try:
        from datetime import timedelta
        from sqlalchemy import func
        
        hours = request.args.get('hours', 24, type=int)
        cutoff = datetime.now() - timedelta(hours=hours)
        
        # Get all events with laps
        events = ProcessEvent.query.join(ProcessEvent.edge).filter(
            GraphEdge.graph_id == graph_id,
            ProcessEvent.start_time >= cutoff,
            ProcessEvent.custom_metadata.isnot(None)
        ).all()
        
        # Filter to only events with laps
        events_with_laps = [
            e for e in events 
            if e.custom_metadata and 'laps' in e.custom_metadata
        ]
        
        if not events_with_laps:
            return jsonify({
                'message': 'No events with laps in time window',
                'events_analyzed': 0
            })
        
        # Aggregate statistics
        all_lap_times = []
        consistent_runs = 0
        inconsistent_runs = 0
        
        for event in events_with_laps:
            laps = event.custom_metadata['laps']
            lap_times = [lap['lapTime'] for lap in laps]
            all_lap_times.extend(lap_times)
            
            # Check consistency (CV < 0.15 = consistent)
            if len(lap_times) > 1:
                import numpy as np
                mean = np.mean(lap_times)
                std = np.std(lap_times)
                cv = std / mean if mean > 0 else 0
                
                if cv < 0.15:
                    consistent_runs += 1
                else:
                    inconsistent_runs += 1
        
        import numpy as np
        
        return jsonify({
            'events_analyzed': len(events_with_laps),
            'total_laps': len(all_lap_times),
            'consistency': {
                'consistent_runs': consistent_runs,
                'inconsistent_runs': inconsistent_runs,
                'consistency_rate': round(consistent_runs / len(events_with_laps) * 100, 1) if events_with_laps else 0
            },
            'lap_time_stats': {
                'mean': round(float(np.mean(all_lap_times)), 2) if all_lap_times else 0,
                'std': round(float(np.std(all_lap_times)), 2) if all_lap_times else 0,
                'min': round(float(np.min(all_lap_times)), 2) if all_lap_times else 0,
                'max': round(float(np.max(all_lap_times)), 2) if all_lap_times else 0
            },
            'time_window_hours': hours
        })
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error analyzing laps'
        }), 500

if __name__ == '__main__':
    app.run(debug=True)