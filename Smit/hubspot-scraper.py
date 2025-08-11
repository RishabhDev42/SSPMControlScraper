import asyncio, time, math
from pathlib import Path
from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright


def login_and_save():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")
        page = context.new_page()

        page.goto("https://app-na2.hubspot.com/login")
        
        # You click "Sign in with Google", log in, solve CAPTCHA/2FA manually
        input("Press Enter after you're fully logged in...")

        # Save login session
        context.storage_state(path="auth.json")
        browser.close()

login_and_save()

NAV_TIMEOUT_MS = 60000

FIND_LARGEST_SCROLL = """
() => {
  let best = document.scrollingElement || document.documentElement;
  let bestScore = Math.max(0, best.scrollHeight - best.clientHeight);

  for (const el of document.querySelectorAll('*')) {
    const cs = getComputedStyle(el);
    const canScroll = el.scrollHeight - el.clientHeight;
    if (canScroll > bestScore && ['auto','scroll','overlay'].includes(cs.overflowY)) {
      best = el; bestScore = canScroll;
    }
  }
  return best;
}
"""

DISABLE_STICKY = """
() => {
  const style = document.createElement('style');
  style.id = 'no-sticky';
  style.textContent = `
    * { scroll-behavior: auto !important; }
    [style*="position: sticky"], [class*="sticky"], header, nav {
      position: static !important; top: auto !important;
    }
  `;
  document.documentElement.appendChild(style);
}
"""

async def tile_scroll_screenshots(page, out_prefix: str, overlap_px: int = 100):
    # 1) choose target scroll container
    root = await page.evaluate_handle(FIND_LARGEST_SCROLL)

    # 2) sizes
    total_h, client_h = await page.evaluate(
        "(el) => [el.scrollHeight, el.clientHeight]", root
    )
    if total_h <= client_h + 5:
        # No inner scroll; just shoot once
        img = await page.screenshot(full_page=True)
        p = Path(f"{out_prefix}_1.png"); p.write_bytes(img); return [str(p)]

    # 3) disable sticky bars so they don't repeat on every tile
    await page.evaluate(DISABLE_STICKY)

    # 4) scroll to top first
    await page.evaluate("(el) => { el.scrollTo(0, 0); }", root)
    await page.wait_for_timeout(200)

    step = client_h - overlap_px
    steps = max(1, math.ceil((total_h - client_h) / max(1, step)) + 1)

    out_files = []
    for i in range(steps):
        y = min(i * step, total_h - client_h)
        await page.evaluate("(args) => { args.el.scrollTo(0, args.y); }", {"el": root, "y": y})

        await page.wait_for_timeout(150)  # let lazy sections render
        img = await page.screenshot()     # viewport shot
        p = Path(f"{out_prefix}_{i+1:02d}.png")
        p.write_bytes(img)
        out_files.append(str(p))
        print(f"[✓] Tile {i+1}/{steps} at y={y}")

    return out_files

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state="auth.json",
            viewport={"width": 1440, "height": 1100},
            device_scale_factor=2,
        )
        page = await context.new_page()
        await page.goto("https://app-na2.hubspot.com/ai-settings/243323139",
                        wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)

        # small settle + wake lazy content a bit
        await page.wait_for_timeout(500)

        files = await tile_scroll_screenshots(page, "shots/hubspot")
        print("Saved tiles:", files)

        time.sleep(8)

        await context.close(); await browser.close()

if __name__ == "__main__":
    asyncio.run(run())