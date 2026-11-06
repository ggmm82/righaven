"""Application-generated run controls do not change the product acceptance brief."""
RESUME_INSTRUCTIONS=frozenset({
    'Prosegui il percorso guidato salvato con harness_journey. Leggi prima gli allegati e le mie scelte; presenta il prossimo risultato utile. Non chiedermi configurazioni tecniche. Mantieni l’obiettivo originale e usa le connessioni che ho scelto; non sostituire una destinazione richiesta con una prova locale.',
    'Continue the saved guided project with harness_journey. Read attachments and my choices first; present the next useful result. Do not ask me to write technical configuration. Keep the original objective and use my selected connections; do not replace a requested destination with a local demonstration.',
    'Prosegui il percorso guidato salvato con harness_journey. Leggi prima gli allegati e le mie scelte; presenta il prossimo risultato utile. Non chiedermi configurazioni tecniche. Le connessioni sono facoltative.',
    'Continue the saved guided project with harness_journey. Read attachments and my choices first; present the next useful result. Do not ask me to write technical configuration. Connections are optional.',
    'Applica la mia scelta del metodo salvata nel progetto. Spiega la prossima prova utile e procedi entro i vincoli concordati.',
    'Apply my saved method choice. Explain the next useful trial and proceed within the agreed constraints.',
    'Riprendi il progetto dal punto attuale. Considera le mie risposte e le scelte aperte sul risultato, conserva i file validi e procedi con la prossima attività utile.',
    'Resume the project from its current state. Consider my answers and open outcome choices, preserve valid files, and proceed with the next useful activity.',
})

def operational_resume(text):
    # Exact application controls only. A genuine request beginning with "resume"
    # or containing new requirements must remain in the acceptance contract.
    return isinstance(text,str) and text.strip() in RESUME_INSTRUCTIONS
