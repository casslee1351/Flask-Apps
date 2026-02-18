"""
Topology Analysis Module for Manufacturing Process Graphs
Implements graph-based bottleneck detection and process flow analysis
"""
import networkx as nx
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple, Optional

# Assuming these will be imported from your models
# from models.graph import ProcessGraph, GraphNode, GraphEdge, ProcessEvent


class ProcessGraphAnalyzer:
    """
    Analyzes manufacturing process graphs to detect bottlenecks,
    calculate utilization, and identify optimization opportunities.
    """
    
    def __init__(self, graph_id, db_session):
        """
        Initialize analyzer with a specific process graph.
        
        Args:
            graph_id: ID of ProcessGraph to analyze
            db_session: SQLAlchemy session for database queries
        """
        self.graph_id = graph_id
        self.db = db_session
        self.nx_graph = None
        self._build_networkx_graph()
    
    def _build_networkx_graph(self):
        """Build NetworkX directed graph from database."""
        from models.graph import GraphNode, GraphEdge
        
        self.nx_graph = nx.DiGraph()
        
        # Add nodes
        nodes = GraphNode.query.filter_by(graph_id=self.graph_id).all()
        for node in nodes:
            self.nx_graph.add_node(
                node.id,
                name=node.machine_name,
                capacity=node.theoretical_capacity,
                cycle_time=node.theoretical_cycle_time
            )
        
        # Add edges
        edges = GraphEdge.query.filter_by(graph_id=self.graph_id).all()
        for edge in edges:
            self.nx_graph.add_edge(
                edge.source_node_id,
                edge.target_node_id,
                edge_id=edge.id,
                process=edge.process_name,
                expected_duration=edge.expected_duration or 0
            )
    
    # ==================== BOTTLENECK DETECTION ====================
    
    def detect_bottlenecks(self, time_window_hours: int = 24, 
                          top_n: int = 5) -> List[Dict]:
        """
        Identify bottleneck nodes using multi-factor analysis.
        
        Args:
            time_window_hours: How far back to look for events
            top_n: Return top N bottleneck candidates
        
        Returns:
            List of dicts with bottleneck scores and details
        """
        from models.graph import GraphNode
        
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        nodes = GraphNode.query.filter_by(graph_id=self.graph_id).all()
        
        bottleneck_scores = []
        
        for node in nodes:
            score_data = self._calculate_bottleneck_score(node, cutoff_time)
            score_data['node_id'] = node.id
            score_data['machine_name'] = node.machine_name
            bottleneck_scores.append(score_data)
        
        # Sort by total score descending
        bottleneck_scores.sort(key=lambda x: x['total_score'], reverse=True)
        
        return bottleneck_scores[:top_n]
    
    def _calculate_bottleneck_score(self, node, cutoff_time) -> Dict:
        """
        Multi-factor bottleneck scoring for a single node.
        
        Factors:
        1. Utilization (30%) - How busy is this machine?
        2. Queue time (25%) - Are items waiting?
        3. Variance (20%) - Is performance unstable?
        4. Centrality (15%) - How critical in network?
        5. Downstream impact (10%) - Does it cause delays?
        """
        from models.graph import ProcessEvent
        
        # Get events where this node is the target (work done at this machine)
        events = ProcessEvent.query.join(ProcessEvent.edge).filter(
            ProcessEvent.edge.has(target_node_id=node.id),
            ProcessEvent.start_time >= cutoff_time
        ).all()
        
        if not events:
            return {
                'total_score': 0,
                'utilization_score': 0,
                'queue_score': 0,
                'variance_score': 0,
                'centrality_score': 0,
                'downstream_score': 0,
                'event_count': 0
            }
        
        durations = [e.duration for e in events if e.duration]
        
        # Factor 1: Utilization
        time_span = (datetime.now() - cutoff_time).total_seconds() / 3600  # hours
        actual_throughput = len(events) / time_span if time_span > 0 else 0
        utilization = (actual_throughput / node.theoretical_capacity 
                      if node.theoretical_capacity and node.theoretical_capacity > 0 
                      else 0)
        utilization_score = min(utilization / 0.95, 1.0) * 30  # 0-30 points
        
        # Factor 2: Queue time (time between consecutive events)
        queue_score = self._calculate_queue_score(events) * 25  # 0-25 points
        
        # Factor 3: Variance (coefficient of variation)
        if durations and len(durations) > 1:
            mean_duration = np.mean(durations)
            std_duration = np.std(durations)
            cv = std_duration / mean_duration if mean_duration > 0 else 0
            variance_score = min(cv / 0.5, 1.0) * 20  # 0-20 points
        else:
            variance_score = 0
        
        # Factor 4: Centrality (betweenness)
        centrality_score = self._calculate_centrality_score(node.id) * 15  # 0-15 points
        
        # Factor 5: Downstream impact
        downstream_score = self._calculate_downstream_impact(node.id, cutoff_time) * 10  # 0-10 points
        
        total_score = (utilization_score + queue_score + variance_score + 
                      centrality_score + downstream_score)
        
        return {
            'total_score': round(total_score, 2),
            'utilization_score': round(utilization_score, 2),
            'queue_score': round(queue_score, 2),
            'variance_score': round(variance_score, 2),
            'centrality_score': round(centrality_score, 2),
            'downstream_score': round(downstream_score, 2),
            'event_count': len(events),
            'actual_throughput': round(actual_throughput, 2),
            'utilization_percent': round(utilization * 100, 1),
            'cv': round(cv, 3) if durations and len(durations) > 1 else 0
        }
    
    def _calculate_queue_score(self, events) -> float:
        """
        Calculate normalized queue score based on wait times between events.
        Returns value between 0 and 1.
        """
        if len(events) < 2:
            return 0
        
        # Sort by start time
        sorted_events = sorted(events, key=lambda e: e.start_time)
        
        # Calculate gaps between consecutive events
        queue_times = []
        for i in range(1, len(sorted_events)):
            prev_end = sorted_events[i-1].end_time
            curr_start = sorted_events[i].start_time
            if prev_end and curr_start:
                gap = (curr_start - prev_end).total_seconds()
                if gap > 0:  # Only count positive gaps (actual queue time)
                    queue_times.append(gap)
        
        if not queue_times:
            return 0
        
        # Normalize: average queue time relative to average process time
        avg_queue = np.mean(queue_times)
        avg_duration = np.mean([e.duration for e in events if e.duration])
        
        if avg_duration and avg_duration > 0:
            queue_ratio = avg_queue / avg_duration
            return min(queue_ratio, 1.0)  # Cap at 1.0
        
        return 0
    
    def _calculate_centrality_score(self, node_id) -> float:
        """
        Calculate betweenness centrality (how critical node is to network flow).
        Returns normalized value between 0 and 1.
        """
        if not self.nx_graph or self.nx_graph.number_of_nodes() < 2:
            return 0
        
        try:
            centrality = nx.betweenness_centrality(self.nx_graph)
            return centrality.get(node_id, 0)
        except:
            return 0
    
    def _calculate_downstream_impact(self, node_id, cutoff_time) -> float:
        """
        Measure how much this node delays downstream processes.
        Returns normalized value between 0 and 1.
        """
        from models.graph import ProcessEvent, GraphEdge
        
        # Get outgoing edges from this node
        outgoing_edges = GraphEdge.query.filter_by(
            graph_id=self.graph_id,
            source_node_id=node_id
        ).all()
        
        if not outgoing_edges:
            return 0
        
        # For each downstream edge, check if actual times exceed expected
        delays = []
        for edge in outgoing_edges:
            events = ProcessEvent.query.filter(
                ProcessEvent.edge_id == edge.id,
                ProcessEvent.start_time >= cutoff_time
            ).all()
            
            if events and edge.expected_duration:
                actual_durations = [e.duration for e in events if e.duration]
                if actual_durations:
                    avg_actual = np.mean(actual_durations)
                    delay_ratio = (avg_actual - edge.expected_duration) / edge.expected_duration
                    if delay_ratio > 0:
                        delays.append(delay_ratio)
        
        if not delays:
            return 0
        
        # Return average delay ratio, capped at 1.0
        return min(np.mean(delays), 1.0)
    
    # ==================== GRAPH METRICS ====================
    
    def calculate_critical_path(self) -> Dict:
        """
        Find the critical path (longest path) through the process graph.
        Uses expected durations as edge weights.
        
        Returns:
            Dict with path nodes and total duration
        """
        if not self.nx_graph:
            return {'path': [], 'total_duration': 0}
        
        try:
            # For DAG, use longest path
            if nx.is_directed_acyclic_graph(self.nx_graph):
                # Weight by expected duration
                for u, v, data in self.nx_graph.edges(data=True):
                    if 'expected_duration' not in data or data['expected_duration'] is None:
                        data['weight'] = 1
                    else:
                        data['weight'] = -data['expected_duration']  # Negative for longest path
                
                path = nx.dag_longest_path(self.nx_graph, weight='weight')
                
                # Calculate total duration
                total_duration = 0
                for i in range(len(path) - 1):
                    edge_data = self.nx_graph[path[i]][path[i+1]]
                    total_duration += abs(edge_data.get('weight', 0))
                
                # Get machine names
                path_names = [self.nx_graph.nodes[node_id]['name'] for node_id in path]
                
                return {
                    'path': path_names,
                    'node_ids': path,
                    'total_duration': total_duration,
                    'is_dag': True
                }
            else:
                # Graph has cycles, return note
                return {
                    'path': [],
                    'total_duration': 0,
                    'is_dag': False,
                    'message': 'Graph contains cycles (rework loops)'
                }
        except Exception as e:
            return {
                'path': [],
                'total_duration': 0,
                'error': str(e)
            }
    
    def calculate_node_metrics(self, node_id, time_window_hours: int = 24) -> Dict:
        """
        Calculate comprehensive metrics for a single node.
        
        Returns:
            Dict with throughput, utilization, variance, queue times, etc.
        """
        from models.graph import GraphNode, ProcessEvent
        
        node = GraphNode.query.get(node_id)
        if not node:
            return {}
        
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        
        # Get all events at this node
        events = ProcessEvent.query.join(ProcessEvent.edge).filter(
            ProcessEvent.edge.has(target_node_id=node_id),
            ProcessEvent.start_time >= cutoff_time
        ).all()
        
        if not events:
            return {
                'node_id': node_id,
                'machine_name': node.machine_name,
                'event_count': 0,
                'throughput': 0,
                'utilization': 0
            }
        
        durations = [e.duration for e in events if e.duration]
        
        # Calculate metrics
        time_span_hours = time_window_hours
        throughput = len(events) / time_span_hours
        utilization = (throughput / node.theoretical_capacity 
                      if node.theoretical_capacity and node.theoretical_capacity > 0 
                      else None)
        
        return {
            'node_id': node_id,
            'machine_name': node.machine_name,
            'event_count': len(events),
            'throughput': round(throughput, 2),
            'theoretical_capacity': node.theoretical_capacity,
            'utilization': round(utilization * 100, 1) if utilization else None,
            'mean_duration': round(np.mean(durations), 2) if durations else 0,
            'median_duration': round(np.median(durations), 2) if durations else 0,
            'std_duration': round(np.std(durations), 2) if len(durations) > 1 else 0,
            'min_duration': round(min(durations), 2) if durations else 0,
            'max_duration': round(max(durations), 2) if durations else 0,
            'cv': round(np.std(durations) / np.mean(durations), 3) if durations and np.mean(durations) > 0 else 0,
            'in_degree': self.nx_graph.in_degree(node_id) if self.nx_graph else 0,
            'out_degree': self.nx_graph.out_degree(node_id) if self.nx_graph else 0,
            'betweenness': round(self._calculate_centrality_score(node_id), 3)
        }
    
    def calculate_edge_metrics(self, edge_id, time_window_hours: int = 24) -> Dict:
        """
        Calculate metrics for a specific process flow (edge).
        
        Returns:
            Dict with flow rate, mean time, variance, etc.
        """
        from models.graph import GraphEdge, ProcessEvent
        
        edge = GraphEdge.query.get(edge_id)
        if not edge:
            return {}
        
        cutoff_time = datetime.now() - timedelta(hours=time_window_hours)
        
        events = ProcessEvent.query.filter(
            ProcessEvent.edge_id == edge_id,
            ProcessEvent.start_time >= cutoff_time
        ).all()
        
        if not events:
            return {
                'edge_id': edge_id,
                'process_name': edge.process_name,
                'source': edge.source_node.machine_name if edge.source_node else None,
                'target': edge.target_node.machine_name if edge.target_node else None,
                'event_count': 0,
                'flow_rate': 0
            }
        
        durations = [e.duration for e in events if e.duration]
        
        return {
            'edge_id': edge_id,
            'process_name': edge.process_name,
            'source': edge.source_node.machine_name if edge.source_node else None,
            'target': edge.target_node.machine_name if edge.target_node else None,
            'event_count': len(events),
            'flow_rate': round(len(events) / time_window_hours, 2),
            'mean_duration': round(np.mean(durations), 2) if durations else 0,
            'expected_duration': edge.expected_duration,
            'variance': round(np.var(durations), 2) if len(durations) > 1 else 0,
            'cv': round(np.std(durations) / np.mean(durations), 3) if durations and np.mean(durations) > 0 else 0,
            'performance_ratio': round(np.mean(durations) / edge.expected_duration, 2) 
                               if durations and edge.expected_duration and edge.expected_duration > 0 
                               else None
        }
    
    def get_graph_summary(self) -> Dict:
        """
        High-level summary of the entire process graph.
        
        Returns:
            Dict with graph-level statistics
        """
        from models.graph import ProcessGraph, GraphNode, GraphEdge
        
        graph = ProcessGraph.query.get(self.graph_id)
        if not graph:
            return {}
        
        nodes = GraphNode.query.filter_by(graph_id=self.graph_id).all()
        edges = GraphEdge.query.filter_by(graph_id=self.graph_id).all()
        
        # NetworkX metrics
        is_dag = nx.is_directed_acyclic_graph(self.nx_graph) if self.nx_graph else False
        density = nx.density(self.nx_graph) if self.nx_graph else 0
        
        # Try to identify strongly connected components
        try:
            num_components = nx.number_strongly_connected_components(self.nx_graph)
        except:
            num_components = 1
        
        return {
            'graph_id': self.graph_id,
            'name': graph.name,
            'node_count': len(nodes),
            'edge_count': len(edges),
            'is_dag': is_dag,
            'density': round(density, 3),
            'strongly_connected_components': num_components,
            'has_cycles': not is_dag,
            'avg_degree': round(2 * len(edges) / len(nodes), 2) if nodes else 0
        }


# ==================== HELPER FUNCTIONS ====================

def sigmoid(x, steepness=0.1):
    """Sigmoid function for normalizing values to 0-1 range."""
    return 1 / (1 + np.exp(-steepness * x))


def detect_process_bottleneck_simple(graph_id, db_session, hours=24):
    """
    Simplified bottleneck detection function.
    Returns the top bottleneck node name.
    
    Args:
        graph_id: ProcessGraph ID
        db_session: SQLAlchemy session
        hours: Time window in hours
    
    Returns:
        String: Name of bottleneck machine or "None"
    """
    analyzer = ProcessGraphAnalyzer(graph_id, db_session)
    bottlenecks = analyzer.detect_bottlenecks(time_window_hours=hours, top_n=1)
    
    if bottlenecks and bottlenecks[0]['total_score'] > 30:  # Threshold
        return bottlenecks[0]['machine_name']
    
    return "None"
