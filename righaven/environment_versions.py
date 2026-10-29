"""Compare observed software with requested versions without changing Latest pointers."""
def inventory(profile,known,defaults,pointers,read):
    runtime=profile['runtime'];observed=runtime.get('installed_versions') or runtime.get('version_names') or {}
    choices={**defaults,**profile['deployment'].get('tool_versions',{})}
    tools=sorted(set(profile['tools'])|{key for key in {*choices,*profile.get('selected_versions',{})} if key.startswith('provider-')})
    rows=[]
    for tool in tools:
        selection=choices.get(tool,'builtin');target=None
        if selection=='builtin':target=known.get(tool,{}).get('version')
        else:
            revision=pointers.get(tool,{}).get('revision') if selection=='latest' else selection
            if revision:
                try:target=read(revision)['bundle']['app']['version']
                except (OSError,ValueError,KeyError):pass
        actual=observed.get(tool)
        state='not_prepared' if runtime.get('status')!='ready' else 'unknown' if actual is None else 'unresolved' if target is None else 'current' if actual.lstrip('v')==target.lstrip('v') else 'update_available'
        rows.append({'tool':tool,'installed':actual,'requested':selection,'target':target,'status':state})
    return rows
