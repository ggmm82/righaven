"""Complementary native capabilities, independent of professional role names."""
try:
    from .schema_types import tool, STRING
except ImportError:
    from schema_types import tool, STRING

TOOLS = {
    'musescore': [
        tool('musescore', 'inspect', 'Reopen a score in MuseScore and read native score metadata.', {'input': STRING, 'output': STRING}, ['input','output']),
        tool('musescore', 'convert', 'Export a score with offline MuseScore Basic sounds. Preserve MSCZ/MusicXML as editable sources; audio is an export.', {'input': STRING, 'output': STRING}, ['input','output']),
    ],
    'ifcopenshell': [
        tool('ifcopenshell', 'execute', 'Run an explicit IFC authoring script with the native IfcOpenShell API; preserve script and IFC.', {'input': STRING, 'output': STRING, 'resource_dir': STRING}, ['input','output']),
        tool('ifcopenshell', 'inspect', 'Read native IFC entities, schema, projects and units; not engineering certification.', {'input': STRING, 'output': STRING}, ['input','output']),
        tool('ifcopenshell', 'check', 'Validate the IFC schema with the native validator, reporting actual issues.', {'input': STRING, 'output': STRING}, ['input','output']),
    ],
    'manim': [tool('manim', 'render', 'Render an explicit Scene with Cairo on CPU, retaining Python and supplied resources. Math can use SVG from the existing Typst tool; LaTeX is not bundled.',
        {'input': STRING, 'output': STRING, 'scene': STRING, 'quality': {'type':'string','enum':['draft','standard','high']}, 'resource_dir': STRING}, ['input','output','scene'])],
    'opentimelineio': [
        tool('opentimelineio', 'execute', 'Author or transform an OTIO timeline with the native API. This is not a video editor or renderer.', {'input': STRING,'output': STRING, 'resource_dir': STRING}, ['input','output']),
        tool('opentimelineio', 'inspect', 'Inspect rational timing, tracks, clips and media references in native OTIO.', {'input': STRING,'output': STRING}, ['input','output']),
        tool('opentimelineio', 'check', 'Check native timeline ranges and local media references. Does not decode media or certify perceptual synchronization.', {'input': STRING,'output': STRING}, ['input','output']),
        tool('opentimelineio', 'pack', 'Create a portable native OTIOD bundle with media, for inclusion in a source ZIP. Reject missing or remote media.', {'input': STRING,'output': STRING}, ['input','output']),
    ],
    'pymeshlab': [
        tool('pymeshlab', 'execute', 'Run an explicit native mesh-processing script. Preserve input geometry and filter/Python recipe; not parametric CAD authoring.', {'input': STRING,'output': STRING, 'resource_dir': STRING}, ['input','output']),
        tool('pymeshlab', 'inspect', 'Reopen a mesh or MLP project and measure actual geometry.', {'input': STRING,'output': STRING}, ['input','output']),
        tool('pymeshlab', 'apply', 'Apply an explicit native MLX filter script and save geometry, recipe and a portable MLP project.', {'input': STRING,'filters': STRING,'output': STRING}, ['input','filters','output']),
        tool('pymeshlab', 'filters', 'Save the actually registered native filter names; registration is not an execution proof.', {'output': STRING}, ['output']),
    ],
}
