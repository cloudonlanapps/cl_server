import time
import requests


def wait_for_server(url: str, timeout: int = 30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=1)
            if r.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError(f"Server did not become ready: {url}")


def verify_compute_auth_from_root(compute_url: str, expected: bool):
    r = requests.get(compute_url, timeout=5)
    r.raise_for_status()
    payload = r.json()

    actual = payload.get("auth_required")
    if actual is None:
        raise RuntimeError("Compute '/' missing 'auth_required'")

    if actual != expected:
        raise RuntimeError(
            f"Compute auth mismatch: expected={expected}, actual={actual}"
        )


def set_store_guest_mode(auth_url, store_url, admin_password, guest_mode):
    enabled = guest_mode == "off"

    token_resp = requests.post(
        f"{auth_url}/auth/token",
        data={"username": "admin", "password": admin_password},
        timeout=5,
    )
    token_resp.raise_for_status()

    token = token_resp.json().get("access_token")
    if not token:
        raise RuntimeError("Failed to obtain admin token")

    r = requests.put(
        f"{store_url}/admin/config/read-auth",
        headers={"Authorization": f"Bearer {token}"},
        files={"enabled": str(enabled).lower()},
        timeout=5,
    )
    r.raise_for_status()


def verify_store_guest_mode(store_url: str, expected: str):
    r = requests.get(store_url, timeout=5)
    r.raise_for_status()

    actual = r.json().get("guestMode")
    if actual != expected:
        raise RuntimeError(
            f"Store guest mode mismatch: expected={expected}, actual={actual}"
        )
