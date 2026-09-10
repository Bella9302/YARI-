from app import create_app


def test_post_without_csrf_token_is_rejected(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "t.sqlite"), "UPLOAD_FOLDER": str(tmp_path)})
    client = app.test_client()
    assert client.post("/contact", data={"name": "x", "email": "x@x", "message": "hi"}).status_code == 400

    # A token rendered into the page is accepted.
    html = client.get("/contact").get_data(as_text=True)
    token = html.split('name="csrf_token" value="')[1].split('"')[0]
    r = client.post("/contact", data={"name": "x", "email": "x@x", "message": "hi", "csrf_token": token})
    assert r.status_code == 302
