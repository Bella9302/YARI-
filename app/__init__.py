"""YARI Lifestyle online store — Flask application factory."""
import os
import secrets
from pathlib import Path

from flask import Flask, abort, request, session
from markupsafe import Markup

from . import db as database
from .auth import load_current_user

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_secret_key(instance_dir):
    """Use SECRET_KEY from the environment, otherwise a random key kept in instance/secret_key.

    The file is created on first start and reused afterwards, so logins survive restarts
    without anyone having to invent a key by hand.
    """
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    key_file = instance_dir / "secret_key"
    try:
        # O_EXCL: only one process can create the file, so every worker shares one key.
        fd = os.open(key_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "w") as fh:
            fh.write(secrets.token_hex(32))
    key = key_file.read_text().strip()
    if not key:  # another worker created the file but hasn't finished writing it
        import time

        time.sleep(0.2)
        key = key_file.read_text().strip()
    return key


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    instance_dir = Path(app.instance_path)
    instance_dir.mkdir(parents=True, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=_load_secret_key(instance_dir),
        DATABASE=os.environ.get("DATABASE_PATH", str(instance_dir / "yari.sqlite")),
        UPLOAD_FOLDER=str(Path(app.root_path) / "static" / "uploads"),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024,  # 5 MB image uploads
        ALLOWED_IMAGE_EXTENSIONS={"png", "jpg", "jpeg", "webp", "gif"},
        # Business details shown across the site — override with env vars in production.
        BUSINESS_NAME=os.environ.get("BUSINESS_NAME", "YARI Lifestyle"),
        BUSINESS_TAGLINE="Lifestyle, household & personal care, delivered by people you trust.",
        BUSINESS_EMAIL=os.environ.get("BUSINESS_EMAIL", "hello@yarilifestyle.co.za"),
        BUSINESS_PHONE=os.environ.get("BUSINESS_PHONE", "+27 00 000 0000"),
        BUSINESS_WHATSAPP=os.environ.get("BUSINESS_WHATSAPP", "27000000000"),
        BUSINESS_ADDRESS=os.environ.get("BUSINESS_ADDRESS", "South Africa"),
        CURRENCY_SYMBOL=os.environ.get("CURRENCY_SYMBOL", "R"),
        # Flip to True once a payment gateway (e.g. PayFast, Yoco) is connected in shop.py.
        ONLINE_PAYMENTS_ENABLED=os.environ.get("ONLINE_PAYMENTS_ENABLED", "false").lower() == "true",
        DELIVERY_FEE=float(os.environ.get("DELIVERY_FEE", "0")),
        # The demo account hints on the login page appear only while the demo owner account
        # exists. Set SHOW_DEMO_LOGINS=false to hide them regardless.
        SHOW_DEMO_LOGINS=os.environ.get("SHOW_DEMO_LOGINS", "true").lower() == "true",
        CSRF_ENABLED=True,
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)

    database.init_app(app)

    from . import shop, auth, admin, seller, rep

    app.register_blueprint(shop.bp)
    app.register_blueprint(auth.bp)
    app.register_blueprint(admin.bp)
    app.register_blueprint(seller.bp)
    app.register_blueprint(rep.bp)

    app.before_request(load_current_user)

    def csrf_token():
        if "_csrf" not in session:
            session["_csrf"] = secrets.token_urlsafe(32)
        return session["_csrf"]

    @app.before_request
    def check_csrf():
        """Every POST must carry the token that was rendered into the form."""
        if request.method == "POST" and app.config["CSRF_ENABLED"]:
            token = session.get("_csrf")
            if not token or not secrets.compare_digest(token, request.form.get("csrf_token", "")):
                abort(400, "The form has expired. Please go back, refresh the page and try again.")

    @app.context_processor
    def inject_globals():
        from .db import query

        cart = session.get("cart", {})
        cart_count = sum(cart.values()) if isinstance(cart, dict) else 0
        categories = query("SELECT * FROM categories ORDER BY sort_order, name")
        return {
            "csrf_field": lambda: Markup(f'<input type="hidden" name="csrf_token" value="{csrf_token()}">'),
            "cart_count": cart_count,
            "nav_categories": categories,
            "cfg": app.config,
        }

    @app.template_filter("money")
    def money(value):
        try:
            value = float(value or 0)
        except (TypeError, ValueError):
            value = 0.0
        return f"{app.config['CURRENCY_SYMBOL']}{value:,.2f}"

    @app.template_filter("status_label")
    def status_label(value):
        return {
            "placed": "Placed — awaiting owner",
            "sent_to_seller": "Sent to seller",
            "processing": "Being prepared",
            "shipped": "On its way",
            "delivered": "Delivered",
            "cancelled": "Cancelled",
        }.get(value, value)

    @app.template_filter("nice_date")
    def nice_date(value):
        if not value:
            return ""
        return str(value)[:16].replace("T", " ")

    with app.app_context():
        database.init_db()

    return app
