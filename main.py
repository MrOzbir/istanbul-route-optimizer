"""
main.py
=======
İstanbul Yol Öneri Projesi — Ana Giriş Noktası

Komut satırı argümanları:
    --mode fetch        : Harita verisini OSMnx'ten çek
    --mode train        : Modeli eğit
    --mode export       : ONNX export + benchmark
    --mode route        : Rota hesapla ve haritaya render et
    --mode all          : Tüm adımları sırayla çalıştır

Örnek kullanımlar:
    python main.py --mode fetch
    python main.py --mode train --epochs 80 --samples 600
    python main.py --mode export --quantize
    python main.py --mode route --waypoints "Taksim,Kadıköy,Beşiktaş,Üsküdar"
    python main.py --mode all
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/run.log", mode="a"),
    ],
)
logger = logging.getLogger("main")

# Önceden tanımlı İstanbul landmark koordinatları
LANDMARKS: dict[str, tuple[float, float]] = {
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="İstanbul Neural-Guided A* Rota Planlayıcı"
    )
    parser.add_argument(
        "--mode",
        choices=["fetch", "train", "export", "route", "server", "all"],
        default="route",
        help="Çalışma modu",
    )
    parser.add_argument(
        "--waypoints",
        type=str,
        default="Taksim,Kadıköy,Beşiktaş,Üsküdar",
        help="Virgülle ayrılmış waypoint isimleri (LANDMARKS anahtarları)",
    )
    parser.add_argument("--epochs",   type=int,  default=100)
    parser.add_argument("--samples",  type=int,  default=800)
    parser.add_argument("--quantize", action="store_true")
    parser.add_argument("--haversine", action="store_true",
                        help="Neural heuristic yerine Haversine kullan")
    parser.add_argument("--port",      type=int,  default=5001,
                        help="Arayüz sunucusu port numarası")
    return parser.parse_args()


def run_fetch() -> None:
    """Görev 1: Harita verisi çek ve kaydet."""
    from core.map_loader import MapLoader
    loader = MapLoader()
    graph  = loader.run()
    stats  = loader.get_graph_stats()
    logger.info("Graf istatistikleri: %s", stats)


def run_train(epochs: int, samples_per_band: int) -> None:
    """Görev 4: Veri seti oluştur + model eğit."""
    import pickle
    from core.map_loader import MapLoader
    from core.graph_processor import GraphProcessor
    from core.astar_engine import AStarEngine
    from training.model_arch import HeuristicNet, FeatureExtractor
    from training.dataset_builder import DatasetBuilder
    from training.trainer import Trainer

    loader    = MapLoader()
    graph     = loader.load_from_disk()
    processor = GraphProcessor(graph)
    hierarchy = processor.build_hierarchy(save=True)
    h_cache   = processor.build_heuristic_cache(save=True)
    engine    = AStarEngine(hierarchy, h_cache, processor)
    extractor = FeatureExtractor(graph)

    ds_path = Path("data/processed/training_dataset.pkl")
    if ds_path.exists():
        with open(ds_path, "rb") as f:
            dataset = pickle.load(f)
        logger.info("Mevcut veri seti yüklendi: %d örnek", len(dataset.labels))
    else:
        builder = DatasetBuilder(
            graph, engine, extractor, n_per_band=samples_per_band
        )
        dataset = builder.build(save=True)

    model   = HeuristicNet()
    trainer = Trainer(model, dataset, epochs=epochs)
    history = trainer.train()
    logger.info(
        "Eğitim bitti. Son val loss: %.4f", history["val_loss"][-1]
    )


def run_export(quantize: bool) -> None:
    """Görev 5: ONNX export ve benchmark."""
    from training.export_onnx import ONNXExporter
    exporter = ONNXExporter(quantize=quantize)
    exporter.export()
    exporter.benchmark(n_runs=5_000)


def run_route(waypoint_names: list[str], use_haversine: bool) -> None:
    """Görev 6: Ring rota hesapla ve haritaya render et."""
    import osmnx as ox
    from core.map_loader import MapLoader
    from core.graph_processor import GraphProcessor
    from core.astar_engine import AStarEngine
    from core.neural_heuristic import NeuralHeuristic
    from core.ring_planner import RingPlanner
    from visualization.map_renderer import MapRenderer

    # ── Altyapı ─────────────────────────────
    loader    = MapLoader()
    graph     = loader.load_from_disk()
    processor = GraphProcessor(graph)
    hierarchy = processor.build_hierarchy(save=False)
    h_cache   = processor.build_heuristic_cache(save=False)

    # ── Sezgisel Seçimi ─────────────────────
    if use_haversine:
        logger.info("Sezgisel: Haversine (klasik A*)")
        heuristic_fn = None
    else:
        logger.info("Sezgisel: Neural Heuristic (ONNX)")
        nh = NeuralHeuristic(
            graph=graph, h_cache=h_cache, processor=processor
        )
        heuristic_fn = nh

    engine = AStarEngine(
        hierarchy, h_cache, processor, heuristic_fn=heuristic_fn
    )

    # ── Waypoint Çözümleme ───────────────────
    waypoint_nodes = []
    for name in waypoint_names:
        name = name.strip()
        if name not in LANDMARKS:
            logger.warning("Bilinmeyen waypoint: '%s'. Atlanıyor.", name)
            continue
        lat, lon = LANDMARKS[name]
        node = ox.distance.nearest_nodes(hierarchy.full, X=lon, Y=lat)
        waypoint_nodes.append(node)
        logger.info("Waypoint: %s → OSM düğüm %d", name, node)

    if len(waypoint_nodes) < 2:
        logger.error("En az 2 geçerli waypoint gereklidir.")
        return

    # ── Ring Planlama ────────────────────────
    planner = RingPlanner(engine, nh if not use_haversine else None)

    # NeuralHeuristic yoksa maliyet matrisini Haversine'le oluştur
    if use_haversine:
        # Basit fallback: Haversine maliyet matrisi
        from core.graph_processor import haversine_meters
        n = len(waypoint_nodes)

        class _FallbackNH:
            def predict_batch(self, pairs):
                import numpy as np
                costs = []
                for u, v in pairs:
                    du = graph.nodes[u]
                    dv = graph.nodes[v]
                    d  = haversine_meters(du["y"], du["x"], dv["y"], dv["x"])
                    costs.append(d / 22.22)
                return np.array(costs, dtype="float32")

        planner.nh = _FallbackNH()

    ring = planner.plan(waypoint_nodes)

    # ── Görselleştirme ───────────────────────
    renderer = MapRenderer(graph)
    out_path = Path("output/istanbul_ring.html")
    renderer.render_ring(ring, output_path=out_path, show_heatmap=True)

    # ── Özet ────────────────────────────────
    print("\n" + "═" * 52)
    print("  İSTANBUL RING ROTA PLANLAYICI — SONUÇ")
    print("═" * 52)
    print(f"  Waypoint'ler   : {' → '.join(waypoint_names)} → başa dön")
    print(f"  Toplam mesafe  : {ring.total_length_m/1000:.2f} km")
    print(f"  Tahmini süre   : {ring.total_time_s/60:.0f} dakika")
    print(f"  Segment sayısı : {len(ring.segments)}")
    print(f"  Planlama süresi: {ring.elapsed_ms:.0f} ms")
    print(f"  Harita         : {out_path.resolve()}")
    print("═" * 52 + "\n")

    for msg in ring.optimization_log:
        logger.info("[2-opt] %s", msg)

    if not use_haversine:
        print("Neural Heuristic İstatistikleri:")
        for k, v in nh.get_stats().items():
            print(f"  {k:<22}: {v}")


def run_server(port: int) -> None:
    """Görev 7: Rota öneri web arayüzünü sun."""
    from app import run_web_server
    logger.info("Web arayüz sunucusu başlatılıyor...")
    run_web_server(port=port)


def main() -> None:
    Path("logs").mkdir(exist_ok=True)
    Path("output").mkdir(exist_ok=True)

    args = parse_args()
    wp_names = [w.strip() for w in args.waypoints.split(",")]

    mode_map = {
        "fetch":  lambda: run_fetch(),
        "train":  lambda: run_train(args.epochs, args.samples),
        "export": lambda: run_export(args.quantize),
        "route":  lambda: run_route(wp_names, args.haversine),
        "server": lambda: run_server(args.port),
        "all": lambda: (
            run_fetch(),
            run_train(args.epochs, args.samples),
            run_export(args.quantize),
            run_route(wp_names, args.haversine),
        ),
    }

    mode_map[args.mode]()


if __name__ == "__main__":
    main()