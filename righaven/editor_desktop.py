"""Trusted graphical entrypoint. Document-provided programs are never launched."""
import os
from pathlib import Path
import signal
import subprocess
import time

Path(os.environ['HOME']).mkdir(parents=True,exist_ok=True)
children=[]
def launch(args):
    child=subprocess.Popen(args);children.append(child);return child

def stop():
    for child in reversed(children):
        if child.poll() is None:child.terminate()
    for child in reversed(children):
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:child.kill()

signal.signal(signal.SIGTERM,lambda *_:exit(0))
try:
    launch(['Xvfb',':99','-screen','0','1920x1080x24','-nolisten','tcp']);time.sleep(.8)
    launch(['openbox']);launch(['x11vnc','-display',':99','-localhost','-nopw','-forever','-shared','-xrandr','-rfbport','5900'])
    tokens=Path('/tmp/editor-tokens');tokens.write_text(os.environ['EDITOR_TOKEN']+': 127.0.0.1:5900\n');tokens.chmod(0o600)
    launch(['websockify','--web','/usr/share/novnc','--token-plugin','TokenFile','--token-source',str(tokens),'8080'])
    path=str(Path('/workspace/output')/os.environ['EDITOR_FILE'])
    if os.environ['EDITOR_APP']=='blender':
        if Path(path).suffix.lower()=='.blend':command=['blender','--factory-startup','--disable-autoexec',path]
        else:
            script=Path('/tmp/import_blender.py')
            script.write_text('import bpy,os\nfrom pathlib import Path\np=Path(os.environ["EDITOR_FILE"])\nfull=str(Path("/workspace/output")/p)\nimporters={".glb":bpy.ops.import_scene.gltf,".gltf":bpy.ops.import_scene.gltf,".fbx":bpy.ops.import_scene.fbx,".obj":bpy.ops.wm.obj_import,".stl":bpy.ops.wm.stl_import,".ply":bpy.ops.wm.ply_import}\nbpy.ops.object.select_all(action="SELECT")\nbpy.ops.object.delete(use_global=False)\nimporters[p.suffix.lower()](filepath=full)\nbpy.ops.wm.save_as_mainfile(filepath=str(Path(full).with_suffix(".blend")))\n')
            command=['blender','--factory-startup','--disable-autoexec','--python-exit-code','1','--python',str(script)]
    elif os.environ['EDITOR_APP']=='freecad':
        choices=list(Path('/opt/righaven/apps/freecad').glob('**/squashfs-root/AppRun'))
        if len(choices)!=1:raise RuntimeError('Prepared FreeCAD GUI not found')
        command=[str(choices[0]),path]
    else:raise ValueError('Unknown graphical editor')
    app=launch(command)
    while app.poll() is None:time.sleep(.5)
    raise SystemExit(app.returncode)
finally:stop()
