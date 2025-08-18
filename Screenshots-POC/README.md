# Automated SaaS Security Controls Extractor using Screenshots and LLM

## Introduction

__Screenshots-POC__ automates SaaS Security Posture Management (SSPM) data collection. It signs in to __SaaS admin pages__ (with your manual first-time login), captures full, scrollable screenshots of settings pages using __Playwright__, and sends those images to __Gemini__ to extract structured controls. The tool then normalizes the output and writes both a readable __JSON__ file and a formatted __Excel__ workbook you can review, share, or import into other systems.

Typical use cases:

* Build a baseline of security controls across many SaaS apps
* Speed up documentation by turning screenshots into structured evidence

## Features

* __Headful Playwright capture__ — manual SSO/MFA once, then reuse the saved storage state per app.
* __Robust full-page tiling__ — auto-detects the main scroll container, neutralizes sticky headers, and stitches tiles so you don’t miss content below the fold.
* __Multi-app workflow__ — prompts for app name, login URL, and target settings URL; organizes screenshots and outputs per app.
* __LLM-powered control extraction__ — sends screenshots to Gemini and returns a structured JSON array of controls with description, category (IAM/DLP/Security/Productivity), severity, and recommendations.
* __Clean exports__

    * Pretty, human-readable JSON
    * Excel (.xlsx) with wrapped, numbered steps (1), 2), 3)…) for easy reading

* __Deterministic file layout__ — creates auth/, shots/, and controls/ folders on demand; keeps outputs in a consistent per-app structure.
* __Extensible & typed__ — Pydantic models for future validation, easy to swap/upgrade the model or add custom post-processing.

## Project Structure

    ├── Screenshots-POC/
    │   ├── README.md
    │   ├── requirements.txt
    │   ├── saas_control_extractor.py
    │   ├── controls_converter.py
    │   ├── .env
    │   ├── auth/
    │   │   └── <APP>.json
    │   ├── shots/
    │   │   └── <APP>
    │   │   │   └── <APP>_01.png
    │   │   │   └── <APP>_02.png    
    │   ├── controls/
    │   │   │   └── <APP>_controls.json
    │   │   │   └── <APP>_pretty.json
    │   │   │   └── <APP>.xlsx
    │   ├── Dropbox_Example/
    

## Installation and Setup

To try the project, follow the steps as below:
* Create a Python virtual environment
    ```
    python -m venv .venv
    source .venv/bin/activate   # Windows: .venv\Scripts\activate
    ```
* Install the required Python packages: `pip install -r requirements.txt`

    ```
    pip install -r requirements.txt
    # If using Playwright for the first time:
    python -m playwright install chromium
    ```

* Create `.env` file with `GEMINI_API_KEY`:`<YOUR_API_KEY>`
* Execute Python File as `python saas_control_extractor.py`
* Enter application name, URL of the login page of the application and the URL of the page from where you want to generate the security controls.
* For this project, manual authentication for SaaS application is required for the first time.
    * After the login is successful, `<APP>.json` containing authentication details is saved inside `auth/` folder.
    * The subsequent login attempts to capture screenshots will use the same `<APP>.json` file for same application. __Note__: Authentication might not be successful in case of old `<APP>.json` file as they might be expired. So just delete that file and log in again.
* When the run finishes, the Excel(`.xlsx`) and pretty JSON(`.json`) will be generated under `controls/<APP>/..` folder as `<APP>_controls.json` and `<APP>_pretty.json`

## Examples

See `Dropbox_Example/` for a full set: authentication files, screeenshots of the SaaS application captured and automated controls in `.json` and `.xlsx` format.
