package com.example;

import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.net.URI;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

import com.microsoft.playwright.Browser;
import com.microsoft.playwright.BrowserContext;
import com.microsoft.playwright.Frame;
import com.microsoft.playwright.Locator;
import com.microsoft.playwright.Page;
import com.microsoft.playwright.Playwright;
import com.microsoft.playwright.PlaywrightException;
import com.microsoft.playwright.options.LoadState;

public class App {

  // ---- timing knobs ----
  private static final int WAIT_AFTER_TOGGLE_MS = 500;   // wait after opening in-page panels
  private static final int WAIT_AFTER_NAV_MS    = 1200;  // wait after a drill-down navigation
  private static final int DOM_SETTLE_BUDGET_MS = 2500;  // max time to wait for DOM stability
  private static final int DOM_SETTLE_STEP_MS   = 120;   // polling cadence

  // file dumps
  private static int dumpIndex = 1;

  public static void main(String[] args) {
    String targetUrl = args.length > 0
        ? args[0]
        : "https://accounts.intuit.com/app/account-manager/security";

    try (Playwright playwright = Playwright.create()) {
      Browser browser = playwright.chromium().connectOverCDP("http://localhost:9222");

      // NOTE: Using the existing default context from your Chrome session.
      // If you want isolation, use: BrowserContext context = browser.newContext();
      BrowserContext context = browser.contexts().get(0);
      context.setDefaultTimeout(10000);

      Page page = context.newPage();
      page.setViewportSize(1400, 1600);
      page.setDefaultTimeout(10000);

      page.navigate(targetUrl);
      page.waitForLoadState(LoadState.NETWORKIDLE);
      waitForDomSettled(page, DOM_SETTLE_BUDGET_MS, DOM_SETTLE_STEP_MS);

      // Scan buttons, write lists, and click only non-navigation (same-page) ones
      scanButtonsAndAct(page, targetUrl);

      // dump the final main page once (NOT to stdout blob)
      dumpPage(page, "main");

      browser.close();
    } catch (Exception e) {
      e.printStackTrace();
    }
  }

  // ================== CONFIG ==================
  private static final String MENU_COUNT_JS =
      "() => document.querySelectorAll(\""
          + "[role='menu'],[role='listbox'],[role='tooltip'],[role='dialog'],"
          + "[data-vibe='Menu'],[data-popper-placement],"
          + ".popover,.dropdown,.dropdown-menu,.menu,.menu-open,"
          + "[data-menu],[data-popover],.MuiPopover-root,.MuiMenu-paper,"
          + ".ant-dropdown,.ant-dropdown-menu,.menu__content"
          + "\").length";

  private static final String TOGGLE_CANDIDATES = String.join(",",
      "[aria-controls]",
      "button[aria-expanded='false']",
      "summary",
      ".accordion button,.accordion__button,.accordion-button",
      "[data-accordion] button,[data-accordion-button]",
      "[data-testid*='accordion'],[data-testid*='Accordion'],[data-testid*='expand'],[data-testid*='Expand']",
      "[role=button][aria-expanded='false']",
      "a[role=button]",
      "button[data-testid='icon-button']",
      "button[data-vibe='Button'][data-testid='icon-button']",
      "button[data-vibe='Button']:has(svg)",
      "[data-vibe='Button']:has([data-testid='icon'])"
  );

  // Broad “button-like” candidates we’ll enumerate
  private static final String BUTTON_CANDIDATES = String.join(",",
      "button",
      "[role='button']",
      "a[role='button']",
      "input[type='button']",
      "input[type='submit']",
      "[data-testid*='button']",
      "[data-vibe='Button']",
      ".btn,.MuiButton-root,.ant-btn"
  );

  // ================== SCAN + CLICK NON-NAV (SAME-PAGE) ==================

  private static void scanButtonsAndAct(Page page, String originalUrl) {
    StringBuilder allOut = new StringBuilder();
    StringBuilder navOut = new StringBuilder();

    // scan main frame
    scanFrameButtons(page, page.mainFrame(), "main", originalUrl, allOut, navOut);

    // scan child frames
    for (Frame f : page.frames()) {
      if (f == page.mainFrame()) continue;
      String tag = "frame@" + safe(f.url());
      scanFrameButtons(page, f, tag, originalUrl, allOut, navOut);
    }

    // write files
    writeText("target/list.txt", allOut.toString());
    writeText("target/nav_buttons.txt", navOut.toString());
  }

  private static void scanFrameButtons(Page page, Frame f, String label,
                                       String originalUrl,
                                       StringBuilder allOut, StringBuilder navOut) {
    // IMPORTANT: Do NOT force-open <details>. We respect current expanded state.

    Locator buttons = f.locator(BUTTON_CANDIDATES);
    int n = buttons.count();
    int idx = 0;

    for (int i = 0; i < n; i++) {
      Locator el = buttons.nth(i);
      try {
        if (!el.isVisible() || !el.isEnabled()) continue;

        String sig = elementSignature(el);
        String tag = upperOr(el.evaluate("n => n.tagName"));
        String id  = safe(el.getAttribute("id"));
        String cls = upperOr(el.evaluate("n => n.className || ''"));
        String role = lowerOr(el.getAttribute("role"));
        String type = lowerOr(el.getAttribute("type"));
        String text = trimMax(upperOr(el.evaluate("n => (n.innerText||n.textContent||'')")), 140)
                        .replace("\n", " ").replace("\r", " ").trim();
        String ariaLabel = safe(el.getAttribute("aria-label"));
        String ariaCtrl  = safe(el.getAttribute("aria-controls"));
        String ariaExp   = safe(el.getAttribute("aria-expanded"));
        String hrefSelf  = safe(el.getAttribute("href"));
        String hrefNear  = safe((String) el.evaluate("n => { const a=n.closest('a[href]'); return a ? a.getAttribute('href') : null; }"));
        String targetAttr= safe(el.getAttribute("target"));
        String onclick   = safe(el.getAttribute("onclick"));
        String dataHref  = safe(el.getAttribute("data-href"));
        String dataUrl   = safe(el.getAttribute("data-url"));
        String dataTo    = safe(el.getAttribute("to"));
        String routerLnk = safe(el.getAttribute("routerlink"));
        String formAct   = safe((String) el.evaluate("n => { const f=n.closest('form'); return f ? f.getAttribute('action') : null; }"));

        boolean hasRealCtrl = hasRealControls(f.page(), el);

        // Compute resolved href and same-page flag
        String hrefA = firstNonEmpty(hrefSelf, hrefNear);
        String resolvedHref = resolveUrl(f.url(), hrefA);
        boolean samePage = isSamePageUrl(f.url(), hrefA);

        // Decide if it's likely navigation (not same-page) vs in-page
        boolean navLike = isLikelyNavigation(
            f.url(), tag, role, hrefSelf, hrefNear,
            onclick, dataHref, dataUrl, dataTo, routerLnk,
            type, formAct, targetAttr
        );
        boolean isNav = navLike && !hasRealCtrl; // aria-controls wins: treat as in-page toggle

        // Expanded state check: if it's already expanded, leave it as-is
        boolean alreadyExpanded = isExpanded(f, el);

        // log line
        String line = String.format(
            Locale.ROOT,
            "%s | #%03d | %s | NAV=%s | SAMEPAGE=%s | EXPANDED=%s | tag=%s role=%s type=%s | text=\"%s\" | id=%s | href=%s | nearHref=%s | resolvedHref=%s | aria-controls=%s aria-expanded=%s | class=\"%s\" | sig=\"%s\"%n",
            label, (++idx), f.url(),
            isNav ? "YES" : "NO",
            samePage ? "YES" : "NO",
            alreadyExpanded ? "YES" : "NO",
            tag, role, type, text, id,
            hrefSelf, hrefNear, resolvedHref,
            ariaCtrl, ariaExp, cls, sig
        );
        allOut.append(line);
        if (isNav) navOut.append(line);

        // click only non-nav (in-page / same-page) and only if NOT already expanded
        if (!isNav && !alreadyExpanded) {
          safeClickInPage(f, el, originalUrl); // pass original URL for recovery
        }
      } catch (PlaywrightException ignore) {
        // continue
      }
    }
  }

  /**
   * Treat as navigation if:
   * - target="_blank", OR
   * - href exists and DOES NOT resolve to the same origin+path as baseUrl, OR
   * - role=link and not same-page, OR
   * - obvious JS/router nav signals, OR
   * - form submit to real action
   * (If aria-controls points to a real element, the caller will override and treat as in-page.)
   */
  private static boolean isLikelyNavigation(
      String baseUrl,
      String tag, String role, String hrefSelf, String hrefNear,
      String onclick, String dataHref, String dataUrl, String dataTo, String routerLnk,
      String type, String formAct, String targetAttr
  ) {
    String hrefA = firstNonEmpty(hrefSelf, hrefNear);
    boolean hasHref = hrefA != null && !hrefA.isEmpty()
        && !hrefA.equals("#")
        && !hrefA.toLowerCase(Locale.ROOT).startsWith("javascript:");

    boolean samePageHref = hasHref && isSamePageUrl(baseUrl, hrefA);
    boolean targetBlank = "_blank".equalsIgnoreCase(safe(targetAttr));
    boolean roleLink = "link".equalsIgnoreCase(safe(role));

    boolean onclickNav = onclick != null && onclick.matches("(?i).*(location\\.|window\\.open|document\\.location|href\\s*=).*");
    boolean dataNav = anyNonEmpty(dataHref, dataUrl, dataTo, routerLnk);

    boolean submitLike = "submit".equalsIgnoreCase(safe(type)) || "BUTTON".equalsIgnoreCase(safe(tag));
    boolean formNav = submitLike && formAct != null && !formAct.isEmpty()
        && !formAct.startsWith("#")
        && !formAct.toLowerCase(Locale.ROOT).startsWith("javascript:");

    if (targetBlank) return true;
    if (hasHref && !samePageHref) return true;
    if (roleLink && !samePageHref) return true;
    if (onclickNav) return true;
    if (dataNav) return true;
    if (formNav) return true;

    return false; // treat as in-page (same-page) otherwise
  }

  /** True if the control already looks expanded (so we should not click it). */
  private static boolean isExpanded(Frame f, Locator el) {
    try {
      // aria-expanded=true => expanded
      String ariaExp = safe(el.getAttribute("aria-expanded"));
      if ("true".equalsIgnoreCase(ariaExp)) return true;

      // Real controlled region visible?
      String id = el.getAttribute("aria-controls");
      if (id != null && !id.isEmpty()) {
        Locator region = f.locator("#" + cssEscape(id));
        if (region.count() > 0) {
          try { if (region.isVisible()) return true; } catch (PlaywrightException ignore) {}
        }
      }

      // <details open> on closest details wrapper => expanded
      Boolean detailsOpen = (Boolean) el.evaluate("n => { const d = n.closest('details'); return !!(d && d.open === true); }");
      if (Boolean.TRUE.equals(detailsOpen)) return true;

    } catch (PlaywrightException ignore) {}
    return false;
  }

  /**
   * Click an element; if a popup opens, close only the newly created page(s).
   * If this page's URL changes, navigate back to the originalUrl.
   */
  private static void safeClickInPage(Frame f, Locator el, String originalUrl) {
    try {
      Page p = f.page();
      BrowserContext ctx = p.context();

      int menusBefore = ((Number) f.evaluate(MENU_COUNT_JS)).intValue();
      long heightBefore = ((Number) f.evaluate("() => document.body ? document.body.scrollHeight : 0")).longValue();

      // Baselines to detect navigation/popups
      String urlBefore = p.url();
      List<Page> before = new ArrayList<>(ctx.pages()); // snapshot pre-existing tabs

      el.scrollIntoViewIfNeeded();
      try { el.hover(); } catch (PlaywrightException ignore) {}
      el.click(new Locator.ClickOptions().setNoWaitAfter(true).setTimeout(3000));

      long start = System.currentTimeMillis();
      while (System.currentTimeMillis() - start < 1500) {
        // Consider opened if aria-expanded flips, controlled region becomes visible,
        // new menu appears, or page height grows.
        String ex = el.getAttribute("aria-expanded");
        if ("true".equalsIgnoreCase(safe(ex))) break;
        String id = el.getAttribute("aria-controls");
        if (id != null && !id.isEmpty() && f.locator("#" + cssEscape(id)).isVisible()) break;

        int menusAfter = ((Number) f.evaluate(MENU_COUNT_JS)).intValue();
        if (menusAfter > menusBefore) break;

        long hAfter = ((Number) f.evaluate("() => document.body ? document.body.scrollHeight : 0")).longValue();
        if (hAfter > heightBefore) break;

        f.waitForTimeout(90);
      }
      f.waitForTimeout(WAIT_AFTER_TOGGLE_MS);
      waitForDomSettled(f.page(), DOM_SETTLE_BUDGET_MS, DOM_SETTLE_STEP_MS);

      // Close ONLY the pages that were created by this click (set-diff)
      List<Page> after = ctx.pages();
      for (Page other : after) {
        if (other != p && !before.contains(other)) {
          try { other.close(); } catch (PlaywrightException ignore) {}
        }
      }

      // If URL changed (SPA or hard nav), go back to the original URL on this page only
      String urlAfter = p.url();
      if (!originalUrl.equals(urlAfter)) {
        try {
          p.navigate(originalUrl);
          p.waitForLoadState(LoadState.NETWORKIDLE);
          waitForDomSettled(p, DOM_SETTLE_BUDGET_MS, DOM_SETTLE_STEP_MS);
        } catch (PlaywrightException ignore) {}
      }

    } catch (PlaywrightException ignore) {
    }
  }

  // ================== DOM + UTILS ==================

  private static void waitForDomSettled(Page page, int budgetMs, int stepMs) {
    long deadline = System.currentTimeMillis() + budgetMs;
    long lastH = -1, lastT = -1;
    int stableRounds = 0;

    while (System.currentTimeMillis() < deadline) {
      Number h = (Number) page.evaluate("() => document.body ? document.body.scrollHeight : 0");
      Number t = (Number) page.evaluate("() => document.body ? document.body.innerText.length : 0");
      long hh = h.longValue(), tt = t.longValue();

      if (hh == lastH && tt == lastT) {
        stableRounds++;
        if (stableRounds >= 3) break;
      } else {
        stableRounds = 0;
        lastH = hh; lastT = tt;
      }
      page.waitForTimeout(stepMs);
    }
  }

  private static boolean hasRealControls(Page page, Locator el) {
    String id = el.getAttribute("aria-controls");
    if (id == null || id.isEmpty()) return false;
    try { return (Boolean) page.evaluate("id => !!document.getElementById(id)", id); }
    catch (PlaywrightException e) { return false; }
  }

  private static String elementSignature(Locator el) {
    try {
      String sig = (String) el.evaluate(
          "n => [n.tagName, n.id, n.getAttribute('aria-controls'),"
              + " n.getAttribute('data-testid'), n.getAttribute('aria-label'),"
              + " n.className, (n.innerText||'').slice(0,40)].join('|')"
      );
      return sig == null ? "null" : sig;
    } catch (PlaywrightException e) {
      return "ex";
    }
  }

  private static String safe(String s) { return s == null ? "" : s.trim(); }
  private static String upperOr(Object s) { return s == null ? "" : String.valueOf(s); }
  private static String lowerOr(String s) { return s == null ? "" : s.toLowerCase(Locale.ROOT); }
  private static String trimMax(String s, int max) { return s.length() <= max ? s : s.substring(0, s.length() - 1) + "…"; }

  private static String cssEscape(String id) {
    return id.replace("\\", "\\\\")
             .replace(".", "\\.")
             .replace("#", "\\#")
             .replace(" ", "\\ ");
  }

  private static String firstNonEmpty(String... vals) {
    for (String v : vals) if (v != null && !v.isEmpty()) return v;
    return null;
  }
  private static boolean anyNonEmpty(String... vals) {
    for (String v : vals) if (v != null && !v.isEmpty()) return true;
    return false;
  }

  // ---- URL helpers ----

  private static String resolveUrl(String baseUrl, String href) {
    try {
      if (href == null || href.isEmpty()) return "";
      if ("#".equals(href) || href.trim().toLowerCase(Locale.ROOT).startsWith("javascript:")) return "";
      URI base = new URI(baseUrl);
      URI abs = base.resolve(href).normalize();
      return abs.toString();
    } catch (Exception e) {
      return "";
    }
  }

  /** Same origin+path (ignores hash). If query differs, treat as navigation (conservative). */
  private static boolean isSamePageUrl(String baseUrl, String href) {
    try {
      if (href == null || href.isEmpty() || "#".equals(href)) return true; // naked anchors -> same page
      URI base = new URI(baseUrl).normalize();
      URI abs  = base.resolve(href).normalize();

      // scheme/host/port
      if (!safe(base.getScheme()).equalsIgnoreCase(safe(abs.getScheme()))) return false;
      if (!safe(base.getHost()).equalsIgnoreCase(safe(abs.getHost()))) return false;
      int bp = effectivePort(base);
      int ap = effectivePort(abs);
      if (bp != ap) return false;

      // path (strip trailing slash)
      String p1 = stripTrailingSlash(safe(base.getPath()));
      String p2 = stripTrailingSlash(safe(abs.getPath()));
      if (!p1.equals(p2)) return false;

      // query: if different, count as navigation (change to 'return true' to ignore query diffs)
      String q1 = safe(base.getQuery());
      String q2 = safe(abs.getQuery());
      return q1.equals(q2);
    } catch (Exception e) {
      return false;
    }
  }

  private static int effectivePort(URI uri) {
    int p = uri.getPort();
    if (p != -1) return p;
    String scheme = safe(uri.getScheme()).toLowerCase(Locale.ROOT);
    if ("http".equals(scheme)) return 80;
    if ("https".equals(scheme)) return 443;
    return -1;
  }

  private static String stripTrailingSlash(String s) {
    if (s == null) return "";
    if (s.endsWith("/") && s.length() > 1) return s.substring(0, s.length() - 1);
    return s;
  }

  // ---- per-page file dump instead of stdout blob ----
  private static synchronized String nextDumpPath(String prefix) {
    String name = String.format("target/dumps/%03d_%s.html", dumpIndex++, prefix);
    return name;
  }

  private static void dumpPage(Page p, String prefix) {
    String html = p.content();
    String path = nextDumpPath(prefix);
    File out = new File(path);
    out.getParentFile().mkdirs();
    try (FileWriter w = new FileWriter(out)) {
      w.write(html);
    } catch (IOException e) {
      System.err.println("Error writing " + path + ": " + e.getMessage());
    }
    System.out.println("<!-- DUMPED " + p.url() + " -> " + out.getAbsolutePath() + " -->");
  }

  // write text files
  private static void writeText(String path, String content) {
    try {
      File out = new File(path);
      out.getParentFile().mkdirs();
      try (FileWriter w = new FileWriter(out)) {
        w.write(content == null ? "" : content);
      }
      System.out.println("WROTE " + out.getAbsolutePath());
    } catch (IOException e) {
      System.err.println("Error writing " + path + ": " + e.getMessage());
    }
  }
}
