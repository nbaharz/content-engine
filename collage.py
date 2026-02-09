"""
Kolaj oluşturma modülü.
Farklı layout stilleri ile estetik kolajlar oluşturur.
"""
from PIL import Image, ImageDraw
from io import BytesIO
import math
from typing import List, Tuple, Literal


LayoutType = Literal["grid", "feature", "full_bleed"]


def crop_to_fill(img: Image.Image, target_width: int, target_height: int) -> Image.Image:
    """
    Görseli hedef boyuta göre ortadan kırp (crop to fill).
    Boşluk kalmaz, görsel tam dolar.
    """
    img_ratio = img.width / img.height
    target_ratio = target_width / target_height

    if img_ratio > target_ratio:
        new_height = target_height
        new_width = int(img.width * (target_height / img.height))
    else:
        new_width = target_width
        new_height = int(img.height * (target_width / img.width))

    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    left = (new_width - target_width) // 2
    top = (new_height - target_height) // 2
    right = left + target_width
    bottom = top + target_height

    return img.crop((left, top, right, bottom))


def prepare_image(img_bytes: bytes) -> Image.Image:
    """Görseli RGB formatına hazırla."""
    img = Image.open(BytesIO(img_bytes))

    if img.mode in ('RGBA', 'P'):
        bg = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        if img.mode == 'RGBA':
            bg.paste(img, mask=img.split()[3])
        else:
            bg.paste(img)
        img = bg
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    return img


def create_full_bleed_grid(
    images: List[Image.Image],
    output_size: Tuple[int, int] = (1080, 1080),
    gap: int = 3
) -> Image.Image:
    """
    Tam kaplama grid - minimal boşluk, görseller neredeyse yapışık.

    Args:
        images: Hazırlanmış Image listesi
        output_size: Çıktı boyutu
        gap: Görseller arası ince çizgi (0-5px)
    """
    n = len(images)

    # Grid boyutları
    if n == 2:
        cols, rows = 2, 1
    elif n == 3:
        cols, rows = 3, 1
    elif n == 4:
        cols, rows = 2, 2
    elif n <= 6:
        cols, rows = 3, 2
    elif n <= 9:
        cols, rows = 3, 3
    else:
        cols = math.ceil(math.sqrt(n))
        rows = math.ceil(n / cols)

    # Canvas
    collage = Image.new('RGB', output_size, (255, 255, 255))

    # Hücre boyutları (gap dahil)
    total_gap_x = gap * (cols - 1)
    total_gap_y = gap * (rows - 1)
    cell_width = (output_size[0] - total_gap_x) // cols
    cell_height = (output_size[1] - total_gap_y) // rows

    for idx, img in enumerate(images):
        if idx >= cols * rows:
            break

        row = idx // cols
        col = idx % cols

        # Crop to fill
        cropped = crop_to_fill(img, cell_width, cell_height)

        # Pozisyon
        x = col * (cell_width + gap)
        y = row * (cell_height + gap)

        collage.paste(cropped, (x, y))

    return collage


def create_feature_layout(
    images: List[Image.Image],
    output_size: Tuple[int, int] = (1080, 1080),
    gap: int = 3
) -> Image.Image:
    """
    Feature layout - 1 büyük ana görsel + küçük görseller.

    2 görsel: Sol büyük (2/3) | Sağ küçük (1/3)
    3 görsel: Sol büyük | Sağ üst + alt
    4 görsel: Sol büyük | Sağda 3 küçük üst üste
    5+ görsel: Sol büyük | Sağda 2 sütun grid
    """
    n = len(images)
    collage = Image.new('RGB', output_size, (255, 255, 255))

    if n == 2:
        # Sol 2/3, sağ 1/3
        left_width = int(output_size[0] * 0.65) - gap // 2
        right_width = output_size[0] - left_width - gap

        # Sol (büyük)
        left_img = crop_to_fill(images[0], left_width, output_size[1])
        collage.paste(left_img, (0, 0))

        # Sağ
        right_img = crop_to_fill(images[1], right_width, output_size[1])
        collage.paste(right_img, (left_width + gap, 0))

    elif n == 3:
        # Sol yarı | Sağ yarı (üst + alt)
        left_width = output_size[0] // 2 - gap // 2
        right_width = output_size[0] - left_width - gap
        half_height = (output_size[1] - gap) // 2

        # Sol büyük
        left_img = crop_to_fill(images[0], left_width, output_size[1])
        collage.paste(left_img, (0, 0))

        # Sağ üst
        right_top = crop_to_fill(images[1], right_width, half_height)
        collage.paste(right_top, (left_width + gap, 0))

        # Sağ alt
        right_bottom = crop_to_fill(images[2], right_width, half_height)
        collage.paste(right_bottom, (left_width + gap, half_height + gap))

    elif n == 4:
        # Sol yarı | Sağda 3 küçük veya 2x2 benzeri
        left_width = output_size[0] // 2 - gap // 2
        right_width = output_size[0] - left_width - gap
        third_height = (output_size[1] - gap * 2) // 3

        # Sol büyük
        left_img = crop_to_fill(images[0], left_width, output_size[1])
        collage.paste(left_img, (0, 0))

        # Sağda 3 küçük
        for i in range(3):
            small_img = crop_to_fill(images[i + 1], right_width, third_height)
            y = i * (third_height + gap)
            collage.paste(small_img, (left_width + gap, y))

    else:
        # 5+ görsel: Sol büyük | Sağda grid
        left_width = int(output_size[0] * 0.55) - gap // 2
        right_width = output_size[0] - left_width - gap

        # Sol büyük
        left_img = crop_to_fill(images[0], left_width, output_size[1])
        collage.paste(left_img, (0, 0))

        # Sağda kalan görseller için grid
        remaining = images[1:]
        remaining_count = len(remaining)

        if remaining_count <= 2:
            # 2 görsel: üst üste
            cell_height = (output_size[1] - gap) // 2
            for i, img in enumerate(remaining):
                cropped = crop_to_fill(img, right_width, cell_height)
                y = i * (cell_height + gap)
                collage.paste(cropped, (left_width + gap, y))
        elif remaining_count <= 4:
            # 2x2 grid
            cols, rows = 2, 2
            cell_w = (right_width - gap) // 2
            cell_h = (output_size[1] - gap) // 2
            for i, img in enumerate(remaining[:4]):
                row, col = i // 2, i % 2
                cropped = crop_to_fill(img, cell_w, cell_h)
                x = left_width + gap + col * (cell_w + gap)
                y = row * (cell_h + gap)
                collage.paste(cropped, (x, y))
        else:
            # 2x3 veya daha fazla
            cols = 2
            rows = math.ceil(remaining_count / cols)
            cell_w = (right_width - gap) // cols
            cell_h = (output_size[1] - gap * (rows - 1)) // rows
            for i, img in enumerate(remaining[:cols * rows]):
                row, col = i // cols, i % cols
                cropped = crop_to_fill(img, cell_w, cell_h)
                x = left_width + gap + col * (cell_w + gap)
                y = row * (cell_h + gap)
                collage.paste(cropped, (x, y))

    return collage


def create_collage(
    image_data_list: List[bytes],
    output_size: Tuple[int, int] = (1080, 1080),
    layout: LayoutType = "feature",
    gap: int = 3
) -> bytes:
    """
    Çoklu görsellerden kolaj oluştur.

    Args:
        image_data_list: Görsel verilerinin bytes listesi
        output_size: Hedef çıktı boyutları (genişlik, yükseklik)
        layout: Layout tipi - "feature", "full_bleed", veya "grid"
        gap: Görseller arası boşluk (0-5 px önerilir)

    Returns:
        Kolaj görseli JPEG bytes olarak
    """
    if not image_data_list:
        raise ValueError("En az bir görsel gerekli")

    # Görselleri hazırla
    images = []
    for img_bytes in image_data_list:
        try:
            img = prepare_image(img_bytes)
            images.append(img)
        except Exception as e:
            print(f"Görsel işlenemedi: {e}")
            continue

    if len(images) < 1:
        raise ValueError("Hiçbir görsel işlenemedi")

    # Layout'a göre kolaj oluştur
    if layout == "feature":
        collage = create_feature_layout(images, output_size, gap)
    elif layout == "full_bleed":
        collage = create_full_bleed_grid(images, output_size, gap)
    else:  # grid (eski default)
        collage = create_full_bleed_grid(images, output_size, gap)

    # Bytes'a çevir
    output = BytesIO()
    collage.save(output, format='JPEG', quality=95)
    return output.getvalue()
