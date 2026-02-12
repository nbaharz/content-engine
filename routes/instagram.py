from flask import Blueprint, request, jsonify

from instagram import post_to_instagram, post_carousel_to_instagram

instagram_bp = Blueprint('instagram', __name__)


@instagram_bp.route('/post-instagram', methods=['POST'])
def post_instagram():
    """Post to Instagram."""
    try:
        data = request.json
        image_url = data.get('image_url')
        caption = data.get('caption')

        if not image_url or not caption:
            return jsonify({"error": "image_url and caption are required"}), 400

        result = post_to_instagram(image_url, caption)

        if result['success']:
            return jsonify({
                "success": True,
                "post_id": result['post_id'],
                "message": "Successfully posted to Instagram!"
            })
        else:
            return jsonify({"error": result['error']}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@instagram_bp.route('/post-instagram-carousel', methods=['POST'])
def post_instagram_carousel():
    """Post multiple images as Instagram carousel."""
    try:
        data = request.json
        image_urls = data.get('image_urls', [])
        caption = data.get('caption', '')

        if not image_urls:
            return jsonify({"error": "image_urls is required"}), 400
        if len(image_urls) < 2:
            return jsonify({"error": "Carousel requires at least 2 images"}), 400
        if len(image_urls) > 10:
            return jsonify({"error": "Carousel can contain at most 10 images"}), 400
        if not caption:
            return jsonify({"error": "caption is required"}), 400

        result = post_carousel_to_instagram(image_urls, caption)

        if result['success']:
            return jsonify({
                "success": True,
                "post_id": result['post_id'],
                "message": "Carousel successfully posted to Instagram!"
            })
        else:
            return jsonify({"error": result['error']}), 500

    except Exception as e:
        return jsonify({"error": str(e)}), 500
