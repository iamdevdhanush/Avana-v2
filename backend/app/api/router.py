from fastapi import APIRouter

from app.api.v1 import auth, incidents, risk, route, sos, community, analytics, chat, admin, reports

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(incidents.router)
api_router.include_router(risk.router)
api_router.include_router(route.router)
api_router.include_router(sos.router)
api_router.include_router(community.router)
api_router.include_router(analytics.router)
api_router.include_router(chat.router)
api_router.include_router(admin.router)
api_router.include_router(reports.router)
