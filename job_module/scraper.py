# job_module/scraper.py
# ============================================================
# Enhanced Real-Time Job Scraper using Playwright
# Sources: RemoteOK, LinkedIn (India), WeWorkRemotely,
#          Naukri.com, Indeed India
# Supports: location + experience-based filtering
# ============================================================

from __future__ import annotations

import re
import time
from typing import Any

from playwright.sync_api import (
    Browser, Page, sync_playwright,
    TimeoutError as PWTimeout,
)

from job_module.config import (
    SCRAPE_LOCATION, SCRAPE_MAX_JOBS, SCRAPE_QUERY,
    SCRAPER_HEADLESS, SCRAPER_TIMEOUT_MS,
)
from job_module.logger import get_logger

logger = get_logger(__name__)

RawJob = dict[str, str]

_HEADERS = {
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


# ════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════

def _clean(text: str | None) -> str:
    if not text:
        return "N/A"
    return re.sub(r"\s+", " ", str(text).strip()) or "N/A"


def _safe_text(page: Page, selector: str, default: str = "N/A") -> str:
    try:
        el = page.query_selector(selector)
        return _clean(el.inner_text()) if el else default
    except Exception:
        return default


def _scroll(page: Page, pause: float = 1.2, max_scrolls: int = 6) -> None:
    prev_h = 0
    for _ in range(max_scrolls):
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(pause)
        new_h = page.evaluate("document.body.scrollHeight")
        if new_h == prev_h:
            break
        prev_h = new_h


def _q(text: str) -> str:
    """URL-encode a query string."""
    return text.replace(" ", "%20").replace("+", "%2B")


# ════════════════════════════════════════════════════════════
# Source 1 — RemoteOK
# ════════════════════════════════════════════════════════════

def _scrape_remoteok(page: Page, query: str, max_jobs: int) -> list[RawJob]:
    jobs: list[RawJob] = []
    intercepted: list[dict] = []

    def on_response(response):
        if "remoteok.com/remote-jobs.json" in response.url:
            try:
                data = response.json()
                if isinstance(data, list):
                    intercepted.extend(data)
            except Exception:
                pass

    page.on("response", on_response)
    logger.info("🌐 Opening RemoteOK …")
    try:
        page.goto("https://remoteok.com/remote-dev-jobs", wait_until="networkidle", timeout=SCRAPER_TIMEOUT_MS)
    except PWTimeout:
        logger.warning("RemoteOK timed-out; using partial load.")

    _scroll(page)

    if intercepted:
        slug_re = re.compile(re.escape(query.lower().replace(" ", "-")), re.I)
        for item in intercepted:
            if not isinstance(item, dict):
                continue
            tags = " ".join(item.get("tags", [])).lower()
            position = (item.get("position") or "").lower()
            if query.lower() not in position and not slug_re.search(tags):
                continue
            jobs.append({
                "title": _clean(item.get("position")),
                "company": _clean(item.get("company")),
                "location": _clean(item.get("location") or "Remote"),
                "salary": _clean(item.get("salary")),
                "skills": _clean(", ".join(item.get("tags", []))),
                "description": _clean(item.get("description", "")[:500]),
                "apply_link": f"https://remoteok.com/l/{item.get('slug', '')}",
                "experience": "N/A",
                "source": "RemoteOK",
            })
            if len(jobs) >= max_jobs:
                break

    if not jobs:
        for row in page.query_selector_all("tr.job")[:max_jobs]:
            try:
                title = _clean(row.query_selector("td.company h2").inner_text() if row.query_selector("td.company h2") else None)
                company = _clean(row.query_selector("td.company h3").inner_text() if row.query_selector("td.company h3") else None)
                location = _clean(row.query_selector(".location").inner_text() if row.query_selector(".location") else "Remote")
                tags = [_clean(t.inner_text()) for t in row.query_selector_all(".tag")]
                link = row.query_selector("a.preventLink")
                href = link.get_attribute("href") if link else ""
                if title == "N/A":
                    continue
                jobs.append({
                    "title": title, "company": company, "location": location,
                    "salary": "N/A", "skills": ", ".join(tags),
                    "description": "N/A", "experience": "N/A",
                    "apply_link": f"https://remoteok.com{href}" if href else "N/A",
                    "source": "RemoteOK",
                })
            except Exception as exc:
                logger.debug("RemoteOK DOM error: %s", exc)

    logger.info("RemoteOK: %d jobs", len(jobs))
    return jobs


# ════════════════════════════════════════════════════════════
# Source 2 — LinkedIn (supports India + global)
# ════════════════════════════════════════════════════════════

def _scrape_linkedin(page: Page, query: str, location: str, max_jobs: int) -> list[RawJob]:
    jobs: list[RawJob] = []
    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={_q(query)}&location={_q(location)}"
        f"&trk=public_jobs_jobs-search-bar_search-submit&position=1&pageNum=0"
    )
    logger.info("🌐 Opening LinkedIn …")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=SCRAPER_TIMEOUT_MS)
    except PWTimeout:
        logger.warning("LinkedIn timed-out; using partial load.")

    for _ in range(4):
        _scroll(page, pause=1.5, max_scrolls=3)
        if len(page.query_selector_all("div.base-card")) >= max_jobs:
            break
        try:
            btn = page.query_selector("button.infinite-scroller__show-more-button")
            if btn:
                btn.click()
                page.wait_for_timeout(2000)
        except Exception:
            break

    for card in page.query_selector_all("div.base-card")[:max_jobs]:
        try:
            title_el    = card.query_selector("h3.base-search-card__title")
            company_el  = card.query_selector("h4.base-search-card__subtitle")
            location_el = card.query_selector("span.job-search-card__location")
            link_el     = card.query_selector("a.base-card__full-link")
            metadata_el = card.query_selector("div.base-search-card__metadata")

            title       = _clean(title_el.inner_text() if title_el else None)
            company     = _clean(company_el.inner_text() if company_el else None)
            location_t  = _clean(location_el.inner_text() if location_el else None)
            apply_link  = link_el.get_attribute("href") if link_el else "N/A"
            # Extract experience from metadata (e.g. "2-5 years")
            meta_text   = _clean(metadata_el.inner_text() if metadata_el else "")

            if title == "N/A":
                continue

            # Fetch description from detail page
            description = "N/A"
            if apply_link and apply_link != "N/A":
                try:
                    dp = page.context.new_page()
                    dp.goto(apply_link, wait_until="domcontentloaded", timeout=15_000)
                    desc_el = dp.query_selector("div.show-more-less-html__markup")
                    if desc_el:
                        description = _clean(desc_el.inner_text()[:600])
                    # Try to extract experience from job description
                    exp_match = re.search(r"(\d+[\+\-]?\s*(?:to\s*\d+\s*)?years?)", description, re.I)
                    experience = exp_match.group(1) if exp_match else "N/A"
                    dp.close()
                except Exception as de:
                    logger.debug("LinkedIn detail error: %s", de)
                    experience = "N/A"
            else:
                experience = "N/A"

            jobs.append({
                "title": title, "company": company, "location": location_t,
                "salary": "N/A", "skills": "N/A",
                "description": description, "experience": experience,
                "apply_link": apply_link, "source": "LinkedIn",
            })
        except Exception as exc:
            logger.debug("LinkedIn card error: %s", exc)

    logger.info("LinkedIn: %d jobs", len(jobs))
    return jobs


# ════════════════════════════════════════════════════════════
# Source 3 — We Work Remotely
# ════════════════════════════════════════════════════════════

def _scrape_weworkremotely(page: Page, query: str, max_jobs: int) -> list[RawJob]:
    jobs: list[RawJob] = []
    url = f"https://weworkremotely.com/remote-jobs/search?term={query.replace(' ', '+')}"
    logger.info("🌐 Opening We Work Remotely …")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=SCRAPER_TIMEOUT_MS)
    except PWTimeout:
        logger.warning("WWR timed-out.")

    _scroll(page, pause=1.0)
    for art in page.query_selector_all("section.jobs article")[:max_jobs]:
        try:
            title_el   = art.query_selector("span.title")
            company_el = art.query_selector("span.company")
            region_el  = art.query_selector("span.region")
            link_el    = art.query_selector("a")

            title   = _clean(title_el.inner_text() if title_el else None)
            company = _clean(company_el.inner_text() if company_el else None)
            location = _clean(region_el.inner_text() if region_el else "Remote")
            href    = link_el.get_attribute("href") if link_el else ""

            if title == "N/A":
                continue

            jobs.append({
                "title": title, "company": company, "location": location,
                "salary": "N/A", "skills": "N/A", "description": "N/A",
                "experience": "N/A",
                "apply_link": f"https://weworkremotely.com{href}" if href else "N/A",
                "source": "WeWorkRemotely",
            })
        except Exception as exc:
            logger.debug("WWR error: %s", exc)

    logger.info("WWR: %d jobs", len(jobs))
    return jobs


# ════════════════════════════════════════════════════════════
# Source 4 — Naukri.com (India)
# ════════════════════════════════════════════════════════════

def _scrape_naukri(page: Page, query: str, location: str, experience: str, max_jobs: int) -> list[RawJob]:
    """
    Scrapes Naukri.com with keyword + location + experience filters.
    experience: e.g. "0", "1", "2-5" — years of experience
    """
    jobs: list[RawJob] = []

    # Build Naukri URL  — experience range: expMin, expMax
    exp_min, exp_max = "0", "5"
    if experience and experience != "N/A":
        m = re.match(r"(\d+)\s*[-–to]+\s*(\d+)", experience)
        if m:
            exp_min, exp_max = m.group(1), m.group(2)
        elif re.match(r"^\d+", experience):
            exp_min = re.match(r"(\d+)", experience).group(1)
            exp_max = str(int(exp_min) + 3)

    # Naukri search URL pattern
    q_slug = query.lower().replace(" ", "-")
    loc_slug = location.lower().replace(" ", "-") if location and location.lower() not in ("remote", "n/a") else ""
    url = f"https://www.naukri.com/{q_slug}-jobs" + (f"-in-{loc_slug}" if loc_slug else "") + \
          f"?experience={exp_min}&to={exp_max}"

    logger.info("🌐 Opening Naukri.com …")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=SCRAPER_TIMEOUT_MS)
        page.wait_for_timeout(3000)   # Naukri is JS-heavy
    except PWTimeout:
        logger.warning("Naukri timed-out.")

    _scroll(page, pause=1.5)

    # Naukri job card selectors (may change; fallback included)
    cards = page.query_selector_all("article.jobTuple") or page.query_selector_all("div.jobTupleHeader")
    if not cards:
        cards = page.query_selector_all("[class*='jobTuple']")

    logger.info("Naukri: found %d raw cards", len(cards))

    for card in cards[:max_jobs]:
        try:
            title_el   = card.query_selector("a.title") or card.query_selector("a[title]")
            company_el = card.query_selector("a.subTitle") or card.query_selector("[class*='companyName']")
            exp_el     = card.query_selector("li.experience") or card.query_selector("[class*='experience']")
            salary_el  = card.query_selector("li.salary") or card.query_selector("[class*='salary']")
            location_el = card.query_selector("li.location") or card.query_selector("[class*='location']")
            skills_el  = card.query_selector("ul.tags") or card.query_selector("[class*='tag']")
            desc_el    = card.query_selector("div.job-description") or card.query_selector("[class*='jobDesc']")

            title       = _clean(title_el.inner_text() if title_el else None)
            company     = _clean(company_el.inner_text() if company_el else None)
            exp_text    = _clean(exp_el.inner_text() if exp_el else experience or "N/A")
            salary      = _clean(salary_el.inner_text() if salary_el else "N/A")
            location_t  = _clean(location_el.inner_text() if location_el else location)
            skills      = _clean(skills_el.inner_text() if skills_el else "N/A")
            description = _clean(desc_el.inner_text()[:400] if desc_el else "N/A")
            apply_link  = title_el.get_attribute("href") if title_el else "N/A"

            if title == "N/A":
                continue

            if not apply_link.startswith("http"):
                apply_link = f"https://www.naukri.com{apply_link}"

            jobs.append({
                "title": title, "company": company, "location": location_t,
                "salary": salary, "skills": skills,
                "description": description, "experience": exp_text,
                "apply_link": apply_link, "source": "Naukri",
            })
        except Exception as exc:
            logger.debug("Naukri card error: %s", exc)

    logger.info("Naukri: %d jobs", len(jobs))
    return jobs


# ════════════════════════════════════════════════════════════
# Source 5 — Indeed India
# ════════════════════════════════════════════════════════════

def _scrape_indeed_india(page: Page, query: str, location: str, experience: str, max_jobs: int) -> list[RawJob]:
    """
    Scrapes Indeed India with keyword + location + experience filters.
    """
    jobs: list[RawJob] = []

    # Build experience param for Indeed (years range)
    exp_param = ""
    if experience and experience != "N/A":
        m = re.match(r"(\d+)", experience)
        if m:
            yrs = int(m.group(1))
            if yrs <= 1:
                exp_param = "&explvl=entry_level"
            elif yrs <= 5:
                exp_param = "&explvl=mid_level"
            else:
                exp_param = "&explvl=senior_level"

    loc = location if location and location.lower() not in ("remote",) else "India"
    url = (
        f"https://in.indeed.com/jobs?q={_q(query)}&l={_q(loc)}"
        f"&sort=date{exp_param}"
    )

    logger.info("🌐 Opening Indeed India …")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=SCRAPER_TIMEOUT_MS)
        page.wait_for_timeout(2000)
    except PWTimeout:
        logger.warning("Indeed India timed-out.")

    _scroll(page, pause=1.0)

    cards = page.query_selector_all("div.job_seen_beacon") or page.query_selector_all("td.resultContent")
    if not cards:
        cards = page.query_selector_all("[class*='jobCard']") or page.query_selector_all("div.result")

    logger.info("Indeed India: found %d raw cards", len(cards))

    for card in cards[:max_jobs]:
        try:
            title_el    = card.query_selector("h2.jobTitle a") or card.query_selector("a[data-jk]")
            company_el  = card.query_selector("span.companyName") or card.query_selector("[class*='company']")
            location_el = card.query_selector("div.companyLocation") or card.query_selector("[class*='location']")
            salary_el   = card.query_selector("div.salary-snippet-container") or card.query_selector("[class*='salary']")
            desc_el     = card.query_selector("div.job-snippet") or card.query_selector("[class*='snippet']")
            badge_el    = card.query_selector("div.jobMetaDataGroup") or card.query_selector("[class*='metadata']")

            title       = _clean(title_el.inner_text() if title_el else None)
            company     = _clean(company_el.inner_text() if company_el else None)
            location_t  = _clean(location_el.inner_text() if location_el else loc)
            salary      = _clean(salary_el.inner_text() if salary_el else "N/A")
            description = _clean(desc_el.inner_text()[:400] if desc_el else "N/A")
            meta        = _clean(badge_el.inner_text() if badge_el else "")

            # Extract experience from description or metadata
            exp_match = re.search(r"(\d+[\+\-]?\s*(?:to\s*\d+\s*)?years?)", description + " " + meta, re.I)
            exp_text  = exp_match.group(1) if exp_match else (experience or "N/A")

            href = title_el.get_attribute("href") if title_el else ""

            if title == "N/A":
                continue

            apply_link = f"https://in.indeed.com{href}" if href and href.startswith("/") else href or "N/A"

            jobs.append({
                "title": title, "company": company, "location": location_t,
                "salary": salary, "skills": "N/A",
                "description": description, "experience": exp_text,
                "apply_link": apply_link, "source": "Indeed India",
            })
        except Exception as exc:
            logger.debug("Indeed card error: %s", exc)

    logger.info("Indeed India: %d jobs", len(jobs))
    return jobs


# ════════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════════

def scrape_jobs(
    query: str = SCRAPE_QUERY,
    location: str = SCRAPE_LOCATION,
    max_jobs: int = SCRAPE_MAX_JOBS,
    experience: str = "",
    sources: list[str] | None = None,
) -> list[RawJob]:
    """
    Scrape jobs from all configured sources.

    Args:
        query:      Search keyword (e.g. "Python developer")
        location:   Location filter (e.g. "Bangalore", "Remote")
        max_jobs:   Total cap on returned jobs
        experience: Experience filter (e.g. "2-5", "3+") — used on Naukri/Indeed
        sources:    Optional list to limit sources, e.g. ["naukri", "linkedin"]
                    Defaults to all: ["remoteok", "linkedin", "wwr", "naukri", "indeed"]

    Returns:
        Deduplicated list of raw job dicts.
    """
    if sources is None:
        sources = ["remoteok", "linkedin", "wwr", "naukri", "indeed"]

    all_jobs: list[RawJob] = []
    per_source = max(1, max_jobs // len(sources))

    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch(
            headless=SCRAPER_HEADLESS,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            user_agent=_HEADERS["user_agent"],
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        context.set_default_timeout(SCRAPER_TIMEOUT_MS)

        try:
            source_map = {
                "remoteok": lambda: _scrape_remoteok(context.new_page(), query, per_source),
                "linkedin": lambda: _scrape_linkedin(context.new_page(), query, location, per_source),
                "wwr":      lambda: _scrape_weworkremotely(context.new_page(), query, per_source),
                "naukri":   lambda: _scrape_naukri(context.new_page(), query, location, experience, per_source),
                "indeed":   lambda: _scrape_indeed_india(context.new_page(), query, location, experience, per_source),
            }

            for src in sources:
                if src not in source_map:
                    logger.warning("Unknown source: %s", src)
                    continue
                try:
                    jobs = source_map[src]()
                    all_jobs.extend(jobs)
                    logger.info("Source '%s': collected %d jobs", src, len(jobs))
                except Exception as exc:
                    logger.error("Source '%s' crashed: %s", src, exc)

        finally:
            browser.close()

    # Deduplicate by (title, company)
    seen: set[tuple[str, str]] = set()
    unique: list[RawJob] = []
    for job in all_jobs:
        key = (job["title"].lower(), job["company"].lower())
        if key not in seen and job["title"] != "N/A":
            seen.add(key)
            unique.append(job)

    logger.info("✅ Scraping done — %d unique / %d raw", len(unique), len(all_jobs))
    return unique[:max_jobs]
