/**
 * İstRoute — Interactive UI Logic
 */

// Global Uygulama Durumu (State)
const state = {
    waypoints: [],         // Kullanıcının eklediği noktalar { lat, lng, name }
    map: null,             // Leaflet harita nesnesi
    markers: [],           // Haritadaki waypoint marker'ları
    polylines: [],         // Çizilen rota segment çizgileri
    clickMarker: null,     // Haritada tıklanan geçici yer işareti
    theme: 'dark',         // Tema: 'dark' | 'light'
    tileLayer: null,       // Harita katman nesnesi
    favorites: JSON.parse(localStorage.getItem('favorites')) || [], // Favori konumlar
    isLoop: true,          // Çembersel rota mı (başladığın yere dön)
    startIndex: 0,         // Başlangıç noktası indeksi
    endIndex: 0,           // Bitiş noktası indeksi (Açık rotalarda kullanılır)
    lang: 'tr',            // Dil: 'tr' | 'en'
    trafficOverlayActive: false, // Canlı trafik katmanı aktif mi
    trafficRouteActive: false,   // Rotalamada trafik hesaba katılsın mı
    trafficLines: [],      // Haritadaki trafik segment çizgileri
    trafficIncidentMarkers: [], // Haritadaki kaza/çalışma işaretleri
    trafficTimer: null,    // Trafik güncelleme timer'ı
    trafficLayerGroup: null,      // Trafik şeritleri LayerGroup
    trafficIncidentGroup: null    // Trafik kaza/olayları LayerGroup
};

const translations = {
    tr: {
        title: "İstRoute",
        subtitle: "Neural A* Rota Planlayıcı",
        addLocation: "Konum Ekle",
        locationDesc: "Haritadan bir noktaya tıklayın veya enlem/boylam girin:",
        placeholder: "Örn: 41.0369, 28.9784",
        addButton: "Ekle",
        popularLocations: "Favori Konumlar",
        noFavorites: "Henüz favori konum eklenmedi.",
        addFav: "Favorilere Ekle",
        removeFav: "Favorilerden Çıkar",
        waypointsTitle: "Uğranacak Konumlar",
        clearAll: "Tümünü Sil",
        emptyStateText: "Henüz konum eklenmedi.",
        emptyStateSub: "Haritaya tıklayarak veya yukarıdan koordinat girerek ilk konumunuzu ekleyin.",
        settingsTitle: "Optimizasyon Ayarları",
        heuristicLabel: "Algoritma Sezgisel (Heuristic)",
        neuralText: "Neural Heuristic (ONNX)",
        classicText: "Haversine Heuristic (Klasik A*)",
        routeModeLabel: "Rota Modu",
        loopText: "Başladığın Yere Dön (Çembersel)",
        openText: "Açık Rota (Sabit Başlangıç/Bitiş)",
        optimizeBtn: "Rotayı Optimize Et",
        optimizingBtn: "Optimize Ediliyor...",
        analysisTitle: "Rota Analizi",
        distanceLabel: "Toplam Mesafe",
        durationLabel: "Tahmini Süre",
        timeLabel: "Optimizasyon Süresi",
        segmentsLabel: "Segment Sayısı",
        logsButton: "Optimizasyon Logları (2-opt)",
        mapOverlay: "Haritaya tıklayarak doğrudan koordinat alabilir, ardından \"Ekle\" ile uğranacak yerlere ekleyebilirsiniz.",
        errorMinWps: "En az 2 adet koordinat girilmelidir.",
        alertCoords: "Lütfen geçerli İstanbul koordinatları girin! (Enlem: 40-42, Boylam: 28-30)",
        alertFormat: "Lütfen koordinatları \"Enlem, Boylam\" formatında girin! (Örn: 41.0369, 28.9784)",
        alertServer: "Rota optimizasyon sunucusu ile bağlantı kurulamadı. Sunucunun çalıştığından emin olun.",
        alertOptError: "Optimizasyon hatası: ",
        startLabel: "Başlangıç",
        endLabel: "Bitiş",
        waypointLabel: "Durak",
        segmentLabel: "Segment",
        foundLabel: "Bulundu",
        notFoundLabel: "Bulunamadı",
        secLabel: "saniye",
        minLabel: "dakika",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "OSM ID",
        deleteLabel: "Noktayı Sil",
        startBadgeTitle: "Başlangıç Noktası Yap",
        endBadgeTitle: "Bitiş Noktası Yap",
        popupSelectedCoord: "Seçilen Konum",
        popupSelectedDesc: "Ekle butonuna basarak rota listenize ekleyebilirsiniz.",
        offlineWarningText: "Şu an internete bağlı olmadığınız için canlı trafik verisi ile arama yaparsanız aktif sonuca ulaşamayabilirsiniz.",
        trafficOverlayLabel: "Canlı Trafik Katmanı",
        trafficRouteLabel: "Trafik Duyarlı Rotalama",
        trafficOverlayOn: "Trafiği Göster",
        trafficOverlayOff: "Trafiği Gizle",
        trafficRouteOn: "Trafikten Kaçın",
        trafficRouteOff: "En Hızlı Yol (Trafiksiz)"
    },
    en: {
        title: "IstRoute",
        subtitle: "Neural A* Route Planner",
        addLocation: "Add Location",
        locationDesc: "Click a point on the map or enter latitude/longitude:",
        placeholder: "e.g. 41.0369, 28.9784",
        addButton: "Add",
        popularLocations: "Favorite Locations",
        noFavorites: "No favorite locations added yet.",
        addFav: "Add Favorite",
        removeFav: "Remove Favorite",
        waypointsTitle: "Waypoints to Visit",
        clearAll: "Clear All",
        emptyStateText: "No locations added yet.",
        emptyStateSub: "Click on the map or enter coordinates above to add your first location.",
        settingsTitle: "Optimization Settings",
        heuristicLabel: "Algorithm Heuristic",
        neuralText: "Neural Heuristic (ONNX)",
        classicText: "Haversine Heuristic (Classic A*)",
        routeModeLabel: "Route Mode",
        loopText: "Return to Start (Closed Loop)",
        openText: "Open Path (Fixed Start/End)",
        optimizeBtn: "Optimize Route",
        optimizingBtn: "Optimizing...",
        analysisTitle: "Route Analysis",
        distanceLabel: "Total Distance",
        durationLabel: "Estimated Time",
        timeLabel: "Optimization Time",
        segmentsLabel: "Segments Count",
        logsButton: "Optimization Logs (2-opt)",
        mapOverlay: "Click on the map to automatically copy coordinates, then click \"Add\" to include them.",
        errorMinWps: "At least 2 coordinates must be entered.",
        alertCoords: "Please enter valid Istanbul coordinates! (Lat: 40-42, Lng: 28-30)",
        alertFormat: "Please enter coordinates in \"Latitude, Longitude\" format! (e.g. 41.0369, 28.9784)",
        alertServer: "Could not connect to route optimization server. Make sure it is running.",
        alertOptError: "Optimization error: ",
        startLabel: "Start",
        endLabel: "End",
        waypointLabel: "Stop",
        segmentLabel: "Segment",
        foundLabel: "Found",
        notFoundLabel: "Not Found",
        secLabel: "seconds",
        minLabel: "minutes",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "OSM ID",
        deleteLabel: "Delete Point",
        startBadgeTitle: "Set as Start Point",
        endBadgeTitle: "Set as End Point",
        popupSelectedCoord: "Selected Location",
        popupSelectedDesc: "Click the Add button to include this in your route.",
        offlineWarningText: "Since you are currently offline, you may not get active results if you search with live traffic data.",
        trafficOverlayLabel: "Live Traffic Overlay",
        trafficRouteLabel: "Traffic-Aware Routing",
        trafficOverlayOn: "Show Traffic",
        trafficOverlayOff: "Hide Traffic",
        trafficRouteOn: "Avoid Traffic",
        trafficRouteOff: "Fastest Path (No Traffic)"
    },
    ar: {
        title: "إستروت",
        subtitle: "مخطط مسار A* العصبي",
        addLocation: "إضافة موقع",
        locationDesc: "انقر على الخريطة أو أدخل خط العرض/خط الطول:",
        placeholder: "مثال: 41.0369, 28.9784",
        addButton: "إضافة",
        popularLocations: "المواقع المفضلة",
        noFavorites: "لم يتم إضافة أي مواقع مفضلة بعد.",
        waypointsTitle: "النقاط المراد زيارتها",
        clearAll: "مسح الكل",
        emptyStateText: "لم يتم إضافة مواقع بعد.",
        emptyStateSub: "انقر على الخريطة أو أدخل الإحداثيات أعلاه لإضافة أول موقع لك.",
        settingsTitle: "إعدادات التحسين",
        heuristicLabel: "خوارزمية الاستدلال",
        neuralText: "الاستدلال العصبي (ONNX)",
        classicText: "استدلال هافيرسين (A* الكلاسيكي)",
        routeModeLabel: "وضع المسار",
        loopText: "العودة إلى البداية (حلقة مغلقة)",
        openText: "مسار مفتوح (بداية/نهاية ثابتة)",
        optimizeBtn: "تحسين المسار",
        optimizingBtn: "جاري التحسين...",
        analysisTitle: "تحليل المسار",
        distanceLabel: "المسافة الإجمالية",
        durationLabel: "الوقت المقدر",
        timeLabel: "وقت التحسين",
        segmentsLabel: "عدد المقاطع",
        logsButton: "سجلات التحسين (2-opt)",
        mapOverlay: "انقر على الخريطة لنسخ الإحداثيات تلقائيًا، ثم انقر فوق \"إضافة\" لإدراجها.",
        errorMinWps: "يجب إدخال إحداثياتين على الأقل.",
        alertCoords: "يرجى إدخال إحداثيات صالحة لإسطنبول! (العرض: 40-42، الطول: 28-30)",
        alertFormat: "يرجى إدخال الإحداثيات بصيغة \"خط العرض، خط الطول\"! (مثال: 41.0369، 28.9784)",
        alertServer: "تعذر الاتصال بخادم تحسين المسار. تأكد من أنه قيد التشغيل.",
        alertOptError: "خطأ في التحسين: ",
        startLabel: "بداية",
        endLabel: "نهاية",
        waypointLabel: "توقف",
        segmentLabel: "مقطع",
        foundLabel: "تم العثور",
        notFoundLabel: "لم يتم العثور",
        secLabel: "ثانية",
        minLabel: "دقيقة",
        kmLabel: "كم",
        msLabel: "ملي ثانية",
        osmIdLabel: "معرف OSM",
        deleteLabel: "حذف النقطة",
        startBadgeTitle: "تعيين كنقطة بداية",
        endBadgeTitle: "تعيين كنقطة نهاية",
        popupSelectedCoord: "الموقع المحدد",
        popupSelectedDesc: "انقر فوق زر الإضافة لتضمين هذا في مسارك.",
        offlineWarningText: "بما أنك غير متصل بالإنترنت حاليًا، فقد لا تحصل على نتائج دقيقة إذا قمت بالبحث باستخدام بيانات المرور المباشرة."
    },
    es: {
        title: "IstRoute",
        subtitle: "Planificador Neuronal de Rutas A*",
        addLocation: "Añadir Ubicación",
        locationDesc: "Haga clic en el mapa o ingrese latitud/longitud:",
        placeholder: "Ej: 41.0369, 28.9784",
        addButton: "Añadir",
        popularLocations: "Lugares Favoritos",
        noFavorites: "Aún no se han añadido lugares favoritos.",
        waypointsTitle: "Puntos a Visitar",
        clearAll: "Borrar Todo",
        emptyStateText: "Aún no se han añadido ubicaciones.",
        emptyStateSub: "Haga clic en el mapa o ingrese las coordenadas arriba para añadir su primera ubicación.",
        settingsTitle: "Ajustes de Optimización",
        heuristicLabel: "Algoritmo Heurístico",
        neuralText: "Heurística Neuronal (ONNX)",
        classicText: "Heurística Haversine (A* Clásico)",
        routeModeLabel: "Modo de Ruta",
        loopText: "Volver al Inicio (Bucle Cerrado)",
        openText: "Ruta Abierta (Inicio/Fin Fijo)",
        optimizeBtn: "Optimizar Ruta",
        optimizingBtn: "Optimizando...",
        analysisTitle: "Análisis de Ruta",
        distanceLabel: "Distancia Total",
        durationLabel: "Tiempo Estimado",
        timeLabel: "Tiempo de Optimización",
        segmentsLabel: "Número de Segmentos",
        logsButton: "Registros de Optimización (2-opt)",
        mapOverlay: "Haga clic en el mapa para copiar las coordenadas automáticamente, luego haga clic en \"Añadir\" para incluirlas.",
        errorMinWps: "Se deben ingresar al menos 2 coordenadas.",
        alertCoords: "¡Ingrese coordenadas válidas de Estambul! (Lat: 40-42, Lng: 28-30)",
        alertFormat: "¡Ingrese las coordenadas en formato \"Latitud, Longitud\"! (Ej: 41.0369, 28.9784)",
        alertServer: "No se pudo conectar al servidor de optimización de rutas. Asegúrese de que esté funcionando.",
        alertOptError: "Error de optimización: ",
        startLabel: "Inicio",
        endLabel: "Fin",
        waypointLabel: "Parada",
        segmentLabel: "Segmento",
        foundLabel: "Encontrado",
        notFoundLabel: "No encontrado",
        secLabel: "segundos",
        minLabel: "minutos",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "ID de OSM",
        deleteLabel: "Eliminar Punto",
        startBadgeTitle: "Establecer como Punto de Inicio",
        endBadgeTitle: "Establecer como Punto Final",
        popupSelectedCoord: "Ubicación Seleccionada",
        popupSelectedDesc: "Haga clic en el botón Añadir para incluir esto en su ruta.",
        offlineWarningText: "Dado que actualmente no tienes conexión, es posible que no obtengas resultados precisos si buscas con datos de tráfico en vivo."
    },
    de: {
        title: "IstRoute",
        subtitle: "Neuronaler A*-Routenplaner",
        addLocation: "Ort hinzufügen",
        locationDesc: "Klicken Sie auf die Karte oder geben Sie Breitengrad/Längengrad ein:",
        placeholder: "z.B. 41.0369, 28.9784",
        addButton: "Hinzufügen",
        popularLocations: "Lieblingsorte",
        noFavorites: "Noch keine Lieblingsorte hinzugefügt.",
        waypointsTitle: "Zu besuchende Punkte",
        clearAll: "Alles löschen",
        emptyStateText: "Noch keine Orte hinzugefügt.",
        emptyStateSub: "Klicken Sie auf die Karte oder geben Sie oben Koordinaten ein, um Ihren ersten Ort hinzuzufügen.",
        settingsTitle: "Optimierungseinstellungen",
        heuristicLabel: "Heuristischer Algorithmus",
        neuralText: "Neuronale Heuristik (ONNX)",
        classicText: "Haversine-Heuristik (Klassisches A*)",
        routeModeLabel: "Routenmodus",
        loopText: "Zum Start zurückkehren (Rundroute)",
        openText: "Offene Route (Start/Ziel fest)",
        optimizeBtn: "Route optimieren",
        optimizingBtn: "Optimierung...",
        analysisTitle: "Routenanalyse",
        distanceLabel: "Gesamtstrecke",
        durationLabel: "Geschätzte Zeit",
        timeLabel: "Optimierungszeit",
        segmentsLabel: "Anzahl der Segmente",
        logsButton: "Optimierungsprotokolle (2-opt)",
        mapOverlay: "Klicken Sie auf die Karte, um Koordinaten automatisch zu kopieren, und klicken Sie dann auf \"Hinzufügen\", um sie einzufügen.",
        errorMinWps: "Es müssen mindestens 2 Koordinaten eingegeben werden.",
        alertCoords: "Bitte geben Sie gültige Koordinaten für Istanbul ein! (Breite: 40-42, Länge: 28-30)",
        alertFormat: "Bitte geben Sie Koordinaten im Format \"Breitengrad, Längengrad\" ein! (z.B. 41.0369, 28.9784)",
        alertServer: "Verbindung zum Routenoptimierungsserver fehlgeschlagen. Stellen Sie sicher, dass er läuft.",
        alertOptError: "Optimierungsfehler: ",
        startLabel: "Start",
        endLabel: "Ende",
        waypointLabel: "Halt",
        segmentLabel: "Segment",
        foundLabel: "Gefunden",
        notFoundLabel: "Nicht gefunden",
        secLabel: "Sekunden",
        minLabel: "Minuten",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "OSM ID",
        deleteLabel: "Punkt löschen",
        startBadgeTitle: "Als Startpunkt festlegen",
        endBadgeTitle: "Als Endpunkt festlegen",
        popupSelectedCoord: "Ausgewählter Ort",
        popupSelectedDesc: "Klicken Sie auf Hinzufügen, um dies in Ihre Route aufzunehmen.",
        offlineWarningText: "Da Sie derzeit offline sind, erhalten Sie möglicherweise keine aktuellen Ergebnisse, wenn Sie mit Live-Verkehrsdaten suchen."
    },
    ru: {
        title: "IstRoute",
        subtitle: "Нейронный планировщик маршрутов A*",
        addLocation: "Добавить место",
        locationDesc: "Нажмите на карту или введите широту/долготу:",
        placeholder: "Например: 41.0369, 28.9784",
        addButton: "Добавить",
        popularLocations: "Избранные места",
        noFavorites: "Избранные места еще не добавлены.",
        waypointsTitle: "Точки для посещения",
        clearAll: "Очистить все",
        emptyStateText: "Места еще не добавлены.",
        emptyStateSub: "Нажмите на карту или введите координаты выше, чтобы добавить первое место.",
        settingsTitle: "Настройки оптимизации",
        heuristicLabel: "Эвристический алгоритм",
        neuralText: "Нейронная эвристика (ONNX)",
        classicText: "Эвристика Гаверсинуса (Классический A*)",
        routeModeLabel: "Режим маршрута",
        loopText: "Вернуться к началу (Замкнутый)",
        openText: "Открытый маршрут (Фикс. старт/финиш)",
        optimizeBtn: "Оптимизировать маршрут",
        optimizingBtn: "Оптимизация...",
        analysisTitle: "Анализ маршрута",
        distanceLabel: "Общее расстояние",
        durationLabel: "Оценочное время",
        timeLabel: "Время оптимизации",
        segmentsLabel: "Количество сегментов",
        logsButton: "Логи оптимизации (2-opt)",
        mapOverlay: "Нажмите на карту, чтобы автоматически скопировать координаты, затем нажмите «Добавить», чтобы включить их.",
        errorMinWps: "Необходимо ввести как минимум 2 координаты.",
        alertCoords: "Пожалуйста, введите корректные координаты Стамбула! (Широта: 40-42, Долгота: 28-30)",
        alertFormat: "Пожалуйста, введите координаты в формате «Широта, Долгота»! (Например: 41.0369, 28.9784)",
        alertServer: "Не удалось подключиться к серверу оптимизации маршрутов. Убедитесь, что он запущен.",
        alertOptError: "Ошибка оптимизации: ",
        startLabel: "Старт",
        endLabel: "Финиш",
        waypointLabel: "Остановка",
        segmentLabel: "Сегмент",
        foundLabel: "Найдено",
        notFoundLabel: "Не найдено",
        secLabel: "сек.",
        minLabel: "мин.",
        kmLabel: "км",
        msLabel: "мс",
        osmIdLabel: "OSM ID",
        deleteLabel: "Удалить точку",
        startBadgeTitle: "Сделать стартовой точкой",
        endBadgeTitle: "Сделать конечной точкой",
        popupSelectedCoord: "Выбранное место",
        popupSelectedDesc: "Нажмите кнопку «Добавить», чтобы включить это в ваш маршрут.",
        offlineWarningText: "Поскольку вы сейчас не в сети, вы можете не получить актуальные результаты при поиске с живыми данными о трафике."
    },
    zh: {
        title: "IstRoute",
        subtitle: "神经引导 A* 路线规划器",
        addLocation: "添加位置",
        locationDesc: "点击地图或输入纬度/经度：",
        placeholder: "例如: 41.0369, 28.9784",
        addButton: "添加",
        popularLocations: "收藏位置",
        noFavorites: "暂无收藏位置。",
        waypointsTitle: "待访问点",
        clearAll: "清除全部",
        emptyStateText: "尚未添加位置。",
        emptyStateSub: "点击地图或在上方输入坐标来添加您的第一个位置。",
        settingsTitle: "优化设置",
        heuristicLabel: "启发式算法",
        neuralText: "神经启发式 (ONNX)",
        classicText: "大圆航线启发式 (经典 A*)",
        routeModeLabel: "路线模式",
        loopText: "返回起点 (闭环)",
        openText: "开放路径 (固定起点/终点)",
        optimizeBtn: "优化路线",
        optimizingBtn: "优化中...",
        analysisTitle: "路线分析",
        distanceLabel: "总距离",
        durationLabel: "预计时间",
        timeLabel: "优化用时",
        segmentsLabel: "路段数量",
        logsButton: "优化日志 (2-opt)",
        mapOverlay: "点击地图自动复制坐标，然后点击“添加”进行包含。",
        errorMinWps: "必须输入至少 2 个坐标。",
        alertCoords: "请输入有效的伊斯坦布尔坐标！（纬度：40-42，经度：28-30）",
        alertFormat: "请使用“纬度, 经度”格式输入坐标！（例如：41.0369, 28.9784）",
        alertServer: "无法连接到路线优化服务器。请确保其正在运行。",
        alertOptError: "优化错误：",
        startLabel: "起点",
        endLabel: "终点",
        waypointLabel: "停靠点",
        segmentLabel: "路段",
        foundLabel: "已找到",
        notFoundLabel: "未找到",
        secLabel: "秒",
        minLabel: "分钟",
        kmLabel: "公里",
        msLabel: "毫秒",
        osmIdLabel: "OSM ID",
        deleteLabel: "删除点",
        startBadgeTitle: "设为起点",
        endBadgeTitle: "设为终点",
        popupSelectedCoord: "选定位置",
        popupSelectedDesc: "点击添加按钮将此包含在您的路线中。",
        offlineWarningText: "由于您当前处于离线状态，如果使用实时路况数据进行搜索，可能无法获得准确的结果。"
    },
    fa: {
        title: "ایست‌روت",
        subtitle: "مسیر‌یاب عصبی A*",
        addLocation: "افزودن موقعیت",
        locationDesc: "روی نقشه کلیک کنید یا عرض/طول جغرافیایی را وارد کنید:",
        placeholder: "مثال: 41.0369, 28.9784",
        addButton: "افزودن",
        popularLocations: "مکان‌های مورد علاقه",
        noFavorites: "هنوز مکانی به مورد علاقه‌ها اضافه نشده است.",
        waypointsTitle: "نقاط بازدید",
        clearAll: "حذف همه",
        emptyStateText: "هنوز مکانی اضافه نشده است.",
        emptyStateSub: "روی نقشه کلیک کنید یا مختصات را در بالا وارد کنید تا اولین مکان خود را اضافه کنید.",
        settingsTitle: "تنظیمات بهینه‌سازی",
        heuristicLabel: "الگوریتم ابتکاری",
        neuralText: "heuristic عصبی (ONNX)",
        classicText: "heuristic هاورسین (A* کلاسیک)",
        routeModeLabel: "حالت مسیر",
        loopText: "بازگشت به شروع (حلقه بسته)",
        openText: "مسیر باز (شروع/پایان ثابت)",
        optimizeBtn: "بهینه‌سازی مسیر",
        optimizingBtn: "در حال بهینه‌سازی...",
        analysisTitle: "تحلیل مسیر",
        distanceLabel: "کل مسافت",
        durationLabel: "زمان تخمینی",
        timeLabel: "زمان بهینه‌سازی",
        segmentsLabel: "تعداد بخش‌ها",
        logsButton: "لاگ‌های بهینه‌سازی (2-opt)",
        mapOverlay: "روی نقشه کلیک کنید تا مختصات به طور خودکار کپی شوند، سپس روی «افزودن» کلیک کنید تا وارد شوند.",
        errorMinWps: "باید حداقل ۲ مختصات وارد کنید.",
        alertCoords: "لطفاً مختصات معتبر استانبول را وارد کنید! (عرض جغرافیایی: ۴۰-۴۲، طول جغرافیایی: ۲۸-۳۰)",
        alertFormat: "لطفاً مختصات را در قالب «عرض جغرافیایی، طول جغرافیایی» وارد کنید! (مثال: 41.0369, 28.9784)",
        alertServer: "ارتباط با سرور بهینه‌سازی مسیر برقرار نشد. مطمئن شوید سرور در حال اجراست.",
        alertOptError: "خطای بهینه‌سازی: ",
        startLabel: "شروع",
        endLabel: "پایان",
        waypointLabel: "ایستگاه",
        segmentLabel: "بخش",
        foundLabel: "پیدا شد",
        notFoundLabel: "پیدا نشد",
        secLabel: "ثانیه",
        minLabel: "دقیقه",
        kmLabel: "کیلومتر",
        msLabel: "میلی‌ثانیه",
        osmIdLabel: "شناسه OSM",
        deleteLabel: "حذف نقطه",
        startBadgeTitle: "تنظیم به عنوان نقطه شروع",
        endBadgeTitle: "تنظیم به عنوان نقطه پایان",
        popupSelectedCoord: "موقعیت انتخاب شده",
        popupSelectedDesc: "برای اضافه کردن این به مسیر خود، روی دکمه افزودن کلیک کنید.",
        offlineWarningText: "از آنجا که در حال حاضر آفلاین هستید، اگر با داده‌های ترافیک زنده جستجو کنید، ممکن است به نتایج فعالی دست نیابید."
    },
    ku: {
        title: "IstRoute",
        subtitle: "Plansazê Rêya A* a Neural",
        addLocation: "Cih Zêde Bike",
        locationDesc: "Li ser nexşeyê bikirtînin an panî/dirêjahî binivîsin:",
        placeholder: "Mînak: 41.0369, 28.9784",
        addButton: "Zêde Bike",
        popularLocations: "Cihên Favorî",
        noFavorites: "Hîn cihekî favorî nehatiye zêdekirin.",
        waypointsTitle: "Xalên Ziyaretê",
        clearAll: "Hemûyan Paqij Bike",
        emptyStateText: "Hîn tu cih zêde nebûne.",
        emptyStateSub: "Ji bo zêdekirina yekemîn cihê xwe li ser nexşeyê bikirtînin an li jorê kordînatan binivîsin.",
        settingsTitle: "Mîhengên Optîmîzasyonê",
        heuristicLabel: "Algorîtmaya Heurîstîk",
        neuralText: "Heurîstîka Neural (ONNX)",
        classicText: "Heurîstîka Haversine (A* Klasîk)",
        routeModeLabel: "Moda Rêyê",
        loopText: "Vegere Serê Rêyê (Çemberî)",
        openText: "Rêya Vekirî (Destpêk/Dawî Fîks)",
        optimizeBtn: "Rêyê Optîmîze Bike",
        optimizingBtn: "Tê optîmîzekirin...",
        analysisTitle: "Analîza Rêyê",
        distanceLabel: "Mesafeya Giştî",
        durationLabel: "Demjimêra Texmînî",
        timeLabel: "Dema Optîmîzasyonê",
        segmentsLabel: "Hejmara Segmentan",
        logsButton: "Logên Optîmîzasyonê (2-opt)",
        mapOverlay: "Li ser nexşeyê bikirtînin da ku kordînatan bixweber kopî bikin, paşê \"Zêde Bike\" bikirtînin.",
        errorMinWps: "Divê herî kêm 2 kordînat werin nivîsandin.",
        alertCoords: "Ji kerema xwe kordînatên Stenbolê yên derbasdar binivîsin! (Panî: 40-42, Dirêjahî: 28-30)",
        alertFormat: "Ji kerema xwe kordînatan di forma \"Panî, Dirêjahî\" de binivîsin! (Mînak: 41.0369, 28.9784)",
        alertServer: "Têkilî bi servera optîmîzasyona rêyê re çênebû. Piştrast bin ku ew dixebite.",
        alertOptError: "Çewtiya optîmîzasyona rêyê: ",
        startLabel: "Destpêk",
        endLabel: "Dawî",
        waypointLabel: "Rawestgeh",
        segmentLabel: "Segment",
        foundLabel: "Hate Dîtin",
        notFoundLabel: "Nexist Dîtin",
        secLabel: "saniye",
        minLabel: "deqîqe",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "OSM ID",
        deleteLabel: "Xalê Jê Bibe",
        startBadgeTitle: "Bike Xala Destpêkê",
        endBadgeTitle: "Bike Xala Dawiyê",
        popupSelectedCoord: "Cihê Hilbijartî",
        popupSelectedDesc: "Ji bo ku vê yekê li rêya xwe zêde bikin li ser bişkoka zêdekirinê bikirtînin.",
        offlineWarningText: "Ji ber ku hûn niha offline in, heke hûn bi daneyên trafîkê yên zindî bigerin, dibe ku hûn negihîjin encamên çalak."
    },
    fr: {
        title: "IstRoute",
        subtitle: "Planificateur de Route A* Neuronal",
        addLocation: "Ajouter un lieu",
        locationDesc: "Cliquez sur la carte ou entrez latitude/longitude :",
        placeholder: "Ex : 41.0369, 28.9784",
        addButton: "Ajouter",
        popularLocations: "Lieux Favoris",
        noFavorites: "Aucun lieu favori ajouté pour le moment.",
        waypointsTitle: "Points à Visiter",
        clearAll: "Tout Effacer",
        emptyStateText: "Aucun lieu ajouté pour le moment.",
        emptyStateSub: "Cliquez sur la carte ou entrez les coordonnées ci-dessus pour ajouter votre premier lieu.",
        settingsTitle: "Paramètres d'Optimisation",
        heuristicLabel: "Algorithme Heuristique",
        neuralText: "Heuristique Neuronale (ONNX)",
        classicText: "Heuristique Haversine (A* Classique)",
        routeModeLabel: "Mode de Route",
        loopText: "Retour au Début (Boucle Fermée)",
        openText: "Route Ouverte (Début/Fin Fixe)",
        optimizeBtn: "Optimiser la Route",
        optimizingBtn: "Optimisation...",
        analysisTitle: "Analyse de Route",
        distanceLabel: "Distance Totale",
        durationLabel: "Temps Estimé",
        timeLabel: "Temps d'Optimisation",
        segmentsLabel: "Nombre de Segments",
        logsButton: "Journaux d'Optimisation (2-opt)",
        mapOverlay: "Cliquez sur la carte pour copier automatiquement les coordonnées, puis cliquez sur \"Ajouter\" pour les inclure.",
        errorMinWps: "Au moins 2 coordonnées doivent être saisies.",
        alertCoords: "Veuillez entrer des coordonnées valides pour Istanbul ! (Lat : 40-42, Lng : 28-30)",
        alertFormat: "Veuillez entrer les coordonnées au format \"Latitude, Longitude\" ! (Ex : 41.0369, 28.9784)",
        alertServer: "Impossible de se connecter au serveur d'optimisation de route. Assurez-vous qu'il fonctionne.",
        alertOptError: "Erreur d'optimisation : ",
        startLabel: "Départ",
        endLabel: "Arrivée",
        waypointLabel: "Arrêt",
        segmentLabel: "Segment",
        foundLabel: "Trouvé",
        notFoundLabel: "Non trouvé",
        secLabel: "secondes",
        minLabel: "minutes",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "ID OSM",
        deleteLabel: "Supprimer le point",
        startBadgeTitle: "Définir comme point de départ",
        endBadgeTitle: "Définir comme point d'arrivée",
        popupSelectedCoord: "Lieu Sélectionné",
        popupSelectedDesc: "Cliquez sur le bouton Ajouter pour inclure ceci dans votre itinéraire.",
        offlineWarningText: "Comme vous êtes actuellement hors ligne, vous risquez de ne pas obtenir de résultats précis si vous effectuez une recherche avec les données de trafic en direct."
    },
    pt: {
        title: "IstRoute",
        subtitle: "Planejador de Rotas A* Neuronal",
        addLocation: "Adicionar Local",
        locationDesc: "Clique no mapa ou insira latitude/longitude:",
        placeholder: "Ex: 41.0369, 28.9784",
        addButton: "Adicionar",
        popularLocations: "Locais Favoritos",
        noFavorites: "Nenhum local favorito adicionado ainda.",
        waypointsTitle: "Pontos a Visitar",
        clearAll: "Limpar Tudo",
        emptyStateText: "Nenhum local adicionado ainda.",
        emptyStateSub: "Clique no mapa ou insira as coordenadas acima para adicionar seu primeiro local.",
        settingsTitle: "Ajustes de Otimização",
        heuristicLabel: "Algoritmo Heurístico",
        neuralText: "Heurística Neuronal (ONNX)",
        classicText: "Heurística Haversine (A* Clássico)",
        routeModeLabel: "Modo de Rota",
        loopText: "Retornar ao Início (Loop Fechado)",
        openText: "Rota Aberta (Início/Fim Fixo)",
        optimizeBtn: "Otimizar Rota",
        optimizingBtn: "Otimizando...",
        analysisTitle: "Análise de Rota",
        distanceLabel: "Distância Total",
        durationLabel: "Tempo Estimado",
        timeLabel: "Tempo de Otimização",
        segmentsLabel: "Número de Segmentos",
        logsButton: "Registros de Otimização (2-opt)",
        mapOverlay: "Clique no mapa para copiar as coordenadas automaticamente, depois clique em \"Adicionar\" para incluí-las.",
        errorMinWps: "Pelo menos 2 coordenadas devem ser inseridas.",
        alertCoords: "Insira coordenadas válidas de Istambul! (Lat: 40-42, Lng: 28-30)",
        alertFormat: "Insira as coordenadas no formato \"Latitude, Longitude\"! (Ex: 41.0369, 28.9784)",
        alertServer: "Não foi possível conectar ao servidor de otimização de rotas. Certifique-se de que ele esteja funcionando.",
        alertOptError: "Erro de otimização: ",
        startLabel: "Início",
        endLabel: "Fim",
        waypointLabel: "Parada",
        segmentLabel: "Segmento",
        foundLabel: "Encontrado",
        notFoundLabel: "Não encontrado",
        secLabel: "segundos",
        minLabel: "minutos",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "ID do OSM",
        deleteLabel: "Excluir Ponto",
        startBadgeTitle: "Definir como Ponto de Início",
        endBadgeTitle: "Definir como Ponto Final",
        popupSelectedCoord: "Local Selecionado",
        popupSelectedDesc: "Clique no botão Adicionar para incluir isso em sua rota.",
        offlineWarningText: "Como você está offline no momento, pode não obter resultados precisos se pesquisar com dados de trânsito em tempo real."
    },
    it: {
        title: "IstRoute",
        subtitle: "Pianificatore di Rotte A* Neuronale",
        addLocation: "Aggiungi Posizione",
        locationDesc: "Fai clic sulla mappa o inserisci latitudine/longitudine:",
        placeholder: "Es: 41.0369, 28.9784",
        addButton: "Aggiungi",
        popularLocations: "Luoghi Preferiti",
        noFavorites: "Nessun luogo preferito aggiunto ancora.",
        waypointsTitle: "Punti da Visitare",
        clearAll: "Cancella Tutto",
        emptyStateText: "Nessuna posizione ancora aggiunta.",
        emptyStateSub: "Fai clic sulla mappa o inserisci le coordinate sopra per aggiungere la prima posizione.",
        settingsTitle: "Impostazioni di Ottimizzazione",
        heuristicLabel: "Algoritmo Euristico",
        neuralText: "Euristica Neuronale (ONNX)",
        classicText: "Euristica Haversine (A* Classico)",
        routeModeLabel: "Modalità di Rotta",
        loopText: "Ritorna all'Inizio (Loop Chiuso)",
        openText: "Rotta Aperta (Inizio/Fine Fissi)",
        optimizeBtn: "Ottimizza Rotta",
        optimizingBtn: "Ottimizzazione...",
        analysisTitle: "Analisi della Rotta",
        distanceLabel: "Distanza Totale",
        durationLabel: "Tempo Stimato",
        timeLabel: "Tempo di Ottimizzazione",
        segmentsLabel: "Numero di Segmenti",
        logsButton: "Registri di Ottimizzazione (2-opt)",
        mapOverlay: "Fai clic sulla mappa per copiare automaticamente le coordinate, quindi fai clic su \"Aggiungi\" per includerle.",
        errorMinWps: "È necessario inserire almeno 2 coordinate.",
        alertCoords: "Inserisci coordinate valide per Istanbul! (Lat: 40-42, Lng: 28-30)",
        alertFormat: "Inserisci le coordinate nel formato \"Latitudine, Longitude\"! (Es: 41.0369, 28.9784)",
        alertServer: "Impossibile connettersi al server di ottimizzazione delle rotte. Assicurati che sia in esecuzione.",
        alertOptError: "Errore di ottimizzazione: ",
        startLabel: "Partenza",
        endLabel: "Arrivo",
        waypointLabel: "Fermata",
        segmentLabel: "Segmento",
        foundLabel: "Trovato",
        notFoundLabel: "Non trovato",
        secLabel: "secondi",
        minLabel: "minuti",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "ID OSM",
        deleteLabel: "Elimina Punto",
        startBadgeTitle: "Imposta come punto di partenza",
        endBadgeTitle: "Imposta come punto di arrivo",
        popupSelectedCoord: "Posizione Selezionata",
        popupSelectedDesc: "Fai clic sul pulsante Aggiungi per includere questo nella tua rotta.",
        offlineWarningText: "Poiché sei attualmente offline, potresti non ottenere risultati precisi se effettui una ricerca con i dati sul traffico in tempo reale."
    },
    ja: {
        title: "IstRoute",
        subtitle: "ニューラル A* ルートプランナー",
        addLocation: "場所を追加",
        locationDesc: "地図上をクリックするか、緯度/経度を入力してください：",
        placeholder: "例: 41.0369, 28.9784",
        addButton: "追加",
        popularLocations: "お気に入りの場所",
        noFavorites: "お気に入りの場所はまだ追加されていません。",
        waypointsTitle: "訪問地リスト",
        clearAll: "すべて削除",
        emptyStateText: "場所がまだ追加されていません。",
        emptyStateSub: "地図上をクリックするか、上に座標を入力して最初の場所を追加してください。",
        settingsTitle: "最適化設定",
        heuristicLabel: "ヒューリスティックアルゴリズム",
        neuralText: "ニューラルヒューリスティック (ONNX)",
        classicText: "ハバースヒューリスティック (古典的な A*)",
        routeModeLabel: "ルートモード",
        loopText: "起点に戻る (巡回ルート)",
        openText: "オープンルート (起点・終点固定)",
        optimizeBtn: "ルートを最適化",
        optimizingBtn: "最適化中...",
        analysisTitle: "ルート分析",
        distanceLabel: "総距離",
        durationLabel: "所要時間",
        timeLabel: "最適化時間",
        segmentsLabel: "区間数",
        logsButton: "最適化ログ (2-opt)",
        mapOverlay: "地図上をクリックして座標を自動的にコピーし、「追加」をクリックしてルートに含めます。",
        errorMinWps: "少なくとも2つの座標を入力する必要があります。",
        alertCoords: "有効なイスタンブールの座標を入力してください！ (緯度: 40-42, 経度: 28-30)",
        alertFormat: "座標は「緯度, 経度」の形式で入力してください！ (例: 41.0369, 28.9784)",
        alertServer: "ルート最適化サーバーに接続できませんでした。サーバーが起動していることを確認してください。",
        alertOptError: "最適化エラー: ",
        startLabel: "スタート",
        endLabel: "ゴール",
        waypointLabel: "経由地",
        segmentLabel: "区間",
        foundLabel: "検出",
        notFoundLabel: "未検出",
        secLabel: "秒",
        minLabel: "分",
        kmLabel: "km",
        msLabel: "ミリ秒",
        osmIdLabel: "OSM ID",
        deleteLabel: "地点を削除",
        startBadgeTitle: "出発地に設定",
        endBadgeTitle: "目的地に設定",
        popupSelectedCoord: "選択された場所",
        popupSelectedDesc: "追加ボタンをクリックして、これをルートに含めます。",
        offlineWarningText: "現在オフラインのため、リアルタイムの交通データで検索すると、正確な結果が得られない場合があります。"
    },
    hi: {
        title: "इस्टरूट",
        subtitle: "न्यूरल ए* मार्ग योजनाकार",
        addLocation: "स्थान जोड़ें",
        locationDesc: "मानचित्र पर क्लिक करें या अक्षांश/देशांतर दर्ज करें:",
        placeholder: "उदा: 41.0369, 28.9784",
        addButton: "जोड़ें",
        popularLocations: "पसंदीदा स्थान",
        noFavorites: "अभी तक कोई पसंदीदा स्थान नहीं जोड़ा गया है।",
        waypointsTitle: "यात्रा के बिंदु",
        clearAll: "सभी साफ़ करें",
        emptyStateText: "अभी तक कोई स्थान नहीं जोड़ा गया।",
        emptyStateSub: "अपना पहला स्थान जोड़ने के लिए मानचित्र पर क्लिक करें या ऊपर निर्देशांक दर्ज करें।",
        settingsTitle: "अनुकूलन सेटिंग्स",
        heuristicLabel: "ह्यूरिस्टिक एल्गोरिथम",
        neuralText: "न्यूरल ह्यूरिस्टिक (ONNX)",
        classicText: "हावेर्सिन ह्यूरिस्टिक (क्लासिक ए*)",
        routeModeLabel: "मार्ग मोड",
        loopText: "प्रारंभ पर लौटें (बंद लूप)",
        openText: "खुला मार्ग (निश्चित प्रारंभ/अंत)",
        optimizeBtn: "मार्ग अनुकूलित करें",
        optimizingBtn: "अनुकूलन किया जा रहा है...",
        analysisTitle: "मार्ग विश्लेषण",
        distanceLabel: "कुल दूरी",
        durationLabel: "अनुमानित समय",
        timeLabel: "अनुकूलन समय",
        segmentsLabel: "खंडों की संख्या",
        logsButton: "अनुकूलन लॉग (2-opt)",
        mapOverlay: "निर्देशांक स्वचालित रूप से कॉपी करने के लिए मानचित्र पर क्लिक करें, फिर शामिल करने के लिए \"जोड़ें\" पर क्लिक करें।",
        errorMinWps: "कम से कम 2 निर्देशांक दर्ज किए जाने चाहिए।",
        alertCoords: "कृपया वैध इस्तांबुल निर्देशांक दर्ज करें! (अक्षांश: 40-42, देशांतर: 28-30)",
        alertFormat: "कृपया निर्देशांक \"अक्षांश, देशांतर\" प्रारूप में दर्ज करें! (उदा: 41.0369, 28.9784)",
        alertServer: "मार्ग अनुकूलन सर्वर से कनेक्ट नहीं हो सका। सुनिश्चित करें कि यह चल रहा है।",
        alertOptError: "अनुकूलन त्रुटि: ",
        startLabel: "प्रारंभ",
        endLabel: "अंत",
        waypointLabel: "पड़ाव",
        segmentLabel: "खंड",
        foundLabel: "प्राप्त हुआ",
        notFoundLabel: "प्राप्त नहीं हुआ",
        secLabel: "सेकंड",
        minLabel: "मिनट",
        kmLabel: "किमी",
        msLabel: "मिलीसेकंड",
        osmIdLabel: "OSM आईडी",
        deleteLabel: "बिंदु हटाएं",
        startBadgeTitle: "प्रारंभ बिंदु के रूप में सेट करें",
        endBadgeTitle: "अंत बिंदु के रूप में सेट करें",
        popupSelectedCoord: "चयनित स्थान",
        popupSelectedDesc: "इसे अपने मार्ग में शामिल करने के लिए जोड़ें बटन पर क्लिक करें।",
        offlineWarningText: "चूंकि आप वर्तमान में ऑफ़लाइन हैं, यदि आप लाइव ट्रैफ़िक डेटा के साथ खोज करते हैं, तो हो सकता है कि आपको सटीक परिणाम न मिलें।"
    },
    ur: {
        title: "ایسٹ‌روٹ",
        subtitle: "نیورل A* روٹ پلانر",
        addLocation: "مقام شامل کریں",
        locationDesc: "نقشے پر کسی نقطہ پر کلک کریں یا عرض بلد/طول بلد درج کریں:",
        placeholder: "مثال: 41.0369, 28.9784",
        addButton: "شامل کریں",
        popularLocations: "پسندیدہ مقامات",
        noFavorites: "ابھی تک کوئی پسندیدہ مقام شامل نہیں کیا گیا۔",
        waypointsTitle: "دورہ کرنے کے مقامات",
        clearAll: "سب صاف کریں",
        emptyStateText: "ابھی تک کوئی مقام شامل نہیں کیا گیا۔",
        emptyStateSub: "اپنا پہلا مقام شامل کرنے کے لیے نقشے پر کلک کریں یا اوپر کوآرڈینیٹس درج کریں۔",
        settingsTitle: "بہتری کی ترتیبات",
        heuristicLabel: "الگورتھم ہیورسٹک",
        neuralText: "نیورل ہیورسٹک (ONNX)",
        classicText: "ہیورسٹک ہاورسین (کلاسیکی A*)",
        routeModeLabel: "روٹ موڈ",
        loopText: "شروع پر واپس جائیں (بند لوپ)",
        openText: "کھلا راستہ (مقرر شدہ شروع/اختتام)",
        optimizeBtn: "روٹ کو بہتر بنائیں",
        optimizingBtn: "بہتر کیا جا رہا ہے...",
        analysisTitle: "روٹ کا تجزیہ",
        distanceLabel: "کل فاصلہ",
        durationLabel: "تخمینی وقت",
        timeLabel: "بہتری کا وقت",
        segmentsLabel: "حصوں کی تعداد",
        logsButton: "بہتری کے لاگز (2-opt)",
        mapOverlay: "کوآرڈینیٹس کو خودکار طور پر کاپی کرنے کے لیے نقشے پر کلک کریں، پھر شامل کرنے کے لیے \"شامل کریں\" پر کلک کریں۔",
        errorMinWps: "کم از کم 2 کوآرڈینیٹ درج کرنا ضروری ہیں۔",
        alertCoords: "براہ کرم استنبول کے درست کوآرڈینیٹ درج کریں! (عرض بلد: 40-42، طول بلد: 28-30)",
        alertFormat: "براہ کرم کوآرڈینیٹس کو \"عرض بلد، طول بلد\" فارمیٹ میں درج کریں! (مثال: 41.0369, 28.9784)",
        alertServer: "روٹ آپٹیمائزیشن سرور سے منسلک نہیں ہو سکا۔ یقینی بنائیں کہ یہ چل رہا ہے۔",
        alertOptError: "بہتری کی خرابی: ",
        startLabel: "شروع",
        endLabel: "اختتام",
        waypointLabel: "پڑاؤ",
        segmentLabel: "حصہ",
        foundLabel: "مل گیا",
        notFoundLabel: "نہیں ملا",
        secLabel: "سیکنڈ",
        minLabel: "منٹ",
        kmLabel: "کلومیٹر",
        msLabel: "ملی سیکنڈ",
        osmIdLabel: "OSM آئی ڈی",
        deleteLabel: "نقطہ حذف کریں",
        startBadgeTitle: "شروع کرنے کا نقطہ مقرر کریں",
        endBadgeTitle: "آخری نقطہ مقرر کریں",
        popupSelectedCoord: "منتخب کردہ مقام",
        popupSelectedDesc: "اسے اپنے روٹ میں شامل کرنے کے لیے شامل کریں بٹن پر کلک کریں۔",
        offlineWarningText: "چونکہ آپ فی الحال آفلاین ہیں، اگر آپ لائیو ٹریفک ڈیٹا کے ساتھ تلاش کرتے ہیں تو ہو سکتا ہے آپ کو درست نتائج نہ ملیں۔"
    },
    id: {
        title: "IstRoute",
        subtitle: "Perencana Rute Neural A*",
        addLocation: "Tambah Lokasi",
        locationDesc: "Klik titik pada peta atau masukkan lintang/bujur:",
        placeholder: "mis. 41.0369, 28.9784",
        addButton: "Tambah",
        popularLocations: "Lokasi Favorit",
        noFavorites: "Belum ada lokasi favorit yang ditambahkan.",
        waypointsTitle: "Titik Kunjungan",
        clearAll: "Hapus Semua",
        emptyStateText: "Belum ada lokasi yang ditambahkan.",
        emptyStateSub: "Klik pada peta atau masukkan koordinat di atas untuk menambahkan lokasi pertama Anda.",
        settingsTitle: "Pengaturan Optimasi",
        heuristicLabel: "Heuristik Algoritma",
        neuralText: "Neural Heuristic (ONNX)",
        classicText: "Haversine Heuristic (A* Klasik)",
        routeModeLabel: "Mode Rute",
        loopText: "Kembali ke Awal (Rute Lingkar)",
        openText: "Jalur Terbuka (Awal/Akhir Tetap)",
        optimizeBtn: "Optimalkan Rute",
        optimizingBtn: "Mengoptimalkan...",
        analysisTitle: "Analisis Rute",
        distanceLabel: "Total Jarak",
        durationLabel: "Estimasi Waktu",
        timeLabel: "Waktu Optimasi",
        segmentsLabel: "Jumlah Segmen",
        logsButton: "Log Optimasi (2-opt)",
        mapOverlay: "Klik pada peta untuk menyalin koordinat secara otomatis, lalu klik \"Tambah\" untuk memasukkannya.",
        errorMinWps: "Minimal harus memasukkan 2 koordinat.",
        alertCoords: "Silakan masukkan koordinat Istanbul yang valid! (Lintang: 40-42, Bujur: 28-30)",
        alertFormat: "Silakan masukkan koordinat dalam format \"Lintang, Bujur\"! (mis. 41.0369, 28.9784)",
        alertServer: "Tidak dapat terhubung ke server optimasi rute. Pastikan server berjalan.",
        alertOptError: "Kesalahan optimasi: ",
        startLabel: "Mulai",
        endLabel: "Selesai",
        waypointLabel: "Pemberhentian",
        segmentLabel: "Segmen",
        foundLabel: "Ditemukan",
        notFoundLabel: "Tidak Ditemukan",
        secLabel: "detik",
        minLabel: "menit",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "ID OSM",
        deleteLabel: "Hapus Titik",
        startBadgeTitle: "Atur sebagai Titik Mulai",
        endBadgeTitle: "Atur sebagai Titik Selesai",
        popupSelectedCoord: "Lokasi Terpilih",
        popupSelectedDesc: "Klik tombol Tambah untuk memasukkan ini ke rute Anda.",
        offlineWarningText: "Karena Anda sedang offline saat ini, Anda mungkin tidak mendapatkan hasil yang akurat jika mencari dengan data lalu lintas langsung."
    },
    sq: {
        title: "IstRoute",
        subtitle: "Planifikues Rrugor Neural A*",
        addLocation: "Shto Vendndodhje",
        locationDesc: "Kliko në hartë ose vendos gjerësinë/gjatësinë gjeografike:",
        placeholder: "p.sh. 41.0369, 28.9784",
        addButton: "Shto",
        popularLocations: "Vendndodhjet e Preferuara",
        noFavorites: "Nuk është shtuar ende asnjë vendndodhje e preferuar.",
        waypointsTitle: "Pikat për t'u Vizituar",
        clearAll: "Fshi të Gjitha",
        emptyStateText: "Ende nuk është shtuar asnjë vendndodhje.",
        emptyStateSub: "Kliko në hartë ose vendos koordinatat më lart për të shtuar vendndodhjen tënde të parë.",
        settingsTitle: "Cilësimet e Optimizimit",
        heuristicLabel: "Algoritmi Heuristike",
        neuralText: "Heuristika Neuronalë (ONNX)",
        classicText: "Heuristika Haversine (A* Klasik)",
        routeModeLabel: "Modaliteti i Rrugës",
        loopText: "Kthehu në Fillim (Rrugë e Mbyllur)",
        openText: "Rrugë e Hapur (Fillim/Fund i Fiksuar)",
        optimizeBtn: "Optimizo Rrugën",
        optimizingBtn: "Duke optimizuar...",
        analysisTitle: "Analiza e Rrugës",
        distanceLabel: "Distanca Totale",
        durationLabel: "Koha e Parashikuar",
        timeLabel: "Koha e Optimizimit",
        segmentsLabel: "Numri i Segmenteve",
        logsButton: "Regjistrat e Optimizimit (2-opt)",
        mapOverlay: "Kliko në hartë për të kopjuar koordinatat automatikisht, pastaj kliko \"Shto\" për t'i përfshirë.",
        errorMinWps: "Duhet të vendosen të paktën 2 koordinata.",
        alertCoords: "Ju lutemi vendosni koordinata të vlefshme për Stambollin! (Gjerësi: 40-42, Gjatësi: 28-30)",
        alertFormat: "Ju lutemi vendosni koordinatat në formatin \"Gjerësi, Gjatësi\"! (p.sh. 41.0369, 28.9784)",
        alertServer: "Nuk u mundësua lidhja me serverin e optimizimit të rrugës. Sigurohuni që ai po funksionon.",
        alertOptError: "Gabim optimizimi: ",
        startLabel: "Fillo",
        endLabel: "Fundo",
        waypointLabel: "Ndalim",
        segmentLabel: "Segment",
        foundLabel: "U gjet",
        notFoundLabel: "Nuk u gjet",
        secLabel: "sekonda",
        minLabel: "minuta",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "ID e OSM",
        deleteLabel: "Fshi Pikën",
        startBadgeTitle: "Vendos si Pikë Fillimi",
        endBadgeTitle: "Vendos si Pikë Fundi",
        popupSelectedCoord: "Vendndodhja e Përzgjedhur",
        popupSelectedDesc: "Kliko butonin Shto për ta përfshirë këtë në rrugën tënd.",
        offlineWarningText: "Duke qenë se aktualisht jeni jashtë linje, mund të mos merrni rezultate të sakta nëse kërkoni me të dhënat e trafikut të drejtpërdrejtë."
    },
    bn: {
        title: "ইস্টরুট",
        subtitle: "নিউরল এ* রুট প্ল্যানার",
        addLocation: "স্থান যোগ করুন",
        locationDesc: "মানচিত্রে একটি বিন্দুতে ক্লিক করুন বা অক্ষাংশ/দ্রাঘিমাংশ লিখুন:",
        placeholder: "উদাঃ 41.0369, 28.9784",
        addButton: "যোগ করুন",
        popularLocations: "প্রিয় স্থানসমূহ",
        noFavorites: "এখনো কোনো প্রিয় স্থান যোগ করা হয়নি।",
        waypointsTitle: "পরিদর্শন করার পয়েন্ট",
        clearAll: "সব মুছে ফেলুন",
        emptyStateText: "এখনও কোনো স্থান যোগ করা হয়নি।",
        emptyStateSub: "আপনার প্রথম স্থানটি যোগ করতে মানচিত্রে ক্লিক করুন বা উপরে স্থানাঙ্ক লিখুন।",
        settingsTitle: "অপ্টিमাইজেশন সেটিংস",
        heuristicLabel: "হিউরিস্টিক অ্যালগরিদম",
        neuralText: "নিউরল হিউরিস্টিক (ONNX)",
        classicText: "হাভারসাইন হিউরিস্টিক (ক্লাসিক এ*)",
        routeModeLabel: "রুট মোড",
        loopText: "শুরুতে ফিরে যান (ক্লোজড লুপ)",
        openText: "খোলা পথ (স্থির শুরু/শেষ)",
        optimizeBtn: "রুট অপ্টিমাইজ করুন",
        optimizingBtn: "অপ্টিমাইজ করা হচ্ছে...",
        analysisTitle: "রুট বিশ্লেষণ",
        distanceLabel: "মোট দূরত্ব",
        durationLabel: "আনুমানিক সময়",
        timeLabel: "অপ্টিমাইজেশন সময়",
        segmentsLabel: "খণ্ডের সংখ্যা",
        logsButton: "অপ্টিমাইজেশন লগ (2-opt)",
        mapOverlay: "স্থানাঙ্কগুলি স্বয়ংক্রিয়ভাবে অনুলিপি করতে মানচিত্রে ক্লিক করুন, তারপর অন্তর্ভুক্ত করতে \"যোগ করুন\" ক্লিক করুন।",
        errorMinWps: "কমপক্ষে ২টি স্থানাঙ্ক প্রবেশ করাতে হবে।",
        alertCoords: "अनुग्रह করে বৈধ ইস্তাম্বুল স্থানাঙ্ক প্রবেশ করান! (অক্ষাংশ: ৪০-৪২, দ্রাঘিমাংশ: ২৮-৩০)",
        alertFormat: "অনুগ্রহ করে স্থানাঙ্কগুলি \"অক্ষাংশ, দ্রাঘিমাংশ\" বিন্যাসে প্রবেশ করান! (উদাঃ 41.0369, 28.9784)",
        alertServer: "রুট অপ্টিমাইজেশান সার্ভারের সাথে সংযোগ করা যায়নি। নিশ্চিত করুন যে এটি চলছে।",
        alertOptError: "অপ্টিমাইজেশন ত্রুটি: ",
        startLabel: "শুরু",
        endLabel: "শেষ",
        waypointLabel: "থামা",
        segmentLabel: "খণ্ড",
        foundLabel: "পাওয়া গেছে",
        notFoundLabel: "পাওয়া যায়নি",
        secLabel: "সেকেন্ড",
        minLabel: "মিনিট",
        kmLabel: "কিমি",
        msLabel: "মিঃসেঃ",
        osmIdLabel: "OSM আইডি",
        deleteLabel: "পয়েন্ট মুছে ফেলুন",
        startBadgeTitle: "शुरू बिंदु के रूप में सेट करें",
        endBadgeTitle: "अंत बिंदु के रूप में सेट करें",
        popupSelectedCoord: "নির্বাচিত স্থান",
        popupSelectedDesc: "এটি আপনার রুটে অন্তর্ভুক্ত করতে যোগ করুন বোতামে ক্লিক করুন।",
        offlineWarningText: "যেহেতু আপনি বর্তমানে অফলাইনে আছেন, তাই আপনি যদি লাইভ ট্রাফিক ডেটা সহ অনুসন্ধান করেন তবে সঠিক ফলাফল নাও পেতে পারেন।"
    },
    pcm: {
        title: "IstRoute",
        subtitle: "Neural A* Route Planner",
        addLocation: "Add Place",
        locationDesc: "Click anywhere for map or put latitude/longitude:",
        placeholder: "e.g. 41.0369, 28.9784",
        addButton: "Add",
        popularLocations: "Favorite Places",
        noFavorites: "You neva add any favorite place yet.",
        waypointsTitle: "Places wey you wan go",
        clearAll: "Delete All",
        emptyStateText: "No place don add yet.",
        emptyStateSub: "Click map or put coordinate for up to add your first place.",
        settingsTitle: "How to set am",
        heuristicLabel: "Algorithm Heuristic",
        neuralText: "Neural Heuristic (ONNX)",
        classicText: "Haversine Heuristic (Classic A*)",
        routeModeLabel: "Route Mode",
        loopText: "Go back to start (Round trip)",
        openText: "Open route (Start/End fixed)",
        optimizeBtn: "Find beta route",
        optimizingBtn: "E dey calculate...",
        analysisTitle: "Route details",
        distanceLabel: "Total Distance",
        durationLabel: "Time wey e go take",
        timeLabel: "Calculation Time",
        segmentsLabel: "How many segments",
        logsButton: "Process logs (2-opt)",
        mapOverlay: "Click map to copy coordinate, then click \"Add\" to put am.",
        errorMinWps: "You must put at least 2 places.",
        alertCoords: "Abeg put correct Istanbul coordinate! (Lat: 40-42, Lng: 28-30)",
        alertFormat: "Abeg put coordinate like \"Latitude, Longitude\"! (e.g. 41.0369, 28.9784)",
        alertServer: "Server no gree connect. Check if e dey run.",
        alertOptError: "Error for calculation: ",
        startLabel: "Start",
        endLabel: "End",
        waypointLabel: "Stop",
        segmentLabel: "Segment",
        foundLabel: "We find am",
        notFoundLabel: "We no find am",
        secLabel: "seconds",
        minLabel: "minutes",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "OSM ID",
        deleteLabel: "Remove Point",
        startBadgeTitle: "Make am start point",
        endBadgeTitle: "Make am end point",
        popupSelectedCoord: "Selected Place",
        popupSelectedDesc: "Click Add button to put this one for your route.",
        offlineWarningText: "As you offline now, you fit no get correct results if you search with live traffic data."
    },
    mr: {
        title: "इस्टरूट",
        subtitle: "न्यूरल ए* मार्ग नियोजक",
        addLocation: "स्थान जोडा",
        locationDesc: "नकाशावर क्लिक करा किंवा अक्षांश/रेखांश प्रविष्ट करा:",
        placeholder: "उदा. 41.0369, 28.9784",
        addButton: "जोडा",
        popularLocations: "आवडती ठिकाणे",
        noFavorites: "अद्याप कोणतीही आवडती ठिकाणे जोडलेली नाहीत.",
        waypointsTitle: "भेट देण्याची ठिकाणे",
        clearAll: "सर्व हटवा",
        emptyStateText: "अद्याप कोणतेही स्थान जोडलेले नाही.",
        emptyStateSub: "तुमचे पहिले स्थान जोडण्यासाठी नकाशावर क्लिक करा किंवा वर निर्देशांक प्रविष्ट करा.",
        settingsTitle: "ऑप्टिमायझेशन सेटिंग्ज",
        heuristicLabel: "ह्यूरिस्टिक अल्गोरिदम",
        neuralText: "न्यूरल ह्यूरिस्टिक (ONNX)",
        classicText: "हावेर्सिन ह्यूरिस्टिक (क्लासिक ए*)",
        routeModeLabel: "मार्ग मोड",
        loopText: "सुरुवातीला परत या (बंद लूप)",
        openText: "खुला मार्ग (निश्चित सुरुवात/शेवट)",
        optimizeBtn: "मार्ग ऑप्टिमाइझ करा",
        optimizingBtn: "ऑप्टिमाइझ करत आहे...",
        analysisTitle: "मार्ग विश्लेषण",
        distanceLabel: "एकूण अंतर",
        durationLabel: "अंदाजे वेळ",
        timeLabel: "ऑप्टिमायझेशन वेळ",
        segmentsLabel: "खंडांची संख्या",
        logsButton: "ऑप्टिमायझेशन लॉग्स (2-opt)",
        mapOverlay: "निर्देशांक स्वयंचलितपणे कॉपी करण्यासाठी नकाशावर क्लिक करा, नंतर समाविष्ट करण्यासाठी \"जोडा\" वर क्लिक करा.",
        errorMinWps: "किमान २ निर्देशांक प्रविष्ट करणे आवश्यक आहे.",
        alertCoords: "कृपया वैध इस्तंबूल निर्देशांक प्रविष्ट करा! (अक्षांश: 40-42, रेखांश: 28-30)",
        alertFormat: "कृपया निर्देशांक \"अक्षांश, रेखांश\" स्वरूपात प्रविष्ट करा! (उदा. 41.0369, 28.9784)",
        alertServer: "मार्ग ऑप्टिमायझेशन सर्व्हरशी कनेक्ट होऊ शकले नाही. तो चालू असल्याची खात्री करा.",
        alertOptError: "ऑप्टिमायझेशन त्रुटी: ",
        startLabel: "सुरुवात",
        endLabel: "शेवट",
        waypointLabel: "थांबा",
        segmentLabel: "खंड",
        foundLabel: "सापडले",
        notFoundLabel: "नाही सापडले",
        secLabel: "सेकंद",
        minLabel: "मिनिटे",
        kmLabel: "किमी",
        msLabel: "मिलीसेकंद",
        osmIdLabel: "OSM आयडी",
        deleteLabel: "बिंदू हटवा",
        startBadgeTitle: "सुरुवातीचा बिंदू म्हणून सेट करा",
        endBadgeTitle: "शेवटचा बिंदू म्हणून सेट करा",
        popupSelectedCoord: "निवडलेले स्थान",
        popupSelectedDesc: "तुमच्या मार्गामध्ये हे समाविष्ट करण्यासाठी जोडा बटणावर क्लिक करा.",
        offlineWarningText: "तुम्ही सध्या ऑफलाइन असल्यामुळे, थेट ट्रॅफिक डेटासह शोधल्यास तुम्हाला अचूक निकाल मिळणार नाहीत."
    },
    sw: {
        title: "IstRoute",
        subtitle: "Kipanga Njia cha Neural A*",
        addLocation: "Ongeza Eneo",
        locationDesc: "Bofya kwenye ramani au ingiza latitudo/longitudo:",
        placeholder: "mfano: 41.0369, 28.9784",
        addButton: "Ongeza",
        popularLocations: "Maeneo Unayoyapenda",
        noFavorites: "Hakuna maeneo unayoyapenda yaliyoongezwa bado.",
        waypointsTitle: "Vituo vya Kutembelea",
        clearAll: "Futa Zote",
        emptyStateText: "Hakuna maeneo yaliyoingizwa bado.",
        emptyStateSub: "Bofya kwenye ramani au ingiza viwianishi hapo juu ili kuongeza eneo lako la kwanza.",
        settingsTitle: "Mipangilio ya Uboreshaji",
        heuristicLabel: "Algorithm Heuristic",
        neuralText: "Neural Heuristic (ONNX)",
        classicText: "Haversine Heuristic (A* ya Kawaida)",
        routeModeLabel: "Hali ya Njia",
        loopText: "Rudi Mwanzo (Mzunguko)",
        openText: "Njia Wazi (Mwanzo/Mwisho Maalum)",
        optimizeBtn: "Boresha Njia",
        optimizingBtn: "Inaboresha...",
        analysisTitle: "Uchambuzi wa Njia",
        distanceLabel: "Jumla ya Umbali",
        durationLabel: "Muda Unaokadiriwa",
        timeLabel: "Muda wa Uboreshaji",
        segmentsLabel: "Idadi ya Sehemu",
        logsButton: "Kumbukumbu za Uboreshaji (2-opt)",
        mapOverlay: "Bofya kwenye ramani ili kunakili viwianishi kiotomatiki, kisha ubofye \"Ongeza\" ili kuviweka.",
        errorMinWps: "Angalau viwianishi 2 lazima viwekwe.",
        alertCoords: "Tafadhali ingiza viwianishi halali vya Istanbul! (Lat: 40-42, Lng: 28-30)",
        alertFormat: "Tafadhali ingiza viwianishi katika mfumo wa \"Latitudo, Longitudo\"! (mfano: 41.0369, 28.9784)",
        alertServer: "Imeshindwa kuunganisha kwenye seva ya uboreshaji wa njia. Hakikisha inafanya kazi.",
        alertOptError: "Hitilafu ya uboreshaji: ",
        startLabel: "Mwanzo",
        endLabel: "Mwisho",
        waypointLabel: "Kituo",
        segmentLabel: "Sehemu",
        foundLabel: "Imepatikana",
        notFoundLabel: "Haipatikani",
        secLabel: "sekunde",
        minLabel: "dakika",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "Kitambulisho cha OSM",
        deleteLabel: "Futa Kituo",
        startBadgeTitle: "Weka kama Kituo cha Kuanzia",
        endBadgeTitle: "Weka kama Kituo cha Mwisho",
        popupSelectedCoord: "Eneo Lililochaguliwa",
        popupSelectedDesc: "Bofya kitufe cha Ongeza ili kuweka hili kwenye njia yako.",
        offlineWarningText: "Kwa kuwa kwa sasa hauko mtandaoni, unaweza usipate matokeo sahihi ukitafuta kwa kutumia data ya trafiki ya moja kwa moja."
    },
    ko: {
        title: "IstRoute",
        subtitle: "Neural A* 경로 플래너",
        addLocation: "위치 추가",
        locationDesc: "지도에서 지점을 클릭하거나 위도/경도를 입력하세요:",
        placeholder: "예: 41.0369, 28.9784",
        addButton: "추가",
        popularLocations: "즐겨찾는 위치",
        noFavorites: "추가된 즐겨찾는 위치가 없습니다.",
        addFav: "즐겨찾기 추가",
        removeFav: "즐겨찾기 제거",
        waypointsTitle: "방문할 웨이포인트",
        clearAll: "전체 삭제",
        emptyStateText: "아직 추가된 위치가 없습니다.",
        emptyStateSub: "지도를 클릭하거나 위에서 좌표를 입력하여 첫 번째 위치를 추가하세요.",
        settingsTitle: "최적화 설정",
        heuristicLabel: "알고리즘 휴리스틱",
        neuralText: "Neural Heuristic (ONNX)",
        classicText: "Haversine Heuristic (클래식 A*)",
        routeModeLabel: "경로 모드",
        loopText: "출발지로 돌아가기 (루프)",
        openText: "열린 경로 (고정 출발/도착)",
        optimizeBtn: "경로 최적화",
        optimizingBtn: "최적화 중...",
        analysisTitle: "경로 분석",
        distanceLabel: "총 거리",
        durationLabel: "예상 시간",
        timeLabel: "최적화 시간",
        segmentsLabel: "세그먼트 수",
        logsButton: "최적화 로그 (2-opt)",
        mapOverlay: "지도를 클릭하여 직접 좌표를 가져온 다음 \"추가\"를 클릭하여 경로에 포함할 수 있습니다.",
        errorMinWps: "최소 2개의 좌표를 입력해야 합니다.",
        alertCoords: "올바른 이스탄불 좌표를 입력하세요! (위도: 40-42, 경도: 28-30)",
        alertFormat: "좌표를 \"위도, 경도\" 형식으로 입력하세요! (예: 41.0369, 28.9784)",
        alertServer: "경로 최적화 서버에 연결할 수 없습니다.",
        alertOptError: "최적화 오류: ",
        startLabel: "출발지",
        endLabel: "도착지",
        waypointLabel: "경유지",
        segmentLabel: "세그먼트",
        foundLabel: "찾음",
        notFoundLabel: "찾을 수 없음",
        secLabel: "초",
        minLabel: "분",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "OSM ID",
        deleteLabel: "경유지 삭제",
        startBadgeTitle: "출발지로 설정",
        endBadgeTitle: "도착지로 설정",
        popupSelectedCoord: "선택된 위치",
        popupSelectedDesc: "추가 버튼을 눌러 경로에 추가하세요.",
        offlineWarningText: "현재 오프라인 상태이므로 실시간 교통 데이터로 검색할 경우 정확한 결과를 얻지 못할 수 있습니다.",
        trafficOverlayLabel: "실시간 교통 레이어",
        trafficRouteLabel: "교통 반영 경로 탐색",
        trafficOverlayOn: "교통 정보 표시",
        trafficOverlayOff: "교통 정보 숨기기",
        trafficRouteOn: "교통 정체 회피",
        trafficRouteOff: "가장 빠른 길 (교통 무시)"
    },
    vi: {
        title: "IstRoute",
        subtitle: "Trình lập lộ trình Neural A*",
        addLocation: "Thêm Địa điểm",
        locationDesc: "Click vào một điểm trên bản đồ hoặc nhập vĩ độ/kinh độ:",
        placeholder: "Ví dụ: 41.0369, 28.9784",
        addButton: "Thêm",
        popularLocations: "Địa điểm Yêu thích",
        noFavorites: "Chưa có địa điểm yêu thích nào được thêm.",
        addFav: "Thêm Yêu thích",
        removeFav: "Xóa Yêu thích",
        waypointsTitle: "Các Điểm Dừng",
        clearAll: "Xóa Tất cả",
        emptyStateText: "Chưa có địa điểm nào được thêm.",
        emptyStateSub: "Click vào bản đồ hoặc nhập tọa độ ở trên để thêm điểm đầu tiên.",
        settingsTitle: "Cấu hình Tối ưu",
        heuristicLabel: "Thuật toán Heuristic",
        neuralText: "Neural Heuristic (ONNX)",
        classicText: "Haversine Heuristic (A* Cổ điển)",
        routeModeLabel: "Chế độ Lộ trình",
        loopText: "Quay lại Điểm đầu (Vòng khép kín)",
        openText: "Đường mở (Bắt đầu/Kết thúc cố định)",
        optimizeBtn: "Tối ưu hóa Lộ trình",
        optimizingBtn: "Đang tối ưu...",
        analysisTitle: "Phân tích Lộ trình",
        distanceLabel: "Tổng Khoảng cách",
        durationLabel: "Thời gian Dự kiến",
        timeLabel: "Thời gian Tối ưu",
        segmentsLabel: "Số Phân đoạn",
        logsButton: "Nhật ký Tối ưu (2-opt)",
        mapOverlay: "Click vào bản đồ để lấy tọa độ trực tiếp, sau đó nhấn \"Thêm\" để đưa vào lộ trình.",
        errorMinWps: "Cần nhập ít nhất 2 tọa độ.",
        alertCoords: "Vui lòng nhập tọa độ Istanbul hợp lệ! (Vĩ độ: 40-42, Kinh độ: 28-30)",
        alertFormat: "Vui lòng nhập tọa độ theo định dạng \"Vĩ độ, Kinh độ\"! (Ví dụ: 41.0369, 28.9784)",
        alertServer: "Không thể kết nối đến máy chủ tối ưu hóa lộ trình.",
        alertOptError: "Lỗi tối ưu hóa: ",
        startLabel: "Điểm đầu",
        endLabel: "Điểm cuối",
        waypointLabel: "Điểm dừng",
        segmentLabel: "Phân đoạn",
        foundLabel: "Tìm thấy",
        notFoundLabel: "Không tìm thấy",
        secLabel: "giây",
        minLabel: "phút",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "OSM ID",
        deleteLabel: "Xóa Điểm dừng",
        startBadgeTitle: "Đặt làm Điểm đầu",
        endBadgeTitle: "Đặt làm Điểm cuối",
        popupSelectedCoord: "Tọa độ đã Chọn",
        popupSelectedDesc: "Nhấn nút Thêm để đưa điểm này vào lộ trình của bạn.",
        offlineWarningText: "Vì bạn hiện đang ngoại tuyến, bạn có thể không nhận được kết quả chính xác nếu tìm kiếm với dữ liệu giao thông trực tiếp.",
        trafficOverlayLabel: "Lớp Giao thông Trực tuyến",
        trafficRouteLabel: "Lộ trình Tránh kẹt xe",
        trafficOverlayOn: "Hiển thị Giao thông",
        trafficOverlayOff: "Ẩn Giao thông",
        trafficRouteOn: "Tránh Kẹt xe",
        trafficRouteOff: "Đường Nhanh nhất (Không kẹt xe)"
    },
    pl: {
        title: "IstRoute",
        subtitle: "Planer tras Neural A*",
        addLocation: "Dodaj Lokalizację",
        locationDesc: "Kliknij punkt na mapie lub wprowadź szerokość/długość:",
        placeholder: "np. 41.0369, 28.9784",
        addButton: "Dodaj",
        popularLocations: "Ulubione Lokalizacje",
        noFavorites: "Nie dodano jeszcze ulubionych lokalizacji.",
        addFav: "Dodaj do ulubionych",
        removeFav: "Usuń z ulubionych",
        waypointsTitle: "Punkty trasy",
        clearAll: "Wyczyść Wszystko",
        emptyStateText: "Nie dodano jeszcze żadnych lokalizacji.",
        emptyStateSub: "Kliknij na mapie lub wpisz współrzędne powyżej, aby dodać swój pierwszy punkt.",
        settingsTitle: "Ustawienia Optymalizacji",
        heuristicLabel: "Algorytm Heurystyczny",
        neuralText: "Neural Heuristic (ONNX)",
        classicText: "Haversine Heuristic (Klasyczny A*)",
        routeModeLabel: "Tryb Trasy",
        loopText: "Powrót do Startu (Pętla)",
        openText: "Trasa Otwarta (Stały Start/Koniec)",
        optimizeBtn: "Optymalizuj Trasę",
        optimizingBtn: "Optymalizacja...",
        analysisTitle: "Analiza Trasy",
        distanceLabel: "Całkowity Dystans",
        durationLabel: "Szacowany Czas",
        timeLabel: "Czas Optymalizacji",
        segmentsLabel: "Liczba Segmentów",
        logsButton: "Logi Optymalizacji (2-opt)",
        mapOverlay: "Kliknij na mapie, aby pobrać współrzędne bezpośrednio, a następnie kliknij \"Dodaj\", aby uwzględnić je w trasie.",
        errorMinWps: "Należy wprowadzić co najmniej 2 współrzędne.",
        alertCoords: "Wprowadź poprawne współrzędne Stambułu! (Szerokość: 40-42, Długość: 28-30)",
        alertFormat: "Wprowadź współrzędne w formacie \"Szerokość, Długość\"! (np. 41.0369, 28.9784)",
        alertServer: "Nie można połączyć się z serwerem optymalizacji tras.",
        alertOptError: "Błąd optymalizacji: ",
        startLabel: "Start",
        endLabel: "Koniec",
        waypointLabel: "Punkt",
        segmentLabel: "Segment",
        foundLabel: "Znaleziono",
        notFoundLabel: "Nie znaleziono",
        secLabel: "sekund",
        minLabel: "minut",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "OSM ID",
        deleteLabel: "Usuń Punkt",
        startBadgeTitle: "Ustaw jako Start",
        endBadgeTitle: "Ustaw jako Koniec",
        popupSelectedCoord: "Wybrana Lokalizacja",
        popupSelectedDesc: "Kliknij przycisk Dodaj, aby dodać to do swojej trasy.",
        offlineWarningText: "Ponieważ jesteś obecnie w trybie offline, możesz nie otrzymać dokładnych wyników, jeśli szukasz z aktywnymi danymi o ruchu drogowym.",
        trafficOverlayLabel: "Warstwa Ruchu na Żywo",
        trafficRouteLabel: "Trasa Uwzględniająca Ruch",
        trafficOverlayOn: "Pokaż Ruch",
        trafficOverlayOff: "Ukryj Ruch",
        trafficRouteOn: "Omijaj Korki",
        trafficRouteOff: "Najszybsza Droga (Bez korków)"
    },
    uk: {
        title: "IstRoute",
        subtitle: "Планувальник маршрутів Neural A*",
        addLocation: "Додати Місце",
        locationDesc: "Клацніть точку на карті або введіть широту/довготу:",
        placeholder: "напр. 41.0369, 28.9784",
        addButton: "Додати",
        popularLocations: "Улюблені місця",
        noFavorites: "Ще немає доданих улюблених місць.",
        addFav: "Додати в обране",
        removeFav: "Видалити з обраного",
        waypointsTitle: "Точки маршруту",
        clearAll: "Очистити Все",
        emptyStateText: "Ще не додано жодного місця.",
        emptyStateSub: "Клацніть на карті або введіть координати вище, щоб додати першу точку.",
        settingsTitle: "Налаштування Оптимізації",
        heuristicLabel: "Евристика Алгоритму",
        neuralText: "Neural Heuristic (ONNX)",
        classicText: "Haversine Heuristic (Класичний A*)",
        routeModeLabel: "Режим Маршруту",
        loopText: "Повернутися до Старту (Замкнутий)",
        openText: "Відкритий Маршрут (Фіксований Старт/Фініш)",
        optimizeBtn: "Оптимізувати Маршрут",
        optimizingBtn: "Оптимізація...",
        analysisTitle: "Аналіз Маршруту",
        distanceLabel: "Загальна Відстань",
        durationLabel: "Очікуваний Час",
        timeLabel: "Час Оптимізації",
        segmentsLabel: "Кількість Сегментів",
        logsButton: "Логи Оптимізації (2-opt)",
        mapOverlay: "Клацніть на карті, щоб отримати координати безпосередньо, а потім натисніть \"Додати\", щоб включити їх у маршрут.",
        errorMinWps: "Необхідно ввести щонайменше 2 координати.",
        alertCoords: "Будь ласка, введіть дійсні координати Стамбула! (Широта: 40-42, Довгота: 28-30)",
        alertFormat: "Введіть координати у форматі \"Широта, Довгота\"! (напр. 41.0369, 28.9784)",
        alertServer: "Не вдалося з'єднатися з сервером оптимізації маршрутів.",
        alertOptError: "Помилка оптимізації: ",
        startLabel: "Старт",
        endLabel: "Фініш",
        waypointLabel: "Точка",
        segmentLabel: "Сегмент",
        foundLabel: "Знайдено",
        notFoundLabel: "Не знайдено",
        secLabel: "секунд",
        minLabel: "хвилин",
        kmLabel: "км",
        msLabel: "мс",
        osmIdLabel: "OSM ID",
        deleteLabel: "Видалити Точку",
        startBadgeTitle: "Зробити Стартом",
        endBadgeTitle: "Зробити Фінішем",
        popupSelectedCoord: "Вибране Місце",
        popupSelectedDesc: "Натисніть кнопку Додати, щоб додати це до вашого маршруту.",
        offlineWarningText: "Оскільки ви зараз перебуваєте в автономному режимі, ви можете не отримати актуальні результати, якщо шукаєте з даними про трафік у реальному часі.",
        trafficOverlayLabel: "Шар Трафіку в Реальному Часі",
        trafficRouteLabel: "Маршрут з урахуванням Трафіку",
        trafficOverlayOn: "Показати Трафік",
        trafficOverlayOff: "Приховати Трафік",
        trafficRouteOn: "Уникати Заторів",
        trafficRouteOff: "Найшвидший Шлях (Без заторів)"
    },
    nl: {
        title: "IstRoute",
        subtitle: "Neural A* Routeplanner",
        addLocation: "Locatie Toevoegen",
        locationDesc: "Klik op een punt op de kaart of voer breedte-/lengtegraad in:",
        placeholder: "bijv. 41.0369, 28.9784",
        addButton: "Toevoegen",
        popularLocations: "Favoriete Locaties",
        noFavorites: "Nog geen favoriete locaties toegevoegd.",
        addFav: "Favoriet toevoegen",
        removeFav: "Favoriet verwijderen",
        waypointsTitle: "Tussenstops",
        clearAll: "Alles Wissen",
        emptyStateText: "Nog geen locaties toegevoegd.",
        emptyStateSub: "Klik op de kaart of voer hierboven coördinaten in om uw eerste locatie toe te voegen.",
        settingsTitle: "Optimalisatie Instellingen",
        heuristicLabel: "Algoritme Heuristiek",
        neuralText: "Neural Heuristic (ONNX)",
        classicText: "Haversine Heuristic (Klassieke A*)",
        routeModeLabel: "Route Modus",
        loopText: "Terug naar Start (Rondrit)",
        openText: "Open Route (Vaste Start/Eind)",
        optimizeBtn: "Route Optimaliseren",
        optimizingBtn: "Optimaliseren...",
        analysisTitle: "Route Analyse",
        distanceLabel: "Totale Afstand",
        durationLabel: "Geschatte Tijd",
        timeLabel: "Optimalisatie Tijd",
        segmentsLabel: "Aantal Segmenten",
        logsButton: "Optimalisatie Logs (2-opt)",
        mapOverlay: "Klik op de kaart om direct coördinaten te krijgen, klik daarna op \"Toevoegen\" om het in uw route op te nemen.",
        errorMinWps: "Er moeten minimaal 2 coördinaten worden ingevoerd.",
        alertCoords: "Voer geldige coördinaten in voor Istanbul! (Breedtegraad: 40-42, Lengtegraad: 28-30)",
        alertFormat: "Voer coördinaten in het formaat \"Breedtegraad, Lengtegraad\" in! (bijv. 41.0369, 28.9784)",
        alertServer: "Kan geen verbinding maken met de route-optimalisatieserver.",
        alertOptError: "Optimalisatiefout: ",
        startLabel: "Start",
        endLabel: "Eind",
        waypointLabel: "Stop",
        segmentLabel: "Segment",
        foundLabel: "Gevonden",
        notFoundLabel: "Niet gevonden",
        secLabel: "seconden",
        minLabel: "minuten",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "OSM ID",
        deleteLabel: "Stop Verwijderen",
        startBadgeTitle: "Als Start Instellen",
        endBadgeTitle: "Als Eind Instellen",
        popupSelectedCoord: "Geselecteerde Locatie",
        popupSelectedDesc: "Klik op de knop Toevoegen om dit aan uw route toe te voegen.",
        offlineWarningText: "Omdat u momenteel offline bent, krijgt u mogelijk geen nauwkeurige resultaten als u zoekt met live verkeersgegevens.",
        trafficOverlayLabel: "Live Verkeerslaag",
        trafficRouteLabel: "Verkeersbewuste Routeplanning",
        trafficOverlayOn: "Toon Verkeer",
        trafficOverlayOff: "Verberg Verkeer",
        trafficRouteOn: "Vermijd Drukte",
        trafficRouteOff: "Snelste Weg (Zonder verkeer)"
    },
    sv: {
        title: "IstRoute",
        subtitle: "Neural A* Ruttplanerare",
        addLocation: "Lägg till Plats",
        locationDesc: "Klicka på en punkt på kartan eller ange latitud/longitud:",
        placeholder: "t.ex. 41.0369, 28.9784",
        addButton: "Lägg till",
        popularLocations: "Favoritplatser",
        noFavorites: "Inga favoritplatser har lagts till än.",
        addFav: "Lägg till i favoriter",
        removeFav: "Ta bort från favoriter",
        waypointsTitle: "Mellanliggande stopp",
        clearAll: "Rensa Allt",
        emptyStateText: "Inga platser har lagts till än.",
        emptyStateSub: "Klicka på kartan eller ange koordinater ovan för att lägga till din första plats.",
        settingsTitle: "Optimeringsinställningar",
        heuristicLabel: "Algoritmeuristisk",
        neuralText: "Neural Heuristic (ONNX)",
        classicText: "Haversine Heuristic (Klassisk A*)",
        routeModeLabel: "Ruttläge",
        loopText: "Återvänd till Start (Rundtur)",
        openText: "Öppen Rutt (Fast Start/Slut)",
        optimizeBtn: "Optimera Rutt",
        optimizingBtn: "Optimerar...",
        analysisTitle: "Ruttanalys",
        distanceLabel: "Total Distans",
        durationLabel: "Beräknad Tid",
        timeLabel: "Optimeringstid",
        segmentsLabel: "Antal Segment",
        logsButton: "Optimeringsloggar (2-opt)",
        mapOverlay: "Klicka på kartan för att hämta koordinater direkt, klicka sedan på \"Lägg till\" för att inkludera det i din rutt.",
        errorMinWps: "Minst 2 koordinater måste anges.",
        alertCoords: "Ange giltiga Istanbul-koordinater! (Latitud: 40-42, Longitud: 28-30)",
        alertFormat: "Ange koordinater i formatet \"Latitud, Longitud\"! (t.ex. 41.0369, 28.9784)",
        alertServer: "Kunde inte ansluta till ruttoptimeringsservern.",
        alertOptError: "Optimeringsfel: ",
        startLabel: "Start",
        endLabel: "Slut",
        waypointLabel: "Stopp",
        segmentLabel: "Segment",
        foundLabel: "Hittad",
        notFoundLabel: "Hittades inte",
        secLabel: "sekunder",
        minLabel: "minuter",
        kmLabel: "km",
        msLabel: "ms",
        osmIdLabel: "OSM ID",
        deleteLabel: "Ta bort Stopp",
        startBadgeTitle: "Sätt som Start",
        endBadgeTitle: "Sätt som Slut",
        popupSelectedCoord: "Vald Plats",
        popupSelectedDesc: "Klicka på knappen Lägg till för att lägga till detta till din rutt.",
        offlineWarningText: "Eftersom du för närvarande är offline kan du eventuellt inte få korrekta resultat om du söker med live-trafikdata.",
        trafficOverlayLabel: "Live Trafikskikt",
        trafficRouteLabel: "Trafikmedveten Ruttplanering",
        trafficOverlayOn: "Visa Trafik",
        trafficOverlayOff: "Dölj Trafik",
        trafficRouteOn: "Undvik Trafik",
        trafficRouteOff: "Snabbaste Väg (Utan trafik)"
    },
    el: {
        title: "IstRoute",
        subtitle: "Neural A* Σχεδιαστής Διαδρομής",
        addLocation: "Προσθήκη Τοποθεσίας",
        locationDesc: "Κάντε κλικ σε ένα σημείο στο χάρτη ή εισάγετε γεωγραφικό πλάτος/μήκος:",
        placeholder: "π.χ. 41.0369, 28.9784",
        addButton: "Προσθήκη",
        popularLocations: "Αγαπημένες Τοποθεσίες",
        noFavorites: "Δεν έχουν προστεθεί αγαπημένες τοποθεσίες ακόμα.",
        addFav: "Προσθήκη στα Αγαπημένα",
        removeFav: "Αφαίρεση από τα Αγαπημένα",
        waypointsTitle: "Σημεία Διαδρομής",
        clearAll: "Διαγραφή Όλων",
        emptyStateText: "Δεν έχουν προστεθεί τοποθεσίες ακόμα.",
        emptyStateSub: "Κάντε κλικ στο χάρτη ή εισάγετε συντεταγμένες παραπάνω για να προσθέσετε το πρώτο σας σημείο.",
        settingsTitle: "Ρυθμίσεις Βελτιστοποίησης",
        heuristicLabel: "Ευρετικός Αλγόριθμος",
        neuralText: "Neural Heuristic (ONNX)",
        classicText: "Haversine Heuristic (Κλασικό A*)",
        routeModeLabel: "Λειτουργία Διαδρομής",
        loopText: "Επιστροφή στην Αφετηρία (Κλειστή)",
        openText: "Ανοιχτή Διαδρομή (Σταθερή Αφετηρία/Τερματισμός)",
        optimizeBtn: "Βελτιστοποίηση Διαδρομής",
        optimizingBtn: "Βελτιστοποίηση...",
        analysisTitle: "Ανάλυση Διαδρομής",
        distanceLabel: "Συνολική Απόσταση",
        durationLabel: "Εκτιμώμενος Χρόνος",
        timeLabel: "Χρόνος Βελτιστοποίησης",
        segmentsLabel: "Αριθμός Τμημάτων",
        logsButton: "Καταγραφές Βελτιστοποίησης (2-opt)",
        mapOverlay: "Κάντε κλικ στο χάρτη για να λάβετε συντεταγμένες απευθείας, και μετά κάντε κλικ στο \"Προσθήκη\" για να τις συμπεριλάβετε στη διαδρομή σας.",
        errorMinWps: "Πρέπει να εισαχθούν τουλάχιστον 2 συντεταγμένες.",
        alertCoords: "Παρακαλώ εισάγετε έγκυρες συντεταγμένες Κωνσταντινούπολης! (Πλάτος: 40-42, Μήκος: 28-30)",
        alertFormat: "Εισάγετε συντεταγμένες στη μορφή \"Πλάτος, Μήκος\"! (π.χ. 41.0369, 28.9784)",
        alertServer: "Αδυναμία σύνδεσης με το διακομιστή βελτιστοποίησης διαδρομής.",
        alertOptError: "Σφάλμα βελτιστοποίησης: ",
        startLabel: "Αφετηρία",
        endLabel: "Τερματισμός",
        waypointLabel: "Στάση",
        segmentLabel: "Τμήμα",
        foundLabel: "Βρέθηκε",
        notFoundLabel: "Δεν βρέθηκε",
        secLabel: "δευτερόλεπτα",
        minLabel: "λεπτά",
        kmLabel: "χλμ",
        msLabel: "ms",
        osmIdLabel: "OSM ID",
        deleteLabel: "Διαγραφή Στάσης",
        startBadgeTitle: "Ορισμός ως Αφετηρία",
        endBadgeTitle: "Ορισμός ως Τερματισμός",
        popupSelectedCoord: "Επιλεγμένη Τοποθεσία",
        popupSelectedDesc: "Κάντε κλικ στο κουμπί Προσθήκη για να το προσθέσετε στη διαδρομή σας.",
        offlineWarningText: "Επειδή βρίσκεστε εκτός σύνδεσης, ενδέχεται να μην λάβετε ακριβή αποτελέσματα εάν κάνετε αναζήτηση με ζωντανά δεδομένα κίνησης.",
        trafficOverlayLabel: "Επίπεδο Κίνησης σε Πραγματικό Χρόνο",
        trafficRouteLabel: "Σχεδιασμός με Αποφυγή Κίνησης",
        trafficOverlayOn: "Εμφάνιση Κίνησης",
        trafficOverlayOff: "Απόκρυψη Κίνησης",
        trafficRouteOn: "Αποφυγή Κίνησης",
        trafficRouteOff: "Γρηγορότερη Διαδρομή (Χωρίς κίνηση)"
    }
};

// Uygulama Başlangıcı
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initLanguage();
    initMap();
    initEventListeners();
    renderFavorites();
});

// --- Tema Yönetimi ---
function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    state.theme = savedTheme;
    
    if (savedTheme === 'light') {
        document.body.classList.remove('dark-theme');
        document.body.classList.add('light-theme');
        updateThemeToggleIcon('light');
    } else {
        document.body.classList.remove('light-theme');
        document.body.classList.add('dark-theme');
        updateThemeToggleIcon('dark');
    }
}

function updateThemeToggleIcon(theme) {
    const btnIcon = document.querySelector('#theme-toggle i');
    if (btnIcon) {
        if (theme === 'light') {
            btnIcon.className = 'fa-solid fa-sun';
        } else {
            btnIcon.className = 'fa-solid fa-moon';
        }
    }
}

function toggleTheme() {
    const newTheme = state.theme === 'dark' ? 'light' : 'dark';
    state.theme = newTheme;
    localStorage.setItem('theme', newTheme);
    
    if (newTheme === 'light') {
        document.body.classList.replace('dark-theme', 'light-theme');
    } else {
        document.body.classList.replace('light-theme', 'dark-theme');
    }
    
    updateThemeToggleIcon(newTheme);
    updateMapTiles();
}

// --- Dil Yönetimi ---
function initLanguage() {
    const savedLang = localStorage.getItem('lang') || 'tr';
    state.lang = savedLang;
    
    const langSelect = document.getElementById('lang-select');
    if (langSelect) {
        langSelect.value = savedLang;
        langSelect.addEventListener('change', (e) => {
            state.lang = e.target.value;
            localStorage.setItem('lang', state.lang);
            updateLanguage();
        });
    }
    
    updateLanguage();
}

function updateLanguage() {
    const lang = state.lang;
    
    // data-i18n etiketli tüm elementleri güncelle (fallback desteğiyle)
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const translationText = (translations[lang] && translations[lang][key]) 
                             || (translations['en'] && translations['en'][key]) 
                             || (translations['tr'] && translations['tr'][key])
                             || key;

        // Elementin içinde ikon var mı diye bak, varsa koru
        const icon = el.querySelector('i');
        if (icon) {
            const badge = el.querySelector('.badge');
            const badgeHtml = badge ? badge.outerHTML : '';
            el.innerHTML = `${icon.outerHTML} <span>${translationText}</span> ${badgeHtml}`;
        } else {
            el.textContent = translationText;
        }
    });
    
    // Giriş kutusu placeholder'ını güncelle
    const coordInput = document.getElementById('coord-input');
    if (coordInput) {
        coordInput.placeholder = translations[lang].placeholder;
    }
    
    // Durum etiketlerini güncelle
    const heuristicToggle = document.getElementById('heuristic-toggle');
    const heuristicStatus = document.getElementById('heuristic-status');
    if (heuristicToggle && heuristicStatus) {
        heuristicStatus.textContent = heuristicToggle.checked ? translations[lang].classicText : translations[lang].neuralText;
    }
    
    const loopToggle = document.getElementById('loop-toggle');
    const loopStatus = document.getElementById('loop-status');
    if (loopToggle && loopStatus) {
        loopStatus.textContent = loopToggle.checked ? translations[lang].loopText : translations[lang].openText;
    }
    
    // Harita üzerindeki overlay metnini doğrudan güncelle
    const overlay = document.querySelector('.map-overlay-info p');
    if (overlay) {
        const mapOverlayText = translations[lang].mapOverlay || translations['en'].mapOverlay || translations['tr'].mapOverlay;
        overlay.innerHTML = `<i class="fa-solid fa-circle-info"></i> ${mapOverlayText}`;
    }

    // Trafik etiketlerini güncelle
    const trafficOverlayToggle = document.getElementById('traffic-overlay-toggle');
    const trafficOverlayStatus = document.getElementById('traffic-overlay-status');
    if (trafficOverlayToggle && trafficOverlayStatus) {
        const key = trafficOverlayToggle.checked ? 'trafficOverlayOn' : 'trafficOverlayOff';
        trafficOverlayStatus.textContent = (translations[lang] && translations[lang][key])
                                        || (translations['en'] && translations['en'][key])
                                        || (translations['tr'] && translations['tr'][key])
                                        || key;
    }
    
    const trafficRouteToggle = document.getElementById('traffic-route-toggle');
    const trafficRouteStatus = document.getElementById('traffic-route-status');
    if (trafficRouteToggle && trafficRouteStatus) {
        const key = trafficRouteToggle.checked ? 'trafficRouteOn' : 'trafficRouteOff';
        trafficRouteStatus.textContent = (translations[lang] && translations[lang][key])
                                      || (translations['en'] && translations['en'][key])
                                      || (translations['tr'] && translations['tr'][key])
                                      || key;
    }
    
    // Waypoint listesini ve harita işaretçilerini dile göre yenile
    updateWaypointList();
    if (state.waypoints.length > 0) {
        if (state.polylines.length > 0) {
            // Rota çizilmiş durumdaysa, sadece marker'ları optimize edilmiş sırada güncelle
            renderInitialMarkers();
        } else {
            renderInitialMarkers();
        }
    }
    renderFavorites();
}

// --- Harita Yönetimi ---
function initMap() {
    const istanbulCenter = [41.0082, 28.9784];
    
    state.map = L.map('map', {
        zoomControl: true,
        preferCanvas: true
    }).setView(istanbulCenter, 11);
    
    updateMapTiles();
    state.map.on('click', onMapClick);
}

function updateMapTiles() {
    if (state.tileLayer) {
        state.map.removeLayer(state.tileLayer);
    }
    
    let tileUrl, attribution;
    if (state.theme === 'light') {
        tileUrl = 'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png';
        attribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';
    } else {
        tileUrl = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
        attribution = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';
    }
    
    state.tileLayer = L.tileLayer(tileUrl, {
        attribution: attribution,
        maxZoom: 20
    }).addTo(state.map);
}

function onMapClick(e) {
    const lat = e.latlng.lat;
    const lng = e.latlng.lng;
    const coordString = `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
    
    const coordInput = document.getElementById('coord-input');
    coordInput.value = coordString;
    coordInput.focus();
    
    if (state.clickMarker) {
        state.clickMarker.setLatLng(e.latlng);
    } else {
        const clickIcon = L.icon({
            iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-gold.png',
            shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
            iconSize: [25, 41],
            iconAnchor: [12, 41],
            popupAnchor: [1, -34],
            shadowSize: [41, 41]
        });
        
        state.clickMarker = L.marker(e.latlng, { icon: clickIcon })
            .addTo(state.map);
    }
    updateClickMarkerPopup(lat, lng);
    state.clickMarker.openPopup();
}

function updateClickMarkerPopup(lat, lng) {
    if (!state.clickMarker) return;
    const lang = state.lang;
    const starred = state.favorites.some(f => Math.abs(f.lat - lat) < 1e-6 && Math.abs(f.lng - lng) < 1e-6);
    
    const labelAdd = translations[lang].addFav || translations['en'].addFav || 'Favorilere Ekle';
    const labelRemove = translations[lang].removeFav || translations['en'].removeFav || 'Favorilerden Çıkar';
    
    const starBtnHtml = `
        <button class="btn btn-sm ${starred ? 'btn-warning' : 'btn-outline-warning'}" 
                style="margin-top: 8px; display: inline-flex; align-items: center; gap: 6px; font-size: 11px; padding: 4px 10px; border-radius: 8px; border: 1px solid var(--border-glass); background: ${starred ? 'rgba(234,179,8,0.15)' : 'var(--card-bg)'}; color: ${starred ? '#eab308' : 'var(--text-secondary)'}; cursor: pointer; transition: all 0.2s; font-family: inherit;" 
                onclick="toggleFavoriteClick(${lat}, ${lng})">
            <i class="${starred ? 'fa-solid' : 'fa-regular'} fa-star" style="${starred ? 'color: #eab308;' : ''}"></i>
            <span>${starred ? labelRemove : labelAdd}</span>
        </button>
    `;
    
    state.clickMarker.setPopupContent(`
        <div style="font-family: var(--font-family, inherit);">
            <b>${translations[lang].popupSelectedCoord}</b><br>
            <span style="font-size: 11px; color: var(--text-muted);">${translations[lang].popupSelectedDesc}</span><br>
            ${starBtnHtml}
        </div>
    `);
}

function toggleFavoriteClick(lat, lng) {
    const favIndex = state.favorites.findIndex(f => Math.abs(f.lat - lat) < 1e-6 && Math.abs(f.lng - lng) < 1e-6);
    if (favIndex > -1) {
        state.favorites.splice(favIndex, 1);
    } else {
        const name = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
        state.favorites.push({ lat, lng, name });
    }
    localStorage.setItem('favorites', JSON.stringify(state.favorites));
    renderFavorites();
    updateClickMarkerPopup(lat, lng);
    updateWaypointList();
}

function renderFavorites() {
    const shortcutsContainer = document.getElementById('favorites-shortcuts') || document.getElementById('landmarks-shortcuts');
    if (!shortcutsContainer) return;
    
    shortcutsContainer.innerHTML = '';
    
    if (state.favorites.length === 0) {
        const emptySpan = document.createElement('span');
        emptySpan.className = 'loading-inline';
        emptySpan.style.fontStyle = 'italic';
        emptySpan.setAttribute('data-i18n', 'noFavorites');
        emptySpan.innerHTML = `<i class="fa-regular fa-star"></i> <span>${translations[state.lang].noFavorites || 'Henüz favori konum eklenmedi.'}</span>`;
        shortcutsContainer.appendChild(emptySpan);
        return;
    }
    
    state.favorites.forEach((fav, index) => {
        const badge = document.createElement('span');
        badge.className = 'landmark-badge';
        badge.style.display = 'inline-flex';
        badge.style.alignItems = 'center';
        badge.style.gap = '6px';
        badge.style.padding = '6px 10px 6px 12px';
        
        badge.innerHTML = `
            <i class="fa-solid fa-location-dot"></i> 
            <span>${fav.name}</span>
            <button class="fav-delete-btn" style="background:none; border:none; padding:0; margin-left:4px; color:var(--text-muted); cursor:pointer; display:flex; align-items:center; justify-content:center; transition:color 0.2s; font-size:10px;" title="Favorilerden Çıkar" onclick="event.stopPropagation(); removeFavorite(${index})">
                <i class="fa-solid fa-xmark"></i>
            </button>
        `;
        badge.title = `${fav.lat.toFixed(5)}, ${fav.lng.toFixed(5)}`;
        
        badge.addEventListener('click', () => {
            addWaypoint(fav.lat, fav.lng, fav.name);
        });
        shortcutsContainer.appendChild(badge);
    });
}

function removeFavorite(index) {
    state.favorites.splice(index, 1);
    localStorage.setItem('favorites', JSON.stringify(state.favorites));
    renderFavorites();
    updateWaypointList();
    if (state.clickMarker) {
        const lat = state.clickMarker.getLatLng().lat;
        const lng = state.clickMarker.getLatLng().lng;
        updateClickMarkerPopup(lat, lng);
    }
}

function toggleFavoriteWaypoint(idx) {
    const wp = state.waypoints[idx];
    if (!wp) return;
    
    const favIndex = state.favorites.findIndex(f => Math.abs(f.lat - wp.lat) < 1e-6 && Math.abs(f.lng - wp.lng) < 1e-6);
    if (favIndex > -1) {
        state.favorites.splice(favIndex, 1);
    } else {
        state.favorites.push({
            lat: wp.lat,
            lng: wp.lng,
            name: wp.name
        });
    }
    localStorage.setItem('favorites', JSON.stringify(state.favorites));
    renderFavorites();
    updateWaypointList();
    if (state.clickMarker) {
        const lat = state.clickMarker.getLatLng().lat;
        const lng = state.clickMarker.getLatLng().lng;
        updateClickMarkerPopup(lat, lng);
    }
}

async function optimizeRoute() {
    if (state.waypoints.length < 2) return;
    
    const optimizeBtn = document.getElementById('optimize-btn');
    const statsPanel = document.getElementById('stats-panel');
    const logsList = document.getElementById('log-list');
    const lang = state.lang;
    
    optimizeBtn.disabled = true;
    optimizeBtn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> ${translations[lang].optimizingBtn}`;
    
    clearRouteLines();
    
    const useHaversine = document.getElementById('heuristic-toggle').checked;
    
    try {
        const response = await fetch('/api/route', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                waypoints: state.waypoints,
                use_haversine: useHaversine,
                is_loop: state.isLoop,
                start_index: state.startIndex,
                end_index: state.endIndex,
                use_traffic: state.trafficRouteActive
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('stat-distance').textContent = `${data.total_length_km.toFixed(2)} ${translations[lang].kmLabel}`;
            document.getElementById('stat-duration').textContent = `${data.total_time_min.toFixed(0)} ${translations[lang].minLabel}`;
            document.getElementById('stat-time').textContent = `${data.elapsed_ms.toFixed(0)} ${translations[lang].msLabel}`;
            document.getElementById('stat-segments').textContent = data.segments.length;
            
            logsList.innerHTML = '';
            data.optimization_log.forEach(log => {
                const li = document.createElement('li');
                li.textContent = log;
                logsList.appendChild(li);
            });
            
            statsPanel.classList.remove('hide');
            drawRoute(data.segments, data.waypoints_ordered);
            
        } else {
            alert(`${translations[lang].alertOptError}${data.error}`);
        }
    } catch (err) {
        console.error(err);
        alert(translations[lang].alertServer);
    } finally {
        optimizeBtn.disabled = false;
        optimizeBtn.innerHTML = `<i class="fa-solid fa-wand-magic-sparkles"></i> ${translations[lang].optimizeBtn}`;
    }
}

// --- Rota Çizimi ---
function clearRouteLines() {
    state.polylines.forEach(pl => state.map.removeLayer(pl));
    state.polylines = [];
}

function drawRoute(segments, orderedWaypoints) {
    clearRouteLines();
    
    const bounds = [];
    const M = segments.length;
    const lang = state.lang;
    
    segments.forEach((seg, idx) => {
        if (!seg.found || seg.path_coords.length === 0) return;
        
        // HSL İnterpolasyonu: Başlangıç Yeşil (120 derece), Bitiş Kırmızı (0 derece)
        const hue = M > 1 ? 120 - (idx / (M - 1)) * 120 : 120;
        const color = `hsl(${hue}, 85%, 45%)`;
        
        // Üst üste binen yollarda önceki yolların (küçük idx) altta kalıp kaybolmaması için
        // daha kalın çizilmesini sağlıyoruz (konsept: iç içe renk halkaları/sınır çizgileri).
        const minWeight = 4;
        const maxWeight = 14;
        const step = 1.5;
        const weight = Math.min(maxWeight, minWeight + (M - 1 - idx) * step);
        
        const latlngs = seg.path_coords.map(coord => [coord[0], coord[1]]);
        bounds.push(...latlngs);
        
        const popupHtml = `
            <div class="popup-details">
                <b>🛣️ ${translations[lang].segmentLabel} ${idx + 1} (${idx + 1} ➔ ${idx + 2})</b>
                <div class="popup-divider"></div>
                <strong>${translations[lang].distanceLabel}:</strong> ${(seg.total_length_m / 1000).toFixed(2)} ${translations[lang].kmLabel}<br>
                <strong>${translations[lang].durationLabel}:</strong> ${(seg.total_time_s / 60).toFixed(1)} ${translations[lang].minLabel}<br>
                <strong>Algorithm:</strong> ${seg.elapsed_ms.toFixed(1)} ms
            </div>
        `;
        
        const polyline = L.polyline(latlngs, {
            color: color,
            weight: weight,
            opacity: 0.85,
            lineJoin: 'round'
        })
        .bindPopup(popupHtml)
        .addTo(state.map);
        
        state.polylines.push(polyline);
    });
    
    if (bounds.length > 0) {
        state.map.fitBounds(L.latLngBounds(bounds), { padding: [50, 50] });
    }
    
    updateMarkersToOptimized(orderedWaypoints);
}

function updateMarkersToOptimized(orderedWaypoints) {
    clearMarkers();
    
    const N = orderedWaypoints.length;
    const lang = state.lang;
    orderedWaypoints.forEach((wp, idx) => {
        const isStart = idx === 0;
        const isEnd = idx === N - 1;
        
        const hue = N > 1 ? 120 - (idx / (N - 1)) * 120 : 120;
        const badgeColor = `hsl(${hue}, 85%, 45%)`;
        
        let classNames = 'stop-number-badge';
        if (isStart) classNames += ' is-start';
        if (isEnd && !state.isLoop) classNames += ' is-end';
        
        const icon = L.divIcon({
            className: 'stop-number-marker',
            html: `<div class="${classNames}" style="--badge-bg: ${badgeColor}">${idx + 1}</div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });
        
        const label = isStart ? `🏁 ${translations[lang].startLabel}` : (isEnd && !state.isLoop ? `🏴 ${translations[lang].endLabel}` : `📍 ${translations[lang].waypointLabel} ${idx + 1}`);
        const marker = L.marker([wp.lat, wp.lng], { icon: icon })
            .bindPopup(`<b>${label}</b><br>${wp.name}<br>${translations[lang].osmIdLabel}: ${wp.node_id}`)
            .addTo(state.map);
            
        state.markers.push(marker);
    });
}

// --- Waypoint Ekleme / Silme / Seçim Mantığı ---
function addWaypoint(lat, lng, name = null) {
    lat = parseFloat(lat);
    lng = parseFloat(lng);
    const lang = state.lang;
    
    if (isNaN(lat) || isNaN(lng) || lat < 39 || lat > 43 || lng < 27 || lng > 31) {
        alert(translations[lang].alertCoords);
        return;
    }
    
    if (!name) {
        name = `${lat.toFixed(5)}, ${lng.toFixed(5)}`;
    }
    
    state.waypoints.push({ lat, lng, name });
    
    if (!state.isLoop) {
        state.endIndex = state.waypoints.length - 1;
    }
    
    updateWaypointList();
    renderInitialMarkers();
    
    document.getElementById('coord-input').value = '';
    
    if (state.clickMarker) {
        state.map.removeLayer(state.clickMarker);
        state.clickMarker = null;
    }
}

function removeWaypoint(index) {
    state.waypoints.splice(index, 1);
    
    if (state.startIndex === index) {
        state.startIndex = 0;
    } else if (state.startIndex > index) {
        state.startIndex--;
    }
    
    if (state.endIndex === index) {
        state.endIndex = Math.max(0, state.waypoints.length - 1);
    } else if (state.endIndex > index) {
        state.endIndex--;
    }
    
    if (state.waypoints.length > 0) {
        state.startIndex = Math.max(0, Math.min(state.startIndex, state.waypoints.length - 1));
        state.endIndex = Math.max(0, Math.min(state.endIndex, state.waypoints.length - 1));
    } else {
        state.startIndex = 0;
        state.endIndex = 0;
    }
    
    updateWaypointList();
    renderInitialMarkers();
    clearRouteLines();
    
    document.getElementById('stats-panel').classList.add('hide');
}

function setStartWaypoint(index) {
    state.startIndex = index;
    if (state.endIndex === index && state.waypoints.length > 1) {
        state.endIndex = (index + 1) % state.waypoints.length;
    }
    updateWaypointList();
    renderInitialMarkers();
    clearRouteLines();
    document.getElementById('stats-panel').classList.add('hide');
}

// Bitiş noktası ayarlar
function setEndWaypoint(index) {
    if (state.isLoop) return;
    state.endIndex = index;
    if (state.startIndex === index && state.waypoints.length > 1) {
        state.startIndex = (index + 1) % state.waypoints.length;
    }
    updateWaypointList();
    renderInitialMarkers();
    clearRouteLines();
    document.getElementById('stats-panel').classList.add('hide');
}

function clearAllWaypoints() {
    state.waypoints = [];
    state.startIndex = 0;
    state.endIndex = 0;
    updateWaypointList();
    clearMarkers();
    clearRouteLines();
    
    if (state.clickMarker) {
        state.map.removeLayer(state.clickMarker);
        state.clickMarker = null;
    }
    
    document.getElementById('stats-panel').classList.add('hide');
    document.getElementById('coord-input').value = '';
}

function clearMarkers() {
    state.markers.forEach(m => state.map.removeLayer(m));
    state.markers = [];
}

// Optimizasyon öncesi (statik) marker çizimi
function renderInitialMarkers() {
    clearMarkers();
    
    const N = state.waypoints.length;
    const lang = state.lang;
    state.waypoints.forEach((wp, idx) => {
        const isStart = state.startIndex === idx;
        const isEnd = state.endIndex === idx;
        
        const hue = N > 1 ? 120 - (idx / (N - 1)) * 120 : 120;
        const badgeColor = `hsl(${hue}, 85%, 45%)`;
        
        let classNames = 'stop-number-badge';
        if (isStart) classNames += ' is-start';
        if (isEnd && !state.isLoop) classNames += ' is-end';
        
        const icon = L.divIcon({
            className: 'stop-number-marker',
            html: `<div class="${classNames}" style="--badge-bg: ${badgeColor}">${idx + 1}</div>`,
            iconSize: [32, 32],
            iconAnchor: [16, 16]
        });
        
        const label = isStart ? `🏁 ${translations[lang].startLabel}` : (isEnd && !state.isLoop ? `🏴 ${translations[lang].endLabel}` : `📍 ${translations[lang].waypointLabel} ${idx + 1}`);
        const marker = L.marker([wp.lat, wp.lng], { icon: icon })
            .bindPopup(`<b>${label}</b><br>${wp.name}`)
            .addTo(state.map);
            
        state.markers.push(marker);
    });
}

function updateWaypointList() {
    const list = document.getElementById('waypoint-list');
    const emptyState = document.getElementById('empty-state');
    const countBadge = document.getElementById('waypoints-count');
    const optimizeBtn = document.getElementById('optimize-btn');
    const lang = state.lang;
    
    list.innerHTML = '';
    countBadge.textContent = state.waypoints.length;
    
    if (state.waypoints.length === 0) {
        emptyState.classList.remove('hide');
        optimizeBtn.disabled = true;
        return;
    }
    
    emptyState.classList.add('hide');
    optimizeBtn.disabled = state.waypoints.length < 2;
    
    state.waypoints.forEach((wp, idx) => {
        const li = document.createElement('li');
        li.className = 'waypoint-item';
        
        const isStart = state.startIndex === idx;
        const isEnd = state.endIndex === idx;
        const starred = state.favorites.some(f => Math.abs(f.lat - wp.lat) < 1e-6 && Math.abs(f.lng - wp.lng) < 1e-6);
        
        li.innerHTML = `
            <div class="wp-meta">
                <div class="wp-index" style="${isStart ? 'background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3);' : (isEnd && !state.isLoop ? 'background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3);' : '')}">
                    ${idx + 1}
                </div>
                <div class="wp-details">
                    <span class="wp-name">${wp.name}</span>
                    <span class="wp-coords">${wp.lat.toFixed(5)}, ${wp.lng.toFixed(5)}</span>
                </div>
            </div>
            <div class="wp-actions">
                <button class="wp-action-btn star-badge-btn ${starred ? 'active' : ''}" title="${starred ? (translations[lang].removeFav || translations['en'].removeFav) : (translations[lang].addFav || translations['en'].addFav)}" onclick="toggleFavoriteWaypoint(${idx})">
                    <i class="${starred ? 'fa-solid' : 'fa-regular'} fa-star" style="${starred ? 'color: #eab308;' : ''}"></i>
                </button>
                <button class="wp-action-btn start-badge-btn ${isStart ? 'active' : ''}" title="${translations[lang].startBadgeTitle}" onclick="setStartWaypoint(${idx})">
                    <i class="fa-solid fa-plane-departure"></i>
                </button>
                <button class="wp-action-btn end-badge-btn ${isEnd && !state.isLoop ? 'active' : ''}" title="${translations[lang].endBadgeTitle}" onclick="setEndWaypoint(${idx})" ${state.isLoop ? 'disabled style="display: none;"' : ''}>
                    <i class="fa-solid fa-plane-arrival"></i>
                </button>
                <button class="wp-delete-btn" title="${translations[lang].deleteLabel}" onclick="removeWaypoint(${idx})">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </div>
        `;
        list.appendChild(li);
    });
}

// --- Event Listeners ve Buton Olayları ---
function initEventListeners() {
    document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
    const lang = state.lang;
    
    document.getElementById('add-coord-btn').addEventListener('click', () => {
        const input = document.getElementById('coord-input').value.trim();
        if (!input) return;
        
        const match = input.match(/^([+-]?\d+\.?\d*)\s*,\s*([+-]?\d+\.?\d*)$/);
        if (match) {
            const lat = parseFloat(match[1]);
            const lng = parseFloat(match[2]);
            addWaypoint(lat, lng);
        } else {
            alert(translations[state.lang].alertFormat);
        }
    });
    
    document.getElementById('coord-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            document.getElementById('add-coord-btn').click();
        }
    });
    
    document.getElementById('clear-all-btn').addEventListener('click', clearAllWaypoints);
    document.getElementById('optimize-btn').addEventListener('click', optimizeRoute);
    
    // Algoritma Seçim Toggle Değişimi
    const heuristicToggle = document.getElementById('heuristic-toggle');
    const heuristicStatus = document.getElementById('heuristic-status');
    heuristicToggle.addEventListener('change', () => {
        heuristicStatus.textContent = heuristicToggle.checked ? translations[state.lang].classicText : translations[state.lang].neuralText;
    });
    
    // Rota Modu Loop Toggle Değişimi
    const loopToggle = document.getElementById('loop-toggle');
    const loopStatus = document.getElementById('loop-status');
    loopToggle.addEventListener('change', () => {
        state.isLoop = loopToggle.checked;
        loopStatus.textContent = state.isLoop ? translations[state.lang].loopText : translations[state.lang].openText;
        if (!state.isLoop) {
            state.endIndex = Math.max(0, state.waypoints.length - 1);
        }
        updateWaypointList();
        renderInitialMarkers();
        clearRouteLines();
        document.getElementById('stats-panel').classList.add('hide');
    });
    
    // Akordeon Log Açma/Kapama
    const toggleLogsBtn = document.getElementById('toggle-logs-btn');
    const logsContainer = document.getElementById('optimization-logs');
    const chevronIcon = toggleLogsBtn.querySelector('.chevron-icon');
    
    toggleLogsBtn.addEventListener('click', () => {
        logsContainer.classList.toggle('hide');
        chevronIcon.classList.toggle('chevron-active');
    });

    // Trafik Overlay Toggle Değişimi
    const trafficOverlayToggle = document.getElementById('traffic-overlay-toggle');
    if (trafficOverlayToggle) {
        trafficOverlayToggle.addEventListener('change', () => {
            state.trafficOverlayActive = trafficOverlayToggle.checked;
            updateLanguage();
            
            if (state.trafficOverlayActive) {
                fetchTrafficData();
                // 60 saniyede bir güncelle
                state.trafficTimer = setInterval(fetchTrafficData, 60000);
            } else {
                if (state.trafficTimer) {
                    clearInterval(state.trafficTimer);
                    state.trafficTimer = null;
                }
                clearTrafficLayers();
            }
        });
    }

    // Trafik Rotalama Toggle Değişimi
    const trafficRouteToggle = document.getElementById('traffic-route-toggle');
    if (trafficRouteToggle) {
        trafficRouteToggle.addEventListener('change', () => {
            state.trafficRouteActive = trafficRouteToggle.checked;
            updateLanguage();
            clearRouteLines();
            document.getElementById('stats-panel').classList.add('hide');
        });
    }

    // İnternet Bağlantı Dinleyicileri
    window.addEventListener('online', updateConnectionStatus);
    window.addEventListener('offline', updateConnectionStatus);
    updateConnectionStatus();
}

function updateConnectionStatus() {
    const warningBox = document.getElementById('offline-warning-box');
    if (!warningBox) return;
    
    if (navigator.onLine) {
        warningBox.classList.add('hide');
    } else {
        warningBox.classList.remove('hide');
    }
}

// Global olarak erişilebilir olmaları için window nesnesine bağlıyoruz
window.removeWaypoint = removeWaypoint;
window.clearAllWaypoints = clearAllWaypoints;
window.setStartWaypoint = setStartWaypoint;
window.setEndWaypoint = setEndWaypoint;
window.removeFavorite = removeFavorite;
window.toggleFavoriteWaypoint = toggleFavoriteWaypoint;
window.toggleFavoriteClick = toggleFavoriteClick;
window.updateConnectionStatus = updateConnectionStatus;

// --- Trafik Katmanı ve API Yönetimi ---
async function fetchTrafficData() {
    if (!state.trafficOverlayActive) return;
    
    try {
        const response = await fetch('/api/traffic');
        const data = await response.json();
        
        if (data.success) {
            clearTrafficLayers();
            
            if (!state.trafficLayerGroup) {
                state.trafficLayerGroup = L.layerGroup().addTo(state.map);
            }
            if (!state.trafficIncidentGroup) {
                state.trafficIncidentGroup = L.layerGroup().addTo(state.map);
            }
            
            // 1. Trafik Yoğunluk Segmentlerini Çiz
            data.segments.forEach(seg => {
                // Motorway/Trunk ise 4px, Primary ise 3px, Secondary ise 2px kalınlık
                let weight = 2.5;
                if (seg.highway === 'motorway' || seg.highway === 'motorway_link') {
                    weight = 4.5;
                } else if (seg.highway === 'trunk' || seg.highway === 'trunk_link') {
                    weight = 4.0;
                } else if (seg.highway === 'primary' || seg.highway === 'primary_link') {
                    weight = 3.2;
                }
                
                const polyline = L.polyline(seg.coords, {
                    color: seg.color,
                    weight: weight,
                    opacity: 0.6,
                    lineJoin: 'round',
                    interactive: true
                });
                
                const typeText = seg.highway.toUpperCase();
                const popupHtml = `
                    <div class="popup-details">
                        <b>🛣️ ${typeText}</b><br>
                        Trafik Gecikmesi: <b>${seg.multiplier.toFixed(2)}x</b><br>
                        Durum: <span style="color: ${seg.color}; font-weight: bold;">${seg.status.toUpperCase()}</span>
                    </div>
                `;
                polyline.bindPopup(popupHtml);
                polyline.addTo(state.trafficLayerGroup);
            });
            
            // 2. Aktif Kazaları / Olayları İşaretle
            data.incidents.forEach(inc => {
                // Custom warning marker
                const iconHtml = inc.type === 'accident'
                    ? '<div class="traffic-incident-marker accident"><i class="fa-solid fa-car-burst"></i></div>'
                    : '<div class="traffic-incident-marker roadwork"><i class="fa-solid fa-person-digging"></i></div>';
                
                const customIcon = L.divIcon({
                    className: 'incident-div-icon',
                    html: iconHtml,
                    iconSize: [28, 28],
                    iconAnchor: [14, 14]
                });
                
                const marker = L.marker([inc.lat, inc.lng], { icon: customIcon })
                    .bindPopup(`<b>${inc.name}</b><br>Gecikme Çarpanı: <b>${inc.multiplier.toFixed(2)}x</b>`)
                    .addTo(state.trafficIncidentGroup);
            });
        }
    } catch (err) {
        console.error("Trafik bilgisi çekilemedi:", err);
    }
}

function clearTrafficLayers() {
    if (state.trafficLayerGroup) {
        state.trafficLayerGroup.clearLayers();
    }
    if (state.trafficIncidentGroup) {
        state.trafficIncidentGroup.clearLayers();
    }
}
