import logging
import sys
from http import HTTPStatus

import pendulum
from flask import Flask, jsonify, request, redirect, url_for
from flasgger import Swagger
from .db import init_db, select_all, select_one, insert, delete
from .utils import normalize_url, generate_random_slug, build_tinyurl

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s]: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

log = logging.getLogger(__name__)


app = Flask(__name__)
app.config["SWAGGER"] = {
    "title": "TinyURL API",
    "uiversion": 3,
}

swagger = Swagger(app)

init_db()


@app.get("/healthz")
def healthz():
    """
    Health check endpoint
    ---
    tags:
      - system
    responses:
      200:
        description: API is healthy
        schema:
          type: object
          properties:
            status:
              type: string
              example: ok
    """

    log.info("Health check")
    return jsonify(status="ok"), HTTPStatus.OK


@app.get("/readyz")
def readyz():
    """
    Readiness check endpoint
    ---
    tags:
      - system
    responses:
      200:
        description: API is ready
        schema:
          type: object
          properties:
            ready:
              type: boolean
              example: true
            db:
              type: boolean
              example: true
      500:
        description: API is not ready
        schema:
          type: object
          properties:
            ready:
              type: boolean
              example: false
            db:
              type: boolean
              example: false
            error:
              type: string
    """
    try:
        res = select_all("SELECT 1 AS ok;")
        ready = bool(res and res[0].get("ok") == 1)
        return jsonify(ready=ready, db=ready), HTTPStatus.OK
    except Exception as e:
        log.exception("Readiness check failed")
        return jsonify(
            ready=False, db=False, error=str(e)
        ), HTTPStatus.INTERNAL_SERVER_ERROR


@app.post("/urls")
def new_url():
    """
    Create a new URL
    ---
    tags:
      - urls
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            url:
              type: string
              example: https://example.com
            expiry_date:
              type: string
              format: date-time
              example: "2025-11-23T11:25:28Z"
    responses:
      201:
        description: URL created
        schema:
          type: object
          properties:
            url:
              type: string
              example: https://example.com
            links:
              type: object
              properties:
                redirect:
                  type: string
                  example: https://localhost:8080/h8GHfnFB
                stats:
                  type: string
                  example: https://localhost:8080/urls/h8GHfnFB
                delete:
                  type: string
                  example: https://localhost:8080/urls/h8GHfnFB
      200:
        description: URL already existed, returning existing tiny URL
        schema:
          type: object
          properties:
            url:
              type: string
            links:
              type: object
              properties:
                redirect:
                  type: string
                stats:
                  type: string
                delete:
                  type: string
      400:
        description: Invalid request body
        schema:
          type: object
          properties:
            error:
              type: string
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        body = request.get_json()
        url, expires_at = body["url"], body["expiry_date"]
        normalized_url = normalize_url(url)
        if existing_tinyurl := select_one(
            "SELECT slug FROM urls WHERE normalized_url = %s", normalized_url
        ):
            slug = existing_tinyurl["slug"]
            tiny_url = build_tinyurl(slug)
            links = {
                "redirect": tiny_url,
                "stats": url_for("get_url_stats", slug=slug, _external=True),
                "delete": url_for("delete_url", slug=slug, _external=True),
            }
            return jsonify(url=tiny_url, links=links), HTTPStatus.OK

        slug = generate_random_slug(url)
        while select_one("SELECT 1 AS ok FROM urls WHERE slug = %s", slug):
            slug = generate_random_slug(url + slug)
        insert(
            "INSERT INTO urls (slug, normalized_url, created_at, expires_at) VALUES (%s, %s, NOW(), %s);",
            slug,
            normalized_url,
            expires_at,
        )
        tiny_url = build_tinyurl(slug)
        links = {
            "redirect": tiny_url,
            "stats": url_for("get_url_stats", slug=slug, _external=True),
            "delete": url_for("delete_url", slug=slug, _external=True),
        }
        return jsonify(url=tiny_url, links=links), HTTPStatus.CREATED
    except Exception as e:
        log.exception("Error creating URL")
        return jsonify(error=str(e)), HTTPStatus.INTERNAL_SERVER_ERROR


@app.get("/urls/<slug>")
def get_url_stats(slug: str):
    """
    Get a URL stats
    ---
    tags:
      - urls
    parameters:
      - name: slug
        in: path
        required: true
        schema:
          type: string
          example: abc123
    responses:
      200:
        description: URL found
        schema:
          type: object
          properties:
            tinyurl:
              type: string
              example: https://localhost:8080/h8GHfnFB
            normalized_url:
              type: string
              example: https://example.com
            created_at:
              type: string
              format: date-time
            expires_at:
              type: string
              format: date-time
            accessed_at:
              type: array
              items:
                type: string
                format: date-time
      404:
        description: URL not found
        schema:
          type: object
          properties:
            error:
              type: string
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        if tinyurl := select_one("SELECT * FROM urls WHERE slug = %s;", slug):
            acceses = select_all(
                "SELECT accessed_at FROM access_logs WHERE url_id = %s;", tinyurl["id"]
            )
            return (
                jsonify(
                    tinyurl=build_tinyurl(tinyurl["slug"]),
                    normalized_url=tinyurl["normalized_url"],
                    created_at=tinyurl["created_at"],
                    expires_at=tinyurl["expires_at"],
                    accessed_at=[access["accessed_at"] for access in acceses],
                ),
                HTTPStatus.OK,
            )
        else:
            return jsonify(error="URL not found"), HTTPStatus.NOT_FOUND
    except Exception as e:
        log.exception("Error getting URL stats")
        return jsonify(error=str(e)), HTTPStatus.INTERNAL_SERVER_ERROR


@app.get("/urls")
def get_urls():
    """
    List all URLs
    ---
    tags:
      - urls
    responses:
      200:
        description: URLs created
        schema:
          type: array
          items:
            type: object
            properties:
              slug:
                type: string
                example: h8GHfnFB
              normalized_url:
                type: string
                example: https://example.com
              created_at:
                type: string
                format: date-time
              expires_at:
                type: string
                format: date-time
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        urls = select_all("SELECT * FROM urls")
        return jsonify(urls), HTTPStatus.OK
    except Exception as e:
        log.exception("Error listing URLs")
        return jsonify(error=str(e)), HTTPStatus.INTERNAL_SERVER_ERROR


@app.delete("/urls/<slug>")
def delete_url(slug: str):
    """
    Delete a URL
    ---
    tags:
      - urls
    parameters:
      - name: slug
        in: path
        required: true
        schema:
          type: string
          example: abc123
    responses:
      204:
        description: URL deleted
      404:
        description: URL not found
        schema:
          type: object
          properties:
            error:
              type: string
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        if tinyurl := select_one(
            "SELECT slug, created_at, normalized_url FROM urls WHERE slug = %s;", slug
        ):
            delete_result = delete("DELETE from urls WHERE slug = %s", tinyurl["slug"])
            return jsonify(
                tinyurl=tinyurl,
                deleted=delete_result,
            ), HTTPStatus.OK
        else:
            return jsonify(error="URL not found"), HTTPStatus.NOT_FOUND
    except Exception as e:
        log.exception("Error deleting URL")
        return jsonify(error=str(e)), HTTPStatus.INTERNAL_SERVER_ERROR


@app.get("/<slug>")
def redirect_url(slug: str):
    """
    Redirect to a URL
    ---
    tags:
      - urls
    parameters:
      - name: slug
        in: path
        required: true
        schema:
          type: string
          example: abc123
    responses:
      302:
        description: Redirect to the original URL
      404:
        description: URL not found
        schema:
          type: object
          properties:
            error:
              type: string
      410:
        description: URL expired
        schema:
          type: object
          properties:
            error:
              type: string
      500:
        description: Internal server error
        schema:
          type: object
          properties:
            error:
              type: string
    """
    try:
        tinyurl = select_one(
            "SELECT id, normalized_url, expires_at FROM urls WHERE slug = %s;", slug
        )
        if not tinyurl:
            return jsonify(error="URL not found"), HTTPStatus.NOT_FOUND

        if tinyurl["expires_at"] and tinyurl["expires_at"] < pendulum.now():
            return jsonify(error="URL expired"), HTTPStatus.GONE

        insert(
            "INSERT INTO access_logs (url_id, accessed_at) VALUES (%s, NOW());",
            tinyurl["id"],
        )
        return redirect(tinyurl["normalized_url"])
    except Exception as e:
        log.exception("Error redirecting URL")
        return jsonify(error=str(e)), HTTPStatus.INTERNAL_SERVER_ERROR
