"""
core/neural_heuristic.py
========================
İstanbul Yol Öneri Projesi — Neural Heuristic Entegrasyon Modülü

Sorumluluk:
    Eğitilmiş HeuristicNet ONNX modelini A* arama motoruna bağlar.
    A* algoritması çalışırken O(1) ile sezgisel tahmini yapar.

Tasarım Kararları:
    - ONNX Runtime → CPU üzerinde PyTorch'tan ~10-15x daha düşük overhead ile çıkarım.
    - expm1 Dönüşümü → Eğitim sırasında log1p ile normalize edilmiş maliyetleri
      tekrar saniye cinsine dönüştürür.
    - Python Bellek Önbelleği (In-Memory Cache) → A* arama ağacında aynı düğüm çifti
      tekrar sorgulandığında ONNX çağrısı yapmadan O(1)'de önbellekten döner.
"""

import logging
from pathlib import Path
from typing import Iterable

import numpy as np
import onnxruntime as ort

from training.model_arch import FeatureExtractor, INPUT_DIM

logger = logging.getLogger(__name__)

# Öntanımlı ONNX yolları
ONNX_DIR = Path(__file__).resolve().parents[1] / "models" / "onnx"
DEFAULT_ONNX_PATH = ONNX_DIR / "heuristic_net.onnx"
QUANT_ONNX_PATH = ONNX_DIR / "heuristic_net_int8.onnx"


class NeuralHeuristic:
    """
    ONNX modeli ile A* için neural heuristic tahmincisi.

    Parameters
    ----------
    graph : nx.MultiDiGraph
        Demet özellikleri ve FeatureExtractor için grafik yapısı.
    h_cache : HeuristicCache
        Coğrafi koordinatlar referansı.
    processor : GraphProcessor
        Graf işlemcisi.
    onnx_path : Path | None
        Özel ONNX dosya yolu. Belirtilmezse varsayılan veya kuantize sürüm seçilir.
    """

    def __init__(
        self,
        graph,
        h_cache,
        processor,
        onnx_path: Path | None = None,
    ) -> None:
        self.graph = graph
        self.h_cache = h_cache
        self.processor = processor

        # Model yolu tespiti: kuantize sürüm varsa tercih et, yoksa standart sürümü al
        if onnx_path is None:
            if QUANT_ONNX_PATH.exists():
                self.onnx_path = QUANT_ONNX_PATH
                logger.info("NeuralHeuristic: Kuantize INT8 model seçildi.")
            else:
                self.onnx_path = DEFAULT_ONNX_PATH
                logger.info("NeuralHeuristic: Standart model seçildi.")
        else:
            self.onnx_path = Path(onnx_path)

        if not self.onnx_path.exists():
            # Eğer eğitim tamamlanmadıysa, AStarEngine fallback moduna geçer.
            logger.warning(
                "ONNX model dosyası bulunamadı: %s. Rota planlamadan önce modeli eğitin ve export edin.",
                self.onnx_path
            )

        # ONNX Runtime oturumu başlatma
        try:
            self.sess = ort.InferenceSession(
                str(self.onnx_path),
                providers=["CPUExecutionProvider"],
            )
            self.input_name = self.sess.get_inputs()[0].name
            self.output_name = self.sess.get_outputs()[0].name
            self.model_loaded = True
            logger.info("ONNX Runtime oturumu başarıyla başlatıldı. Model: %s", self.onnx_path.name)
        except Exception as e:
            logger.error("ONNX model yükleme hatası: %s. Heuristic fallback modunda çalışabilir.", e)
            self.model_loaded = False
            self.sess = None

        # Özellik çıkarıcı
        self.extractor = FeatureExtractor(graph)

        # A* arama hızını maksimize etmek için python tabanlı bellek önbelleği
        self._pred_cache: dict[tuple[int, int], float] = {}
        self._hits = 0
        self._misses = 0

    def __call__(self, u: int, v: int) -> float:
        """
        A* sezgisel fonksiyonu arayüzü. (u, v) çifti için maliyet tahmini döndürür.

        Tekil tahminlerde ONNX runtime çağrı yükünü engellemek için cache kontrolü yapar.

        Parameters
        ----------
        u : int  Kaynak düğüm ID'si
        v : int  Hedef düğüm ID'si

        Returns
        -------
        float  Saniye cinsinden tahmini geçiş süresi.
        """
        key = (u, v)
        if key in self._pred_cache:
            self._hits += 1
            return self._pred_cache[key]

        self._misses += 1

        # Model yüklü değilse Haversine fallback'e başvur
        if not self.model_loaded:
            dist_m = self.processor.get_heuristic(self.h_cache, u, v)
            # Otoyol hızı varsayımı ~80km/s -> 22.22 m/s
            val = dist_m / 22.22
            self._pred_cache[key] = val
            return val

        # Özellikleri çıkar
        feat = self.extractor.extract(u, v)  # shape (8,)

        # Batch=1 boyutuna uyarla
        feat_input = feat.reshape(1, INPUT_DIM).astype(np.float32)

        # ONNX çıkarımı
        pred = self.sess.run([self.output_name], {self.input_name: feat_input})[0]

        # log1p normalizasyonunu expm1 ile tersine çevirerek saniye değerini geri kazan
        cost_seconds = float(np.expm1(pred[0, 0]))

        # Sezgisel değer asla negatif olamaz (admissibility gereği alt sınır 0.0'dır)
        cost_seconds = max(0.0, cost_seconds)

        self._pred_cache[key] = cost_seconds
        return cost_seconds

    def predict_batch(self, pairs: list[tuple[int, int]]) -> np.ndarray:
        """
        Gezgin Satıcı (TSP) veya maliyet matrisi hesaplama için toplu tahmin yapar.

        ONNX Runtime'ın paralel işlem gücünü kullanarak N çifti tek çağrıda hesaplar.

        Parameters
        ----------
        pairs : list[(u, v)]

        Returns
        -------
        np.ndarray  Tahmini saniye maliyetleri (N,) boyutunda float32 dizi.
        """
        if not pairs:
            return np.empty(0, dtype=np.float32)

        # Model yüklü değilse hızlı Haversine tahmini
        if not self.model_loaded:
            from core.graph_processor import haversine_meters
            fallback_costs = []
            for u, v in pairs:
                du = self.graph.nodes[u]
                dv = self.graph.nodes[v]
                d = haversine_meters(du["y"], du["x"], dv["y"], dv["x"])
                fallback_costs.append(max(0.0, d / 22.22))
            return np.array(fallback_costs, dtype=np.float32)

        # Vektörize özellik çıkarımı
        features = self.extractor.extract_batch(pairs).astype(np.float32)  # shape (N, 8)

        # ONNX toplu çıkarım
        preds = self.sess.run([self.output_name], {self.input_name: features})[0]  # shape (N, 1)

        # Log ölçeğinden saniye ölçeğine geri çevir
        costs = np.expm1(preds.squeeze(-1))

        # Admissible sınır güvencesi
        costs = np.clip(costs, a_min=0.0, a_max=None)
        return costs

    def get_stats(self) -> dict:
        """
        Bellek önbelleği isabet ve performans istatistiklerini döndürür.
        """
        total = self._hits + self._misses
        hit_rate = (self._hits / max(1, total)) * 100
        return {
            "model_path": str(self.onnx_path) if self.model_loaded else "N/A",
            "model_loaded": self.model_loaded,
            "cache_hits": self._hits,
            "cache_misses": self._misses,
            "cache_size": len(self._pred_cache),
            "total_queries": total,
            "hit_rate": f"{hit_rate:.1f}%",
        }
