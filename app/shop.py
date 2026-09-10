"""Public storefront: browsing, search, cart, checkout, promotions, contact, delivery info."""
from datetime import date

from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template,
                   request, session, url_for)

from .db import execute, get_db, query
from .utils import generate_order_number, parse_int

bp = Blueprint("shop", __name__)

# --------------------------------------------------------------------------- helpers


def get_cart():
    cart = session.get("cart")
    if not isinstance(cart, dict):
        cart = {}
    return cart


def save_cart(cart):
    session["cart"] = {k: v for k, v in cart.items() if v > 0}
    session.modified = True


def cart_details():
    """Return (items, subtotal) for the current session cart, dropping stale products."""
    cart = get_cart()
    if not cart:
        return [], 0.0
    ids = [int(k) for k in cart.keys()]
    placeholders = ",".join("?" * len(ids))
    rows = query(f"SELECT * FROM products WHERE id IN ({placeholders}) AND active = 1", ids)
    by_id = {str(r["id"]): r for r in rows}
    items, subtotal = [], 0.0
    changed = False
    for pid, qty in list(cart.items()):
        product = by_id.get(pid)
        if product is None:
            cart.pop(pid)
            changed = True
            continue
        line_total = product["price"] * qty
        subtotal += line_total
        items.append({"product": product, "quantity": qty, "line_total": line_total})
    if changed:
        save_cart(cart)
    return items, round(subtotal, 2)


def active_promotions():
    today = date.today().isoformat()
    return query(
        """SELECT * FROM promotions
           WHERE active = 1
             AND (starts_at IS NULL OR starts_at = '' OR starts_at <= ?)
             AND (ends_at IS NULL OR ends_at = '' OR ends_at >= ?)
           ORDER BY created_at DESC""",
        (today, today),
    )


def find_promotion(code):
    if not code:
        return None
    today = date.today().isoformat()
    return query(
        """SELECT * FROM promotions WHERE code = ? AND active = 1
             AND (starts_at IS NULL OR starts_at = '' OR starts_at <= ?)
             AND (ends_at IS NULL OR ends_at = '' OR ends_at >= ?)""",
        (code.strip(), today, today),
        one=True,
    )


def active_reps():
    return query("SELECT id, name, rep_code FROM users WHERE role = 'rep' AND active = 1 ORDER BY name")


# --------------------------------------------------------------------------- pages


@bp.route("/")
def home():
    featured = query(
        "SELECT p.*, c.name AS category_name FROM products p LEFT JOIN categories c ON c.id = p.category_id "
        "WHERE p.active = 1 AND p.is_featured = 1 ORDER BY p.created_at DESC LIMIT 8"
    )
    new_arrivals = query(
        "SELECT p.*, c.name AS category_name FROM products p LEFT JOIN categories c ON c.id = p.category_id "
        "WHERE p.active = 1 AND p.is_new = 1 ORDER BY p.created_at DESC LIMIT 8"
    )
    return render_template(
        "shop/home.html",
        featured=featured,
        new_arrivals=new_arrivals,
        promotions=active_promotions()[:3],
    )


@bp.route("/shop")
def products():
    q = request.args.get("q", "").strip()
    category_slug = request.args.get("category", "").strip()
    sort = request.args.get("sort", "newest")
    only_sale = request.args.get("sale") == "1"
    only_new = request.args.get("new") == "1"

    sql = ("SELECT p.*, c.name AS category_name, c.slug AS category_slug FROM products p "
           "LEFT JOIN categories c ON c.id = p.category_id WHERE p.active = 1")
    params = []
    category = None
    if category_slug:
        category = query("SELECT * FROM categories WHERE slug = ?", (category_slug,), one=True)
        if category is None:
            abort(404)
        sql += " AND p.category_id = ?"
        params.append(category["id"])
    if q:
        sql += " AND (p.name LIKE ? OR p.description LIKE ? OR c.name LIKE ?)"
        like = f"%{q}%"
        params += [like, like, like]
    if only_sale:
        sql += " AND p.compare_at_price IS NOT NULL AND p.compare_at_price > p.price"
    if only_new:
        sql += " AND p.is_new = 1"

    order = {
        "newest": "p.created_at DESC, p.id DESC",
        "price_asc": "p.price ASC",
        "price_desc": "p.price DESC",
        "name": "p.name ASC",
    }.get(sort, "p.created_at DESC")
    sql += f" ORDER BY {order}"

    items = query(sql, params)
    return render_template(
        "shop/products.html",
        products=items, q=q, category=category, sort=sort, only_sale=only_sale, only_new=only_new,
    )


@bp.route("/product/<slug>")
def product_detail(slug):
    product = query(
        "SELECT p.*, c.name AS category_name, c.slug AS category_slug FROM products p "
        "LEFT JOIN categories c ON c.id = p.category_id WHERE p.slug = ? AND p.active = 1",
        (slug,), one=True,
    )
    if product is None:
        abort(404)
    related = query(
        "SELECT * FROM products WHERE active = 1 AND category_id = ? AND id != ? ORDER BY RANDOM() LIMIT 4",
        (product["category_id"], product["id"]),
    )
    return render_template("shop/product.html", product=product, related=related)


@bp.route("/promotions")
def promotions():
    on_sale = query(
        "SELECT p.*, c.name AS category_name FROM products p LEFT JOIN categories c ON c.id = p.category_id "
        "WHERE p.active = 1 AND p.compare_at_price IS NOT NULL AND p.compare_at_price > p.price "
        "ORDER BY (p.compare_at_price - p.price) / p.compare_at_price DESC"
    )
    return render_template("shop/promotions.html", promotions=active_promotions(), on_sale=on_sale)


@bp.route("/delivery-and-returns")
def delivery():
    return render_template("shop/delivery.html")


@bp.route("/about")
def about():
    return render_template("shop/about.html")


@bp.route("/contact", methods=("GET", "POST"))
def contact():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        subject = request.form.get("subject", "").strip()
        body = request.form.get("message", "").strip()
        if not name or not email or not body:
            flash("Please fill in your name, email and message.", "error")
        else:
            execute(
                "INSERT INTO messages (name, email, phone, subject, body) VALUES (?,?,?,?,?)",
                (name, email, phone, subject, body),
            )
            flash("Thank you — your message has been sent. We'll get back to you shortly.", "success")
            return redirect(url_for("shop.contact"))
    return render_template("shop/contact.html")


# --------------------------------------------------------------------------- cart


@bp.route("/cart")
def cart():
    items, subtotal = cart_details()
    return render_template("shop/cart.html", items=items, subtotal=subtotal)


@bp.route("/cart/add", methods=("POST",))
def cart_add():
    product_id = parse_int(request.form.get("product_id"))
    qty = max(1, parse_int(request.form.get("quantity"), 1))
    product = query("SELECT * FROM products WHERE id = ? AND active = 1", (product_id,), one=True)
    if product is None:
        flash("That product is no longer available.", "error")
        return redirect(url_for("shop.products"))
    cart = get_cart()
    cart[str(product_id)] = cart.get(str(product_id), 0) + qty
    save_cart(cart)
    flash(f"Added {product['name']} to your cart.", "success")
    return redirect(request.form.get("next") or url_for("shop.cart"))


@bp.route("/cart/update", methods=("POST",))
def cart_update():
    cart = get_cart()
    for key, value in request.form.items():
        if key.startswith("qty_"):
            pid = key[4:]
            if pid in cart:
                cart[pid] = max(0, parse_int(value, 0))
    save_cart(cart)
    flash("Cart updated.", "info")
    return redirect(url_for("shop.cart"))


@bp.route("/cart/remove/<int:product_id>", methods=("POST",))
def cart_remove(product_id):
    cart = get_cart()
    cart.pop(str(product_id), None)
    save_cart(cart)
    return redirect(url_for("shop.cart"))


# --------------------------------------------------------------------------- checkout


@bp.route("/checkout", methods=("GET", "POST"))
def checkout():
    items, subtotal = cart_details()
    if not items:
        flash("Your cart is empty.", "info")
        return redirect(url_for("shop.products"))

    reps = active_reps()
    logged_in_rep = g.user if (g.user and g.user["role"] == "rep") else None
    promo_code = (request.form.get("promo_code") or session.get("promo_code") or "").strip()
    promotion = find_promotion(promo_code)
    discount = round(subtotal * promotion["discount_percent"] / 100, 2) if promotion else 0.0
    delivery_fee = current_app.config["DELIVERY_FEE"]
    total = round(subtotal - discount + delivery_fee, 2)

    form = {
        "customer_name": "", "customer_phone": "", "customer_email": "", "customer_address": "",
        "rep_id": str(logged_in_rep["id"]) if logged_in_rep else "", "rep_code": "",
        "payment_method": "rep", "notes": "", "promo_code": promo_code,
    }

    if request.method == "POST":
        for key in form:
            form[key] = request.form.get(key, form[key]).strip()
        if request.form.get("action") == "apply_promo":
            if promotion:
                session["promo_code"] = promotion["code"]
                flash(f"Promo code {promotion['code']} applied — {promotion['discount_percent']:g}% off.", "success")
            else:
                session.pop("promo_code", None)
                if promo_code:
                    flash("That promo code is not valid.", "error")
            return redirect(url_for("shop.checkout"))

        errors = []
        if not form["customer_name"]:
            errors.append("Please enter your full name.")
        if not form["customer_phone"]:
            errors.append("Please enter a phone number so your representative can reach you.")
        if not form["customer_address"]:
            errors.append("Please enter a delivery address.")

        # Every order must belong to a sales representative.
        rep = None
        if logged_in_rep:
            rep = logged_in_rep
        elif form["rep_code"]:
            rep = query("SELECT * FROM users WHERE rep_code = ? AND role = 'rep' AND active = 1",
                        (form["rep_code"].upper(),), one=True)
            if rep is None:
                errors.append("We couldn't find a representative with that code.")
        elif form["rep_id"]:
            rep = query("SELECT * FROM users WHERE id = ? AND role = 'rep' AND active = 1",
                        (parse_int(form["rep_id"]),), one=True)
            if rep is None:
                errors.append("Please choose a valid sales representative.")
        else:
            errors.append("Please choose your sales representative (or enter their code).")

        payment_method = form["payment_method"] if form["payment_method"] in ("online", "rep") else "rep"
        if payment_method == "online" and not current_app.config["ONLINE_PAYMENTS_ENABLED"]:
            payment_method = "rep"

        if promo_code and promotion is None:
            errors.append("That promo code is not valid.")

        if errors:
            for e in errors:
                flash(e, "error")
        else:
            db = get_db()
            order_number = generate_order_number()
            cur = db.execute(
                """INSERT INTO orders (order_number, customer_name, customer_phone, customer_email, customer_address,
                                       rep_id, payment_method, promo_code, subtotal, discount, total, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (order_number, form["customer_name"], form["customer_phone"], form["customer_email"],
                 form["customer_address"], rep["id"], payment_method,
                 promotion["code"] if promotion else None, subtotal, discount, total, form["notes"]),
            )
            order_id = cur.lastrowid
            for item in items:
                p = item["product"]
                db.execute(
                    "INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity) VALUES (?,?,?,?,?)",
                    (order_id, p["id"], p["name"], p["price"], item["quantity"]),
                )
                db.execute("UPDATE products SET stock = MAX(0, stock - ?) WHERE id = ?", (item["quantity"], p["id"]))
            db.execute(
                "INSERT INTO order_events (order_id, status, note, user_id) VALUES (?,?,?,?)",
                (order_id, "placed", f"Order placed via representative {rep['name']} ({rep['rep_code']}).",
                 g.user["id"] if g.user else None),
            )
            db.commit()
            session.pop("cart", None)
            session.pop("promo_code", None)
            if payment_method == "online":
                return redirect(url_for("shop.pay_online", order_number=order_number))
            return redirect(url_for("shop.order_confirmation", order_number=order_number))

    return render_template(
        "shop/checkout.html",
        items=items, subtotal=subtotal, discount=discount, delivery_fee=delivery_fee, total=total,
        promotion=promotion, reps=reps, logged_in_rep=logged_in_rep, form=form,
    )


@bp.route("/checkout/pay/<order_number>")
def pay_online(order_number):
    """Placeholder for a payment gateway redirect (PayFast, Yoco, etc.).

    Integration point: build the gateway payload from the order here, redirect the customer
    to the gateway, and mark `orders.payment_status = 'paid'` in the gateway's callback.
    """
    order = query("SELECT * FROM orders WHERE order_number = ?", (order_number,), one=True)
    if order is None:
        abort(404)
    return render_template("shop/pay_online.html", order=order)


@bp.route("/order/<order_number>")
def order_confirmation(order_number):
    order = query(
        "SELECT o.*, u.name AS rep_name, u.phone AS rep_phone, u.rep_code FROM orders o "
        "JOIN users u ON u.id = o.rep_id WHERE o.order_number = ?",
        (order_number,), one=True,
    )
    if order is None:
        abort(404)
    items = query("SELECT * FROM order_items WHERE order_id = ?", (order["id"],))
    return render_template("shop/order_confirmation.html", order=order, items=items)


@bp.route("/track", methods=("GET", "POST"))
def track():
    order, items, events = None, [], []
    number = (request.values.get("order_number") or "").strip().upper()
    phone = (request.values.get("phone") or "").strip()
    if number and phone:
        order = query(
            "SELECT o.*, u.name AS rep_name, u.phone AS rep_phone FROM orders o JOIN users u ON u.id = o.rep_id "
            "WHERE o.order_number = ? AND REPLACE(o.customer_phone, ' ', '') = REPLACE(?, ' ', '')",
            (number, phone), one=True,
        )
        if order is None:
            flash("We couldn't find an order with that number and phone.", "error")
        else:
            items = query("SELECT * FROM order_items WHERE order_id = ?", (order["id"],))
            events = query("SELECT * FROM order_events WHERE order_id = ? ORDER BY id", (order["id"],))
    return render_template("shop/track.html", order=order, items=items, events=events, number=number, phone=phone)


@bp.app_errorhandler(404)
def not_found(_e):
    return render_template("errors/404.html"), 404


@bp.app_errorhandler(403)
def forbidden(_e):
    return render_template("errors/403.html"), 403
