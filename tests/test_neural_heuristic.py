import pytest
import networkx as nx
import numpy as np
from core.graph_processor import GraphProcessor, HeuristicCache
from core.neural_heuristic import NeuralHeuristic


def test_neural_heuristic_fallback_and_caching():
    # Basit bir test grafiği
    G = nx.MultiDiGraph()
    G.add_node(1, y=41.00, x=29.00)
    G.add_node(2, y=41.05, x=29.05)
    G.add_edge(1, 2, key=0, length=5000.0, travel_time=200.0, highway="motorway")
    
    processor = GraphProcessor(G)
    h_cache = HeuristicCache(
        node_coords={
            1: (41.00, 29.00),
            2: (41.05, 29.05)
        }
    )
    
    from pathlib import Path
    # ONNX dosyası yokken başlatacağız -> model_loaded = False olmalı ve fallback çalışmalı
    nh = NeuralHeuristic(
        graph=G,
        h_cache=h_cache,
        processor=processor,
        onnx_path=Path("non_existent.onnx")
    )
    
    assert nh.model_loaded is False
    
    # 1. Tahmin (Cache Miss)
    cost1 = nh(1, 2)
    assert cost1 > 0.0
    stats1 = nh.get_stats()
    assert stats1["cache_misses"] == 1
    assert stats1["cache_hits"] == 0
    assert stats1["cache_size"] == 1
    
    # 2. Tahmin (Cache Hit)
    cost2 = nh(1, 2)
    assert cost2 == cost1
    stats2 = nh.get_stats()
    assert stats2["cache_misses"] == 1
    assert stats2["cache_hits"] == 1
    assert stats2["cache_size"] == 1
    
    # Toplu tahmin (predict_batch) testi
    costs_batch = nh.predict_batch([(1, 2), (2, 1)])
    assert len(costs_batch) == 2
    assert costs_batch[0] > 0.0
    assert isinstance(costs_batch, np.ndarray)
