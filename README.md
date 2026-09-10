# YARI Lifestyle — Online Store

A modern, mobile-friendly e-commerce website for lifestyle, household and personal care
products, built around an Avon-style sales model:

- **Customers** browse, search, shop by category, add to cart and check out.
  Every order is placed through a **sales representative** (chosen at checkout, or via the rep's unique code).
- **Sales representatives** log in to see the orders placed through them, collect payment,
  and confirm the EFT using their unique code as reference.
- The **store owner** uploads products, manages categories, promotions and accounts,
  reviews every order placed by representatives and **sends it to a seller**.
- **Sellers** log in to see the orders sent to them and update progress
  (being prepared → on its way → delivered).

The site uses clean white/neutral backgrounds, is fully responsive, and works well from a phone.

## Quick start

Requirements: Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

flask --app app seed               # creates the database and loads demo data
python run.py                      # open http://localhost:5000
```

### Demo logins (password for all: `password123`)

| Role  | Email               | Where they land |
|-------|---------------------|-----------------|
| Owner | owner@yari.co.za    | `/owner/`       |
| Seller| naledi@yari.co.za   | `/seller/`      |
| Seller| thabo@yari.co.za    | `/seller/`      |
| Rep   | lerato@yari.co.za (code `YR-LER01`) | `/rep/` |
| Rep   | sipho@yari.co.za  (code `YR-SIP02`) | `/rep/` |

To start with an empty catalogue instead, run `flask --app app init-db` and create your
owner account by inserting it via the seed command, then delete the demo data from the owner portal.
(The simplest path: run `seed`, log in as the owner, change the owner's email/password
under *Sellers & reps*, and delete the demo products/accounts you don't need.)

## How an order flows

1. Customer adds products to the cart and checks out, choosing a representative (or entering the rep code).
   A logged-in rep placing an order for a customer is linked automatically.
2. The order appears as **Placed — awaiting owner** on the owner dashboard.
3. The owner opens the order and **sends it to a seller** (the seller that supplies the products is suggested).
4. The seller sees it under **New to prepare** and updates it to *Being prepared*, *On its way* and *Delivered*.
5. The representative collects payment and clicks **Confirm payment received**, which records the EFT reference.
6. Customers can follow progress on **Track an order** using the order number and their phone number.

## Features

- Product catalogue with search, category filter, "New in", "On sale", and sorting.
- Product detail pages with related products.
- Session cart, promo codes (percentage discounts with optional start/end dates).
- Checkout: representative selection, payment method (pay the representative, or online when enabled), order notes.
- Promotions page, delivery & returns, about/how-it-works, contact form (messages land in the owner inbox).
- Owner portal: dashboard stats, orders (filter by status/rep/search), send to seller, payment tracking,
  status changes with history, product CRUD with image upload, categories, promotions, seller/rep accounts, messages.
- Seller portal: assigned orders, status updates, own product list.
- Rep portal: unique code, orders, outstanding payments, payment confirmation, shareable tracking link.

## Configuration

Set these environment variables in production (all optional):

| Variable | Purpose | Default |
|----------|---------|---------|
| `SECRET_KEY` | Session signing key — **set a long random value** | dev value |
| `DATABASE_PATH` | SQLite file location | `instance/yari.sqlite` |
| `BUSINESS_NAME`, `BUSINESS_EMAIL`, `BUSINESS_PHONE`, `BUSINESS_WHATSAPP`, `BUSINESS_ADDRESS` | Shown in header/footer/contact page | placeholders |
| `CURRENCY_SYMBOL` | Price prefix | `R` |
| `DELIVERY_FEE` | Flat delivery fee added at checkout | `0` |
| `ONLINE_PAYMENTS_ENABLED` | `true` to offer the "Pay online" option | `false` |
| `SHOW_DEMO_LOGINS` | `false` to hide the demo account hints on the login page | `true` |

### Adding online payments

`app/shop.py` → `pay_online()` is the integration point. Build the gateway request from the order,
redirect the customer to the gateway (PayFast, Yoco, Ozow, …), and in the gateway's callback set
`orders.payment_status = 'paid'` with the gateway reference. Then set `ONLINE_PAYMENTS_ENABLED=true`.

## Deploying

The app is a standard WSGI app (`wsgi:app`) with a `Procfile`, so it runs on Render, Railway,
Fly.io, PythonAnywhere or any VPS:

```bash
gunicorn wsgi:app --bind 0.0.0.0:8000
```

Persist `instance/` (the SQLite database) and `app/static/uploads/` (product images) on a
disk that survives deploys. Set `SECRET_KEY` before going live, and change the demo passwords.

## Tests

```bash
pytest
```

## Project layout

```
app/
  __init__.py     app factory, config, template filters
  schema.sql      database tables
  db.py           SQLite helpers + `flask init-db` / `flask seed`
  seed.py         demo data
  auth.py         login/logout, role guard
  shop.py         storefront, cart, checkout, tracking, contact
  admin.py        owner portal
  seller.py       seller portal
  rep.py          sales-rep portal
  templates/      Jinja templates (shop/, admin/, seller/, rep/, auth/)
  static/         css, js, images, uploads/
tests/            pytest suite
```
