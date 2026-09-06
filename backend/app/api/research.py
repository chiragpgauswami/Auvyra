from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from backend.app.auth.dependencies import require_auth
from backend.app.database import get_db
from backend.app.config import get_settings
from backend.app.services.research_service import ResearchService
from backend.app.ai.gateway import AIGateway, OllamaUnavailableError
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/research", tags=["research"])

class ResearchCreateReq(BaseModel):
    channel_id: str
    topic: str
    channel_context: Optional[dict] = None

def get_research_service(db = Depends(get_db), settings = Depends(get_settings)):
    ai = AIGateway(settings)
    return ResearchService(db, ai)

@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_research(req: ResearchCreateReq, user: dict = Depends(require_auth), service: ResearchService = Depends(get_research_service)):
    try:
        return await service.create_research(
            user_id=str(user["_id"]),
            channel_id=req.channel_id,
            topic=req.topic,
            channel_context=req.channel_context
        )
    except OllamaUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": e.code, "message": e.message, "details": {"url": e.url}}
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/")
async def list_research(channel_id: str = Query(...), user: dict = Depends(require_auth), service: ResearchService = Depends(get_research_service)):
    return await service.list_research(str(user["_id"]), channel_id)

@router.get("/{report_id}")
async def get_research(report_id: str, user: dict = Depends(require_auth), service: ResearchService = Depends(get_research_service)):
    report = await service.get_research(str(user["_id"]), report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "REPORT_NOT_FOUND", "message": f"Research report {report_id} not found or access denied"}
        )
    return report