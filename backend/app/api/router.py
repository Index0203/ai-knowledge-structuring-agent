from fastapi import APIRouter

from app.api.routes.documents import router as documents_router
from app.api.routes.questions import router as questions_router
from app.api.routes.uploads import router as uploads_router

api_router = APIRouter()
api_router.include_router(uploads_router)
api_router.include_router(documents_router)
api_router.include_router(questions_router)
