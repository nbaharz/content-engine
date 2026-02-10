"""
Grupanya Content Engine - Zamanlanmis Otomasyon
GitHub Actions tarafindan hafta ici gunde 3 kere calistirilir.

Akis:
1. campaigns.json'dan URL listesini oku
2. Gundeki sirayla bir URL sec (gunde 3 farkli kampanya)
3. Sayfayi scrape et, AI ile kampanya bilgilerini cikar
4. Sayfadaki ilk 3 gorseli al
5. Gorseller varsa -> poster (afis) modu: collage + text overlay
   Gorseller yoksa -> fal.ai workflow ile gorsel uret
6. Instagram'a paylas
"""

import os
import json
import sys
import tempfile
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import requests
import fal_client
from bs4 import BeautifulSoup

from instagram import post_to_instagram
from poster import create_poster, create_poster_from_multiple

# fal.ai workflow endpoint
WORKFLOW_ENDPOINT = "workflows/baharyavuz/grupanya-content-engine"

# Turkiye saat dilimi (UTC+3)
TZ_TR = timezone(timedelta(hours=3))

# Calisma saatleri (TR) - (saat, dakika) formatinda
SCHEDULE_HOURS = [(9, 0), (11, 20), (18, 0)]


def load_campaign_urls():
    """Kampanya URL'lerini yukle. Oncelik: lokal dosya > Gist > env var."""
    # 1) Lokal dosya (gelistirme ortami)
    campaigns_path = os.path.join(os.path.dirname(__file__), "campaigns.json")
    if os.path.exists(campaigns_path):
        with open(campaigns_path, "r", encoding="utf-8") as f:
            return json.load(f)
    # 2) Private GitHub Gist (production - dinamik guncelleme)
    gist_url = os.environ.get("CAMPAIGNS_GIST_URL")
    if gist_url:
        resp = requests.get(gist_url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    # 3) Env var fallback
    campaigns_env = os.environ.get("CAMPAIGNS_JSON")
    if campaigns_env:
        return json.loads(campaigns_env)
    raise FileNotFoundError(
        "campaigns.json bulunamadi, CAMPAIGNS_GIST_URL ve CAMPAIGNS_JSON env var tanimli degil."
    )


def pick_url(urls):
    """
    Gundeki sirayla bir URL sec.
    Gunde 3 calisma: her biri farkli bir URL secer.
    """
    now = datetime.now(TZ_TR)
    day_of_year = now.timetuple().tm_yday

    # Simdi kacinci dakikadayiz (gun icinde)
    now_minutes = now.hour * 60 + now.minute
    slot = 0
    best_diff = float("inf")
    for i, (h, m) in enumerate(SCHEDULE_HOURS):
        diff = abs(now_minutes - (h * 60 + m))
        if diff < best_diff:
            best_diff = diff
            slot = i

    index = (day_of_year * 3 + slot) % len(urls)
    return urls[index], index


def scrape_campaign_page(url):
    """Kampanya sayfasini scrape edip metin icerigini dondur."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_desc = meta_tag["content"].strip()

    body_text = soup.get_text(separator="\n", strip=True)
    if len(body_text) > 4000:
        body_text = body_text[:4000]

    return f"Sayfa Basligi: {title}\nMeta Aciklama: {meta_desc}\n\nSayfa Icerigi:\n{body_text}"


def scrape_campaign_images(url, max_images=3):
    """
    Kampanya sayfasindan gorsel URL'lerini cikar.
    Grupanya gorselleri grpstat.com/DealImages/ altinda bulunur.
    Buyuk boyutlu gorselleri (766-511) tercih eder.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    image_urls = []
    seen = set()

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src:
            continue

        # Tam URL'ye cevir
        src = urljoin(url, src)

        # Grupanya kampanya gorselleri: grpstat.com/DealImages/
        if "DealImages" not in src and "dealimages" not in src.lower():
            continue

        # Kucuk thumbnailleri atla (127-85 gibi)
        if re.search(r'_\d{2,3}-\d{2,3}\.', src):
            if "_127-85" in src or "_85-85" in src:
                continue

        # Ayni gorselin farkli boyutlarini engelle
        # Base key: boyut bilgisi olmadan
        base_key = re.sub(r'_?\d{3,4}-\d{3,4}', '', src)
        if base_key in seen:
            continue
        seen.add(base_key)

        image_urls.append(src)

        if len(image_urls) >= max_images:
            break

    return image_urls


def download_image(url):
    """Gorsel indir, bytes dondur."""
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.content


def upload_to_fal(image_bytes):
    """Gorsel bytes'ini fal.ai'a yukle, public URL dondur."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name
    url = fal_client.upload_file(tmp_path)
    os.unlink(tmp_path)
    return url


def extract_campaign_info(page_content):
    """AI kullanarak sayfa iceriginden kampanya bilgilerini cikar."""
    system_prompt = """Sen bir kampanya analiz asistanisin. Sana verilen web sayfasi iceriginden kampanya bilgilerini cikarmalsin.

Yanitini SADECE asagidaki JSON formatinda ver, baska hicbir sey yazma:
{
    "title": "Kampanya basligi (isletme adi + firsat ozeti, Turkce)",
    "category": "Kampanyanin kategorisini Ingilizce olarak yaz. Bu alan gorsel olusturmak icin kullanilacak, o yuzden gorselde ne olmasi gerektigini detayli anlat. Ornek: 'luxury spa massage therapy', 'fresh fruits and vegetables market'",
    "discount": "Indirim miktari veya fiyat bilgisi (orn: '%30', '150 TL', '2.750 TL'den baslayan fiyatlarla')"
}"""

    result = fal_client.subscribe(
        "fal-ai/any-llm",
        arguments={
            "model": "anthropic/claude-sonnet-4.5",
            "prompt": f"Asagidaki kampanya sayfasinin icerigini analiz et ve kampanya bilgilerini JSON olarak cikar:\n\n{page_content}",
            "system_prompt": system_prompt,
        },
    )

    raw_output = result.get("output", "")

    json_str = raw_output.strip()
    if "```json" in json_str:
        json_str = json_str.split("```json")[1].split("```")[0].strip()
    elif "```" in json_str:
        json_str = json_str.split("```")[1].split("```")[0].strip()

    start = json_str.find("{")
    end = json_str.rfind("}") + 1
    if start != -1 and end > start:
        json_str = json_str[start:end]

    return json.loads(json_str)


def generate_content_ai(campaign):
    """fal.ai workflow ile sifirdan gorsel + metin uret (fallback)."""
    image_prompt = (
        f"A real photograph taken with a DSLR camera of {campaign['category']}, "
        "natural lighting, shot on Canon EOS R5, 35mm lens, shallow depth of field, "
        "raw unedited photo, no illustration, no cartoon, no 3D render, no CGI, "
        "photojournalistic style, candid real moment"
    )
    system_prompt = (
        "Sen Grupanya sosyal medya yoneticisisin. "
        "Turkce, kisa, esprili ve satis odakli yaz. 1 CTA ve 1-2 hashtag ekle."
    )
    text_prompt = (
        f"{campaign['title']} kampanyasi: {campaign['discount']} indirim. "
        "Instagram post metni yaz."
    )

    handler = fal_client.submit(
        WORKFLOW_ENDPOINT,
        arguments={
            "image_prompt": image_prompt,
            "text_prompt": text_prompt,
            "system_prompt": system_prompt,
        },
    )
    result = handler.get()

    images = result.get("images", [])
    post_text = result.get("output", "")

    if not images:
        raise RuntimeError(f"Workflow gorsel dondurmedi: {result}")

    image_url = images[0].get("url") or images[0].get("image_url")
    if not image_url:
        raise RuntimeError(f"Image URL bulunamadi: {images}")

    if not post_text:
        post_text = result.get("text", "")

    return {"image_url": image_url, "post_text": post_text}


def generate_post_text(campaign):
    """AI ile sadece Instagram post metni uret."""
    result = fal_client.subscribe(
        "fal-ai/any-llm",
        arguments={
            "model": "anthropic/claude-sonnet-4.5",
            "prompt": (
                f"{campaign['title']} kampanyasi: {campaign['discount']} indirim. "
                "Instagram post metni yaz."
            ),
            "system_prompt": (
                "Sen Grupanya sosyal medya yoneticisisin. "
                "Turkce, kisa, esprili ve satis odakli yaz. 1 CTA ve 1-2 hashtag ekle."
            ),
        },
    )
    return result.get("output", "")


def run():
    """Ana otomasyon akisi."""
    # Gerekli env var kontrolu
    missing = []
    for var in ["FAL_KEY", "INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_ACCOUNT_ID"]:
        if not os.getenv(var):
            missing.append(var)
    if missing:
        print(f"HATA: Eksik environment variable'lar: {', '.join(missing)}")
        sys.exit(1)

    # URL listesini yukle
    urls = load_campaign_urls()
    if not urls:
        print("HATA: campaigns.json bos veya bulunamadi.")
        sys.exit(1)

    # URL sec
    url, index = pick_url(urls)
    now = datetime.now(TZ_TR).strftime("%Y-%m-%d %H:%M")
    print(f"[{now}] Secilen URL ({index + 1}/{len(urls)}): {url}")

    # Sayfayi scrape et
    print("Sayfa scrape ediliyor...")
    page_content = scrape_campaign_page(url)

    # AI ile kampanya bilgilerini cikar
    print("Kampanya bilgileri cikariliyor...")
    campaign = extract_campaign_info(page_content)
    print(f"Kampanya: {campaign['title']} | {campaign['discount']}")

    # Sayfadaki gorselleri kontrol et
    print("Kampanya gorselleri araniyor...")
    image_urls = scrape_campaign_images(url)

    if image_urls:
        # AFIS MODU: Sayfadaki gorselleri kullanarak poster olustur
        print(f"{len(image_urls)} gorsel bulundu, afis modu...")

        image_data_list = []
        for img_url in image_urls:
            print(f"  Indiriliyor: {img_url[:80]}...")
            image_data_list.append(download_image(img_url))

        # Poster olustur
        if len(image_data_list) == 1:
            poster_bytes = create_poster(
                image_data_list[0],
                campaign["title"],
                campaign["discount"],
            )
        else:
            poster_bytes = create_poster_from_multiple(
                image_data_list,
                campaign["title"],
                campaign["discount"],
            )

        # fal.ai'a yukle (Instagram public URL istiyor)
        print("Poster yukleniyor...")
        image_url = upload_to_fal(poster_bytes)

        # Post metni uret
        print("Post metni uretiliyor...")
        post_text = generate_post_text(campaign)
    else:
        # FALLBACK: AI ile sifirdan gorsel uret
        print("Sayfada gorsel bulunamadi, AI ile uretiliyor...")
        content = generate_content_ai(campaign)
        image_url = content["image_url"]
        post_text = content["post_text"]

    print(f"Gorsel URL: {image_url}")
    print(f"Post metni: {post_text[:100]}...")

    # Instagram'a paylas
    print("Instagram'a paylasiliyor...")
    result = post_to_instagram(image_url, post_text)

    if result["success"]:
        print(f"Basariyla paylasildi! Post ID: {result['post_id']}")
    else:
        print(f"HATA: Instagram paylasim basarisiz: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    run()
