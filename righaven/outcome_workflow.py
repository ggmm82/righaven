"""A small, domain-independent path selected explicitly by the owner."""


def definition():
    return {'version': 2, 'guidance':
        'The owner chose a first working result. Produce the actual requested product early, with appropriate professional finish, '
        'including its editable sources, instructions and verification in the same result. Keep every explicit requirement and selected connection. '
        'Do not expand the goal into cataloging, deployment, recurring automation or extra deliverables unless the goal needs them. '
        'The recipe is expertise, not a mandatory checklist of tools. Technical checks run internally; ask the owner once about the visible result. '
        'After approval, present those same verified files. Do not launch a packaging or repeated review assignment just to relabel them final. '
        'Further refinement or an additional review is performed only when requested by the owner or a specific unmet requirement needs correction.',
        'stages': [
            {'id': 'preview', 'title': {'it': 'Risultato da provare', 'en': 'Working result'},
             'outcome': {'it': 'Risultato utilizzabile, sorgenti modificabili, verifiche e istruzioni essenziali',
                         'en': 'Usable result, editable sources, verification and concise instructions'}, 'depends_on': [], 'gate': True}]}
