from http import HTTPStatus

import pytest

from src.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


def test_url_lifecycle(client):
    # NOT FOUND
    resp = client.get("/urls/abcdefgh")
    assert resp.status_code == HTTPStatus.NOT_FOUND

    original_url = "https://example.com/path?param1=param1&param2=param2"
    payload = {
        "url": original_url,
        "expiry_date": "2030-01-01T00:00:00Z",
    }

    # POST
    resp = client.post("/urls", json=payload)
    assert resp.status_code in (HTTPStatus.CREATED, HTTPStatus.OK)
    created = resp.get_json()
    tiny_url = created["url"]
    slug = tiny_url.split("/")[-1]

    # REDIRECT
    resp = client.get(tiny_url, follow_redirects=False)
    assert resp.status_code in (HTTPStatus.FOUND, HTTPStatus.MOVED_PERMANENTLY, 302)
    assert "Location" in resp.headers
    assert resp.headers["Location"] == original_url

    # STATS
    resp = client.get(f"/urls/{slug}")
    stats = resp.get_json()
    assert stats["tinyurl"] == tiny_url
    assert stats["normalized_url"] == original_url
    assert len(stats["accessed_at"]) == 1

    # DELETE
    resp = client.delete(f"/urls/{slug}").get_json()
    assert resp["tinyurl"]["normalized_url"] == original_url
    assert resp["deleted"] is True

    # REDIRECT 404
    resp = client.get(f"/{slug}", follow_redirects=False)
    assert resp.status_code == HTTPStatus.NOT_FOUND
