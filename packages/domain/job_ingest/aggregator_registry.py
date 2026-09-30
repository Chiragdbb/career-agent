"""Registry and heuristics for third-party job aggregators (any host, not only LinkedIn/Naukri)."""

from __future__ import annotations

import os
import re
from urllib.parse import parse_qs, urlparse

# Known aggregator / job-board hosts (suffix match). Extend via AGGREGATOR_EXTRA_HOSTS.
AGGREGATOR_HOST_SUFFIXES: tuple[str, ...] = (
    "linkedin.com",
    "naukri.com",
    "indeed.com",
    "glassdoor.com",
    "ziprecruiter.com",
    "monster.com",
    "careerbuilder.com",
    "simplyhired.com",
    "dice.com",
    "shine.com",
    "timesjobs.com",
    "foundit.in",
    "instahyre.com",
    "hirect.in",
    "wellfound.com",
    "angel.co",
    "angellist.com",
    "flexjobs.com",
    "remote.co",
    "weworkremotely.com",
    "builtin.com",
    "seek.com.au",
    "seek.com",
    "reed.co.uk",
    "totaljobs.com",
    "cv-library.co.uk",
    "stepstone.de",
    "stepstone.com",
    "xing.com",
    "jooble.org",
    "talent.com",
    "snagajob.com",
    "grabjobs.co",
    "internshala.com",
    "freshersworld.com",
    "iimjobs.com",
    "hirist.com",
    "cutshort.io",
    "apna.co",
    "foundit.com",
)

# Employer ATS — never treat as aggregator card listings.
_EMPLOYER_ATS_HOST_MARKERS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "myworkdayjobs.com",
    "workday.com",
    "smartrecruiters.com",
    "bamboohr.com",
    "icims.com",
    "taleo.net",
    "jobvite.com",
)

_GH_JOB_RE = re.compile(r"/jobs/\d+(?:/|$|\?)", re.IGNORECASE)
_LEVER_UUID_RE = re.compile(
    r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)
_LINKEDIN_VIEW_RE = re.compile(
    r"linkedin\.com/jobs/view(?:/|\?|)(?:currentJobId=)?(\d+)",
    re.IGNORECASE,
)
_Naukri_DETAIL_RE = _NAUKRI_DETAIL_RE = re.compile(
    r"/job-listings-.+-(\d{6,})(?:/|$|\?)",
    re.IGNORECASE,
)
_INDEED_VIEW_RE = re.compile(r"/(?:viewjob|rc/clk)\?.*?jk=([a-z0-9]+)", re.IGNORECASE)
_GENERIC_DETAIL_PATH_RE = re.compile(
    r"/(?:job|jobs|position|opening|vacancy|role|requisition|view)[/_-][^/?#]*?(\d{5,})(?:/|$|\?)",
    re.IGNORECASE,
)
_JOB_ID_QUERY_KEYS = frozenset(
    {
        "jobid",
        "job_id",
        "id",
        "jk",
        "vjk",
        "currentjobid",
        "postingid",
        "posting_id",
        "uid",
        "rb",
        "vacancyid",
        "requisitionid",
    }
)

_JOB_BOARD_HOST_KEYWORDS = (
    "jobs",
    "job",
    "career",
    "careers",
    "recruit",
    "hiring",
    "talent",
    "emplo",
    "vacancy",
    "work",
)

# Detail pages where automated fetch is policy-blocked (not a scraper limitation).
SCRAPE_POLICY_BLOCKED_DETAIL_CHECKS: tuple[str, ...] = ("linkedin",)


def _normalize_host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _extra_aggregator_hosts() -> frozenset[str]:
    raw = (os.getenv("AGGREGATOR_EXTRA_HOSTS") or "").strip()
    if not raw:
        return frozenset()
    return frozenset(h.strip().lower().removeprefix("www.") for h in raw.split(",") if h.strip())


def _host_id_slug(url: str) -> str:
    host = _normalize_host(url)
    for suffix in AGGREGATOR_HOST_SUFFIXES:
        if host == suffix or host.endswith(f".{suffix}"):
            return suffix.split(".")[0]
    parts = [p for p in host.split(".") if p not in ("www", "com", "co", "in", "org", "net", "io", "au", "uk", "de")]
    return parts[0] if parts else host.replace(".", "-")


def is_employer_ats_host(url: str) -> bool:
    host = _normalize_host(url)
    return any(marker in host for marker in _EMPLOYER_ATS_HOST_MARKERS)


def is_employer_ats_single_job(url: str) -> bool:
    """Single posting on an employer ATS (handled by ATS/scrape pipeline, not card listing)."""
    if not is_employer_ats_host(url):
        return False
    path = (urlparse(url).path or "").lower()
    if "greenhouse.io" in _normalize_host(url):
        return bool(_GH_JOB_RE.search(path))
    if "lever.co" in _normalize_host(url):
        return bool(_LEVER_UUID_RE.search(path))
    if "ashbyhq.com" in _normalize_host(url):
        return bool(_LEVER_UUID_RE.search(path))
    return False


def is_employer_ats_board_listing(url: str) -> bool:
    """Company board root/listing on ATS — skip as aggregator cards."""
    if not is_employer_ats_host(url):
        return False
    return not is_employer_ats_single_job(url)


def is_aggregator_host(url: str) -> bool:
    host = _normalize_host(url)
    if host in _extra_aggregator_hosts():
        return True
    if any(host == suffix or host.endswith(f".{suffix}") for suffix in AGGREGATOR_HOST_SUFFIXES):
        return True
    return _host_matches_job_board_heuristic(host)


def _host_matches_job_board_heuristic(host: str) -> bool:
    if not host or is_employer_ats_host(f"https://{host}/"):
        return False
    blob = host.lower()
    return any(keyword in blob for keyword in _JOB_BOARD_HOST_KEYWORDS)


def is_linkedin_job_detail_url(url: str) -> bool:
    raw = (url or "").strip().lower()
    if "linkedin.com" not in raw:
        return False
    if "/jobs/view/" in raw or "/jobs/viewjob" in raw:
        return True
    parsed = urlparse(url)
    if "currentjobid" in (k.lower() for k in parse_qs(parsed.query)):
        return True
    return bool(_LINKEDIN_VIEW_RE.search(raw))


def is_naukri_job_detail_url(url: str) -> bool:
    if "naukri.com" not in _normalize_host(url):
        return False
    path = (urlparse(url).path or "").lower()
    if "-jobs-in-" in path:
        return False
    if "/job-details/" in path:
        return True
    return bool(_NAUKRI_DETAIL_RE.search(path))


def _indeed_job_detail_url(url: str) -> bool:
    host = _normalize_host(url)
    if "indeed.com" not in host:
        return False
    path = (urlparse(url).path or "").lower()
    if "/viewjob" in path or "/rc/clk" in path:
        return True
    qs = parse_qs(urlparse(url).query)
    return any(k.lower() == "jk" for k in qs)


def _glassdoor_job_detail_url(url: str) -> bool:
    host = _normalize_host(url)
    if "glassdoor.com" not in host:
        return False
    path = (urlparse(url).path or "").lower()
    return "/job-listing/" in path or "/partners/job" in path


def is_aggregator_job_detail_url(url: str) -> bool:
    """Single job on a third-party aggregator (full scrape path, not card listing)."""
    if is_employer_ats_single_job(url):
        return False
    if is_linkedin_job_detail_url(url):
        return True
    if is_naukri_job_detail_url(url):
        return True
    if _indeed_job_detail_url(url):
        return True
    if _glassdoor_job_detail_url(url):
        return True
    if not is_aggregator_host(url):
        return False
    parsed = urlparse(url)
    path = parsed.path or ""
    if _GENERIC_DETAIL_PATH_RE.search(path):
        return True
    for key in parse_qs(parsed.query):
        if key.lower() in _JOB_ID_QUERY_KEYS:
            return True
    return False


def is_scrape_policy_blocked_url(url: str) -> bool:
    """URLs that must not be fetched by Scrapling/Playwright (policy)."""
    if is_linkedin_job_detail_url(url):
        return True
    blocked = (os.getenv("SCRAPE_POLICY_BLOCKED_HOSTS") or "").strip()
    if blocked:
        host = _normalize_host(url)
        for part in blocked.split(","):
            p = part.strip().lower()
            if p and (host == p or host.endswith(f".{p}")):
                return True
    return False


def extract_aggregator_job_id(url: str | None) -> str | None:
    """Embedded job id from card/detail URL; prefixed with host slug when possible."""
    raw = (url or "").strip()
    if not raw:
        return None
    slug = _host_id_slug(raw)
    if match := _LINKEDIN_VIEW_RE.search(raw):
        return f"linkedin:{match.group(1)}"
    parsed = urlparse(raw)
    qs = parse_qs(parsed.query)
    for key, values in qs.items():
        if key.lower() not in _JOB_ID_QUERY_KEYS or not values:
            continue
        val = str(values[0]).strip()
        if not val:
            continue
        if val.isdigit() or len(val) >= 8:
            if "linkedin.com" in _normalize_host(raw):
                return f"linkedin:{val}"
            return f"{slug}:{val}"
    if match := _NAUKRI_DETAIL_RE.search(parsed.path):
        return f"naukri:{match.group(1)}"
    if match := _GENERIC_DETAIL_PATH_RE.search(parsed.path):
        return f"{slug}:{match.group(1)}"
    if "naukri.com" in _normalize_host(raw):
        tail = parsed.path.rstrip("/").split("-")[-1]
        if tail.isdigit() and len(tail) >= 6:
            return f"naukri:{tail}"
    return None
