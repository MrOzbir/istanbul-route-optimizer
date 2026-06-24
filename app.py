import logging
import sys
import os
import webbrowser
from pathlib import Path
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import networkx as nx
import numpy as np
import osmnx as ox

# Proje ana dizinini sys.path'e ekle
sys.path.append(str(Path(__file__).resolve().parent))

from core.map_loader import MapLoader
from core.graph_processor import GraphProcessor
from core.astar_engine import AStarEngine
from core.neural_heuristic import NeuralHeuristic
from core.ring_planner import RingPlanner
from core.traffic_manager import TrafficManager

# Loglama ayarları
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("flask_app")

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)
CORS(app)

# Landmark koordinatları
LANDMARKS = {
    "Taksim":       (41.0369,  28.9784),
    "Kadıköy":      (40.9906,  29.0264),
    "Beşiktaş":     (41.0430,  29.0058),
    "Üsküdar":      (41.0267,  29.0184),
    "Fatih":        (41.0193,  28.9397),
    "Bakırköy":     (40.9819,  28.8772),
    "Şişli":        (41.0602,  28.9877),
    "Ataşehir":     (40.9923,  29.1244),
    "Sarıyer":      (41.1657,  29.0518),
    "Bağcılar":     (41.0390,  28.8560),
}

# Sunucu başlangıcında graf ve planlayıcıların bir defalık yüklenmesi
logger.info("OSM Grafı yükleniyor ve hiyerarşi oluşturuluyor...")
try:
    loader = MapLoader()
    graph = loader.load_from_disk()
    processor = GraphProcessor(graph)
    hierarchy = processor.build_hierarchy(save=False)
    h_cache = processor.build_heuristic_cache(save=False)

    # 0. Trafik Yönetim Katmanı
    traffic_manager = TrafficManager(graph)

    # 1. Neural Heuristic Planlayıcı (ONNX)
    nh_neural = NeuralHeuristic(graph=graph, h_cache=h_cache, processor=processor)
    engine_neural = AStarEngine(hierarchy, h_cache, processor, heuristic_fn=nh_neural, traffic_manager=traffic_manager)
    planner_neural = RingPlanner(engine_neural, nh_neural)

    # 2. Haversine Planlayıcı (Klasik A*)
    from core.graph_processor import haversine_meters
    class FallbackNH:
        def predict_batch(self, pairs):
            costs = []
            for u, v in pairs:
                du = graph.nodes[u]
                dv = graph.nodes[v]
                d = haversine_meters(du["y"], du["x"], dv["y"], dv["x"])
                costs.append(d / 22.22)
            return np.array(costs, dtype="float32")

    nh_fallback = FallbackNH()
    engine_fallback = AStarEngine(hierarchy, h_cache, processor, heuristic_fn=None, traffic_manager=traffic_manager)
    planner_fallback = RingPlanner(engine_fallback, nh_fallback)
    
    logger.info("OSM Grafı, Trafik Yöneticisi ve Rota Planlayıcılar başarıyla hazırlandı.")
except Exception as e:
    logger.error("Başlangıç yüklemesinde hata oluştu: %s", str(e), exc_info=True)
    sys.exit(1)


@app.route("/")
def index():
    """Ana arayüz sayfasını döndürür."""
    return render_template("index.html")


@app.route("/api/landmarks", methods=["GET"])
def get_landmarks():
    """Hazır landmark listesini döner."""
    return jsonify({
        "success": True,
        "landmarks": [
            {"name": name, "lat": coords[0], "lng": coords[1]}
            for name, coords in LANDMARKS.items()
        ]
    })


@app.route("/api/traffic", methods=["GET"])
def get_traffic():
    """Mevcut trafik yoğunluk verisini ve kazaları döner."""
    try:
        traffic_manager.update_traffic()
        segments = traffic_manager.get_traffic_overlay_data()
        incidents = traffic_manager.get_active_incidents_coords()
        return jsonify({
            "success": True,
            "segments": segments,
            "incidents": incidents
        })
    except Exception as e:
        logger.error("Trafik verisi alınırken hata oluştu: %s", str(e), exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Trafik verisi alınamadı: {str(e)}"
        }), 500


def solve_open_tsp(cost_matrix, start_idx, end_idx):
    """
    Sabit başlangıç ve bitiş noktaları için Açık TSP (Open Path TSP) problemini çözer.
    Eğer intermediate sayısı <= 6 ise brute-force ile kesin optimal,
    aksi halde Nearest Neighbor + 2-opt local search kullanır.
    """
    n = len(cost_matrix)
    intermediates = [i for i in range(n) if i != start_idx and i != end_idx]
    
    # 1. Küçük boyutlarda Brute-Force (Tam Çözüm)
    if len(intermediates) <= 6:
        import itertools
        best_order = None
        best_cost = float('inf')
        for p in itertools.permutations(intermediates):
            path = [start_idx] + list(p) + [end_idx]
            cost = sum(cost_matrix[path[i], path[i+1]] for i in range(n-1))
            if cost < best_cost:
                best_cost = cost
                best_order = path
        return best_order, best_cost, ["Brute-force ile kesin en kısa açık rota bulundu."]
        
    # 2. Nearest Neighbor (Başlangıç Rota)
    unvisited = set(intermediates)
    path = [start_idx]
    current = start_idx
    while unvisited:
        best_next = -1
        best_cost = float('inf')
        for nxt in unvisited:
            c = cost_matrix[current, nxt]
            if c < best_cost:
                best_cost = c
                best_next = nxt
        if best_next == -1:
            best_next = unvisited.pop()
            unvisited.add(best_next)
            
        path.append(best_next)
        unvisited.remove(best_next)
        current = best_next
        
    path.append(end_idx)
    
    def path_cost(p):
        return sum(cost_matrix[p[i], p[i+1]] for i in range(n-1))
        
    best_cost = path_cost(path)
    best_path = path[:]
    log = [f"Açık NN başlangıç maliyeti: {best_cost:.1f}"]
    
    # 3. 2-opt Local Search (İyileştirme)
    improved = True
    iteration = 0
    while improved and iteration < 100:
        improved = False
        iteration += 1
        for i in range(1, n - 2):
            for k in range(i + 1, n - 1):
                new_path = best_path[:i] + best_path[i:k+1][::-1] + best_path[k+1:]
                new_cost = path_cost(new_path)
                if new_cost < best_cost - 1e-5:
                    best_path = new_path
                    best_cost = new_cost
                    improved = True
                    log.append(f"  İter {iteration:3d} | swap ({i},{k}) | maliyet: {best_cost:.2f}")
                    break
            if improved:
                break
                
    log.append(f"Açık 2-opt bitti. {iteration} iterasyon | final: {best_cost:.2f}")
    return best_path, best_cost, log


@app.route("/api/route", methods=["POST"])
def calculate_route():
    """Uğranacak koordinatları alıp ring rotasını optimize eder."""
    try:
        data = request.json or {}
        waypoints = data.get("waypoints", [])
        use_haversine = data.get("use_haversine", False)
        is_loop = data.get("is_loop", True)
        start_index = data.get("start_index", 0)
        end_index = data.get("end_index", len(waypoints) - 1)
        use_traffic = data.get("use_traffic", False)

        if len(waypoints) < 2:
            return jsonify({
                "success": False,
                "error": "En az 2 adet koordinat girilmelidir."
            }), 400

        n_wps = len(waypoints)
        start_index = max(0, min(int(start_index), n_wps - 1))
        end_index = max(0, min(int(end_index), n_wps - 1))

        logger.info("Rota hesaplama isteği alındı. Nokta sayısı: %d, Mod: %s, Sezgisel: %s", 
                    len(waypoints), "Çembersel" if is_loop else "Açık Rota", "Haversine" if use_haversine else "Neural ONNX")

        # Koordinatları OSM düğümlerine (node) eşleme
        waypoint_nodes = []
        waypoint_info = []
        
        for idx, wp in enumerate(waypoints):
            lat = float(wp["lat"])
            lon = float(wp["lng"])
            name = wp.get("name", f"Nokta {idx + 1}")
            
            # En yakın OSM düğümünü bulma
            node = ox.distance.nearest_nodes(hierarchy.full, X=lon, Y=lat)
            waypoint_nodes.append(node)
            
            node_lat = graph.nodes[node]["y"]
            node_lon = graph.nodes[node]["x"]
            
            waypoint_info.append({
                "name": name,
                "node_id": int(node),
                "lat": node_lat,
                "lng": node_lon,
                "input_lat": lat,
                "input_lng": lon
            })
            logger.info("Waypoint Eşleşmesi: '%s' (%f, %f) -> Düğüm %d (%f, %f)", 
                        name, lat, lon, node, node_lat, node_lon)

        # Planlayıcı seçimi
        planner = planner_fallback if use_haversine else planner_neural
        
        if is_loop:
            # ── 1. Çembersel Rota Çözümü (Ring Route) ──
            # Seçilen başlangıç noktasını dizinin ilk sırasına kaydırıyoruz (rotate)
            reordered_nodes = waypoint_nodes[start_index:] + waypoint_nodes[:start_index]
            ring = planner.plan(reordered_nodes, use_traffic=use_traffic)

            # Rota segment koordinatlarını çıkarma
            segments_data = []
            for idx, segment in enumerate(ring.segments):
                if segment.found and segment.path:
                    path_coords = []
                    for node in segment.path:
                        if node in graph.nodes:
                            path_coords.append([graph.nodes[node]["y"], graph.nodes[node]["x"]])
                    
                    segments_data.append({
                        "segment_index": idx,
                        "found": True,
                        "path_coords": path_coords,
                        "total_length_m": float(segment.total_length_m),
                        "total_time_s": float(segment.total_time_s),
                        "nodes_explored": int(segment.nodes_explored),
                        "elapsed_ms": float(segment.elapsed_ms)
                    })
                else:
                    segments_data.append({
                        "segment_index": idx,
                        "found": False,
                        "path_coords": []
                    })

            # Sıralanmış waypointleri eşleme
            optimized_waypoints = []
            for node in ring.waypoints:
                if node in graph.nodes:
                    lat = graph.nodes[node]["y"]
                    lon = graph.nodes[node]["x"]
                    name = f"{lat:.5f}, {lon:.5f}"
                    for info in waypoint_info:
                        if info["node_id"] == node:
                            name = info["name"]
                            break
                    optimized_waypoints.append({
                        "name": name,
                        "node_id": int(node),
                        "lat": lat,
                        "lng": lon
                    })
            
            total_len = ring.total_length_m
            total_t = ring.total_time_s
            opt_log = ring.optimization_log
            elapsed = ring.elapsed_ms

        else:
            # ── 2. Açık Rota Çözümü (Fixed Start & End Path) ──
            import time
            t0 = time.perf_counter()

            # Maliyet matrisini hesapla (neural batch inference)
            cost_matrix = planner._build_cost_matrix(waypoint_nodes)

            # Açık TSP optimizasyonu
            best_path, best_cost, opt_log = solve_open_tsp(cost_matrix, start_index, end_index)

            # Sıralı düğümler
            ordered_nodes = [waypoint_nodes[i] for i in best_path]

            # Rota segment koordinatlarını çıkarma (Sequential - n-1 segment)
            segments_data = []
            total_len = 0.0
            total_t = 0.0

            for idx in range(len(ordered_nodes) - 1):
                src = ordered_nodes[idx]
                tgt = ordered_nodes[idx + 1]

                segment = planner.engine.find_path(src, tgt, use_traffic=use_traffic)

                if segment.found and segment.path:
                    path_coords = []
                    for node in segment.path:
                        if node in graph.nodes:
                            path_coords.append([graph.nodes[node]["y"], graph.nodes[node]["x"]])

                    segments_data.append({
                        "segment_index": idx,
                        "found": True,
                        "path_coords": path_coords,
                        "total_length_m": float(segment.total_length_m),
                        "total_time_s": float(segment.total_time_s),
                        "nodes_explored": int(segment.nodes_explored),
                        "elapsed_ms": float(segment.elapsed_ms)
                    })
                    total_len += segment.total_length_m
                    total_t += segment.total_time_s
                else:
                    segments_data.append({
                        "segment_index": idx,
                        "found": False,
                        "path_coords": []
                    })

            # Sıralanmış waypointleri eşleme
            optimized_waypoints = []
            for node in ordered_nodes:
                if node in graph.nodes:
                    lat = graph.nodes[node]["y"]
                    lon = graph.nodes[node]["x"]
                    name = f"{lat:.5f}, {lon:.5f}"
                    for info in waypoint_info:
                        if info["node_id"] == node:
                            name = info["name"]
                            break
                    optimized_waypoints.append({
                        "name": name,
                        "node_id": int(node),
                        "lat": lat,
                        "lng": lon
                    })

            elapsed = (time.perf_counter() - t0) * 1000

        # Başarılı yanıt
        return jsonify({
            "success": True,
            "total_length_km": float(total_len / 1000.0),
            "total_time_min": float(total_t / 60.0),
            "segments": segments_data,
            "waypoints_ordered": optimized_waypoints,
            "optimization_log": opt_log,
            "elapsed_ms": float(elapsed)
        })

    except Exception as e:
        logger.error("Rota hesaplanırken hata oluştu: %s", str(e), exc_info=True)
        return jsonify({
            "success": False,
            "error": f"Rota hesaplanamadı: {str(e)}"
        }), 500


def run_web_server(port=5001, debug=False):
    """Flask web sunucusunu çalıştırır ve tarayıcıda otomatik açar."""
    # Sunucu başladıktan sonra tarayıcıyı aç
    url = f"http://127.0.0.1:{port}"
    logger.info("Tarayıcı açılıyor: %s", url)
    
    # Fork/Thread ile açmak yerine port kilitlenmesini önlemek için
    # flask çalıştırmadan önce tarayıcı açma komutunu gecikmesiz tetikleyebiliriz
    try:
        webbrowser.open(url)
    except Exception as e:
        logger.warning("Tarayıcı otomatik açılamadı: %s", str(e))
        
    app.run(host="127.0.0.1", port=port, debug=debug)


if __name__ == "__main__":
    run_web_server()
