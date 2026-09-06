from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from backend.app.auth.dependencies import require_auth
from backend.app.database import get_db
from backend.app.repositories.jobs import JobRepository
from backend.app.utils.serializers import serialize_doc, serialize_docs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

def get_job_repo(db = Depends(get_db)):
    return JobRepository(db)

@router.get("/")
async def list_jobs(status: Optional[str] = Query(None), user: dict = Depends(require_auth), repo: JobRepository = Depends(get_job_repo)):
    jobs = await repo.find_by_user(str(user["_id"]), status=status)
    return serialize_docs(jobs)

@router.get("/{job_id}")
async def get_job(job_id: str, user: dict = Depends(require_auth), repo: JobRepository = Depends(get_job_repo)):
    job = await repo.find_by_id(job_id, user_id=str(user["_id"]))
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "JOB_NOT_FOUND", "message": f"Job {job_id} not found or access denied"}
        )
    return serialize_doc(job)