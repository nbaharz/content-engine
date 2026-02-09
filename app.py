import os
import json
from pathlib import Path
import requests
import fal_client
from flask import Flask, render_template, request, jsonify, send_file
import base64
from io import BytesIO
from dotenv import load_dotenv
from bs4 import BeautifulSoup

from instagram import post_to_instagram, post_carousel_to_instagram
from collage import create_collage
from poster import create_poster, create_poster_from_multiple, create_raw_collage

load_dotenv()

app = Flask(__name__)

# workflow endpoint
WORKFLOW_ENDPOINT = "workflows/baharyavuz/grupanya-content-engine"

CAMPAIGNS = [
    {"id": 1, "title": "Oley Manav İndirimi", "category": "fresh fruits and vegetables market", "discount": "150 TL"},
    {"id": 2, "title": "Kız Kulesi Kahvaltı Fırsatı", "category": "Istanbul Bosphorus breakfast", "discount": "%20"},
    {"id": 3, "title": "Sanda Spa Masaj Fırsatı", "category": "luxury spa massage", "discount": "%30"},
    {"id": 4, "title": "Meloni Tur Sevgililer Günü Özel Kapadokya Turu", "category": "romantic couple watching hot air balloons at sunrise in Cappadocia Turkey, fairy chimneys, golden hour, Valentine's Day atmosphere", "discount": "4.000 TL"},
    {
        "id": 5, 
        "title": "Dedeman Kartepe Kocaeli’de Yarım Pansiyon Konaklama", 
        "category": "winter resort, ski holiday, luxury stay", 
        "discount": "2.750 TL'den başlayan fiyatlarla"
    }
]

def scrape_campaign_page(url: str) -> str:
    """Kampanya sayfasını scrape edip metin içeriğini döndür"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Script ve style etiketlerini kaldır
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # Sayfa başlığı
    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    # Meta description
    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_desc = meta_tag["content"].strip()

    # Ana içerik metnini al
    body_text = soup.get_text(separator="\n", strip=True)

    # Çok uzun metni kısalt (LLM token limiti için)
    if len(body_text) > 4000:
        body_text = body_text[:4000]

    return f"Sayfa Başlığı: {title}\nMeta Açıklama: {meta_desc}\n\nSayfa İçeriği:\n{body_text}"


def extract_campaign_info(page_content: str) -> dict:
    """AI kullanarak sayfa içeriğinden kampanya bilgilerini çıkar"""
    system_prompt = """Sen bir kampanya analiz asistanısın. Sana verilen web sayfası içeriğinden kampanya bilgilerini çıkarmalısın.

Yanıtını SADECE aşağıdaki JSON formatında ver, başka hiçbir şey yazma:
{
    "title": "Kampanya başlığı (işletme adı + fırsat özeti, Türkçe)",
    "category": "Kampanyanın kategorisini İngilizce olarak yaz. Bu alan görsel oluşturmak için kullanılacak, o yüzden görselde ne olması gerektiğini detaylı anlat. Örnek: 'luxury spa massage therapy', 'fresh fruits and vegetables market', 'romantic dinner restaurant'",
    "discount": "İndirim miktarı veya fiyat bilgisi (örn: '%30', '150 TL', '2.750 TL'den başlayan fiyatlarla')"
}"""

    user_prompt = f"Aşağıdaki kampanya sayfasının içeriğini analiz et ve kampanya bilgilerini JSON olarak çıkar:\n\n{page_content}"

    result = fal_client.subscribe(
        "fal-ai/any-llm",
        arguments={
            "model": "anthropic/claude-sonnet-4.5",
            "prompt": user_prompt,
            "system_prompt": system_prompt,
        },
    )

    raw_output = result.get("output", "")

    # JSON'u parse et - ```json ... ``` bloğu varsa çıkar
    json_str = raw_output.strip()
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0].strip()
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0].strip()

    # { ile başlayıp } ile biten kısmı bul
    start = json_str.find("{")
    end = json_str.rfind("}") + 1
    if start != -1 and end > start:
        json_str = json_str[start:end]

    return json.loads(json_str)


def download_image_bytes(url: str) -> bytes:
    """Download image and return bytes"""
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content

def generate_campaign_content(campaign):
    """Generate campaign content using FAL workflow"""
    # Workflow input'ları
    image_prompt = (
        f"A real photograph taken with a DSLR camera of {campaign['category']}, "
        "natural lighting, shot on Canon EOS R5, 35mm lens, shallow depth of field, "
        "raw unedited photo, no illustration, no cartoon, no 3D render, no CGI, "
        "photojournalistic style, candid real moment"
    )
    system_prompt = "Sen Grupanya sosyal medya yöneticisisin. Türkçe, kısa, esprili ve satış odaklı yaz. 1 CTA ve 1-2 hashtag ekle."
    text_prompt = f"{campaign['title']} kampanyası: {campaign['discount']} indirim. Instagram post metni yaz."

    # Workflow çağrısı
    handler = fal_client.submit(
        WORKFLOW_ENDPOINT,
        arguments={
            "image_prompt": image_prompt,
            "text_prompt": text_prompt,
            "system_prompt": system_prompt,
        },
    )
    result = handler.get()

    # Response mapping
    images = result.get("images", [])
    post_text = result.get("output", "")

    if not images:
        raise RuntimeError(f"Workflow images boş döndü. result: {result}")

    # images[0] içinde genelde url olur
    image_url = images[0].get("url") or images[0].get("image_url")
    if not image_url:
        raise RuntimeError(f"Workflow image url bulunamadı. images: {images}")

    if not post_text:
        post_text = result.get("text") or str(result)

    # Görseli indir
    image_data = download_image_bytes(image_url)

    # Base64'e çevir (web'de göstermek için)
    image_base64 = base64.b64encode(image_data).decode('utf-8')

    return {
        "image_url": image_url,
        "image_base64": image_base64,
        "post_text": post_text,
        "image_data": image_data
    }

@app.route('/')
def index():
    """Ana sayfa"""
    return render_template('index.html', campaigns=CAMPAIGNS)

@app.route('/add-campaign', methods=['POST'])
def add_campaign():
    """URL'den kampanya bilgilerini AI ile çıkar ve listeye ekle"""
    try:
        url = request.json.get('url', '').strip()
        if not url:
            return jsonify({"error": "URL gerekli"}), 400

        # Sayfayı scrape et
        page_content = scrape_campaign_page(url)

        # AI ile kampanya bilgilerini çıkar
        info = extract_campaign_info(page_content)

        # Yeni kampanyayı listeye ekle
        new_id = max((c["id"] for c in CAMPAIGNS), default=0) + 1
        campaign = {
            "id": new_id,
            "title": info["title"],
            "category": info["category"],
            "discount": info["discount"],
        }
        CAMPAIGNS.append(campaign)

        return jsonify({
            "success": True,
            "campaign": campaign
        })

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Sayfa yüklenemedi: {str(e)}"}), 400
    except json.JSONDecodeError:
        return jsonify({"error": "AI yanıtı parse edilemedi, lütfen tekrar deneyin"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/update-campaign', methods=['POST'])
def update_campaign():
    """Kampanya bilgilerini güncelle"""
    try:
        data = request.json
        campaign_id = int(data.get('campaign_id'))
        campaign = next((c for c in CAMPAIGNS if c["id"] == campaign_id), None)

        if not campaign:
            return jsonify({"error": "Kampanya bulunamadı"}), 404

        campaign["title"] = data.get("title", campaign["title"])
        campaign["category"] = data.get("category", campaign["category"])
        campaign["discount"] = data.get("discount", campaign["discount"])

        return jsonify({"success": True, "campaign": campaign})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/generate', methods=['POST'])
def generate():
    """Kampanya içeriği oluştur"""
    try:
        # FAL_KEY kontrol
        if not os.getenv("FAL_KEY"):
            return jsonify({"error": "FAL_KEY environment variable bulunamadı"}), 400

        campaign_id = int(request.json.get('campaign_id'))
        poster_mode = request.json.get('poster_mode', False)
        campaign = next((c for c in CAMPAIGNS if c["id"] == campaign_id), None)

        if not campaign:
            return jsonify({"error": "Kampanya bulunamadı"}), 404

        # İçerik oluştur
        result = generate_campaign_content(campaign)

        image_base64 = result["image_base64"]

        # Poster modu: gorselin uzerine kampanya bilgilerini yaz
        if poster_mode:
            poster_bytes = create_poster(
                result["image_data"],
                campaign["title"],
                campaign["discount"],
            )
            image_base64 = base64.b64encode(poster_bytes).decode("utf-8")

        return jsonify({
            "success": True,
            "image_base64": image_base64,
            "post_text": result["post_text"],
            "image_url": result["image_url"]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

def generate_ai_poster(image_data_list, campaign):
    """
    AI ile stilize edilmis poster olustur.

    Akis:
    1. Pillow ile gorselleri collage'a birlestir
    2. fal.ai'a yukle
    3. Any LLM ile stil promptu uret
    4. Flux img2img ile stilize et
    5. Sonuc gorseli indir
    6. Pillow ile text overlay ekle (create_poster)

    Returns:
        dict: {poster_bytes, poster_url}
    """
    import tempfile

    # 1. Ham collage olustur (text overlay yok)
    collage_bytes = create_raw_collage(image_data_list)

    # 2. Collage'i fal.ai'a yukle
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
        tmp.write(collage_bytes)
        tmp_path = tmp.name
    collage_url = fal_client.upload_file(tmp_path)
    os.unlink(tmp_path)

    # 3. LLM ile stil promptu uret
    style_result = fal_client.subscribe(
        "fal-ai/any-llm",
        arguments={
            "model": "anthropic/claude-sonnet-4.5",
            "prompt": (
                f"Campaign: {campaign['title']}\n"
                f"Category: {campaign['category']}\n"
                f"Discount: {campaign['discount']}\n\n"
                "Generate a short English style prompt for Flux image-to-image model. "
                "The prompt should enhance this collage photo into a professional "
                "marketing poster aesthetic. Focus on lighting, color grading, "
                "and visual polish. Keep the original photos recognizable. "
                "Output ONLY the prompt, nothing else."
            ),
            "system_prompt": (
                "You are a visual style expert. Generate concise img2img style prompts "
                "that enhance photos with professional poster aesthetics. "
                "Output only the English prompt, no explanations."
            ),
        },
    )
    style_prompt = style_result.get("output", "").strip()

    # Fallback prompt
    if not style_prompt or len(style_prompt) < 10:
        style_prompt = (
            "Professional marketing poster, enhanced lighting, vibrant colors, "
            "commercial photography style, high contrast, polished look"
        )

    # 4. Flux img2img ile stilize et
    styled_result = fal_client.subscribe(
        "fal-ai/flux/dev/image-to-image",
        arguments={
            "image_url": collage_url,
            "prompt": style_prompt,
            "strength": 0.28,
            "num_inference_steps": 28,
            "guidance_scale": 3.5,
            "image_size": "square_hd",
        },
    )

    styled_images = styled_result.get("images", [])
    if not styled_images:
        raise RuntimeError(f"Flux img2img gorsel dondurmedi: {styled_result}")

    styled_url = styled_images[0].get("url")
    if not styled_url:
        raise RuntimeError(f"Styled image URL bulunamadi: {styled_images}")

    # 5. Stilize edilmis gorseli indir
    styled_bytes = download_image_bytes(styled_url)

    # 6. Text overlay ekle (mevcut create_poster fonksiyonu)
    poster_bytes = create_poster(
        styled_bytes,
        campaign["title"],
        campaign["discount"],
    )

    return {
        "poster_bytes": poster_bytes,
        "raw_bytes": styled_bytes,
        "style_prompt": style_prompt,
    }


@app.route('/create-posters', methods=['POST'])
def create_posters():
    """Birden fazla gorselden afis olustur (AI veya basic)"""
    import tempfile
    try:
        if 'files' not in request.files:
            return jsonify({"error": "Dosyalar bulunamadi"}), 400

        files = request.files.getlist('files')
        campaign_id = int(request.form.get('campaign_id', 0))
        ai_mode = request.form.get('ai_mode', 'false') == 'true'

        if not files:
            return jsonify({"error": "Dosya secilmedi"}), 400
        if len(files) > 4:
            return jsonify({"error": "En fazla 4 gorsel yuklenebilir"}), 400

        campaign = next((c for c in CAMPAIGNS if c["id"] == campaign_id), None)
        if not campaign:
            return jsonify({"error": "Kampanya bulunamadi"}), 404

        # Tum gorselleri oku
        image_data_list = []
        for file in files:
            if file.filename:
                image_data_list.append(file.read())

        if not image_data_list:
            return jsonify({"error": "Gecerli dosya bulunamadi"}), 400

        if ai_mode:
            # AI ile stilize edilmis poster
            result = generate_ai_poster(image_data_list, campaign)
            poster_bytes = result["poster_bytes"]
            # AI modunda raw = stilize edilmis gorsel (text overlay oncesi)
            # generate_ai_poster icinde styled_bytes'i da dondurelim
            raw_bytes = result.get("raw_bytes")
        else:
            # Basic modunda raw = ham collage
            raw_bytes = create_raw_collage(image_data_list)
            poster_bytes = create_poster_from_multiple(
                image_data_list,
                campaign["title"],
                campaign["discount"],
            )

        poster_base64 = base64.b64encode(poster_bytes).decode("utf-8")
        raw_base64 = base64.b64encode(raw_bytes).decode("utf-8") if raw_bytes else None

        # fal.ai'a yukle
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            tmp.write(poster_bytes)
            tmp_path = tmp.name
        poster_url = fal_client.upload_file(tmp_path)
        os.unlink(tmp_path)

        return jsonify({
            "success": True,
            "poster": {
                "image_base64": poster_base64,
                "image_url": poster_url,
            },
            "raw_image_base64": raw_base64,
            "mode": "ai" if ai_mode else "basic",
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/adjust-poster', methods=['POST'])
def adjust_poster():
    """Poster uzerindeki yazi konumunu ayarla ve yeniden render et"""
    import tempfile
    try:
        data = request.json
        raw_base64 = data.get('raw_image_base64')
        campaign_id = int(data.get('campaign_id', 0))
        title_y_percent = int(data.get('title_y_percent', 58))
        mode = data.get('mode', 'ai')

        if not raw_base64:
            return jsonify({"error": "raw_image_base64 gerekli"}), 400

        campaign = next((c for c in CAMPAIGNS if c["id"] == campaign_id), None)
        if not campaign:
            return jsonify({"error": "Kampanya bulunamadi"}), 404

        raw_bytes = base64.b64decode(raw_base64)

        # Kullanici tarafindan duzenlenmis baslik/indirim (opsiyonel)
        title = data.get('title') or campaign["title"]
        discount = data.get('discount') or campaign["discount"]

        if mode == 'ai':
            # AI modu: raw = stilize gorsel, uzerine text overlay
            poster_bytes = create_poster(
                raw_bytes,
                title,
                discount,
                title_y_percent=title_y_percent,
            )
        else:
            # Basic modu: raw = ham collage, poster_from_multiple ile render
            poster_bytes = create_poster_from_multiple(
                [raw_bytes],  # tek gorsel olarak ver (zaten collage)
                title,
                discount,
                title_y_percent=title_y_percent,
            )

        poster_base64 = base64.b64encode(poster_bytes).decode("utf-8")

        # fal.ai'a yukle
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            tmp.write(poster_bytes)
            tmp_path = tmp.name
        poster_url = fal_client.upload_file(tmp_path)
        os.unlink(tmp_path)

        return jsonify({
            "success": True,
            "poster": {
                "image_base64": poster_base64,
                "image_url": poster_url,
            },
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/download/<int:campaign_id>')
def download(campaign_id):
    """İçerikleri indir"""
    try:
        campaign = next((c for c in CAMPAIGNS if c["id"] == campaign_id), None)
        if not campaign:
            return "Kampanya bulunamadı", 404

        # Desktop klasörü + kampanya adı klasörü
        out_dir = Path.home() / "Desktop" / campaign["title"].replace(" ", "_")
        out_dir.mkdir(parents=True, exist_ok=True)

        # Son oluşturulan içeriği kaydet (session'da tutabilirsiniz, şimdilik yeniden oluşturuyoruz)
        result = generate_campaign_content(campaign)

        # Kaydet
        image_path = out_dir / "gorsel.jpg"
        image_path.write_bytes(result["image_data"])
        (out_dir / "metin.txt").write_text(result["post_text"], encoding="utf-8")

        return jsonify({
            "success": True,
            "folder_path": str(out_dir),
            "message": f"İçerikler Desktop/{campaign['title'].replace(' ', '_')} klasörüne kaydedildi"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/upload-image', methods=['POST'])
def upload_image():
    """Görseli fal.ai storage'a yükle ve public URL al"""
    import tempfile
    try:
        if 'file' not in request.files:
            return jsonify({"error": "Dosya bulunamadı"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Dosya seçilmedi"}), 400

        # Geçici dosyaya kaydet
        ext = os.path.splitext(file.filename)[1] or '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        # fal.ai'a yükle (dosya path'i ile)
        url = fal_client.upload_file(tmp_path)

        # Geçici dosyayı sil
        os.unlink(tmp_path)

        print(f"Uploaded image URL: {url}")  # Debug

        return jsonify({
            "success": True,
            "url": url
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/post-instagram', methods=['POST'])
def post_instagram():
    """Instagram'a paylaş"""
    try:
        data = request.json
        image_url = data.get('image_url')
        caption = data.get('caption')

        if not image_url or not caption:
            return jsonify({"error": "image_url ve caption gerekli"}), 400

        result = post_to_instagram(image_url, caption)

        if result['success']:
            return jsonify({
                "success": True,
                "post_id": result['post_id'],
                "message": "Instagram'a başarıyla paylaşıldı!"
            })
        else:
            return jsonify({"error": result['error']}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/upload-images', methods=['POST'])
def upload_images():
    """Çoklu görsel yükle ve fal.ai URL'lerini döndür"""
    import tempfile
    try:
        if 'files' not in request.files:
            return jsonify({"error": "Dosyalar bulunamadı"}), 400

        files = request.files.getlist('files')
        if not files or len(files) == 0:
            return jsonify({"error": "Dosya seçilmedi"}), 400

        if len(files) > 10:
            return jsonify({"error": "En fazla 10 görsel yüklenebilir"}), 400

        uploaded_urls = []

        for file in files:
            if file.filename == '':
                continue

            # Geçici dosyaya kaydet
            ext = os.path.splitext(file.filename)[1] or '.jpg'
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name

            # fal.ai'a yükle
            url = fal_client.upload_file(tmp_path)
            uploaded_urls.append(url)

            # Geçici dosyayı sil
            os.unlink(tmp_path)

        return jsonify({
            "success": True,
            "urls": uploaded_urls,
            "count": len(uploaded_urls)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/create-collage', methods=['POST'])
def create_collage_endpoint():
    """Görsellerden kolaj oluştur"""
    import tempfile
    try:
        image_data_list = []
        layout = "feature"  # default

        # Dosya upload'u
        if 'files' in request.files:
            files = request.files.getlist('files')
            for file in files:
                if file.filename:
                    image_data_list.append(file.read())
            layout = request.form.get('layout', 'feature')

        # URL'lerden indir
        elif request.json and 'image_urls' in request.json:
            for url in request.json['image_urls']:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                image_data_list.append(response.content)
            layout = request.json.get('layout', 'feature')

        if len(image_data_list) < 2:
            return jsonify({"error": "Kolaj için en az 2 görsel gerekli"}), 400

        # Kolaj oluştur
        collage_bytes = create_collage(image_data_list, layout=layout, gap=3)
        collage_base64 = base64.b64encode(collage_bytes).decode('utf-8')

        # fal.ai'a yükle
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            tmp.write(collage_bytes)
            tmp_path = tmp.name

        collage_url = fal_client.upload_file(tmp_path)
        os.unlink(tmp_path)

        return jsonify({
            "success": True,
            "image_base64": collage_base64,
            "image_url": collage_url
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/post-instagram-carousel', methods=['POST'])
def post_instagram_carousel():
    """Çoklu görseli Instagram carousel olarak paylaş"""
    try:
        data = request.json
        image_urls = data.get('image_urls', [])
        caption = data.get('caption', '')

        if not image_urls:
            return jsonify({"error": "image_urls gerekli"}), 400
        if len(image_urls) < 2:
            return jsonify({"error": "Carousel için en az 2 görsel gerekli"}), 400
        if len(image_urls) > 10:
            return jsonify({"error": "Carousel en fazla 10 görsel içerebilir"}), 400
        if not caption:
            return jsonify({"error": "caption gerekli"}), 400

        result = post_carousel_to_instagram(image_urls, caption)

        if result['success']:
            return jsonify({
                "success": True,
                "post_id": result['post_id'],
                "message": "Carousel Instagram'a başarıyla paylaşıldı!"
            })
        else:
            return jsonify({"error": result['error']}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)
