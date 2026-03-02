"""
What-If Scenario Modeling
Simulate changes to the process graph and predict impact on bottlenecks
"""
import copy
from typing import Dict, List, Optional
import numpy as np
from models.graph import ProcessGraph, GraphNode, GraphEdge, ProcessEvent
from analysis.topology import ProcessGraphAnalyzer


class ScenarioModeler:
    """
    Model what-if scenarios for process optimization
    """
    
    def __init__(self, graph_id, db_session):
        self.graph_id = graph_id
        self.db = db_session
        self.baseline_analyzer = ProcessGraphAnalyzer(graph_id, db_session)
    
    def get_baseline_metrics(self, hours: int = 24) -> Dict:
        """
        Get current state metrics as baseline
        """
        bottlenecks = self.baseline_analyzer.detect_bottlenecks(
            time_window_hours=hours,
            top_n=10
        )
        
        summary = self.baseline_analyzer.get_graph_summary()
        critical_path = self.baseline_analyzer.calculate_critical_path()
        
        # Calculate overall metrics
        total_score = sum(b['total_score'] for b in bottlenecks if b['event_count'] > 0)
        avg_score = total_score / len([b for b in bottlenecks if b['event_count'] > 0]) if bottlenecks else 0
        
        return {
            'bottlenecks': bottlenecks,
            'summary': summary,
            'critical_path': critical_path,
            'avg_bottleneck_score': round(avg_score, 2),
            'total_bottleneck_score': round(total_score, 2)
        }
    
    def simulate_capacity_increase(self, node_id: int, new_capacity: float, hours: int = 24) -> Dict:
        """
        Simulate what happens if we increase a machine's capacity
        
        Args:
            node_id: ID of the node to modify
            new_capacity: New theoretical capacity (units/hour)
            hours: Time window for analysis
        
        Returns:
            Comparison of before and after
        """
        # Get baseline
        baseline = self.get_baseline_metrics(hours)
        
        # Get the node
        node = GraphNode.query.get(node_id)
        if not node:
            return {'error': 'Node not found'}
        
        original_capacity = node.theoretical_capacity
        
        # Find this node's bottleneck data
        node_baseline = next(
            (b for b in baseline['bottlenecks'] if b['node_id'] == node_id),
            None
        )
        
        if not node_baseline or node_baseline['event_count'] == 0:
            return {
                'error': 'No data for this node',
                'node': node.machine_name
            }
        
        # Simulate new utilization
        current_throughput = node_baseline['actual_throughput']
        new_utilization = (current_throughput / new_capacity) * 100 if new_capacity > 0 else 0
        
        # Estimate new bottleneck score (simplified)
        # In reality, would need to recalculate all factors
        utilization_improvement = node_baseline['utilization_percent'] - new_utilization
        score_improvement = utilization_improvement * 0.3  # 30% weight on utilization
        
        new_score = max(0, node_baseline['total_score'] - score_improvement)
        
        # Calculate impact on downstream
        downstream_improvement = self._estimate_downstream_impact(
            node_id, 
            utilization_improvement,
            baseline
        )
        
        return {
            'scenario': 'capacity_increase',
            'node': node.machine_name,
            'changes': {
                'capacity': {
                    'original': original_capacity,
                    'new': new_capacity,
                    'change_percent': round(((new_capacity - original_capacity) / original_capacity) * 100, 1)
                }
            },
            'baseline': {
                'utilization': node_baseline['utilization_percent'],
                'bottleneck_score': node_baseline['total_score'],
                'throughput': node_baseline['actual_throughput']
            },
            'projected': {
                'utilization': round(new_utilization, 1),
                'bottleneck_score': round(new_score, 1),
                'throughput': current_throughput,
                'score_improvement': round(score_improvement, 1)
            },
            'impact': {
                'primary_improvement': round(score_improvement, 1),
                'downstream_improvement': round(downstream_improvement, 1),
                'total_improvement': round(score_improvement + downstream_improvement, 1)
            },
            'recommendation': self._generate_recommendation(
                score_improvement,
                new_score,
                new_capacity,
                original_capacity
            )
        }
    
    def simulate_add_machine(self, machine_name: str, machine_type: str, 
                           capacity: float, hours: int = 24) -> Dict:
        """
        Simulate adding a new machine in parallel to existing process
        
        Args:
            machine_name: Name of new machine
            machine_type: Type of machine
            capacity: Theoretical capacity
            hours: Time window
        
        Returns:
            Impact analysis
        """
        baseline = self.get_baseline_metrics(hours)
        
        # Find the biggest bottleneck
        top_bottleneck = next(
            (b for b in baseline['bottlenecks'] if b['event_count'] > 0),
            None
        )
        
        if not top_bottleneck:
            return {'error': 'No bottleneck data available'}
        
        # Simulate adding parallel capacity
        original_capacity = top_bottleneck.get('utilization_percent', 0)
        combined_capacity = original_capacity + capacity
        
        # Calculate load distribution
        load_per_machine = top_bottleneck['actual_throughput'] / 2  # Split evenly
        new_utilization = (load_per_machine / capacity) * 100 if capacity > 0 else 0
        
        return {
            'scenario': 'add_machine',
            'new_machine': {
                'name': machine_name,
                'type': machine_type,
                'capacity': capacity
            },
            'baseline': {
                'bottleneck': top_bottleneck['machine_name'],
                'current_score': top_bottleneck['total_score'],
                'current_utilization': top_bottleneck['utilization_percent']
            },
            'projected': {
                'load_distribution': 'Split 50/50 between machines',
                'new_utilization_per_machine': round(new_utilization, 1),
                'estimated_score_reduction': round(top_bottleneck['total_score'] * 0.6, 1),
                'throughput_increase_potential': '100%'
            },
            'recommendation': f'Adding {machine_name} would reduce bottleneck score by ~40-60%'
        }
    
    def simulate_remove_process_step(self, edge_id: int, hours: int = 24) -> Dict:
        """
        Simulate removing a process step (edge)
        
        Args:
            edge_id: Edge to remove
            hours: Time window
        
        Returns:
            Impact analysis
        """
        edge = GraphEdge.query.get(edge_id)
        if not edge:
            return {'error': 'Edge not found'}
        
        baseline = self.get_baseline_metrics(hours)
        
        # Get events for this edge
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(hours=hours)
        
        events = ProcessEvent.query.filter(
            ProcessEvent.edge_id == edge_id,
            ProcessEvent.start_time >= cutoff
        ).all()
        
        if not events:
            return {
                'scenario': 'remove_process',
                'edge': edge.process_name,
                'impact': 'No data - cannot assess impact'
            }
        
        avg_duration = np.mean([e.duration for e in events if e.duration])
        
        # Calculate time savings
        time_saved_per_part = avg_duration
        parts_per_day = len(events) / (hours / 24)
        daily_time_savings = time_saved_per_part * parts_per_day / 3600  # hours
        
        return {
            'scenario': 'remove_process_step',
            'edge': {
                'process': edge.process_name,
                'from': edge.source_node.machine_name,
                'to': edge.target_node.machine_name
            },
            'baseline': {
                'avg_duration': round(avg_duration, 1),
                'daily_occurrences': round(parts_per_day, 1)
            },
            'projected_impact': {
                'time_saved_per_part': f'{round(avg_duration, 1)}s',
                'daily_time_savings': f'{round(daily_time_savings, 2)} hours',
                'throughput_increase': 'Depends on critical path impact'
            },
            'critical_path_impact': self._check_critical_path_impact(edge_id, baseline),
            'recommendation': 'Review if this step adds value or can be automated'
        }
    
    def compare_scenarios(self, scenarios: List[Dict]) -> Dict:
        """
        Compare multiple scenarios side by side
        
        Args:
            scenarios: List of scenario results from other methods
        
        Returns:
            Comparison table
        """
        comparison = {
            'scenarios': [],
            'best_option': None,
            'best_score_improvement': 0
        }
        
        for scenario in scenarios:
            if 'projected' in scenario and 'score_improvement' in scenario.get('impact', {}):
                improvement = scenario['impact']['total_improvement']
                comparison['scenarios'].append({
                    'type': scenario['scenario'],
                    'description': scenario.get('node', scenario.get('new_machine', {}).get('name', 'Unknown')),
                    'score_improvement': improvement,
                    'cost_estimate': 'N/A',  # Would integrate with cost data
                    'roi': 'N/A'
                })
                
                if improvement > comparison['best_score_improvement']:
                    comparison['best_score_improvement'] = improvement
                    comparison['best_option'] = scenario['scenario']
        
        return comparison
    
    def _estimate_downstream_impact(self, node_id: int, utilization_improvement: float, 
                                   baseline: Dict) -> float:
        """
        Estimate how improving one node affects downstream nodes
        """
        # Get outgoing edges
        outgoing_edges = GraphEdge.query.filter_by(source_node_id=node_id).all()
        
        if not outgoing_edges:
            return 0
        
        # Simple heuristic: downstream improvement is 50% of primary improvement
        return utilization_improvement * 0.15  # 15% weight downstream factor
    
    def _check_critical_path_impact(self, edge_id: int, baseline: Dict) -> str:
        """
        Check if removing an edge affects the critical path
        """
        critical_path = baseline.get('critical_path', {})
        
        if not critical_path.get('path'):
            return 'Unknown - no critical path identified'
        
        # In a full implementation, would check if edge is on critical path
        return 'Requires detailed critical path analysis'
    
    def _generate_recommendation(self, score_improvement: float, new_score: float,
                                 new_capacity: float, original_capacity: float) -> str:
        """
        Generate actionable recommendation
        """
        improvement_pct = (score_improvement / 100) * 100
        
        if improvement_pct > 30:
            return f'Highly recommended: {improvement_pct:.1f}% improvement expected'
        elif improvement_pct > 15:
            return f'Recommended: {improvement_pct:.1f}% improvement expected'
        elif improvement_pct > 5:
            return f'Consider: {improvement_pct:.1f}% improvement (marginal)'
        else:
            return 'Limited impact - investigate other options'


# ============================================================================
# API Helper Functions
# ============================================================================

def run_scenario(graph_id, db_session, scenario_type: str, params: Dict) -> Dict:
    """
    Run a specific scenario
    
    Args:
        graph_id: Graph ID
        db_session: Database session
        scenario_type: 'capacity_increase', 'add_machine', 'remove_step'
        params: Scenario-specific parameters
    
    Returns:
        Scenario results
    """
    modeler = ScenarioModeler(graph_id, db_session)
    
    if scenario_type == 'capacity_increase':
        return modeler.simulate_capacity_increase(
            node_id=params['node_id'],
            new_capacity=params['new_capacity'],
            hours=params.get('hours', 24)
        )
    
    elif scenario_type == 'add_machine':
        return modeler.simulate_add_machine(
            machine_name=params['machine_name'],
            machine_type=params['machine_type'],
            capacity=params['capacity'],
            hours=params.get('hours', 24)
        )
    
    elif scenario_type == 'remove_step':
        return modeler.simulate_remove_process_step(
            edge_id=params['edge_id'],
            hours=params.get('hours', 24)
        )
    
    else:
        return {'error': f'Unknown scenario type: {scenario_type}'}
