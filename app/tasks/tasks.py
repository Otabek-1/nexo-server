from app.tasks.celery_app import celery


@celery.task(name="app.tasks.tasks.submission_postprocess")
def submission_postprocess(submission_id: str) -> dict:
    return {"ok": True, "submission_id": submission_id}


@celery.task(name="app.tasks.tasks.review_finalized")
def review_finalized(submission_id: str) -> dict:
    return {"ok": True, "submission_id": submission_id}


@celery.task(name="app.tasks.tasks.storage_cleanup_orphans")
def storage_cleanup_orphans() -> dict:
    return {"ok": True}


@celery.task(name="app.tasks.tasks.audit_export")
def audit_export() -> dict:
    return {"ok": True}


@celery.task(name="app.tasks.tasks.notifications_send")
def notifications_send(payload: dict) -> dict:
    return {"ok": True, "payload": payload}

