import pytest
import networkx as nx
from core.map_loader import MapLoader


def test_enrich_graph():
    # Test için küçük bir dummy MultiDiGraph oluşturuyoruz
    G = nx.MultiDiGraph()
    G.graph["crs"] = "epsg:4326"
    G.add_node(1, y=41.0, x=29.0)
    G.add_node(2, y=41.1, x=29.1)
    
    # highway = "motorway" olan bir kenar ekle
    G.add_edge(1, 2, key=0, highway="motorway", length=100.0, maxspeed="50")
    
    loader = MapLoader(use_cache=False)
    # Zenginleştirme işlemini çağır
    G_enriched = loader._enrich_graph(G)
    
    # motorway yol rank'ı 5 olmalı
    edge_data = G_enriched.get_edge_data(1, 2, 0)
    assert edge_data["highway_rank"] == 5
    
    # speed_kph ve travel_time eklenmiş olmalı (OSMnx taklidi)
    assert "speed_kph" in edge_data or "travel_time" in edge_data


def test_get_graph_stats():
    G = nx.MultiDiGraph()
    G.add_node(1, y=41.0, x=29.0)
    G.add_node(2, y=41.1, x=29.1)
    G.add_edge(1, 2, key=0, length=2000.0)
    
    loader = MapLoader(use_cache=False)
    loader.graph = G
    
    stats = loader.get_graph_stats()
    assert stats["node_count"] == 2
    assert stats["edge_count"] == 1
    assert stats["total_length_km"] == 2.0
