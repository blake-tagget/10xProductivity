#!/usr/bin/env python3
"""
ServiceNow catalog item field discovery tool.

Opens a form, iterates through all select options to map cascading fields,
and saves the complete field spec to form-specs/<item>.json.

Usage:
  python3 personal/servicenow/discover_form.py <item_key>
  python3 personal/servicenow/discover_form.py github_cloud

Output: personal/servicenow/form-specs/<item>.json

Re-run any time the form changes to update the spec.

Performance: uses async Playwright — one browser tab per top-level select field
running in parallel, with no page reload between options within each tab.
"""

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    import os
    os.system(f"{sys.executable} -m pip install playwright -q")
    os.system(f"{sys.executable} -m playwright install chromium -q")
    from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "tool_connections" / "servicenow"))

AUTH_FILE = Path.home() / ".browser_automation" / "servicenow_auth.json"
INSTANCE = "https://workday.service-now.com"
SPECS_DIR = Path(__file__).parent.parent.parent / "personal" / "servicenow" / "form-specs"

FORM_URL = "{instance}/esc?id=sc_cat_item&sys_id={sys_id}&table=sc_cat_item"

# Shared JS for visible field detection.
# Two-pass approach: reference (typeahead) fields first so they override any plain input
# with the same name that the DOM query might encounter first.
_VISIBLE_FIELDS_JS = """
    () => {
        const fields = [];
        const seenIdx = new Map(); // name -> index in fields array (allows override)

        function getLabel(el) {
            const id = el.id || '';
            const labelEl = document.querySelector(`label[for="${id}"]`);
            if (labelEl) return labelEl.innerText.trim().replace(/\s+/g, ' ');
            if (el.getAttribute('aria-label')) return el.getAttribute('aria-label').trim().replace(/\s+/g, ' ');
            return '';
        }

        // Pass 1: reference (typeahead) fields detected by label-id attribute.
        // ServiceNow glide reference widgets: aria-hidden select2-offscreen input.
        // The Select2 visible wrapper doesn't exist at page load time, so we check
        // Angular scope's isVisible() — the authoritative source for field visibility.
        // Must run first so they can override any plain-text input with the same name.
        document.querySelectorAll('input[label-id]').forEach(el => {
            if (!el.name) return;
            // Use Angular scope isVisible() to check if the field is shown
            try {
                const scope = angular.element(el).scope();
                if (scope && scope.field && typeof scope.field.isVisible === 'function') {
                    if (!scope.field.isVisible()) return;
                }
            } catch(e) {
                // If Angular not available, fall back to checking ng-hide on parent
                const group = el.closest('.form-group');
                if (group && group.classList.contains('ng-hide')) return;
            }

            const field = {
                name: el.name, label: getLabel(el), tag: 'typeahead',
                required: el.required || el.getAttribute('aria-required') === 'true',
            };
            if (seenIdx.has(el.name)) {
                fields[seenIdx.get(el.name)] = field; // override plain input detected earlier
            } else {
                seenIdx.set(el.name, fields.length);
                fields.push(field);
            }
        });

        // Pass 2: all other visible fields (selects, textareas, plain text inputs).
        document.querySelectorAll('input[name], select[name], textarea[name]').forEach(el => {
            if (!el.name) return;
            if (el.getAttribute('label-id')) return;                                        // handled in pass 1
            if (el.tagName === 'INPUT' && el.getAttribute('aria-hidden') === 'true') return; // reference backing input
            if (el.tagName === 'INPUT' && el.classList.contains('select2-offscreen')) return; // Select2 input backing

            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            let visible = rect.width > 0 && rect.height > 0 &&
                          style.display !== 'none' &&
                          style.visibility !== 'hidden' &&
                          el.offsetParent !== null;

            // Select2 hides the native <select> — check the Select2 container instead
            if (!visible && el.tagName === 'SELECT') {
                const s2 = document.getElementById(`s2id_sp_formfield_${el.name}`) ||
                           document.getElementById(`s2id_${el.id || ''}`);
                if (s2) {
                    const s2style = window.getComputedStyle(s2);
                    visible = s2.offsetParent !== null && s2style.display !== 'none';
                }
            }

            if (!visible) return;

            if (seenIdx.has(el.name)) return; // already a typeahead — don't downgrade

            seenIdx.set(el.name, fields.length);

            const field = {
                name: el.name, label: getLabel(el), tag: el.tagName.toLowerCase(),
                required: el.required || el.getAttribute('aria-required') === 'true',
            };

            if (el.tagName === 'SELECT') {
                field.options = Array.from(el.options)
                    .map(o => ({ value: o.value, text: o.text.trim() }))
                    .filter(o => o.text && o.text !== '-- None --');
            }

            fields.push(field);
        });

        return fields;
    }
"""


def _load_state() -> dict:
    if not AUTH_FILE.exists():
        sys.exit(f"Auth file not found: {AUTH_FILE}\nRun: python3 tool_connections/servicenow/sso.py")
    return json.loads(AUTH_FILE.read_text())


async def _get_visible_fields(page) -> list[dict]:
    return await page.evaluate(_VISIBLE_FIELDS_JS)


async def _select_option(page, field_name: str, opt_val: str, opt_text: str) -> bool:
    """Click a Select2 option to trigger Angular cascade. Returns True if clicked."""
    container_id = f"s2id_sp_formfield_{field_name}"
    try:
        trigger = page.locator(f"#{container_id} .select2-choice, #{container_id} .select2-selection").first
        await trigger.wait_for(timeout=5000)
        await trigger.click()
    except PlaywrightTimeout:
        try:
            sel_id = await page.evaluate(f"document.querySelector(\"select[name='{field_name}']\")?.id || ''")
            await page.locator(f"#s2id_{sel_id} .select2-choice").click()
        except Exception:
            return False
    await asyncio.sleep(0.4)

    opts = page.locator(".select2-results li, .select2-results__option")
    for opt in await opts.all():
        try:
            text = (await opt.inner_text()).strip()
            if opt_text.lower() in text.lower() and text:
                await opt.click()
                await asyncio.sleep(2.0)  # Wait for Angular cascade to settle
                return True
        except Exception:
            pass

    try:
        await page.keyboard.press("Escape")
    except Exception:
        pass
    return False


async def _load_form(ctx, sys_id: str):
    """Open a new tab and load the catalog item form."""
    page = await ctx.new_page()
    url = FORM_URL.format(instance=INSTANCE, sys_id=sys_id)
    await page.goto(url, wait_until="networkidle", timeout=30_000)
    await asyncio.sleep(3)
    return page


async def _explore_select_field(
    ctx, sys_id: str, field: dict, baseline_names: set, print_lock: asyncio.Lock
) -> dict:
    """
    Open one tab and explore all options for a single select field.
    No page reload between options — just re-click the Select2 trigger.
    Returns cascade info and newly discovered field specs.
    """
    fname = field["name"]
    cascades_to: dict[str, list[str]] = {}
    new_field_specs: dict[str, dict] = {}

    page = await _load_form(ctx, sys_id)
    async with print_lock:
        print(f"\n  Exploring cascades for {fname!r}...", flush=True)

    current_l1_cascade_names: set[str] = set()

    for opt in field["options"]:
        opt_text = opt["text"]
        async with print_lock:
            print(f"    Option: {opt_text!r}", flush=True)

        clicked = await _select_option(page, fname, opt["value"], opt_text)
        if not clicked:
            async with print_lock:
                print(f"      (could not click — skipping)", flush=True)
            continue

        after_fields = await _get_visible_fields(page)
        after_names = {af["name"] for af in after_fields}
        new_names = [af["name"] for af in after_fields if af["name"] not in baseline_names]

        # Track all cascade field names we've seen so far (for L2 new-field detection)
        current_l1_cascade_names.update(new_names)

        if new_names:
            async with print_lock:
                print(f"      → reveals: {new_names}", flush=True)
            cascades_to[opt_text] = new_names

            for af in after_fields:
                if af["name"] not in baseline_names:
                    if af["name"] not in new_field_specs:
                        new_field_specs[af["name"]] = {
                            "name": af["name"],
                            "label": af["label"],
                            "tag": af["tag"],
                            "required": af["required"],
                            "options": af.get("options", []),
                            "always_visible": False,
                            "shown_when": [f"{fname}={opt_text!r}"],
                            "cascades_to": {},
                        }
                    else:
                        entry = f"{fname}={opt_text!r}"
                        if entry not in new_field_specs[af["name"]]["shown_when"]:
                            new_field_specs[af["name"]]["shown_when"].append(entry)

            # Explore L2 cascades for newly revealed select fields (no reload)
            for af in after_fields:
                if af["name"] not in baseline_names and af["tag"] == "select" and af.get("options"):
                    l2_baseline = baseline_names | after_names
                    async with print_lock:
                        print(f"      Exploring L2 cascades for {af['name']!r}...", flush=True)

                    for opt2 in af["options"]:
                        await _select_option(page, af["name"], opt2["value"], opt2["text"])
                        l2_fields = await _get_visible_fields(page)
                        l2_new = [
                            lf["name"] for lf in l2_fields
                            if lf["name"] not in l2_baseline
                        ]
                        if l2_new:
                            async with print_lock:
                                print(f"        {af['name']}={opt2['text']!r} → {l2_new}", flush=True)
                            new_field_specs[af["name"]]["cascades_to"][opt2["text"]] = l2_new
                            for lf in l2_fields:
                                if lf["name"] in l2_new and lf["name"] not in new_field_specs:
                                    new_field_specs[lf["name"]] = {
                                        "name": lf["name"],
                                        "label": lf["label"],
                                        "tag": lf["tag"],
                                        "required": lf["required"],
                                        "options": lf.get("options", []),
                                        "always_visible": False,
                                        "shown_when": [f"{af['name']}={opt2['text']!r}"],
                                        "cascades_to": {},
                                    }

    await page.close()
    return {"cascades_to": cascades_to, "new_field_specs": new_field_specs}


async def _discover_item(item_key: str) -> dict:
    from submit import CATALOG_ITEMS
    if item_key not in CATALOG_ITEMS:
        sys.exit(f"Unknown item: {item_key!r}. Known: {list(CATALOG_ITEMS)}")

    item = CATALOG_ITEMS[item_key]
    sys_id = item["sys_id"]
    state = _load_state()

    spec = {
        "item_key": item_key,
        "sys_id": sys_id,
        "form_title": None,
        "discovered_at": datetime.now(timezone.utc).isoformat(),
        "fields": [],
        "notes": item.get("notes"),
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--window-size=1400,900"],
        )
        ctx = await browser.new_context(
            storage_state=state,
            ignore_https_errors=True,
            viewport={"width": 1400, "height": 900},
        )

        # Step 1: load form once to enumerate initial fields
        page = await _load_form(ctx, sys_id)
        spec["form_title"] = (await page.title()).replace(" - Employee Center", "").strip()
        print(f"\n  Form: {spec['form_title']}", flush=True)

        initial_fields = await _get_visible_fields(page)
        print(f"  Initial visible fields: {[f['name'] for f in initial_fields]}", flush=True)
        await page.close()

        # Build always-visible field specs
        baseline_names = {f["name"] for f in initial_fields}
        field_specs: dict[str, dict] = {}
        for f in initial_fields:
            field_specs[f["name"]] = {
                "name": f["name"],
                "label": f["label"],
                "tag": f["tag"],
                "required": f["required"],
                "options": f.get("options", []),
                "always_visible": True,
                "shown_when": [],
                "cascades_to": {},
            }

        # Step 2: one tab per select field, all running in parallel
        select_fields = [f for f in initial_fields if f["tag"] == "select" and f.get("options")]
        if select_fields:
            print_lock = asyncio.Lock()
            tasks = [
                _explore_select_field(ctx, sys_id, field, baseline_names, print_lock)
                for field in select_fields
            ]
            results = await asyncio.gather(*tasks)

            # Merge results into field_specs
            for field, result in zip(select_fields, results):
                field_specs[field["name"]]["cascades_to"] = result["cascades_to"]
                for new_name, new_spec in result["new_field_specs"].items():
                    if new_name not in field_specs:
                        field_specs[new_name] = new_spec
                    else:
                        for entry in new_spec["shown_when"]:
                            if entry not in field_specs[new_name]["shown_when"]:
                                field_specs[new_name]["shown_when"].append(entry)
                        field_specs[new_name]["cascades_to"].update(new_spec["cascades_to"])

        spec["fields"] = list(field_specs.values())
        await ctx.close()
        await browser.close()

    return spec


def main():
    if len(sys.argv) < 2:
        sys.exit("Usage: python3 discover_form.py <item_key>")

    item_key = sys.argv[1].lower()
    print(f"Discovering form: {item_key}", flush=True)

    spec = asyncio.run(_discover_item(item_key))

    SPECS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SPECS_DIR / f"{item_key}.json"
    out_path.write_text(json.dumps(spec, indent=2))
    print(f"\n  Saved → {out_path}", flush=True)

    print(f"\n{'='*60}")
    print(f"FORM: {spec['form_title']}")
    print(f"{'='*60}")
    for f in spec["fields"]:
        vis = "always" if f["always_visible"] else f"when: {f['shown_when']}"
        opts = f"  options: {[o['text'] for o in f['options']]}" if f.get("options") else ""
        cascades = f"  cascades: {f['cascades_to']}" if f.get("cascades_to") else ""
        tag_label = "TYPEAHEAD" if f["tag"] == "typeahead" else f["tag"].upper()
        print(f"\n  [{tag_label}] {f['name']!r} — {f['label']}")
        print(f"    visible: {vis}")
        if opts:
            print(f"    {opts}")
        if cascades:
            print(f"    {cascades}")


if __name__ == "__main__":
    main()
