"""
Mock OAuth 2.0 server (client-credentials / 2LO) + a dummy protected API.

This single Cloud Run service plays BOTH roles needed to demo the
Agent Identity auth manager 2LO flow entirely inside GCP:

  1. POST /token        -> OAuth 2.0 token endpoint (client_credentials grant).
                           This is what you register as the 2LO auth provider's
                           token endpoint in Agent Identity auth manager.
  2. GET  /api/orders   -> A dummy "third-party" resource API that requires a
                           Bearer token issued by /token. This is what the ADK
                           agent's tool calls with the injected token.

Tokens are self-contained HMAC-signed JWTs, so the service stays stateless
and works correctly even when Cloud Run scales to multiple instances.

Environment variables:
  DEMO_CLIENT_ID       expected OAuth client id      (default: demo-client)
  DEMO_CLIENT_SECRET   expected OAuth client secret  (default: demo-secret)
  TOKEN_SIGNING_KEY    HMAC key used to sign tokens  (default: insecure dev key)
  TOKEN_TTL_SECONDS    access token lifetime         (default: 3600)
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from typing import Optional

from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mock-oauth")

CLIENT_ID = os.environ.get("DEMO_CLIENT_ID", "demo-client")
CLIENT_SECRET = os.environ.get("DEMO_CLIENT_SECRET", "demo-secret")
SIGNING_KEY = os.environ.get("TOKEN_SIGNING_KEY", "dev-only-signing-key-change-me")
TOKEN_TTL = int(os.environ.get("TOKEN_TTL_SECONDS", "3600"))

app = FastAPI(title="Mock 2LO OAuth Server", version="1.0.0")


# --------------------------------------------------------------------------
# Minimal JWT helpers (HS256) - no external JWT dependency needed.
# --------------------------------------------------------------------------
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(msg: bytes) -> bytes:
    return hmac.new(SIGNING_KEY.encode("utf-8"), msg, hashlib.sha256).digest()


def issue_token(client_id: str, scope: str) -> dict:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": "mock-2lo-oauth-server",
        "sub": client_id,
        "aud": "demo-api",
        "scope": scope,
        "iat": now,
        "exp": now + TOKEN_TTL,
        "jti": secrets.token_hex(8),
    }
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64url(json.dumps(payload, separators=(",", ":")).encode())
    )
    token = signing_input + "." + _b64url(_sign(signing_input.encode("ascii")))
    return {
        "access_token": token,
        "token_type": "Bearer",
        "expires_in": TOKEN_TTL,
        "scope": scope,
    }


def verify_token(token: str) -> dict:
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
    except ValueError:
        raise HTTPException(status_code=401, detail="Malformed token")

    expected_sig = _sign(f"{header_b64}.{payload_b64}".encode("ascii"))
    if not hmac.compare_digest(expected_sig, _b64url_decode(sig_b64)):
        raise HTTPException(status_code=401, detail="Invalid token signature")

    payload = json.loads(_b64url_decode(payload_b64))
    if payload.get("exp", 0) < time.time():
        raise HTTPException(status_code=401, detail="Token expired")
    return payload


# --------------------------------------------------------------------------
# OAuth 2.0 token endpoint (client_credentials grant).
#
# Supports both common client authentication styles, since different OAuth
# brokers use different ones:
#   - HTTP Basic auth header:  Authorization: Basic base64(client_id:secret)
#   - Form body parameters:    client_id=...&client_secret=...
# --------------------------------------------------------------------------
def _extract_client_creds(
    authorization: Optional[str],
    form_client_id: Optional[str],
    form_client_secret: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    if authorization and authorization.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(authorization[6:]).decode("utf-8")
            cid, _, csecret = decoded.partition(":")
            return cid, csecret
        except Exception:
            return None, None
    return form_client_id, form_client_secret


@app.post("/token")
async def token(
    request: Request,
    grant_type: str = Form(...),
    scope: str = Form(default="orders.read"),
    client_id: Optional[str] = Form(default=None),
    client_secret: Optional[str] = Form(default=None),
    authorization: Optional[str] = Header(default=None),
):
    if grant_type != "client_credentials":
        return JSONResponse(
            status_code=400,
            content={
                "error": "unsupported_grant_type",
                "error_description": "Only client_credentials is supported",
            },
        )

    cid, csecret = _extract_client_creds(authorization, client_id, client_secret)

    if not cid or not csecret:
        return JSONResponse(
            status_code=401,
            content={
                "error": "invalid_client",
                "error_description": "Missing client credentials",
            },
        )

    valid = hmac.compare_digest(cid, CLIENT_ID) and hmac.compare_digest(
        csecret, CLIENT_SECRET
    )
    if not valid:
        logger.warning("Rejected token request for client_id=%s", cid)
        return JSONResponse(
            status_code=401,
            content={
                "error": "invalid_client",
                "error_description": "Client authentication failed",
            },
        )

    logger.info("Issued token for client_id=%s scope=%s", cid, scope)
    return issue_token(cid, scope)


# --------------------------------------------------------------------------
# Dummy protected resource API - the "third-party service" the agent calls.
# --------------------------------------------------------------------------
FAKE_ORDERS = [
    {"order_id": "ORD-1001", "customer": "Acme Corp", "total": 1250.00, "status": "SHIPPED"},
    {"order_id": "ORD-1002", "customer": "Globex", "total": 340.50, "status": "PENDING"},
    {"order_id": "ORD-1003", "customer": "Initech", "total": 99.99, "status": "DELIVERED"},
]


def _require_bearer(authorization: Optional[str]) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    return verify_token(authorization[7:])


@app.get("/api/orders")
async def list_orders(authorization: Optional[str] = Header(default=None)):
    claims = _require_bearer(authorization)
    logger.info("Authorized /api/orders call from sub=%s", claims.get("sub"))
    return {"caller": claims.get("sub"), "scope": claims.get("scope"), "orders": FAKE_ORDERS}


@app.get("/api/orders/{order_id}")
async def get_order(order_id: str, authorization: Optional[str] = Header(default=None)):
    _require_bearer(authorization)
    for order in FAKE_ORDERS:
        if order["order_id"] == order_id:
            return order
    raise HTTPException(status_code=404, detail=f"Order {order_id} not found")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
