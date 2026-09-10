import io

from app.db import query
from tests.conftest import login


def place_order(client, app, rep_code="YR-LER01"):
    with app.app_context():
        p = query("SELECT id FROM products WHERE stock > 0 AND seller_id IS NOT NULL LIMIT 1", one=True)
    client.post("/cart/add", data={"product_id": p["id"], "quantity": 1})
    client.post("/checkout", data={
        "customer_name": "Cust", "customer_phone": "0800000000", "customer_address": "1 Road", "rep_code": rep_code,
    })
    with app.app_context():
        return query("SELECT * FROM orders ORDER BY id DESC LIMIT 1", one=True)


def test_login_logout_and_role_redirects(client):
    assert client.get("/owner/").status_code == 302  # anonymous → login
    r = login(client, "owner@yari.co.za", "wrong")
    assert "Incorrect email or password" in r.get_data(as_text=True)
    r = login(client, "owner@yari.co.za")
    assert "Dashboard" in r.get_data(as_text=True)
    assert client.get("/seller/").status_code == 403
    assert client.get("/rep/").status_code == 403
    client.post("/account/logout")
    assert client.get("/owner/").status_code == 302


def test_full_order_flow_owner_sends_to_seller_and_seller_fulfils(client, app):
    order = place_order(client, app)

    # Owner sees the new order and sends it to a seller.
    login(client, "owner@yari.co.za")
    r = client.get("/owner/orders?status=placed")
    assert order["order_number"] in r.get_data(as_text=True)
    with app.app_context():
        seller = query("SELECT id FROM users WHERE email = 'naledi@yari.co.za'", one=True)
    r = client.post(f"/owner/orders/{order['id']}/send", data={"seller_id": seller["id"], "note": "Urgent"}, follow_redirects=True)
    assert "sent to Naledi" in r.get_data(as_text=True)
    with app.app_context():
        o = query("SELECT * FROM orders WHERE id = ?", (order["id"],), one=True)
        assert o["status"] == "sent_to_seller" and o["seller_id"] == seller["id"]
    client.post("/account/logout")

    # Another seller cannot see it; the assigned seller can and updates status.
    login(client, "thabo@yari.co.za")
    assert client.get(f"/seller/orders/{order['id']}").status_code == 404
    client.post("/account/logout")

    login(client, "naledi@yari.co.za")
    r = client.get("/seller/")
    assert order["order_number"] in r.get_data(as_text=True)
    client.post(f"/seller/orders/{order['id']}/status", data={"status": "shipped", "note": "Courier collected"})
    with app.app_context():
        assert query("SELECT status FROM orders WHERE id = ?", (order["id"],), one=True)["status"] == "shipped"
        events = query("SELECT status FROM order_events WHERE order_id = ? ORDER BY id", (order["id"],))
        assert [e["status"] for e in events] == ["placed", "sent_to_seller", "shipped"]
    client.post("/account/logout")

    # The rep sees the order, records payment with their code.
    login(client, "lerato@yari.co.za")
    r = client.get("/rep/")
    assert order["order_number"] in r.get_data(as_text=True)
    client.post(f"/rep/orders/{order['id']}/payment", data={"payment_reference": ""})
    with app.app_context():
        o = query("SELECT payment_status, payment_reference FROM orders WHERE id = ?", (order["id"],), one=True)
        assert o["payment_status"] == "paid" and o["payment_reference"] == "YR-LER01"

    # A different rep cannot open it.
    client.post("/account/logout")
    login(client, "sipho@yari.co.za")
    assert client.get(f"/rep/orders/{order['id']}").status_code == 404


def test_logged_in_rep_checkout_is_linked_automatically(client, app):
    login(client, "sipho@yari.co.za")
    with app.app_context():
        p = query("SELECT id FROM products WHERE stock > 0 LIMIT 1", one=True)
    client.post("/cart/add", data={"product_id": p["id"]})
    client.post("/checkout", data={"customer_name": "C", "customer_phone": "1", "customer_address": "a"})
    with app.app_context():
        o = query("SELECT o.*, u.email FROM orders o JOIN users u ON u.id = o.rep_id", one=True)
        assert o["email"] == "sipho@yari.co.za"


def test_owner_can_add_edit_and_hide_products(client, app):
    login(client, "owner@yari.co.za")
    with app.app_context():
        cat = query("SELECT id FROM categories LIMIT 1", one=True)
    data = {
        "name": "Test Lamp", "description": "Warm light", "price": "349.99", "compare_at_price": "",
        "category_id": cat["id"], "seller_id": "", "stock": "7", "is_new": "on", "active": "on",
        "image": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 32), "lamp.png"),
    }
    r = client.post("/owner/products/new", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert "has been added" in r.get_data(as_text=True)
    with app.app_context():
        p = query("SELECT * FROM products WHERE name = 'Test Lamp'", one=True)
        assert p["slug"] == "test-lamp" and p["price"] == 349.99 and p["image"].startswith("/static/uploads/")

    # Bad image type is rejected.
    data["name"], data["image"] = "Bad", (io.BytesIO(b"x"), "evil.exe")
    r = client.post("/owner/products/new", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert "PNG, JPG" in r.get_data(as_text=True)

    # Public shop shows it; hiding removes it.
    assert "Test Lamp" in client.get("/shop?q=lamp").get_data(as_text=True)
    client.post(f"/owner/products/{p['id']}/edit", data={"name": "Test Lamp", "price": "349.99", "stock": "7"})
    assert "Test Lamp" not in client.get("/shop?q=lamp").get_data(as_text=True)
    client.post(f"/owner/products/{p['id']}/delete")
    with app.app_context():
        assert query("SELECT id FROM products WHERE id = ?", (p["id"],), one=True) is None


def test_owner_creates_rep_with_unique_code(client, app):
    login(client, "owner@yari.co.za")
    r = client.post("/owner/users/new", data={
        "name": "New Rep", "email": "new@yari.co.za", "role": "rep", "password": "supersecret",
    }, follow_redirects=True)
    assert "unique representative code is YR-" in r.get_data(as_text=True)
    with app.app_context():
        u = query("SELECT rep_code, active FROM users WHERE email = 'new@yari.co.za'", one=True)
        assert u["rep_code"].startswith("YR-") and u["active"] == 1
    client.post("/account/logout")
    assert "Welcome back" in login(client, "new@yari.co.za", "supersecret").get_data(as_text=True)


def test_owner_promotion_and_category_management(client, app):
    login(client, "owner@yari.co.za")
    client.post("/owner/promotions", data={"title": "Flash", "code": "flash20", "discount_percent": "20"})
    client.post("/owner/categories", data={"name": "Kitchen", "description": "Cook"})
    with app.app_context():
        assert query("SELECT code FROM promotions WHERE code = 'FLASH20'", one=True) is not None
        assert query("SELECT slug FROM categories WHERE name = 'Kitchen'", one=True)["slug"] == "kitchen"
    assert "Kitchen" in client.get("/").get_data(as_text=True)
