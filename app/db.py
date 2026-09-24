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


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_command)
    app.cli.add_command(create_owner_command)
