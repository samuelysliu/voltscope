from fastapi import APIRouter

from app.api.v1 import admin, auth, health, member, public

api_router = APIRouter()

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(public.router)
api_v1_router.include_router(member.router)
api_v1_router.include_router(admin.router)

api_compat_router = APIRouter(prefix="/api")
api_compat_router.include_router(health.router)
api_compat_router.include_router(auth.router)
api_compat_router.include_router(public.router)
api_compat_router.include_router(member.router)
api_compat_router.include_router(admin.router)

api_router.include_router(api_v1_router)
api_router.include_router(api_compat_router)
