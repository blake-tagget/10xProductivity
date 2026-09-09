#!/usr/bin/env python3
"""
Shared Playwright browser utilities for tool SSO scripts.

Each tool's sso.py imports from here rather than duplicating boilerplate.

Requirements:
    pip install playwright && playwright install chromium
"""

import functools
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("Installing playwright...")
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# Re-export for tool sso.py files that need it
__all__ = [
    "sync_playwright", "PlaywrightTimeout",
    "load_env_var", "load_env_file", "update_env_file",
    "http_get", "http_get_no_redirect",
    "make_ssl_ctx", "urlopen",
    "DEFAULT_ENV_FILE", "TENX_PRIVATE_DIR", "private_path", "resolve_env_file",
    "BROWSER_AUTOMATION_DIR",
]

TENX_PRIVATE_DIR = Path(
    os.environ.get("TENX_PRIVATE_DIR", Path.home() / ".10xProductivity")
).expanduser()

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REPO_ENV_FILE = _REPO_ROOT / ".env"


def private_path(*parts: str) -> Path:
    return TENX_PRIVATE_DIR.joinpath(*parts)


def resolve_env_file() -> Path:
    """Prefer ~/.10xProductivity/.env; fall back to repo-root .env when present."""
    private = private_path(".env")
    if private.exists():
        return private
    if _REPO_ENV_FILE.exists():
        return _REPO_ENV_FILE
    return private


DEFAULT_ENV_FILE = resolve_env_file()

# Shared home for all persistent browser profiles and auth snapshots.
# Lives outside the repo (~/.browser_automation/) so sessions survive
# repo re-clones and are never accidentally committed.
BROWSER_AUTOMATION_DIR = Path.home() / ".browser_automation"


def load_env_var(key: str, default: str = "") -> str:
    """Load a variable from .env file or environment, falling back to default."""
    env_file = resolve_env_file()
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    return os.environ.get(key, default)


def load_env_file(env_path: Path | None = None) -> dict:
    """Read all key=value pairs from a .env file."""
    env_path = env_path or resolve_env_file()
    result = {}
    if not env_path.exists():
        return result
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            result[k.strip()] = v.strip()
    return result


def update_env_file(env_path: Path | None, tokens: dict) -> None:
    """Write / update token values in a .env file."""
    env_path = env_path or resolve_env_file()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    if not env_path.exists():
        env_path.write_text("")
    content = env_path.read_text()

    def _upsert(text: str, key: str, value: str, section_hint: str = "") -> str:
        pattern = rf"^({re.escape(key)}=).*$"
        new_line = f"{key}={value}"
        if re.search(pattern, text, flags=re.MULTILINE):
            return re.sub(pattern, new_line, text, flags=re.MULTILINE)
        if section_hint and section_hint in text:
            return re.sub(
                rf"({re.escape(section_hint)}[^\n]*\n)",
                r"\1" + new_line + "\n",
                text,
            )
        return text + f"\n{new_line}\n"

    for key, value in tokens.items():
        if value:
            env_key = key.upper()
            section_hint = _section_hint(env_key)
            content = _upsert(content, env_key, value, section_hint)

    env_path.write_text(content)
    print(f"  Updated {env_path}")


def _section_hint(env_key: str) -> str:
    """Return the .env section comment that precedes the given env var."""
    _overrides = {
        "GRAPH": "# --- Outlook / Microsoft 365",
        "OWA": "# --- Outlook / Microsoft 365",
        "GDRIVE": "# --- Google Drive",
    }
    prefix = env_key.split("_")[0]
    if prefix in _overrides:
        return _overrides[prefix]
    return f"# --- {prefix.title()}"


def make_ssl_ctx(verify: bool = True) -> ssl.SSLContext:
    """Create an SSL context.

    Pass ``verify=False`` only after a verified request fails with ``ssl.SSLError``
    (for example on laptops where Zscaler intercepts HTTPS).
    """
    ctx = ssl.create_default_context()
    if not verify:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


@functools.lru_cache(maxsize=1)
def _verified_ssl_ctx() -> ssl.SSLContext:
    return make_ssl_ctx(verify=True)


@functools.lru_cache(maxsize=1)
def _unverified_ssl_ctx() -> ssl.SSLContext:
    return make_ssl_ctx(verify=False)


def _is_ssl_error(exc: BaseException) -> bool:
    if isinstance(exc, ssl.SSLError):
        return True
    reason = getattr(exc, "reason", None)
    return isinstance(reason, ssl.SSLError)


def urlopen(req, timeout: int = 15):
    """Open a URL with certificate verification, retrying once for Zscaler SSL."""
    try:
        return urllib.request.urlopen(req, context=_verified_ssl_ctx(), timeout=timeout)
    except Exception as exc:
        if not _is_ssl_error(exc):
            raise
        return urllib.request.urlopen(req, context=_unverified_ssl_ctx(), timeout=timeout)


def http_get(url: str, headers: dict) -> int:
    """Make a GET request and return the HTTP status code."""
    try:
        req = urllib.request.Request(url, headers=headers)
        with urlopen(req, timeout=8) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return 0


def http_get_no_redirect(url: str, headers: dict) -> int:
    """GET without following redirects — returns 302 for expired sessions."""
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None

    def _open_with(ctx: ssl.SSLContext) -> int:
        opener = urllib.request.build_opener(_NoRedirect(), urllib.request.HTTPSHandler(context=ctx))
        req = urllib.request.Request(url, headers=headers)
        with opener.open(req, timeout=8) as resp:
            return resp.status

    try:
        return _open_with(_verified_ssl_ctx())
    except Exception as exc:
        if not _is_ssl_error(exc):
            if isinstance(exc, urllib.error.HTTPError):
                return exc.code
            return 0
        try:
            return _open_with(_unverified_ssl_ctx())
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:
            return 0
