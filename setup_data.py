"""
setup_data.py
=============
İstanbul Yol Öneri Projesi — Veri & Model Kurulum Scripti

Bu script projeyi klonladıktan sonra çalıştırılır. İki görev yapar:

  1. Model ağırlıkları (best_heuristic_net.pt, heuristic_net.onnx)
     GitHub Releases'ten otomatik indirilir.

  2. Harita verileri (*.graphml, heuristic_cache.pkl)
     OpenStreetMap'ten OSMnx aracılığıyla otomatik üretilir.
     → İnternet bağlantısı gerektirir (~5-15 dk, internet hızına göre).

Kullanım:
    python setup_data.py

Opsiyonel argümanlar:
    --skip-map        Harita verisi zaten varsa işlemi atlar
    --skip-model      Model ağırlıkları zaten varsa işlemi atlar
    --force           Mevcut dosyaları silerek yeniden indirir/üretir
"""

import argparse
import logging
import sys
import urllib.request
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  Proje dizin yapısı
# ─────────────────────────────────────────────

ROOT        = Path(__file__).resolve().parent
DATA_RAW    = ROOT / "data" / "raw"
DATA_PROC   = ROOT / "data" / "processed"
CHECKPOINTS = ROOT / "models" / "checkpoints"
ONNX_DIR    = ROOT / "models" / "onnx"

# ─────────────────────────────────────────────
#  GitHub Releases model dosyaları
#  Release tag'i: v1.0.0 olarak sabitlenmiştir.
# ─────────────────────────────────────────────

GITHUB_REPO = "MrOzbir/istanbul-route-optimizer"
RELEASE_TAG = "v1.0.0"
BASE_URL    = f"https://github.com/{GITHUB_REPO}/releases/download/{RELEASE_TAG}"

MODEL_FILES = {
    CHECKPOINTS / "best_heuristic_net.pt":      f"{BASE_URL}/best_heuristic_net.pt",
    ONNX_DIR    / "heuristic_net.onnx":         f"{BASE_URL}/heuristic_net.onnx",
    ONNX_DIR    / "heuristic_net.onnx.data":    f"{BASE_URL}/heuristic_net.onnx.data",
}


# ─────────────────────────────────────────────
#  Yardımcı Fonksiyonlar
# ─────────────────────────────────────────────

def _ensure_dirs() -> None:
    """Gerekli dizinleri oluşturur."""
    for d in (DATA_RAW, DATA_PROC, CHECKPOINTS, ONNX_DIR):
        d.mkdir(parents=True, exist_ok=True)


def _download_file(url: str, dest: Path) -> None:
    """
    Belirtilen URL'den dosyayı indirir ve dest'e kaydeder.
    İlerleme göstergesi terminale yazdırılır.
    """
    logger.info("İndiriliyor: %s", dest.name)
    logger.info("  Kaynak: %s", url)

    def _reporthook(count, block_size, total_size):
        if total_size > 0:
            pct = min(count * block_size * 100 // total_size, 100)
            bar = "█" * (pct // 5) + "░" * (20 - pct // 5)
            print(f"\r  [{bar}] {pct}%", end="", flush=True)

    try:
        urllib.request.urlretrieve(url, dest, reporthook=_reporthook)
        print()  # Satır sonu
        size_mb = dest.stat().st_size / (1024 ** 2)
        logger.info("  ✓ İndirildi (%.2f MB)", size_mb)
    except Exception as e:
        logger.error("  ✗ İndirme başarısız: %s", e)
        logger.error(
            "  Model dosyasını manuel olarak indirip '%s' dizinine koyun:", dest.parent
        )
        logger.error("  %s", url)
        raise


# ─────────────────────────────────────────────
#  Adım 1: Model Ağırlıklarını İndir
# ─────────────────────────────────────────────

def download_models(force: bool = False) -> bool:
    """
    GitHub Releases'ten model ağırlıklarını indirir.

    Parameters
    ----------
    force : bool
        True ise mevcut dosyaların üzerine yazar.

    Returns
    -------
    bool  Tüm dosyalar başarıyla indirildi mi?
    """
    logger.info("=" * 50)
    logger.info("ADIM 1: Model Ağırlıklarını İndir")
    logger.info("=" * 50)

    all_ok = True
    for dest, url in MODEL_FILES.items():
        if dest.exists() and not force:
            size_mb = dest.stat().st_size / (1024 ** 2)
            logger.info("✓ Mevcut: %s (%.2f MB) — atlanıyor", dest.name, size_mb)
            continue

        if force and dest.exists():
            dest.unlink()

        try:
            _download_file(url, dest)
        except Exception:
            all_ok = False

    if all_ok:
        logger.info("✓ Tüm model dosyaları hazır.\n")
    else:
        logger.warning(
            "⚠ Bazı model dosyaları indirilemedi.\n"
            "  İnternet bağlantınızı kontrol edin veya dosyaları manuel indirin:\n"
            "  https://github.com/%s/releases/tag/%s\n",
            GITHUB_REPO, RELEASE_TAG,
        )

    return all_ok


# ─────────────────────────────────────────────
#  Adım 2: Harita Verilerini OSMnx ile Üret
# ─────────────────────────────────────────────

def build_map_data(force: bool = False) -> bool:
    """
    OSMnx ile İstanbul harita verilerini OpenStreetMap'ten çeker
    ve GraphProcessor ile hiyerarşik katmanları oluşturur.

    Bu işlem internet bağlantısı gerektirir ve ~5-15 dakika sürebilir.

    Parameters
    ----------
    force : bool
        True ise mevcut .graphml dosyaları silinerek yeniden üretilir.

    Returns
    -------
    bool  Başarıyla tamamlandı mı?
    """
    logger.info("=" * 50)
    logger.info("ADIM 2: Harita Verilerini OSMnx ile Üret")
    logger.info("=" * 50)

    raw_graphml      = DATA_RAW  / "istanbul_main_arteries.graphml"
    full_graphml     = DATA_PROC / "full_hierarchy.graphml"
    express_graphml  = DATA_PROC / "express.graphml"
    arterial_graphml = DATA_PROC / "arterial.graphml"
    cache_pkl        = DATA_PROC / "heuristic_cache.pkl"

    required_files = [raw_graphml, full_graphml, express_graphml, arterial_graphml]

    if not force and all(f.exists() for f in required_files):
        logger.info("✓ Harita verileri zaten mevcut — atlanıyor.")
        logger.info("  Yeniden oluşturmak için: python setup_data.py --force\n")
        return True

    if force:
        for f in required_files + [cache_pkl]:
            if f.exists():
                f.unlink()
                logger.info("  Silindi: %s", f.name)

    # OSMnx import kontrolü
    try:
        import osmnx as ox  # noqa: F401
        import networkx as nx  # noqa: F401
    except ImportError:
        logger.error(
            "✗ osmnx veya networkx bulunamadı.\n"
            "  Kurulum: pip install osmnx networkx"
        )
        return False

    logger.info("İstanbul ana arterler haritası indiriliyor...")
    logger.info("(Bu işlem internet hızınıza göre 5-15 dakika sürebilir)\n")

    try:
        # ── Adım 2a: Ham haritayı OSMnx'ten çek ──────────────────
        from core.map_loader import MapLoader
        loader = MapLoader()
        graph  = loader.run()   # → data/raw/istanbul_main_arteries.graphml

        # ── Adım 2b: Hiyerarşik katmanları işle ──────────────────
        logger.info("\nHiyerarşik graflar oluşturuluyor...")
        from core.graph_processor import GraphProcessor
        processor = GraphProcessor(graph)

        processor.build_hierarchy()       # → express + arterial + full .graphml
        logger.info("✓ Hiyerarşik graflar kaydedildi.")

        processor.build_heuristic_cache() # → heuristic_cache.pkl
        logger.info("✓ Heuristic cache oluşturuldu.")

        logger.info("\n✓ Harita verisi hazır!\n")
        return True

    except Exception as e:
        logger.error("✗ Harita üretimi başarısız: %s", e)
        logger.exception("Detay:")
        return False


# ─────────────────────────────────────────────
#  Ana Akış
# ─────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="İstanbul Yol Optimizer — Veri & Model Kurulum Scripti",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  python setup_data.py                   # Tam kurulum
  python setup_data.py --skip-map        # Sadece model dosyalarını indir
  python setup_data.py --skip-model      # Sadece harita verisi üret
  python setup_data.py --force           # Her şeyi sıfırdan yeniden kur
        """,
    )
    parser.add_argument(
        "--skip-map",
        action="store_true",
        help="Harita verisi üretimini atla",
    )
    parser.add_argument(
        "--skip-model",
        action="store_true",
        help="Model ağırlığı indirmeyi atla",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Mevcut dosyaları silerek yeniden indir/üret",
    )
    args = parser.parse_args()

    print()
    print("╔══════════════════════════════════════════════╗")
    print("║   İstanbul Yol Optimizer — Veri Kurulumu     ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    _ensure_dirs()

    model_ok = True
    map_ok   = True

    if not args.skip_model:
        model_ok = download_models(force=args.force)

    if not args.skip_map:
        map_ok = build_map_data(force=args.force)

    print()
    print("╔══════════════════════════════════════════════╗")
    if model_ok and map_ok:
        print("║   ✓ Kurulum tamamlandı!                      ║")
        print("║                                              ║")
        print("║   Uygulamayı başlatmak için:                 ║")
        print("║     python app.py                            ║")
    else:
        print("║   ⚠ Kurulum kısmen tamamlandı.               ║")
        print("║   Yukarıdaki hata mesajlarını inceleyin.     ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    sys.exit(0 if (model_ok and map_ok) else 1)


if __name__ == "__main__":
    main()
