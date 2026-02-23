"""
Test script for topology analysis module
Run this to verify bottleneck detection is working
"""
from kitsu_app import app, db
from models.graph import ProcessGraph, ProcessEvent
from analysis.topology import ProcessGraphAnalyzer

def test_bottleneck_detection():
    """Test the bottleneck detection on your real graph"""
    
    print("=" * 70)
    print("TESTING BOTTLENECK DETECTION")
    print("=" * 70)
    
    with app.app_context():
        # Get all graphs
        graphs = ProcessGraph.query.filter_by(is_active=True).all()
        
        if not graphs:
            print("\n❌ No graphs found!")
            print("Please create a graph in the graph builder first.")
            return
        
        print(f"\n📊 Found {len(graphs)} graph(s)")
        
        for graph in graphs:
            print(f"\n{'=' * 70}")
            print(f"Analyzing: {graph.name}")
            print(f"{'=' * 70}")
            
            # Check if we have events
            event_count = ProcessEvent.query.join(ProcessEvent.edge).filter(
                ProcessEvent.edge.has(graph_id=graph.id)
            ).count()
            
            print(f"\n📈 Events recorded: {event_count}")
            
            if event_count == 0:
                print("⚠️  No events yet - record some timer runs first!")
                continue
            
            # Create analyzer
            analyzer = ProcessGraphAnalyzer(graph.id, db.session)
            
            # Get graph summary
            print("\n🔍 Graph Summary:")
            summary = analyzer.get_graph_summary()
            print(f"   Nodes: {summary['node_count']}")
            print(f"   Edges: {summary['edge_count']}")
            print(f"   Is DAG: {summary['is_dag']}")
            print(f"   Density: {summary['density']}")
            
            # Detect bottlenecks
            print("\n🚨 Bottleneck Analysis (Last 24 hours):")
            bottlenecks = analyzer.detect_bottlenecks(time_window_hours=24, top_n=5)
            
            if not bottlenecks or bottlenecks[0]['total_score'] == 0:
                print("   ✅ No bottlenecks detected - all machines running smoothly!")
            else:
                for i, bottle in enumerate(bottlenecks, 1):
                    if bottle['total_score'] > 0:
                        print(f"\n   #{i}: {bottle['machine_name']}")
                        print(f"      Overall Score: {bottle['total_score']:.1f}/100")
                        
                        # Color code
                        if bottle['total_score'] > 66:
                            status = "🔴 CRITICAL BOTTLENECK"
                        elif bottle['total_score'] > 33:
                            status = "🟡 WATCH THIS MACHINE"
                        else:
                            status = "🟢 Healthy"
                        print(f"      Status: {status}")
                        
                        print(f"      Utilization: {bottle['utilization_percent']:.1f}%")
                        print(f"      Events: {bottle['event_count']}")
                        print(f"      Throughput: {bottle['actual_throughput']:.2f} units/hr")
                        
                        # Breakdown
                        print(f"      Score Breakdown:")
                        print(f"         Utilization: {bottle['utilization_score']:.1f}/30")
                        print(f"         Queue Time: {bottle['queue_score']:.1f}/25")
                        print(f"         Variance: {bottle['variance_score']:.1f}/20")
                        print(f"         Centrality: {bottle['centrality_score']:.1f}/15")
                        print(f"         Downstream: {bottle['downstream_score']:.1f}/10")
            
            # Critical path
            print("\n🛤️  Critical Path Analysis:")
            critical = analyzer.calculate_critical_path()
            
            if critical.get('path'):
                print(f"   Path: {' → '.join(critical['path'])}")
                print(f"   Total Duration: {critical['total_duration']:.1f} seconds")
            elif critical.get('is_dag') == False:
                print("   ⚠️  Graph contains cycles (rework loops)")
            else:
                print("   No clear path found")
            
            # Node-level metrics
            print("\n📊 Machine Metrics:")
            for node in graph.nodes:
                metrics = analyzer.calculate_node_metrics(node.id, time_window_hours=24)
                
                if metrics['event_count'] > 0:
                    print(f"\n   {metrics['machine_name']}:")
                    print(f"      Events: {metrics['event_count']}")
                    print(f"      Throughput: {metrics['throughput']:.2f} units/hr")
                    if metrics['utilization']:
                        print(f"      Utilization: {metrics['utilization']:.1f}%")
                    print(f"      Mean Time: {metrics['mean_duration']:.1f}s")
                    print(f"      Variance (CV): {metrics['cv']:.3f}")
        
        print("\n" + "=" * 70)
        print("✅ ANALYSIS COMPLETE!")
        print("=" * 70)


def test_individual_node():
    """Test metrics for a specific node"""
    with app.app_context():
        from models.graph import GraphNode
        
        nodes = GraphNode.query.all()
        if not nodes:
            print("No nodes found")
            return
        
        node = nodes[0]
        print(f"\nDetailed analysis for: {node.machine_name}")
        
        analyzer = ProcessGraphAnalyzer(node.graph_id, db.session)
        metrics = analyzer.calculate_node_metrics(node.id, time_window_hours=24)
        
        print(f"Metrics: {metrics}")


if __name__ == "__main__":
    try:
        test_bottleneck_detection()
        
        print("\n💡 TIP: To see more detailed analysis, try:")
        print("   python -c 'from test_analysis import test_individual_node; test_individual_node()'")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        print("\n🔧 Troubleshooting:")
        print("1. Make sure analysis/topology.py exists")
        print("2. Verify you have recorded some events in graph mode")
        print("3. Check that your graph has nodes and edges defined")
