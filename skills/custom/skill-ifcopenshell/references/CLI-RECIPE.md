# Ricetta verificabile: IfcOpenShell

1. Leggi `ifcopenshell-cli commands` oppure `craft tools ifcopenshell` per gli schemi della versione fissata.
2. Invoca `ifcopenshell-cli call OPERAZIONE '{"input":"/mnt/user-data/...","output":"/mnt/user-data/..."}'` con i campi esatti dello schema. I nomi sono senza prefisso, per esempio `execute`. Output sempre nuovi e separati dagli originali.
3. Le operazioni execute/render richiedono uno script `.py` esplicito; `resource_dir` raccoglie script e risorse relative. Non includere la directory di output fra gli input. Lo script usa `righaven_JOB_OUTPUT` per salvare i documenti.
4. Controlla il documento nativo e l’export, poi ripeti la riapertura dopo aver spostato lo ZIP. Un esito negativo resta un difetto, non una consegna.
5. Compila `delivery` con artifact, editable_source, source_archive, guida d’uso e componenti effettive. Non limitarti a un file piatto.

Fonte API: https://docs.ifcopenshell.org/. Prove native ripetibili: `scripts/acceptance_production.py`. La copertura è limitata alle prove eseguite, non a ogni funzione upstream.

## Authoring BIM semantico

- In uno script `execute` usa `ifcopenshell.api.run('project.create_file', version='IFC4')`, `root.create_entity`, `unit.assign_unit`, `aggregate.assign_object` e `spatial.assign_container` per struttura e relazioni. Dichiara esplicitamente lo schema e le unità; leggi la documentazione delle firme correnti.
- Crea contesti e rappresentazioni con `context.add_context`, `geometry.add_wall_representation` e `geometry.assign_representation` quando serve geometria. Un elenco di entità senza rappresentazioni non è una consegna geometrica.
- Salva con `model.write(str(Path(os.environ['righaven_JOB_OUTPUT'])/'building.ifc'))`. `inspect` riporta entità/progetti; `check` usa `ifcopenshell.validate.validate` con `json_logger`, propagando errori veri.
- Verifica separatamente quantità, coordinate, aperture, proprietà e forma rispetto al brief. Per soluzioni parametriche usa FreeCAD quando pertinente; un IFC non conserva uno storico `.FCStd` e uno STEP non conserva tutte le proprietà BIM.
