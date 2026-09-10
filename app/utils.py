"""Small helpers shared by the blueprints."""
import re
import secrets
import string
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

from .db import query


def slugify(text, table=None, exclude_id=None):
    """Turn 'Rose Hand Cream' into 'rose-hand-cream', keeping it unique in `table`."""
    base = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "item"
    if table is None:
        return base
    slug, n = base, 2
    while True:
        params = [slug]
        sql = f"SELECT id FROM {table} WHERE slug = ?"
        if exclude_id:
            sql += " AND id != ?"
            params.append(exclude_id)
        if query(sql, params, one=True) is None:
            return slug
        slug = f"{base}-{n}"
        n += 1


def generate_rep_code():
    """Unique short code a sales representative uses as their EFT reference."""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "YR-" + "".join(secrets.choice(alphabet) for _ in range(5))
        if query("SELECT id FROM users WHERE rep_code = ?", (code,), one=True) is None:
            return code


def generate_order_number():
    while True:
        number = "YL" + "".join(secrets.choice(string.digits) for _ in range(6))
        if query("SELECT id FROM orders WHERE order_number = ?", (number,), one=True) is None:
            return number


def save_image(file_storage):
    """Store an uploaded image in static/uploads and return its URL path, or None."""
    if not file_storage or not file_storage.filename:
        return None
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        raise ValueError("Please upload a PNG, JPG, WEBP or GIF image.")
    name = f"{uuid.uuid4().hex}.{ext}"
    dest = Path(current_app.config["UPLOAD_FOLDER"]) / secure_filename(name)
    file_storage.save(dest)
    return f"/static/uploads/{name}"


def parse_price(value, default=None):
    try:
        value = float(str(value).replace(",", "").strip())
        return round(value, 2) if value >= 0 else default
    except (TypeError, ValueError):
        return default


def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
