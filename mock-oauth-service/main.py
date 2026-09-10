"""
Mock OAuth 2LO server + dummy API as a single Cloud Run function (gen2).

No Dockerfile, no local Docker, no Artifact Registry push from your machine:
`gcloud functions deploy` uploads this source and Google builds/runs it.

One HTTP function routes both endpoints by path:
  POST <FUNCTION_URL>/token        -> client_credentials token endpoint
  GET  <FUNCTION_URL>/api/orders   -> Bearer-protected dummy API
  GET  <FUNCTION_URL>/api/orders/<id>
  GET  <FUNCTION_URL>/healthz

Env vars (same as the Cloud Run version):
  DEMO_CLIENT_ID, DEMO_CLIENT_SECRET, TOKEN_SIGNING_KEY, TOKEN_TTL_SECONDS
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time

import functions_framework
from flask import Request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mock-oauth-fn")

CLIENT_ID = os.environ.get("DEMO_CLIENT_ID", "demo-client")
CLIENT_SECRET = os.environ.get("DEMO_CLIENT_SECRET", "demo-secret")
SIGNING_KEY = os.environ.get("TOKEN_SIGNING_KEY", "dev-only-signing-key-change-me")
TOKEN_TTL = int(os.environ.get("TOKEN_TTL_SECONDS", "3600"))

FAKE_ORDERS = [
    {"order_id": "ORD-1001", "customer": "Acme Corp", "total": 1250.00, "status": "SHIPPED"},
    {"order_id": "ORD-1002", "customer": "Globex", "total": 340.50, "status": "PENDING"},
    {"order_id": "ORD-1003", "customer": "Initech", "total": 99.99, "status": "DELIVERED"},
]


# ----------------------------- JWT helpers (HS256) -------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _sign(msg: bytes) -> bytes:
    return hmac.new(SIGNING_KEY.encode(), msg, hashlib.sha256).digest()


def _issue_token(client_id: str, scope: str) -> dict:
    now = int(time.time())
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(
        json.dumps(
            {
                "iss": "mock-2lo-oauth-fn",
                "sub": client_id,
                "aud": "demo-api",
                "scope": scope,
                "iat": now,
                "exp": now + TOKEN_TTL,
                "jti": secrets.token_hex(8),
            },
            separators=(",", ":"),
        ).encode()
    )
    signing_input = f"{header}.{payload}"
    return {
        "access_token": f"{signing_input}.{_b64url(_sign(signing_input.encode()))}",
        "token_type": "Bearer",
        "expires_in": TOKEN_TTL,
        "scope": scope,
    }


def _verify_token(token: str):
    """Returns (claims, None) on success or (None, error_message)."""
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError:
        return None, "Malformed token"
    if not hmac.compare_digest(_sign(f"{header_b64}.{payload_b64}".encode()), _b64url_decode(sig_b64)):
        return None, "Invalid token signature"
    claims = json.loads(_b64url_decode(payload_b64))
    if claims.get("exp", 0) < time.time():
        return None, "Token expired"
    return claims, None


# ----------------------------- route handlers ------------------------------
def _handle_token(request: Request):
    if request.form.get("grant_type") != "client_credentials":
        return jsonify(error="unsupported_grant_type",
                       error_description="Only client_credentials is supported"), 400

    # Client auth: HTTP Basic header OR form body params.
    cid, csecret = None, None
    authz = request.headers.get("Authorization", "")
    if authz.lower().startswith("basic "):
        try:
            cid, _, csecret = base64.b64decode(authz[6:]).decode().partition(":")
        except Exception:
            pass
    if not cid:
        cid = request.form.get("client_id")
        csecret = request.form.get("client_secret")

    if not cid or not csecret:
        return jsonify(error="invalid_client",
                       error_description="Missing client credentials"), 401
    if not (hmac.compare_digest(cid, CLIENT_ID) and hmac.compare_digest(csecret, CLIENT_SECRET)):
        logger.warning("Rejected token request for client_id=%s", cid)
        return jsonify(error="invalid_client",
                       error_description="Client authentication failed"), 401

    logger.info("Issued token for client_id=%s", cid)
    return jsonify(_issue_token(cid, request.form.get("scope", "orders.read")))


def _require_bearer(request: Request):
    authz = request.headers.get("Authorization", "")
    if not authz.lower().startswith("bearer "):
        return None, (jsonify(detail="Missing Bearer token"), 401)
    claims, err = _verify_token(authz[7:])
    if err:
        return None, (jsonify(detail=err), 401)
    return claims, None


def _handle_orders(request: Request, order_id: str | None):
    claims, err_resp = _require_bearer(request)
    if err_resp:
        return err_resp
    if order_id is None:
        logger.info("Authorized /api/orders call from sub=%s", claims.get("sub"))
        return jsonify(caller=claims.get("sub"), scope=claims.get("scope"), orders=FAKE_ORDERS)
    for order in FAKE_ORDERS:
        if order["order_id"] == order_id:
            return jsonify(order)
    return jsonify(detail=f"Order {order_id} not found"), 404


# ----------------------------- entry point ---------------------------------
@functions_framework.http
def app(request: Request):
    path = request.path.rstrip("/") or "/"

    if path == "/token" and request.method == "POST":
        return _handle_token(request)
    if path == "/api/orders" and request.method == "GET":
        return _handle_orders(request, None)
    if path.startswith("/api/orders/") and request.method == "GET":
        return _handle_orders(request, path.rsplit("/", 1)[-1])
    if path in ("/healthz", "/"):
        return jsonify(status="ok")

    return jsonify(detail=f"No route for {request.method} {path}"), 404
