from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any, Optional
from backend.app.auth.dependencies import require_auth
from backend.app.database import get_db
from backend.app.config import get_settings
from backend.app.services.content_service import ContentService
from backend.app.ai.gateway import AIGateway, OllamaUnavailableError
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/content", tags=["content"])

class IdeaGenerateReq(BaseModel):
    channel_id: str
    channel_context: dict = {}

class IdeaCreate(BaseModel):
    channel_id: str
    title: str
    description: str = ""
    keywords: list[str] = []
    target_audience: str = ""

class IdeaStatusUpdate(BaseModel):
    status: str

class ScriptGenerateReq(BaseModel):
    channel_id: str
    topic: str
    duration: int = 45
    channel_context: Optional[dict] = None

class ScriptCreate(BaseModel):
    channel_id: str
    topic: Optional[str] = None
    title: Optional[str] = None
    script_text: str
    duration: Optional[int] = 45
    duration_estimate: Optional[int] = 45
    content_idea_id: Optional[str] = None

class ScriptUpdate(BaseModel):
    title: Optional[str] = None
    script_text: Optional[str] = None
    status: Optional[str] = None

def get_content_service(db = Depends(get_db), settings = Depends(get_settings)):
    ai = AIGateway(settings)
    return ContentService(db, ai)

@router.post("/ideas/generate", status_code=status.HTTP_201_CREATED)
async def generate_ideas(req: IdeaGenerateReq, user: dict = Depends(require_auth), service: ContentService = Depends(get_content_service)):
    try:
        return await service.generate_ideas(str(user["_id"]), req.channel_id, req.channel_context)
    except OllamaUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": e.code, "message": e.message, "details": {"url": e.url}}
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/ideas")
async def list_ideas(channel_id: str = Query(...), status: Optional[str] = Query(None), user: dict = Depends(require_auth), service: ContentService = Depends(get_content_service)):
    return await service.list_ideas(str(user["_id"]), channel_id, status)

@router.post("/ideas", status_code=status.HTTP_201_CREATED)
async def create_idea(data: IdeaCreate, user: dict = Depends(require_auth), service: ContentService = Depends(get_content_service)):
    return await service.create_idea(str(user["_id"]), data.channel_id, data.model_dump())

@router.get("/ideas/{idea_id}")
async def get_idea(idea_id: str, user: dict = Depends(require_auth), service: ContentService = Depends(get_content_service)):
    idea = await service.get_idea(str(user["_id"]), idea_id)
    if not idea:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "IDEA_NOT_FOUND", "message": f"Idea {idea_id} not found or access denied"}
        )
    return idea

@router.put("/ideas/{idea_id}/status")
async def update_idea_status(idea_id: str, data: IdeaStatusUpdate, user: dict = Depends(require_auth), service: ContentService = Depends(get_content_service)):
    updated = await service.update_idea_status(str(user["_id"]), idea_id, data.status)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "IDEA_NOT_FOUND", "message": f"Idea {idea_id} not found or access denied"}
        )
    return {"status": "success"}

@router.post("/scripts/generate", status_code=status.HTTP_201_CREATED)
async def generate_script(req: ScriptGenerateReq, user: dict = Depends(require_auth), service: ContentService = Depends(get_content_service)):
    try:
        return await service.generate_script(
            user_id=str(user["_id"]),
            channel_id=req.channel_id,
            topic=req.topic,
            duration=req.duration,
            channel_context=req.channel_context
        )
    except OllamaUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": e.code, "message": e.message, "details": {"url": e.url}}
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/scripts")
async def list_scripts(channel_id: str = Query(...), user: dict = Depends(require_auth), service: ContentService = Depends(get_content_service)):
    return await service.list_scripts(str(user["_id"]), channel_id)

@router.post("/scripts", status_code=status.HTTP_201_CREATED)
async def create_script(data: ScriptCreate, user: dict = Depends(require_auth), service: ContentService = Depends(get_content_service)):
    return await service.create_script(str(user["_id"]), data.channel_id, data.model_dump())

@router.get("/scripts/{script_id}")
async def get_script(script_id: str, user: dict = Depends(require_auth), service: ContentService = Depends(get_content_service)):
    script = await service.get_script(str(user["_id"]), script_id)
    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SCRIPT_NOT_FOUND", "message": f"Script {script_id} not found or access denied"}
        )
    return script

@router.put("/scripts/{script_id}")
async def update_script(script_id: str, data: ScriptUpdate, user: dict = Depends(require_auth), service: ContentService = Depends(get_content_service)):
    updated = await service.update_script(str(user["_id"]), script_id, data.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SCRIPT_NOT_FOUND", "message": f"Script {script_id} not found or access denied"}
        )
    return {"status": "success"}