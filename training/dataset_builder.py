"""
training/dataset_builder.py
============================
İstanbul Yol Öneri Projesi — Eğitim Verisi Üretici

Sorumluluk:
    A* algoritmasını gerçek graf üzerinde koşturarak "öğretmen sinyali"
    üretir. Her (source, target) çifti için:
      - Gerçek A* maliyeti → etiket (label)
      - FeatureExtractor çıktısı → özellik vektörü (feature)

    Bu yaklaşım "imitation learning" veya "learning to search" olarak
    bilinir: model A*'ın bulduğu gerçek maliyeti taklit etmeyi öğrenir.

Örnekleme Stratejisi:
    Rastgele düğüm çifti seçmek yerine mesafe bantlarına göre
    dengeli örnekleme yapılır:
        Bant 1: 0–5 km    (kısa)   → arterial layer örnekleri
        Bant 2: 5–20 km   (orta)   → mixed
        Bant 3: 20–80 km  (uzun)   → express layer örnekleri
    Her bantten eşit sayıda örnek alınır → model tüm mesafe
    aralıklarında dengeli performans gösterir.
"""

import logging
import pickle
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import networkx as nx

from core.map_loader import MapLoader
from core.graph_processor import GraphProcessor, haversine_meters
from core.astar_engine import AStarEngine, COST_TRAVEL_TIME
from training.model_arch import FeatureExtractor

logger = logging.getLogger(__name__)

DATA_PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"

# Mesafe bantları (metre)
DISTANCE_BANDS = [
    (0,       5_000),
    (5_000,  20_000),
    (20_000, 80_000),
]


@dataclass
class TrainingDataset:
    """
    Eğitim veri seti paketi.

    Attributes
    ----------
    features : np.ndarray  shape (N, 8)
    labels   : np.ndarray  shape (N,)    gerçek A* maliyeti (saniye)
    pairs    : list[(int,int)]           (source, target) düğüm çiftleri
    meta     : dict                      örnekleme istatistikleri
    """
    features: np.ndarray = field(default_factory=lambda: np.empty((0, 8)))
    labels:   np.ndarray = field(default_factory=lambda: np.empty(0))
    pairs:    list       = field(default_factory=list)
    meta:     dict       = field(default_factory=dict)


class DatasetBuilder:
    """
    A* koşturarak eğitim verisi üretir.

    Parameters
    ----------
    graph      : nx.MultiDiGraph
    engine     : AStarEngine
    extractor  : FeatureExtractor
    n_per_band : int    Her mesafe bandından kaç örnek üretilecek
    seed       : int    Tekrarlanabilirlik için rastgele tohum
    """

    def __init__(
        self,
        graph:      nx.MultiDiGraph,
        engine:     AStarEngine,
        extractor:  FeatureExtractor,
        n_per_band: int = 1000,
        seed:       int = 42,
    ) -> None:
        self.graph      = graph
        self.engine     = engine
        self.extractor  = extractor
        self.n_per_band = n_per_band
        random.seed(seed)
        np.random.seed(seed)

        self._all_nodes = list(engine.hierarchy.full.nodes())
        self._coords    = {
            n: (d["y"], d["x"])
            for n, d in graph.nodes(data=True)
        }
        logger.info(
            "DatasetBuilder hazır. %d düğüm | %d bant | band başına %d örnek",
            len(self._all_nodes), len(DISTANCE_BANDS), n_per_band,
        )

    def build(self, save: bool = True) -> TrainingDataset:
        """
        Tüm bantlar için eğitim verisi üretir.

        Returns
        -------
        TrainingDataset
        """
        t0 = time.perf_counter()
        all_features, all_labels, all_pairs = [], [], []
        meta = {"band_stats": [], "total_failed": 0}

        for band_min, band_max in DISTANCE_BANDS:
            logger.info(
                "Bant işleniyor: %d–%d km",
                band_min // 1000, band_max // 1000
            )
            features, labels, pairs, stats = self._sample_band(
                band_min, band_max
            )
            all_features.append(features)
            all_labels.append(labels)
            all_pairs.extend(pairs)
            meta["band_stats"].append(stats)
            meta["total_failed"] += stats["failed"]

        dataset = TrainingDataset(
            features=np.vstack(all_features),
            labels=np.concatenate(all_labels),
            pairs=all_pairs,
            meta=meta,
        )

        elapsed = time.perf_counter() - t0
        logger.info(
            "Veri seti tamamlandı. %d örnek | %.1f saniye | %d başarısız",
            len(dataset.labels), elapsed, meta["total_failed"],
        )

        if save:
            path = DATA_PROCESSED / "training_dataset.pkl"
            with open(path, "wb") as f:
                pickle.dump(dataset, f, protocol=pickle.HIGHEST_PROTOCOL)
            logger.info("Veri seti kaydedildi: %s", path)

        return dataset

    def _sample_band(
        self,
        band_min: float,
        band_max: float,
    ) -> tuple[np.ndarray, np.ndarray, list, dict]:
        """
        Belirtilen mesafe bandından n_per_band çift örnekler,
        A* koşturur ve etiketleri toplar.

        Ret koşulları:
            - A* rota bulamazsa (bağlantısız düğümler)
            - Maliyet 0 veya inf ise (dejenere durum)

        Returns
        -------
        features, labels, pairs, stats_dict
        """
        features_list, labels_list, pairs_list = [], [], []
        attempted = 0
        failed    = 0

        while len(labels_list) < self.n_per_band:
            attempted += 1

            # Mesafe bandına uyan rastgele çift seç
            source = random.choice(self._all_nodes)
            target = random.choice(self._all_nodes)
            if source == target:
                continue

            lat1, lon1 = self._coords[source]
            lat2, lon2 = self._coords[target]
            dist = haversine_meters(lat1, lon1, lat2, lon2)

            if not (band_min <= dist < band_max):
                continue

            # A* koştur
            result = self.engine.find_path(source, target)

            if not result.found or result.total_cost <= 0 or \
               result.total_cost == float("inf"):
                failed += 1
                continue

            # Özellik çıkar
            feat = self.extractor.extract(source, target)
            features_list.append(feat)
            labels_list.append(result.total_cost)
            pairs_list.append((source, target))

        stats = {
            "band":     f"{band_min//1000}–{band_max//1000}km",
            "sampled":  len(labels_list),
            "attempted":attempted,
            "failed":   failed,
            "success_rate": f"{len(labels_list)/max(attempted,1)*100:.1f}%",
        }
        logger.info("  %s", stats)

        return (
            np.array(features_list, dtype=np.float32),
            np.array(labels_list, dtype=np.float32),
            pairs_list,
            stats,
        )