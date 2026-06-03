#!/bin/bash
# İstRoute Başlatıcı (Mac)
# Bu dosyaya çift tıklayarak sunucuyu başlatabilir ve tarayıcıyı otomatik açabilirsiniz.

cd "$(dirname "$0")"
echo "============================================="
echo "   İstRoute Rota Planlama Sunucusu Başlatılıyor"
echo "============================================="

# 1. Sanal ortamı kontrol et
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Hata: .venv klasörü bulunamadı! Sanal ortamın yüklü olduğundan emin olun."
    read -p "Çıkmak için Enter tuşuna basın..."
    exit 1
fi

# 2. Tarayıcıyı 1.5 saniye sonra arka planda otomatik aç
(sleep 1.5 && open http://127.0.0.1:5001) &

# 3. Flask web sunucusunu çalıştır
python main.py --mode server
