import json
import requests
from flask import Blueprint, request, jsonify

from services.campaigns import load_campaigns, save_campaigns, DEFAULT_NEGATIVE_PROMPT
from services.scraper import scrape_campaign_page, extract_campaign_info

campaigns_bp = Blueprint('campaigns', __name__)


@campaigns_bp.route('/add-campaign', methods=['POST'])
def add_campaign():
    """Extract campaign info from URL with AI and add to the list."""
    try:
        url = request.json.get('url', '').strip()
        if not url:
            return jsonify({"error": "URL is required"}), 400

        page_content = scrape_campaign_page(url)
        info = extract_campaign_info(page_content)

        campaigns = load_campaigns()
        new_id = max((c["id"] for c in campaigns), default=0) + 1
        campaign = {
            "id": new_id,
            "url": url,
            "title": info["title"],
            "category": info["category"],
            "discount": info["discount"],
            "negative_prompt": DEFAULT_NEGATIVE_PROMPT,
        }
        campaigns.append(campaign)
        save_campaigns(campaigns)

        return jsonify({"success": True, "campaign": campaign})

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to load page: {str(e)}"}), 400
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse AI response, please try again"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@campaigns_bp.route('/scrape-campaign', methods=['POST'])
def scrape_campaign():
    """Scrape campaign URL, fill in info, and save."""
    try:
        campaign_id = int(request.json.get('campaign_id'))
        campaigns = load_campaigns()
        campaign = next((c for c in campaigns if c["id"] == campaign_id), None)

        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        url = campaign.get("url", "")
        if not url:
            return jsonify({"error": "Campaign has no URL"}), 400

        page_content = scrape_campaign_page(url)
        info = extract_campaign_info(page_content)

        campaign["title"] = info["title"]
        campaign["category"] = info["category"]
        campaign["discount"] = info["discount"]
        if "negative_prompt" not in campaign:
            campaign["negative_prompt"] = DEFAULT_NEGATIVE_PROMPT
        save_campaigns(campaigns)

        return jsonify({"success": True, "campaign": campaign})

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to load page: {str(e)}"}), 400
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse AI response, please try again"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@campaigns_bp.route('/update-campaign', methods=['POST'])
def update_campaign():
    """Update campaign info."""
    try:
        data = request.json
        campaign_id = int(data.get('campaign_id'))
        campaigns = load_campaigns()
        campaign = next((c for c in campaigns if c["id"] == campaign_id), None)

        if not campaign:
            return jsonify({"error": "Campaign not found"}), 404

        campaign["title"] = data.get("title", campaign["title"])
        campaign["category"] = data.get("category", campaign["category"])
        campaign["discount"] = data.get("discount", campaign["discount"])
        campaign["negative_prompt"] = data.get("negative_prompt", campaign.get("negative_prompt", DEFAULT_NEGATIVE_PROMPT))
        save_campaigns(campaigns)

        return jsonify({"success": True, "campaign": campaign})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
