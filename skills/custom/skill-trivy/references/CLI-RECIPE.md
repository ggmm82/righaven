# Ricetta: trivy

`craft commands trivy` e `craft tools trivy` descrivono gli schemi esatti. Gli input sono percorsi assoluti del workspace e l’output deve essere una directory nuova.

```bash
trivy-cli call config '{"input":"/mnt/user-data/outputs/JOB/source","output":"/mnt/user-data/outputs/JOB/config-scan"}'
```

Config funziona senza rete con controlli incorporati. Per le vulnerabilità esegui database_update in una nuova directory, poi passa quella directory come database a vulnerabilities. Conserva metadata e data del DB: non distribuire soltanto il numero dei finding. SBOM produce un inventario, non un verdetto. Il collaudo verifica un Dockerfile e il relativo report senza rete; il download del DB non è provato offline.

Il collaudo tecnico ripetibile è scripts/acceptance_security.py. Non certifica la sicurezza o la qualità professionale di qualsiasi progetto.

Nel manifest delivery registra report e sorgenti con percorsi e verifiche reali.
