import pytest
import networkx as nx
from core.graph_processor import GraphProcessor, HierarchicalGraph, HeuristicCache
from core.astar_engine import AStarEngine, PathResult, COST_TRAVEL_TIME


def test_astar_find_path():
    # Basit bir ardışık grafik kuruyoruz: 1 -> 2 -> 3
    G = nx.MultiDiGraph()
    G.add_node(1, y=41.00, x=29.00)
    G.add_node(2, y=41.01, x=29.01)
    G.add_node(3, y=41.02, x=29.02)
    
    # Kenar özellikleri (travel_time ve length)
    G.add_edge(1, 2, key=0, length=1000.0, travel_time=45.0, highway="motorway")
    G.add_edge(2, 3, key=0, length=1000.0, travel_time=45.0, highway="motorway")
    
    # processor ve caches
    processor = GraphProcessor(G)
    
    # Basit test hiyerarşisi (tüm katmanları G ile besliyoruz)
    hierarchy = HierarchicalGraph(
        express=G,
        arterial=G,
        full=G,
        express_reversed=G.reverse(copy=True),
        arterial_reversed=G.reverse(copy=True),
        layer_stats={}
    )
    
    h_cache = HeuristicCache(
        node_coords={
            1: (41.00, 29.00),
            2: (41.01, 29.01),
            3: (41.02, 29.02)
        }
    )
    
    engine = AStarEngine(
        hierarchy=hierarchy,
        h_cache=h_cache,
        processor=processor,
        cost_key=COST_TRAVEL_TIME
    )
    
    # A* araması koştur
    result = engine.find_path(1, 3, force_layer="express")
    
    assert result.found is True
    assert result.path == [1, 2, 3]
    assert result.total_cost == 90.0  # 45 + 45
    assert result.total_length_m == 2000.0
    assert result.total_time_s == 90.0
