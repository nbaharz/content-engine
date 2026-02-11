# Grupanya Content Engine - Proje Raporu

## Genel Bakış

AI destekli sosyal medya içerik otomasyon aracı. Kampanya görsellerini oluşturur, profesyonel posterler üretir ve doğrudan Instagram'a yayınlar.

---

## Dosya Yapısı ve Amaçları

```
grupanya-content-engine/
├── app.py                          # Flask web uygulaması - ana dashboard ve API endpoint'leri
├── main.py                         # CLI arayüzü - test ve manuel içerik üretimi
├── scheduler.py                    # GitHub Actions ile otomatik zamanlama motoru
├── instagram.py                    # Instagram Graph API entegrasyonu
├── poster.py                       # Pillow ile poster/görsel oluşturma
├── collage.py                      # Çoklu görsel kolaj düzenleri
├── requirements.txt                # Python bağımlılıkları
├── campaigns.json                  # Kampanya verileri (gitignore)
├── campaigns.example.json          # campaigns.json şablonu
├── .env                            # API anahtarları (gitignore)
├── .env.example                    # Environment variables şablonu
├── static/
│   └── css/
│       └── style.css               # UI stilleri (açık/koyu tema)
├── templates/
│   └── index.html                  # Flask web arayüzü (responsive, interaktif)
└── .github/
    └── workflows/
        └── schedule.yml            # GitHub Actions otomasyon (günde 3 kez)
```

---

## Kullanılan Teknolojiler

| Katman | Teknoloji | Neden Kullanıldı |
|--------|-----------|------------------|
| **Web Framework** | Flask | Hafif, hızlı dashboard ve API sunumu |
| **AI Görsel Üretimi** | fal.ai (Flux) | Kampanya görseli oluşturma ve img2img stilizasyon |
| **LLM** | Claude Sonnet 4.5 (fal.ai üzerinden) | Kampanya bilgisi çıkarma, caption yazma, stil prompt'u üretme |
| **Görüntü İşleme** | Pillow | Poster oluşturma, metin yerleştirme, kolaj düzeni |
| **Web Scraping** | BeautifulSoup4 | Kampanya sayfalarından bilgi ve görsel çekme |
| **HTTP** | requests | API çağrıları ve görsel indirme |
| **Sosyal Medya** | Instagram Graph API v19.0 | Tek/carousel post yayınlama |
| **Otomasyon** | GitHub Actions (cron) | Hafta içi günde 3 kez otomatik paylaşım |
| **Frontend** | HTML5 + CSS3 + Vanilla JS | Tab-based UI, drag-drop, gerçek zamanlı önizleme |
| **İkonlar** | Lucide (CDN) | Modern UI ikonları |
| **Fontlar** | Google Fonts (Inter), Arial Unicode/DejaVu | Türkçe karakter desteği |

---

## Ana İş Akışları

### 1. Web UI ile Manuel İçerik Üretimi

```
Kampanya URL'si ekle → AI bilgi çıkarır → Görsel yükle/üret → Poster oluştur → Instagram'a paylaş
```

- Kullanıcı kampanya URL'sini girer
- Claude Sonnet 4.5 sayfayı analiz edip başlık, kategori ve indirim bilgisi çıkarır
- Kullanıcı görsel yükler veya AI ile üretir
- Poster/kolaj oluşturulur, metin pozisyonu ayarlanır
- Tek görsel veya carousel olarak Instagram'a paylaşılır

### 2. Otomatik Zamanlayıcı (GitHub Actions)

```
Cron tetikler (09:00, 11:20, 18:00 TR) → Kampanya seç → Sayfayı tara → Görsel bul/üret → Poster yap → Caption yaz → Instagram'a paylaş
```

- GitHub Actions hafta içi günde 3 kez tetiklenir
- Deterministik algoritma ile o slot için kampanya seçilir
- Sayfa scrape edilir, görseller ve bilgiler çekilir
- Görsel varsa poster, yoksa AI ile görsel üretilir
- Claude ile caption yazılır ve otomatik paylaşılır

### 3. AI Poster Üretimi (Gelişmiş)

```
Görselleri yükle → Kolaj oluştur → fal.ai'ye gönder → Flux img2img stilize et → Metin ve badge ekle → Paylaş
```

- Birden fazla görsel yüklenir
- Ham kolaj oluşturulur (metin olmadan)
- fal.ai'ye yüklenir, Claude stil prompt'u üretir
- Flux img2img ile stilize edilir
- Kampanya metni ve indirim badge'i eklenir

---

## Temel Modüller

### app.py - Flask Web Uygulaması

Ana dashboard ve tüm API endpoint'lerini barındırır.

**Endpoint'ler:**

| Route | Metod | Açıklama |
|-------|-------|----------|
| `/` | GET | Ana dashboard, kampanya listesi |
| `/add-campaign` | POST | URL ile kampanya ekleme (AI bilgi çıkarır) |
| `/scrape-campaign` | POST | Kampanya URL'sini yeniden tarıma |
| `/update-campaign` | POST | Kampanya başlık/kategori/indirim düzenleme |
| `/generate` | POST | AI ile içerik üretimi (görsel + caption) |
| `/generate-caption` | POST | Claude ile Instagram caption üretimi |
| `/create-posters` | POST | Yüklenen görsellerden poster oluşturma |
| `/adjust-poster` | POST | Poster üzerinde metin pozisyonu ayarlama |
| `/create-collage` | POST | Çoklu görsel kolaj düzeni oluşturma |
| `/upload-image` | POST | Tek görsel yükleme (fal.ai) |
| `/upload-images` | POST | Çoklu görsel yükleme (fal.ai) |
| `/post-instagram` | POST | Tek görsel Instagram paylaşımı |
| `/post-instagram-carousel` | POST | Carousel Instagram paylaşımı |
| `/download/<campaign_id>` | GET | Üretilen içeriği indirme |

**Temel Fonksiyonlar:**

- `scrape_campaign_page()` - BeautifulSoup ile web scraping
- `extract_campaign_info()` - Claude Sonnet 4.5 ile kampanya bilgisi çıkarma
- `generate_campaign_content()` - fal.ai workflow ile görsel + caption üretimi
- `generate_ai_poster()` - Kolaj → Flux stilizasyon → metin overlay

---

### poster.py - Poster Oluşturma Motoru

Pillow tabanlı poster oluşturma sistemi.

**Fonksiyonlar:**

- `create_poster()` - Tek görsel + metin overlay
  - Gradient arka plan overlay (alt kısım daha koyu)
  - Otomatik metin sarma ve gölge efekti
  - İndirim badge'i (kırmızı yuvarlak dikdörtgen)
  - Ayarlanabilir metin pozisyonu (%0-%90 dikey)

- `create_poster_from_multiple()` - Çoklu görsel düzeni
  - %62 görsel alanı, %38 bilgi alanı
  - 1, 2, 3, 4+ görsel için farklı layout'lar
  - Gradient geçiş ve aksanlı çizgi ayracı

- `create_raw_collage()` - Çoklu görsel grid (metin olmadan)
  - AI stilizasyon öncesi ham kolaj
  - Crop-to-fill mantığı (boş alan yok)

**Çıktı:** 1080x1350px (Instagram 4:5), JPEG kalite 95

---

### collage.py - Kolaj Düzen Motoru

Çoklu görsel düzenleme sistemi.

**Düzenler:**

- `create_full_bleed_grid()` - Eşit boyutlu grid, minimal boşluk (0-5px)
- `create_feature_layout()` - 1 büyük + küçük görseller
  - 2 görsel: 2/3 sol büyük, 1/3 sağ küçük
  - 3 görsel: %50/%50 bölünmüş
  - 4 görsel: Sol büyük, sağ 3 üst üste
  - 5+ görsel: Sol %55, sağ grid

---

### scheduler.py - Zamanlama Motoru

GitHub Actions ile otomatik içerik üretimi ve paylaşımı.

**Özellikler:**

- Türkiye saatine duyarlı zamanlama (UTC+3)
- Deterministik kampanya seçimi (her slot farklı kampanya)
- Cascading fallback: yerel dosya → GitHub Gist → environment variable
- Görsel tekilleştirme ve filtreleme
- Hafta içi 3 zaman dilimi: 09:00, 11:20, 18:00

---

### instagram.py - Instagram Entegrasyonu

Facebook Graph API v19.0 üzerinden Instagram paylaşımı.

**Fonksiyonlar:**

- `post_to_instagram()` - Tek görsel paylaşımı
  1. Media container oluştur (görsel URL + caption)
  2. İşlem bekle (10s)
  3. Yayınla

- `post_carousel_to_instagram()` - Carousel paylaşımı (2-10 görsel)
  1. Her görsel için child container oluştur
  2. Parent carousel container oluştur
  3. Yayınla

---

### index.html - Web Arayüzü

Modern, responsive tek sayfa uygulama.

- **Navigasyon:** Marka, durum göstergesi, tema değiştirici
- **Kampanya Yönetimi:** URL ile ekleme, dropdown seçici, düzenlenebilir alanlar
- **İki Ana Sekme:** Instagram Post Üretimi / Kampanya Görsel Üretimi
- **Alt Modlar:** Manuel yükleme, AI üretim, kolaj seçici, metin pozisyon slider
- **Yükleme:** Çoklu dosya drag-drop, görsel önizleme grid
- **Koyu Mod:** localStorage ile kalıcı tema tercihi

---

### style.css - Stil Sistemi

- CSS değişkenleri ile açık/koyu tema
- Bileşen kütüphanesi: butonlar, kartlar, inputlar, alertler, tablar
- Flexbox tabanlı düzen, 1080px max genişlik
- Animasyonlar: geçişler, yükleme spinner'ları, hover efektleri
- Inter fontu (Google Fonts)
- Mobile-first responsive tasarım

---

## Konfigürasyon

### Environment Variables (.env)

| Değişken | Açıklama |
|----------|----------|
| `FAL_KEY` | fal.ai API anahtarı |
| `INSTAGRAM_ACCESS_TOKEN` | 60 günlük Instagram token |
| `INSTAGRAM_ACCOUNT_ID` | Instagram business hesap ID |
| `CAMPAIGNS_GIST_URL` | (Opsiyonel) GitHub Gist URL'si |

### GitHub Actions Secrets

| Secret | Açıklama |
|--------|----------|
| `FAL_KEY` | fal.ai API anahtarı |
| `INSTAGRAM_ACCESS_TOKEN` | Instagram token |
| `INSTAGRAM_ACCOUNT_ID` | Instagram hesap ID |
| `CAMPAIGNS_GIST_URL` | (Opsiyonel) Gist URL |

### Zamanlama (schedule.yml)

- **Sıklık:** Hafta içi günde 3 kez
- **Saatler (TR):** 09:00, 11:20, 18:00
- **Platform:** Ubuntu-latest, Python 3.11
- **Fontlar:** DejaVu (Ubuntu sistem fontları)

---

## Veri Modelleri

### Kampanya Objesi

```json
{
  "id": 1,
  "url": "https://...",
  "title": "Kampanya Başlığı",
  "category": "Görsel üretimi için kategori açıklaması",
  "discount": "İndirim tutarı/yüzdesi"
}
```

### fal.ai Workflow Endpoint'leri

| Endpoint | Kullanım |
|----------|----------|
| `workflows/baharyavuz/grupanya-content-engine` | Ana içerik üretimi |
| `workflows/baharyavuz/grupanya-content-caption` | Sadece caption üretimi |
| `fal-ai/any-llm` | Claude Sonnet 4.5 metin üretimi |
| `fal-ai/flux/dev/image-to-image` | Görsel stilizasyonu |

---

## Mimari Öne Çıkanlar

- **Modüler yapı:** Scraping, AI, görüntü işleme, sosyal medya birbirinden bağımsız modüller
- **Cross-platform:** macOS (geliştirme) + Linux (GitHub Actions production)
- **Sıfır dokunuş otomasyonu:** Akıllı kampanya rotasyonu ile günlük paylaşım
- **Cascading fallback:** Kampanya verisi için 3 katmanlı yedekleme sistemi
- **Responsive UI:** Dark mode, drag-drop, gerçek zamanlı önizleme
- **Genişletilebilir:** Yeni layout, AI model veya sosyal platform kolayca eklenebilir

---

## Bağımlılıklar (requirements.txt)

```
flask>=3.0.0
requests>=2.31.0
Pillow>=10.0.0
beautifulsoup4>=4.12.0
python-dotenv>=1.0.0
```
