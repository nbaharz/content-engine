import os
import tempfile
import base64
import requests
import fal_client

from services.campaigns import DEFAULT_NEGATIVE_PROMPT

WORKFLOW_ENDPOINT = "workflows/baharyavuz/grupanya-content-engine"
CAPTION_WORKFLOW_ENDPOINT = "workflows/baharyavuz/grupanya-content-caption"


def download_image_bytes(url: str) -> bytes:
    """Download image and return bytes."""
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content


def generate_instagram_content(campaign):
    """Generate image and caption for Instagram post with AI."""
    negative = campaign.get("negative_prompt", DEFAULT_NEGATIVE_PROMPT)
    image_prompt = (
        f"A real photograph taken with a DSLR camera of {campaign['category']}, "
        "natural lighting, shot on Canon EOS R5, 35mm lens, shallow depth of field, "
        f"raw unedited photo, photojournalistic style, candid real moment, {negative}"
    )
    system_prompt = "Sen Grupanya sosyal medya yöneticisisin. Türkçe, kısa, esprili ve satış odaklı yaz. 1 CTA ve 1-2 hashtag ekle."
    text_prompt = f"{campaign['title']} kampanyası: {campaign['discount']} indirim. Instagram post metni yaz."

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
        raise RuntimeError(f"Workflow returned empty images. result: {result}")

    image_url = images[0].get("url") or images[0].get("image_url")
    if not image_url:
        raise RuntimeError(f"Workflow image URL not found. images: {images}")

    if not post_text:
        post_text = result.get("text") or str(result)

    image_data = download_image_bytes(image_url)
    image_base64 = base64.b64encode(image_data).decode('utf-8')

    return {
        "image_url": image_url,
        "image_base64": image_base64,
        "post_text": post_text,
        "image_data": image_data
    }


def generate_caption(campaign):
    """Generate campaign caption with AI (grupanya-content-caption workflow)."""
    system_prompt = (
        "Sen Grupanya sosyal medya yoneticisisin. Turkce, kisa, esprili "
        "ve satis odakli yaz. 1 CTA ve 1-2 hashtag ekle."
    )
    text_prompt = (
        f"{campaign['title']} kampanyasi: {campaign['discount']} indirim. "
        "Instagram post metni yaz."
    )

    handler = fal_client.submit(
        CAPTION_WORKFLOW_ENDPOINT,
        arguments={
            "text_prompt": text_prompt,
            "system_prompt": system_prompt,
        },
    )
    result = handler.get()

    caption = result.get("output", "") or result.get("text", "")
    if not caption:
        raise RuntimeError("Workflow returned no caption")

    return caption


def generate_website_content(campaign, reference_images=None, num_images=1):
    """
    Generate campaign images for website.
    Args:
        campaign: dict (title, category, discount)
        reference_images: [bytes] or None
        num_images: int (1-4)
    Returns:
        List[dict]: Each containing { 'image_url', 'image_base64', 'image_data' }
    """
    results = []
    negative = campaign.get("negative_prompt", DEFAULT_NEGATIVE_PROMPT)
    image_prompt = (
        f"A real photograph taken with a DSLR camera of {campaign['category']}, "
        "natural lighting, shot on Canon EOS R5, 35mm lens, shallow depth of field, "
        f"raw unedited photo, photojournalistic style, candid real moment, {negative}"
    )
    for i in range(num_images):
        if reference_images and len(reference_images) > i:
            ref_bytes = reference_images[i]
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
                tmp.write(ref_bytes)
                tmp_path = tmp.name
            ref_url = fal_client.upload_file(tmp_path)
            os.unlink(tmp_path)

            style_result = fal_client.subscribe(
                "fal-ai/any-llm",
                arguments={
                    "model": "openai/gpt-4o-mini",
                    "prompt": (
                        f"Campaign: {campaign['title']}\n"
                        f"Category: {campaign['category']}\n"
                        f"Discount: {campaign['discount']}\n\n"
                        "Generate a short English style prompt for Flux image-to-image model. "
                        "The prompt should enhance this photo into a professional "
                        "marketing poster aesthetic. Focus on lighting, color grading, "
                        "and visual polish. Keep the original photo recognizable. "
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
            if not style_prompt or len(style_prompt) < 10:
                style_prompt = (
                    "Professional marketing poster, enhanced lighting, vibrant colors, "
                    "commercial photography style, high contrast, polished look"
                )

            combined_prompt = (
                f"A real photograph taken with a DSLR camera of {campaign['category']}, "
                "natural lighting, shot on Canon EOS R5, 35mm lens, shallow depth of field, "
                "raw unedited photo, photojournalistic style, candid real moment. "
                f"About: {campaign['title']}, discount: {campaign['discount']}. "
                f"{style_prompt}, {negative}"
            )

            styled_result = fal_client.subscribe(
                "fal-ai/flux/dev/image-to-image",
                arguments={
                    "image_url": ref_url,
                    "prompt": combined_prompt,
                    "strength": 0.28,
                    "num_inference_steps": 28,
                    "guidance_scale": 3.5,
                    "image_size": {"width": 1080, "height": 1350},
                },
            )
            styled_images = styled_result.get("images", [])
            if not styled_images:
                raise RuntimeError(f"Flux img2img returned no image: {styled_result}")
            styled_url = styled_images[0].get("url")
            if not styled_url:
                raise RuntimeError(f"Styled image URL not found: {styled_images}")
            image_url = styled_url
        else:
            text_prompt = (
                f"{campaign.get('title', 'Kampanya')} icin {campaign.get('discount', 'firsat')} "
                "vurgulu kisa bir Instagram aciklamasi yaz."
            )
            system_prompt = (
                "Sen Grupanya sosyal medya yoneticisisin. Turkce, kisa ve satis odakli yaz."
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
            if not images:
                raise RuntimeError(f"Workflow returned empty images. result: {result}")
            image_url = images[0].get("url") or images[0].get("image_url")
            if not image_url:
                raise RuntimeError(f"Workflow image URL not found. images: {images}")

        image_data = download_image_bytes(image_url)
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        results.append({
            "image_url": image_url,
            "image_base64": image_base64,
            "image_data": image_data
        })
    return results
