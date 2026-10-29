"""Inspect native skill packages and safely customize instructions per account."""
import hashlib
import os
from pathlib import Path
import shutil
import uuid
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from pydantic import BaseModel,Field
from app.gateway.deps import get_config
from righaven_core.runtime.user_context import get_effective_user_id
from .identity import current_user_id
from .router import same_origin
router=APIRouter(prefix='/api/harness/skills',tags=['Skill instructions'])


def storage():
    from righaven_core.skills.storage import get_or_new_user_skill_storage
    return get_or_new_user_skill_storage(get_effective_user_id())


async def visible(name,request,config):
    from app.gateway.routers.skills import list_skills
    listed=await list_skills(request,config)
    if name not in {item.name for item in listed.skills}:raise HTTPException(404,'Skill not available in your account')
    skill=next((item for item in storage().load_skills(enabled_only=False) if item.name==name),None)
    if skill is None:raise HTTPException(404,'Skill package no longer exists')
    return skill


def document(skill,file):
    root=Path(skill.skill_dir).resolve();target=root/file
    if Path(file).is_absolute() or '..' in Path(file).parts or target.is_symlink() or not target.resolve().is_relative_to(root) or not target.is_file() or target.stat().st_size>200000:
        raise HTTPException(422,'Choose a text file inside this skill package')
    try:return target.read_text()
    except UnicodeError:raise HTTPException(422,'Only text instructions can be displayed') from None


@router.get('/{name}/instructions')
async def read_instructions(name:str,request:Request,file:str=Query('SKILL.md',max_length=200),config=Depends(get_config)):
    current_user_id(request);skill=await visible(name,request,config)
    content=document(skill,file)
    files=[str(p.relative_to(skill.skill_dir)) for p in Path(skill.skill_dir).rglob('*.md') if p.is_file() and not p.is_symlink()][:100]
    from .environment_routes import native_agents
    from .environments import profile
    usage=[]
    for agent in await native_agents(request):
        try:value=profile(get_effective_user_id(),agent)
        except ValueError:continue
        if name in value['skills']:usage.append({'name':value['name'],'display_name':value['display_name'],'enabled':name not in value['disabled']})
    return {'name':name,'content':content,'file':file,'files':files,'category':str(skill.category),
            'customized':str(skill.category)=='custom','revision':hashlib.sha256(content.encode()).hexdigest(),
            'environments':usage,'enabled':skill.enabled,'editable':file.lower().endswith('.md')}


class Edit(BaseModel):
    content:str=Field(min_length=1,max_length=200000)
    revision:str=Field(pattern='^[a-f0-9]{64}$')
    file:str=Field(default='SKILL.md',min_length=1,max_length=200)


@router.put('/{name}/instructions')
async def edit_instructions(name:str,body:Edit,request:Request,config=Depends(get_config)):
    current_user_id(request);same_origin(request)
    skill=await visible(name,request,config);store=storage()
    document(skill,body.file)
    if not body.file.lower().endswith('.md'):raise HTTPException(422,'Edit Markdown instructions only')
    try:
        if body.file=='SKILL.md':store.validate_skill_markdown_content(name,body.content)
    except ValueError as error:raise HTTPException(422,str(error)) from None
    from app.gateway.routers.skills import _scan_static_skill_markdown_or_raise,_custom_skill_mutation
    from righaven_core.skills.security_scanner import scan_skill_content
    scan_text=body.content
    if body.file!='SKILL.md':
        import re
        metadata=re.match(r'^---.*?\n---',document(skill,'SKILL.md'),re.S)
        scan_text=(metadata[0]+'\n' if metadata else '')+body.content
    findings=await _scan_static_skill_markdown_or_raise(name,scan_text,app_config=config)
    scan=await scan_skill_content(body.content,executable=False,location=name+'/'+body.file,app_config=config,static_findings=findings)
    if scan.decision=='block':raise HTTPException(400,'Skill scanner blocked this edit: '+scan.reason)
    with _custom_skill_mutation(store):
        skill=next(item for item in store.load_skills(enabled_only=False) if item.name==name)
        before=document(skill,body.file)
        if hashlib.sha256(before.encode()).hexdigest()!=body.revision:raise HTTPException(409,'Instructions changed; reload before editing')
        target=store.get_custom_skill_dir(name)
        if not store.custom_skill_exists(name):
            files=list(Path(skill.skill_dir).rglob('*'))
            if any(p.is_symlink() for p in files) or sum(p.stat().st_size for p in files if p.is_file())>8*1024**2:
                raise HTTPException(422,'Package cannot be copied safely; export and inspect it first')
            staged=target.parent/('.instructions-'+uuid.uuid4().hex);target.parent.mkdir(parents=True,exist_ok=True)
            try:
                shutil.copytree(skill.skill_dir,staged)
                (staged/body.file).write_text(body.content)
                os.replace(staged,target)
            finally:shutil.rmtree(staged,ignore_errors=True)
        else:store.write_custom_skill(name,body.file,body.content)
        store.set_skill_enabled_state(name,skill.enabled)
        store.append_history(name,{'action':'human_edit','author':'human','prev_content':before,'new_content':body.content,'file_path':body.file,'scanner':{'decision':scan.decision,'reason':scan.reason}})
    from righaven_core.agents.lead_agent.prompt import invalidate_user_skill_cache,publish_skills_cache_reset
    invalidate_user_skill_cache(get_effective_user_id());publish_skills_cache_reset(user_id=get_effective_user_id())
    return await read_instructions(name,request,body.file,config)
