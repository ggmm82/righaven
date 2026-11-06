"""Shared, capability-scoped file associations. Imports are not native sources."""
from pathlib import Path

# Browser editors use their selected, checksum-verified upstream release.
# An available binary/web page is not evidence of an editing round trip.
CRAFT = {
 'photocraft':('PhotoCraft','.psd .psb .ora','.png .jpg .jpeg .webp .tif .tiff .bmp'),
 'vectorcraft':('VectorCraft','.vectorcraft .svg','.pdf .png'),
 'filmcraft':('FilmCraft','.fcproj','.mp4 .mov .mkv .webm .wav .mp3'),
 'lightcraft':('LightCraft','','.dng .nef .cr2 .cr3 .arw .raf .rw2 .tif .tiff .jpg .jpeg'),
 'pdfcraft':('PDFCraft','.pdf',''),
 'effectcraft':('EffectCraft','.ecproj','.svg .png .jpg .jpeg .mp4'),
 'designcraft':('DesignCraft','.designcraft','.idml .pdf .svg'),
 'gridcraft':('GridCraft','.xlsx','.ods .csv .tsv'),
 'wordcraft':('WordCraft','.docx .odt .rtf','.doc .txt .md .html'),
 'deckcraft':('DeckCraft','.deckcraft .pptx','.odp .pdf'),
 'cadcraft':('CADCraft','.dxf','.dwg'),
 'soundcraft':('SoundCraft','.scraft','.wav .flac .mp3 .ogg .mid .midi'),
 'figcraft':('FigCraft','.figcraft','.svg .png .jpg .jpeg'),
}
TEXT = '.txt .md .markdown .csv .tsv .json .yaml .yml .toml .ini .py .js .jsx .ts .tsx .css .html .sql .xml .sh .r .qmd .typ .d2 .puml .mmd .dsl .svg'


def definitions():
    rows=[{'id':key,'name':value[0],'tool':key,'mode':'browser','package':'craft-web',
           'native_extensions':value[1].split(),'import_extensions':value[2].split(),
           'integration':'verified' if key in ('wordcraft','photocraft') else 'preview'} for key,value in CRAFT.items()]
    for key,name,tool,mode,package,native,imports in [
        ('text','Text and code',None,'browser','builtin',TEXT,''),
        ('excalidraw','Excalidraw','excalidraw','browser','builtin','.excalidraw',''),
        ('bpmn','BPMN','bpmn','browser','builtin','.bpmn',''),
        ('jupyter','JupyterLab','jupyter','service','notebook','.ipynb '+TEXT,''),
        ('blender','Blender','blender','desktop','desktop','.blend','.glb .gltf .obj .stl .fbx .ply'),
        ('freecad','FreeCAD','freecad','desktop','desktop','.fcstd','.step .stp .iges .igs .brep .stl')]:
        rows.append({'id':key,'name':name,'tool':tool,'mode':mode,'package':package,
                     'native_extensions':native.split(),'import_extensions':imports.split(),
                     'integration':'verified' if mode=='browser' else 'preview'})
    return rows


def editor(identifier,allowed):
    value=next((row for row in definitions() if row['id']==identifier),None)
    if value is None or value['tool'] and value['tool'] not in allowed:
        raise ValueError('Editor unavailable or disabled in your capabilities')
    return value


def candidates(filename,allowed):
    suffix=Path(filename).suffix.lower();rows=[]
    for row in definitions():
        if row['tool'] and row['tool'] not in allowed:continue
        native=suffix in row['native_extensions']
        if native or suffix in row['import_extensions']:
            rows.append({**row,'opening_mode':'text' if row['id']=='jupyter' and suffix!='.ipynb' else '', 'relationship':'source' if native else 'import',
                         'notice':'' if native else 'Import creates a new document; original editing history may be unavailable.'})
    return sorted(rows,key=lambda row:(row['relationship']!='source',row['id']=='text' or row['opening_mode']=='text',row['opening_mode']=='text',row['name']))
