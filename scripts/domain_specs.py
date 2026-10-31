"""Lightweight domain CLIs: accounting, chemistry, bioinformatics, logic, climate data,
metadata and privacy, fonts, barcodes, configuration linters, data, music notation and prose."""
try:from .schema_types import tool,STRING
except ImportError:from schema_types import tool,STRING

BOOL={'type':'boolean'}
LENGTH={'type':'integer','minimum':1,'maximum':100000000}
SECONDS={'type':'integer','minimum':1,'maximum':600}


def op(app,name,description,extra=None,required=None):
    return tool(app,name,description,{'input':STRING,'output':STRING,**(extra or {})},['input','output',*(required or [])])


def enum(*values):
    return {'type':'string','enum':list(values)}


TOOLS={
 'hledger':[
  op('hledger','check','Check a plain-text journal: parsing, balanced transactions and balance assertions; strict also requires declared accounts and commodities. Errors are reported, never corrected.',{'strict':BOOL}),
  op('hledger','report','Run a native report on a plain-text journal and save CSV; the journal stays the editable source. Totals reflect only the recorded entries.',
     {'report':enum('balance','balancesheet','incomestatement','cashflow','register')},['report'])],
 'beancount':[
  op('beancount','check','Check a Beancount ledger: syntax, open accounts, balanced postings and balance assertions. Errors are reported, never corrected.'),
  op('beancount','query','Run a read-only BQL query on a Beancount ledger and save CSV results.',{'query':STRING},['query'])],
 'openbabel':[
  op('openbabel','convert','Convert molecules between SMILES, SDF, MOL, MOL2, XYZ, PDB, CML and InChI; optionally generate 3D coordinates. Generated geometry is a starting point, not a validated conformer.',
     {'format':enum('sdf','mol','mol2','xyz','pdb','cml','smi','can','inchi'),'generate_3d':BOOL},['format']),
  op('openbabel','properties','Compute formula, molecular weight, logP and TPSA per molecule. Descriptors are estimates, not measurements.')],
 'xtb':[
  op('xtb','optimize','Optimize a molecular geometry (XYZ) with the GFN2-xTB semiempirical method; save the optimized structure and native log. Semiempirical energies are approximate.',
     {'charge':{'type':'integer','minimum':-10,'maximum':10},'unpaired':{'type':'integer','minimum':0,'maximum':10}})],
 'seqkit':[
  op('seqkit','stats','Summarize FASTA/FASTQ files: counts, lengths, N50, GC and quality fractions as TSV.'),
  op('seqkit','filter','Keep sequences within a length range, optionally reverse-complemented, into a new FASTA/FASTQ.',
     {'min_length':LENGTH,'max_length':LENGTH,'reverse_complement':BOOL})],
 'samtools':[
  op('samtools','flagstat','Count mapped, paired and duplicate reads of a SAM/BAM/CRAM alignment as TSV.'),
  op('samtools','sort','Sort an alignment by coordinate into BAM and build its index.')],
 'bcftools':[
  op('bcftools','stats','Summarize a VCF/BCF: records, SNPs, indels, transitions/transversions and quality distributions.')],
 'minimap2':[
  op('minimap2','align','Align reads or assemblies to a reference FASTA into SAM with an explicit preset; alignment is evidence for interpretation, not a variant call.',
     {'reference':STRING,'preset':enum('sr','map-ont','map-pb','map-hifi','asm5','asm20','splice')},['reference'])],
 'mafft':[
  op('mafft','align','Build a multiple sequence alignment from FASTA with MAFFT --auto; save the aligned FASTA.')],
 'z3':[
  op('z3','solve','Check an SMT-LIB 2 problem with the Z3 solver; report sat, unsat or unknown with the model or core it prints. unknown is not a proof.',
     {'timeout_seconds':SECONDS})],
 'minizinc':[
  op('minizinc','solve','Solve a MiniZinc constraint model (optionally with a .dzn data file) using Gecode within a time limit; save every printed solution and the optimality status.',
     {'data':STRING,'all_solutions':BOOL,'timeout_seconds':SECONDS})],
 'maxima':[
  op('maxima','evaluate','Run a Maxima batch file (symbolic algebra, calculus, equations) and save the transcript. Check results against the problem statement.')],
 'pari':[
  op('pari','evaluate','Run a PARI/GP script (number theory, exact arithmetic, polynomials) and save its output.')],
 'cdo':[
  op('cdo','info','Describe a NetCDF/GRIB dataset: variables, grid, levels and time steps.'),
  op('cdo','statistic','Compute a time or field statistic of a NetCDF/GRIB dataset into a new NetCDF file.',
     {'operator':enum('timmean','timmin','timmax','timstd','yearmean','monmean','daymean','fldmean','fldmin','fldmax')},['operator'])],
 'nco':[
  op('nco','inspect','Print the metadata of a NetCDF file: dimensions, variables, attributes and units.'),
  op('nco','subset','Extract selected variables of a NetCDF file into a new file.',{'variables':STRING},['variables'])],
 'exiftool':[
  op('exiftool','read','Read embedded metadata (EXIF, IPTC, XMP, GPS, document properties) of a file into grouped JSON, without changing it.')],
 'mat2':[
  op('mat2','inspect','List the metadata mat2 would remove from a document, image or media file.'),
  op('mat2','clean','Write a cleaned copy without metadata; the original is preserved. Visible content (faces, text, watermarks) is not anonymized.')],
 'fonttools':[
  op('fonttools','inspect','List the OpenType tables of a font file with their checksums and sizes.'),
  op('fonttools','subset','Subset a font to the characters of a given text and save TTF, WOFF or WOFF2; licences must allow subsetting.',
     {'text':STRING,'flavor':enum('ttf','woff','woff2')},['text'])],
 'fontforge':[
  op('fontforge','convert','Open a font (TTF, OTF, SFD, UFO, WOFF) and generate it in another format, reporting the glyph count. Font licences still apply.',
     {'format':enum('ttf','otf','woff','woff2','sfd')},['format'])],
 'zint':[
  tool('zint','encode','Encode data as a barcode or 2D code (QR, Data Matrix, PDF417, Code 128, EAN-13, GS1-128) in SVG or PNG; check scannability on the final medium.',
       {'data':STRING,'symbology':enum('qrcode','datamatrix','pdf417','code128','ean13','gs1-128'),'format':enum('svg','png'),'output':STRING},['data','symbology','output'])],
 'shellcheck':[
  op('shellcheck','lint','Analyze a shell script for bugs and portability issues; save JSON findings. No finding does not prove the script is correct.')],
 'hadolint':[
  op('hadolint','lint','Lint a Dockerfile against best practices (including ShellCheck on RUN steps); save JSON findings.')],
 'actionlint':[
  op('actionlint','lint','Check a GitHub Actions workflow: syntax, expressions, job dependencies and embedded scripts; save JSON findings.')],
 'tflint':[
  op('tflint','lint','Lint a Terraform module directory with the bundled core rules (no provider plugins downloaded); save JSON findings.')],
 'spectral':[
  op('spectral','lint','Lint an OpenAPI or AsyncAPI document with the standard Spectral rulesets or a supplied ruleset; save JSON findings.',{'ruleset':STRING})],
 'jq':[
  op('jq','transform','Apply a jq filter to JSON and save the result; the filter is kept with the output.',{'filter':STRING},['filter'])],
 'yq':[
  op('yq','transform','Apply a jq filter to YAML (or XML/TOML read as YAML) and save YAML output.',{'filter':STRING},['filter'])],
 'miller':[
  op('miller','transform','Convert or transform CSV, TSV or JSON with Miller; an optional DSL script file is kept with the output.',
     {'script':STRING,'input_format':enum('csv','tsv','json'),'output_format':enum('csv','tsv','json','markdown')})],
 'ajv':[
  op('ajv','validate','Validate JSON data against a JSON Schema (draft 2020-12, 2019-09 or 07) and save all errors.',
     {'schema':STRING,'draft':enum('2020','2019','draft7')},['schema'])],
 'mjml':[
  op('mjml','compile','Compile an MJML email template into responsive HTML with strict validation. Rendering still differs by email client.')],
 'abcm2ps':[
  op('abcm2ps','engrave','Engrave ABC music notation into SVG pages, one per tune.')],
 'abcmidi':[
  op('abcmidi','midi','Convert ABC music notation into a MIDI file for listening checks.')],
 'hunspell':[
  op('hunspell','check','List words not found in the Italian or English Hunspell dictionary; names and technical terms need human review.',
     {'language':enum('it_IT','en_US')})],
 'vale':[
  op('vale','lint','Check prose against style rules (Vale built-in rules or a supplied .vale.ini with local styles); save JSON alerts.',{'config':STRING})],
}
