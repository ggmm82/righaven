"""Explain preparation transitions without confusing them with running projects."""

def reason(trigger,tool=''):
    labels={
      'manual':'Preparazione richiesta dall’utente: verifico cache e versioni selezionate.',
      'configuration':'La configurazione dell’ambiente è cambiata: preparo le capacità selezionate.',
      'version_change':'È cambiata la versione predefinita di '+(tool or 'uno strumento')+': preparo una nuova variante.',
      'startup':'Ripristino dopo l’avvio: verifico prima le immagini già conservate.',
    }
    return {'code':trigger,'tool':tool,'message':labels.get(trigger,labels['manual'])}


def difference(previous,spec):
    if not previous:return {'code':'new_combination','message':'Prima preparazione di questa combinazione di programmi e versioni.'}
    if previous.get('core')!=spec.get('core'):
        return {'code':'base_changed','message':'La base software è cambiata: la variante precedente resta distinta da quella richiesta.'}
    changes=sorted(k for k in set(previous.get('versions',{}))|set(spec.get('versions',{})) if previous.get('versions',{}).get(k)!=spec.get('versions',{}).get(k))
    if changes:return {'code':'versions_changed','tools':changes,'message':'Versioni selezionate cambiate: '+', '.join(changes)+'. Riutilizzo gli strumenti compatibili.'}
    if set(previous.get('tools',[]))!=set(spec.get('tools',[])):
        return {'code':'tools_changed','message':'La combinazione di programmi richiesta è cambiata.'}
    return {'code':'image_missing','message':'La ricetta è conservata, ma la sua immagine software non è più disponibile nel runtime.'}
