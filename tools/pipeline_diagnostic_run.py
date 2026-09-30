#!/usr/bin/env python3
"""Live discovery + enrichment diagnostic with structured logs for tuning."""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps" / "api"))

os.environ.setdefault("DISCOVERY_LOG_DIR", str(ROOT / "logs" / "discovery"))
os.environ.setdefault("DISCOVERY_LOG_BODIES", "1")
os.environ.setdefault("PYTHONPATH", f"{ROOT};{ROOT / 'apps' / 'api'}")

from packages.shared.env import load_project_env

load_project_env()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
for name in ("career.discovery", "career.discovery.run", "career.search.composite", "career.scrapling"):
    logging.getLogger(name).setLevel(logging.DEBUG)

REPORT_DIR = ROOT / "logs" / "pipeline_runs"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    from app.database import get_session_factory, init_db
    from database.models.schema import Company, Job, JobMatch, ProviderUsage, User
    from packages.domain.contacts import ContactEnrichmentService
    from packages.domain.job_discovery import JobDiscoveryService
    from packages.domain.preferences import PreferencesService
    from packages.domain.provider_usage import ProviderUsageService
    from packages.providers.factory import (
        ProviderSettings,
        create_email_finder_provider,
        create_extraction_llm_provider,
        create_llm_provider,
        create_people_provider,
        create_playwright_contacts_provider,
        create_playwright_jobs_provider,
        create_discovery_scraper_provider,
        create_search_provider,
    )

    init_db()
    session = get_session_factory()()
    settings = ProviderSettings.from_env()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORT_DIR / f"run_{stamp}.json"
    report: dict = {"started_at": stamp, "steps": []}

    user = session.query(User).order_by(User.created_at.asc()).first()
    if user is None:
        print("No users in database — sign in via the web app first.")
        return 1
    user_id = user.id
    report["user_id"] = str(user_id)
    print(f"Using user_id={user_id}")

    try:
        playwright_jobs = create_playwright_jobs_provider(settings)
    except Exception as exc:
        playwright_jobs = None
        report["steps"].append({"playwright_jobs": f"unavailable: {exc}"})

    max_results = int(os.getenv("DIAGNOSTIC_MAX_RESULTS", "3"))
    max_urls_raw = (os.getenv("DIAGNOSTIC_MAX_URLS") or os.getenv("DISCOVERY_MAX_URLS") or "").strip()
    max_urls = int(max_urls_raw) if max_urls_raw.isdigit() else None
    service = JobDiscoveryService(
        session,
        user_id,
        search=create_search_provider(settings),
        scraper=create_discovery_scraper_provider(settings),
        llm=create_llm_provider(settings),
        extraction_llm=create_extraction_llm_provider(settings),
        playwright_jobs=playwright_jobs,
        max_results=max_results,
        max_urls=max_urls,
        discovery_lock=None,
        cancellation=None,
    )

    cap_note = f", max_urls={max_urls}" if max_urls else ""
    print(f"Starting discovery (max_results={max_results} per query{cap_note})...")
    try:
        result = service.run()
        session.commit()
        report["discovery"] = {
            "workflow_run_id": str(result.workflow_run_id),
            "created_jobs": [str(j) for j in result.created_jobs],
            "duplicate_jobs": [str(j) for j in result.duplicate_jobs],
            "skipped_invalid": result.skipped_invalid,
            "errors": result.errors,
            "scrapes_fresh": result.scrapes_fresh,
        }
        print("Discovery result:", json.dumps(report["discovery"], indent=2))
    except Exception as exc:
        session.rollback()
        report["discovery_error"] = str(exc)
        print("Discovery failed:", exc)
        logging.exception("discovery_failed")

    run_id = report.get("discovery", {}).get("workflow_run_id")
    if run_id:
        usage_rows = (
            session.query(ProviderUsage)
            .filter(ProviderUsage.workflow_run_id == uuid.UUID(run_id))
            .order_by(ProviderUsage.created_at.asc())
            .all()
        )
        report["provider_usage"] = [
            {
                "provider": r.provider_name,
                "operation": r.operation,
                "success": r.success,
                "tier_reached": r.tier_reached,
                "error": r.error,
                "payload": r.payload,
            }
            for r in usage_rows
        ]

    usage_svc = ProviderUsageService(session)
    report["efficiency"] = usage_svc.efficiency_report()

    jobs = (
        session.query(Job)
        .join(JobMatch, JobMatch.job_id == Job.id)
        .filter(JobMatch.user_id == user_id)
        .order_by(Job.created_at.desc())
        .limit(10)
        .all()
    )
    report["recent_jobs"] = [
        {
            "id": str(j.id),
            "title": j.title,
            "url": j.url,
            "completeness_score": j.completeness_score,
            "missing_fields": j.missing_fields,
            "extraction_provenance": j.extraction_provenance,
            "source": j.source,
            "skills_count": len(j.skills or []),
        }
        for j in jobs
    ]

    if jobs:
        job = jobs[0]
        company = session.query(Company).filter(Company.id == job.company_id).one()
        enrich = ContactEnrichmentService(
            session,
            user_id,
            people=create_people_provider(settings),
            email_finder=create_email_finder_provider(settings),
            playwright_contacts=create_playwright_contacts_provider(settings),
            search=create_search_provider(settings),
        )
        print(f"Contact enrichment for company={company.name} job={job.title}...")
        try:
            contact_result = enrich.find_or_enrich_contact(company.id, job=job)
            session.commit()
            report["contact_sample"] = {
                "company_id": str(company.id),
                "job_id": str(job.id),
                "tier": contact_result.tier,
                "cache_hit": contact_result.cache_hit,
                "contact_name": contact_result.contact.name if contact_result.contact else None,
                "contact_source": contact_result.contact.source if contact_result.contact else None,
            }
            print("Contact result:", report["contact_sample"])
        except Exception as exc:
            session.rollback()
            report["contact_sample_error"] = str(exc)
            logging.exception("contact_enrich_failed")

    prefs = PreferencesService(session, user_id).get_settings()
    report["preferences_snapshot"] = {
        "target_roles": prefs.target_roles,
        "locations": prefs.locations,
    }

    log_dir = Path(os.environ["DISCOVERY_LOG_DIR"])
    if run_id:
        run_log = log_dir / str(run_id)
        if run_log.exists():
            report["discovery_log_dir"] = str(run_log)
            events_file = run_log / "events.jsonl"
            if events_file.exists():
                report["discovery_event_count"] = sum(1 for _ in events_file.open(encoding="utf-8"))

    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nFull report written to: {report_path}")
    if report.get("discovery_log_dir"):
        print(f"Discovery JSONL: {report['discovery_log_dir']}")
    session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
