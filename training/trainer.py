"""
training/trainer.py
===================
İstanbul Yol Öneri Projesi — PyTorch MPS Eğitim Döngüsü

Sorumluluk:
    HeuristicNet modelini TrainingDataset üzerinde eğitir.
    Apple Silicon MPS cihazında çalışır, CUDA/CPU'ya otomatik fallback yapar.

Kayıp Fonksiyonu Seçimi:
    Huber Loss (SmoothL1Loss):
        - MSE'nin aksine aykırı değerlere (outlier) daha dayanıklı.
        - MAE'nin aksine sıfırda türevlenebilir (eğitim stabilitesi).
        - δ=1.0: hata < 1 → MSE davranışı, hata ≥ 1 → MAE davranışı.
        A* maliyet değerleri (saniye) geniş aralıkta (10s – 7200s)
        dağılır; Huber bu aralıkta MSE'den belirgin üstündür.

Optimizer Seçimi:
    AdamW:
        - Adam + weight decay ayrıştırması (Loshchilov & Hutter, 2019).
        - L2 regularization yerine ağırlık çürümesi → daha iyi genelleme.
        - lr=1e-3, weight_decay=1e-4

Öğrenme Oranı Planlaması:
    CosineAnnealingLR:
        - Sabit lr'den belirgin üstün (Sharp minima'dan kaçınır).
        - T_max = toplam epoch → eğitim sonunda lr ~ 0'a yaklaşır.

Erken Durdurma (Early Stopping):
    Validation loss patience=10 epoch artmazsa eğitim durur.
    Overfitting önlenir, gereksiz hesaplama engellenir.
"""

import logging
import pickle
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset, random_split

from training.model_arch import HeuristicNet, DEVICE, get_device
from training.dataset_builder import TrainingDataset

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parents[1] / "models" / "checkpoints"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


class EarlyStopping:
    """
    Validation loss izleyerek erken durdurma uygular.

    Parameters
    ----------
    patience : int    Kaç epoch iyileşme beklenir
    min_delta : float  Anlamlı iyileşme eşiği
    """

    def __init__(self, patience: int = 10, min_delta: float = 1e-4) -> None:
        self.patience   = patience
        self.min_delta  = min_delta
        self.best_loss  = float("inf")
        self.counter    = 0
        self.should_stop = False

    def step(self, val_loss: float) -> bool:
        """
        Returns True ise eğitim durdurulmalı.
        """
        if val_loss < self.best_loss - self.min_delta:
            self.best_loss = val_loss
            self.counter   = 0
        else:
            self.counter += 1
            if self.counter >= self.patience:
                self.should_stop = True
        return self.should_stop


class Trainer:
    """
    HeuristicNet eğitim orkestratörü.

    Parameters
    ----------
    model      : HeuristicNet
    dataset    : TrainingDataset
    epochs     : int     Maksimum epoch sayısı
    batch_size : int
    lr         : float   Başlangıç öğrenme oranı
    val_ratio  : float   Validation ayrımı oranı
    patience   : int     Early stopping sabrı
    device     : torch.device
    """

    def __init__(
        self,
        model:      HeuristicNet,
        dataset:    TrainingDataset,
        epochs:     int   = 100,
        batch_size: int   = 512,
        lr:         float = 1e-3,
        val_ratio:  float = 0.15,
        patience:   int   = 10,
        device:     torch.device = DEVICE,
    ) -> None:
        self.model      = model.to(device)
        self.device     = device
        self.epochs     = epochs
        self.batch_size = batch_size

        # Veri hazırlığı
        self.train_loader, self.val_loader = self._prepare_data(
            dataset, batch_size, val_ratio
        )

        # Optimizer, kayıp, scheduler
        self.optimizer = torch.optim.AdamW(
            model.parameters(), lr=lr, weight_decay=1e-4
        )
        self.criterion = nn.SmoothL1Loss(beta=1.0)   # Huber loss
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=epochs, eta_min=1e-6
        )
        self.early_stopping = EarlyStopping(patience=patience)

        # Eğitim geçmişi
        self.history = {"train_loss": [], "val_loss": [], "lr": []}

        logger.info(
            "Trainer hazır. Cihaz: %s | Epoch: %d | Batch: %d | "
            "Train: %d | Val: %d",
            device, epochs, batch_size,
            len(self.train_loader.dataset),
            len(self.val_loader.dataset),
        )

    def train(self) -> dict:
        """
        Tam eğitim döngüsünü çalıştırır.

        Her epoch:
            1. Training pass  (backward + optimizer step)
            2. Validation pass (no_grad)
            3. Scheduler step
            4. Early stopping kontrolü
            5. En iyi model checkpoint kaydetme

        Returns
        -------
        dict  Eğitim geçmişi (train_loss, val_loss, lr listeleri)
        """
        t0      = time.perf_counter()
        best_val = float("inf")

        logger.info("=== Eğitim Başlıyor ===")

        for epoch in range(1, self.epochs + 1):
            train_loss = self._train_epoch()
            val_loss   = self._validate_epoch()

            # Scheduler adımı
            self.scheduler.step()
            current_lr = self.scheduler.get_last_lr()[0]

            # Geçmişe kaydet
            self.history["train_loss"].append(train_loss)
            self.history["val_loss"].append(val_loss)
            self.history["lr"].append(current_lr)

            # Checkpoint: en iyi model
            if val_loss < best_val:
                best_val = val_loss
                self._save_checkpoint(epoch, val_loss)

            # İlerleme logu (her 5 epoch'ta bir)
            if epoch % 5 == 0 or epoch == 1:
                logger.info(
                    "Epoch %3d/%d | Train: %.4f | Val: %.4f | LR: %.2e",
                    epoch, self.epochs, train_loss, val_loss, current_lr,
                )

            # Early stopping
            if self.early_stopping.step(val_loss):
                logger.info(
                    "Early stopping tetiklendi. Epoch: %d | En iyi Val: %.4f",
                    epoch, best_val,
                )
                break

        elapsed = time.perf_counter() - t0
        logger.info(
            "=== Eğitim Tamamlandı (%.1f saniye) | En iyi Val Loss: %.4f ===",
            elapsed, best_val,
        )
        return self.history

    def _train_epoch(self) -> float:
        """Tek bir training epoch'u. Gradyan hesaplanır ve geri yayılır."""
        self.model.train()
        total_loss = 0.0

        for X_batch, y_batch in self.train_loader:
            X_batch = X_batch.to(self.device)
            y_batch = y_batch.to(self.device).unsqueeze(1)

            self.optimizer.zero_grad()
            pred = self.model(X_batch)
            loss = self.criterion(pred, y_batch)
            loss.backward()

            # Gradient clipping: patlayan gradyan önlemi
            nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

            self.optimizer.step()
            total_loss += loss.item() * len(X_batch)

        return total_loss / len(self.train_loader.dataset)

    def _validate_epoch(self) -> float:
        """Tek bir validation epoch'u. Gradyan hesaplanmaz."""
        self.model.eval()
        total_loss = 0.0

        with torch.no_grad():
            for X_batch, y_batch in self.val_loader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device).unsqueeze(1)
                pred    = self.model(X_batch)
                loss    = self.criterion(pred, y_batch)
                total_loss += loss.item() * len(X_batch)

        return total_loss / len(self.val_loader.dataset)

    def _prepare_data(
        self,
        dataset: TrainingDataset,
        batch_size: int,
        val_ratio: float,
    ) -> tuple[DataLoader, DataLoader]:
        """
        NumPy dizilerini PyTorch TensorDataset'e dönüştürür ve böler.

        Normalizasyon:
            Etiketler (saniye) log1p ile sıkıştırılır:
            log(1 + x) → geniş aralığı [0, ~9] bandına çeker.
            Model bu sıkıştırılmış değeri tahmin eder;
            inference sırasında expm1 ile geri açılır.
        """
        X = torch.tensor(dataset.features, dtype=torch.float32)
        # Log1p normalizasyon: 10s → 2.4, 3600s → 8.2
        y = torch.tensor(
            np.log1p(dataset.labels), dtype=torch.float32
        )

        full_dataset = TensorDataset(X, y)
        n_val   = int(len(full_dataset) * val_ratio)
        n_train = len(full_dataset) - n_val

        train_ds, val_ds = random_split(
            full_dataset, [n_train, n_val],
            generator=torch.Generator().manual_seed(42),
        )

        train_loader = DataLoader(
            train_ds, batch_size=batch_size, shuffle=True,
            num_workers=0,    # MPS ile num_workers > 0 sorun çıkarabilir
            pin_memory=False,
        )
        val_loader = DataLoader(
            val_ds, batch_size=batch_size * 2, shuffle=False,
            num_workers=0,
        )
        return train_loader, val_loader

    def _save_checkpoint(self, epoch: int, val_loss: float) -> None:
        """En iyi modeli .pt formatında kaydeder."""
        path = MODELS_DIR / "best_heuristic_net.pt"
        torch.save({
            "epoch":      epoch,
            "val_loss":   val_loss,
            "model_state_dict":     self.model.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
        }, path)
        logger.debug("Checkpoint kaydedildi → epoch %d | val=%.4f", epoch, val_loss)


# ─────────────────────────────────────────────
#  CLI Giriş Noktası
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import pickle
    from core.map_loader import MapLoader
    from core.graph_processor import GraphProcessor
    from core.astar_engine import AStarEngine
    from training.model_arch import FeatureExtractor
    from training.dataset_builder import DatasetBuilder

    # 1. Altyapı
    loader    = MapLoader()
    graph     = loader.load_from_disk()
    processor = GraphProcessor(graph)
    hierarchy = processor.build_hierarchy(save=False)
    h_cache   = processor.build_heuristic_cache(save=False)
    engine    = AStarEngine(hierarchy, h_cache, processor)
    extractor = FeatureExtractor(graph)

    # 2. Veri seti
    ds_path = Path("data/processed/training_dataset.pkl")
    if ds_path.exists():
        with open(ds_path, "rb") as f:
            dataset = pickle.load(f)
        logger.info("Mevcut veri seti yüklendi: %d örnek", len(dataset.labels))
    else:
        builder = DatasetBuilder(graph, engine, extractor, n_per_band=800)
        dataset = builder.build(save=True)

    # 3. Model ve eğitim
    model   = HeuristicNet()
    trainer = Trainer(model, dataset, epochs=100, batch_size=256)
    history = trainer.train()

    print("\n── Eğitim Özeti ───────────────────────────")
    print(f"  Son train loss : {history['train_loss'][-1]:.4f}")
    print(f"  Son val loss   : {history['val_loss'][-1]:.4f}")
    print(f"  Toplam epoch   : {len(history['train_loss'])}")
    print("────────────────────────────────────────────")
