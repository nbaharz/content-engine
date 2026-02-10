from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import textwrap

# Font paths - macOS + Linux (GitHub Actions) destegi
import platform

if platform.system() == "Darwin":
    FONT_UNICODE = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
    FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    FONT_REGULAR = "/System/Library/Fonts/Supplemental/Arial.ttf"
    FONT_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
else:
    # Linux (Ubuntu/GitHub Actions) - DejaVu fontlari
    FONT_UNICODE = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    FONT_BLACK = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

SIZE = (1080, 1350)


def _load_font(path, size):
    """Font yukle, bulamazsa Turkce destekli fallback dene"""
    for font_path in [path, FONT_UNICODE, FONT_BOLD, FONT_REGULAR]:
        try:
            return ImageFont.truetype(font_path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _draw_gradient(draw, width, height):
    """Alt kismi karanliklastiran gradient overlay ciz"""
    # Ust %25 hafif karanlik (marka alani)
    for y in range(int(height * 0.25)):
        alpha = 60
        draw.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, alpha))

    # Orta kisim hafif
    for y in range(int(height * 0.25), int(height * 0.5)):
        alpha = 40
        draw.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, alpha))

    # Alt %50 giderek koyulasan gradient
    for y in range(int(height * 0.5), height):
        progress = (y - height * 0.5) / (height * 0.5)
        alpha = int(40 + progress * 180)
        draw.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, alpha))


def _draw_discount_badge(draw, text, center_x, center_y, font):
    """Indirim badge'i ciz"""
    bbox = font.getbbox(text)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    pad_x, pad_y = 40, 20
    badge_w = text_w + pad_x * 2
    badge_h = text_h + pad_y * 2

    x0 = center_x - badge_w // 2
    y0 = center_y - badge_h // 2

    draw.rounded_rectangle(
        [(x0, y0), (x0 + badge_w, y0 + badge_h)],
        radius=badge_h // 2,
        fill="#e11d48",
    )
    draw.text((center_x, center_y), text, fill="white", font=font, anchor="mm")


def _draw_text_with_shadow(draw, xy, text, font, fill="white", shadow_offset=3):
    """Golge efektli metin ciz"""
    x, y = xy
    # Golge
    draw.text((x + shadow_offset, y + shadow_offset), text, fill=(0, 0, 0, 150), font=font, anchor="mt")
    # Asil metin
    draw.text((x, y), text, fill=fill, font=font, anchor="mt")


def create_poster(image_bytes, title, discount, title_y_percent=58):
    """
    AI gorselinin uzerine kampanya bilgileri ekleyerek afis olustur.

    Args:
        image_bytes: Arka plan gorseli (bytes)
        title: Kampanya basligi
        discount: Indirim bilgisi
        title_y_percent: Baslik dikey konumu (0-90, yuzde olarak). Default 58.

    Returns:
        bytes: JPEG poster gorseli
    """
    width, height = SIZE

    # Arka plan gorselini ac ve boyutlandir
    bg = Image.open(BytesIO(image_bytes)).convert("RGBA")
    bg = bg.resize(SIZE, Image.LANCZOS)

    # Gradient overlay
    overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    _draw_gradient(draw_overlay, width, height)
    bg = Image.alpha_composite(bg, overlay)

    # RGB'ye cevir ve cizim baslat
    poster = bg.convert("RGB")
    draw = ImageDraw.Draw(poster)

    # Fontlar - Türkçe karakter desteği için FONT_UNICODE öncelikli
    font_title = _load_font(FONT_UNICODE, 58)
    font_discount = _load_font(FONT_UNICODE, 52)

    # === KAMPANYA BASLIGI (alt bolge) ===
    if len(title) > 40:
        font_title = _load_font(FONT_UNICODE, 46)
        wrap_width = 24
    elif len(title) > 25:
        font_title = _load_font(FONT_UNICODE, 52)
        wrap_width = 20
    else:
        wrap_width = 18

    wrapped_lines = textwrap.wrap(title, width=wrap_width)

    # Baslik konumu - ayarlanabilir
    title_y_percent = max(10, min(90, title_y_percent))
    title_start_y = height * (title_y_percent / 100.0)
    line_spacing = 70 if len(title) <= 40 else 58

    for line in wrapped_lines:
        _draw_text_with_shadow(draw, (width // 2, title_start_y), line, font_title)
        title_start_y += line_spacing

    # === INDIRIM BADGE (basligin altinda) ===
    badge_y = title_start_y + 40
    _draw_discount_badge(draw, discount, width // 2, int(badge_y), font_discount)

    # Kaydet
    output = BytesIO()
    poster.save(output, format="JPEG", quality=95)
    return output.getvalue()


def _crop_to_fill(img, target_width, target_height):
    """Gorseli hedef boyuta gore ortadan kirp (bosluk kalmaz)"""
    img_ratio = img.width / img.height
    target_ratio = target_width / target_height

    if img_ratio > target_ratio:
        new_height = target_height
        new_width = int(img.width * (target_height / img.height))
    else:
        new_width = target_width
        new_height = int(img.height * (target_width / img.width))

    img = img.resize((new_width, new_height), Image.LANCZOS)

    left = (new_width - target_width) // 2
    top = (new_height - target_height) // 2
    return img.crop((left, top, left + target_width, top + target_height))


def create_raw_collage(image_bytes_list):
    """
    Birden fazla gorseli tek bir 1080x1350 collage'a birlestir.
    Text overlay YOK - AI stilizasyonu oncesi ham gorsel.

    Args:
        image_bytes_list: Gorsel bytes listesi (1-4 adet)

    Returns:
        bytes: JPEG collage gorseli
    """
    width, height = SIZE
    gap = 4

    images = []
    for img_bytes in image_bytes_list:
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        images.append(img)

    n = len(images)
    canvas = Image.new("RGB", SIZE, (0, 0, 0))

    if n == 1:
        cropped = _crop_to_fill(images[0], width, height)
        canvas.paste(cropped, (0, 0))

    elif n == 2:
        cell_w = (width - gap) // 2
        for i, img in enumerate(images[:2]):
            cropped = _crop_to_fill(img, cell_w, height)
            x = i * (cell_w + gap)
            canvas.paste(cropped, (x, 0))

    elif n == 3:
        # 1 buyuk ust (%58) + 2 kucuk alt
        top_h = int(height * 0.58)
        bottom_h = height - top_h - gap

        cropped_top = _crop_to_fill(images[0], width, top_h)
        canvas.paste(cropped_top, (0, 0))

        cell_w = (width - gap) // 2
        for i, img in enumerate(images[1:3]):
            cropped = _crop_to_fill(img, cell_w, bottom_h)
            x = i * (cell_w + gap)
            canvas.paste(cropped, (x, top_h + gap))

    else:
        # 4 gorsel: 2x2 grid
        cols, rows = 2, 2
        cell_w = (width - gap) // cols
        cell_h = (height - gap) // rows

        for idx, img in enumerate(images[:4]):
            row = idx // cols
            col = idx % cols
            cropped = _crop_to_fill(img, cell_w, cell_h)
            x = col * (cell_w + gap)
            y = row * (cell_h + gap)
            canvas.paste(cropped, (x, y))

    output = BytesIO()
    canvas.save(output, format="JPEG", quality=95)
    return output.getvalue()


def create_poster_from_multiple(image_bytes_list, title, discount, title_y_percent=None):
    """
    Birden fazla gorseli tek bir poster icinde birlestir.

    Args:
        image_bytes_list: Gorsel bytes listesi
        title: Kampanya basligi
        discount: Indirim bilgisi
        title_y_percent: Yazi dikey konumu (0-90). None ise otomatik ortala.

    Returns:
        bytes: JPEG poster gorseli
    """
    width, height = SIZE
    gap = 4

    # Gorselleri ac
    images = []
    for img_bytes in image_bytes_list:
        img = Image.open(BytesIO(img_bytes)).convert("RGB")
        images.append(img)

    n = len(images)

    # Gorsel alani: ust %62, kampanya bilgisi alt %38
    image_zone_h = int(height * 0.62)
    info_zone_h = height - image_zone_h

    # Canvas
    canvas = Image.new("RGBA", SIZE, (0, 0, 0, 255))

    if n == 1:
        # Tek gorsel - tam kapla
        cropped = _crop_to_fill(images[0], width, image_zone_h)
        canvas.paste(cropped, (0, 0))

    elif n == 2:
        # Yan yana 2 gorsel
        cell_w = (width - gap) // 2
        for i, img in enumerate(images[:2]):
            cropped = _crop_to_fill(img, cell_w, image_zone_h)
            x = i * (cell_w + gap)
            canvas.paste(cropped, (x, 0))

    elif n == 3:
        # Ust: 1 buyuk gorsel (tam genislik, %55 yukseklik)
        # Orta: 2 kucuk gorsel yan yana
        top_h = int(image_zone_h * 0.58)
        bottom_h = image_zone_h - top_h - gap

        # Ust buyuk gorsel
        cropped_top = _crop_to_fill(images[0], width, top_h)
        canvas.paste(cropped_top, (0, 0))

        # Alt 2 gorsel
        cell_w = (width - gap) // 2
        for i, img in enumerate(images[1:3]):
            cropped = _crop_to_fill(img, cell_w, bottom_h)
            x = i * (cell_w + gap)
            canvas.paste(cropped, (x, top_h + gap))

    else:
        # 4+ gorsel: 2x2 grid
        cols, rows = 2, 2
        cell_w = (width - gap) // cols
        cell_h = (image_zone_h - gap) // rows

        for idx, img in enumerate(images[:4]):
            row = idx // cols
            col = idx % cols
            cropped = _crop_to_fill(img, cell_w, cell_h)
            x = col * (cell_w + gap)
            y = row * (cell_h + gap)
            canvas.paste(cropped, (x, y))

    # Alt bilgi alanina koyu arka plan + hafif gradient gecisi
    overlay = Image.new("RGBA", SIZE, (0, 0, 0, 0))
    draw_ov = ImageDraw.Draw(overlay)

    # Gorsel bolgesinin alt kismindan baslayan yumusak gecis
    fade_start = image_zone_h - 80
    for y in range(fade_start, image_zone_h):
        progress = (y - fade_start) / 80
        alpha = int(progress * 230)
        draw_ov.rectangle([(0, y), (width, y + 1)], fill=(0, 0, 0, alpha))

    # Bilgi alani - koyu gradient arka plan
    for y in range(image_zone_h, height):
        progress = (y - image_zone_h) / info_zone_h
        r = int(15 + progress * 5)
        g = int(15 + progress * 5)
        b = int(30 + progress * 10)
        draw_ov.rectangle([(0, y), (width, y + 1)], fill=(r, g, b, 245))

    canvas = Image.alpha_composite(canvas, overlay)

    # RGB'ye cevir ve cizim
    poster = canvas.convert("RGB")
    draw = ImageDraw.Draw(poster)

    # Accent cizgi (gorsel ile bilgi arasi ince renkli serit)
    accent_color = "#e11d48"
    draw.rectangle(
        [(width // 4, image_zone_h + 2), (3 * width // 4, image_zone_h + 5)],
        fill=accent_color,
    )

    # Fontlar
    font_title = _load_font(FONT_UNICODE, 54)
    font_discount = _load_font(FONT_UNICODE, 46)

    # === KAMPANYA BASLIGI ===
    if len(title) > 40:
        font_title = _load_font(FONT_UNICODE, 42)
        wrap_width = 26
    elif len(title) > 25:
        font_title = _load_font(FONT_UNICODE, 48)
        wrap_width = 22
    else:
        wrap_width = 18

    wrapped_lines = textwrap.wrap(title, width=wrap_width)

    # Tum icerik yuksekligini hesapla ve dikey ortala
    line_spacing = 64 if len(title) <= 40 else 52
    title_block_h = len(wrapped_lines) * line_spacing
    badge_h = 70
    spacing_title_badge = 45
    total_content_h = title_block_h + spacing_title_badge + badge_h

    if title_y_percent is not None:
        content_start_y = int(height * (max(10, min(90, title_y_percent)) / 100.0))
    else:
        content_start_y = image_zone_h + (info_zone_h - total_content_h) // 2 + 10

    title_y = content_start_y
    for line in wrapped_lines:
        _draw_text_with_shadow(draw, (width // 2, title_y), line, font_title)
        title_y += line_spacing

    # === INDIRIM BADGE ===
    badge_y = title_y + spacing_title_badge
    _draw_discount_badge(draw, discount, width // 2, int(badge_y), font_discount)

    # Kaydet
    output = BytesIO()
    poster.save(output, format="JPEG", quality=95)
    return output.getvalue()
