import json
import requests
import fal_client
from bs4 import BeautifulSoup


def scrape_campaign_page(url: str) -> str:
    """Scrape campaign page and return text content."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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

    return f"Sayfa Başlığı: {title}\nMeta Açıklama: {meta_desc}\n\nSayfa İçeriği:\n{body_text}"


def extract_campaign_info(page_content: str) -> dict:
    """Extract campaign info from page content using AI."""
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
            "model": "openai/gpt-4o-mini",
            "prompt": user_prompt,
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
