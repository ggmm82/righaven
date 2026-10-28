"""Program release management; binary installation is administrator-only."""
from fastapi import APIRouter,Request,HTTPException
from pydantic import BaseModel,Field
from app.gateway.authz import require_permission
from app.gateway.deps import require_admin_user
from starlette.concurrency import run_in_threadpool
from .router import same_origin
from . import tool_versions as versions

router=APIRouter(prefix='/api/harness/tool-versions',tags=['Versioni strumenti'])


@router.get('')
@require_permission('agents','read')
async def catalogue(request:Request):
    return await run_in_threadpool(versions.library)


@router.get('/{tool}/releases')
@require_permission('agents','read')
async def releases(tool:str,request:Request):
    from .release_catalog import options
    app=versions.builtins().get(tool)
    if not app:raise HTTPException(404,'Strumento sconosciuto')
    try:return {'releases':await run_in_threadpool(options,app)}
    except Exception as error:raise HTTPException(409,'Elenco ufficiale non disponibile: '+str(error)[:300]) from error


class VersionRequest(BaseModel):
    tool:str=Field(max_length=64)
    version:str=Field(min_length=1,max_length=101)


@router.post('')
@require_permission('agents','write')
async def prepare(value:VersionRequest,request:Request):
    same_origin(request)
    await require_admin_user(request,detail='La verifica di nuovi programmi richiede un amministratore')
    try:return await run_in_threadpool(versions.start,value.tool,value.version)
    except ValueError as error:raise HTTPException(400,str(error)) from error


class Activation(BaseModel):
    tool:str=Field(max_length=64)
    revision:str=Field(max_length=64)


@router.put('/default')
@require_permission('agents','write')
async def activate(value:Activation,request:Request):
    same_origin(request)
    await require_admin_user(request,detail='Le versioni predefinite condivise richiedono un amministratore')
    try:
        result=await run_in_threadpool(versions.activate,value.tool,value.revision)
        from .environment_routes import schedule_affected
        result['preparing_environments']=await run_in_threadpool(schedule_affected,value.tool)
        return result
    except (ValueError,OSError) as error:raise HTTPException(409,str(error)) from error
