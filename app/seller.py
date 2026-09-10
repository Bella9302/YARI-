"""Seller portal: orders the owner has sent to this seller, and the seller's own products."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .auth import login_required
from .db import get_db, query

bp = Blueprint("seller", __name__, url_prefix="/seller")

SELLER_STATUSES = ["processing", "shipped", "delivered"]


@bp.before_request
@login_required("seller")
def _guard():
    pass


def _my_order(order_id):
    order = query(
        "SELECT o.*, r.name AS rep_name, r.phone AS rep_phone, r.rep_code FROM orders o "
        "JOIN users r ON r.id = o.rep_id WHERE o.id = ? AND o.seller_id = ?",
        (order_id, g.user["id"]), one=True,
    )
    if order is None:
        abort(404)
    return order


@bp.route("/")
def dashboard():
    counts = {
        s: query("SELECT COUNT(*) AS n FROM orders WHERE seller_id = ? AND status = ?", (g.user["id"], s), one=True)["n"]
        for s in ("sent_to_seller", "processing", "shipped", "delivered")
    }
    status = request.args.get("status", "")
    sql = ("SELECT o.*, r.name AS rep_name FROM orders o JOIN users r ON r.id = o.rep_id "
           "WHERE o.seller_id = ?")
    params = [g.user["id"]]
    if status in ("sent_to_seller", "processing", "shipped", "delivered", "cancelled"):
        sql += " AND o.status = ?"
        params.append(status)
    sql += " ORDER BY CASE o.status WHEN 'sent_to_seller' THEN 0 WHEN 'processing' THEN 1 WHEN 'shipped' THEN 2 ELSE 3 END, o.updated_at DESC"
    products = query("SELECT * FROM products WHERE seller_id = ? ORDER BY active DESC, name", (g.user["id"],))
    return render_template("seller/dashboard.html", orders=query(sql, params), counts=counts, status=status,
                           products=products)


@bp.route("/orders/<int:order_id>")
def order_detail(order_id):
    order = _my_order(order_id)
    items = query("SELECT oi.*, p.image, p.slug FROM order_items oi LEFT JOIN products p ON p.id = oi.product_id "
                  "WHERE oi.order_id = ?", (order_id,))
    events = query("SELECT e.*, u.name AS user_name FROM order_events e LEFT JOIN users u ON u.id = e.user_id "
                   "WHERE e.order_id = ? ORDER BY e.id", (order_id,))
    return render_template("seller/order_detail.html", order=order, items=items, events=events,
                           statuses=SELLER_STATUSES)


@bp.route("/orders/<int:order_id>/status", methods=("POST",))
def order_status(order_id):
    order = _my_order(order_id)
    status = request.form.get("status")
    note = request.form.get("note", "").strip()
    if status not in SELLER_STATUSES or order["status"] == "cancelled":
        abort(400)
    db = get_db()
    db.execute("UPDATE orders SET status = ?, updated_at = datetime('now') WHERE id = ?", (status, order_id))
    db.execute("INSERT INTO order_events (order_id, status, note, user_id) VALUES (?,?,?,?)",
               (order_id, status, note or None, g.user["id"]))
    db.commit()
    flash("Order updated — the owner and representative can see the new status.", "success")
    return redirect(url_for("seller.order_detail", order_id=order_id))
