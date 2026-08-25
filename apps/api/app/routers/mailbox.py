"""Mailbox connection status stub (no live OAuth)."""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies import CurrentUserIdDep
from app.schemas.human_tasks import MailboxStatusResponse
from packages.providers.mailbox import MockMailboxProvider

router = APIRouter(prefix="/settings/mailbox", tags=["settings"])

_mailbox = MockMailboxProvider()


@router.get("", response_model=MailboxStatusResponse)
def get_mailbox_status(user_id: CurrentUserIdDep) -> MailboxStatusResponse:
    info = _mailbox.get_connection_status(user_id)
    return MailboxStatusResponse(
        provider=info.provider.value,
        status=info.status.value,
        email_address=info.email_address,
        has_encrypted_token=info.has_encrypted_token,
        error=info.error,
    )
