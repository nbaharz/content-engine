import os
from pathlib import Path
import requests
import fal_client
from dotenv import load_dotenv

from instagram import post_to_instagram

load_dotenv()  # .env dosyasından değişkenleri yükle

# workflow endpoint
WORKFLOW_ENDPOINT = "workflows/baharyavuz/grupanya-content-engine"

CAMPAIGNS = [
    {"id": 1, "title": "Oley Manav İndirimi", "category": "fresh fruits and vegetables market", "discount": "150 TL"},
    {"id": 2, "title": "Kız Kulesi Kahvaltı Fırsatı", "category": "Istanbul Bosphorus breakfast", "discount": "%20"},
    {"id": 3, "title": "Sanda Spa Masaj Fırsatı", "category": "luxury spa massage", "discount": "%30"},
    {"id": 4, "title": "Meloni Tur Sevgililer Günü Özel Kapadokya Turu", "category": "romantic couple watching hot air balloons at sunrise in Cappadocia Turkey, fairy chimneys, golden hour, Valentine's Day atmosphere", "discount": "4.000 TL"},

]

def pick_campaign():
    print("\nHangi kampanya?")
    for c in CAMPAIGNS:
        print(f"{c['id']}) {c['title']}")
    cid = int(input("ID gir: ").strip())
    return next(c for c in CAMPAIGNS if c["id"] == cid)

def download_image(url: str, save_path: Path):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    save_path.write_bytes(r.content)

def main():
    # FAL_KEY kontrol
    if not os.getenv("FAL_KEY"):
        raise RuntimeError("FAL_KEY yok. Terminalde export FAL_KEY='...' yapmalısın.")

    campaign = pick_campaign()

    # Desktop klasörü + kampanya adı klasörü
    out_dir = Path.home() / "Desktop" / campaign["title"].replace(" ", "_")
    out_dir.mkdir(parents=True, exist_ok=True)

    # Workflow input'ları (senin workflow input adların: image_prompt, text_prompt, system_prompt)
    image_prompt = (
        f"Professional advertising photo of {campaign['category']}, "
        "studio lighting, cinematic, 8k, hyper-realistic"
    )
    system_prompt = "Sen Grupanya sosyal medya yöneticisisin. Türkçe, kısa, esprili ve satış odaklı yaz. 1 CTA ve 1-2 hashtag ekle."
    text_prompt = f"{campaign['title']} kampanyası: {campaign['discount']} indirim. Instagram post metni yaz."

    print("\nAI çalışıyor, lütfen bekleyin... ☕")

    # ✅ TEK ÇAĞRI: Workflow
    handler = fal_client.submit(
        WORKFLOW_ENDPOINT,
        arguments={
            "image_prompt": image_prompt,
            "text_prompt": text_prompt,
            "system_prompt": system_prompt,
        },
    )
    result = handler.get()

    # ✅ Response mapping (Response panelinde: images ve output)
    images = result.get("images", [])
    post_text = result.get("output", "")

    if not images:
        raise RuntimeError(f"Workflow images boş döndü. result: {result}")

    # images[0] içinde genelde url olur
    image_url = images[0].get("url") or images[0].get("image_url")
    if not image_url:
        raise RuntimeError(f"Workflow image url bulunamadı. images: {images}")

    if not post_text:
        # bazen 'text' diye gelebilir
        post_text = result.get("text") or str(result)

    # Kaydet
    download_image(image_url, out_dir / "gorsel.jpg")
    (out_dir / "metin.txt").write_text(post_text, encoding="utf-8")

    print("\n✅ İçerik oluşturuldu!")
    print("Klasör:", out_dir)
    print("Görsel URL:", image_url)
    print("\nCaption:")
    print(post_text)

    # Instagram'a paylaş
    share = input("\nInstagram'a paylaşmak ister misin? (e/h): ").strip().lower()
    if share == 'e':
        result = post_to_instagram(image_url, post_text)
        if result['success']:
            print(f"\n Instagram'a paylaşıldı! Post ID: {result['post_id']}")
        else:
            print(f"\n Hata: {result['error']}")
    else:
        print("\nPaylaşım iptal edildi. İçerik klasörde kayıtlı.")

if __name__ == "__main__":
    main()

