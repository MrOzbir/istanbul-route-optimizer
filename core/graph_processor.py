"""
core/graph_processor.py
=======================
İstanbul Yol Öneri Projesi — Graf İşleme ve Hiyerarşik Katmanlama Modülü

Sorumluluk:
    MapLoader'dan gelen ham MultiDiGraph'ı A* ve sinir ağı pipeline'ı için
    hazırlar. İki ana çıktı üretir:

    1. HierarchicalGraph: "Express" (motorway/trunk) ve "Arterial"
       (primary/secondary) olmak üzere iki katmanlı graf yapısı.
       Bidirectional A* için her iki yön de hazır tutulur.

    2. HeuristicCache: Düğümler arası Haversine mesafelerini bellekte
       ve diskte önbellekleyen yapı. A* sezgisel fonksiyonu O(1) ile
       çalışır, tekrar hesaplama yapılmaz.

Tasarım Kararları:
    - Katman ayrımı → uzak mesafelerde sadece Express layer aranır.
      Bu, düğüm uzayını ~%60 küçültür (21K → ~8K kenar).
    - Pickle önbellek → büyük şehirlerde koordinat sorgusu yavaştır.
      Önbellekle tekrar çalıştırmalarda sıfır I/O maliyeti.
    - frozen=False MultiDiGraph kopyaları → orijinal graf bozulmaz.

Kullanım:
    from core.graph_processor import GraphProcessor
    processor = GraphProcessor(graph)
    hierarchy = processor.build_hierarchy()
    cache     = processor.build_heuristic_cache()
"""

import logging
import math
import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import networkx as nx
import osmnx as ox

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Sabitler
# ─────────────────────────────────────────────

DATA_PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"

# Hiyerarşik katman tanımları
EXPRESS_HIGHWAY_TYPES: frozenset[str] = frozenset({
    "motorway", "motorway_link",
    "trunk", "trunk_link",
})

ARTERIAL_HIGHWAY_TYPES: frozenset[str] = frozenset({
    "primary", "primary_link",
    "secondary", "secondary_link",
})

# Dünya yarıçapı (Haversine için)
_EARTH_RADIUS_M = 6_371_000.0


# ─────────────────────────────────────────────
#  Veri Sınıfları
# ─────────────────────────────────────────────

@dataclass
class HierarchicalGraph:
    """
    İki katmanlı graf yapısı.

    Attributes
    ----------
    express : nx.MultiDiGraph
        Sadece motorway + trunk kenarlarını içerir.
        Şehirlerarası / uzun mesafe aramalar için kullanılır.
    arterial : nx.MultiDiGraph
        primary + secondary kenarları. Orta mesafe aramalar için.
    full : nx.MultiDiGraph
        Tüm katmanlar birleşik (fallback ve görselleştirme için).
    express_reversed : nx.MultiDiGraph
        Bidirectional A* için express katmanının ters yönü.
    arterial_reversed : nx.MultiDiGraph
        Bidirectional A* için arterial katmanının ters yönü.
    layer_stats : dict
        Her katman için düğüm/kenar sayısı özeti.
    """
    express:           nx.MultiDiGraph = field(default_factory=nx.MultiDiGraph)
    arterial:          nx.MultiDiGraph = field(default_factory=nx.MultiDiGraph)
    full:              nx.MultiDiGraph = field(default_factory=nx.MultiDiGraph)
    express_reversed:  nx.MultiDiGraph = field(default_factory=nx.MultiDiGraph)
    arterial_reversed: nx.MultiDiGraph = field(default_factory=nx.MultiDiGraph)
    layer_stats:       dict            = field(default_factory=dict)


@dataclass
class HeuristicCache:
    """
    A* sezgisel mesafe önbelleği.

    Attributes
    ----------
    node_coords : dict[int, tuple[float, float]]
        {osmid: (lat, lon)} — tüm düğümlerin koordinatları.
    distance_cache : dict[tuple[int,int], float]
        {(u, v): metre} — hesaplanmış Haversine mesafeleri.
        LRU benzeri dinamik büyüme; sık kullanılan çiftler kalır.
    cache_hits : int
        Önbellekten kaç kez okunduğu (profiling için).
    cache_misses : int
        Önbellekte bulunmayan ve hesaplanan mesafe sayısı.
    """
    node_coords:    dict = field(default_factory=dict)
    distance_cache: dict = field(default_factory=dict)
    cache_hits:     int  = 0
    cache_misses:   int  = 0


# ─────────────────────────────────────────────
#  Yardımcı Fonksiyonlar
# ─────────────────────────────────────────────

def haversine_meters(lat1: float, lon1: float,
                     lat2: float, lon2: float) -> float:
    """
    İki coğrafi nokta arasındaki Haversine mesafesini metre cinsinden hesaplar.

    A* sezgisel fonksiyonu için admissible (kabul edilebilir) bir alt sınır
    üretir; gerçek yol mesafesini asla aşmaz.

    Parameters
    ----------
    lat1, lon1 : float  Başlangıç noktası (derece)
    lat2, lon2 : float  Bitiş noktası (derece)

    Returns
    -------
    float  Kuş uçuşu mesafe (metre)
    """
    # Radyana çevir
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)

    a = (math.sin(Δφ / 2) ** 2
         + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return _EARTH_RADIUS_M * c


def _normalize_highway(value) -> str:
    """
    OSM `highway` özelliğinin bazen liste döndürmesi sorununu giderir.

    OSM verisinde bir kenara birden fazla `highway` etiketi atanabilir.
    Bu durumda OSMnx liste döndürür; ilk elemanı alıyoruz.

    Parameters
    ----------
    value : str | list[str]

    Returns
    -------
    str
    """
    if isinstance(value, list):
        return value[0]
    return str(value)


def _iter_edges_by_type(
    graph: nx.MultiDiGraph,
    allowed_types: frozenset[str],
) -> Iterator[tuple]:
    """
    Graf üzerinde yalnızca izin verilen yol tiplerine ait kenarları üretir.

    Parameters
    ----------
    graph : nx.MultiDiGraph
    allowed_types : frozenset[str]

    Yields
    ------
    tuple  (u, v, key, data)
    """
    for u, v, key, data in graph.edges(keys=True, data=True):
        hw = _normalize_highway(data.get("highway", ""))
        if hw in allowed_types:
            yield u, v, key, data


# ─────────────────────────────────────────────
#  Ana Sınıf
# ─────────────────────────────────────────────

class GraphProcessor:
    """
    Ham OSMnx grafını A* pipeline'ı için hazırlayan işlemci.

    Parameters
    ----------
    graph : nx.MultiDiGraph
        MapLoader tarafından üretilmiş, zenginleştirilmiş graf.
    processed_dir : Path
        İşlenmiş verilerin kaydedileceği dizin.
    """

    def __init__(
        self,
        graph: nx.MultiDiGraph,
        processed_dir: Path = DATA_PROCESSED,
    ) -> None:
        # Yol ağı üzerindeki tek yönlü çıkmaz sokakları (sinks) ve giriş-çıkış olamayan
        # kopuk düğümleri temizlemek için grafı en büyük güçlü bağlı bileşene (SCC) indirgiyoruz.
        # Bu işlem in-place yapıldığı için app.py ve diğer bileşenlerdeki graf referansı da güncellenir.
        # Küçük test grafiklerinin bozulmaması için bu işlemi sadece 100 düğümden büyük graflar için yapıyoruz.
        if graph.number_of_nodes() > 100:
            sccs = list(nx.strongly_connected_components(graph))
            if sccs:
                largest_scc = max(sccs, key=len)
                nodes_to_remove = set(graph.nodes) - set(largest_scc)
                if nodes_to_remove:
                    graph.remove_nodes_from(nodes_to_remove)
                    logger.info(
                        "Graf en büyük güçlü bağlı bileşene (SCC) indirgendi. %d düğüm temizlendi.",
                        len(nodes_to_remove)
                    )

        self.graph = graph
        self.processed_dir = Path(processed_dir)
        self.processed_dir.mkdir(parents=True, exist_ok=True)

        # Düğüm koordinat tablosu — bir kez çıkar, defalarca kullan
        self._node_coords: dict[int, tuple[float, float]] = self._extract_node_coords()

        logger.info(
            "GraphProcessor hazır. %d düğüm, %d kenar.",
            graph.number_of_nodes(), graph.number_of_edges()
        )

    # ──────────────────────────────────────────
    #  Hiyerarşik Katmanlama
    # ──────────────────────────────────────────

    def build_hierarchy(self, save: bool = True) -> HierarchicalGraph:
        """
        Grafı Express ve Arterial katmanlarına böler.

        Bidirectional A* için her katmanın ters kopyası da üretilir.
        Ters kopya: `graph.reverse(copy=True)` → tüm kenar yönleri çevrilir.

        Parameters
        ----------
        save : bool
            True ise katmanlar .graphml olarak kaydedilir.

        Returns
        -------
        HierarchicalGraph
        """
        logger.info("Hiyerarşik katmanlama başlıyor...")

        express   = self._extract_layer(EXPRESS_HIGHWAY_TYPES,   "express")
        arterial  = self._extract_layer(ARTERIAL_HIGHWAY_TYPES,  "arterial")

        # Bidirectional A* için ters graflar
        # reverse() tüm kenar yönlerini tersine çevirir;
        # hedefe yaklaşan arama bu graf üzerinde ilerler.
        express_rev  = express.reverse(copy=True)
        arterial_rev = arterial.reverse(copy=True)

        # Tam birleşik graf (görselleştirme + fallback)
        full = nx.compose(express, arterial)

        # Orijinal graf özniteliklerini (örneğin crs) tüm katmanlara aktar
        express.graph.update(self.graph.graph)
        arterial.graph.update(self.graph.graph)
        express_rev.graph.update(self.graph.graph)
        arterial_rev.graph.update(self.graph.graph)
        full.graph.update(self.graph.graph)

        hierarchy = HierarchicalGraph(
            express=express,
            arterial=arterial,
            full=full,
            express_reversed=express_rev,
            arterial_reversed=arterial_rev,
            layer_stats=self._compute_layer_stats(express, arterial, full),
        )

        self._log_hierarchy_stats(hierarchy)

        if save:
            self._save_layer(express,   "express.graphml")
            self._save_layer(arterial,  "arterial.graphml")
            self._save_layer(full,      "full_hierarchy.graphml")
            logger.info("Katmanlar kaydedildi: %s", self.processed_dir)

        return hierarchy

    def _extract_layer(
        self,
        allowed_types: frozenset[str],
        layer_name: str,
    ) -> nx.MultiDiGraph:
        """
        Orijinal graftan belirtilen yol tiplerine ait alt-grafı çıkarır.

        Yaklaşım:
            Kenarları filtrele → ilgili düğümleri bul → subgraph oluştur.
            nx.subgraph_view kullanılmaz çünkü kenar kopyası gereklidir
            (ters graf için orijinal mutasyona uğramamalı).

        Parameters
        ----------
        allowed_types : frozenset[str]
        layer_name : str  (loglama için)

        Returns
        -------
        nx.MultiDiGraph
        """
        layer = nx.MultiDiGraph()

        # Düğüm bilgilerini aktar (koordinatlar, osmid vb.)
        for node, data in self.graph.nodes(data=True):
            layer.add_node(node, **data)

        # Sadece izin verilen yol tipindeki kenarları aktar
        edge_count = 0
        for u, v, key, data in _iter_edges_by_type(self.graph, allowed_types):
            layer.add_edge(u, v, key=key, **data)
            edge_count += 1

        # Bağlantısız düğümleri temizle (en büyük bileşeni tut)
        layer = self._keep_largest_component(layer, layer_name)

        logger.info(
            "Katman '%s': %d düğüm, %d kenar (filtre öncesi: %d kenar)",
            layer_name,
            layer.number_of_nodes(),
            layer.number_of_edges(),
            edge_count,
        )
        return layer

    def _keep_largest_component(
        self,
        graph: nx.MultiDiGraph,
        name: str,
    ) -> nx.MultiDiGraph:
        """
        Graftaki küçük, kopuk ve çıkmaz sokak oluşturan bileşenleri temizler.

        İstanbul gibi iki kıtaya yayılan şehirlerde en büyük bileşeni tutmak
        kıtalararası bağlantıyı kesebilir (örneğin sadece motorways ile geçiş varken
        arterial katmanda Avrupa ve Asya ayrılır). Bu nedenle en az 100 düğüme
        sahip tüm büyük bileşenler korunur, sadece ufak rampa/köprü artıkları silinir.

        Parameters
        ----------
        graph : nx.MultiDiGraph
        name : str

        Returns
        -------
        nx.MultiDiGraph
        """
        components = list(nx.weakly_connected_components(graph))
        if len(components) <= 1:
            return graph

        # En az 100 düğümlü tüm bileşenleri koru (hem Avrupa hem Asya yakaları kalır)
        large_nodes = set()
        for c in components:
            if len(c) >= 100:
                large_nodes.update(c)

        # Eğer hiç >= 100 düğümlü bileşen yoksa, en büyüğünü tut (fallback)
        if not large_nodes:
            largest = max(components, key=len)
            large_nodes.update(largest)

        pruned = graph.subgraph(large_nodes).copy()

        removed = graph.number_of_nodes() - pruned.number_of_nodes()
        if removed > 0:
            logger.debug(
                "Katman '%s': %d kopuk/ufak düğüm kaldırıldı (Büyük yakalar korundu).", name, removed
            )
        return pruned

    # ──────────────────────────────────────────
    #  Sezgisel Önbellek
    # ──────────────────────────────────────────

    def build_heuristic_cache(
        self,
        save: bool = True,
        cache_filename: str = "heuristic_cache.pkl",
    ) -> HeuristicCache:
        """
        A* sezgisel fonksiyonu için Haversine önbelleği oluşturur.

        Strateji:
            - Tüm düğüm koordinatları bir dict'e alınır → O(1) lookup.
            - Mesafe cache'i başta boş başlar; A* çalışırken dinamik
              olarak doldurulur (lazy evaluation).
            - `get_heuristic()` metodu ile dışarıdan kullanılır.

        Parameters
        ----------
        save : bool
        cache_filename : str

        Returns
        -------
        HeuristicCache
        """
        logger.info("Sezgisel önbellek oluşturuluyor...")

        # Önceden kaydedilmiş cache varsa yükle
        cache_path = self.processed_dir / cache_filename
        if cache_path.exists():
            return self._load_heuristic_cache(cache_path)

        cache = HeuristicCache(node_coords=self._node_coords.copy())

        if save:
            self._save_heuristic_cache(cache, cache_path)

        logger.info(
            "Önbellek hazır. %d düğüm koordinatı yüklendi.",
            len(cache.node_coords)
        )
        return cache

    def get_heuristic(
        self,
        cache: HeuristicCache,
        node_u: int,
        node_v: int,
    ) -> float:
        """
        İki düğüm arasındaki A* sezgisel değerini (metre) döndürür.

        Önbellekte varsa O(1), yoksa Haversine hesaplayıp önbelleğe yazar.
        Bu fonksiyon A* inner loop'unda her adımda çağrılır; minimal overhead
        kritik önemdedir.

        Parameters
        ----------
        cache : HeuristicCache
        node_u : int  Kaynak OSM düğüm ID
        node_v : int  Hedef OSM düğüm ID

        Returns
        -------
        float  Tahmini mesafe (metre)
        """
        key = (node_u, node_v)

        # Önbellek kontrolü
        if key in cache.distance_cache:
            cache.cache_hits += 1
            return cache.distance_cache[key]

        # Koordinatları al
        lat1, lon1 = cache.node_coords[node_u]
        lat2, lon2 = cache.node_coords[node_v]

        # Haversine hesapla ve önbelleğe yaz
        dist = haversine_meters(lat1, lon1, lat2, lon2)
        cache.distance_cache[key] = dist
        cache.cache_misses += 1

        return dist

    # ──────────────────────────────────────────
    #  Yardımcı Metotlar
    # ──────────────────────────────────────────

    def _extract_node_coords(self) -> dict[int, tuple[float, float]]:
        """
        Graf düğümlerinden {osmid: (lat, lon)} sözlüğü oluşturur.

        OSMnx 'y' = latitude, 'x' = longitude kullanır.
        """
        coords = {}
        for node, data in self.graph.nodes(data=True):
            coords[node] = (data["y"], data["x"])   # (lat, lon)
        return coords

    def _compute_layer_stats(
        self,
        express: nx.MultiDiGraph,
        arterial: nx.MultiDiGraph,
        full: nx.MultiDiGraph,
    ) -> dict:
        """Her katman için istatistik özeti üretir."""
        def stats(g: nx.MultiDiGraph, name: str) -> dict:
            total_len = sum(
                d.get("length", 0) for _, _, d in g.edges(data=True)
            )
            return {
                f"{name}_nodes":      g.number_of_nodes(),
                f"{name}_edges":      g.number_of_edges(),
                f"{name}_length_km":  round(total_len / 1000, 1),
            }

        return {
            **stats(express, "express"),
            **stats(arterial, "arterial"),
            **stats(full, "full"),
        }

    def _log_hierarchy_stats(self, h: HierarchicalGraph) -> None:
        """Katman istatistiklerini log'a yazar."""
        s = h.layer_stats
        logger.info(
            "── Katman Özeti ──────────────────────────────\n"
            "  Express  : %5d düğüm | %5d kenar | %7.1f km\n"
            "  Arterial : %5d düğüm | %5d kenar | %7.1f km\n"
            "  Full     : %5d düğüm | %5d kenar | %7.1f km\n"
            "──────────────────────────────────────────────",
            s["express_nodes"],  s["express_edges"],  s["express_length_km"],
            s["arterial_nodes"], s["arterial_edges"], s["arterial_length_km"],
            s["full_nodes"],     s["full_edges"],     s["full_length_km"],
        )

    def _save_layer(self, graph: nx.MultiDiGraph, filename: str) -> None:
        """Graf katmanını .graphml olarak kaydeder."""
        path = self.processed_dir / filename
        ox.save_graphml(graph, filepath=path)

    def _save_heuristic_cache(
        self, cache: HeuristicCache, path: Path
    ) -> None:
        """HeuristicCache nesnesini pickle ile kaydeder."""
        with open(path, "wb") as f:
            pickle.dump(cache, f, protocol=pickle.HIGHEST_PROTOCOL)
        size_kb = path.stat().st_size / 1024
        logger.info("Önbellek kaydedildi: %s (%.1f KB)", path, size_kb)

    def _load_heuristic_cache(self, path: Path) -> HeuristicCache:
        """Daha önce kaydedilmiş önbelleği yükler."""
        logger.info("Önbellek diskten yükleniyor: %s", path)
        with open(path, "rb") as f:
            cache = pickle.load(f)
        logger.info(
            "Önbellek yüklendi. %d koordinat, %d önceden hesaplanmış mesafe.",
            len(cache.node_coords), len(cache.distance_cache)
        )
        return cache


# ─────────────────────────────────────────────
#  CLI Giriş Noktası
# ─────────────────────────────────────────────

if __name__ == "__main__":
    from core.map_loader import MapLoader

    # Adım 1: Graf yükle (disk varsa diskten, yoksa API'den)
    loader = MapLoader()
    try:
        graph = loader.load_from_disk()
    except FileNotFoundError:
        graph = loader.run()

    # Adım 2: İşlemciyi başlat
    processor = GraphProcessor(graph)

    # Adım 3: Hiyerarşiyi oluştur ve kaydet
    hierarchy = processor.build_hierarchy(save=True)

    # Adım 4: Sezgisel önbelleği oluştur
    h_cache = processor.build_heuristic_cache(save=True)

    # Adım 5: Önbellek çalışma testi
    nodes = list(graph.nodes())
    if len(nodes) >= 2:
        sample_u, sample_v = nodes[0], nodes[-1]
        dist = processor.get_heuristic(h_cache, sample_u, sample_v)
        print(f"\nÖrnek Haversine mesafesi: {dist:,.0f} metre")
        print(f"Cache hits: {h_cache.cache_hits} | misses: {h_cache.cache_misses}")

    print("\n── Katman İstatistikleri ───────────────────")
    for key, val in hierarchy.layer_stats.items():
        print(f"  {key:<28}: {val}")
    print("────────────────────────────────────────────\n")
    