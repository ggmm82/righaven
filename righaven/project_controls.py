"""Application-generated run controls do not change the product acceptance brief."""
RESUME_INSTRUCTIONS=frozenset({
    'Riprendi il progetto dal punto attuale. Considera le mie risposte e le scelte aperte sul risultato, conserva i file validi e procedi con la prossima attività utile.',
    'Resume the project from its current state. Consider my answers and open outcome choices, preserve valid files, and proceed with the next useful activity.',
})

def operational_resume(text):
    # Exact application controls only. A genuine request beginning with "resume"
    # or containing new requirements must remain in the acceptance contract.
    return isinstance(text,str) and text.strip() in RESUME_INSTRUCTIONS
