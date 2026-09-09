"""
Standalone smoke test for the mock OAuth service - no ADK or GCP required.

Run this against a local instance:
    cd mock-oauth-service
    pip install -r requirements.txt
    uvicorn main:app --port 8080
    # in another terminal:
    python ../scripts/smoke_test.py http://localhost:8080 demo-client demo-secret

Or against the deployed Cloud Run URL:
    python scripts/smoke_test.py https://mock-2lo-oauth-XXXX-uc.a.run.app demo-client <secret>
"""

import sys

import httpx


def main() -> int:
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} BASE_URL CLIENT_ID CLIENT_SECRET")
        return 2

    base_url, client_id, client_secret = (
        sys.argv[1].rstrip("/"),
        sys.argv[2],
        sys.argv[3],
    )

    print(f"1) Requesting token from {base_url}/token ...")
    resp = httpx.post(
        f"{base_url}/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    token_payload = resp.json()
    assert token_payload["token_type"] == "Bearer"
    token = token_payload["access_token"]
    print(f"   OK - token issued, expires_in={token_payload['expires_in']}s")

    print("2) Calling /api/orders WITHOUT a token (expect 401)...")
    resp = httpx.get(f"{base_url}/api/orders", timeout=15.0)
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}"
    print("   OK - unauthenticated call rejected")

    print("3) Calling /api/orders WITH the token...")
    resp = httpx.get(
        f"{base_url}/api/orders",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    resp.raise_for_status()
    orders = resp.json()["orders"]
    print(f"   OK - got {len(orders)} orders: {[o['order_id'] for o in orders]}")

    print("4) Rejecting a bad client secret (expect 401)...")
    resp = httpx.post(
        f"{base_url}/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": "wrong-secret",
        },
        timeout=15.0,
    )
    assert resp.status_code == 401, f"expected 401, got {resp.status_code}"
    print("   OK - bad credentials rejected")

    print("\nAll smoke tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
