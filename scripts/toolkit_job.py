"""Native FreeCAD headless job; no GUI imports, output paths supplied by the adapter."""
import json
import os
from pathlib import Path
import runpy
import sys


def main():
    # The adapter launches the official image's bundled Python and module path.
    native_lib = os.environ.get('PATH_TO_FREECAD_LIBDIR')
    if native_lib: sys.path.insert(0, native_lib)
    import FreeCAD as App
    # Embedded Python does not run FreeCADCmd's standard workbench discovery.
    # Include the packaged Mod roots (packages such as PartDesign) and each
    # workbench directory (modules such as Draft). No GUI/add-on init is run.
    module_roots = {Path(App.getHomePath()) / 'Mod', Path(App.getResourceDir()) / 'Mod',
                    Path('/usr/share/freecad/Mod'), Path('/usr/lib/freecad/Mod')}
    for base in sorted(module_roots):
        if base.is_dir():
            sys.path.append(str(base))
            sys.path.extend(str(child) for child in sorted(base.iterdir()) if child.is_dir())
    import Part
    # Load the official public package, which registers its native _PartDesign
    # extension, before constructing or restoring Body/Pad/Pocket documents.
    import PartDesign
    action, source, target = sys.argv[1:]
    target = Path(target)
    if action == 'version':
        print('.'.join(App.Version()[:3])); return
    if action == 'execute':
        os.environ['righaven_JOB_OUTPUT'] = str(target)
        runpy.run_path(source, run_name='__main__')
        return
    document = App.openDocument(source)
    try:
        document.recompute()
        shapes = [obj for obj in document.Objects if hasattr(obj, 'Shape') and not obj.Shape.isNull()]
        if action == 'export_step':
            solids = [obj for obj in shapes if obj.Shape.Solids]
            # A Body and its Pad share the final solid; exporting both doubles
            # geometry. Likewise do not export operands beside their final Cut.
            final_shapes = [obj for obj in solids if not any(parent in solids for parent in obj.InList)]
            if not final_shapes:
                raise ValueError('No final solid shapes to export')
            Part.export(final_shapes, str(target)); return
        objects = []
        dependencies = []
        for obj in document.Objects:
            row = {'name': obj.Name, 'label': obj.Label, 'type': obj.TypeId}
            row['invalid'] = 'Invalid' in obj.State
            if obj in shapes:
                row.update(volume=obj.Shape.Volume, valid=obj.Shape.isValid(), solids=len(obj.Shape.Solids))
            row['dimensions_mm'] = {key: float(getattr(obj, key).Value) for key in ('Length', 'Width', 'Height', 'Radius') if key in obj.PropertiesList}
            objects.append(row)
            for key in obj.PropertiesList:
                kind = obj.getTypeIdOfProperty(key)
                if kind in ('App::PropertyFile', 'App::PropertyFileIncluded'):
                    value = str(getattr(obj, key))
                    if value: dependencies.append(value)
            linked = obj.getLinkedObject() if hasattr(obj, 'getLinkedObject') else None
            if linked and linked.Document != document:
                dependencies.append(linked.Document.FileName)
        target.write_text(json.dumps({'document': document.Name, 'objects': objects,
                                     'dependencies': sorted(set(dependencies))}, indent=2))
    finally:
        App.closeDocument(document.Name)


if __name__ == '__main__':
    main()
