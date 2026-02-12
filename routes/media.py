import os
import tempfile
import base64
import requests
import fal_client
from flask import Blueprint, request, jsonify

from services.campaigns import load_campaigns
from collage import create_collage
from poster import create_poster, create_poster_from_multiple, create_raw_collage

media_bp = Blueprint('media', __name__)


@media_bp.route('/upload-image', methods=['POST'])
def upload_image():
    """Upload image to fal.ai storage and get a public URL."""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "File not found"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400

        ext = os.path.splitext(file.filename)[1] or '.jpg'
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name

        url = fal_client.upload_file(tmp_path)
        os.unlink(tmp_path)

        return jsonify({"success": True, "url": url})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@media_bp.route('/upload-images', methods=['POST'])
def upload_images():
    """Upload multiple images and return fal.ai URLs."""
    try:
        if 'files' not in request.files:
            return jsonify({"error": "Files not found"}), 400

        files = request.files.getlist('files')
        if not files or len(files) == 0:
            return jsonify({"error": "No files selected"}), 400
        if len(files) > 10:
            return jsonify({"error": "Maximum 10 images can be uploaded"}), 400

        uploaded_urls = []
        for file in files:
            if file.filename == '':
                continue

            ext = os.path.splitext(file.filename)[1] or '.jpg'
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
                file.save(tmp.name)
                tmp_path = tmp.name

            url = fal_client.upload_file(tmp_path)
            uploaded_urls.append(url)
            os.unlink(tmp_path)

        return jsonify({
            "success": True,
            "urls": uploaded_urls,
            "count": len(uploaded_urls)
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@media_bp.route('/create-collage', methods=['POST'])
def create_collage_endpoint():
    """Create collage from images."""
    try:
        image_data_list = []
        layout = "feature"

        if 'files' in request.files:
            files = request.files.getlist('files')
            for file in files:
                if file.filename:
                    image_data_list.append(file.read())
            layout = request.form.get('layout', 'feature')
        elif request.json and 'image_urls' in request.json:
            for url in request.json['image_urls']:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                image_data_list.append(response.content)
            layout = request.json.get('layout', 'feature')

        if len(image_data_list) < 2:
            return jsonify({"error": "Collage requires at least 2 images"}), 400

        collage_bytes = create_collage(image_data_list, layout=layout, gap=3)
        collage_base64 = base64.b64encode(collage_bytes).decode('utf-8')

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
        return jsonify({"error": str(e)}), 500


@media_bp.route('/create-posters', methods=['POST'])
def create_posters():
    """Create poster from multiple images (AI or basic mode)."""
    try:
        if 'files' not in request.files:
            return jsonify({"error": "Files not found"}), 400

        files = request.files.getlist('files')
        campaign_id = int(request.form.get('campaign_id', 0))
        ai_mode = request.form.get('ai_mode', 'false') == 'true'

        if not files:
            return jsonify({"error": "No files selected"}), 400
        if len(files) > 4:
            return jsonify({"error": "Maximum 4 images can be uploaded"}), 400

        campaign = next((c for c in load_campaigns() if c["id"] == campaign_id), None)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        image_data_list = []
        for file in files:
            if file.filename:
                image_data_list.append(file.read())

        if not image_data_list:
            return jsonify({"error": "No valid files found"}), 400

        if ai_mode:
            # NOTE: generate_ai_poster is not yet defined (existing bug)
            from services.content import generate_ai_poster
            result = generate_ai_poster(image_data_list, campaign)
            poster_bytes = result["poster_bytes"]
            raw_bytes = result.get("raw_bytes")
        else:
            raw_bytes = create_raw_collage(image_data_list)
            poster_bytes = create_poster_from_multiple(
                image_data_list,
                campaign["title"],
                campaign["discount"],
            )

        poster_base64 = base64.b64encode(poster_bytes).decode("utf-8")
        raw_base64 = base64.b64encode(raw_bytes).decode("utf-8") if raw_bytes else None

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


@media_bp.route('/adjust-poster', methods=['POST'])
def adjust_poster():
    """Adjust text position on poster and re-render."""
    try:
        data = request.json
        raw_base64 = data.get('raw_image_base64')
        campaign_id = int(data.get('campaign_id', 0))
        title_y_percent = int(data.get('title_y_percent', 58))
        mode = data.get('mode', 'ai')

        if not raw_base64:
            return jsonify({"error": "raw_image_base64 is required"}), 400

        campaign = next((c for c in load_campaigns() if c["id"] == campaign_id), None)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        raw_bytes = base64.b64decode(raw_base64)

        title = data.get('title') or campaign["title"]
        discount = data.get('discount') or campaign["discount"]

        if mode == 'ai':
            poster_bytes = create_poster(
                raw_bytes,
                title,
                discount,
                title_y_percent=title_y_percent,
            )
        else:
            poster_bytes = create_poster_from_multiple(
                [raw_bytes],
                title,
                discount,
                title_y_percent=title_y_percent,
            )

        poster_base64 = base64.b64encode(poster_bytes).decode("utf-8")

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
