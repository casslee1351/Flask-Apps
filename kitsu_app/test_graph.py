# """
# Test file to verify graph module installation
# Run this after completing Steps 1-5 of the installation guide

# Usage: python test_graph.py
# """
# from kitsu_app import app, db
# from models.graph import ProcessGraph, GraphNode, GraphEdge, ProcessEvent

# def test_graph_creation():
#     """Test creating a simple process graph"""
#     print("=" * 60)
#     print("Testing Graph Module Installation")
#     print("=" * 60)
    
#     with app.app_context():
#         print("\n📊 Step 1: Creating test graph...")
        
#         # Create a simple test graph
#         graph = ProcessGraph(
#             name="Test Assembly Line",
#             description="Testing the graph module installation"
#         )
#         db.session.add(graph)
#         db.session.flush()  # Get the ID without committing
        
#         print(f"   ✅ Graph created: '{graph.name}' (ID: {graph.id})")
        
#         print("\n🏭 Step 2: Adding machines (nodes)...")
        
#         # Add a couple of nodes (machines)
#         node1 = GraphNode(
#             graph_id=graph.id,
#             machine_name="CNC Cutter",
#             machine_type="CNC",
#             theoretical_capacity=50.0,
#             position_x=100,
#             position_y=100
#         )
        
#         node2 = GraphNode(
#             graph_id=graph.id,
#             machine_name="Assembly Station",
#             machine_type="Assembly",
#             theoretical_capacity=40.0,
#             position_x=300,
#             position_y=100
#         )
        
#         node3 = GraphNode(
#             graph_id=graph.id,
#             machine_name="Quality Inspection",
#             machine_type="Inspection",
#             theoretical_capacity=60.0,
#             position_x=500,
#             position_y=100
#         )
        
#         db.session.add_all([node1, node2, node3])
#         db.session.flush()
        
#         print(f"   ✅ Added 3 machines:")
#         print(f"      - {node1.machine_name} (ID: {node1.id})")
#         print(f"      - {node2.machine_name} (ID: {node2.id})")
#         print(f"      - {node3.machine_name} (ID: {node3.id})")
        
#         print("\n🔗 Step 3: Creating process flows (edges)...")
        
#         # Add edges connecting them
#         edge1 = GraphEdge(
#             graph_id=graph.id,
#             source_node_id=node1.id,
#             target_node_id=node2.id,
#             process_name="Cutting to Assembly",
#             expected_duration=120.0,
#             sequence_order=1
#         )
        
#         edge2 = GraphEdge(
#             graph_id=graph.id,
#             source_node_id=node2.id,
#             target_node_id=node3.id,
#             process_name="Assembly to Inspection",
#             expected_duration=90.0,
#             sequence_order=2
#         )
        
#         db.session.add_all([edge1, edge2])
#         db.session.commit()
        
#         print(f"   ✅ Added 2 process flows:")
#         print(f"      - {edge1.process_name}")
#         print(f"      - {edge2.process_name}")
        
#         print("\n📈 Step 4: Testing analysis module...")
        
#         # Test the analysis module
#         try:
#             from analysis.topology import ProcessGraphAnalyzer
            
#             analyzer = ProcessGraphAnalyzer(graph.id, db.session)
#             summary = analyzer.get_graph_summary()
            
#             print(f"   ✅ Analysis module loaded successfully!")
#             print(f"   Graph Summary:")
#             print(f"      - Name: {summary['name']}")
#             print(f"      - Nodes: {summary['node_count']}")
#             print(f"      - Edges: {summary['edge_count']}")
#             print(f"      - Is DAG: {summary['is_dag']}")
#             print(f"      - Density: {summary['density']}")
            
#             # Test critical path calculation
#             critical_path = analyzer.calculate_critical_path()
#             if critical_path.get('path'):
#                 print(f"   Critical Path: {' → '.join(critical_path['path'])}")
#                 print(f"   Total Duration: {critical_path['total_duration']} seconds")
            
#         except ImportError as e:
#             print(f"   ⚠️  Warning: Could not import analysis module")
#             print(f"      Error: {e}")
#             print(f"      This is OK if you haven't added analysis/topology.py yet")
#             return False
        
#         print("\n🎉 SUCCESS! All modules integrated correctly.")
#         print("\n" + "=" * 60)
#         print("Next steps:")
#         print("1. Open implementation_checklist.html in your browser")
#         print("2. Start working through Phase 1 tasks")
#         print("3. Build your real process graph with your manufacturing data")
#         print("=" * 60)
        
#         return True


# def test_database_tables():
#     """Verify all required tables exist"""
#     print("\n🗄️  Checking database tables...")
    
#     with app.app_context():
#         from sqlalchemy import inspect
#         inspector = inspect(db.engine)
#         tables = inspector.get_table_names()
        
#         required_tables = ['process_graph', 'graph_node', 'graph_edge', 'process_event']
#         missing_tables = [t for t in required_tables if t not in tables]
        
#         if missing_tables:
#             print(f"   ❌ Missing tables: {', '.join(missing_tables)}")
#             print(f"   All tables found: {', '.join(tables)}")
#             print("\n   Please run db.create_all() first!")
#             return False
#         else:
#             print(f"   ✅ All required tables exist:")
#             for table in required_tables:
#                 print(f"      - {table}")
#             return True


# if __name__ == "__main__":
#     print("\n" + "🚀 " * 20)
#     print("\nGRAPH MODULE INSTALLATION TEST")
#     print("\n" + "🚀 " * 20)
    
#     try:
#         # First check if tables exist
#         if not test_database_tables():
#             print("\n❌ FAILED: Database tables not found")
#             print("\nMake sure you:")
#             print("1. Added 'from models.graph import ...' to kitsu_app.py")
#             print("2. Ran the app once to create tables with db.create_all()")
#             exit(1)
        
#         # Then test graph creation
#         if test_graph_creation():
#             print("\n✨ Installation verification complete! ✨\n")
#             exit(0)
#         else:
#             print("\n⚠️  Partial success - check warnings above\n")
#             exit(0)
            
#     except Exception as e:
#         print(f"\n❌ ERROR: {e}\n")
#         import traceback
#         traceback.print_exc()
        
#         print("\n" + "=" * 60)
#         print("Troubleshooting tips:")
#         print("1. Make sure you completed Steps 1-5 of INSTALLATION_GUIDE.md")
#         print("2. Check that models/graph.py exists and imports db correctly")
#         print("3. Verify networkx is installed: pip install networkx numpy")
#         print("4. Make sure analysis/__init__.py exists (can be empty)")
#         print("=" * 60)
#         exit(1)

from kitsu_app import app, db
from models.graph import ProcessEvent

with app.app_context():
    events = ProcessEvent.query.all()
    print(f"Total events: {len(events)}")
    for event in events:
        print(f"  - {event.edge.process_name}: {event.duration}s by {event.operator}")