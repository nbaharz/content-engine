# Content Engine

AI-powered social media content automation tool. Generates campaign visuals, creates posters, and publishes directly to Instagram — all from a single campaign URL.

> Currently being developed for [Grupanya](https://grupanya.com), a leading deals platform in Turkey.

## What It Does

1. **Scrapes** a campaign page and extracts key info (title, category, discount) using AI
2. **Generates** a photorealistic campaign image via [fal.ai](https://fal.ai) workflows
3. **Creates** professional posters with text overlays, gradient backgrounds, and discount badges
4. **Posts** directly to Instagram (single image or carousel).
5. **Runs on schedule** via GitHub Actions — fully automated, no manual intervention needed

## Features

- **AI Content Generation** — Uses fal.ai workflows to generate campaign images and captions from a text prompt
- **Smart Scraping** — Extracts campaign details and images from any deal page
- **Poster Creator** — Pillow-based poster engine with gradient overlays, discount badges, and auto text wrapping
- **Collage Layouts** — Multiple layout options (feature, grid, full bleed) for multi-image posts
- **AI Poster Mode** — Flux img2img stylization on top of collage, then text overlay
- **Instagram Integration** — Single image and carousel posting via Instagram Graph API
- **Scheduled Automation** — GitHub Actions cron runs 3x daily on weekdays
- **Web UI** — Flask dashboard to manage campaigns, preview content, and publish manually

## Tech Stack

| Layer | Technology |
|---|---|
| AI Image Generation | [fal.ai](https://fal.ai) (Flux, Any LLM) |
| LLM | Claude Sonnet 4.5 (via fal.ai) |
| Image Processing | Pillow |
| Web Scraping | BeautifulSoup4 |
| Web UI | Flask |
| Social Media | Instagram Graph API |
| Automation | GitHub Actions |

## Setup

### 1. Clone and install

```bash
git clone https://github.com/nbaharz/content-engine.git
cd content-engine
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```
FAL_KEY=your_fal_api_key
INSTAGRAM_ACCESS_TOKEN=your_instagram_token
INSTAGRAM_ACCOUNT_ID=your_account_id
```

### 3. Add campaign URLs

```bash
cp campaigns.example.json campaigns.json
```

Add your campaign page URLs to `campaigns.json`:

```json
[
    "https://example.com/campaign-1",
    "https://example.com/campaign-2"
]
```

## Usage

### Web UI

```bash
python app.py
```

Opens at `http://localhost:5000`. From the dashboard you can:

- Add campaigns by URL (AI auto-extracts info)
- Edit campaign details
- Generate content with or without poster mode
- Upload custom images and create collages/posters
- Adjust text position on posters
- Post to Instagram (single or carousel)

### CLI

```bash
python main.py
```

Interactive mode — pick a campaign, generate content, and optionally post to Instagram.

### Scheduled Automation

The included GitHub Actions workflow (`.github/workflows/schedule.yml`) runs `scheduler.py` three times daily on weekdays:

- 09:00, 11:20, 18:00 (Turkey time)

It cycles through your `campaigns.json` URLs automatically. Set `FAL_KEY`, `INSTAGRAM_ACCESS_TOKEN`, and `INSTAGRAM_ACCOUNT_ID` as repository secrets.

## Project Structure

```
content-engine/
├── app.py              # Flask web UI and API endpoints
├── main.py             # CLI interface
├── scheduler.py        # Automated scheduling logic
├── instagram.py        # Instagram Graph API integration
├── poster.py           # Poster generation with text overlays
├── collage.py          # Multi-image collage layouts
├── requirements.txt
├── campaigns.json      # Your campaign URLs (gitignored)
├── .env                # Your API keys (gitignored)
├── static/
│   └── css/style.css
├── templates/
│   └── index.html
└── .github/
    └── workflows/
        └── schedule.yml
```

