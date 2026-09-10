"""Login / logout and role-based access control for owner, sellers and sales reps."""
from functools import wraps

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from .db import query

bp = Blueprint("auth", __name__, url_prefix="/account")

ROLE_HOME = {
    "owner": "admin.dashboard",
    "seller": "seller.dashboard",
    "rep": "rep.dashboard",
}


def load_current_user():
    user_id = session.get("user_id")
    g.user = None
    if user_id:
        user = query("SELECT * FROM users WHERE id = ? AND active = 1", (user_id,), one=True)
        g.user = user
        if user is None:
            session.pop("user_id", None)


def login_required(*roles):
    """Require a logged-in user, optionally restricted to the given roles."""

    def decorator(view):
        @wraps(view)
        def wrapped(**kwargs):
            if g.user is None:
                flash("Please log in to continue.", "info")
                return redirect(url_for("auth.login", next=request.path))
            if roles and g.user["role"] not in roles:
                abort(403)
            return view(**kwargs)

        return wrapped

    return decorator


@bp.route("/login", methods=("GET", "POST"))
def login():
    if g.user is not None:
        return redirect(url_for(ROLE_HOME[g.user["role"]]))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = query("SELECT * FROM users WHERE email = ?", (email,), one=True)
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Incorrect email or password.", "error")
        elif not user["active"]:
            flash("This account has been deactivated. Please contact the store owner.", "error")
        else:
            session["user_id"] = user["id"]
            flash(f"Welcome back, {user['name'].split()[0]}.", "success")
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return redirect(url_for(ROLE_HOME[user["role"]]))

    return render_template("auth/login.html")


@bp.route("/logout", methods=("POST",))
def logout():
    session.pop("user_id", None)
    flash("You have been logged out.", "info")
    return redirect(url_for("shop.home"))


@bp.route("/")
def account_home():
    if g.user is None:
        return redirect(url_for("auth.login"))
    return redirect(url_for(ROLE_HOME[g.user["role"]]))
