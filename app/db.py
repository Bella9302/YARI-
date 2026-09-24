"""SQLite helpers: connection per request, schema creation, CLI commands."""
import sqlite3
from pathlib import Path

import click
from flask import current_app, g
from flask.cli import with_appcontext


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    schema = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    db.executescript(schema)
    db.commit()


def query(sql, params=(), one=False):
    cur = get_db().execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute(sql, params=()):
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    return cur.lastrowid


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Create the database tables (safe to run more than once)."""
    init_db()
    click.echo("Database initialised.")


@click.command("seed")
@with_appcontext
@click.option("--force", is_flag=True, help="Seed even if data already exists.")
def seed_command(force):
    """Load demo categories, products, promotions and user accounts."""
    from .seed import seed

    init_db()
    if seed(force=force):
        click.echo("Demo data loaded. See README for the demo logins.")
    else:
        click.echo("Database already has data; use --force to add demo data anyway.")


@click.command("create-owner")
@with_appcontext
@click.option("--name", prompt="Your full name")
@click.option("--email", prompt="Login email")
@click.password_option("--password", prompt="Password (at least 8 characters)")
def create_owner_command(name, email, password):
    """Create a store owner account, so you can log in without loading demo data."""
    from werkzeug.security import generate_password_hash

    init_db()
    name, email = name.strip(), email.strip()
    if len(password) < 8:
        raise click.ClickException("The password must be at least 8 characters.")
    if "@" not in email:
        raise click.ClickException("Please enter a valid email address.")
    if query("SELECT id FROM users WHERE email = ?", (email,), one=True):
        raise click.ClickException(f"An account with {email} already exists.")
    execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'owner')",
        (name, email, generate_password_hash(password)),
    )
    click.echo(f"Owner account created. Log in at /account/login with {email}.")


@click.command("users")
@with_appcontext
def list_users_command():
    """List every login account, so you can see which emails exist."""
    init_db()
    rows = query("SELECT name, email, role, rep_code, active FROM users ORDER BY role, name")
    if not rows:
        click.echo("There are no accounts yet. Create one with:  flask --app app create-owner")
        return
    labels = {"owner": "Owner", "seller": "Seller", "rep": "Sales rep"}
    for r in rows:
        extra = f"  code {r['rep_code']}" if r["rep_code"] else ""
        status = "" if r["active"] else "  (deactivated)"
        click.echo(f"{labels.get(r['role'], r['role']):<10} {r['email']:<35} {r['name']}{extra}{status}")


@click.command("reset-password")
@click.option("--email", prompt="Email of the account")
@click.password_option("--password", prompt="New password (at least 8 characters)")
@with_appcontext
def reset_password_command(email, password):
    """Set a new password for an account and make sure it is active."""
    from werkzeug.security import generate_password_hash

    init_db()
    email = email.strip()
    if len(password) < 8:
        raise click.ClickException("The password must be at least 8 characters.")
    user = query("SELECT id FROM users WHERE email = ?", (email,), one=True)
    if user is None:
        raise click.ClickException(
            f"No account uses {email}. See every account with:  flask --app app users"
        )
    execute("UPDATE users SET password_hash = ?, active = 1 WHERE id = ?",
            (generate_password_hash(password), user["id"]))
    click.echo(f"Password updated. Log in at /account/login with {email}.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_command)
    app.cli.add_command(create_owner_command)
    app.cli.add_command(list_users_command)
    app.cli.add_command(reset_password_command)
