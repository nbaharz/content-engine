import os
import base64
from pathlib import Path
from flask import Blueprint, request, jsonify

from services.campaigns import load_campaigns
from services.content import generate_instagram_content, generate_caption, generate_website_content
from poster import create_poster

generation_bp = Blueprint('generation', __name__)


@generation_bp.route('/generate', methods=['POST'])
def generate():
    """Generate campaign content."""
    try:
        if not os.getenv("FAL_KEY"):
            return jsonify({"error": "FAL_KEY environment variable not found"}), 400

        campaign_id = int(request.json.get('campaign_id'))
        poster_mode = request.json.get('poster_mode', False)
        campaign = next((c for c in load_campaigns() if c["id"] == campaign_id), None)

        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        result = generate_instagram_content(campaign)
        image_base64 = result["image_base64"]

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


@generation_bp.route('/generate-caption', methods=['POST'])
def generate_caption_endpoint():
    """Generate campaign caption with AI."""
    try:
        if not os.getenv("FAL_KEY"):
            return jsonify({"error": "FAL_KEY environment variable not found"}), 400

        campaign_id = int(request.json.get('campaign_id'))
        campaign = next((c for c in load_campaigns() if c["id"] == campaign_id), None)

        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        caption = generate_caption(campaign)
        return jsonify({"success": True, "caption": caption})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@generation_bp.route('/generate-website-content', methods=['POST'])
def generate_website_content_endpoint():
    """Generate campaign image for website."""
    try:
        if not os.getenv("FAL_KEY"):
            return jsonify({"error": "FAL_KEY environment variable not found"}), 400

        campaign_id = int(request.form.get('campaign_id', 0))
        num_images = int(request.form.get('num_images', 1))
        if num_images < 1 or num_images > 4:
            return jsonify({"error": "num_images must be between 1 and 4"}), 400

        campaign = next((c for c in load_campaigns() if c["id"] == campaign_id), None)
        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        reference_images = []
        if 'files' in request.files:
            files = request.files.getlist('files')
            for file in files:
                if file.filename:
                    reference_images.append(file.read())
        if not reference_images:
            reference_images = None

        results = generate_website_content(campaign, reference_images, num_images)
        images = [{
            "image_base64": r["image_base64"],
            "image_url": r["image_url"]
        } for r in results]

        return jsonify({"success": True, "images": images})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@generation_bp.route('/download/<int:campaign_id>')
def download(campaign_id):
    """Download generated content."""
    try:
        campaign = next((c for c in load_campaigns() if c["id"] == campaign_id), None)
        if not campaign:
            return "Campaign not found", 404

        out_dir = Path.home() / "Desktop" / campaign["title"].replace(" ", "_")
        out_dir.mkdir(parents=True, exist_ok=True)

        result = generate_instagram_content(campaign)

        image_path = out_dir / "image.jpg"
        image_path.write_bytes(result["image_data"])
        (out_dir / "caption.txt").write_text(result["post_text"], encoding="utf-8")

        return jsonify({
            "success": True,
            "folder_path": str(out_dir),
            "message": f"Content saved to Desktop/{campaign['title'].replace(' ', '_')}"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500
