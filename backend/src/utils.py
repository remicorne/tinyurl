import string
from random import Random
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, ParseResult
from flask import request

BASE36_ALPHABET = string.ascii_lowercase + string.digits


def order_query(query: str) -> str:
    query_pairs = parse_qsl(query, keep_blank_values=True)  # permissif
    query_pairs.sort()
    query = urlencode(query_pairs, doseq=True)
    return query


def parse_url(raw_url: str) -> ParseResult:
    validated_url = raw_url
    parsed = urlparse(validated_url)
    # pour bien interpreter netloc
    if not parsed.scheme:
        validated_url = "http://" + validated_url.lstrip("://")
    parsed = urlparse(validated_url)
    if not parsed.netloc:
        raise ValueError("Malformed URL.")
    return parsed


def normalize_url(url: str) -> str:
    parsed_url = parse_url(url)
    scheme = parsed_url.scheme
    netloc = parsed_url.netloc.lower()
    path = parsed_url.path or "/"
    query = order_query(parsed_url.query)
    return urlunparse(
        (scheme, netloc, path, parsed_url.params, query, parsed_url.fragment)
    )


def generate_random_slug(url: str, length: int = 8) -> str:
    rd = Random()
    rd.seed(url)
    return "".join(rd.choice(BASE36_ALPHABET) for _ in range(length))


def build_tinyurl(slug: str):
    return request.url_root + slug
