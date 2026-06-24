"""
core/ring_planner.py
====================
İstanbul Yol Öneri Projesi — Çembersel Rota Planlayıcı

Sorumluluk:
    Kullanıcının belirlediği N waypoint üzerinden geçen ve başlangıç
    noktasına dönen kapalı (ring/loop) rotayı optimize eder.

Problem Tanımı:
    Bu problem Gezgin Satıcı Problemi'nin (TSP) özel bir halidir.
    Tam TSP NP-hard olduğundan büyük N için iki aşamalı yaklaşım uygulanır:

    Aşama 1 — Nearest Neighbor Heuristic (Greedy başlangıç):
        En yakın ziyaret edilmemiş noktaya git.
        Zaman: O(N²) | Kalite: optimal'den %20-25 uzak

    Aşama 2 — 2-opt Local Search (İyileştirme):
        Rota üzerinde çapraz geçen (crossing) kenar çiftlerini bul,
        bu çifti tersine çevirerek toplam maliyeti düşür.
        Her başarılı swap yeni rotayı kullanarak tekrar tarar.
        Zaman: O(N² × iter) | Kalite: genellikle optimal'e %5 içinde

    Neden tam TSP değil?
        N ≤ 15 waypoint için 2-opt yeterince iyi sonuç verir.
        N > 15 için Or-opt veya Lin-Kernighan önerilir (gelecek geliştirme).

Maliyet Matrisi:
    N×N matris, her waypoint çifti arasındaki A* maliyetini saklar.
    NeuralHeuristic.predict_batch() ile toplu hesaplanır → tek ONNX çağrısı.
    A* tam rota hesaplaması ise sadece final sıralama için yapılır.

Kullanım:
    from core.ring_planner import RingPlanner
    planner = RingPlanner(engine, neural_heuristic)
    ring = planner.plan(waypoint_nodes)
"""

import itertools
import logging
import math
import time
from dataclasses import dataclass, field

import numpy as np

from core.astar_engine import AStarEngine, PathResult
from core.neural_heuristic import NeuralHeuristic

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Veri Sınıfları
# ─────────────────────────────────────────────

@dataclass
class RingRoute:
    """
    Çembersel rota sonuç paketi.

    Attributes
    ----------
    waypoints       : list[int]   Kullanıcı tanımlı waypoint sırası (optimize edilmiş)
    segments        : list[PathResult]  Her waypoint çifti arası A* rotası
    full_path       : list[int]   Tüm düğümleri içeren birleşik rota
    total_length_m  : float       Toplam rota uzunluğu (metre)
    total_time_s    : float       Tahmini toplam süre (saniye)
    cost_matrix     : np.ndarray  N×N waypoint maliyet matrisi
    optimization_log: list[str]   2-opt iyileştirme adımları
    elapsed_ms      : float       Toplam planlama süresi
    """
    waypoints:        list            = field(default_factory=list)
    segments:         list            = field(default_factory=list)
    full_path:        list            = field(default_factory=list)
    total_length_m:   float           = 0.0
    total_time_s:     float           = 0.0
    cost_matrix:      np.ndarray      = field(default_factory=lambda: np.empty((0,0)))
    optimization_log: list            = field(default_factory=list)
    elapsed_ms:       float           = 0.0


# ─────────────────────────────────────────────
#  Ana Sınıf
# ─────────────────────────────────────────────

class RingPlanner:
    """
    Waypoint listesinden optimize edilmiş çembersel rota üretir.

    Parameters
    ----------
    engine          : AStarEngine
        Segment bazlı rota hesaplama için.
    neural_heuristic: NeuralHeuristic
        Maliyet matrisi toplu hesaplama için.
    max_2opt_iter   : int
        2-opt maksimum iterasyon sayısı (büyük N için limit).
    """

    def __init__(
        self,
        engine:           AStarEngine,
        neural_heuristic: NeuralHeuristic,
        max_2opt_iter:    int = 100,
    ) -> None:
        self.engine           = engine
        self.nh               = neural_heuristic
        self.max_2opt_iter    = max_2opt_iter

        logger.info(
            "RingPlanner hazır. Max 2-opt iterasyon: %d", max_2opt_iter
        )

    # ──────────────────────────────────────────
    #  Ana Akış
    # ──────────────────────────────────────────

    def plan(self, waypoints: list[int], use_traffic: bool = False) -> RingRoute:
        """
        Waypoint listesinden optimize kapalı rota üretir.

        Adımlar:
            1. Maliyet matrisi hesapla (neural batch inference)
            2. Nearest neighbor ile başlangıç sıralaması bul
            3. 2-opt local search ile iyileştir
            4. Final sıralamaya göre A* ile segment rotalarını hesapla
            5. Segmentleri birleştir → tam rota

        Parameters
        ----------
        waypoints : list[int]
            OSM düğüm ID'lerinden oluşan waypoint listesi.
            Minimum 3, maksimum 20 waypoint önerilir.

        Returns
        -------
        RingRoute
        """
        t0 = time.perf_counter()
        n  = len(waypoints)

        if n < 2:
            raise ValueError("En az 2 waypoint gereklidir.")
        if n == 2:
            logger.warning("2 waypoint: gidiş-dönüş rotası üretilecek.")

        logger.info("Ring planlama başlıyor. %d waypoint.", n)

        # ── 1. Maliyet Matrisi ──────────────────
        cost_matrix = self._build_cost_matrix(waypoints)

        # ── 2. Nearest Neighbor Başlangıcı ──────
        order, nn_cost = self._nearest_neighbor(cost_matrix, start=0)
        log = [f"Nearest Neighbor başlangıç maliyeti: {nn_cost:.1f}"]
        logger.info("NN başlangıç sırası: %s | maliyet: %.1f", order, nn_cost)

        # ── 3. 2-opt İyileştirme ─────────────────
        if n > 3:
            order, final_cost, opt_log = self._two_opt(cost_matrix, order)
            log.extend(opt_log)
            improvement = (nn_cost - final_cost) / nn_cost * 100
            logger.info(
                "2-opt tamamlandı. Final maliyet: %.1f (iyileşme: %.1f%%)",
                final_cost, improvement,
            )
        else:
            log.append("n≤3: 2-opt atlandı.")

        # Optimize edilmiş waypoint sırası
        ordered_waypoints = [waypoints[i] for i in order]
        # Kapalı rota: başa dön
        ordered_waypoints_ring = ordered_waypoints + [ordered_waypoints[0]]

        # ── 4. A* Segment Hesaplama ──────────────
        segments = self._compute_segments(ordered_waypoints_ring, use_traffic=use_traffic)

        # ── 5. Birleştirme ───────────────────────
        full_path = self._merge_segments(segments)
        total_length = sum(s.total_length_m for s in segments)
        total_time   = sum(s.total_time_s   for s in segments)

        elapsed_ms = (time.perf_counter() - t0) * 1000

        logger.info(
            "Ring rota tamamlandı. %.2f km | %.0f dk | %d segment | %.0f ms",
            total_length / 1000, total_time / 60,
            len(segments), elapsed_ms,
        )

        return RingRoute(
            waypoints=ordered_waypoints,
            segments=segments,
            full_path=full_path,
            total_length_m=total_length,
            total_time_s=total_time,
            cost_matrix=cost_matrix,
            optimization_log=log,
            elapsed_ms=elapsed_ms,
        )

    # ──────────────────────────────────────────
    #  Maliyet Matrisi
    # ──────────────────────────────────────────

    def _build_cost_matrix(self, waypoints: list[int]) -> np.ndarray:
        """
        NxN simetrik olmayan maliyet matrisi oluşturur.

        Yönlü graf (DiGraph) kullanıldığından A→B ≠ B→A.
        NeuralHeuristic.predict_batch() ile tüm çiftler tek ONNX çağrısında
        hesaplanır; ayrı ayrı __call__ çağırmaktan ~N² kat hızlı.

        Parameters
        ----------
        waypoints : list[int]

        Returns
        -------
        np.ndarray  shape (N, N)  diagonal = inf (kendine gidiş yok)
        """
        n     = len(waypoints)
        pairs = []

        # Diagonal dışı tüm çiftler
        for i in range(n):
            for j in range(n):
                if i != j:
                    pairs.append((waypoints[i], waypoints[j]))

        logger.info(
            "Maliyet matrisi hesaplanıyor. %d çift, ONNX batch inference...",
            len(pairs),
        )

        costs = self.nh.predict_batch(pairs)

        # N×N matrise doldur
        matrix = np.full((n, n), np.inf, dtype=np.float32)
        idx = 0
        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i, j] = costs[idx]
                    idx += 1

        return matrix

    # ──────────────────────────────────────────
    #  Nearest Neighbor Heuristic
    # ──────────────────────────────────────────

    def _nearest_neighbor(
        self,
        cost_matrix: np.ndarray,
        start: int = 0,
    ) -> tuple[list[int], float]:
        """
        Açgözlü (greedy) en yakın komşu sıralaması üretir.

        Her adımda ziyaret edilmemiş düğümler arasından en düşük
        maliyetli olanı seçer. Kapalı rota için başa döner.

        Parameters
        ----------
        cost_matrix : np.ndarray  N×N
        start       : int  Başlangıç indeksi

        Returns
        -------
        tuple[order_list, total_cost]
        """
        n       = len(cost_matrix)
        visited = [False] * n
        order   = [start]
        visited[start] = True
        total_cost = 0.0

        current = start
        for _ in range(n - 1):
            # Ziyaret edilmemişler arasından en ucuz
            best_cost = np.inf
            best_next = -1
            for j in range(n):
                if not visited[j] and cost_matrix[current, j] < best_cost:
                    best_cost = cost_matrix[current, j]
                    best_next = j

            if best_next == -1:
                break   # Bağlantısız — kalan düğümleri ekle
                # (fallback: sırayla ekle)
                for j in range(n):
                    if not visited[j]:
                        order.append(j)
                        visited[j] = True
                break

            order.append(best_next)
            visited[best_next] = True
            total_cost += best_cost
            current = best_next

        # Başa dönüş maliyeti
        total_cost += cost_matrix[current, start]

        return order, total_cost

    # ──────────────────────────────────────────
    #  2-opt Local Search
    # ──────────────────────────────────────────

    def _two_opt(
        self,
        cost_matrix: np.ndarray,
        order: list[int],
    ) -> tuple[list[int], float, list[str]]:
        """
        2-opt local search ile rota iyileştirir.

        Algoritma:
            Tüm (i, k) kenar çifti kombinasyonlarını dene.
            order[i+1..k] segmentini tersine çevir.
            Yeni maliyet daha düşükse swap'ı kabul et.
            Hiçbir iyileştirme bulunamadığında veya max_iter'e
            ulaşıldığında dur.

        2-opt swap görsel açıklama:
            Önce:  A → B → ... → C → D → ... → A
            Sonra: A → C → ... → B → D → ... → A
            (B→C kesimi tersine çevrilir)

        Parameters
        ----------
        cost_matrix : np.ndarray
        order       : list[int]  Başlangıç sırası

        Returns
        -------
        tuple[improved_order, final_cost, log_messages]
        """
        n    = len(order)
        best = order[:]
        log  = []

        def route_cost(o: list[int]) -> float:
            """Kapalı rota maliyeti."""
            return sum(
                cost_matrix[o[i], o[(i + 1) % n]]
                for i in range(n)
            )

        best_cost    = route_cost(best)
        improved     = True
        iteration    = 0

        while improved and iteration < self.max_2opt_iter:
            improved  = False
            iteration += 1

            for i in range(n - 1):
                for k in range(i + 2, n):
                    # i ve k arasındaki segmenti tersine çevir
                    new_order = best[:i+1] + best[i+1:k+1][::-1] + best[k+1:]
                    new_cost  = route_cost(new_order)

                    if new_cost < best_cost - 1e-6:
                        best      = new_order
                        best_cost = new_cost
                        improved  = True
                        msg = (
                            f"  İter {iteration:3d} | "
                            f"swap ({i},{k}) | maliyet: {best_cost:.2f}"
                        )
                        log.append(msg)
                        break   # Bu iterasyonda en iyi swap bulundu → yeniden başla

                if improved:
                    break

        log.append(f"2-opt bitti. {iteration} iterasyon | final: {best_cost:.2f}")
        return best, best_cost, log

    # ──────────────────────────────────────────
    #  A* Segment Hesaplama
    # ──────────────────────────────────────────

    def _compute_segments(
        self,
        waypoints_ring: list[int],
        use_traffic: bool = False,
    ) -> list[PathResult]:
        """
        Ardışık waypoint çiftleri arasında A* ile segment rotaları hesaplar.

        Parameters
        ----------
        waypoints_ring : list[int]
            Optimize sıralı waypoints + ilk waypoint (kapalı rota).
            Örn: [A, C, B, D, A]

        Returns
        -------
        list[PathResult]  Her segment için bir PathResult.
        """
        segments = []
        n = len(waypoints_ring) - 1   # Son eleman başlangıca dönüş

        for idx in range(n):
            src = waypoints_ring[idx]
            tgt = waypoints_ring[idx + 1]

            logger.info(
                "Segment %d/%d: %d → %d", idx + 1, n, src, tgt
            )

            result = self.engine.find_path(src, tgt, use_traffic=use_traffic)

            if not result.found:
                logger.warning(
                    "Segment %d/%d bulunamadı: %d → %d. Boş segment eklendi.",
                    idx + 1, n, src, tgt,
                )

            segments.append(result)

        found_count = sum(1 for s in segments if s.found)
        logger.info(
            "%d/%d segment başarıyla hesaplandı.", found_count, n
        )
        return segments

    # ──────────────────────────────────────────
    #  Segment Birleştirme
    # ──────────────────────────────────────────

    def _merge_segments(self, segments: list[PathResult]) -> list[int]:
        """
        Birden fazla A* segmentini tek kesintisiz düğüm listesine birleştirir.

        Birleştirme kuralı:
            Segment i'nin son düğümü = Segment i+1'in ilk düğümü.
            Tekrarı önlemek için her segmentin ilk düğümü (segment 0 hariç) atlanır.

        Örnek:
            Segment 1: [A, B, C]
            Segment 2: [C, D, E]   → [C atlanır]
            Segment 3: [E, F, A]   → [E atlanır]
            Birleşik:  [A, B, C, D, E, F, A]

        Parameters
        ----------
        segments : list[PathResult]

        Returns
        -------
        list[int]  Tam rota düğüm listesi
        """
        full_path: list[int] = []

        for i, seg in enumerate(segments):
            if not seg.found or not seg.path:
                continue
            if i == 0:
                full_path.extend(seg.path)
            else:
                full_path.extend(seg.path[1:])  # İlk düğüm öncekinin sonu

        return full_path