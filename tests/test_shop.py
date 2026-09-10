from app.db import query
from tests.conftest import login


def test_home_lists_categories_and_products(client):
    r = client.get("/")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Household" in html and "Personal Care" in html
    assert "Rose &amp; Shea Hand Cream" in html


def test_search_and_category_filter(client):
    r = client.get("/shop?q=candle")
    html = r.get_data(as_text=True)
    assert "Linen Scented Candle" in html and "Hand Cream" not in html

    r = client.get("/shop?category=jewellery")
    html = r.get_data(as_text=True)
    assert "Pearl Necklace" in html and "Shampoo" not in html

    assert client.get("/shop?category=does-not-exist").status_code == 404


def test_product_detail_page(client, app):
    with app.app_context():
        p = query("SELECT slug FROM products LIMIT 1", one=True)
    r = client.get(f"/product/{p['slug']}")
    assert r.status_code == 200
    assert "Add to cart" in r.get_data(as_text=True)


def test_cart_add_update_remove(client, app):
    with app.app_context():
        p = query("SELECT id, name, price FROM products WHERE stock > 0 AND name NOT LIKE '%&%' LIMIT 1", one=True)
    r = client.post("/cart/add", data={"product_id": p["id"], "quantity": 2}, follow_redirects=True)
    assert p["name"] in r.get_data(as_text=True)
    with client.session_transaction() as s:
        assert s["cart"] == {str(p["id"]): 2}

    client.post("/cart/update", data={f"qty_{p['id']}": 5})
    with client.session_transaction() as s:
        assert s["cart"][str(p["id"])] == 5

    client.post(f"/cart/remove/{p['id']}")
    with client.session_transaction() as s:
        assert s["cart"] == {}


def test_checkout_requires_a_representative(client, app):
    with app.app_context():
        p = query("SELECT id FROM products WHERE stock > 0 LIMIT 1", one=True)
    client.post("/cart/add", data={"product_id": p["id"], "quantity": 1})
    r = client.post("/checkout", data={
        "customer_name": "Ayanda M", "customer_phone": "0821234567", "customer_address": "12 Main Rd",
    })
    assert "choose your sales representative" in r.get_data(as_text=True)
    with app.app_context():
        assert query("SELECT COUNT(*) AS n FROM orders", one=True)["n"] == 0


def test_checkout_with_rep_code_and_promo(client, app):
    with app.app_context():
        p = query("SELECT id, price, stock FROM products WHERE stock > 3 LIMIT 1", one=True)
    client.post("/cart/add", data={"product_id": p["id"], "quantity": 2})
    r = client.post("/checkout", data={
        "customer_name": "Ayanda M", "customer_phone": "082 123 4567", "customer_address": "12 Main Rd, Soweto",
        "rep_code": "yr-ler01", "payment_method": "rep", "promo_code": "WELCOME10",
    }, follow_redirects=True)
    html = r.get_data(as_text=True)
    assert "Thank you, Ayanda" in html and "Lerato Sithole" in html

    with app.app_context():
        order = query("SELECT o.*, u.rep_code FROM orders o JOIN users u ON u.id = o.rep_id", one=True)
        assert order["rep_code"] == "YR-LER01"
        assert order["status"] == "placed"
        assert order["subtotal"] == round(p["price"] * 2, 2)
        assert order["discount"] == round(p["price"] * 2 * 0.10, 2)
        assert order["total"] == round(order["subtotal"] - order["discount"], 2)
        assert query("SELECT stock FROM products WHERE id = ?", (p["id"],), one=True)["stock"] == p["stock"] - 2
        assert query("SELECT COUNT(*) AS n FROM order_items WHERE order_id = ?", (order["id"],), one=True)["n"] == 1

    # Cart is cleared and the customer can track the order with number + phone.
    with client.session_transaction() as s:
        assert "cart" not in s
    r = client.get(f"/track?order_number={order['order_number']}&phone=0821234567")
    assert "Placed" in r.get_data(as_text=True)


def test_online_payment_falls_back_when_disabled(client, app):
    with app.app_context():
        p = query("SELECT id FROM products WHERE stock > 0 LIMIT 1", one=True)
        rep_id = query("SELECT id FROM users WHERE role = 'rep' LIMIT 1", one=True)["id"]
    client.post("/cart/add", data={"product_id": p["id"]})
    client.post("/checkout", data={
        "customer_name": "B", "customer_phone": "1", "customer_address": "x", "rep_id": rep_id, "payment_method": "online",
    })
    with app.app_context():
        assert query("SELECT payment_method FROM orders", one=True)["payment_method"] == "rep"


def test_contact_form_stores_message(client, app):
    r = client.post("/contact", data={"name": "Zee", "email": "z@example.com", "message": "Hi there"}, follow_redirects=True)
    assert "your message has been sent" in r.get_data(as_text=True)
    with app.app_context():
        assert query("SELECT name FROM messages", one=True)["name"] == "Zee"


def test_static_pages(client):
    for path in ("/promotions", "/delivery-and-returns", "/about", "/contact", "/track", "/cart"):
        assert client.get(path).status_code == 200, path
