"""Check declared visual-event times against distinct transients in the actual master.

A numerical cue check is not listening and cannot identify a sound's meaning.
Ambiguous or continuous audio stays not_run, never silently passed.
"""
from array import array
import math
from pathlib import Path
import statistics
import subprocess
import sys


def check_timing(handoff, *, required=False):
    manifest=(handoff.get('delivery') or {}).get('timing')
    if manifest is None:
        return {'status':'not_run','cues':[], 'issues':['Sincronismo degli eventi non verificato sul master finale.'] if required else []}
    try:
        if not isinstance(manifest,dict):raise ValueError('mappa temporale non valida')
        master=manifest.get('master');cues=manifest.get('cues')
        if master not in handoff.get('output_files',[]) or Path(master).suffix.lower() not in ('.mp4','.mov','.mkv','.webm'):
            raise ValueError('il master deve essere il video effettivamente consegnato')
        if not isinstance(cues,list) or not 1<=len(cues)<=12:raise ValueError('indicare da 1 a 12 eventi osservati')
        checked=[]
        for cue in cues:
            if not isinstance(cue,dict):raise ValueError('evento non valido')
            name,seconds,tolerance=cue.get('name'),cue.get('visual_seconds'),cue.get('tolerance_seconds',.12)
            if (not isinstance(name,str) or not 1<=len(name)<=140 or type(seconds) not in (int,float)
                    or not math.isfinite(seconds) or not 0<=seconds<=86400 or type(tolerance) not in (int,float)
                    or not math.isfinite(tolerance) or not .01<=tolerance<=.25):
                raise ValueError('evento, istante visivo e tolleranza 0.01–0.25 s obbligatori')
            start=max(0,seconds-2)
            decoded=subprocess.run(['ffmpeg','-v','error','-ss',str(start),'-i',master,'-t','4',
                '-vn','-ac','1','-ar','8000','-f','s16le','pipe:1'],capture_output=True,timeout=30)
            if decoded.returncode:raise ValueError('audio del master non decodificabile')
            samples=array('h');samples.frombytes(decoded.stdout)
            if sys.byteorder!='little':samples.byteswap()
            bins=[math.sqrt(sum(v*v for v in samples[i:i+160])/len(samples[i:i+160])) for i in range(0,len(samples),160)]
            if not bins:raise ValueError('audio assente nella finestra dell’evento')
            index=max(range(len(bins)),key=bins.__getitem__);peak=bins[index]
            other=max([v for i,v in enumerate(bins) if abs(i-index)>12] or [0])
            observed=start+(index+.5)*.02;delta=observed-seconds
            distinctive=peak>128 and peak>max(1,statistics.median(bins))*1.8 and peak>other*1.2
            status=('passed' if abs(delta)<=tolerance else 'failed') if distinctive else 'not_run'
            checked.append({'name':name,'visual_seconds':seconds,'audio_transient_seconds':round(observed,3),
                'delta_seconds':round(delta,3),'tolerance_seconds':tolerance,'status':status,
                'notice':'Picco numerico nel master; identità sonora e significato dell’evento visivo richiedono revisione.'})
        status='failed' if any(c['status']=='failed' for c in checked) else 'passed' if all(c['status']=='passed' for c in checked) else 'not_run'
        return {'status':status,'master':master,'cues':checked,'issues':[
            c['name']+(': audio fuori tempo di '+str(c['delta_seconds'])+' s' if c['status']=='failed' else ': transiente non distinguibile, serve verifica percettiva')
            for c in checked if c['status']!='passed']}
    except (ValueError,TypeError,OSError,subprocess.SubprocessError) as error:
        return {'status':'not_run','cues':[],'issues':['Sincronismo non verificato: '+str(error)[:300]]}
