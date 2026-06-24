import pytest
import networkx as nx
from core.graph_processor import GraphProcessor, HierarchicalGraph, HeuristicCache
from core.astar_engine import AStarEngine, COST_TRAVEL_TIME
from core.traffic_manager import TrafficManager


def test_traffic_manager_multipliers():
    # Basit bir ardışık grafik kuruyoruz: 1 -> 2 -> 3
    G = nx.MultiDiGraph()
    G.add_node(1, y=41.00, x=29.00)
    G.add_node(2, y=41.01, x=29.01)
    G.add_node(3, y=41.02, x=29.02)
    
    # Kenarlar
    G.add_edge(1, 2, key=0, length=1000.0, travel_time=50.0, highway="motorway")
    G.add_edge(2, 3, key=0, length=1000.0, travel_time=50.0, highway="motorway")
    
    # TrafficManager oluştur
    tm = TrafficManager(G)
    tm.update_traffic()
    
    # Çarpanların oluşturulduğunu kontrol et
    m1 = tm.get_edge_multiplier(1, 2)
    m2 = tm.get_edge_multiplier(2, 3)
    
    assert m1 >= 1.0
    assert m2 >= 1.0
    
    # AStarEngine entegrasyon testi
    processor = GraphProcessor(G)
    hierarchy = HierarchicalGraph(
        express=G,
        arterial=G,
        full=G,
        express_reversed=G.reverse(copy=True),
        arterial_reversed=G.reverse(copy=True),
        layer_stats={}
    )
    h_cache = HeuristicCache(
        node_coords={1: (41.00, 29.00), 2: (41.01, 29.01), 3: (41.02, 29.02)}
    )
    
    # Trafiksiz arama
    engine_no_traffic = AStarEngine(
        hierarchy=hierarchy,
        h_cache=h_cache,
        processor=processor,
        cost_key=COST_TRAVEL_TIME,
        traffic_manager=None
    )
    res_no_traffic = engine_no_traffic.find_path(1, 3, force_layer="express", use_traffic=False)
    
    # Trafikli arama
    engine_traffic = AStarEngine(
        hierarchy=hierarchy,
        h_cache=h_cache,
        processor=processor,
        cost_key=COST_TRAVEL_TIME,
        traffic_manager=tm
    )
    res_traffic = engine_traffic.find_path(1, 3, force_layer="express", use_traffic=True)
    
    assert res_no_traffic.found is True
    assert res_traffic.found is True
    assert res_no_traffic.total_time_s == 100.0  # 50 + 50
    assert res_traffic.total_time_s == 50.0 * m1 + 50.0 * m2
