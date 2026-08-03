"""
ServiceNow REST client — token-safe (reads only from ~/.browser_automation/servicenow_auth.json).

Usage:
    from servicenow import ServiceNow
    sn = ServiceNow()
    results = sn.search_catalog_items("snowflake")
"""

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

AUTH_FILE = Path.home() / ".browser_automation" / "servicenow_auth.json"
INSTANCE = "https://workday.service-now.com"

REFRESH_HINT = (
    "Session expired or missing.\n"
    "Run: python3 tool_connections/servicenow/sso.py"
)


class ServiceNow:
    def __init__(self, auth_file: Path = AUTH_FILE):
        if not auth_file.exists():
            raise RuntimeError(
                f"Auth file not found: {auth_file}\n{REFRESH_HINT}"
            )

        state = json.loads(auth_file.read_text())
        cookies = {
            c["name"]: c["value"]
            for c in state.get("cookies", [])
            if "service-now.com" in c.get("domain", "")
        }
        if not cookies:
            raise RuntimeError(f"No ServiceNow cookies in {auth_file}\n{REFRESH_HINT}")

        self._cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        self._user_token: str | None = None
        self._ssl = ssl.create_default_context()
        self._ssl.check_hostname = False
        self._ssl.verify_mode = ssl.CERT_NONE

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_user_token(self) -> str | None:
        """Fetch X-UserToken (CSRF key) from any REST GET response header."""
        if self._user_token:
            return self._user_token
        try:
            req = urllib.request.Request(
                f"{INSTANCE}/api/now/table/sys_user?sysparm_limit=1&sysparm_fields=name",
                headers={"Cookie": self._cookie_str, "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, context=self._ssl, timeout=15) as r:
                self._user_token = r.headers.get("X-UserToken")
        except Exception:
            pass
        return self._user_token

    def _request(self, method: str, path: str, data: dict | None = None) -> dict:
        url = f"{INSTANCE}{path}"
        body = json.dumps(data).encode() if data else None
        headers: dict[str, str] = {
            "Cookie": self._cookie_str,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if method != "GET":
            token = self._get_user_token()
            if token:
                headers["X-UserToken"] = token

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, context=self._ssl, timeout=30) as r:
                raw = r.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            if e.code in (301, 302, 401):
                raise RuntimeError(REFRESH_HINT)
            try:
                msg = json.loads(detail).get("error", {}).get("message", detail[:300])
            except Exception:
                msg = detail[:300]
            raise RuntimeError(f"HTTP {e.code}: {msg}")

    # ------------------------------------------------------------------
    # Catalog search & discovery
    # ------------------------------------------------------------------

    def search_catalog_items(self, query: str, limit: int = 20) -> list[dict]:
        """Search catalog items by keyword. Returns list of items."""
        q = urllib.parse.quote(
            f"nameLIKE{query}^ORshort_descriptionLIKE{query}^active=true"
        )
        result = self._request(
            "GET",
            f"/api/now/table/sc_cat_item"
            f"?sysparm_query={q}"
            f"&sysparm_limit={limit}"
            f"&sysparm_fields=sys_id,name,short_description,category,sys_class_name",
        )
        return result.get("result", [])

    def get_catalog_item(self, item_sys_id: str) -> dict:
        """Get catalog item details (name, description, pricing, etc.)."""
        result = self._request("GET", f"/api/now/sc/catalog/items/{item_sys_id}")
        return result.get("result", result)

    def get_item_variables(self, item_sys_id: str) -> list[dict]:
        """Get the form variables (fields) for a catalog item."""
        result = self._request(
            "GET",
            f"/api/now/sc/catalog/items/{item_sys_id}/variables",
        )
        return result.get("result", result) if isinstance(result, dict) else result

    # ------------------------------------------------------------------
    # Cart & submission
    # ------------------------------------------------------------------

    def get_cart(self) -> dict:
        """Get current cart contents."""
        return self._request("GET", "/api/now/sc/cart")

    def empty_cart(self) -> dict:
        """Remove all items from the cart."""
        return self._request("DELETE", "/api/now/sc/cart")

    def add_to_cart(self, item_sys_id: str, variables: dict | None = None) -> dict:
        """Add a catalog item to the cart with optional variable values."""
        body: dict = {"sysparm_id": item_sys_id}
        if variables:
            body["variables"] = variables
        return self._request("POST", "/api/now/sc/cart", body)

    def checkout_cart(self) -> dict:
        """Checkout cart — creates one REQ with one RITM per item."""
        return self._request("POST", "/api/now/sc/cart/checkout")

    def bundle_submit(
        self,
        items: list[tuple[str, dict | None]],
        clear_first: bool = True,
    ) -> dict:
        """
        Add multiple catalog items to cart and checkout as one order.

        items: list of (item_sys_id, variables_dict_or_None)
        Returns the checkout result with REQ number.
        """
        if clear_first:
            try:
                self.empty_cart()
            except Exception:
                pass

        for item_sys_id, variables in items:
            self.add_to_cart(item_sys_id, variables)

        return self.checkout_cart()

    # ------------------------------------------------------------------
    # Request tracking
    # ------------------------------------------------------------------

    def get_my_requests(self, limit: int = 10) -> list[dict]:
        """Get recent service catalog requests submitted by the current user."""
        result = self._request(
            "GET",
            "/api/now/table/sc_request"
            "?sysparm_query=opened_by=javascript:gs.getUserID()"
            "^ORDERBYDESCsys_created_on"
            f"&sysparm_limit={limit}"
            "&sysparm_fields=number,short_description,state,sys_created_on,sys_id",
        )
        return result.get("result", [])
