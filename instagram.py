import os
import time
import requests
from typing import List, Dict


def get_instagram_credentials():
    """Environment variable'lardan Instagram credentials al."""
    access_token = os.getenv("INSTAGRAM_ACCESS_TOKEN")
    account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")

    if not access_token:
        raise RuntimeError("INSTAGRAM_ACCESS_TOKEN yok. .env dosyasını kontrol et.")
    if not account_id:
        raise RuntimeError("INSTAGRAM_ACCOUNT_ID yok. .env dosyasını kontrol et.")

    return access_token, account_id


def post_to_instagram(image_url: str, caption: str) -> dict:
    """
    Instagram'a görsel paylaş.

    Args:
        image_url: Herkese açık erişilebilir görsel URL'si (fal.ai'dan gelen)
        caption: Post açıklaması

    Returns:
        dict: Başarılıysa {'success': True, 'post_id': '...'},
              değilse {'success': False, 'error': '...'}
    """
    access_token, account_id = get_instagram_credentials()

    # 1. ADIM: Media Container Oluşturma
    container_url = f"https://graph.facebook.com/v19.0/{account_id}/media"
    payload = {
        'image_url': image_url,
        'caption': caption,
        'access_token': access_token
    }

    print("Instagram'a yükleniyor...")
    response = requests.post(container_url, data=payload, timeout=30)
    result = response.json()

    if 'id' not in result:
        return {'success': False, 'error': f"Container hatası: {result}"}

    creation_id = result['id']
    print(f"Media container oluşturuldu: {creation_id}")

    # Instagram'ın görseli işlemesi için bekle
    time.sleep(10)

    # 2. ADIM: Medyayı Yayınla
    publish_url = f"https://graph.facebook.com/v19.0/{account_id}/media_publish"
    publish_payload = {
        'creation_id': creation_id,
        'access_token': access_token
    }

    publish_response = requests.post(publish_url, data=publish_payload, timeout=30)
    publish_result = publish_response.json()

    if 'id' in publish_result:
        return {'success': True, 'post_id': publish_result['id']}
    else:
        return {'success': False, 'error': f"Yayınlama hatası: {publish_result}"}


def create_carousel_child_container(image_url: str, access_token: str, account_id: str) -> str:
    """
    Carousel için child container oluştur.

    Args:
        image_url: Görselin public URL'si
        access_token: Instagram access token
        account_id: Instagram account ID

    Returns:
        Container ID (creation_id)
    """
    endpoint = f"https://graph.facebook.com/v19.0/{account_id}/media"
    payload = {
        'image_url': image_url,
        'is_carousel_item': 'true',
        'access_token': access_token
    }

    response = requests.post(endpoint, data=payload, timeout=30)
    result = response.json()

    if 'id' not in result:
        raise RuntimeError(f"Child container oluşturulamadı: {result}")

    return result['id']


def create_carousel_parent_container(
    child_ids: List[str],
    caption: str,
    access_token: str,
    account_id: str
) -> str:
    """
    Tüm child'ları birleştiren carousel parent container oluştur.

    Args:
        child_ids: Child container ID listesi
        caption: Post açıklaması
        access_token: Instagram access token
        account_id: Instagram account ID

    Returns:
        Parent container ID (creation_id)
    """
    endpoint = f"https://graph.facebook.com/v19.0/{account_id}/media"
    payload = {
        'media_type': 'CAROUSEL',
        'children': ','.join(child_ids),
        'caption': caption,
        'access_token': access_token
    }

    response = requests.post(endpoint, data=payload, timeout=30)
    result = response.json()

    if 'id' not in result:
        raise RuntimeError(f"Carousel container oluşturulamadı: {result}")

    return result['id']


def publish_media(creation_id: str, access_token: str, account_id: str) -> str:
    """
    Media container'ı Instagram'da yayınla.

    Args:
        creation_id: Media container ID
        access_token: Instagram access token
        account_id: Instagram account ID

    Returns:
        Yayınlanan post ID
    """
    endpoint = f"https://graph.facebook.com/v19.0/{account_id}/media_publish"
    payload = {
        'creation_id': creation_id,
        'access_token': access_token
    }

    response = requests.post(endpoint, data=payload, timeout=30)
    result = response.json()

    if 'id' not in result:
        raise RuntimeError(f"Yayınlama hatası: {result}")

    return result['id']


def post_carousel_to_instagram(image_urls: List[str], caption: str) -> Dict:
    """
    Çoklu görseli Instagram carousel olarak paylaş.

    Args:
        image_urls: Public görsel URL listesi (2-10 görsel)
        caption: Post açıklaması

    Returns:
        dict: Başarılıysa {'success': True, 'post_id': '...'},
              değilse {'success': False, 'error': '...'}
    """
    # Görsel sayısı kontrolü
    if len(image_urls) < 2:
        return {'success': False, 'error': 'Carousel en az 2 görsel gerektirir'}
    if len(image_urls) > 10:
        return {'success': False, 'error': 'Carousel en fazla 10 görsel içerebilir'}

    try:
        access_token, account_id = get_instagram_credentials()

        print(f"Carousel oluşturuluyor... ({len(image_urls)} görsel)")

        # Adım 1: Her görsel için child container oluştur
        child_ids = []
        for i, url in enumerate(image_urls):
            print(f"  Child {i+1}/{len(image_urls)} oluşturuluyor...")
            child_id = create_carousel_child_container(url, access_token, account_id)
            child_ids.append(child_id)
            time.sleep(2)  # Rate limiting

        # İşlenmesi için bekle
        print("Instagram görselleri işliyor...")
        time.sleep(10)

        # Adım 2: Parent container oluştur
        print("Carousel container oluşturuluyor...")
        parent_id = create_carousel_parent_container(
            child_ids, caption, access_token, account_id
        )

        # İşlenmesi için bekle
        time.sleep(10)

        # Adım 3: Yayınla
        print("Yayınlanıyor...")
        post_id = publish_media(parent_id, access_token, account_id)

        return {'success': True, 'post_id': post_id}

    except Exception as e:
        return {'success': False, 'error': str(e)}
