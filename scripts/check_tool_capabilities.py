#!/usr/bin/env python3
"""Verify the complete pinned registry map and a genuine native MIDI instrument workflow."""
import argparse
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
try:
    from .capability_catalog import command_ids
except ImportError:
    from capability_catalog import command_ids


def validate(root, *, native=False, catalog_dir=None):
    root=Path(root)
    lock=json.loads((root/'versions.lock.json').read_text())
    file=root/'tool-capabilities.json'
    if not file.exists():file=root/'config/tool-capabilities.json'
    data=json.loads(file.read_text());apps={a['id']:a for a in lock['applications']}
    entries=data['applications'];seen=set();report=[]
    for entry in entries:
        identifier=entry['id']
        if identifier in seen or identifier not in apps:raise ValueError('Strumento duplicato o sconosciuto: '+identifier)
        seen.add(identifier)
        if entry['version']!=apps[identifier]['version']:raise ValueError('Versione capacità non aggiornata: '+identifier)
        ids=set(entry['catalog_ids'])
        if not ids or len(ids)!=len(entry['catalog_ids']) or len(ids)!=entry['catalog_count']:raise ValueError('Inventario comandi non valido: '+identifier)
        if not all(isinstance(entry.get(k),str) and entry[k].strip() for k in ('choose_for','sources','limits','reference')):
            raise ValueError('Scelta, sorgenti, limiti o fonte mancanti: '+identifier)
        if not entry.get('groups'):raise ValueError('Obiettivi operativi mancanti: '+identifier)
        expected_hash=hashlib.sha256(('\n'.join(sorted(ids))+'\n').encode()).hexdigest()
        if entry.get('ids_sha256')!=expected_hash:raise ValueError('Identità del catalogo non aggiornata: '+identifier)
        for group in entry['groups']:
            if group['evidence']!='registered' or not group['commands'] or set(group['commands'])-ids:
                raise ValueError('Capacità o livello di prova non valido: '+identifier)
        if native or catalog_dir:
            if catalog_dir and identifier not in ('blender','calibre') and not apps[identifier].get('adapter'):
                text=(Path(catalog_dir)/identifier/'commands.txt').read_text()
            else:
                argv=[apps[identifier]['executable'],*apps[identifier]['registry_args']]
                result=subprocess.run(argv,capture_output=True,text=True,timeout=30,check=True)
                text=result.stdout
            actual=set(command_ids(text))
            if ids!=actual:raise ValueError(identifier+': catalogo diverso dalla release documentata; missing='+str(sorted(ids-actual)[:8])+', extra='+str(sorted(actual-ids)[:8]))
        report.append({'id':identifier,'version':entry['version'],'registered_ids':len(ids),'groups':len(entry['groups'])})
    if seen!=set(apps):raise ValueError('Mancano le capacità di strumenti installati')
    return report


def check_bounce(path):
    """Decode genuine audio, including WAV extensible on Debian's Python 3.11."""
    probe=subprocess.run(['ffprobe','-v','error','-select_streams','a:0',
        '-show_entries','stream=sample_rate,channels','-of','json',str(path)],
        capture_output=True,text=True,check=True,timeout=30)
    streams=json.loads(probe.stdout).get('streams',[])
    assert len(streams)==1 and streams[0]['sample_rate']=='48000' and streams[0]['channels']==2, 'Unexpected native bounce format.'
    # Do not resample or remix: validate the frames actually present in the file.
    decoded=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-map','0:a:0',
        '-f','s16le','-acodec','pcm_s16le','pipe:1'],capture_output=True,check=True,timeout=30).stdout
    assert len(decoded)==96000*2*2, 'Native bounce must contain exactly two seconds.'
    assert any(decoded), 'Native synthesis is silent.'


def native_soundcraft(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    def run(*args):
        return subprocess.run(['soundcraft-cli',*map(str,args)],capture_output=True,text=True,check=True,timeout=45).stdout
    def command(name,args):return name+'='+json.dumps(args)
    base=output/'instrument.scraft'
    run('run','--cmd',command('session.new',{'name':'Native instrument fixture','sample_rate':48000}),
        '--cmd',command('track.new',{'kind':'instrument','instrument':'subtractive_synth','name':'Lead'}),'--save',base)
    value=json.loads(base.read_text());track=value['tracks'][0]['id']
    clipfile=output/'with-clip.scraft'
    run('run','--in',base,'--cmd',command('midi.new_clip',{'track':track,'start':0,'end':96000}),'--save',clipfile)
    value=json.loads(clipfile.read_text());clip=value['tracks'][0]['playlists'][0]['clips'][0]['id']
    final=output/'editable.scraft';mix=output/'mix.wav'
    argv=['run','--in',clipfile]
    for i,pitch in enumerate((60,64,67)):
        argv += ['--cmd',command('midi.note_add',{'clip':clip,'pitch':pitch,'start_ticks':i*480,'length_ticks':480,'velocity':90})]
    # CLI bounds are seconds; MCP bounce_mix bounds are samples.
    run(*argv,'--save',final,'--bounce',mix,'--start','0','--end','2')
    value=json.loads(final.read_text())
    assert value['tracks'][0]['instrument']['plugin']=='subtractive_synth'
    assert len(value['tracks'][0]['playlists'][0]['clips'][0]['content']['Midi']['sequence']['notes'])==3
    assert not value.get('sources'), 'The fixture must synthesize MIDI, not import a WAV.'
    relocated=output/'relocated';relocated.mkdir(exist_ok=True);shutil.copy2(final,relocated/final.name)
    run('run','--in',relocated/final.name,'--inspect','--bounce',relocated/'reopened.wav','--end','2')
    for path in (mix,relocated/'reopened.wav'):
        check_bounce(path)
    return {'instrument':'subtractive_synth','midi_notes':3,'duration_seconds':2,'sample_rate':48000,
            'relocated_native_reopen':True,'listening':'not_run','note':'Functional native authoring fixture, not a musical-quality benchmark.'}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,default=Path('/opt/righaven'))
    parser.add_argument('--native',action='store_true');parser.add_argument('--catalog-dir',type=Path)
    parser.add_argument('--soundcraft-authoring',action='store_true');parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report={'tools':validate(args.root,native=args.native,catalog_dir=args.catalog_dir)}
    if args.soundcraft_authoring:
        folder=args.output.parent/'soundcraft-authoring' if args.output else Path(tempfile.mkdtemp(prefix='soundcraft-capabilities-'))
        report['soundcraft_authoring']=native_soundcraft(folder)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print('Capability audit OK:',len(report['tools']),'tools;',sum(r['registered_ids'] for r in report['tools']),'registered IDs;',
          'native MIDI and relocated session passed' if 'soundcraft_authoring' in report else 'registry audit only')


if __name__=='__main__':main()
