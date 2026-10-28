import { enUS } from './en-US';
import type { Translations } from './types';

// Untranslated advanced surfaces explicitly fall back to English.
export const itIT: Translations = {
  ...enUS,
  locale: { localName: 'Italiano' },
  common: { ...enUS.common, home: 'Home', settings: 'Impostazioni', delete: 'Elimina',
    edit: 'Modifica', rename: 'Rinomina', share: 'Condividi', close: 'Chiudi',
    more: 'Altro', search: 'Cerca', loadMore: 'Carica altri', download: 'Scarica',
    thinking: 'Elaborazione', artifacts: 'Risultati', public: 'Pubblico', custom: 'Personalizzato',
    loading: 'Caricamento…', error: 'Errore:', version: 'Versione', lastUpdated: 'Ultimo aggiornamento',
    code: 'Codice', preview: 'Anteprima', cancel: 'Annulla', save: 'Salva', install: 'Installa',
    create: 'Crea', import: 'Importa', export: 'Esporta', regenerate: 'Rigenera',
    openInNewWindow: 'Apri in una nuova finestra', showingOf: (loaded, total) => `${loaded} di ${total}` },
  sidebar: { ...enUS.sidebar, newChat: 'Nuova chat', chats: 'Chat', channels: 'Canali',
    recentChats: 'Chat recenti', demoChats: 'Esempi', agents: 'Agenti',
    scheduledTasks: 'Attività pianificate', agentsDisabledTooltip: 'Funzione disattivata' },
  welcome: { ...enUS.welcome, greeting: 'Benvenuto in RigHaven',
    description: 'Definisci il risultato da ottenere. RigHaven organizza ruoli, strumenti e ambienti per realizzarlo.',
    createYourOwnSkill: 'Crea una skill' },
  settings: { ...enUS.settings, title: 'Impostazioni',
    description: 'Configura il tuo spazio di lavoro RigHaven.' },
};
