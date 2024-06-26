import secrets
import warnings

from frontend.server.bp import bp
from frontend.server.website import Website
from frontend.server.backend import Backend_Api
from frontend.server.babel import create_babel
from json import load
from flask import Flask

warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", message="Enable tracemalloc to get the object allocation traceback")

# Load configuration from config.json
config = load(open('frontend/server/config.json', 'r'))
site_config = config['site_config']
url_prefix = config.pop('url_prefix')


# Create the app
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)


# Set up Babel
create_babel(app)


# Set up the website routes
site = Website(bp, url_prefix)
for route in site.routes:
    bp.add_url_rule(
        route,
        view_func=site.routes[route]['function'],
        methods=site.routes[route]['methods'],
    )


# Set up the backend API routes
backend_api = Backend_Api(bp, config)
for route in backend_api.routes:
    bp.add_url_rule(
        route,
        view_func=backend_api.routes[route]['function'],
        methods=backend_api.routes[route]['methods'],
    )


# Register the blueprint
app.register_blueprint(bp, url_prefix=url_prefix)


# Run the Flask server
print(f"Running on {site_config['port']}{url_prefix}")
app.run(**site_config)
print(f"Closing port {site_config['port']}")
