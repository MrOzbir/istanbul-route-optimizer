"""
core/traffic_manager.py
========================
İstanbul Yol Öneri Projesi — Trafik Yönetim ve Simülasyon Motoru

Sorumluluk:
    İstanbul'un otoyol, ana arter ve köprülerindeki trafik yoğunluğunu simüle eder.
    TomTom Traffic Flow API entegrasyonu sunarak canlı veriyi de destekler.
    Rotalama motorunun kenar maliyetlerini (travel_time) dinamik güncellemesini sağlar.
"""

import os
import random
import logging
import math
import time
from datetime import datetime
import yaml
import requests
import networkx as nx

logger = logging.getLogger(__name__)

class TrafficManager:
    """
    Graf üzerindeki kenarlar için trafik yoğunluğunu yönetir ve çarpanlar üretir.
    """

    def __init__(self, graph: nx.MultiDiGraph, config_path: str = "configs/settings.yaml") -> None:
        self.graph = graph
        self.config_path = config_path
        self.tomtom_key = None
        self.incidents = []  # [{ "u": u, "v": v, "type": "accident"|"roadwork", "multiplier": 8.0, "name": "Kaza" }]
        self.edge_multipliers = {}  # { (u, v): multiplier }
        self.last_update = 0
        self.update_interval = 60  # Saniye cinsinden güncelleme aralığı

        self.load_config()
        self.update_traffic()

    def load_config(self) -> None:
        """Yapılandırma dosyasından API anahtarını yükler."""
        # İlk olarak ortam değişkenine bak
        self.tomtom_key = os.environ.get("TOMTOM_API_KEY")
        
        # Ortam değişkeni yoksa settings.yaml dosyasına bak
        if not self.tomtom_key and os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                    if config and isinstance(config, dict):
                        self.tomtom_key = config.get("tomtom_api_key")
            except Exception as e:
                logger.warning("Ayarlar dosyası yüklenemedi: %s", str(e))
        
        if self.tomtom_key:
            logger.info("TomTom Traffic API anahtarı yüklendi (Canlı Mod Aktif).")
        else:
            logger.info("TomTom API anahtarı bulunamadı. İstanbul Trafik Simülasyonu devrede.")

    def update_traffic(self) -> None:
        """Trafik durumunu günceller. Canlı API varsa çeker, yoksa simülasyonu yeniler."""
        current_time = time.time()
        # Çok sık güncellemeyi engellemek için önbellek süresi kontrolü
        if current_time - self.last_update < 5:
            return

        self.edge_multipliers.clear()
        
        # 1. Temel Trafik Simülasyonunu Hesapla (Saatlik Yoğunluk)
        self._simulate_base_traffic()

        # 2. Rastgele Kaza/Yol Çalışması Olayları Üret (Simülasyona Zenginlik Katma)
        self._generate_simulated_incidents()

        # 3. TomTom API ile Canlı Akış Verisi Çek (API Anahtarı varsa)
        if self.tomtom_key:
            self._fetch_live_tomtom_traffic()

        self.last_update = current_time
        logger.info("Trafik çarpanları güncellendi. Aktif kaza/olay sayısı: %d", len(self.incidents))

    def _simulate_base_traffic(self) -> None:
        """İstanbul için saatlik ve yönlü baz trafik çarpanlarını simüle eder."""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        time_float = hour + minute / 60.0

        # İstanbul trafik zirve saatleri çarpan profili
        # Sabah Zirve (07:30 - 09:30)
        # Akşam Zirve (17:30 - 20:00)
        # Öğle yoğunluğu (12:00 - 14:00)
        
        rush_hour_factor = 1.0
        if 7.5 <= time_float <= 9.5:
            # Sabah zirve saati (en yüksek yoğunluk: 08:30)
            dist_to_peak = abs(time_float - 8.5)
            rush_hour_factor = 3.5 - dist_to_peak * 2.0  # max 3.5
        elif 17.5 <= time_float <= 20.0:
            # Akşam zirve saati (en yüksek yoğunluk: 18:30)
            dist_to_peak = abs(time_float - 18.5)
            rush_hour_factor = 4.2 - dist_to_peak * 1.8  # max 4.2
        elif 12.0 <= time_float <= 14.0:
            # Öğle yoğunluğu
            rush_hour_factor = 1.6
        elif 20.0 < time_float <= 23.0 or 6.0 <= time_float < 7.5:
            # Ara saatler
            rush_hour_factor = 1.3
        else:
            # Gece akıcı
            rush_hour_factor = 1.0

        # Her kenar için niteliğine göre yoğunluk çarpanı ata
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            hw = data.get("highway", "unclassified")
            if isinstance(hw, list):
                hw = hw[0]

            # Varsayılan çarpan
            multiplier = 1.0

            # Yol tipine göre hassasiyet
            if hw in ("motorway", "motorway_link", "trunk", "trunk_link"):
                # Otoyollar ve TEM/E-5 ana arterleri yoğunluktan en çok etkilenenlerdir
                multiplier = 1.0 + (rush_hour_factor - 1.0) * 0.9
            elif hw in ("primary", "primary_link"):
                multiplier = 1.0 + (rush_hour_factor - 1.0) * 0.7
            elif hw in ("secondary", "secondary_link"):
                multiplier = 1.0 + (rush_hour_factor - 1.0) * 0.5
            else:
                # Ara sokaklar ve yerel yollar daha az etkilenir
                multiplier = 1.0 + (rush_hour_factor - 1.0) * 0.2

            # Boğaziçi Köprüleri ve Tüneller Kontrolü (Asya ➔ Avrupa boylamı geçişi)
            # Avrupa boylamı ~ < 29.01, Asya boylamı ~ > 29.01.
            node_u = self.graph.nodes[u]
            node_v = self.graph.nodes[v]
            u_x, v_x = node_u.get("x", 29.0), node_v.get("x", 29.0)

            is_crossing = (u_x < 29.01 and v_x > 29.01) or (u_x > 29.01 and v_x < 29.01)
            
            if is_crossing:
                # Köprüler ve Avrasya tüneli her zaman daha yoğundur
                bridge_multiplier = 1.5
                if 7.5 <= time_float <= 9.5:
                    # Sabah: Asya'dan Avrupa'ya gidiş çok kilit (u_x > v_x, yani doğudan batıya)
                    if u_x > v_x:
                        bridge_multiplier = 4.8
                    else:
                        bridge_multiplier = 2.2
                elif 17.5 <= time_float <= 20.0:
                    # Akşam: Avrupa'dan Asya'ya dönüş kilit (u_x < v_x, yani batıdan doğuya)
                    if u_x < v_x:
                        bridge_multiplier = 5.2
                    else:
                        bridge_multiplier = 2.4
                else:
                    bridge_multiplier = 1.8 * rush_hour_factor

                multiplier = max(multiplier, bridge_multiplier)

            # Çarpanı kaydet (rastgele hafif dalgalanma ekleyerek doğallık katalım)
            noise = random.uniform(0.95, 1.05)
            self.edge_multipliers[(u, v)] = max(1.0, multiplier * noise)

    def _generate_simulated_incidents(self) -> None:
        """
        Rastgele kazalar veya yol çalışmaları üreterek trafiği bloke eder.
        Bu sayede A* alternatif yolları (detour) tercih etmek zorunda kalır.
        """
        # Her güncellemede eski olayları %30 ihtimalle temizle veya yenile
        if self.incidents and random.random() < 0.3:
            self.incidents.clear()

        # Olay yoksa 2-4 adet yeni olay oluştur
        if not self.incidents:
            # Yoğun yollardan (motorway, trunk, primary) rastgele kenarlar seç
            candidate_edges = []
            for u, v, key, data in self.graph.edges(keys=True, data=True):
                hw = data.get("highway", "")
                if isinstance(hw, list):
                    hw = hw[0]
                if hw in ("motorway", "trunk", "primary"):
                    candidate_edges.append((u, v))

            if candidate_edges:
                num_incidents = random.randint(2, 4)
                chosen_edges = random.sample(candidate_edges, min(num_incidents, len(candidate_edges)))
                
                for idx, (u, v) in enumerate(chosen_edges):
                    incident_type = random.choice(["accident", "roadwork"])
                    multiplier = random.uniform(5.5, 8.5) if incident_type == "accident" else random.uniform(4.0, 6.0)
                    name = "Trafik Kazası 💥" if incident_type == "accident" else "Yol Çalışması 🚧"
                    
                    self.incidents.append({
                        "id": idx + 1,
                        "u": u,
                        "v": v,
                        "type": incident_type,
                        "multiplier": multiplier,
                        "name": name
                    })

        # Kaza ve olayların etrafındaki yollara (komşularına) gecikme yayılımı uygula
        for inc in self.incidents:
            u, v = inc["u"], inc["v"]
            # Olayın gerçekleştiği ana kenara yüksek çarpan ata
            self.edge_multipliers[(u, v)] = inc["multiplier"]
            
            # Geriye doğru tıkanıklık yayılımı (incident'a gelen kenarları da etkile)
            for pred in self.graph.predecessors(u):
                self.edge_multipliers[(pred, u)] = max(
                    self.edge_multipliers.get((pred, u), 1.0),
                    inc["multiplier"] * 0.6  # %60 oranında tıkanıklık geriye yansır
                )

    def _fetch_live_tomtom_traffic(self) -> None:
        """
        TomTom Traffic Flow API'sini kullanarak İstanbul'un önemli merkezleri
        veya haritadaki aktif koordinatlar için canlı akış çarpanlarını çeker.
        """
        # Not: Tüm graf kenarlarını API ile sorgulamak limitleri aşar.
        # Bu yüzden, İstanbul'daki 5 kritik referans koordinatını sorgulayarak o bölgelere yakın 
        # otoyol/primary kenarlarının çarpanlarını canlı veriye göre güncelliyoruz.
        reference_points = {
            "15_Martyrs_Bridge": (41.0475, 29.0345),  # 15 Temmuz Şehitler Köprüsü
            "FSM_Bridge": (41.0911, 29.0619),         # Fatih Sultan Mehmet Köprüsü
            "Mecidiyekoy": (41.0638, 28.9922),        # Mecidiyeköy E-5 Katılımı
            "Kadikoy_E5": (40.9995, 29.0435),         # Kadıköy E-5 Katılımı
            "Halic_Bridge": (41.0425, 28.9405)        # Haliç Köprüsü E-5
        }

        headers = {"Accept": "application/json"}
        
        for name, coords in reference_points.items():
            lat, lon = coords
            url = f"https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json?point={lat},{lon}&key={self.tomtom_key}"
            try:
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    flow_data = data.get("flowSegmentData", {})
                    current_speed = flow_data.get("currentSpeed", 1)
                    free_flow_speed = flow_data.get("freeFlowSpeed", 1)
                    
                    if current_speed > 0:
                        # Hız düşüş oranını çarpan olarak belirle
                        live_multiplier = max(1.0, free_flow_speed / current_speed)
                        logger.debug("TomTom Live Traffic [%s]: Speed %d/%d km/h -> Multiplier %.2f", 
                                     name, current_speed, free_flow_speed, live_multiplier)
                        
                        # Bu referans noktasına en yakın otoyol/ana arter kenarlarını bulup çarpanı ata
                        # 200 metre çapındaki kenarları güncelle
                        for u, v, key, edge_data in self.graph.edges(keys=True, data=True):
                            node_u = self.graph.nodes[u]
                            # Yakınlık kontrolü (basit box kontrolü)
                            dist = self._haversine(lat, lon, node_u["y"], node_u["x"])
                            if dist < 500: # 500 metre yarıçap
                                hw = edge_data.get("highway", "")
                                if isinstance(hw, list):
                                    hw = hw[0]
                                if hw in ("motorway", "trunk", "primary"):
                                    self.edge_multipliers[(u, v)] = live_multiplier
            except Exception as e:
                logger.warning("TomTom API sorgusu başarısız [%s]: %s", name, str(e))

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """İki nokta arasındaki Haversine mesafesini metre olarak bulur."""
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
        return 6371000.0 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    def get_edge_multiplier(self, u: int, v: int, edge_data: dict = None) -> float:
        """Rotalama sırasında belirli bir kenar için geçerli trafik çarpanını döner."""
        return self.edge_multipliers.get((u, v), 1.0)

    def get_traffic_overlay_data(self) -> list:
        """
        Harita üzerinde çizdirilmek üzere önemli yolların koordinatlarını,
        hız çarpanlarını ve trafik rengini döner.
        """
        overlay_segments = []
        
        # Sadece motorway, trunk ve primary yolları harita katmanında göster (aşırı yükü önlemek için)
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            hw = data.get("highway", "")
            if isinstance(hw, list):
                hw = hw[0]
                
            if hw not in ("motorway", "trunk", "primary"):
                continue

            multiplier = self.get_edge_multiplier(u, v, data)
            
            # Yoğunluk rengi belirleme
            if multiplier >= 4.0:
                status = "blocked"  # Koyu Kırmızı (Kaza veya kilit köprü)
                color = "#7f0000"
            elif multiplier >= 2.5:
                status = "heavy"    # Kırmızı
                color = "#dc2626"
            elif multiplier >= 1.5:
                status = "moderate" # Turuncu / Sarı
                color = "#f97316"
            else:
                status = "free"     # Yeşil
                color = "#10b981"

            # Kenar koordinatlarını topla (geometry varsa al yoksa düğümlerden çıkar)
            coords = []
            if "geometry" in data:
                # Shapely LineString objesi coordinates'larını [lat, lon] yap
                coords = [[lat, lon] for lon, lat in data["geometry"].coords]
            else:
                node_u = self.graph.nodes[u]
                node_v = self.graph.nodes[v]
                coords = [
                    [node_u["y"], node_u["x"]],
                    [node_v["y"], node_v["x"]]
                ]

            overlay_segments.append({
                "u": int(u),
                "v": int(v),
                "highway": hw,
                "multiplier": float(multiplier),
                "status": status,
                "color": color,
                "coords": coords
            })

        return overlay_segments

    def get_active_incidents_coords(self) -> list:
        """Aktif olayların (kaza/çalışma) harita marker'ları için koordinatlarını döner."""
        incident_markers = []
        for inc in self.incidents:
            u, v = inc["u"], inc["v"]
            node_u = self.graph.nodes[u]
            incident_markers.append({
                "id": inc["id"],
                "lat": node_u["y"],
                "lng": node_u["x"],
                "type": inc["type"],
                "name": inc["name"],
                "multiplier": float(inc["multiplier"])
            })
        return incident_markers
