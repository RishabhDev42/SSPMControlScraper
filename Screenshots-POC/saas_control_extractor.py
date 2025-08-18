import os, asyncio, math
from pathlib import Path
from typing import Dict, List, Tuple
from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright


from controls_converter import convert_controls
from pathlib import Path

from fileinput import filename
import enum, os

from PIL import Image
from pydantic import BaseModel

from google.genai import types
from google import genai

from dotenv import load_dotenv
load_dotenv()

import json 
from pathlib import Path

# ---------- Globals (updated per app at runtime) ----------
APP_NAME: str | None = None
APP_LOGIN_URL: str | None = None
AUTH_FILE: str | None = None
APP_CONTROLS_URL: str | None = None
DEFAULT_MODEL = "gemini-2.5-flash"

# ---------- Enums and Models ----------
class Category(enum.Enum):
    IAM = "IAM"
    DLP = "DLP"
    SECURITY = "Security"
    PRODUCTIVITY = "Productivity"

# class SubCategory(enum.Enum):

class SeverityLevel(enum.Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"     
    
class Control(BaseModel):
  application: str
  url:str
  control_subject: str
  description: str
  category: Category
  severity: SeverityLevel
  recommendations: str
  additional_info: str | None = None
#   subcategory: str | None = None

# ---------- Constants ----------
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

def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p

def prompt_yes_no(msg: str, default: bool = False) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    ans = input(msg + suffix).strip().lower()
    if ans == "" and default: return True
    return ans in ("y", "yes")

def login_and_save_interactive(app_name: str, app_login_url: str, auth_file: Path):
    """
    Sync Playwright login step (manual SSO, MFA, etc.).
    Saves storage_state to auth/{app}.json
    """
    print(f"[i] Starting manual login for {app_name}. Auth file -> {auth_file}")
    ensure_dir(auth_file.parent)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/114.0.0.0 Safari/537.36"
        ))
        page = context.new_page()

        # Change this start URL if your login entry differs per app
        page.goto(APP_LOGIN_URL)
        input(">>> Complete login (SSO/MFA) then press Enter here... ")

        context.storage_state(path=str(auth_file))
        browser.close()
        print(f"[✓] Saved auth state to {auth_file}")

async def tile_scroll_screenshots(page, out_prefix: str, overlap_px: int = 100) -> List[str]:
    out_prefix_path = Path(out_prefix)
    ensure_dir(out_prefix_path.parent)

    root = await page.evaluate_handle(FIND_LARGEST_SCROLL)

    total_h, client_h = await page.evaluate(
        "(el) => [el.scrollHeight, el.clientHeight]", root
    )
    if total_h <= client_h + 5:
        img = await page.screenshot(full_page=True)
        p = out_prefix_path.with_name(f"{out_prefix_path.stem}_1.png")
        p.write_bytes(img)
        return [str(p)]

    await page.evaluate(DISABLE_STICKY)
    await page.evaluate("(el) => { el.scrollTo(0, 0); }", root)
    await page.wait_for_timeout(200)

    step = max(1, client_h - overlap_px)
    steps = max(1, math.ceil((total_h - client_h) / step) + 1)

    out_files = []
    for i in range(steps):
        y = min(i * step, total_h - client_h)
        await page.evaluate("(args) => { args.el.scrollTo(0, args.y); }", {"el": root, "y": y})
        await page.wait_for_timeout(150)
        img = await page.screenshot()  # viewport tile
        p = out_prefix_path.with_name(f"{out_prefix_path.stem}_{i+1:02d}.png")
        p.write_bytes(img)
        out_files.append(str(p))
        print(f"[✓] Tile {i+1}/{steps} at y={y}")
    return out_files

async def capture_app(app_name: str, app_login_url: str, auth_file: Path, controls_url: str):
    """
    Uses saved auth to open the controls page and produce tiled screenshots
    under shots/{APP_NAME}/{APP_NAME}.png tiles.
    """
    global APP_NAME, APP_LOGIN_URL, AUTH_FILE, APP_CONTROLS_URL
    APP_NAME = app_name
    APP_LOGIN_URL = app_login_url
    AUTH_FILE = str(auth_file)
    APP_CONTROLS_URL = controls_url

    shots_dir = ensure_dir(Path("shots") / APP_NAME)
    out_prefix = str(shots_dir / APP_NAME)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            storage_state=str(auth_file),
            viewport={"width": 1440, "height": 1100},
            device_scale_factor=2,
        )
        page = await context.new_page()

        print(f"[i] Navigating to {controls_url}")
        await page.goto(controls_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        await page.wait_for_timeout(800)  # small settle for SPA

        tiles = await tile_scroll_screenshots(page, out_prefix)
        print(f"[✓] Saved tiles for {APP_NAME}: {tiles}")

        await context.close()
        await browser.close()

def get_apps_from_user() -> list[Tuple[str, str, str, Path]]:
    """
    Returns a list of (app_name, app_login_url, controls_url, auth_file) tuples based on user input.
    """
    apps_raw = input("Enter application name: ").strip()
    if not apps_raw:
        print("No apps provided. Exiting.")
        raise SystemExit(1)

    apps_login_urls = input("Enter application login URL(s) (comma-separated): ").strip()
    if not apps_login_urls:
        print("No app login URLs provided. Exiting.")
        raise SystemExit(1)

    app_names = [a.strip() for a in apps_raw.split(",") if a.strip()]
    app_login_urls = [url.strip() for url in apps_login_urls.split(",") if url.strip()]
    result: list[Tuple[str, str, str, Path]] = []

    for app, app_login_url in zip(app_names, app_login_urls):
        default_auth = Path("auth") / f"{app}.json"
        ensure_dir(default_auth.parent)

        if not default_auth.exists():
            print(f"[!] Auth file not found for {app}: {default_auth}")
            if prompt_yes_no(f"Do you want to login now to create auth for '{app}'?", default=True):
                login_and_save_interactive(app, app_login_url, default_auth)
            else:
                # Allow user to specify a different existing auth file
                alt = input("Provide an existing auth file path (or press Enter to abort this app): ").strip()
                if not alt:
                    print(f"Skipping {app} (no auth).")
                    continue
                default_auth = Path(alt).expanduser().resolve()
                if not default_auth.exists():
                    print(f"[!] Provided auth file does not exist: {default_auth}. Skipping {app}.")
                    continue

        controls_url = input(f"Enter the Controls URL for '{app}': ").strip()
        if not controls_url:
            print(f"Skipping {app} (no URL provided).")
            continue

        result.append((app, app_login_url, controls_url, default_auth))

    return result

def require_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val

def load_client() -> genai.Client:
    api_key = require_env("GEMINI_API_KEY")
    return genai.Client(api_key=api_key)

def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p

def list_image_paths(image_folder: str) -> List[Path]:
    folder = Path(image_folder)
    if not folder.exists():
        raise FileNotFoundError(f"Image folder not found: {folder}")
    # Sort to keep deterministic order (tile_01, tile_02, …)
    return sorted([p for p in folder.iterdir() if p.suffix.lower() in (".png", ".jpg", ".jpeg")])

def upload_images(client: genai.Client, paths: List[Path]) -> Tuple[List[object], Dict[str, object]]:
    """
    Returns:
      contents: list of uploaded file handles (to be spread into 'contents')
      name_map: dict[stem] -> uploaded file handle
    """
    contents: List[object] = []
    name_map: Dict[str, object] = {}
    for p in paths:
        handle = client.files.upload(file=str(p))
        name_map[p.stem] = handle
        contents.append(handle)
    return contents, name_map

def build_sspm_prompt(application: str, url: str) -> str:
    # Parameterize app/url into the prompt if you want the model to echo them back.
    return f"""
You are an expert in SaaS Security Posture Management (SSPM). Given the following section of documentation from a SaaS platform, determine whether it describes a setting or configuration that can be transformed into an SSPM control.

If it qualifies as an SSPM control:
- Provide the name of the control
- Provide a description of the control and its rationale in 2-3 lines.
- Suggest the best-fitting category from the following:
  IAM (Manages digital identities and access rights; ensuring the right individuals have the right resource access at the right time)
  DLP (Prevents unauthorized access or leakage of sensitive data)
  Security (Protection against cybersecurity threats that are external to an organization)
  Productivity (Optimizes users' workflow efficiency and task management)
- Investigate the severity of the suggested control from a SSPM POV:
  Low, Medium, High
- Write the recommendation details in a user-friendly step-by-step format.

Respond in the following format:
Description: <description>
Category: <category>
Severity: <severity>
Recommendation Steps:
1) <step 1>
2) <step 2>
3) <step 3>
...

Extract the relevant details and return a structured JSON object in the following format:
[{{ 
  "name": "[Concise control title]",
  "description": "[What the control is about]",
  "category": "[IAM | DLP | Security | Productivity]",
  "severity": "[Low | Medium | High]",
  "recommendation_details": "[Steps or configuration needed to enforce or validate the control]"
}},{{...}}]

If it does not qualify as an SSPM control, simply return:
[]

Generate multiple controls if applicable, but ensure each control is distinct and relevant to the provided documentation section.

The response should be a JSON array of objects, each representing a control with the specified fields.
Ensure the response is well-structured and adheres to the JSON format.

Example 1:
Here is an example of a sample response:
[{{ 
  "application": "HubSpot",
  "url": "https://app-na2.hubspot.com/ai-settings/<organization_id>",
  "control_subject": "Use secure cookies only",
  "description": "By using secure cookies, data is exclusively transmitted over encrypted connections (HTTPS), thereby protecting it from interception by attackers and safeguarding privacy. This prevents man-in-the-middle attacks and aligns with modern web security standards.",
  "category": "Security",
  "severity": "High",
  "recommendations": ["1) Navigate to https://app-na2.hubspot.com/ai-settings/<organization_id>",
                      "2) From the side panel, under Account Management, select Tracking Code",
                      "3) Select the Advanced Tracking tab",
                      "4) Enable Use secure cookies only"]
}}]
"""

def call_gemini_json_text(
    client: genai.Client,
    model: str,
    text_prompt: str,
    image_contents: List[object]
) -> str:
    """
    For google-genai 1.29: Put instructions + images into 'contents'.
    """
    response = client.models.generate_content(
        model=model,
        contents=[text_prompt, *image_contents],
        config = {
        "response_mime_type": "application/json",
        "response_schema": list[Control],  
        }
    )

    return response.text or ""

def run_sspm_extraction(
    app_name: str,
    url: str,
    image_folder: str,
    model: str = DEFAULT_MODEL
) -> List[Control]:
    """
    High-level function:
      - loads client
      - uploads images in `image_folder`
      - builds prompt for `app_name`, `url`
      - calls Gemini and parses JSON into List[Control]
    """
    client = load_client()
    image_paths = list_image_paths(image_folder)
    if not image_paths:
        print(f"[i] No images found in {image_folder}. Returning empty list.")
        return []

    image_contents, _ = upload_images(client, image_paths)
    prompt = build_sspm_prompt(app_name, url)

    print("Calling Gemini API...")
    json_text = call_gemini_json_text(client, model, prompt, image_contents)
    if not json_text:
        print(f"[!] No JSON response from Gemini for {app_name}. Returning empty list.")
        return []

    # Ensure 'controls' folder exists
    output_dir = Path("controls") / APP_NAME
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Build filename: controls/<APP_NAME>/<APP_NAME>.json
    output_path = output_dir / f"{APP_NAME}_controls.json"

    # Save JSON data
    with open(output_path, "w") as f:
        json.dump(json_text, f, indent=2)

    print(f"[i] Saved controls to {output_path}")

# After you save raw JSON to controls/Dropbox_controls.json:
# pretty, xlsx = convert_controls("controls/Dropbox_controls.json")
# print(pretty, xlsx)



async def main():
    items = get_apps_from_user()
    if not items:
        print("Nothing to process.")
        return
    for app, login_url, controls_url, auth in items:
        await capture_app(app, login_url, auth, controls_url)
        run_sspm_extraction(app, controls_url, f"shots/{app}")

        pretty_json, xlsx = convert_controls(app)

        print("JSON and Excel files generated successfully.")

if __name__ == "__main__":
    asyncio.run(main())