# SSPM Control Scraper

A proof-of-concept tool for automating the generation of SaaS Security Posture Management (SSPM) controls using web scraping and generative AI. Built to accelerate the traditionally manual process of analyzing SaaS platform settings and creating security controls, this tool reduces time spent from ~8 hours to ~1 hour per platform.

---

## Summary

Creating SSPM controls for a new SaaS platform typically requires ~8 hours of manual analysis. This tool streamlines the process by extracting settings documentation from SaaS platforms, parsing it into logical sections, and using a GenAI model to identify and format relevant security controls. The final output is a structured CSV file ready for integration or human validation.

---

## Scope

This Proof of Concept (PoC) focuses on:

- Generating controls from a **single static webpage** per platform
- Validating core pipeline functionality (scraping → GenAI → CSV output)

**Out of Scope for PoC:**
- Multi-page navigation or redirection handling
- Anti-scraping protection (e.g. JavaScript rendering, CAPTCHA)
- Advanced authentication flows (e.g. MFA, OAuth)
- Dynamic or non-HTML content (e.g. PDFs, React-SPAs)
- Multilingual or non-standard documentation

These will be considered in future iterations post-PoC validation.

---

## GenAI Model Selection

After evaluating various LLMs, the following models were considered:

| Model               | Pros                                                                 | Cons                              |
|--------------------|----------------------------------------------------------------------|-----------------------------------|
| **GPT-4o (OpenAI)**| High accuracy, enterprise-ready, great at formatting and structure   | Highest cost                      |
| **Claude 4 Sonnet**| Excellent for security analysis and alignment                        | Expensive for marginal gains      |
| **Gemini 2.5 Pro** | Best context window (2M tokens), GCP integration, cost-effective     | Slightly less structured output   |

**Chosen Model:** `Google Gemini 2.5 Pro` — due to its balance of technical capabilities, cost-efficiency, and integration with Spin.AI's existing GCP credits.

---

## Flow & Logic

The tool accepts a target **URL** and optional **authentication credentials**, scrapes the page content, segments it, and sends each section to the GenAI model. Valid control sections are formatted into a standard CSV for export.

**Inputs:**
- URL of SaaS documentation/settings page
- Auth credentials (if needed)

**Output:**
- CSV file of structured SSPM controls

---

### Response Format:
```json
[{
  "name": "Use secure cookies only",
  "description": "Enforces HTTPS-only transmission for cookies, reducing risk of MITM attacks.",
  "category": "Security",
  "severity": "High",
  "resolution_details": [
    "Login to HubSpot",
    "Go to Settings → Tracking Code → Advanced Tracking",
    "Enable 'Use secure cookies only'"
  ]
}]
