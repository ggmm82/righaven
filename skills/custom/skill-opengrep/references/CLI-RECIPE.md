# Ricetta: opengrep

`craft commands opengrep` e `craft tools opengrep` descrivono gli schemi esatti. Gli input sono percorsi assoluti del workspace e l’output deve essere una directory nuova.

```bash
opengrep-cli call scan '{"input":"/mnt/user-data/outputs/JOB/source","rules":"/mnt/user-data/outputs/JOB/rules.yaml","output":"/mnt/user-data/outputs/JOB/scan"}'
```

Usa regole locali, pertinenti alla lingua e alla vulnerabilità cercata. Salva il file di regole insieme al report. Il collaudo rileva eval() in una fixture Python senza eseguirla.

Il collaudo tecnico ripetibile è scripts/acceptance_security.py. Non certifica la sicurezza o la qualità professionale di qualsiasi progetto.

Nel manifest delivery registra report e sorgenti con percorsi e verifiche reali.
