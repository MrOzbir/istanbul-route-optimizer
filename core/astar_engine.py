"""
core/astar_engine.py
====================
İstanbul Yol Öneri Projesi — Bidirectional Hierarchical A* Motoru

Sorumluluk:
    Graf hiyerarşisi üzerinde iki yönlü (bidirectional) A* araması yapar.
    Neural heuristic ile entegre çalışacak şekilde tasarlanmıştır;
    mevcut hâlde saf Haversine sezgiseli kullanır, Görev 5'te sinir ağı
    tahmini bu fonksiyonun yerine geçecektir.

Algoritma Seçimi — Neden Bidirectional A*?
    Tek yönlü A* en kötü durumda O(b^d) düğüm açar (b: dallanma faktörü,
    d: derinlik). Bidirectional versiyonda her yön O(b^(d/2)) açar;
    toplam maliyet O(2 * b^(d/2)) ≈ O(b^(d/2)) — karesel kazanım.
    İstanbul gibi ~8.000 düğümlü graflarda bu fark 10-50x hız anlamına gelir.

Hiyerarşik Katman Stratejisi:
    ┌─────────────────────────────────────────────────────┐
    │ Mesafe < 5 km  → Arterial katman (primary/secondary)│
    │ Mesafe ≥ 5 km  → Express katman (motorway/trunk)    │
    │ Fallback       → Full graf (express bulamazsa)      │
    └─────────────────────────────────────────────────────┘

Min-Heap (heapq) Kullanımı:
    Python heapq modülü min-heap uygular.
    Her eleman: (f_score, counter, node_id)
    - f_score    : A* öncelik değeri (g + h)
    - counter    : Aynı f_score'da FIFO sırası (tie-breaking)
    - node_id    : OSM düğüm ID'si
    counter olmadan eşit f_score'lu düğümlerde node karşılaştırması yapılır,
    bu int için çalışır ama gelecekteki obje tipleri için güvenli değildir.

Kullanım:
    from core.astar_engine import AStarEngine
    engine = AStarEngine(hierarchy, h_cache, processor)
    result = engine.find_path(source_node, target_node)
"""

import heapq
import logging
import math
import time
from dataclasses import dataclass, field
from typing import Callable

import networkx as nx

from core.graph_processor import (
    GraphProcessor,
    HeuristicCache,
    HierarchicalGraph,
    haversine_meters,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Sabitler
# ─────────────────────────────────────────────

# Katman seçim eşiği (metre)
EXPRESS_THRESHOLD_M: float = 5_000.0   # 5 km üzeri → express layer

# Bidirectional buluşma toleransı
# İki yönün arama sınırları örtüştüğünde durdurulur
_MEET_TOLERANCE: float = 1e-6

# A* açma limiti — sonsuz döngü güvencesi
MAX_OPEN_NODES: int = 500_000

# Kenar maliyet anahtarı seçenekleri
COST_TRAVEL_TIME  = "travel_time"   # Saniye cinsinden geçiş süresi
COST_LENGTH       = "length"        # Metre cinsinden kenar uzunluğu


# ─────────────────────────────────────────────
#  Veri Sınıfları
# ─────────────────────────────────────────────

@dataclass
class PathResult:
    """
    A* aramasının sonuç paketi.

    Attributes
    ----------
    found : bool
        Rota bulundu mu?
    path : list[int]
        OSM düğüm ID'lerinden oluşan sıralı rota listesi.
    total_cost : float
        Kullanılan maliyet metriğinde toplam rota maliyeti.
    total_length_m : float
        Rota toplam uzunluğu (metre).
    total_time_s : float
        Tahmini geçiş süresi (saniye).
    nodes_explored : int
        Toplam açılan düğüm sayısı (forward + backward).
    layer_used : str
        Aramanın yapıldığı katman adı ("express" / "arterial" / "full").
    elapsed_ms : float
        Algoritma çalışma süresi (milisaniye).
    meet_node : int | None
        Bidirectional buluşma düğümü.
    """
    found:           bool        = False
    path:            list        = field(default_factory=list)
    total_cost:      float       = math.inf
    total_length_m:  float       = 0.0
    total_time_s:    float       = 0.0
    nodes_explored:  int         = 0
    layer_used:      str         = "unknown"
    elapsed_ms:      float       = 0.0
    meet_node:       int | None  = None


@dataclass
class _SearchState:
    """
    Tek yön (forward veya backward) için A* arama durumu.

    Attributes
    ----------
    open_heap : list
        Min-heap; elemanlar (f_score, counter, node) üçlüsü.
    g_score : dict[int, float]
        Kaynaktan her düğüme bilinen en iyi maliyet.
    came_from : dict[int, int | None]
        Yol yeniden yapılandırma için önceki düğüm.
    closed : set[int]
        Kesin maliyet bulunmuş düğümler.
    counter : int
        Tie-breaking sayacı (her push'ta artar).
    """
    open_heap: list              = field(default_factory=list)
    g_score:   dict              = field(default_factory=dict)
    came_from: dict              = field(default_factory=dict)
    closed:    set               = field(default_factory=set)
    counter:   int               = 0


# ─────────────────────────────────────────────
#  Ana Sınıf
# ─────────────────────────────────────────────

class AStarEngine:
    """
    Hiyerarşik Bidirectional A* arama motoru.

    Parameters
    ----------
    hierarchy : HierarchicalGraph
        GraphProcessor tarafından üretilmiş katmanlı graf yapısı.
    h_cache : HeuristicCache
        Haversine önbelleği (GraphProcessor.build_heuristic_cache()).
    processor : GraphProcessor
        get_heuristic() çağrıları için referans.
    cost_key : str
        Kenar maliyet metriği. "travel_time" (sn) veya "length" (m).
    heuristic_fn : Callable | None
        Özel sezgisel fonksiyon. None ise Haversine kullanılır.
        Görev 5'te ONNX sinir ağı buraya enjekte edilecektir.
    """

    def __init__(
        self,
        hierarchy: HierarchicalGraph,
        h_cache: HeuristicCache,
        processor: GraphProcessor,
        cost_key: str = COST_TRAVEL_TIME,
        heuristic_fn: Callable | None = None,
        traffic_manager = None,
    ) -> None:
        self.hierarchy    = hierarchy
        self.h_cache      = h_cache
        self.processor    = processor
        self.cost_key     = cost_key
        self.traffic_manager = traffic_manager

        # Sezgisel fonksiyon: dışarıdan enjekte edilebilir (sinir ağı için)
        # Görev 5'te: heuristic_fn = neural_heuristic.predict
        self._heuristic   = heuristic_fn or self._default_heuristic

        logger.info(
            "AStarEngine hazır. Maliyet metriği: '%s' | Sezgisel: %s | Trafik Desteği: %s",
            cost_key,
            "neural" if heuristic_fn else "haversine",
            "evet" if traffic_manager else "hayır"
        )

    # ──────────────────────────────────────────
    #  Dış Arayüz
    # ──────────────────────────────────────────

    def find_path(
        self,
        source: int,
        target: int,
        force_layer: str | None = None,
        use_traffic: bool = False,
    ) -> PathResult:
        """
        İki OSM düğümü arasında en kısa rotayı bulur.

        Katman seçimi:
            force_layer=None ise mesafeye göre otomatik seçim.
            force_layer="express" | "arterial" | "full" ile zorlanabilir.

        Parameters
        ----------
        source : int  Başlangıç OSM düğüm ID
        target : int  Bitiş OSM düğüm ID
        force_layer : str | None

        Returns
        -------
        PathResult
        """
        t_start = time.perf_counter()

        # ── Önkoşul Kontrolleri ─────────────────
        if source == target:
            return PathResult(found=True, path=[source], total_cost=0.0)

        # Katman seçimi
        graph_fwd, graph_bwd, layer_name = self._select_layer(
            source, target, force_layer
        )

        # Düğüm varlık kontrolü — seçilen katmanda yoksa fallback
        if source not in graph_fwd or target not in graph_fwd:
            logger.warning(
                "Düğüm katmanda bulunamadı (%s). Full grafa fallback.",
                layer_name,
            )
            graph_fwd  = self.hierarchy.full
            graph_bwd  = self.hierarchy.full.reverse(copy=False)
            layer_name = "full_fallback"

        # Güvenlik Kontrolü: Fallback sonrasında da düğüm yoksa arama yapmadan dön
        if source not in graph_fwd or target not in graph_fwd:
            logger.debug("Düğüm(ler) hiyerarşik grafikte mevcut değil. Rota bulunamadı.")
            return PathResult(found=False, layer_used=layer_name)

        # ── Bidirectional A* ────────────────────
        result = self._bidirectional_astar(
            graph_fwd, graph_bwd, source, target, layer_name, use_traffic=use_traffic
        )

        # Rota alt katmanda bulunamadıysa (örneğin iki kıta arasında arterial yolla geçiş yoksa), full grafa fallback yap
        if not result.found and layer_name not in ("full", "full_fallback"):
            logger.warning(
                "Rota alt katmanda (%s) bulunamadı. Full grafa fallback yapılıyor...",
                layer_name,
            )
            graph_fwd  = self.hierarchy.full
            graph_bwd  = self.hierarchy.full.reverse(copy=False)
            layer_name = "full_fallback"
            
            if source in graph_fwd and target in graph_fwd:
                result = self._bidirectional_astar(
                    graph_fwd, graph_bwd, source, target, layer_name, use_traffic=use_traffic
                )

        result.elapsed_ms = (time.perf_counter() - t_start) * 1000

        # Rota boyunca gerçek mesafe ve süreyi hesapla
        if result.found and len(result.path) > 1:
            result.total_length_m, result.total_time_s = (
                self._compute_path_metrics(graph_fwd, result.path, use_traffic=use_traffic)
            )

        logger.info(
            "Rota %s | %d düğüm | %.1f km | %.0f sn | %d açılmış | %.1f ms",
            "BULUNDU ✓" if result.found else "BULUNAMADI ✗",
            len(result.path),
            result.total_length_m / 1000,
            result.total_time_s,
            result.nodes_explored,
            result.elapsed_ms,
        )
        return result

    # ──────────────────────────────────────────
    #  Katman Seçici
    # ──────────────────────────────────────────

    def _select_layer(
        self,
        source: int,
        target: int,
        force_layer: str | None,
    ) -> tuple[nx.MultiDiGraph, nx.MultiDiGraph, str]:
        """
        Aramanın yapılacağı graf çiftini (forward, backward) döndürür.

        Mesafe eşiği:
            < 5 km  → arterial (primary/secondary)
            ≥ 5 km  → express  (motorway/trunk)

        Parameters
        ----------
        source, target : int
        force_layer : str | None

        Returns
        -------
        tuple[forward_graph, backward_graph, layer_name]
        """
        if force_layer == "express":
            return (
                self.hierarchy.express,
                self.hierarchy.express_reversed,
                "express",
            )
        if force_layer == "arterial":
            return (
                self.hierarchy.arterial,
                self.hierarchy.arterial_reversed,
                "arterial",
            )
        if force_layer == "full":
            return (
                self.hierarchy.full,
                self.hierarchy.full.reverse(copy=False),
                "full",
            )

        # Otomatik seçim: kuş uçuşu mesafeye bak
        dist_m = self.processor.get_heuristic(self.h_cache, source, target)

        if dist_m >= EXPRESS_THRESHOLD_M:
            logger.debug(
                "Katman → express (mesafe: %.1f km)", dist_m / 1000
            )
            return (
                self.hierarchy.express,
                self.hierarchy.express_reversed,
                "express",
            )

        logger.debug(
            "Katman → arterial (mesafe: %.1f km)", dist_m / 1000
        )
        return (
            self.hierarchy.arterial,
            self.hierarchy.arterial_reversed,
            "arterial",
        )

    # ──────────────────────────────────────────
    #  Bidirectional A* Çekirdeği
    # ──────────────────────────────────────────

    def _bidirectional_astar(
        self,
        graph_fwd: nx.MultiDiGraph,
        graph_bwd: nx.MultiDiGraph,
        source: int,
        target: int,
        layer_name: str,
        use_traffic: bool = False,
    ) -> PathResult:
        """
        İki yönlü A* aramasını çalıştırır.

        Algoritma Akışı:
        ─────────────────────────────────────────
        1. Forward state  : source → target yönünde
           Backward state : target → source yönünde (ters graf üzerinde)

        2. Her adımda daha düşük f_score'u olan yönden bir düğüm aç.

        3. Buluşma koşulu:
           Forward'ın açtığı düğüm backward'ın closed set'inde ise
           (veya tam tersi) iki yol birleşir.

        4. En iyi buluşma maliyeti: μ (mu)
           μ = min over all meet_nodes of (g_fwd[m] + g_bwd[m])

        5. Durma koşulu:
           top(fwd_heap) + top(bwd_heap) >= μ
           (Pohl, 1971 — bidirectional optimality condition)

        Parameters
        ----------
        graph_fwd : forward arama grafı
        graph_bwd : backward arama grafı (ters kenarlar)
        source, target : int
        layer_name : str

        Returns
        -------
        PathResult
        """
        # ── Başlangıç Durumları ─────────────────
        fwd = _SearchState()
        bwd = _SearchState()

        # g_score başlangıcı
        fwd.g_score[source] = 0.0
        bwd.g_score[target] = 0.0

        # came_from kökü None
        fwd.came_from[source] = None
        bwd.came_from[target] = None

        # Min-heap başlangıç push'ları
        h_source = self._heuristic(source, target)
        h_target = self._heuristic(target, source)

        heapq.heappush(fwd.open_heap, (h_source, fwd.counter, source))
        heapq.heappush(bwd.open_heap, (h_target, bwd.counter, target))
        fwd.counter += 1
        bwd.counter += 1

        # En iyi buluşma maliyeti ve düğümü
        mu:        float    = math.inf
        meet_node: int | None = None
        explored:  int      = 0

        # ── Ana Döngü ───────────────────────────
        while fwd.open_heap and bwd.open_heap:

            # Güvenlik limiti
            if explored >= MAX_OPEN_NODES:
                logger.warning(
                    "MAX_OPEN_NODES (%d) sınırına ulaşıldı. Arama sonlandırıldı.",
                    MAX_OPEN_NODES,
                )
                break

            # Durma koşulu (Pohl): iki heap tepesinin toplamı μ'yu geçtiyse dur
            f_fwd_top = fwd.open_heap[0][0]
            f_bwd_top = bwd.open_heap[0][0]

            if f_fwd_top + f_bwd_top >= mu - _MEET_TOLERANCE:
                break

            # Hangi yön daha umut verici? Küçük f_score'u seç
            if f_fwd_top <= f_bwd_top:
                mu, meet_node, explored = self._expand_node(
                    state=fwd,
                    graph=graph_fwd,
                    other_state=bwd,
                    target=target,
                    direction="forward",
                    mu=mu,
                    meet_node=meet_node,
                    explored=explored,
                    use_traffic=use_traffic,
                )
            else:
                mu, meet_node, explored = self._expand_node(
                    state=bwd,
                    graph=graph_bwd,
                    other_state=fwd,
                    target=source,         # backward için "hedef" source'dur
                    direction="backward",
                    mu=mu,
                    meet_node=meet_node,
                    explored=explored,
                    use_traffic=use_traffic,
                )

        # ── Sonuç Oluştur ───────────────────────
        if meet_node is None or mu == math.inf:
            return PathResult(
                found=False,
                layer_used=layer_name,
                nodes_explored=explored,
            )

        path = self._reconstruct_path(fwd.came_from, bwd.came_from, meet_node)
        return PathResult(
            found=True,
            path=path,
            total_cost=mu,
            layer_used=layer_name,
            nodes_explored=explored,
            meet_node=meet_node,
        )

    def _expand_node(
        self,
        state: _SearchState,
        graph: nx.MultiDiGraph,
        other_state: _SearchState,
        target: int,
        direction: str,
        mu: float,
        meet_node: int | None,
        explored: int,
        use_traffic: bool = False,
    ) -> tuple[float, int | None, int]:
        """
        Min-heap'ten en düşük f_score'lu düğümü çıkarır ve komşularını genişletir.

        Lazy deletion stratejisi:
            Heap'ten çekilen düğüm zaten closed set'indeyse atlanır.
            Bu, heapq'nun decrease-key eksikliğini telafi eder:
            güncellenen düğüm heap'e tekrar push edilir,
            eski kopyası lazy olarak discard edilir.

        Parameters
        ----------
        state      : Aktif yönün arama durumu
        graph      : Aktif yönün grafı
        other_state: Karşı yönün durumu (buluşma kontrolü için)
        target     : Bu yön için hedef düğüm
        direction  : "forward" | "backward" (loglama)
        mu         : Mevcut en iyi buluşma maliyeti
        meet_node  : Mevcut en iyi buluşma düğümü
        explored   : Toplam açılan düğüm sayacı

        Returns
        -------
        tuple[mu, meet_node, explored]
        """
        # Min-heap'ten çek
        _, _, current = heapq.heappop(state.open_heap)

        # Lazy deletion: zaten işlendiyse atla
        if current in state.closed:
            return mu, meet_node, explored

        state.closed.add(current)
        explored += 1

        g_current = state.g_score[current]

        # ── Komşu Genişletme ────────────────────
        for neighbor in graph.neighbors(current):
            if neighbor in state.closed:
                continue

            # En ucuz kenarı al (paralel kenar olabilir)
            edge_cost = self._get_edge_cost(graph, current, neighbor, use_traffic=use_traffic)
            if edge_cost is None:
                continue

            tentative_g = g_current + edge_cost

            # Daha iyi yol bulundu mu?
            if tentative_g < state.g_score.get(neighbor, math.inf):
                state.g_score[neighbor]   = tentative_g
                state.came_from[neighbor] = current

                h = self._heuristic(neighbor, target)
                f = tentative_g + h

                state.counter += 1
                heapq.heappush(state.open_heap, (f, state.counter, neighbor))

            # Buluşma kontrolü: komşu karşı yönün g_score'unda mı? (her iki taraftan da erişilmiş mi?)
            if neighbor in other_state.g_score:
                candidate_mu = (
                    tentative_g
                    + other_state.g_score.get(neighbor, math.inf)
                )
                if candidate_mu < mu:
                    mu        = candidate_mu
                    meet_node = neighbor
                    logger.debug(
                        "[%s] Yeni buluşma düğümü: %d | μ=%.2f",
                        direction, neighbor, mu,
                    )

        return mu, meet_node, explored

    # ──────────────────────────────────────────
    #  Yol Yeniden Yapılandırma
    # ──────────────────────────────────────────

    def _reconstruct_path(
        self,
        came_from_fwd: dict[int, int | None],
        came_from_bwd: dict[int, int | None],
        meet_node: int,
    ) -> list[int]:
        """
        Forward ve backward came_from zincirlerini buluşma noktasında birleştirir.

        Forward yol : source → meet_node
        Backward yol: meet_node → target  (ters çevrilmiş)

        Parameters
        ----------
        came_from_fwd : {düğüm: önceki_düğüm} forward zinciri
        came_from_bwd : {düğüm: önceki_düğüm} backward zinciri
        meet_node : int

        Returns
        -------
        list[int]  Tam rota (source dahil, target dahil)
        """
        # Forward: meet_node'dan source'a geri git, sonra tersle
        path_fwd: list[int] = []
        node = meet_node
        while node is not None:
            path_fwd.append(node)
            node = came_from_fwd.get(node)
        path_fwd.reverse()   # source → meet_node

        # Backward: meet_node'dan target'a git
        path_bwd: list[int] = []
        node = came_from_bwd.get(meet_node)  # meet_node zaten fwd'de var
        while node is not None:
            path_bwd.append(node)
            node = came_from_bwd.get(node)
        # path_bwd zaten target'a doğru sıralı

        return path_fwd + path_bwd

    # ──────────────────────────────────────────
    #  Yardımcı Metotlar
    # ──────────────────────────────────────────

    def _get_edge_cost(
        self,
        graph: nx.MultiDiGraph,
        u: int,
        v: int,
        use_traffic: bool = False,
    ) -> float | None:
        """
        İki düğüm arasındaki en ucuz kenar maliyetini döndürür.

        MultiDiGraph'ta u→v arasında birden fazla kenar olabilir
        (paralel yollar, farklı şeritler). En düşük maliyetli seçilir.

        Eksik maliyet değeri için fallback:
            travel_time yoksa: length / 13.88 (50 km/s varsayım)
            length     yoksa: Haversine mesafesi

        Parameters
        ----------
        graph : nx.MultiDiGraph
        u, v : int

        Returns
        -------
        float | None  (None: kenar yoksa)
        """
        edges = graph.get_edge_data(u, v)
        if not edges:
            return None

        best = math.inf
        for edge_data in edges.values():
            if self.cost_key == COST_TRAVEL_TIME:
                multiplier = 1.0
                if use_traffic and self.traffic_manager:
                    multiplier = self.traffic_manager.get_edge_multiplier(u, v, edge_data)
                cost = edge_data.get(
                    "travel_time",
                    edge_data.get("length", 0) / 13.888,  # 50 km/s fallback
                ) * multiplier
            else:  # LENGTH
                cost = edge_data.get("length", 0)

            if cost < best:
                best = cost

        return best if best < math.inf else None

    def _default_heuristic(self, node_u: int, node_v: int) -> float:
        """
        Varsayılan Haversine sezgiseli.

        Görev 5'te bu fonksiyon ONNX sinir ağı tahminiyle değiştirilecek.
        Maliyet travel_time ise heuristici saniyeye çevir (÷ 13.88 m/s).

        Parameters
        ----------
        node_u, node_v : int

        Returns
        -------
        float  Tahmin edilen maliyet
        """
        dist_m = self.processor.get_heuristic(self.h_cache, node_u, node_v)

        if self.cost_key == COST_TRAVEL_TIME:
            # Otoyolda ortalama hız ~80 km/s → 22.22 m/s
            # Admissible: gerçek süreyi asla aşmaz
            return dist_m / 22.22

        return dist_m  # LENGTH metriği için metre olarak döner

    def _compute_path_metrics(
        self,
        graph: nx.MultiDiGraph,
        path: list[int],
        use_traffic: bool = False,
    ) -> tuple[float, float]:
        """
        Bulunan rota üzerindeki toplam mesafe ve süreyi hesaplar.

        Parameters
        ----------
        graph : nx.MultiDiGraph
        path  : list[int]
        use_traffic : bool

        Returns
        -------
        tuple[total_length_m, total_time_s]
        """
        total_length = 0.0
        total_time   = 0.0

        for i in range(len(path) - 1):
            u, v  = path[i], path[i + 1]
            edges = graph.get_edge_data(u, v)
            if not edges:
                continue

            # En kısa kenarı seç
            best = min(edges.values(), key=lambda d: d.get("length", math.inf))
            total_length += best.get("length", 0)
            
            multiplier = 1.0
            if use_traffic and self.traffic_manager:
                multiplier = self.traffic_manager.get_edge_multiplier(u, v, best)
                
            total_time   += best.get(
                "travel_time",
                best.get("length", 0) / 13.888,
            ) * multiplier

        return total_length, total_time


# ─────────────────────────────────────────────
#  CLI Giriş Noktası
# ─────────────────────────────────────────────

if __name__ == "__main__":
    from core.map_loader import MapLoader
    from core.graph_processor import GraphProcessor

    # 1. Graf yükle
    loader = MapLoader()
    try:
        graph = loader.load_from_disk()
    except FileNotFoundError:
        graph = loader.run()

    # 2. İşlemci ve hiyerarşi
    processor  = GraphProcessor(graph)
    hierarchy  = processor.build_hierarchy(save=False)
    h_cache    = processor.build_heuristic_cache(save=False)

    # 3. Motor
    engine = AStarEngine(hierarchy, h_cache, processor, cost_key=COST_TRAVEL_TIME)

    # 4. Test: Taksim → Kadıköy
    nodes = list(graph.nodes(data=True))

    # Yaklaşık koordinatlara en yakın düğümleri bul
    import osmnx as ox
    taksim_node  = ox.distance.nearest_nodes(hierarchy.full, X=28.9784, Y=41.0369)
    kadikoy_node = ox.distance.nearest_nodes(hierarchy.full, X=29.0264, Y=40.9906)

    print(f"\nTaksim  düğüm ID : {taksim_node}")
    print(f"Kadıköy düğüm ID : {kadikoy_node}")

    result = engine.find_path(taksim_node, kadikoy_node)

    print("\n── Rota Sonucu ─────────────────────────────")
    print(f"  Bulundu         : {result.found}")
    print(f"  Katman          : {result.layer_used}")
    print(f"  Düğüm sayısı    : {len(result.path)}")
    print(f"  Toplam mesafe   : {result.total_length_m/1000:.2f} km")
    print(f"  Tahmini süre    : {result.total_time_s/60:.1f} dakika")
    print(f"  Açılan düğüm    : {result.nodes_explored}")
    print(f"  Algoritma süresi: {result.elapsed_ms:.1f} ms")
    print(f"  Buluşma düğümü  : {result.meet_node}")
    print("────────────────────────────────────────────")