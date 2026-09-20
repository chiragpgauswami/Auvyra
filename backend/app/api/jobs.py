from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from backend.app.auth.dependencies import require_auth
from backend.app.database import get_db
from backend.app.repositories.jobs import JobRepository
from backend.app.utils.serializers import serialize_doc, serialize_docs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

def get_job_repo(db = Depends(get_db)):
    return JobRepository(db)

@router.get("", include_in_schema=False)
@router.get("/")
async def list_jobs(status: Optional[str] = Query(None), user: dict = Depends(require_auth), repo: JobRepository = Depends(get_job_repo)):
    jobs = await repo.find_by_user(str(user["_id"]), status=status)
    return serialize_docs(jobs)

@router.get("/active")
async def get_active_job(user: dict = Depends(require_auth), repo: JobRepository = Depends(get_job_repo)):
    """Fetch the most recent active (queued or processing) job for the user."""
    active_jobs = await repo.find_by_user(str(user["_id"]), status="processing", limit=1)
    if not active_jobs:
        active_jobs = await repo.find_by_user(str(user["_id"]), status="queued", limit=1)
    if not active_jobs:
        return {"job": None}
    return {"job": serialize_doc(active_jobs[0])}

@router.get("/{job_id}")
async def get_job(job_id: str, user: dict = Depends(require_auth), repo: JobRepository = Depends(get_job_repo)):
    job = await repo.find_by_id(job_id, user_id=str(user["_id"]))
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found or access denied"}
        )
    return serialize_doc(job)

@router.get("/{job_id}/progress")
async def get_job_progress(job_id: str, user: dict = Depends(require_auth), repo: JobRepository = Depends(get_job_repo)):
    job = await repo.find_by_id(job_id, user_id=str(user["_id"]))
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found or access denied"}
        )
    return {
        "job_id": str(job.get("_id", job_id)),
        "stage": job.get("stage") or job.get("status", "processing"),
        "percent": job.get("progress", 0),
        "message": job.get("message") or f"Job status: {job.get('status', 'processing')}",
        "status": job.get("status", "processing"),
        "result": serialize_doc(job.get("result")) if isinstance(job.get("result"), dict) else job.get("result"),
        "error": job.get("error"),
        "created_at": job.get("created_at").isoformat() if hasattr(job.get("created_at"), "isoformat") else str(job.get("created_at")) if job.get("created_at") else None,
        "completed_at": job.get("completed_at").isoformat() if hasattr(job.get("completed_at"), "isoformat") else str(job.get("completed_at")) if job.get("completed_at") else None,
    }