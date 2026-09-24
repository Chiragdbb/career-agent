from __future__ import annotations

import uuid
from unittest.mock import patch

from app.tasks import QStashDiscoveryTaskClient


def test_enqueue_discover_jobs_publishes_expected_url() -> None:
    user_id = uuid.uuid4()
    run_id = uuid.uuid4()
    client = QStashDiscoveryTaskClient(
        token="tok",
        callback_base_url="https://api.example.com",
    )
    with patch("packages.providers.qstash.publish_json", return_value="msg_abc") as pub:
        tid = client.enqueue_discover_jobs(
            user_id=user_id, workflow_run_id=run_id, max_results=10
        )
    assert tid == "msg_abc"
    pub.assert_called_once()
    kwargs = pub.call_args.kwargs
    assert kwargs["destination_url"] == "https://api.example.com/internal/qstash/discover-jobs"
    assert kwargs["body"]["max_results"] == 10
    assert kwargs["body"]["user_id"] == str(user_id)
    assert kwargs["body"]["workflow_run_id"] == str(run_id)
    assert kwargs["token"] == "tok"


def test_enqueue_rescrape_job_publishes_expected_url() -> None:
    user_id = uuid.uuid4()
    run_id = uuid.uuid4()
    match_id = uuid.uuid4()
    client = QStashDiscoveryTaskClient(
        token="tok",
        callback_base_url="https://api.example.com/",
    )
    with patch("packages.providers.qstash.publish_json", return_value="msg_xyz") as pub:
        tid = client.enqueue_rescrape_job(
            user_id=user_id, workflow_run_id=run_id, match_id=match_id
        )
    assert tid == "msg_xyz"
    pub.assert_called_once()
    kwargs = pub.call_args.kwargs
    assert kwargs["destination_url"] == "https://api.example.com/internal/qstash/rescrape-job"
    assert kwargs["body"]["match_id"] == str(match_id)
    assert kwargs["body"]["user_id"] == str(user_id)
    assert kwargs["body"]["workflow_run_id"] == str(run_id)
