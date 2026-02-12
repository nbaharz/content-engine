import os
import json

CAMPAIGNS_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "campaigns.json")

DEFAULT_NEGATIVE_PROMPT = (
    "no illustration, no cartoon, no 3D render, no CGI, no anime, "
    "no watermark, no text overlay, no logo, no blurry, no low quality"
)


def load_campaigns():
    """Load campaign list from campaigns.json."""
    if os.path.exists(CAMPAIGNS_PATH):
        with open(CAMPAIGNS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_campaigns(campaigns):
    """Save campaign list to campaigns.json."""
    with open(CAMPAIGNS_PATH, "w", encoding="utf-8") as f:
        json.dump(campaigns, f, ensure_ascii=False, indent=4)
