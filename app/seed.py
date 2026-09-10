"""Demo data so the store looks alive the first time it is opened."""
from werkzeug.security import generate_password_hash

from .db import execute, query
from .utils import slugify

DEMO_PASSWORD = "password123"

USERS = [
    ("Store Owner", "owner@yari.co.za", "owner", None, None),
    ("Naledi Dlamini", "naledi@yari.co.za", "seller", None, "Naledi Home & Living"),
    ("Thabo Mokoena", "thabo@yari.co.za", "seller", None, "Mokoena Beauty Supplies"),
    ("Lerato Sithole", "lerato@yari.co.za", "rep", "YR-LER01", None),
    ("Sipho Ndlovu", "sipho@yari.co.za", "rep", "YR-SIP02", None),
]

CATEGORIES = [
    ("Household", "Everyday essentials that make a house feel like home."),
    ("Personal Care", "Skin, hair and body care you can trust."),
    ("Clothing", "Comfortable, elegant pieces for every day."),
    ("Jewellery", "Timeless accessories with a modern touch."),
    ("Fragrance", "Signature scents for him and her."),
]

# name, category, price, compare_at, stock, is_new, is_featured, seller_email, description
PRODUCTS = [
    ("Rose & Shea Hand Cream", "Personal Care", 89.00, 119.00, 40, 1, 1, "thabo@yari.co.za",
     "A rich, fast-absorbing hand cream with rose extract and shea butter. Leaves hands soft without any greasy feel."),
    ("Vitamin C Glow Serum", "Personal Care", 249.00, None, 25, 1, 1, "thabo@yari.co.za",
     "Brightening daily serum with 10% vitamin C and hyaluronic acid for a fresh, even complexion."),
    ("Coconut Repair Shampoo 400ml", "Personal Care", 129.00, None, 60, 0, 0, "thabo@yari.co.za",
     "Gentle sulphate-free shampoo that restores shine and softness to dry, damaged hair."),
    ("Charcoal Body Wash 500ml", "Personal Care", 99.00, 129.00, 50, 0, 1, "thabo@yari.co.za",
     "Deep-cleansing body wash with activated charcoal and a clean cedar scent."),
    ("Bamboo Kitchen Towel Set (3)", "Household", 159.00, None, 30, 0, 1, "naledi@yari.co.za",
     "Three ultra-absorbent bamboo towels in warm neutral tones. Machine washable and quick drying."),
    ("Ceramic Soap Dispenser", "Household", 189.00, 229.00, 20, 1, 0, "naledi@yari.co.za",
     "Matte ceramic dispenser with a brushed-gold pump. Fits perfectly in kitchens and bathrooms."),
    ("Linen Scented Candle 220g", "Household", 219.00, None, 35, 1, 1, "naledi@yari.co.za",
     "Hand-poured soy candle with notes of fresh linen and white musk. Around 45 hours of burn time."),
    ("Microfibre Cleaning Cloths (6)", "Household", 79.00, None, 100, 0, 0, "naledi@yari.co.za",
     "Streak-free cloths for glass, counters and appliances. Reusable hundreds of times."),
    ("Glass Storage Jars Set (4)", "Household", 299.00, 349.00, 15, 0, 0, "naledi@yari.co.za",
     "Airtight borosilicate glass jars with bamboo lids for pantry staples."),
    ("Everyday Cotton T-Shirt", "Clothing", 199.00, None, 45, 0, 1, None,
     "Soft 100% cotton tee with a relaxed fit. Available in oat, black and sage. Sizes S–XXL."),
    ("Wide-Leg Linen Trousers", "Clothing", 449.00, 549.00, 20, 1, 0, None,
     "Breathable linen trousers with an elasticated waist and a flattering wide leg."),
    ("Knitted Lounge Cardigan", "Clothing", 399.00, None, 18, 1, 0, None,
     "Cosy oversized cardigan in a chunky rib knit. Perfect for cool evenings."),
    ("Gold-Plated Hoop Earrings", "Jewellery", 179.00, None, 50, 0, 1, None,
     "Lightweight 18k gold-plated hoops with a hypoallergenic post. Tarnish resistant."),
    ("Freshwater Pearl Necklace", "Jewellery", 349.00, 429.00, 12, 1, 1, None,
     "Delicate freshwater pearls on a gold-plated chain. An elegant gift for any occasion."),
    ("Layered Chain Bracelet", "Jewellery", 149.00, None, 40, 0, 0, None,
     "Three fine chains in one adjustable bracelet. Waterproof stainless steel."),
    ("Amber Woods Eau de Parfum 50ml", "Fragrance", 399.00, None, 22, 1, 1, "thabo@yari.co.za",
     "Warm amber, sandalwood and vanilla. A long-lasting signature scent for evenings."),
    ("Citrus Bloom Body Mist 200ml", "Fragrance", 149.00, 179.00, 40, 0, 0, "thabo@yari.co.za",
     "A light, refreshing mist with grapefruit and orange blossom. Ideal for daytime."),
    ("Ocean Breeze Aftershave Balm", "Fragrance", 169.00, None, 30, 0, 0, "thabo@yari.co.za",
     "Soothing alcohol-free balm that calms the skin with a crisp marine scent."),
]

PROMOTIONS = [
    ("Welcome offer — 10% off your first order", "Use the code below at checkout and save on everything in store.",
     "WELCOME10", 10),
    ("Personal Care Week", "15% off all skin, hair and body care until the end of the month.",
     "CARE15", 15),
]


def seed(force=False):
    if not force and query("SELECT id FROM users LIMIT 1", one=True):
        return False

    pw = generate_password_hash(DEMO_PASSWORD)
    for name, email, role, rep_code, business in USERS:
        if query("SELECT id FROM users WHERE email = ?", (email,), one=True):
            continue
        execute(
            "INSERT INTO users (name, email, phone, password_hash, role, rep_code, business_name) VALUES (?,?,?,?,?,?,?)",
            (name, email, "+27 82 000 0000", pw, role, rep_code, business),
        )

    for i, (name, desc) in enumerate(CATEGORIES):
        if query("SELECT id FROM categories WHERE name = ?", (name,), one=True):
            continue
        execute(
            "INSERT INTO categories (name, slug, description, sort_order, image) VALUES (?,?,?,?,?)",
            (name, slugify(name, "categories"), desc, i, f"/static/img/categories/{slugify(name)}.svg"),
        )

    for name, cat, price, compare, stock, is_new, featured, seller_email, desc in PRODUCTS:
        if query("SELECT id FROM products WHERE name = ?", (name,), one=True):
            continue
        category = query("SELECT id FROM categories WHERE name = ?", (cat,), one=True)
        seller = query("SELECT id FROM users WHERE email = ?", (seller_email,), one=True) if seller_email else None
        slug = slugify(name, "products")
        execute(
            """INSERT INTO products (name, slug, description, price, compare_at_price, category_id, seller_id,
                                     image, stock, is_new, is_featured)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (name, slug, desc, price, compare, category["id"], seller["id"] if seller else None,
             f"/static/img/products/{slugify(name)}.svg", stock, is_new, featured),
        )

    for title, desc, code, pct in PROMOTIONS:
        if query("SELECT id FROM promotions WHERE code = ?", (code,), one=True):
            continue
        execute(
            "INSERT INTO promotions (title, description, code, discount_percent) VALUES (?,?,?,?)",
            (title, desc, code, pct),
        )
    return True
