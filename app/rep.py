"""Sales representative portal: their unique code, orders they placed, and payment recording."""
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .auth import login_required
from .db import execute, query

bp = Blueprint("rep", __name__, url_prefix="/rep")


@bp.before_request
@login_required("rep")
def _guard():
    pass


def _my_order(order_id):
    order = query(
        "SELECT o.*, s.name AS seller_name, s.business_name AS seller_business FROM orders o "
        "LEFT JOIN users s ON s.id = o.seller_id WHERE o.id = ? AND o.rep_id = ?",
        (order_id, g.user["id"]), one=True,
    )
    if order is None:
        abort(404)
    return order


@bp.route("/")
def dashboard():
    status = request.args.get("status", "")
    sql = ("SELECT o.*, s.name AS seller_name FROM orders o LEFT JOIN users s ON s.id = o.seller_id "
           "WHERE o.rep_id = ?")
    params = [g.user["id"]]
    if status:
        sql += " AND o.status = ?"
        params.append(status)
    sql += " ORDER BY o.created_at DESC, o.id DESC"
    totals = query(
        "SELECT COUNT(*) AS orders, COALESCE(SUM(total),0) AS sales, "
        "COALESCE(SUM(CASE WHEN payment_status='unpaid' AND status != 'cancelled' THEN total ELSE 0 END),0) AS outstanding "
        "FROM orders WHERE rep_id = ?", (g.user["id"],), one=True,
    )
    return render_template("rep/dashboard.html", orders=query(sql, params), status=status, totals=totals)


@bp.route("/orders/<int:order_id>")
def order_detail(order_id):
    order = _my_order(order_id)
    items = query("SELECT oi.*, p.image, p.slug FROM order_items oi LEFT JOIN products p ON p.id = oi.product_id "
                  "WHERE oi.order_id = ?", (order_id,))
    events = query("SELECT e.*, u.name AS user_name FROM order_events e LEFT JOIN users u ON u.id = e.user_id "
                   "WHERE e.order_id = ? ORDER BY e.id", (order_id,))
    return render_template("rep/order_detail.html", order=order, items=items, events=events)


@bp.route("/orders/<int:order_id>/payment", methods=("POST",))
def order_payment(order_id):
    """The rep collected the money and made an EFT using their unique code as reference."""
    _my_order(order_id)
    reference = request.form.get("payment_reference", "").strip() or g.user["rep_code"]
    execute("UPDATE orders SET payment_status = 'paid', payment_reference = ?, updated_at = datetime('now') WHERE id = ?",
            (reference, order_id))
    execute("INSERT INTO order_events (order_id, status, note, user_id) VALUES (?,?,?,?)",
            (order_id, "payment", f"Payment received — EFT reference {reference}.", g.user["id"]))
    flash("Payment recorded. Thank you!", "success")
    return redirect(url_for("rep.order_detail", order_id=order_id))
