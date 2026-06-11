"""WebUI Analysis Tool - Uses Playwright to inspect the AgentPlane WebUI.

Captures:
1. ARIA snapshot (accessibility tree)
2. Console errors
3. Network failures
4. DOM structure
5. Interactive element inventory
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def analyze_webui(url: str = "http://127.0.0.1:8080", output_dir: str = "tmp"):
    """Run full WebUI analysis."""
    out = Path(output_dir)
    out.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})

        # Collect errors
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page_errors = []
        page.on("pageerror", lambda err: page_errors.append(str(err)))

        # Navigate
        page.goto(url)
        page.wait_for_timeout(2000)

        # 1. ARIA snapshot
        try:
            aria = page.aria_snapshot()
            (out / "aria-snapshot.yaml").write_text(aria, encoding="utf-8")
            print("[OK] ARIA snapshot saved")
        except Exception as e:
            print(f"[WARN] ARIA snapshot failed: {e}")

        # 2. ARIA snapshot with AI mode
        try:
            aria_ai = page.aria_snapshot(mode="ai")
            (out / "aria-snapshot-ai.yaml").write_text(aria_ai, encoding="utf-8")
            print("[OK] ARIA AI snapshot saved")
        except Exception as e:
            print(f"[WARN] ARIA AI snapshot failed: {e}")

        # 3. Console errors
        (out / "console-errors.json").write_text(
            json.dumps(console_errors, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[OK] Console errors: {len(console_errors)}")

        # 4. Page errors
        (out / "page-errors.json").write_text(
            json.dumps(page_errors, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[OK] Page errors: {len(page_errors)}")

        # 5. Interactive elements
        interactive = page.evaluate("""() => {
            const els = document.querySelectorAll('button, a, input, select, textarea, [role="button"], [role="link"], [tabindex]');
            return Array.from(els).map(el => ({
                tag: el.tagName.toLowerCase(),
                type: el.type || '',
                text: (el.textContent || '').trim().substring(0, 100),
                id: el.id || '',
                class: el.className || '',
                disabled: el.disabled || false,
                href: el.href || '',
                placeholder: el.placeholder || '',
            }));
        }""")
        (out / "interactive-elements.json").write_text(
            json.dumps(interactive, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[OK] Interactive elements: {len(interactive)}")

        # 6. Page structure
        structure = page.evaluate("""() => {
            function getStructure(el, depth) {
                if (depth > 3) return null;
                const children = Array.from(el.children).map(c => getStructure(c, depth + 1)).filter(Boolean);
                return {
                    tag: el.tagName.toLowerCase(),
                    id: el.id || undefined,
                    class: (el.className || '').toString().substring(0, 100) || undefined,
                    children: children.length > 0 ? children : undefined,
                };
            }
            return getStructure(document.body, 0);
        }""")
        (out / "page-structure.json").write_text(
            json.dumps(structure, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print("[OK] Page structure saved")

        # 7. Screenshot
        page.screenshot(path=str(out / "screenshot-dashboard.png"), full_page=False)
        print("[OK] Dashboard screenshot saved")

        # 8. Navigate to each view and capture
        views = [("能力地图", "capabilities"), ("运维", "operations"), ("日志", "logs")]
        for view_name, file_name in views:
            try:
                page.click(f'.nav-item:has-text("{view_name}")', timeout=3000)
                page.wait_for_timeout(1000)
                page.screenshot(path=str(out / f"screenshot-{file_name}.png"), full_page=False)
                
                # Get ARIA snapshot for this view
                try:
                    view_aria = page.aria_snapshot()
                    (out / f"aria-{file_name}.yaml").write_text(view_aria, encoding="utf-8")
                except Exception:
                    pass
                
                print(f"[OK] {view_name} view captured")
            except Exception as e:
                print(f"[WARN] Could not navigate to {view_name}: {e}")

        browser.close()

    return {
        "console_errors": len(console_errors),
        "page_errors": len(page_errors),
        "interactive_elements": len(interactive),
    }


if __name__ == "__main__":
    result = analyze_webui()
    print(f"\nAnalysis complete: {result}")
