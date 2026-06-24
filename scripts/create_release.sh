#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# scripts/create_release.sh
# GitHub Releases'e model ağırlıklarını yükler (gh CLI kullanır).
#
# Ön gereksinim:
#   brew install gh
#   gh auth login
#
# Kullanım:
#   chmod +x scripts/create_release.sh
#   ./scripts/create_release.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e

TAG="v1.0.0"
TITLE="v1.0.0 — İlk Kararlı Sürüm"
NOTES="## Model Ağırlıkları

Bu release, \`setup_data.py\` tarafından otomatik olarak indirilir.

### Kurulum
\`\`\`bash
python setup_data.py
\`\`\`

### İçerik
| Dosya | Boyut | Açıklama |
|---|---|---|
| \`best_heuristic_net.pt\` | ~1.3 MB | PyTorch eğitim checkpoint'i |
| \`heuristic_net.onnx\` | ~12 KB | ONNX model tanımı |
| \`heuristic_net.onnx.data\` | ~430 KB | ONNX model ağırlıkları |

### Veri Üretimi
GraphML harita dosyaları bu release'e dahil edilmemiştir.
\`setup_data.py\` bu dosyaları OpenStreetMap'ten otomatik olarak üretir."

CHECKPOINT="models/checkpoints/best_heuristic_net.pt"
ONNX_MODEL="models/onnx/heuristic_net.onnx"
ONNX_DATA="models/onnx/heuristic_net.onnx.data"

echo "══════════════════════════════════════════════"
echo "  GitHub Release Oluşturuluyor: $TAG"
echo "══════════════════════════════════════════════"
echo ""

# gh CLI varlığını kontrol et
if ! command -v gh &> /dev/null; then
    echo "✗ 'gh' CLI bulunamadı."
    echo "  Kurulum: brew install gh"
    echo "  Giriş:   gh auth login"
    exit 1
fi

# Dosya varlığını kontrol et
for f in "$CHECKPOINT" "$ONNX_MODEL" "$ONNX_DATA"; do
    if [ ! -f "$f" ]; then
        echo "✗ Dosya bulunamadı: $f"
        echo "  Önce modeli eğitin: python main.py --train"
        exit 1
    fi
done

echo "✓ Tüm dosyalar mevcut. Release oluşturuluyor..."
echo ""

# Mevcut release'i sil (varsa)
if gh release view "$TAG" &> /dev/null; then
    echo "⚠ '$TAG' zaten mevcut. Siliniyor..."
    gh release delete "$TAG" --yes --cleanup-tag
fi

# Release oluştur ve dosyaları yükle
gh release create "$TAG" \
    --title "$TITLE" \
    --notes "$NOTES" \
    "$CHECKPOINT" \
    "$ONNX_MODEL" \
    "$ONNX_DATA"

echo ""
echo "✓ Release başarıyla oluşturuldu!"
echo "  https://github.com/MrOzbir/istanbul-route-optimizer/releases/tag/$TAG"
