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
  sidebar: { ...enUS.sidebar, newChat: 'Nuovo incarico', chats: 'Attività', channels: 'Canali',
    recentChats: 'Incarichi recenti', demoChats: 'Esempi', agents: 'Agenti',
    scheduledTasks: 'Attività pianificate', agentsDisabledTooltip: 'Funzione disattivata' },
  welcome: { ...enUS.welcome, greeting: 'Benvenuto in RigHaven',
    description: 'Definisci il risultato da ottenere. RigHaven organizza ruoli, strumenti e ambienti per realizzarlo.',
    createYourOwnSkill: 'Crea una skill' },
  settings: { ...enUS.settings, title: 'Impostazioni',
    description: 'Configura il tuo spazio di lavoro RigHaven.',
    sections: { ...enUS.settings.sections, models: 'Modelli', users: 'Utenti', account: 'Account', appearance: 'Aspetto e lingua', notification: 'Notifiche', about: 'Informazioni' },
    appearance: { ...enUS.settings.appearance, themeTitle: 'Aspetto', themeDescription: 'Scegli come visualizzare RigHaven.', system: 'Sistema', light: 'Chiaro', dark: 'Scuro', systemDescription: 'Segui le preferenze del dispositivo.', lightDescription: 'Interfaccia chiara.', darkDescription: 'Interfaccia scura.', languageTitle: 'Lingua', languageDescription: 'Scegli la lingua dello spazio di lavoro.' } },
  agents: { ...enUS.agents, title: 'Profili della squadra', description: 'Conserva istruzioni e selezioni di skill riutilizzabili. I ruoli del progetto vengono definiti dinamicamente per ogni obiettivo.', newAgent: 'Nuovo profilo', importAgent: 'Importa profilo' },
  login: { ...enUS.login, signInTitle: 'Accedi al tuo account', createAccountTitle: 'Crea un account', email: 'Email', password: 'Password', rememberMe: 'Resta connesso', pleaseWait: 'Attendi…', signIn: 'Accedi', createAccount: 'Crea account', createAdminAccount: 'Crea account amministratore', noAccountSignUp: 'Non hai un account? Registrati', haveAccountSignIn: 'Hai già un account? Accedi', backToHome: 'Torna alla home', retry: 'Riprova', networkError: 'Connessione non riuscita. Riprova.', serviceUnavailableTitle: 'Servizio non disponibile', serviceUnavailableDescription: 'Non è stato possibile verificare lo stato del servizio.', authFailed: 'Accesso non riuscito' },
};
