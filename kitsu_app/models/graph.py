"""
Graph Database Models for Manufacturing Process Network
Ready-to-use version for your Flask project

Installation: Save this file as models/graph.py
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship

# Import db from your existing timer_run module
from models.timer_run import db


class ProcessGraph(db.Model):
    """
    Represents a complete manufacturing process flow graph.
    Multiple graphs can exist for different product lines or process configurations.
    """
    __tablename__ = 'process_graph'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    nodes = relationship('GraphNode', back_populates='graph', cascade='all, delete-orphan')
    edges = relationship('GraphEdge', back_populates='graph', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active,
            'node_count': len(self.nodes),
            'edge_count': len(self.edges)
        }


class GraphNode(db.Model):
    """
    Represents a machine/workstation in the manufacturing process.
    Nodes are the vertices in the process graph.
    """
    __tablename__ = 'graph_node'
    
    id = Column(Integer, primary_key=True)
    graph_id = Column(Integer, ForeignKey('process_graph.id'), nullable=False)
    
    # Core attributes
    machine_name = Column(String(200), nullable=False)
    machine_type = Column(String(100))  # e.g., "CNC", "Assembly", "Inspection"
    
    # Capacity planning
    theoretical_capacity = Column(Float)  # units per hour
    theoretical_cycle_time = Column(Float)  # seconds per unit
    
    # Visualization
    position_x = Column(Float, default=0)
    position_y = Column(Float, default=0)
    
    # Extensibility
    custom_metadata = Column(JSON)  # Store any additional machine-specific data
    
    # Relationships
    graph = relationship('ProcessGraph', back_populates='nodes')
    outgoing_edges = relationship('GraphEdge', foreign_keys='GraphEdge.source_node_id', 
                                  back_populates='source_node')
    incoming_edges = relationship('GraphEdge', foreign_keys='GraphEdge.target_node_id',
                                  back_populates='target_node')
    
    def to_dict(self):
        return {
            'id': self.id,
            'graph_id': self.graph_id,
            'machine_name': self.machine_name,
            'machine_type': self.machine_type,
            'theoretical_capacity': self.theoretical_capacity,
            'theoretical_cycle_time': self.theoretical_cycle_time,
            'position': {'x': self.position_x, 'y': self.position_y},
            'custom_metadata': self.custom_metadata
        }


class GraphEdge(db.Model):
    """
    Represents a process flow between two machines.
    Edges are directed (source → target) and weighted by expected duration.
    """
    __tablename__ = 'graph_edge'
    
    id = Column(Integer, primary_key=True)
    graph_id = Column(Integer, ForeignKey('process_graph.id'), nullable=False)
    
    # Topology
    source_node_id = Column(Integer, ForeignKey('graph_node.id'), nullable=False)
    target_node_id = Column(Integer, ForeignKey('graph_node.id'), nullable=False)
    
    # Process definition
    process_name = Column(String(200), nullable=False)  # e.g., "Drilling", "Quality Check"
    sequence_order = Column(Integer)  # Order in overall workflow (optional)
    
    # Expected performance
    expected_duration = Column(Float)  # seconds (baseline/standard time)
    expected_setup_time = Column(Float)  # seconds (if applicable)
    
    # Extensibility
    custom_metadata = Column(JSON)  # Process-specific parameters
    
    # Relationships
    graph = relationship('ProcessGraph', back_populates='edges')
    source_node = relationship('GraphNode', foreign_keys=[source_node_id],
                              back_populates='outgoing_edges')
    target_node = relationship('GraphNode', foreign_keys=[target_node_id],
                              back_populates='incoming_edges')
    events = relationship('ProcessEvent', back_populates='edge', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'graph_id': self.graph_id,
            'source_node_id': self.source_node_id,
            'target_node_id': self.target_node_id,
            'source_machine': self.source_node.machine_name if self.source_node else None,
            'target_machine': self.target_node.machine_name if self.target_node else None,
            'process_name': self.process_name,
            'sequence_order': self.sequence_order,
            'expected_duration': self.expected_duration,
            'custom_metadata': self.custom_metadata
        }


class ProcessEvent(db.Model):
    """
    Represents an actual occurrence of a process flow (edge traversal).
    This is the temporal/observational data linked to the graph topology.
    """
    __tablename__ = 'process_event'
    
    id = Column(Integer, primary_key=True)
    edge_id = Column(Integer, ForeignKey('graph_edge.id'), nullable=False)
    
    # Who, when, how long
    operator = Column(String(200))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    duration = Column(Float)  # seconds (calculated: end_time - start_time)
    
    # Batch/job tracking
    batch_id = Column(String(100))  # Link multiple events as one job/batch
    part_number = Column(String(100))  # Individual part identifier
    
    # Observations
    notes = Column(Text)
    quality_flag = Column(Boolean, default=True)  # False if defect/rework
    
    # Extensibility
    custom_metadata = Column(JSON)  # Event-specific data (temperature, pressure, etc.)
    
    # Relationships
    edge = relationship('GraphEdge', back_populates='events')
    
    def to_dict(self):
        return {
            'id': self.id,
            'edge_id': self.edge_id,
            'process_name': self.edge.process_name if self.edge else None,
            'source_machine': self.edge.source_node.machine_name if self.edge and self.edge.source_node else None,
            'target_machine': self.edge.target_node.machine_name if self.edge and self.edge.target_node else None,
            'operator': self.operator,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration': self.duration,
            'batch_id': self.batch_id,
            'part_number': self.part_number,
            'notes': self.notes,
            'quality_flag': self.quality_flag,
            'custom_metadata': self.custom_metadata
        }
    
    @property
    def calculated_duration(self):
        """Calculate duration from timestamps if not stored"""
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return self.duration


# Migration helper: Convert existing TimerRun to ProcessEvent
def migrate_timer_run_to_event(timer_run, edge_id):
    """
    Convert an existing TimerRun to a ProcessEvent linked to a graph edge.
    
    Args:
        timer_run: TimerRun instance
        edge_id: ID of the GraphEdge this run corresponds to
    
    Returns:
        ProcessEvent instance (not yet committed)
    """
    event = ProcessEvent(
        edge_id=edge_id,
        operator=timer_run.operator,
        start_time=timer_run.start_time,
        end_time=timer_run.end_time,
        duration=timer_run.duration,
        notes=timer_run.notes,
        custom_metadata={'legacy_id': timer_run.id, 'time_type': timer_run.time_type}
    )
    return event
