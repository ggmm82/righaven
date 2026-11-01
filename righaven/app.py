"""Register RigHaven Harness, Community Gallery, Cloud Portal, and i18n routes on the Gateway."""
from app.gateway.app import app
from app.gateway.deps import require_admin_user
from fastapi import Depends, Request
from .router import router
from .team_routing import TeamRoutingMiddleware
from .progress_routes import router as progress_router
from .gallery_routes import router as gallery_router
from .cloud_routes import router as cloud_router
from .i18n_routes import router as i18n_router
from .i18n import resolve_request_locale, translate


async def harness_admin(request: Request):
    locale = resolve_request_locale(request)
    await require_admin_user(request, detail=translate('notifications.auth_Required', locale=locale))


from starlette.exceptions import HTTPException as StarletteHTTPException
from .error_catalog import localized_http_exception
app.add_exception_handler(StarletteHTTPException, localized_http_exception)
app.include_router(router, dependencies=[Depends(harness_admin)])
app.include_router(progress_router)
app.include_router(gallery_router)
app.include_router(cloud_router)
app.include_router(i18n_router)
from .environment_routes import router as environment_router, preload_startup
app.include_router(environment_router)
from .skill_routes import router as skill_router
app.include_router(skill_router)
from .maintenance import router as maintenance_router
app.include_router(maintenance_router)
from .version_routes import router as version_router
app.include_router(version_router)
from .policy_routes import router as policy_router
from .recipe_routes import router as recipe_router, journey_router
from .connection_routes import router as connection_router
app.include_router(policy_router)
app.include_router(recipe_router)
app.include_router(journey_router)
app.include_router(connection_router)
from .usage_routes import router as usage_router
app.include_router(usage_router)
from .build_routes import router as build_router
app.include_router(build_router)
from contextlib import asynccontextmanager
from starlette.concurrency import run_in_threadpool
_native_lifespan = app.router.lifespan_context

@asynccontextmanager
async def environment_lifespan(application):
    async with _native_lifespan(application) as lifecycle:
        await run_in_threadpool(preload_startup)
        try:
            yield lifecycle
        finally:
            from .environment_runtime import stop_preparations
            stop_preparations()

app.router.lifespan_context = environment_lifespan
app.add_middleware(TeamRoutingMiddleware)
