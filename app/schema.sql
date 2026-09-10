PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL,
    email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
    phone         TEXT,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('owner', 'seller', 'rep')),
    rep_code      TEXT    UNIQUE,
    business_name TEXT,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL UNIQUE,
    description TEXT,
    image       TEXT,
    sort_order  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS products (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT    NOT NULL,
    slug             TEXT    NOT NULL UNIQUE,
    description      TEXT,
    price            REAL    NOT NULL,
    compare_at_price REAL,
    category_id      INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    seller_id        INTEGER REFERENCES users(id) ON DELETE SET NULL,
    image            TEXT,
    stock            INTEGER NOT NULL DEFAULT 0,
    is_new           INTEGER NOT NULL DEFAULT 0,
    is_featured      INTEGER NOT NULL DEFAULT 0,
    active           INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS promotions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT    NOT NULL,
    description      TEXT,
    code             TEXT    UNIQUE COLLATE NOCASE,
    discount_percent REAL    NOT NULL DEFAULT 0,
    starts_at        TEXT,
    ends_at          TEXT,
    active           INTEGER NOT NULL DEFAULT 1,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number      TEXT    NOT NULL UNIQUE,
    customer_name     TEXT    NOT NULL,
    customer_phone    TEXT    NOT NULL,
    customer_email    TEXT,
    customer_address  TEXT    NOT NULL,
    rep_id            INTEGER NOT NULL REFERENCES users(id),
    seller_id         INTEGER REFERENCES users(id),
    status            TEXT    NOT NULL DEFAULT 'placed'
                      CHECK (status IN ('placed','sent_to_seller','processing','shipped','delivered','cancelled')),
    payment_method    TEXT    NOT NULL CHECK (payment_method IN ('online','rep')),
    payment_status    TEXT    NOT NULL DEFAULT 'unpaid' CHECK (payment_status IN ('unpaid','paid')),
    payment_reference TEXT,
    promo_code        TEXT,
    subtotal          REAL    NOT NULL,
    discount          REAL    NOT NULL DEFAULT 0,
    total             REAL    NOT NULL,
    notes             TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS order_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id     INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id   INTEGER REFERENCES products(id) ON DELETE SET NULL,
    product_name TEXT    NOT NULL,
    unit_price   REAL    NOT NULL,
    quantity     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS order_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    status     TEXT    NOT NULL,
    note       TEXT,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    phone      TEXT,
    subject    TEXT,
    body       TEXT NOT NULL,
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_orders_rep ON orders(rep_id);
CREATE INDEX IF NOT EXISTS idx_orders_seller ON orders(seller_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
