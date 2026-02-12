from flask import Flask, render_template
from dotenv import load_dotenv

from services.campaigns import load_campaigns
from routes.campaigns import campaigns_bp
from routes.generation import generation_bp
from routes.instagram import instagram_bp
from routes.media import media_bp

load_dotenv()

app = Flask(__name__)

app.register_blueprint(campaigns_bp)
app.register_blueprint(generation_bp)
app.register_blueprint(instagram_bp)
app.register_blueprint(media_bp)


@app.route('/')
def index():
    """Home page."""
    return render_template('index.html', campaigns=load_campaigns())


if __name__ == '__main__':
    app.run(debug=True, port=5000)
