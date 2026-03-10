from __future__ import annotations


def _notify_ingestion_complete(ingestion_id: str, username: str, db_path: str) -> None:
    """Send notification when a PDF ingestion job completes.

    Currently a no-op. Wire up when an outgoing mail server is configured.
    Expected implementation: send email to the user who queued the job
    with a link to /import/pdf/review/{ingestion_id}.

    Args:
        ingestion_id: The ingestion job ID.
        username: The user who queued the job.
        db_path: The DB path the job ran against (for multi-tenant context).
    """
    pass  # TODO: implement when mail server is available
