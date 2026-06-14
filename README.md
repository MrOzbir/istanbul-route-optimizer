# İstanbul Neural-Guided A* Rota Planlayıcı

İstanbul'un yol ağı üzerinde **sinir ağı destekli, hiyerarşik, çift yönlü A\*** algoritması kullanan çok duraklı rota optimizasyon sistemi. Kullanıcı harita üzerinde istediği noktaları işaretler; sistem bu noktaları en kısa sürede birbirine bağlayan optimal rotayı gerçek zamanlı trafik verisiyle birlikte hesaplar ve interaktif bir haritada görselleştirir.

---

## İçindekiler

- [Proje Amacı](#proje-amacı)
- [Sistem Mimarisi](#sistem-mimarisi)
- [Modüller ve Çalışma Mantığı](#modüller-ve-çalışma-mantığı)
  - [1. Harita Verisi: MapLoader](#1-harita-verisi-maploader)
  - [2. Graf İşleme: GraphProcessor](#2-graf-işleme-graphprocessor)
  - [3. Rota Motoru: AStarEngine](#3-rota-motoru-astarengine)
  - [4. Sinir Ağı Eğitimi: training/](#4-sinir-ağı-eğitimi-training)
  - [5. Neural Heuristic: NeuralHeuristic](#5-neural-heuristic-neuralheuristic)
  - [6. Çok Duraklı Rota: RingPlanner](#6-çok-duraklı-rota-ringplanner)
  - [7. Trafik Yönetimi: TrafficManager](#7-trafik-yönetimi-trafficmanager)
  - [8. Web Arayüzü: app.py + Flask](#8-web-arayüzü-apppy--flask)
  - [9. Görselleştirme: MapRenderer](#9-görselleştirme-maprenderer)
- [Veri Akışı (Uçtan Uca)](#veri-akışı-uçtan-uca)
- [Algoritma Detayları](#algoritma-detayları)
  - [Bidirectional A*](#bidirectional-a)
  - [Hiyerarşik Graf Katmanlama](#hiyerarşik-graf-katmanlama)
  - [Neural Heuristic](#neural-heuristic)
  - [TSP Çözümü: Nearest Neighbor + 2-opt](#tsp-çözümü-nearest-neighbor--2-opt)
  - [Trafik Simülasyonu](#trafik-simülasyonu)
- [Özellik Mühendisliği](#özellik-mühendisliği)
- [Model Mimarisi: HeuristicNet](#model-mimarisi-heuristicnet)
- [Önbellekleme Stratejisi](#önbellekleme-stratejisi)
- [Kurulum ve Çalıştırma](#kurulum-ve-çalıştırma)
- [Komut Satırı Kullanımı](#komut-satırı-kullanımı)
- [API Uç Noktaları](#api-uç-noktaları)
- [Proje Dizin Yapısı](#proje-dizin-yapısı)
- [Landmark Koordinatları](#landmark-koordinatları)

---

## Proje Amacı

Klasik navigasyon yazılımlarının İstanbul gibi büyük, iki kıtalı ve karmaşık topolojili şehirlerde yaşadığı ölçeklenebilirlik sorununu çözmek. Bu proje:

- **Klasik A\***'ı üç ayrı teknikle iyileştirerek (çift yönlülük + hiyerarşi + neural heuristic) 10–50x hız kazanımı sağlar.
- N adet kullanıcı seçimli durak arasındaki **en optimum geçiş sırasını** TSP tabanlı algoritmalarla bulur.
- Gerçek zamanlı veya simüle edilmiş **trafik yoğunluğunu** kenar maliyetlerine yansıtarak trafik farkında rotalar üretir.
- Tüm bu işlemleri kullanıcı dostu bir **web arayüzünden** tek tıkla sunar.

---

## Sistem Mimarisi

```
OpenStreetMap (Overpass API)
         │
         ▼
   core/map_loader.py          ← Ham harita verisi çekme
         │
         ▼
 core/graph_processor.py       ← Hiyerarşik katmanlama + Haversine önbelleği
         │
    ┌────┴────┐
    │         │
    ▼         ▼
Express    Arterial             ← İki ayrı arama katmanı
  Graf       Graf
    │         │
    └────┬────┘
         │
         ▼
  core/astar_engine.py         ← Bidirectional Hierarchical A*
    ▲         ▲
    │         │
  Haversine  NeuralHeuristic   ← Değiştirilebilir sezgisel fonksiyon
  (fallback) (ONNX, inference)
         │
         ▼
  core/ring_planner.py         ← TSP: Nearest Neighbor + 2-opt
         │
         ▼
  core/traffic_manager.py      ← Kenar maliyeti çarpanları (trafik)
         │
         ▼
   app.py (Flask)              ← REST API sunucusu
         │
         ▼
  templates/index.html         ← Leaflet.js interaktif harita arayüzü
```

---

## Modüller ve Çalışma Mantığı

### 1. Harita Verisi: MapLoader

**Dosya:** `core/map_loader.py`

**Amaç:** OpenStreetMap'ten İstanbul'un ana yol ağını çekerek projeye hazır hale getirir.

**Çalışma Adımları:**

1. **Graf Çekme:** OSMnx kütüphanesi aracılığıyla Overpass API'ye sorgu atar. Yalnızca üst düzey yollar alınır: `motorway`, `motorway_link`, `trunk`, `trunk_link`, `primary`, `primary_link`, `secondary`, `secondary_link`. Düşük hiyerarşili yollar (residential, unclassified, tertiary) bilinçli olarak hariç tutulur — bu hem veri boyutunu küçültür hem de A\* arama uzayını daraltır.

2. **Graf Zenginleştirme:** Çekilen ham grafa ek özellikler eklenir:
   - `speed_kph`: OSMnx'in `add_edge_speeds()` fonksiyonu eksik hız limitlerini yol tipine göre tahmin eder.
   - `travel_time`: `length / speed_ms` formülüyle saniye cinsinden kenar geçiş süresi hesaplanır. A\* bu değeri maliyet metriği olarak kullanır.
   - `highway_rank`: Yol öncelik skoru (motorway=5 … secondary=1). Sinir ağı özellik mühendisliğinde ve katman seçiminde kullanılır.

3. **Kaydetme:** Graf `.graphml` formatında `data/raw/istanbul_main_arteries.graphml` olarak diske yazılır. Sonraki çalıştırmalarda API'ye tekrar sorgu atılmaz; `load_from_disk()` ile doğrudan yüklenir.

**Neden `.graphml`?** NetworkX'in tüm düğüm/kenar özelliklerini tam olarak koruyan XML tabanlı format. QGIS, Gephi gibi araçlarla da açılabilir.

---

### 2. Graf İşleme: GraphProcessor

**Dosya:** `core/graph_processor.py`

**Amaç:** Ham grafı A\* için optimize eder: hiyerarşik katmanlara böler ve Haversine önbelleği oluşturur.

**SCC Temizliği:** 100'den fazla düğümlü graflarda önce en büyük Strongly Connected Component (SCC) belirlenir. Çıkmaz sokaklar, tek yönlü ölü uçlar ve küçük kopuk parçalar kaldırılır. Bu işlem grafiği tutarlı ve her noktadan her noktaya erişilebilir hale getirir.

**Hiyerarşik Katmanlama (`build_hierarchy()`):**

Graf iki ayrı katmana bölünür:

| Katman | Yol Tipleri | Kullanım |
|---|---|---|
| **Express** | motorway, motorway_link, trunk, trunk_link | ≥5 km arası aramalar |
| **Arterial** | primary, primary_link, secondary, secondary_link | <5 km arası aramalar |
| **Full** | Express + Arterial birleşimi | Fallback ve görselleştirme |

Her katman için aynı zamanda **ters graf** (reversed) da üretilir. Bidirectional A\* hedeften geriye arama yaparken bu ters grafı kullanır; çalışma anında ters çevirme maliyeti sıfırdır.

İstanbul'un iki kıtalı yapısı nedeniyle, katman oluştururken 100 düğümden büyük tüm bağlantılı bileşenler korunur (sadece en büyüğü değil). Aksi takdirde Avrupa ve Asya yakasının birbirinden kopması riski ortaya çıkar.

**Haversine Önbelleği (`build_heuristic_cache()`):**

`HeuristicCache` nesnesi iki şey içerir:
- `node_coords`: Tüm düğümlerin `{osmid: (lat, lon)}` sözlüğü — O(1) koordinat erişimi.
- `distance_cache`: Daha önce hesaplanmış Haversine mesafelerinin `{(u,v): metre}` sözlüğü — tekrar hesaplama olmaz.

`get_heuristic(cache, u, v)` fonksiyonu A\*'ın iç döngüsünde her adımda çağrılır. Önbellekte varsa O(1), yoksa Haversine hesaplayarak önbelleğe yazar. Önbellek `pickle` formatında diske kaydedilir; sunucu yeniden başladığında sıfırdan hesaplama yapılmaz.

---

### 3. Rota Motoru: AStarEngine

**Dosya:** `core/astar_engine.py`

**Amaç:** İki OSM düğümü arasındaki en kısa rotayı Bidirectional Hierarchical A\* algoritmasıyla bulur.

**Katman Seçimi (`_select_layer()`):**

`find_path()` çağrılır çağrılmaz, kaynak ile hedef arasındaki kuş uçuşu mesafe hesaplanır:
- **< 5 km:** Arterial katmanda arama. Daha küçük arama uzayı.
- **≥ 5 km:** Express katmanda arama. Sadece otoyol/trunk ağı.
- **Fallback:** Seçilen katmanda düğüm bulunamazsa veya rota oluşturulamazsa Full grafa düşülür.

**Bidirectional A\* Çekirdeği (`_bidirectional_astar()`):**

İki ayrı arama durumu (`_SearchState`) tutulur:
- **Forward:** Kaynaktan hedefe doğru.
- **Backward:** Hedeften kaynağa doğru (ters graf üzerinde).

Her adımda iki min-heap'in tepesindeki `f_score` karşılaştırılır; daha küçük olanın yönünden bir düğüm açılır. Bu, her iki yönün de dengeli ilerlemesini sağlar.

**Buluşma ve Durma Koşulu (Pohl, 1971):**
- Her düğüm açıldığında, o düğümün karşı yönün `g_score` sözlüğünde var olup olmadığı kontrol edilir.
- Varsa, bu bir buluşma adayıdır: `μ = g_fwd[m] + g_bwd[m]` hesaplanır.
- **Durma:** `f_fwd_top + f_bwd_top >= μ` koşulu sağlandığında arama kesin optimal sonuçla durur.

**Lazy Deletion:**

Python'un `heapq` modülü `decrease-key` operasyonunu desteklemez. Bunun yerine güncellenmiş düğüm heap'e yeniden `push` edilir. Eski kopya `closed set` kontrolüyle anında atılır. Bu strateji ekstra bellek kullanımına karşılık her adımda O(log n) push garantisi sağlar.

**Kenar Maliyeti (`_get_edge_cost()`):**

MultiDiGraph'ta aynı iki düğüm arasında birden fazla paralel kenar bulunabilir (farklı şeritler, köprüler). Her seferinde bu kenarlar arasından en düşük maliyetli seçilir. Trafik modu aktifse `TrafficManager.get_edge_multiplier()` sonucuyla çarılır. `travel_time` eksikse `length / 13.888` (50 km/s fallback) kullanılır.

**Sezgisel Fonksiyon (`_default_heuristic()`):**

Varsayılan sezgisel Haversine mesafesini `22.22 m/s` (80 km/s) ile bölerek saniyeye çevirir. Bu değer admissible'dır — gerçek yol süresini asla aşmaz (kuş uçuşu mesafe / otoyol hızı, gerçek yol süresinin alt sınırıdır). Dışarıdan `heuristic_fn` enjekte edilirse bu fonksiyonun yerini ONNX sinir ağı alır.

---

### 4. Sinir Ağı Eğitimi: training/

Bu klasördeki modüller, A\*'ın sezgisel fonksiyonunu öğrenen sinir ağının eğitim pipeline'ını oluşturur.

#### dataset_builder.py — Eğitim Verisi Üretimi

Gerçek A\* çalıştırılarak etiketli veri üretilir:
- Graf üzerinde rastgele (source, target) çiftleri seçilir.
- Her çift için A\* ile **gerçek maliyet** (saniye) hesaplanır.
- Bu çiftin `FeatureExtractor.extract()` ile 8 boyutlu özellik vektörü çıkarılır.
- (özellik vektörü, gerçek maliyet) ikilisi eğitim örneği olur.

Mesafe bantlarına göre örnekleme yapılır (0-1 km, 1-5 km, 5-15 km, 15+ km), böylece model her mesafe aralığını dengeli öğrenir.

#### model_arch.py — Model Tanımı

`HeuristicNet` ve `FeatureExtractor` sınıfları bu dosyada tanımlanır (detaylar: [Model Mimarisi](#model-mimarisi-heuristicnet) bölümünde).

#### trainer.py — Eğitim Döngüsü

- **Optimizer:** AdamW (`lr=1e-3`, `weight_decay=1e-4`) — Adam + ağırlık çürümesi ayrıştırması.
- **Kayıp Fonksiyonu:** Huber Loss (SmoothL1, `β=1.0`) — MSE'ye kıyasla aykırı değerlere dayanıklı; seyahat sürelerinin geniş aralığı (10s – 7200s) için idealdir.
- **Öğrenme Oranı Planlaması:** `CosineAnnealingLR` — sabit LR'ye göre keskin minimumlardan kaçınır; eğitim sonunda LR ≈ 0'a yaklaşır.
- **Early Stopping:** Validation loss `patience=10` epoch boyunca iyileşmezse eğitim durur.
- **Gradient Clipping:** `max_norm=1.0` — patlayan gradyan önlemi.
- **Normalizasyon:** Etiketler `log1p(saniye)` ile sıkıştırılır (10s → 2.4, 3600s → 8.2). Inference'da `expm1` ile geri çevrilir.
- **Eğitim Cihazı:** Apple Silicon MPS > CUDA > CPU öncelik sırasıyla otomatik seçim.
- **En iyi model** her epoch sonunda `models/checkpoints/best_heuristic_net.pt` olarak kaydedilir.

#### export_onnx.py — ONNX Dışa Aktarma ve Benchmark

Eğitilen PyTorch modeli ONNX formatına aktarılır:
- **Standart model:** `models/onnx/heuristic_net.onnx`
- **INT8 kuantize model:** `models/onnx/heuristic_net_int8.onnx` (daha hızlı, hafif boyut kaybı)

5000 çalıştırmalık benchmark ile PyTorch ve ONNX Runtime süreleri karşılaştırılır. ONNX Runtime, PyTorch'a kıyasla CPU'da ~10-15x daha düşük çıkarım overhead'i sağlar.

---

### 5. Neural Heuristic: NeuralHeuristic

**Dosya:** `core/neural_heuristic.py`

**Amaç:** Eğitilmiş ONNX modelini A\* motoruna bağlayan sezgisel fonksiyon arayüzü.

**Başlangıç:**

Sınıf başlatıldığında önce kuantize (`int8`) model aranır; yoksa standart model seçilir. ONNX Runtime oturumu (`InferenceSession`) CPU üzerinde başlatılır.

**`__call__(u, v)` — Tekil Tahmin:**

A\* her adımda `h(neighbor, target)` çağırır. Bu fonksiyon:
1. `(u, v)` çiftini Python `dict` önbelleğinde arar → varsa O(1)'de döner.
2. Yoksa `FeatureExtractor.extract(u, v)` ile 8 boyutlu özellik vektörü çıkarır.
3. Vektörü ONNX Runtime'a verir → `float32` tahmin alır.
4. `expm1(pred)` ile log ölçeğinden saniyeye geri çevirir.
5. `max(0.0, ...)` ile admissibility garantisi verir (negatif maliyet imkânsız).
6. Sonucu önbelleğe yazar.

**`predict_batch(pairs)` — Toplu Tahmin:**

`RingPlanner` maliyet matrisini hesaplarken N×N çifti tek ONNX çağrısında işler. `FeatureExtractor.extract_batch()` ile vektörize özellik çıkarımı yapılır; ONNX Runtime'ın paralel işlem gücünden yararlanılır.

---

### 6. Çok Duraklı Rota: RingPlanner

**Dosya:** `core/ring_planner.py`

**Amaç:** N adet kullanıcı seçimli durak arasında **en optimum geçiş sırasını** bularak kapalı (ring) veya açık rota üretir.

**Problem:** Bu bir Gezgin Satıcı Problemi (TSP) örneğidir. Tam çözüm NP-hard olduğundan iki aşamalı yaklaşım uygulanır:

**Aşama 1 — Maliyet Matrisi:**

N×N asimetrik maliyet matrisi oluşturulur. Her `(i, j)` çifti için `NeuralHeuristic.predict_batch()` ile tahmini maliyet hesaplanır. Tüm N×(N-1) çift tek ONNX batch çağrısıyla işlenir.

**Aşama 2 — Nearest Neighbor Heuristic:**

Açgözlü başlangıç sıralaması üretir: Başlangıç noktasından itibaren her adımda henüz ziyaret edilmemiş en yakın noktaya git. O(N²) karmaşıklık. Optimal'den %20-25 uzak ama hızlı bir başlangıç noktası sağlar.

**Aşama 3 — 2-opt Local Search:**

Nearest Neighbor çıktısını iteratif olarak iyileştirir. Tüm `(i, k)` kenar çifti kombinasyonları denenir; `order[i+1..k]` segmenti tersine çevrilince maliyet düşüyorsa kabul edilir. Hiçbir iyileştirme bulunamayana veya `max_2opt_iter` (varsayılan 100) sınırına ulaşana kadar tekrar eder. Genellikle optimal'e %5 içinde ulaşır.

**Açık TSP (Fixed Start & End):** Web arayüzünden gelen sabit başlangıç/bitiş noktalı açık rota isteklerinde ≤6 ara nokta için brute-force (kesin optimal), daha fazlası için Nearest Neighbor + 2-opt uygulanır (`app.py/solve_open_tsp()`).

**Aşama 4 — A\* Segment Hesaplama:**

Optimize edilmiş sıralamaya göre ardışık her waypoint çifti için `AStarEngine.find_path()` çağrılır. Bu, tahmini maliyet değil **gerçek yol rotası** üretir.

**Aşama 5 — Segment Birleştirme:**

Segment sınırlarındaki tekrar eden düğümler atılarak tüm segmentler tek kesintisiz rota listesine birleştirilir.

---

### 7. Trafik Yönetimi: TrafficManager

**Dosya:** `core/traffic_manager.py`

**Amaç:** Her kenar için `travel_time` çarpanı üretir. A\* bu çarpanı kenar maliyetine uygular; tıkanan yollar daha pahalı hale gelir ve algoritma alternatif güzergahları tercih eder.

**Üç Katmanlı Trafik Modeli:**

**1. Saatlik Simülasyon (`_simulate_base_traffic()`):**

Güncel saate göre İstanbul'a özgü trafik profili uygulanır:
- **Sabah zirvesi (07:30–09:30):** Max çarpan 3.5 (pik 08:30'da).
- **Akşam zirvesi (17:30–20:00):** Max çarpan 4.2 (pik 18:30'da).
- **Öğle yoğunluğu (12:00–14:00):** Sabit 1.6 çarpan.
- **Ara saatler / gece:** 1.0–1.3 çarpan.

Yol tipine göre hassasiyet: Otoyollar %90, primary yollar %70, secondary %50, yerel yollar %20 oranında trafik dalgalanmasından etkilenir.

**Boğaz Köprüleri ve Tüneller:** Boylam geçişi (< 29.01° ↔ > 29.01°) tespit edilir. Sabah Asya→Avrupa, akşam Avrupa→Asya yönlerinde çarpan 4.8–5.2'ye kadar çıkar. Geriye doğru tıkanıklık yayılımı: olayın olduğu kenara gelen komşular %60 oranında etkilenir.

**2. Rastgele Olay Simülasyonu (`_generate_simulated_incidents()`):**

Her güncellemede motorway/trunk/primary yollardan rastgele 2-4 kenar seçilir:
- **Kaza (accident):** 5.5–8.5 çarpan — A\* bu yolu neredeyse tamamen kaçınır.
- **Yol çalışması (roadwork):** 4.0–6.0 çarpan.

%30 ihtimalle eski olaylar temizlenerek yeni olaylar üretilir.

**3. TomTom Traffic Flow API (İsteğe Bağlı):**

`configs/settings.yaml` veya `TOMTOM_API_KEY` ortam değişkeni ile API anahtarı tanımlanırsa canlı moda geçilir. İstanbul'un 5 kritik noktası (15 Temmuz Köprüsü, FSM Köprüsü, Mecidiyeköy, Kadıköy E-5, Haliç Köprüsü) sorgulanır. `freeFlowSpeed / currentSpeed` oranı çarpan olarak hesaplanır ve 500 metre yarıçapındaki motorway/primary kenarlara uygulanır.

---

### 8. Web Arayüzü: app.py + Flask

**Dosya:** `app.py`

**Amaç:** Tüm bileşenleri bir araya getiren REST API sunucusu ve web arayüzü.

**Sunucu Başlangıcında Yapılanlar:**

Sunucu başladığında tek seferlik yükleme yapılır:
1. `MapLoader` → Graf diskten yüklenir.
2. `GraphProcessor` → Hiyerarşi ve Haversine önbelleği oluşturulur.
3. `TrafficManager` → Trafik çarpanları ilk kez hesaplanır.
4. İki ayrı planlayıcı hazırlanır:
   - **Neural:** `NeuralHeuristic` + `AStarEngine` + `RingPlanner`
   - **Haversine:** Fallback `NeuralHeuristic` (Haversine tabanlı) + `AStarEngine` + `RingPlanner`

**API Uç Noktaları:**

| Uç Nokta | Yöntem | Açıklama |
|---|---|---|
| `GET /` | GET | Interaktif Leaflet.js haritası |
| `GET /api/landmarks` | GET | 10 önceden tanımlı İstanbul noktasının listesi |
| `GET /api/traffic` | GET | Mevcut trafik segment ve olay verileri |
| `POST /api/route` | POST | Rota hesaplama (waypoint listesi + seçenekler) |

`POST /api/route` isteği şu parametreleri kabul eder:
- `waypoints`: `[{lat, lng, name}]` listesi (en az 2 nokta)
- `use_haversine`: `true` ise Neural yerine Haversine sezgisel kullan
- `is_loop`: `true` ise kapalı ring rota, `false` ise açık rota
- `start_index` / `end_index`: Açık rotada başlangıç/bitiş indeksi
- `use_traffic`: `true` ise trafik çarpanları kenar maliyetlerine uygulanır

---

### 9. Görselleştirme: MapRenderer

**Dosya:** `visualization/map_renderer.py`

**Amaç:** Hesaplanan ring rotayı Folium kullanarak interaktif HTML haritasına dönüştürür.

Waypoint markerları, rota segmentleri ve isteğe bağlı trafik ısı haritası (heatmap) katmanı desteklenir. CLI modunda çıktı `output/istanbul_ring.html` olarak kaydedilir.

---

## Veri Akışı (Uçtan Uca)

```
1. Kullanıcı haritada nokta işaretler
        │
        ▼
2. POST /api/route → [{lat, lng, name}, ...]
        │
        ▼
3. Her koordinat en yakın OSM düğümüne eşlenir
   ox.distance.nearest_nodes(full_graph, X=lon, Y=lat)
        │
        ▼
4. RingPlanner.plan(waypoint_nodes)
   ├── NeuralHeuristic.predict_batch(N×N çiftler) → maliyet matrisi
   ├── Nearest Neighbor → başlangıç sırası
   └── 2-opt iterasyon → optimize sıra
        │
        ▼
5. AStarEngine.find_path(src, tgt) × N segment
   ├── Katman seçimi (mesafeye göre express/arterial)
   ├── Bidirectional A* (NeuralHeuristic sezgisel)
   │   ├── Forward heap: source → target
   │   └── Backward heap: target → source (ters graf)
   ├── Pohl durma koşulu → buluşma düğümü
   └── _reconstruct_path() → OSM düğüm listesi
        │
        ▼
6. Segment koordinatları JSON formatında döner
        │
        ▼
7. Leaflet.js haritada polyline olarak çizilir
```

---

## Algoritma Detayları

### Bidirectional A\*

Klasik A\*'da arama uzayı O(b^d) düğüm açar (b: ortalama dallanma faktörü, d: derinlik). Bidirectional versiyonda her yön O(b^(d/2)) açar; toplam O(2·b^(d/2)) ≈ karesel kazanım.

İstanbul grafında (yaklaşık 8.000 düğüm) bu, 10-50x hız farkı anlamına gelir.

Heap içeriği `(f_score, counter, node_id)` üçlüsüdür. `counter`, eşit f_score'lu düğümlerde deterministik FIFO sırası sağlar.

### Hiyerarşik Graf Katmanlama

5 km eşiği, şehir içi kısa mesafeli aramalar (arterial) ile kıtalar arası uzun mesafeli aramalar (express) arasındaki doğal ayrımdır. Express katmanı ortalama %60 daha küçük arama uzayı sunar.

### Neural Heuristic

Klasik Haversine sezgiselinin yerini alan sinir ağı, aynı admissibility garantisini korurken şu ek bilgileri öğrenir:
- Kaynak ve hedef düğümlerin yol hiyerarşisindeki yeri (highway_rank)
- Kavşak yoğunluğu (derece bilgisi)
- Yön bilgisi (bearing) — özellikle Boğaz geçişi gibi doğu-batı yönlü rotalar için anlamlı
- Gerçek A\* maliyetiyle eğitildiğinden İstanbul'a özgü topolojiyi öğrenir

Bu sayede A\* daha isabetli düğümleri önce açar ve toplam açılan düğüm sayısını azaltır.

### TSP Çözümü: Nearest Neighbor + 2-opt

| Seçenek | Kullanım | Karmaşıklık | Kalite |
|---|---|---|---|
| Brute-force | ≤6 ara nokta | O(n!) | Kesin optimal |
| Nearest Neighbor | >6 ara nokta | O(n²) | Optimal'den ~%20-25 uzak |
| 2-opt iyileştirme | Her zaman | O(n²·iter) | Optimal'e ~%5 içinde |

### Trafik Simülasyonu

Trafik çarpanları `travel_time` değeriyle çarpılır. Çarpan 1.0 = serbest akış, 5.0 = ciddi yoğunluk, 8.5 = kaza/blokaj. A\* bu maliyetleri doğrudan hesaba katar; tıkanan yollar yerine alternatif güzergahlar tercih edilir.

---

## Özellik Mühendisliği

Her (source, target) düğüm çifti için `FeatureExtractor` 8 boyutlu vektör üretir:

| İndeks | Özellik | Normalizasyon | Açıklama |
|---|---|---|---|
| [0] | Haversine mesafesi | ÷ 80,000 m | İstanbul çapı ~80 km |
| [1] | Δlat | ÷ 2.0 | Enlem farkı |
| [2] | Δlon | ÷ 2.0 | Boylam farkı |
| [3] | Source düğüm derecesi | ÷ 8 | Kavşak yoğunluğu |
| [4] | Target düğüm derecesi | ÷ 8 | Kavşak yoğunluğu |
| [5] | Source highway_rank ortalaması | ÷ 5.0 | Yol hiyerarşisi skoru |
| [6] | Target highway_rank ortalaması | ÷ 5.0 | Yol hiyerarşisi skoru |
| [7] | Bearing açısı (radyan) | ÷ π | Yön bilgisi [-1, 1] |

Koordinatlar, dereceler ve highway_rank'lar başlangıçta önbelleklenir; her çıkarmada graf taranmaz.

---

## Model Mimarisi: HeuristicNet

```
Input(8)
   │
   ▼
InputProjection: Linear(8→128) + LayerNorm + GELU
   │
   ▼
ResidualBlock × 3:
   ┌─────────────────────────┐
   │ Linear(128→128)         │
   │ LayerNorm               │
   │ GELU                    │
   │ Dropout(0.1)            │
   │ Linear(128→128)         │
   │ LayerNorm               │
   └─────────────────────────┘
   x → x + F(x) → GELU   (skip connection)
   │
   ▼
OutputHead: Linear(128→64) + GELU + Linear(64→1) + Softplus
   │
   ▼
Output: tahmini maliyet (log1p-normalize edilmiş saniye)
```

**Tasarım Kararları:**
- **MLP (Multilayer Perceptron):** GNN alternatifinın aksine ONNX export için ek bağımlılık gerektirmez ve A\*'ın iç döngüsünde ~0.1ms inference süresi sunar (GNN'in yaklaşık 50 katı hızında).
- **ResidualBlock:** Skip connection gradyan akışını stabilize eder. LayerNorm, BatchNorm'un küçük batch'lerde yaşadığı istatistik sorununu ortadan kaldırır. GELU, negatif bölgede yumuşak geçişiyle ReLU'ya tercih edilir.
- **Softplus çıkış aktivasyonu:** `log(1 + e^x)` — her zaman pozitif çıktı garantisi. Maliyet negatif olamaz; ReLU'nun sıfır-gradyan bölgesinden kaçınır.
- **Xavier başlatma:** GELU aktivasyonu için Kaiming'e göre daha stabil başlangıç ağırlıkları.
- **Toplam parametre:** ~100K (hafif, hızlı inference için optimize).

---

## Önbellekleme Stratejisi

Sistem üç katmanlı önbellekleme kullanır:

| Katman | Sınıf | Amaç | Kalıcılık |
|---|---|---|---|
| **Koordinat önbelleği** | `HeuristicCache.node_coords` | Haversine hesabı için O(1) koordinat erişimi | Pickle (disk) |
| **Haversine önbelleği** | `HeuristicCache.distance_cache` | Aynı düğüm çifti için tekrar hesaplama yok | Pickle (disk) |
| **Neural tahmin önbelleği** | `NeuralHeuristic._pred_cache` | Aynı (u,v) için ONNX çağrısı tekrarı yok | Bellekte (uçucu) |

`NeuralHeuristic.get_stats()` ile önbellekte isabet oranı (`hit_rate`) izlenebilir.

---

## Kurulum ve Çalıştırma

### Gereksinimler

```
Python >= 3.10
```

### Bağımlılıklar

```
# Harita & Graf
osmnx>=1.9.0
networkx>=3.3
shapely>=2.0
geopandas>=0.14
rtree>=1.2

# Yapay Zeka
torch>=2.3          # Apple Silicon MPS desteği için
onnxruntime>=1.18
onnx>=1.16

# Web Sunucusu
flask
flask-cors

# Görselleştirme
folium>=0.17

# Geliştirme
pytest>=8.0
pyyaml>=6.0
```

### Adım Adım Kurulum

```bash
# 1. Sanal ortam oluştur
python3 -m venv .venv
source .venv/bin/activate

# 2. Bağımlılıkları kur
pip install osmnx networkx shapely geopandas rtree \
            torch onnxruntime onnx \
            flask flask-cors folium pyyaml pytest

# 3. Harita verisini çek (ilk kez, ~2-5 dakika sürer)
python main.py --mode fetch

# 4. Modeli eğit (isteğe bağlı, ~10-30 dakika)
python main.py --mode train --epochs 100 --samples 800

# 5. Modeli ONNX'e aktar
python main.py --mode export --quantize

# 6. Web sunucusunu başlat
python main.py --mode server
```

### TomTom Canlı Trafik (İsteğe Bağlı)

```bash
# Ortam değişkeni olarak
export TOMTOM_API_KEY="your_api_key_here"
python main.py --mode server
```

Veya `configs/settings.yaml` dosyasına:
```yaml
tomtom_api_key: "your_api_key_here"
```

---

## Komut Satırı Kullanımı

```bash
# Harita verisini OSMnx'ten çek
python main.py --mode fetch

# Modeli eğit (özel parametre)
python main.py --mode train --epochs 80 --samples 600

# ONNX export + INT8 kuantizasyon + benchmark
python main.py --mode export --quantize

# Rota hesapla ve HTML haritasına render et
python main.py --mode route --waypoints "Taksim,Kadıköy,Beşiktaş,Üsküdar"

# Klasik Haversine ile rota (neural heuristic kullanma)
python main.py --mode route --haversine --waypoints "Taksim,Sarıyer"

# Web arayüzünü özel portta başlat
python main.py --mode server --port 8080

# Tüm adımları sırayla çalıştır
python main.py --mode all
```

---

## API Uç Noktaları

### GET /api/landmarks

Önceden tanımlı 10 İstanbul noktasını döner.

```json
{
  "success": true,
  "landmarks": [
    {"name": "Taksim", "lat": 41.0369, "lng": 28.9784},
    ...
  ]
}
```

### GET /api/traffic

Mevcut trafik durumunu döner.

```json
{
  "success": true,
  "segments": [
    {
      "u": 12345, "v": 67890,
      "highway": "motorway",
      "multiplier": 3.2,
      "status": "heavy",
      "color": "#dc2626",
      "coords": [[41.05, 29.01], ...]
    }
  ],
  "incidents": [
    {"id": 1, "lat": 41.04, "lng": 28.98, "type": "accident", "name": "Trafik Kazası 💥", "multiplier": 7.2}
  ]
}
```

### POST /api/route

```json
// İstek
{
  "waypoints": [
    {"lat": 41.0369, "lng": 28.9784, "name": "Taksim"},
    {"lat": 40.9906, "lng": 29.0264, "name": "Kadıköy"}
  ],
  "use_haversine": false,
  "is_loop": true,
  "use_traffic": true
}

// Yanıt
{
  "success": true,
  "total_length_km": 18.4,
  "total_time_min": 32.0,
  "elapsed_ms": 245.3,
  "waypoints_ordered": [...],
  "segments": [
    {
      "segment_index": 0,
      "found": true,
      "path_coords": [[41.03, 28.97], ...],
      "total_length_m": 9200.0,
      "total_time_s": 960.0,
      "nodes_explored": 412,
      "elapsed_ms": 120.1
    }
  ],
  "optimization_log": ["Nearest Neighbor başlangıç maliyeti: 1842.3", "2-opt bitti. 4 iterasyon | final: 1788.1"]
}
```

---

## Proje Dizin Yapısı

```
istanbul-route-optimizer/
│
├── main.py                     # CLI giriş noktası
├── app.py                      # Flask web sunucusu
├── start_up.sh                 # Hızlı başlatma betiği
│
├── core/
│   ├── map_loader.py           # OSMnx harita veri çekici
│   ├── graph_processor.py      # Hiyerarşik katmanlama + önbellek
│   ├── astar_engine.py         # Bidirectional Hierarchical A*
│   ├── neural_heuristic.py     # ONNX sezgisel entegrasyon
│   ├── ring_planner.py         # TSP: Nearest Neighbor + 2-opt
│   └── traffic_manager.py      # Trafik simülasyon + TomTom API
│
├── training/
│   ├── model_arch.py           # HeuristicNet + FeatureExtractor
│   ├── dataset_builder.py      # A* ile etiketli veri üretimi
│   ├── trainer.py              # PyTorch eğitim döngüsü
│   └── export_onnx.py          # ONNX export + benchmark
│
├── visualization/
│   └── map_renderer.py         # Folium HTML harita renderer
│
├── templates/
│   └── index.html              # Leaflet.js interaktif arayüz
│
├── static/
│   ├── css/                    # Arayüz stilleri
│   └── js/                     # Arayüz JS mantığı
│
├── tests/
│   ├── test_astar_engine.py
│   ├── test_map_loader.py
│   ├── test_neural_heuristic.py
│   └── test_traffic_manager.py
│
├── configs/
│   └── settings.yaml           # API anahtarları ve ayarlar
│
├── data/
│   ├── raw/                    # istanbul_main_arteries.graphml
│   └── processed/              # Katman graflar + Haversine önbellek
│
├── models/
│   ├── checkpoints/            # best_heuristic_net.pt
│   └── onnx/                   # heuristic_net.onnx + int8
│
├── logs/                       # run.log
├── notebooks/                  # Keşif notebook'ları
├── .gitignore
└── README.md
```

---

## Landmark Koordinatları

| İsim | Enlem | Boylam |
|---|---|---|
| Taksim | 41.0369 | 28.9784 |
| Kadıköy | 40.9906 | 29.0264 |
| Beşiktaş | 41.0430 | 29.0058 |
| Üsküdar | 41.0267 | 29.0184 |
| Fatih | 41.0193 | 28.9397 |
| Bakırköy | 40.9819 | 28.8772 |
| Şişli | 41.0602 | 28.9877 |
| Ataşehir | 40.9923 | 29.1244 |
| Sarıyer | 41.1657 | 29.0518 |
| Bağcılar | 41.0390 | 28.8560 |
