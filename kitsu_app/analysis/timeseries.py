"""
Time-Series Bottleneck Analysis
Track bottleneck scores over time to identify trends and patterns
"""
from datetime import datetime, timedelta
from typing import List, Dict
import numpy as np
from models.graph import ProcessGraph, GraphNode, ProcessEvent
from analysis.topology import ProcessGraphAnalyzer


class TimeSeriesAnalyzer:
    """
    Analyzes how bottlenecks change over time
    """
    
    def __init__(self, graph_id, db_session):
        self.graph_id = graph_id
        self.db = db_session
    
    def analyze_bottleneck_trends(self, days: int = 7, interval_hours: int = 4) -> Dict:
        """
        Track bottleneck scores over time
        
        Args:
            days: How many days back to analyze
            interval_hours: Time interval for each data point (default 4 hours)
        
        Returns:
            Dict with time series data for each node
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # Calculate number of intervals
        total_hours = days * 24
        num_intervals = total_hours // interval_hours
        
        # Initialize data structure
        nodes = GraphNode.query.filter_by(graph_id=self.graph_id).all()
        time_series = {
            'timestamps': [],
            'nodes': {}
        }
        
        for node in nodes:
            time_series['nodes'][node.machine_name] = {
                'node_id': node.id,
                'scores': [],
                'utilizations': [],
                'event_counts': []
            }
        
        # Analyze each time interval
        for i in range(num_intervals):
            interval_end = end_time - timedelta(hours=i * interval_hours)
            interval_start = interval_end - timedelta(hours=interval_hours)
            
            time_series['timestamps'].insert(0, interval_end.isoformat())
            
            # Get events in this interval
            analyzer = ProcessGraphAnalyzer(self.graph_id, self.db)
            
            # Temporarily modify the analyzer to look at specific time window
            cutoff_time = interval_start
            
            for node in nodes:
                # Get events for this node in this interval
                events = ProcessEvent.query.join(ProcessEvent.edge).filter(
                    ProcessEvent.edge.has(target_node_id=node.id),
                    ProcessEvent.start_time >= interval_start,
                    ProcessEvent.start_time < interval_end
                ).all()
                
                if events:
                    # Calculate bottleneck score for this interval
                    durations = [e.duration for e in events if e.duration]
                    
                    # Simple score calculation (could use full analyzer)
                    if node.theoretical_capacity and node.theoretical_capacity > 0:
                        throughput = len(events) / interval_hours
                        utilization = (throughput / node.theoretical_capacity) * 100
                        
                        # Simplified bottleneck score
                        score = min(utilization, 100)
                    else:
                        score = 0
                        utilization = 0
                    
                    time_series['nodes'][node.machine_name]['scores'].insert(0, round(score, 1))
                    time_series['nodes'][node.machine_name]['utilizations'].insert(0, round(utilization, 1))
                    time_series['nodes'][node.machine_name]['event_counts'].insert(0, len(events))
                else:
                    # No events in this interval
                    time_series['nodes'][node.machine_name]['scores'].insert(0, 0)
                    time_series['nodes'][node.machine_name]['utilizations'].insert(0, 0)
                    time_series['nodes'][node.machine_name]['event_counts'].insert(0, 0)
        
        # Calculate trends
        for node_name, data in time_series['nodes'].items():
            data['trend'] = self._calculate_trend(data['scores'])
            data['volatility'] = self._calculate_volatility(data['scores'])
        
        return time_series
    
    def _calculate_trend(self, scores: List[float]) -> str:
        """
        Determine if bottleneck is getting worse, better, or stable
        """
        if len(scores) < 2:
            return 'insufficient_data'
        
        # Filter out zeros
        non_zero_scores = [s for s in scores if s > 0]
        if len(non_zero_scores) < 2:
            return 'insufficient_data'
        
        # Simple linear regression
        x = np.arange(len(scores))
        y = np.array(scores)
        
        # Remove zero values for trend calculation
        mask = y > 0
        if mask.sum() < 2:
            return 'insufficient_data'
        
        x_filtered = x[mask]
        y_filtered = y[mask]
        
        # Calculate slope
        slope = np.polyfit(x_filtered, y_filtered, 1)[0]
        
        if slope > 2:
            return 'worsening'
        elif slope < -2:
            return 'improving'
        else:
            return 'stable'
    
    def _calculate_volatility(self, scores: List[float]) -> float:
        """
        Calculate how much the bottleneck score fluctuates
        """
        if len(scores) < 2:
            return 0
        
        non_zero_scores = [s for s in scores if s > 0]
        if len(non_zero_scores) < 2:
            return 0
        
        return round(float(np.std(non_zero_scores)), 2)
    
    def detect_pattern_shifts(self, hours: int = 24) -> Dict:
        """
        Detect when the primary bottleneck shifts from one machine to another
        
        Returns:
            Dict with shift events and current vs previous bottleneck
        """
        # Analyze current period
        current_end = datetime.now()
        current_start = current_end - timedelta(hours=hours)
        
        current_analyzer = ProcessGraphAnalyzer(self.graph_id, self.db)
        current_bottlenecks = current_analyzer.detect_bottlenecks(time_window_hours=hours, top_n=3)
        
        # Analyze previous period
        previous_end = current_start
        previous_start = previous_end - timedelta(hours=hours)
        
        # Get events in previous period
        previous_events = ProcessEvent.query.join(ProcessEvent.edge).filter(
            ProcessEvent.edge.has(graph_id=self.graph_id),
            ProcessEvent.start_time >= previous_start,
            ProcessEvent.start_time < previous_end
        ).count()
        
        if previous_events == 0:
            return {
                'shift_detected': False,
                'message': 'Insufficient data in previous period'
            }
        
        # For simplicity, we'll check if top bottleneck changed
        # In production, you'd run full analysis on previous period
        
        current_top = current_bottlenecks[0] if current_bottlenecks else None
        
        return {
            'shift_detected': False,  # Would need previous analysis to compare
            'current_bottleneck': current_top,
            'current_period': f'Last {hours} hours',
            'analysis_note': 'Full shift detection requires storing historical analysis results'
        }
    
    def predict_future_bottleneck(self, hours_ahead: int = 24) -> Dict:
        """
        Use trend analysis to predict which machine might become a bottleneck
        
        Args:
            hours_ahead: How many hours into the future to predict
        
        Returns:
            Dict with predictions
        """
        trends = self.analyze_bottleneck_trends(days=7, interval_hours=4)
        
        predictions = []
        
        for node_name, data in trends['nodes'].items():
            if data['trend'] == 'worsening' and data['volatility'] < 20:
                # Bottleneck is getting worse consistently
                current_score = data['scores'][-1] if data['scores'] else 0
                
                if current_score > 40:
                    predictions.append({
                        'machine': node_name,
                        'current_score': current_score,
                        'trend': 'worsening',
                        'risk_level': 'high' if current_score > 60 else 'medium',
                        'recommendation': f'{node_name} is trending worse and may become a critical bottleneck'
                    })
        
        return {
            'predictions': predictions,
            'prediction_window': f'{hours_ahead} hours',
            'confidence': 'medium',  # Would improve with ML model
            'note': 'Based on recent trend analysis'
        }


# ============================================================================
# API Endpoint Functions
# ============================================================================

def get_bottleneck_time_series(graph_id, db_session, days=7, interval_hours=4):
    """
    Get time series data for API endpoint
    """
    analyzer = TimeSeriesAnalyzer(graph_id, db_session)
    return analyzer.analyze_bottleneck_trends(days=days, interval_hours=interval_hours)


def get_bottleneck_predictions(graph_id, db_session, hours_ahead=24):
    """
    Get predictions for API endpoint
    """
    analyzer = TimeSeriesAnalyzer(graph_id, db_session)
    return analyzer.predict_future_bottleneck(hours_ahead=hours_ahead)
