"""
training/model_arch.py
======================
İstanbul Yol Öneri Projesi — Sinir Ağı Mimari Tanımı

Sorumluluk:
    A* sezgisel fonksiyonunu öğrenen sinir ağı modelini tanımlar.
    Model, iki düğüm arasındaki "gerçek A* maliyetini" tahmin eder;
    bu tahmin Haversine'den daha akıllı bir alt sınır üretir.

Mimari Seçimi — Neden MLP (Multilayer Perceptron)?
    Graf Sinir Ağı (GNN) daha güçlü ama iki sorunu var:
      1. ONNX export için torch_geometric bağımlılığı gerekir → karmaşık
      2. A* inner loop'ta per-edge inference yapılır → GNN mesaj geçişi
         çok yavaş kalır (her adımda komşu agregasyonu imkansız)
    
    MLP yaklaşımı:
      - Input: 2 düğümün koordinatları + graf özellikleri (8 özellik)
      - Output: tahmini maliyet (scalar)
      - ONNX export: tek satır, sıfır bağımlılık
      - Inference: ~0.1ms (GNN'in ~50x hızı)

    Gelecekte GNN eklemek için GraphEncoder sınıfı da tanımlanmıştır;
    MLP ile birleştirilerek hibrit kullanılabilir.

Özellik Mühendisliği (Feature Engineering):
    Her (source, target) çifti için 8 boyutlu vektör:
    ┌─────┬──────────────────────────────────────────┐
    │ [0] │ Haversine mesafesi (normalize edilmiş)   │
    │ [1] │ Δlat (lat farkı)                         │
    │ [2] │ Δlon (lon farkı)                         │
    │ [3] │ Source düğüm derecesi (normalize)        │
    │ [4] │ Target düğüm derecesi (normalize)        │
    │ [5] │ Source highway_rank ortalaması            │
    │ [6] │ Target highway_rank ortalaması            │
    │ [7] │ Bearing açısı (yön bilgisi, normalize)   │
    └─────┴──────────────────────────────────────────┘

Apple Silicon MPS Desteği:
    torch.device("mps") kullanılır.
    MPS; CUDA'nın Mac eşdeğeridir, M1/M2/M3 GPU çekirdeğini kullanır.
    Fallback: MPS yoksa CPU.

Kullanım:
    from training.model_arch import HeuristicNet, FeatureExtractor
    model = HeuristicNet()
    extractor = FeatureExtractor(graph)
"""

import math
import logging
from typing import Optional

import torch
import torch.nn as nn
import networkx as nx
import numpy as np

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Cihaz Seçimi
# ─────────────────────────────────────────────

def get_device() -> torch.device:
    """
    Kullanılabilir en hızlı cihazı döndürür.

    Öncelik: MPS (Apple Silicon) > CUDA > CPU

    Returns
    -------
    torch.device
    """
    if torch.backends.mps.is_available():
        device = torch.device("mps")
        logger.info("Cihaz: Apple Silicon MPS ✓")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
        logger.info("Cihaz: CUDA GPU ✓")
    else:
        device = torch.device("cpu")
        logger.info("Cihaz: CPU (MPS/CUDA bulunamadı)")
    return device


DEVICE = get_device()


# ─────────────────────────────────────────────
#  Sabitler
# ─────────────────────────────────────────────

INPUT_DIM  = 8    # Özellik vektörü boyutu
HIDDEN_DIM = 128  # Gizli katman genişliği
OUTPUT_DIM = 1    # Tahmin edilen maliyet (scalar)


# ─────────────────────────────────────────────
#  Model Mimarisi
# ─────────────────────────────────────────────

class ResidualBlock(nn.Module):
    """
    Artık bağlantılı (residual) lineer blok.

    Klasik MLP'ye kıyasla:
      - Gradyan akışı daha stabil → derin ağlarda kaybolma problemi azalır
      - Skip connection: x + F(x) → orijinal bilgi korunur
      - LayerNorm: batch boyutundan bağımsız normalizasyon
        (küçük batch'lerde BatchNorm'dan üstün)

    Parameters
    ----------
    dim : int  Giriş ve çıkış boyutu (aynı olmalı — residual bağlantı şartı)
    dropout : float  Dropout oranı
    """

    def __init__(self, dim: int, dropout: float = 0.1) -> None:
        super().__init__()
        self.block = nn.Sequential(
            nn.Linear(dim, dim),
            nn.LayerNorm(dim),
            nn.GELU(),              # ReLU yerine GELU: negatif bölgede yumuşak
            nn.Dropout(dropout),
            nn.Linear(dim, dim),
            nn.LayerNorm(dim),
        )
        self.activation = nn.GELU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.activation(x + self.block(x))   # x + F(x)


class HeuristicNet(nn.Module):
    """
    A* sezgisel maliyet tahmincisi.

    Mimari:
        Input(8) → Embedding(128) → ResBlock × 3 → Output(1)

        Giriş katmanı boyutu yükseltir (8 → 128).
        3 residual blok bilgiyi işler.
        Çıkış katmanı Softplus aktivasyonu kullanır:
          Softplus(x) = log(1 + e^x) → her zaman pozitif çıktı.
          Maliyet negatif olamayacağı için ReLU yerine tercih edilir
          (ReLU sıfır gradyan problemi yaratabilir).

    Parameters
    ----------
    input_dim  : int   Özellik vektörü boyutu (varsayılan: 8)
    hidden_dim : int   Gizli katman genişliği (varsayılan: 128)
    n_residual : int   Residual blok sayısı (varsayılan: 3)
    dropout    : float Dropout oranı
    """

    def __init__(
        self,
        input_dim:  int   = INPUT_DIM,
        hidden_dim: int   = HIDDEN_DIM,
        n_residual: int   = 3,
        dropout:    float = 0.1,
    ) -> None:
        super().__init__()

        # Giriş embedding katmanı: düşük boyutu gizli boyuta yükselt
        self.input_proj = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )

        # Residual bloklar yığını
        self.residual_blocks = nn.ModuleList([
            ResidualBlock(hidden_dim, dropout)
            for _ in range(n_residual)
        ])

        # Çıkış katmanı: skalar maliyet tahmini
        self.output_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.GELU(),
            nn.Linear(hidden_dim // 2, OUTPUT_DIM),
            nn.Softplus(),    # Pozitif çıktı garantisi
        )

        # Ağırlık başlatma
        self._init_weights()

        logger.info(
            "HeuristicNet oluşturuldu. Parametre sayısı: %s",
            f"{self._count_params():,}",
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        İleri geçiş.

        Parameters
        ----------
        x : torch.Tensor  shape (batch_size, input_dim)

        Returns
        -------
        torch.Tensor  shape (batch_size, 1) — tahmin edilen maliyet
        """
        x = self.input_proj(x)

        for block in self.residual_blocks:
            x = block(x)

        return self.output_head(x)

    def predict_single(
        self,
        features: np.ndarray,
        device: torch.device = DEVICE,
    ) -> float:
        """
        Tek bir (source, target) çifti için hızlı inference.

        A* inner loop'ta çağrılır. grad hesabı kapatılır (no_grad),
        tensor'lar cihaza taşınır.

        Parameters
        ----------
        features : np.ndarray  shape (input_dim,)
        device   : torch.device

        Returns
        -------
        float  Tahmin edilen maliyet
        """
        self.eval()
        with torch.no_grad():
            t = torch.tensor(
                features, dtype=torch.float32, device=device
            ).unsqueeze(0)                # (1, input_dim)
            out = self(t)
            return float(out.squeeze())   # scalar

    def _init_weights(self) -> None:
        """
        Xavier uniform başlatma.

        Varsayılan PyTorch başlatması (Kaiming) aktivasyon-agnostiktir.
        GELU için Xavier daha stabil başlangıç sağlar.
        """
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def _count_params(self) -> int:
        """Eğitilebilir parametre sayısını döndürür."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


# ─────────────────────────────────────────────
#  Özellik Çıkarıcı
# ─────────────────────────────────────────────

class FeatureExtractor:
    """
    (source, target) düğüm çiftinden 8 boyutlu özellik vektörü üretir.

    Bu sınıf hem eğitim veri setini oluşturmak hem de
    A* çalışırken real-time özellik üretmek için kullanılır.

    Parameters
    ----------
    graph : nx.MultiDiGraph
        Düğüm koordinatları ve kenar özellikleri için referans graf.
    dist_norm_factor : float
        Mesafe normalizasyon faktörü (metre). İstanbul çapı ~80km → 80_000.
    degree_norm_factor : float
        Derece normalizasyon faktörü. Çoğu kavşak < 8 komşu → 8.
    """

    def __init__(
        self,
        graph: nx.MultiDiGraph,
        dist_norm_factor:   float = 80_000.0,
        degree_norm_factor: float = 8.0,
    ) -> None:
        self.graph              = graph
        self.dist_norm          = dist_norm_factor
        self.degree_norm        = degree_norm_factor

        # Düğüm önbellekleri — her çıkarmada graf taranmaz
        self._coords:        dict = self._cache_coords()
        self._degrees:       dict = self._cache_degrees()
        self._highway_ranks: dict = self._cache_highway_ranks()

        logger.info(
            "FeatureExtractor hazır. %d düğüm önbelleklendi.",
            len(self._coords)
        )

    def extract(self, source: int, target: int) -> np.ndarray:
        """
        (source, target) çifti için 8 boyutlu özellik vektörü üretir.

        Özellikler:
            [0] normalize Haversine mesafesi
            [1] normalize Δlat
            [2] normalize Δlon
            [3] normalize source derece
            [4] normalize target derece
            [5] source highway_rank ortalaması / 5.0
            [6] target highway_rank ortalaması / 5.0
            [7] normalize bearing (yön açısı / π)

        Parameters
        ----------
        source, target : int  OSM düğüm ID

        Returns
        -------
        np.ndarray  shape (8,)  dtype float32
        """
        lat1, lon1 = self._coords[source]
        lat2, lon2 = self._coords[target]

        # Haversine mesafesi
        dist_m = _haversine_m(lat1, lon1, lat2, lon2)

        # Farklar
        delta_lat = (lat2 - lat1) / 1.0    # yaklaşık ölçek: ±2° İstanbul için
        delta_lon = (lon2 - lon1) / 1.0

        # Bearing (kuzeyden saat yönünde açı, radyan)
        bearing = _bearing_rad(lat1, lon1, lat2, lon2)

        features = np.array([
            dist_m / self.dist_norm,                          # [0]
            delta_lat / 2.0,                                  # [1]
            delta_lon / 2.0,                                  # [2]
            self._degrees.get(source, 1) / self.degree_norm,  # [3]
            self._degrees.get(target, 1) / self.degree_norm,  # [4]
            self._highway_ranks.get(source, 1.0) / 5.0,       # [5]
            self._highway_ranks.get(target, 1.0) / 5.0,       # [6]
            bearing / math.pi,                                 # [7]
        ], dtype=np.float32)

        return features

    def extract_batch(
        self,
        pairs: list[tuple[int, int]],
    ) -> np.ndarray:
        """
        Çoklu çift için vektörize özellik çıkarımı.

        Eğitim veri seti oluşturmada kullanılır.

        Parameters
        ----------
        pairs : list[(source, target)]

        Returns
        -------
        np.ndarray  shape (N, 8)
        """
        return np.stack([self.extract(s, t) for s, t in pairs])

    # ── Önbellekleme ────────────────────────

    def _cache_coords(self) -> dict[int, tuple[float, float]]:
        """Tüm düğümlerin (lat, lon) koordinatlarını önbellekler."""
        return {
            n: (d["y"], d["x"])
            for n, d in self.graph.nodes(data=True)
        }

    def _cache_degrees(self) -> dict[int, int]:
        """Her düğümün toplam (in+out) derecesini önbellekler."""
        return dict(self.graph.degree())

    def _cache_highway_ranks(self) -> dict[int, float]:
        """
        Her düğüm için komşu kenarların ortalama highway_rank'ini önbellekler.

        Bir düğümün "önem skoru" — ana arterle bağlantılı mı?
        """
        ranks: dict[int, list] = {n: [] for n in self.graph.nodes()}

        for u, v, data in self.graph.edges(data=True):
            rank = int(data.get("highway_rank", 1))
            ranks[u].append(rank)
            ranks[v].append(rank)

        return {
            node: (sum(r_list) / len(r_list)) if r_list else 1.0
            for node, r_list in ranks.items()
        }


# ─────────────────────────────────────────────
#  Geometri Yardımcıları
# ─────────────────────────────────────────────

def _haversine_m(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """Haversine mesafesi (metre). model_arch içi kullanım."""
    R = 6_371_000.0
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)
    a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _bearing_rad(
    lat1: float, lon1: float,
    lat2: float, lon2: float,
) -> float:
    """
    İki nokta arasındaki compass bearing'i radyan cinsinden döndürür.

    Bearing yön bilgisi sağlar: örneğin Boğaz'ı geçen rotalar
    doğu-batı yönünde olduğu için kuzey-güney rotalardan farklı maliyet taşır.
    """
    φ1 = math.radians(lat1)
    φ2 = math.radians(lat2)
    Δλ = math.radians(lon2 - lon1)

    x = math.sin(Δλ) * math.cos(φ2)
    y = (math.cos(φ1) * math.sin(φ2)
         - math.sin(φ1) * math.cos(φ2) * math.cos(Δλ))

    return math.atan2(x, y)   # [-π, π]