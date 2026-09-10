"""SQLite helpers: connection per request, schema creation, CLI commands."""
import sqlite3
from pathlib import Path

import click
from flask import current_app, g


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
def init_db_command():
    """Create the database tables (safe to run more than once)."""
    init_db()
    click.echo("Database initialised.")


@click.command("seed")
@click.option("--force", is_flag=True, help="Seed even if data already exists.")
def seed_command(force):
    """Load demo categories, products, promotions and user accounts."""
    from .seed import seed

    init_db()
    if seed(force=force):
        click.echo("Demo data loaded. See README for the demo logins.")
    else:
        click.echo("Database already has data; use --force to add demo data anyway.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(seed_command)
