"""
core/map_loader.py
==================
İstanbul Yol Öneri Projesi — Harita Verisi Hazırlama Modülü

Sorumluluk:
    OSMnx aracılığıyla İstanbul'un ana arterlerini (motorway, trunk,
    primary, secondary) OpenStreetMap'ten çekerek NetworkX MultiDiGraph'a
    dönüştürür ve .graphml formatında diske kaydeder.

Kullanım:
    python -m core.map_loader           # Doğrudan çalıştırma
    from core.map_loader import MapLoader  # Modül olarak import
"""

import logging
import time
from pathlib import Path

import networkx as nx
import osmnx as ox

# ─────────────────────────────────────────────
#  Loglama Yapılandırması
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
#  Sabitler
# ─────────────────────────────────────────────

# Proje kök dizinine göre veri klasörü
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

# İstanbul için kullanılan OSM yol hiyerarşileri
# Sadece ana arterler alınır; residential/unclassified hariç tutulur.
ISTANBUL_ROAD_FILTERS = [
    "motorway",       # Otoyol (O-1, O-2, O-3...)
    "motorway_link",  # Otoyol bağlantı rampaları
    "trunk",          # Ana devlet yolları (E-5, TEM vb.)
    "trunk_link",
    "primary",        # İl yolları, büyük caddeler
    "primary_link",
    "secondary",      # İlçe bağlantı yolları
    "secondary_link",
]

# OSMnx custom_filter string'i oluştur
_FILTER_STRING = (
    '["highway"~"'
    + "|".join(ISTANBUL_ROAD_FILTERS)
    + '"]'
)


class MapLoader:
    """
    İstanbul harita verisini OSMnx ile çeken ve işleyen sınıf.

    Parameters
    ----------
    city_name : str
       OSM'e gönderilecek şehir sorgusu.
       Varsayılan: "Istanbul, Turkey"
    output_dir : Path
       .graphml dosyasının kaydedileceği dizin.
    network_type : str
       OSMnx network tipi. Ana arterler için "drive" kullanılır.
    use_cache : bool
       OSMnx HTTP cache'ini etkinleştirir (tekrar çekimlerde süre kazandırır).
    """

    def __init__(
        self,
        city_name: str = "Istanbul, Turkey",
        output_dir: Path = DATA_DIR,
        network_type: str = "drive",
        use_cache: bool = True,
    ) -> None:
        self.city_name = city_name
        self.output_dir = Path(output_dir)
        self.network_type = network_type

        # Dizin yoksa oluştur
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # OSMnx global ayarları
        ox.settings.use_cache = use_cache
        ox.settings.log_console = False  # OSMnx kendi logunu bastırıyoruz
        ox.settings.timeout = 300        # İstanbul büyük → uzun timeout

        self.graph: nx.MultiDiGraph | None = None
        logger.info("MapLoader başlatıldı. Şehir: %s", self.city_name)

    # ──────────────────────────────────────────
    #  Ana İş Akışı
    # ──────────────────────────────────────────

    def run(self) -> nx.MultiDiGraph:
        """
        Tam iş akışını çalıştırır:
        1. Grafu OSMnx ile çek
        2. Graf özelliklerini zenginleştir
        3. .graphml olarak kaydet

        Returns
        -------
        nx.MultiDiGraph
            İşlenmiş NetworkX grafu.
        """
        logger.info("=== Harita Hazırlama Başlıyor ===")
        t0 = time.perf_counter()

        self.graph = self._fetch_graph()
        self.graph = self._enrich_graph(self.graph)
        self._save_graph(self.graph)

        elapsed = time.perf_counter() - t0
        logger.info("=== Tamamlandı (%.1f saniye) ===", elapsed)
        return self.graph

    # ──────────────────────────────────────────
    #  1. Graf Çekme
    # ──────────────────────────────────────────

    def _fetch_graph(self) -> nx.MultiDiGraph:
        """
        OSMnx'i kullanarak İstanbul ana arterlerini Overpass API'den çeker.

        Strateji:
            - custom_filter ile yalnızca üst düzey yol tipleri alınır.
            - simplify=True: Gereksiz ara düğümler kaldırılır → daha az bellek.
            - retain_all=False: Bağlantısız parçalar (adalar, yalnız yollar) atılır.

        Returns
        -------
        nx.MultiDiGraph
        """
        logger.info("OSMnx'ten graf çekiliyor: '%s'", self.city_name)
        logger.info("Yol filtresi: %s", _FILTER_STRING)

        graph = ox.graph_from_place(
            query=self.city_name,
            network_type=self.network_type,
            custom_filter=_FILTER_STRING,
            simplify=True,       # Topolojiyi basitleştir
            retain_all=False,    # Sadece ana bileşeni tut
        )

        node_count = graph.number_of_nodes()
        edge_count = graph.number_of_edges()
        logger.info(
            "Graf çekildi → %d düğüm, %d kenar", node_count, edge_count
        )
        return graph

    # ──────────────────────────────────────────
    #  2. Graf Zenginleştirme
    # ──────────────────────────────────────────

    def _enrich_graph(self, graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
        """
        A* algoritması ve sinir ağı için gerekli özellikleri grafa ekler.

        Eklenen özellikler:
            - `length`    : Kenar uzunluğu (metre) — OSMnx zaten ekler, kontrol edilir.
            - `speed_kph` : Hız limiti (km/s). Eksik değerler yol tipine göre doldurulur.
            - `travel_time`: Kenar geçiş süresi (saniye) = length / speed_ms.
            - `highway_rank`: Yol hiyerarşisi (motorway=5 … secondary=2).

        Parameters
        ----------
        graph : nx.MultiDiGraph

        Returns
        -------
        nx.MultiDiGraph
        """
        logger.info("Graf özellikleri zenginleştiriliyor...")

        # OSMnx'in yerleşik hız/süre hesaplama fonksiyonu
        # Eksik maxspeed değerlerini yol tipine göre tahmin eder
        graph = ox.add_edge_speeds(graph)
        graph = ox.add_edge_travel_times(graph)

        # Yol tipi → hiyerarşi skoru eşlemesi (A* için)
        highway_rank_map: dict[str, int] = {
            "motorway":      5,
            "motorway_link": 4,
            "trunk":         4,
            "trunk_link":    3,
            "primary":       3,
            "primary_link":  2,
            "secondary":     2,
            "secondary_link": 1,
        }

        enriched_edges = 0
        for _, _, data in graph.edges(data=True):
            hw = data.get("highway", "secondary")
            # highway bazen liste olabilir (OSM multi-tag)
            if isinstance(hw, list):
                hw = hw[0]
            data["highway_rank"] = highway_rank_map.get(hw, 1)
            enriched_edges += 1

        logger.info("%d kenara highway_rank eklendi.", enriched_edges)
        return graph

    # ──────────────────────────────────────────
    #  3. Diske Kaydetme
    # ──────────────────────────────────────────

    def _save_graph(self, graph: nx.MultiDiGraph) -> Path:
        """
        Grafu .graphml formatında kaydeder.

        .graphml seçilme nedeni:
            - NetworkX natif desteği → tam özellik (attribute) korunumu
            - Taşınabilir XML formatı; QGIS, Gephi gibi araçlarla açılabilir
            - Binary formatların aksine insan tarafından okunabilir

        Parameters
        ----------
        graph : nx.MultiDiGraph

        Returns
        -------
        Path
            Kaydedilen dosyanın tam yolu.
        """
        output_path = self.output_dir / "istanbul_main_arteries.graphml"
        logger.info("Graf kaydediliyor: %s", output_path)

        ox.save_graphml(graph, filepath=output_path)

        file_size_mb = output_path.stat().st_size / (1024 ** 2)
        logger.info("Kayıt tamamlandı. Dosya boyutu: %.2f MB", file_size_mb)
        return output_path

    # ──────────────────────────────────────────
    #  Yardımcı Metotlar
    # ──────────────────────────────────────────

    def load_from_disk(self, filepath: Path | None = None) -> nx.MultiDiGraph:
        """
        Daha önce kaydedilmiş .graphml dosyasını yükler.

        API'ye tekrar istek atmaktan kaçınmak için kullanılır.

        Parameters
        ----------
        filepath : Path, optional
            Dosya yolu. None ise varsayılan konum kullanılır.

        Returns
        -------
        nx.MultiDiGraph
        """
        if filepath is None:
            filepath = self.output_dir / "istanbul_main_arteries.graphml"

        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(
                f"Graf dosyası bulunamadı: {filepath}\n"
                "Önce MapLoader().run() ile veriyi çekin."
            )

        logger.info("Graf diskten yükleniyor: %s", filepath)
        self.graph = ox.load_graphml(filepath)
        logger.info(
            "Yüklendi → %d düğüm, %d kenar",
            self.graph.number_of_nodes(),
            self.graph.number_of_edges(),
        )
        return self.graph

    def get_graph_stats(self) -> dict:
        """
        Yüklü grafın temel istatistiklerini döndürür.

        Returns
        -------
        dict
            node_count, edge_count, avg_degree, total_length_km
        """
        if self.graph is None:
            raise RuntimeError("Graf henüz yüklenmedi. run() veya load_from_disk() çağırın.")

        total_length_m = sum(
            data.get("length", 0)
            for _, _, data in self.graph.edges(data=True)
        )

        return {
            "node_count":      self.graph.number_of_nodes(),
            "edge_count":      self.graph.number_of_edges(),
            "avg_degree":      round(
                self.graph.number_of_edges() / max(self.graph.number_of_nodes(), 1), 2
            ),
            "total_length_km": round(total_length_m / 1000, 1),
        }


# ─────────────────────────────────────────────
#  CLI Giriş Noktası
# ─────────────────────────────────────────────

if __name__ == "__main__":
    loader = MapLoader()

    # İlk çalıştırmada veriyi OSMnx'ten çek ve kaydet
    graph = loader.run()

    # İstatistikleri yazdır
    stats = loader.get_graph_stats()
    print("\n── Graf İstatistikleri ──────────────────")
    for key, value in stats.items():
        print(f"  {key:<22}: {value}")
    print("─────────────────────────────────────────\n")
