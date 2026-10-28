# Ricetta verificabile: PyMeshLab

1. Leggi `pymeshlab-cli commands` oppure `craft tools pymeshlab` per gli schemi della versione fissata.
2. Invoca `pymeshlab-cli call OPERAZIONE '{"input":"/mnt/user-data/...","output":"/mnt/user-data/..."}'` con i campi esatti dello schema. I nomi sono senza prefisso, per esempio `execute`. Output sempre nuovi e separati dagli originali.
3. Le operazioni execute/render richiedono uno script `.py` esplicito; `resource_dir` raccoglie script e risorse relative. Non includere la directory di output fra gli input. Lo script usa `righaven_JOB_OUTPUT` per salvare i documenti.
4. Controlla il documento nativo e l’export, poi ripeti la riapertura dopo aver spostato lo ZIP. Un esito negativo resta un difetto, non una consegna.
5. Compila `delivery` con artifact, editable_source, source_archive, guida d’uso e componenti effettive. Non limitarti a un file piatto.

Fonte API: https://pymeshlab.readthedocs.io/. Prove native ripetibili: `scripts/acceptance_production.py`. La copertura è limitata alle prove eseguite, non a ogni funzione upstream.

## Riparazione misurata della geometria

- `filters` salva i nomi realmente registrati. Scopri API e parametri nel runtime con `pymeshlab.print_filter_parameter_list` prima di `MeshSet.apply_filter`; il nome Python (`meshing_remove_duplicate_vertices`) differisce dal nome visuale nel MLX (`Remove Duplicate Vertices`).
- `MeshSet.load_new_mesh`, `current_mesh`, `vertex_number`, `face_number`, `bounding_box` misurano il dato prima/dopo. Per topologia usa `get_topological_measures`; confronta componenti, bordi, manifold, volumi e perdita di dettagli rispetto all’obiettivo.
- `apply` accetta una sola mesh priva di texture e un filtro `.mlx`, preserva input e procedura, salva `mesh.ply`, `project.mlp` e misure prima/dopo. È una riparazione esplicita, non una rigenerazione artistica del modello.
- Per progetti multipli, texture e UV usa `execute` con `resource_dir`, API native, export e controlli dedicati. Conserva OBJ/MTL, texture, UV e ricetta; non appiattire asset texturizzati nella scorciatoia PLY.
- Una mesh watertight può avere un design mediocre: confronta silhouette, scala, normali e dettagli con il riferimento. Rimanda al modellatore pertinente se serve cambiare la forma progettuale.

Il controllo portabilità comprende MLP, geometrie PLY/OBJ/STL/OFF, materiali MTL e texture referenziate. Normalizza le opzioni nelle righe texture MTL prima del trasferimento: il verificatore le rifiuta esplicitamente invece di dichiarare una completezza non provata. Formati di dipendenze diversi richiedono una conversione verificata.

Per la sola introspezione dei parametri, con la capacità abilitata, usa il Python isolato del medesimo runtime: `/opt/righaven/apps/pymeshlab/venv/bin/python -c "import pymeshlab; pymeshlab.print_filter_parameter_list('meshing_remove_duplicate_vertices')"`. Non serve avviare una produzione per consultare un filtro. La policy nasconde anche questo percorso quando lo strumento è disattivato; non cercare installazioni alternative.
