"""Bounded RigHaven adapters, not the complete APIs of the upstream tools."""

try:
    from .schema_types import tool, STRING
except ImportError:
    from schema_types import tool, STRING


TOOLS = {
    'ffmpeg': [
        tool('ffmpeg', 'probe', 'Inspect actual streams, codecs, duration, rates and container metadata with ffprobe.',
             {'input': STRING, 'output': STRING}, ['input', 'output']),
        tool('ffmpeg', 'transcode', 'Create a new media export with explicit codec/rate/size. Preserve authoring projects and dependencies separately.',
             {'input': STRING, 'output': STRING, 'video_codec': {'type': 'string', 'enum': ['libx264', 'libvpx-vp9', 'copy']},
              'audio_codec': {'type': 'string', 'enum': ['aac', 'libopus', 'pcm_s16le', 'copy']},
              'fps': {'type': 'number', 'minimum': 1, 'maximum': 120},
              'width': {'type': 'integer', 'minimum': 16, 'maximum': 3840},
              'height': {'type': 'integer', 'minimum': 16, 'maximum': 2160},
              'start': {'type': 'number', 'minimum': 0, 'maximum': 86400},
              'duration': {'type': 'number', 'minimum': .01, 'maximum': 86400}}, ['input', 'output']),
        tool('ffmpeg', 'extract_audio', 'Extract/decode audio to a new PCM16 WAV with declared sample rate and channels.',
             {'input': STRING, 'output': STRING, 'sample_rate': {'type': 'integer', 'enum': [16000, 44100, 48000]},
              'channels': {'type': 'integer', 'enum': [1, 2]}}, ['input', 'output']),
        tool('ffmpeg', 'mux', 'Mux supplied video and audio from a shared zero origin; preserve video and encode AAC, without asserting sync.',
             {'input': STRING, 'audio': STRING, 'output': STRING}, ['input', 'audio', 'output']),
    ],
    'playwright': [
        tool('playwright', 'test', 'Run an explicit local *.test.cjs with Chromium, one worker, JSON report and failure traces.',
             {'input': STRING, 'output': STRING}, ['input', 'output']),
        tool('playwright', 'execute', 'Run an explicit local Node .cjs browser automation script; keep script, assertions and evidence.',
             {'input': STRING, 'output': STRING}, ['input', 'output']),
        tool('playwright', 'screenshot', 'Capture a web URL or a workspace file URL in headless Chromium. Not a visual approval.',
             {'url': STRING, 'output': STRING, 'width': {'type': 'integer', 'minimum': 320, 'maximum': 3840},
              'height': {'type': 'integer', 'minimum': 240, 'maximum': 2160}}, ['url', 'output']),
    ],
    'aubio': [tool('aubio', 'analyze', 'Estimate onset/beat times in seconds, overall tempo in BPM, pitch in Hz or MIDI-like notes. Estimates do not recognize a song or certify quality.',
        {'input': STRING, 'output': STRING, 'feature': {'type': 'string', 'enum': ['onset', 'beat', 'tempo', 'pitch', 'notes']}}, ['input', 'output', 'feature'])],
    'fluidsynth': [tool('fluidsynth', 'render', 'Offline MIDI + SF2 synthesis into a new portable folder: WAV, MIDI, bank and render settings. No audio device.',
        {'input': STRING, 'output': STRING, 'soundfont': STRING,
         'sample_rate': {'type': 'integer', 'enum': [44100, 48000]}, 'gain': {'type': 'number', 'minimum': 0.01, 'maximum': 2}}, ['input', 'output'])],
    'epubcheck': [tool('epubcheck', 'check', 'Run independent EPUB conformance validation; report errors and warnings, not editorial or visual quality.',
        {'input': STRING, 'output': STRING}, ['input', 'output'])],
    'pandoc': [tool('pandoc', 'convert', 'Convert a structured source into a new document. Preserve templates, bibliography, assets and conversion recipe.',
        {'input': STRING, 'output': STRING, 'from_format': STRING, 'to_format': STRING,
         'standalone': {'type': 'boolean'}, 'template': STRING, 'bibliography': STRING, 'csl': STRING,
         'resource_dir': STRING}, ['input', 'output'])],
    'typst': [tool('typst', 'compile', 'Compile a local .typ source into PDF, SVG or PNG with explicit resource root. Does not certify print readiness.',
        {'input': STRING, 'output': STRING, 'resource_dir': STRING, 'font_dir': STRING}, ['input', 'output'])],
    'freecad': [
        tool('freecad', 'execute', 'Run an explicit Python authoring script in native headless FreeCAD; save .FCStd and geometry evidence in the output folder.',
             {'input': STRING, 'output': STRING}, ['input', 'output']),
        tool('freecad', 'inspect', 'Reopen .FCStd, report native objects, parametric properties and solid volumes. No GUI or engineering certification.',
             {'input': STRING, 'output': STRING}, ['input', 'output']),
        tool('freecad', 'export_step', 'Reopen .FCStd and export selected solid shapes to a new STEP; STEP is not a parametric authoring source.',
             {'input': STRING, 'output': STRING}, ['input', 'output']),
    ],
    'whisper': [tool('whisper', 'transcribe', 'CPU speech transcription into TXT/SRT/JSON with pinned multilingual tiny model. Does not assess music or speaker identity.',
        {'input': STRING, 'output': STRING, 'language': {'type': 'string', 'enum': ['auto', 'it', 'en', 'fr', 'de', 'es', 'pt', 'ja', 'zh']}}, ['input', 'output'])],
}

try:
    from .production_specs import TOOLS as PRODUCTION_TOOLS
except ImportError:
    from production_specs import TOOLS as PRODUCTION_TOOLS
TOOLS.update(PRODUCTION_TOOLS)
try:
    from .design_specs import TOOLS as DESIGN_TOOLS
except ImportError:
    from design_specs import TOOLS as DESIGN_TOOLS
TOOLS.update(DESIGN_TOOLS)

try:from .security_specs import TOOLS as SECURITY_TOOLS
except ImportError:from security_specs import TOOLS as SECURITY_TOOLS
TOOLS.update(SECURITY_TOOLS)

try:from .extended_specs import TOOLS as EXTENDED_TOOLS
except ImportError:from extended_specs import TOOLS as EXTENDED_TOOLS
TOOLS.update(EXTENDED_TOOLS)
