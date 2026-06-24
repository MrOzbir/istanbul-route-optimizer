"""
visualization/map_renderer.py
==============================
İstanbul Yol Öneri Projesi — Folium Harita Görselleştirici

Sorumluluk:
    RingRoute ve PathResult nesnelerini etkileşimli Folium haritasına
    dönüştürür ve HTML olarak diske kaydeder.

Katmanlar:
    1. Ana rota çizgisi   — gradient renkli polyline
    2. Waypoint marker'ları — numaralı, renk kodlu
    3. Segment bilgileri  — her segmente tıklanabilir popup
    4. İstatistik kartı   — sağ üst köşe HTML overlay
    5. Opsiyonel: trafik yoğunluk ısı haritası (HeatMap)

Folium Notları:
    - Folium, Leaflet.js üzerine kurulu Python kütüphanesidir.
    - Tüm katmanlar LayerControl ile açılıp kapatılabilir.
    - Polyline koordinatları (lat, lon) sırasında verilmeli (lon, lat değil).
    - Büyük rotalarda (>5000 düğüm) SimplifyGeometry ile sadeleştirme yapılır.

Kullanım:
    from visualization.map_renderer import MapRenderer
    renderer = MapRenderer(graph)
    renderer.render_ring(ring_route, output_path="output/istanbul_ring.html")
"""

import logging
from pathlib import Path
from typing import Optional

import folium
from folium import plugins
import networkx as nx
import numpy as np

from core.ring_planner import RingRoute
from core.astar_engine import PathResult

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────
#  Renk Paleti
# ─────────────────────────────────────────────

# Segment renkleri (her waypoint çifti farklı renk)
SEGMENT_COLORS = [
    "#E63946",   # Kırmızı
    "#2196F3",   # Mavi
    "#4CAF50",   # Yeşil
    "#FF9800",   # Turuncu
    "#9C27B0",   # Mor
    "#00BCD4",   # Cyan
    "#F44336",   # Koyu kırmızı
    "#8BC34A",   # Açık yeşil
    "#3F51B5",   # İndigo
    "#FF5722",   # Derin turuncu
]

WAYPOINT_COLORS = {
    "start":   "#E63946",   # Başlangıç — kırmızı
    "middle":  "#2196F3",   # Ara nokta — mavi
    "end":     "#4CAF50",   # Bitiş (başa dönüş) — yeşil
}

# İstanbul merkezi
ISTANBUL_CENTER = [41.0082, 28.9784]


class MapRenderer:
    """
    Rota verilerini etkileşimli Folium haritasına dönüştürür.

    Parameters
    ----------
    graph         : nx.MultiDiGraph
        Düğüm koordinatları için referans graf.
    default_zoom  : int
        Başlangıç zoom seviyesi.
    tile_style    : str
        Harita arka plan stili.
        "CartoDB dark_matter" | "CartoDB positron" | "OpenStreetMap"
    simplify_threshold : int
        Bu değerin üzerindeki düğüm sayısında rota sadeleştirilir.
    """

    def __init__(
        self,
        graph:               nx.MultiDiGraph,
        default_zoom:        int = 11,
        tile_style:          str = "CartoDB dark_matter",
        simplify_threshold:  int = 2000,
    ) -> None:
        self.graph               = graph
        self.default_zoom        = default_zoom
        self.tile_style          = tile_style
        self.simplify_threshold  = simplify_threshold

        # Düğüm koordinat önbelleği
        self._coords: dict[int, tuple[float, float]] = {
            n: (d["y"], d["x"])
            for n, d in graph.nodes(data=True)
        }

        logger.info(
            "MapRenderer hazır. Tema: '%s' | %d düğüm koordinatı.",
            tile_style, len(self._coords),
        )

    # ──────────────────────────────────────────
    #  Ana Render Metotları
    # ──────────────────────────────────────────

    def render_ring(
        self,
        ring: RingRoute,
        output_path: Optional[Path] = None,
        show_heatmap: bool = False,
    ) -> folium.Map:
        """
        Çembersel rotayı tam katmanlı haritaya dönüştürür.

        Parameters
        ----------
        ring         : RingRoute  ring_planner çıktısı
        output_path  : Path | None  HTML kayıt yolu
        show_heatmap : bool  Düğüm yoğunluk ısı haritasını göster

        Returns
        -------
        folium.Map
        """
        logger.info("Harita render ediliyor...")

        # Harita başlat
        fmap = self._init_map(ring)

        # Katman 1: Rota segmentleri
        seg_group = folium.FeatureGroup(name="🛣️ Rota Segmentleri", show=True)
        for idx, (segment, waypoint_pair) in enumerate(
            zip(ring.segments, self._segment_pairs(ring.waypoints))
        ):
            self._add_segment(seg_group, segment, idx, waypoint_pair)
        seg_group.add_to(fmap)

        # Katman 2: Waypoint marker'ları
        wp_group = folium.FeatureGroup(name="📍 Waypoint'ler", show=True)
        self._add_waypoints(wp_group, ring.waypoints)
        wp_group.add_to(fmap)

        # Katman 3: İstatistik overlay
        self._add_stats_overlay(fmap, ring)

        # Katman 4: Opsiyonel ısı haritası
        if show_heatmap and ring.full_path:
            heat_group = folium.FeatureGroup(
                name="🌡️ Yoğunluk Haritası", show=False
            )
            self._add_heatmap(heat_group, ring.full_path)
            heat_group.add_to(fmap)

        # Katman kontrolü
        folium.LayerControl(collapsed=False).add_to(fmap)

        # Kaydet
        if output_path is None:
            output_path = OUTPUT_DIR / "istanbul_ring.html"
        fmap.save(str(output_path))
        logger.info("Harita kaydedildi: %s", output_path)

        return fmap

    def render_path(
        self,
        result: PathResult,
        source_name: str = "Başlangıç",
        target_name: str = "Bitiş",
        output_path: Optional[Path] = None,
    ) -> folium.Map:
        """
        Tek A* rotasını haritada gösterir.

        Hızlı test ve debug için kullanılır.

        Parameters
        ----------
        result      : PathResult
        source_name : str
        target_name : str
        output_path : Path | None

        Returns
        -------
        folium.Map
        """
        if not result.found or not result.path:
            logger.warning("Rota bulunamadı, boş harita döndürülüyor.")
            return self._init_map_empty()

        coords = self._path_to_coords(result.path)

        fmap = folium.Map(
            location=coords[len(coords) // 2],
            zoom_start=self.default_zoom,
            tiles=self.tile_style,
        )

        # Rota çizgisi
        folium.PolyLine(
            locations=coords,
            color=SEGMENT_COLORS[0],
            weight=4,
            opacity=0.85,
            tooltip=f"{result.total_length_m/1000:.2f} km | "
                    f"{result.total_time_s/60:.0f} dk",
        ).add_to(fmap)

        # Başlangıç / bitiş marker
        self._add_endpoint_marker(fmap, coords[0],  source_name, "green")
        self._add_endpoint_marker(fmap, coords[-1], target_name, "red")

        if output_path is None:
            output_path = OUTPUT_DIR / "istanbul_path.html"
        fmap.save(str(output_path))
        return fmap

    # ──────────────────────────────────────────
    #  Yardımcı Render Metotları
    # ──────────────────────────────────────────

    def _init_map(self, ring: RingRoute) -> folium.Map:
        """
        Haritayı rotanın orta noktasına göre başlatır.
        """
        if ring.full_path:
            coords  = self._path_to_coords(ring.full_path)
            center  = self._compute_center(coords)
        else:
            center  = ISTANBUL_CENTER

        return folium.Map(
            location=center,
            zoom_start=self.default_zoom,
            tiles=self.tile_style,
        )

    def _init_map_empty(self) -> folium.Map:
        """İstanbul merkezli boş harita."""
        return folium.Map(
            location=ISTANBUL_CENTER,
            zoom_start=self.default_zoom,
            tiles=self.tile_style,
        )

    def _add_segment(
        self,
        group: folium.FeatureGroup,
        segment: PathResult,
        idx: int,
        waypoint_pair: tuple[int, int],
    ) -> None:
        """
        Tek bir A* segmentini renkli polyline olarak ekler.

        Büyük segmentlerde Douglas-Peucker benzeri sadeleştirme yapılır:
        her nth düğüm alınır.

        Parameters
        ----------
        group        : FeatureGroup
        segment      : PathResult
        idx          : int  Segment indeksi (renk seçimi)
        waypoint_pair: (source_id, target_id)
        """
        if not segment.found or not segment.path:
            return

        path = segment.path

        # Sadeleştirme: çok fazla düğüm varsa seyrelt
        if len(path) > self.simplify_threshold:
            step = len(path) // self.simplify_threshold
            path = path[::step] + [path[-1]]   # Son düğümü koru

        coords = self._path_to_coords(path)
        color  = SEGMENT_COLORS[idx % len(SEGMENT_COLORS)]

        popup_html = self._segment_popup_html(segment, idx + 1)

        folium.PolyLine(
            locations=coords,
            color=color,
            weight=5,
            opacity=0.80,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=(
                f"Segment {idx+1} | "
                f"{segment.total_length_m/1000:.2f} km | "
                f"{segment.total_time_s/60:.0f} dk"
            ),
        ).add_to(group)

    def _add_waypoints(
        self,
        group: folium.FeatureGroup,
        waypoints: list[int],
    ) -> None:
        """
        Waypoint'leri numaralı dairesel marker olarak ekler.

        Başlangıç: kırmızı yıldız | Ara: mavi daire | Bitiş: yeşil işaret
        """
        n = len(waypoints)
        for idx, wp_node in enumerate(waypoints):
            if wp_node not in self._coords:
                continue
            lat, lon = self._coords[wp_node]

            # Marker tipi
            if idx == 0:
                icon_color = "red"
                icon_name  = "star"
                label      = f"🏁 Başlangıç (WP {idx+1})"
            elif idx == n - 1:
                icon_color = "green"
                icon_name  = "flag"
                label      = f"🏴 Son (WP {idx+1})"
            else:
                icon_color = "blue"
                icon_name  = "map-marker"
                label      = f"📍 WP {idx+1}"

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(
                    f"<b>{label}</b><br>OSM ID: {wp_node}<br>"
                    f"Koordinat: {lat:.5f}, {lon:.5f}",
                    max_width=200,
                ),
                tooltip=label,
                icon=folium.Icon(color=icon_color, icon=icon_name, prefix="fa"),
            ).add_to(group)

    def _add_stats_overlay(
        self,
        fmap: folium.Map,
        ring: RingRoute,
    ) -> None:
        """
        Sağ üst köşeye rota istatistik kartı ekler.

        Folium'un custom HTML ekleme yöntemi kullanılır.
        """
        found_segments = sum(1 for s in ring.segments if s.found)
        total_segments = len(ring.segments)

        html = f"""
        <div style="
            position: fixed;
            top: 10px; right: 10px;
            z-index: 9999;
            background: rgba(15, 20, 30, 0.90);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 10px;
            padding: 14px 18px;
            font-family: 'Segoe UI', sans-serif;
            color: #f0f0f0;
            font-size: 13px;
            min-width: 220px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        ">
            <div style="font-size:15px; font-weight:700;
                        margin-bottom:10px; color:#64b5f6;">
                🗺️ İstanbul Ring Rotası
            </div>
            <table style="width:100%; border-collapse:collapse;">
                <tr>
                    <td style="padding:3px 0; color:#aaa;">Toplam mesafe</td>
                    <td style="text-align:right; font-weight:600;">
                        {ring.total_length_m/1000:.2f} km
                    </td>
                </tr>
                <tr>
                    <td style="padding:3px 0; color:#aaa;">Tahmini süre</td>
                    <td style="text-align:right; font-weight:600;">
                        {ring.total_time_s/60:.0f} dakika
                    </td>
                </tr>
                <tr>
                    <td style="padding:3px 0; color:#aaa;">Waypoint sayısı</td>
                    <td style="text-align:right; font-weight:600;">
                        {len(ring.waypoints)}
                    </td>
                </tr>
                <tr>
                    <td style="padding:3px 0; color:#aaa;">Başarılı segment</td>
                    <td style="text-align:right; font-weight:600;">
                        {found_segments}/{total_segments}
                    </td>
                </tr>
                <tr>
                    <td style="padding:3px 0; color:#aaa;">Planlama süresi</td>
                    <td style="text-align:right; font-weight:600;">
                        {ring.elapsed_ms:.0f} ms
                    </td>
                </tr>
                <tr>
                    <td style="padding:3px 0; color:#aaa;">Toplam düğüm</td>
                    <td style="text-align:right; font-weight:600;">
                        {len(ring.full_path):,}
                    </td>
                </tr>
            </table>
        </div>
        """

        fmap.get_root().html.add_child(folium.Element(html))

    def _add_heatmap(
        self,
        group: folium.FeatureGroup,
        path: list[int],
    ) -> None:
        """
        Rota düğümlerinden ısı haritası oluşturur.
        Yoğun kullanılan kavşakları gösterir.
        """
        heat_data = []
        for node in path:
            if node in self._coords:
                lat, lon = self._coords[node]
                heat_data.append([lat, lon])

        if heat_data:
            plugins.HeatMap(
                heat_data,
                radius=12,
                blur=15,
                min_opacity=0.4,
            ).add_to(group)

    def _add_endpoint_marker(
        self,
        fmap: folium.Map,
        coord: list[float],
        label: str,
        color: str,
    ) -> None:
        """Tek nokta marker ekler."""
        folium.Marker(
            location=coord,
            popup=label,
            icon=folium.Icon(color=color, icon="map-marker", prefix="fa"),
        ).add_to(fmap)

    # ──────────────────────────────────────────
    #  Geometri Yardımcıları
    # ──────────────────────────────────────────

    def _path_to_coords(self, path: list[int]) -> list[list[float]]:
        """
        Düğüm ID listesini [lat, lon] listesine dönüştürür.

        Koordinatı olmayan düğümler atlanır.
        """
        coords = []
        for node in path:
            if node in self._coords:
                lat, lon = self._coords[node]
                coords.append([lat, lon])
        return coords

    def _compute_center(
        self,
        coords: list[list[float]],
    ) -> list[float]:
        """Koordinat listesinin ağırlık merkezini hesaplar."""
        if not coords:
            return ISTANBUL_CENTER
        lats = [c[0] for c in coords]
        lons = [c[1] for c in coords]
        return [np.mean(lats), np.mean(lons)]

    def _segment_pairs(
        self,
        waypoints: list[int],
    ) -> list[tuple[int, int]]:
        """Waypoint listesinden ardışık çiftler üretir (kapalı)."""
        n = len(waypoints)
        return [(waypoints[i], waypoints[(i + 1) % n]) for i in range(n)]

    def _segment_popup_html(
        self,
        segment: PathResult,
        segment_num: int,
    ) -> str:
        """Segment popup içeriğini HTML olarak üretir."""
        return f"""
        <div style="font-family: 'Segoe UI', sans-serif; font-size:13px;">
            <b style="color:#1976D2;">Segment {segment_num}</b><br>
            <hr style="margin:4px 0; border-color:#ddd;">
            <b>Mesafe:</b> {segment.total_length_m/1000:.2f} km<br>
            <b>Süre:</b> {segment.total_time_s/60:.1f} dakika<br>
            <b>Katman:</b> {segment.layer_used}<br>
            <b>Düğüm sayısı:</b> {len(segment.path)}<br>
            <b>Açılan düğüm:</b> {segment.nodes_explored}<br>
            <b>Algoritma:</b> {segment.elapsed_ms:.1f} ms
        </div>
        """