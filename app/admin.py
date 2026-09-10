"""Owner portal: products, categories, promotions, orders, users and messages."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from .auth import login_required
from .db import execute, get_db, query
from .utils import generate_rep_code, parse_int, parse_price, save_image, slugify

bp = Blueprint("admin", __name__, url_prefix="/owner")

ORDER_STATUSES = ["placed", "sent_to_seller", "processing", "shipped", "delivered", "cancelled"]


@bp.before_request
@login_required("owner")
def _guard():
    pass


# --------------------------------------------------------------------------- dashboard


@bp.route("/")
def dashboard():
    stats = {
        "new_orders": query("SELECT COUNT(*) AS n FROM orders WHERE status = 'placed'", one=True)["n"],
        "in_progress": query(
            "SELECT COUNT(*) AS n FROM orders WHERE status IN ('sent_to_seller','processing','shipped')", one=True)["n"],
        "delivered": query("SELECT COUNT(*) AS n FROM orders WHERE status = 'delivered'", one=True)["n"],
        "revenue": query("SELECT COALESCE(SUM(total),0) AS n FROM orders WHERE status != 'cancelled'", one=True)["n"],
        "products": query("SELECT COUNT(*) AS n FROM products WHERE active = 1", one=True)["n"],
        "low_stock": query("SELECT COUNT(*) AS n FROM products WHERE active = 1 AND stock <= 5", one=True)["n"],
        "unread_messages": query("SELECT COUNT(*) AS n FROM messages WHERE is_read = 0", one=True)["n"],
        "reps": query("SELECT COUNT(*) AS n FROM users WHERE role = 'rep' AND active = 1", one=True)["n"],
        "sellers": query("SELECT COUNT(*) AS n FROM users WHERE role = 'seller' AND active = 1", one=True)["n"],
    }
    recent = query(
        "SELECT o.*, r.name AS rep_name, s.name AS seller_name FROM orders o "
        "JOIN users r ON r.id = o.rep_id LEFT JOIN users s ON s.id = o.seller_id "
        "ORDER BY o.created_at DESC, o.id DESC LIMIT 8"
    )
    return render_template("admin/dashboard.html", stats=stats, recent=recent)


# --------------------------------------------------------------------------- orders


@bp.route("/orders")
def orders():
    status = request.args.get("status", "")
    rep_id = parse_int(request.args.get("rep"), 0)
    q = request.args.get("q", "").strip()
    sql = ("SELECT o.*, r.name AS rep_name, r.rep_code, s.name AS seller_name FROM orders o "
           "JOIN users r ON r.id = o.rep_id LEFT JOIN users s ON s.id = o.seller_id WHERE 1=1")
    params = []
    if status in ORDER_STATUSES:
        sql += " AND o.status = ?"
        params.append(status)
    if rep_id:
        sql += " AND o.rep_id = ?"
        params.append(rep_id)
    if q:
        sql += " AND (o.order_number LIKE ? OR o.customer_name LIKE ? OR o.customer_phone LIKE ?)"
        params += [f"%{q}%"] * 3
    sql += " ORDER BY o.created_at DESC, o.id DESC"
    reps = query("SELECT id, name FROM users WHERE role = 'rep' ORDER BY name")
    return render_template("admin/orders.html", orders=query(sql, params), status=status, rep_id=rep_id, q=q,
                           reps=reps, statuses=ORDER_STATUSES)


def _load_order(order_id):
    order = query(
        "SELECT o.*, r.name AS rep_name, r.rep_code, r.phone AS rep_phone, r.email AS rep_email, "
        "s.name AS seller_name, s.business_name AS seller_business FROM orders o "
        "JOIN users r ON r.id = o.rep_id LEFT JOIN users s ON s.id = o.seller_id WHERE o.id = ?",
        (order_id,), one=True,
    )
    if order is None:
        abort(404)
    return order


@bp.route("/orders/<int:order_id>")
def order_detail(order_id):
    order = _load_order(order_id)
    items = query(
        "SELECT oi.*, p.slug, p.image, u.name AS product_seller FROM order_items oi "
        "LEFT JOIN products p ON p.id = oi.product_id LEFT JOIN users u ON u.id = p.seller_id WHERE oi.order_id = ?",
        (order_id,),
    )
    events = query(
        "SELECT e.*, u.name AS user_name FROM order_events e LEFT JOIN users u ON u.id = e.user_id "
        "WHERE e.order_id = ? ORDER BY e.id", (order_id,),
    )
    sellers = query("SELECT id, name, business_name FROM users WHERE role = 'seller' AND active = 1 ORDER BY name")
    # Suggest the seller who supplies most of the items in this order.
    suggested = query(
        "SELECT p.seller_id, COUNT(*) AS n FROM order_items oi JOIN products p ON p.id = oi.product_id "
        "WHERE oi.order_id = ? AND p.seller_id IS NOT NULL GROUP BY p.seller_id ORDER BY n DESC LIMIT 1",
        (order_id,), one=True,
    )
    return render_template("admin/order_detail.html", order=order, items=items, events=events, sellers=sellers,
                           suggested_seller_id=suggested["seller_id"] if suggested else None, statuses=ORDER_STATUSES)


@bp.route("/orders/<int:order_id>/send", methods=("POST",))
def order_send(order_id):
    order = _load_order(order_id)
    seller_id = parse_int(request.form.get("seller_id"))
    seller = query("SELECT * FROM users WHERE id = ? AND role = 'seller' AND active = 1", (seller_id,), one=True)
    if seller is None:
        flash("Please choose a seller.", "error")
        return redirect(url_for("admin.order_detail", order_id=order_id))
    note = request.form.get("note", "").strip()
    db = get_db()
    db.execute("UPDATE orders SET seller_id = ?, status = 'sent_to_seller', updated_at = datetime('now') WHERE id = ?",
               (seller_id, order_id))
    db.execute("INSERT INTO order_events (order_id, status, note, user_id) VALUES (?,?,?,?)",
               (order_id, "sent_to_seller", note or f"Sent to {seller['name']} for fulfilment.", g.user["id"]))
    db.commit()
    flash(f"Order {order['order_number']} sent to {seller['name']}.", "success")
    return redirect(url_for("admin.order_detail", order_id=order_id))


@bp.route("/orders/<int:order_id>/status", methods=("POST",))
def order_status(order_id):
    _load_order(order_id)
    status = request.form.get("status")
    note = request.form.get("note", "").strip()
    if status not in ORDER_STATUSES:
        abort(400)
    db = get_db()
    db.execute("UPDATE orders SET status = ?, updated_at = datetime('now') WHERE id = ?", (status, order_id))
    db.execute("INSERT INTO order_events (order_id, status, note, user_id) VALUES (?,?,?,?)",
               (order_id, status, note or None, g.user["id"]))
    db.commit()
    flash("Order status updated.", "success")
    return redirect(url_for("admin.order_detail", order_id=order_id))


@bp.route("/orders/<int:order_id>/payment", methods=("POST",))
def order_payment(order_id):
    _load_order(order_id)
    paid = request.form.get("payment_status") == "paid"
    reference = request.form.get("payment_reference", "").strip()
    execute("UPDATE orders SET payment_status = ?, payment_reference = ?, updated_at = datetime('now') WHERE id = ?",
            ("paid" if paid else "unpaid", reference or None, order_id))
    flash("Payment details updated.", "success")
    return redirect(url_for("admin.order_detail", order_id=order_id))


# --------------------------------------------------------------------------- products


@bp.route("/products")
def products():
    q = request.args.get("q", "").strip()
    sql = ("SELECT p.*, c.name AS category_name, u.name AS seller_name FROM products p "
           "LEFT JOIN categories c ON c.id = p.category_id LEFT JOIN users u ON u.id = p.seller_id WHERE 1=1")
    params = []
    if q:
        sql += " AND p.name LIKE ?"
        params.append(f"%{q}%")
    sql += " ORDER BY p.active DESC, p.created_at DESC"
    return render_template("admin/products.html", products=query(sql, params), q=q)


def _product_form_context(product=None):
    return {
        "product": product,
        "categories": query("SELECT * FROM categories ORDER BY sort_order, name"),
        "sellers": query("SELECT id, name, business_name FROM users WHERE role = 'seller' ORDER BY name"),
    }


def _read_product_form():
    data = {
        "name": request.form.get("name", "").strip(),
        "description": request.form.get("description", "").strip(),
        "price": parse_price(request.form.get("price")),
        "compare_at_price": parse_price(request.form.get("compare_at_price")) or None,
        "category_id": parse_int(request.form.get("category_id")) or None,
        "seller_id": parse_int(request.form.get("seller_id")) or None,
        "stock": max(0, parse_int(request.form.get("stock"), 0)),
        "is_new": 1 if request.form.get("is_new") else 0,
        "is_featured": 1 if request.form.get("is_featured") else 0,
        "active": 1 if request.form.get("active") else 0,
    }
    errors = []
    if not data["name"]:
        errors.append("Product name is required.")
    if data["price"] is None:
        errors.append("Please enter a valid price.")
    if data["compare_at_price"] and data["price"] is not None and data["compare_at_price"] <= data["price"]:
        errors.append("The 'was' price must be higher than the selling price.")
    return data, errors


@bp.route("/products/new", methods=("GET", "POST"))
def product_new():
    if request.method == "POST":
        data, errors = _read_product_form()
        image = None
        try:
            image = save_image(request.files.get("image"))
        except ValueError as e:
            errors.append(str(e))
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            execute(
                """INSERT INTO products (name, slug, description, price, compare_at_price, category_id, seller_id,
                                         image, stock, is_new, is_featured, active)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (data["name"], slugify(data["name"], "products"), data["description"], data["price"],
                 data["compare_at_price"], data["category_id"], data["seller_id"], image, data["stock"],
                 data["is_new"], data["is_featured"], data["active"]),
            )
            flash(f"{data['name']} has been added to the shop.", "success")
            return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", **_product_form_context())


@bp.route("/products/<int:product_id>/edit", methods=("GET", "POST"))
def product_edit(product_id):
    product = query("SELECT * FROM products WHERE id = ?", (product_id,), one=True)
    if product is None:
        abort(404)
    if request.method == "POST":
        data, errors = _read_product_form()
        image = product["image"]
        try:
            new_image = save_image(request.files.get("image"))
            if new_image:
                image = new_image
        except ValueError as e:
            errors.append(str(e))
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            execute(
                """UPDATE products SET name=?, slug=?, description=?, price=?, compare_at_price=?, category_id=?,
                                       seller_id=?, image=?, stock=?, is_new=?, is_featured=?, active=? WHERE id=?""",
                (data["name"], slugify(data["name"], "products", exclude_id=product_id), data["description"],
                 data["price"], data["compare_at_price"], data["category_id"], data["seller_id"], image,
                 data["stock"], data["is_new"], data["is_featured"], data["active"], product_id),
            )
            flash("Product saved.", "success")
            return redirect(url_for("admin.products"))
    return render_template("admin/product_form.html", **_product_form_context(product))


@bp.route("/products/<int:product_id>/delete", methods=("POST",))
def product_delete(product_id):
    # Products referenced by orders are hidden rather than removed, so order history stays intact.
    used = query("SELECT id FROM order_items WHERE product_id = ? LIMIT 1", (product_id,), one=True)
    if used:
        execute("UPDATE products SET active = 0 WHERE id = ?", (product_id,))
        flash("Product hidden from the shop (it appears in past orders so it was not deleted).", "info")
    else:
        execute("DELETE FROM products WHERE id = ?", (product_id,))
        flash("Product deleted.", "info")
    return redirect(url_for("admin.products"))


# --------------------------------------------------------------------------- categories


@bp.route("/categories", methods=("GET", "POST"))
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        if not name:
            flash("Category name is required.", "error")
        else:
            execute("INSERT INTO categories (name, slug, description, sort_order) VALUES (?,?,?,?)",
                    (name, slugify(name, "categories"), description,
                     query("SELECT COALESCE(MAX(sort_order),0)+1 AS n FROM categories", one=True)["n"]))
            flash(f"Category '{name}' added.", "success")
        return redirect(url_for("admin.categories"))
    cats = query(
        "SELECT c.*, (SELECT COUNT(*) FROM products p WHERE p.category_id = c.id) AS product_count "
        "FROM categories c ORDER BY c.sort_order, c.name"
    )
    return render_template("admin/categories.html", categories=cats)


@bp.route("/categories/<int:category_id>/edit", methods=("POST",))
def category_edit(category_id):
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    if name:
        execute("UPDATE categories SET name = ?, slug = ?, description = ? WHERE id = ?",
                (name, slugify(name, "categories", exclude_id=category_id), description, category_id))
        flash("Category updated.", "success")
    return redirect(url_for("admin.categories"))


@bp.route("/categories/<int:category_id>/delete", methods=("POST",))
def category_delete(category_id):
    execute("DELETE FROM categories WHERE id = ?", (category_id,))
    flash("Category removed. Its products are now uncategorised.", "info")
    return redirect(url_for("admin.categories"))


# --------------------------------------------------------------------------- promotions


@bp.route("/promotions", methods=("GET", "POST"))
def promotions():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        code = request.form.get("code", "").strip().upper() or None
        pct = parse_price(request.form.get("discount_percent"), 0) or 0
        if not title:
            flash("Please give the promotion a title.", "error")
        elif code and query("SELECT id FROM promotions WHERE code = ?", (code,), one=True):
            flash("That promo code already exists.", "error")
        elif not 0 <= pct <= 100:
            flash("Discount must be between 0 and 100 percent.", "error")
        else:
            execute(
                "INSERT INTO promotions (title, description, code, discount_percent, starts_at, ends_at) VALUES (?,?,?,?,?,?)",
                (title, request.form.get("description", "").strip(), code, pct,
                 request.form.get("starts_at") or None, request.form.get("ends_at") or None),
            )
            flash("Promotion created.", "success")
        return redirect(url_for("admin.promotions"))
    return render_template("admin/promotions.html",
                           promotions=query("SELECT * FROM promotions ORDER BY active DESC, created_at DESC"))


@bp.route("/promotions/<int:promo_id>/toggle", methods=("POST",))
def promotion_toggle(promo_id):
    execute("UPDATE promotions SET active = 1 - active WHERE id = ?", (promo_id,))
    return redirect(url_for("admin.promotions"))


@bp.route("/promotions/<int:promo_id>/delete", methods=("POST",))
def promotion_delete(promo_id):
    execute("DELETE FROM promotions WHERE id = ?", (promo_id,))
    flash("Promotion deleted.", "info")
    return redirect(url_for("admin.promotions"))


# --------------------------------------------------------------------------- users


@bp.route("/users")
def users():
    people = query(
        "SELECT u.*, (SELECT COUNT(*) FROM orders o WHERE o.rep_id = u.id OR o.seller_id = u.id) AS order_count "
        "FROM users u ORDER BY u.role, u.name"
    )
    return render_template("admin/users.html", users=people)


@bp.route("/users/new", methods=("GET", "POST"))
def user_new():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        role = request.form.get("role")
        password = request.form.get("password", "")
        business = request.form.get("business_name", "").strip() or None
        errors = []
        if not name or not email:
            errors.append("Name and email are required.")
        if role not in ("seller", "rep", "owner"):
            errors.append("Please choose a role.")
        if len(password) < 8:
            errors.append("Password must be at least 8 characters.")
        if query("SELECT id FROM users WHERE email = ?", (email,), one=True):
            errors.append("An account with that email already exists.")
        if errors:
            for e in errors:
                flash(e, "error")
        else:
            rep_code = generate_rep_code() if role == "rep" else None
            execute(
                "INSERT INTO users (name, email, phone, password_hash, role, rep_code, business_name) VALUES (?,?,?,?,?,?,?)",
                (name, email, phone, generate_password_hash(password), role, rep_code, business),
            )
            msg = f"Account created for {name}."
            if rep_code:
                msg += f" Their unique representative code is {rep_code}."
            flash(msg, "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html", user=None)


@bp.route("/users/<int:user_id>/edit", methods=("GET", "POST"))
def user_edit(user_id):
    user = query("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    if user is None:
        abort(404)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        business = request.form.get("business_name", "").strip() or None
        password = request.form.get("password", "")
        active = 1 if request.form.get("active") else 0
        if user_id == g.user["id"]:
            active = 1
        if not name or not email:
            flash("Name and email are required.", "error")
        elif query("SELECT id FROM users WHERE email = ? AND id != ?", (email, user_id), one=True):
            flash("Another account already uses that email.", "error")
        elif password and len(password) < 8:
            flash("Password must be at least 8 characters.", "error")
        else:
            execute("UPDATE users SET name=?, email=?, phone=?, business_name=?, active=? WHERE id=?",
                    (name, email, phone, business, active, user_id))
            if password:
                execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(password), user_id))
            flash("Account updated.", "success")
            return redirect(url_for("admin.users"))
    return render_template("admin/user_form.html", user=user)


# --------------------------------------------------------------------------- messages


@bp.route("/messages")
def messages():
    return render_template("admin/messages.html",
                           messages=query("SELECT * FROM messages ORDER BY is_read, created_at DESC"))


@bp.route("/messages/<int:message_id>/read", methods=("POST",))
def message_read(message_id):
    execute("UPDATE messages SET is_read = 1 - is_read WHERE id = ?", (message_id,))
    return redirect(url_for("admin.messages"))


@bp.route("/messages/<int:message_id>/delete", methods=("POST",))
def message_delete(message_id):
    execute("DELETE FROM messages WHERE id = ?", (message_id,))
    return redirect(url_for("admin.messages"))
