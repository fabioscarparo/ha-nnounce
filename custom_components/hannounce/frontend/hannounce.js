/*
 * HA-nnounce: card, card editor and sidebar panel.
 * Record your voice and play it on the speakers of Home Assistant: Google Home and Nest, Sonos, ESPHome and more.
 * Served by the integration itself: no dashboard resource to add, no build step.
 */

export const VERSION = "0.3.0";
const DOMAIN = "hannounce";
const CARD_TYPE = "hannounce-card";
const EDITOR_TYPE = "hannounce-card-editor";
const PANEL_TYPE = "hannounce-panel";
const UPLOAD_URL = "/api/hannounce/announce";
const CHIME_URL = "/api/hannounce/chime";
const DEFAULT_ICON = "mdi:bullhorn";
const DEFAULT_COLOR = "primary";
const HOLD_MS = 400;
const LONG_PRESS_MS = 550;
const MIN_SECONDS = 0.6;
const SUCCESS_MS = 5000;
const STORAGE_KEY = "hannounce";
const COMPACT_THRESHOLD = 6;
const CHIMES = ["none", "ding_dong", "soft", "three_tone"];
const ALL_CHIMES = [...CHIMES, "custom"];

/* Matches CHIME_EXPRESSIONS in audio.py so previews sound identical to playback. */
export const CHIME_SPECS = {
  ding_dong: {
    duration: 1.55,
    notes: [
      { freq: 659.25, start: 0, decay: 3.6, gain: 0.42 },
      { freq: 523.25, start: 0.45, decay: 2.8, gain: 0.42 },
    ],
  },
  soft: {
    duration: 1.1,
    notes: [
      { freq: 880.0, start: 0, decay: 4.5, gain: 0.3 },
      { freq: 1174.66, start: 0.16, decay: 3.8, gain: 0.26 },
    ],
  },
  three_tone: {
    duration: 1.6,
    notes: [
      { freq: 523.25, start: 0, decay: 4.0, gain: 0.34 },
      { freq: 659.25, start: 0.22, decay: 4.0, gain: 0.34 },
      { freq: 783.99, start: 0.44, decay: 3.0, gain: 0.36 },
    ],
  },
};

export const renderChimeSamples = (chime, sampleRate = 44100) => {
  const spec = CHIME_SPECS[chime];
  if (!spec) return null;
  const length = Math.ceil(spec.duration * sampleRate);
  const samples = new Float32Array(length);
  for (let i = 0; i < length; i++) {
    const tSec = i / sampleRate;
    let sum = 0;
    for (const note of spec.notes) {
      const dt = tSec - note.start;
      if (dt < 0) continue;
      const env = note.gain * Math.min(1, dt * 250) * Math.exp(-note.decay * dt);
      sum +=
        env *
        (Math.sin(2 * Math.PI * note.freq * dt) +
          0.28 * Math.sin(2 * Math.PI * note.freq * 2 * dt) +
          0.08 * Math.sin(2 * Math.PI * note.freq * 2.76 * dt));
    }
    samples[i] = Math.max(-1, Math.min(1, sum));
  }
  return samples;
};

/* One table for every string the card shows, English as fallback. */
export const STRINGS = {
  en: {
    title: "Announcement",
    panel_title: "Announcements",
    loading: "Loading…",
    no_selection: "No speaker chosen",
    n_speakers: "{n} speakers",
    all: "All",
    speakers: "Speakers",
    group: "Speaker group",
    unavailable: "Unavailable",
    hint_idle: "Hold to talk, or tap to start",
    hint_choose: "Choose at least one speaker",
    hint_preparing: "Opening the microphone…",
    hint_hold: "{time} · Release to send",
    hint_toggle: "{time} · Tap to send",
    hint_review: "{time} · Listen, then send or discard",
    hint_sending: "Sending…",
    sent: "Sent to {targets}",
    replayed: "Played again on {targets}",
    sent_intercom: "Sent to the intercom",
    talk: "Talk",
    stop_send: "Stop and send",
    play: "Listen",
    stop: "Stop",
    send: "Send",
    discard: "Discard",
    replay: "Replay last message",
    settings: "Message options",
    close: "Close",
    volume: "Message volume",
    volume_helper: "The message plays at this volume, then each speaker goes back to its own.",
    volume_keep: "Each speaker's own volume",
    chime: "Chime before the message",
    chime_preview: "Preview chime",
    chime_none: "None",
    chime_ding_dong: "Ding dong",
    chime_soft: "Soft",
    chime_three_tone: "3 tones",
    chime_custom: "Custom",
    mode_text: "Text mode",
    mode_voice: "Voice mode",
    tts_label: "Announcement message",
    tts_placeholder: "Type a message to announce…",
    quiet_hours: "Quiet hours",
    quiet_cap: "Max {volume}",
    quiet_skip_pill: "Quiet: {targets}",
    quiet_skipped: "Silenced by quiet hours",
    other_area: "Other",
    choose_speakers: "Choose speakers",
    filter_speakers: "Filter by name or area…",
    no_matches: "No matching speakers",
    deselect_all: "Clear",
    keep_volume: "Keep each speaker's volume",
    keep_volume_helper: "Off: the message plays at the chosen volume, then each speaker goes back to its own.",
    review: "Listen before sending",
    upload: "Send an audio file",
    intercom: "Intercom",
    intercom_helper: "Open an intercom and press Start talking to talk on that speaker.",
    intercom_labs: "Turn on Two-way audio in Settings > System > Labs to see the Start talking button.",
    open_intercom: "Open to talk",
    menu: "Menu",
    err_no_voice: "No voice heard. Try again closer to the microphone.",
    err_audio: "This audio can't be read. Try another file, or record again.",
    err_too_large: "The audio file is too large.",
    err_unavailable: "None of the chosen speakers is available right now.",
    err_too_short: "Too short. Hold the button while you talk.",
    err_mic_denied: "Microphone access is blocked. Allow it in the browser or app settings.",
    err_mic_missing: "No microphone found on this device.",
    err_insecure:
      "Browsers only open the microphone over HTTPS. Open Home Assistant over HTTPS, or send an audio file recorded on this device.",
    err_insecure_app: " The iOS app can also use the microphone over HTTP once the intercom is turned on in the integration options.",
    err_not_set_up: "HA-nnounce is not set up.",
    err_quiet_hours: "Quiet hours are active and skipped all selected speakers.",
    err_tts_unavailable: "No text-to-speech engine is configured in Home Assistant.",
    err_tts_failed: "Could not generate speech: {message}",
    err_no_speakers: "No speakers yet. Add the integration of your speakers (Google Cast, Sonos, ESPHome...), or choose them in the HA-nnounce options.",
    err_generic: "Could not send the message: {message}",
    err_app: "The app could not use the microphone: {message}",
    editor_title: "Title",
    editor_icon: "Icon",
    editor_color: "Color",
    editor_entities: "Speakers",
    helper_entities: "Empty shows every speaker of the integration.",
    editor_content: "Content",
    editor_speaker_style: "Speaker selector",
    helper_speaker_style: "Auto switches to a compact dialog when there are more than 6 speakers.",
    style_auto: "Automatic",
    style_chips: "Chips",
    style_compact: "Compact (dialog)",
    editor_show_volume: "Volume slider",
    editor_show_settings: "Options button",
    editor_review: "Listen before sending",
    helper_review: "Each person can still change it in the options.",
  },
  it: {
    title: "Annuncio",
    panel_title: "Annunci",
    loading: "Caricamento…",
    no_selection: "Nessun altoparlante scelto",
    n_speakers: "{n} altoparlanti",
    all: "Tutti",
    speakers: "Altoparlanti",
    group: "Gruppo di altoparlanti",
    unavailable: "Non disponibile",
    hint_idle: "Tieni premuto per parlare, oppure tocca per iniziare",
    hint_choose: "Scegli almeno un altoparlante",
    hint_preparing: "Apro il microfono…",
    hint_hold: "{time} · Rilascia per inviare",
    hint_toggle: "{time} · Tocca per inviare",
    hint_review: "{time} · Ascolta, poi invia o elimina",
    hint_sending: "Invio in corso…",
    sent: "Inviato a {targets}",
    replayed: "Ripetuto su {targets}",
    sent_intercom: "Inviato all'interfono",
    talk: "Parla",
    stop_send: "Ferma e invia",
    play: "Ascolta",
    stop: "Ferma",
    send: "Invia",
    discard: "Elimina",
    replay: "Ripeti l'ultimo messaggio",
    settings: "Opzioni del messaggio",
    close: "Chiudi",
    volume: "Volume del messaggio",
    volume_helper: "Il messaggio si sente a questo volume, poi ogni altoparlante torna al suo.",
    volume_keep: "Volume di ogni altoparlante",
    chime: "Suono prima del messaggio",
    chime_preview: "Ascolta il suono",
    chime_none: "Nessuno",
    chime_ding_dong: "Din don",
    chime_soft: "Leggero",
    chime_three_tone: "3 note",
    chime_custom: "Pers.",
    mode_text: "Modalità testo",
    mode_voice: "Modalità voce",
    tts_label: "Messaggio da annunciare",
    tts_placeholder: "Scrivi un messaggio da annunciare…",
    quiet_hours: "Orari di silenzio",
    quiet_cap: "Max {volume}",
    quiet_skip_pill: "Silenzio: {targets}",
    quiet_skipped: "Escluso dagli orari di silenzio",
    other_area: "Altri",
    choose_speakers: "Scegli altoparlanti",
    filter_speakers: "Filtra per nome o area…",
    no_matches: "Nessun altoparlante trovato",
    deselect_all: "Deseleziona",
    keep_volume: "Mantieni il volume di ogni altoparlante",
    keep_volume_helper: "Se disattivato, il messaggio usa il volume scelto e poi ogni altoparlante torna al suo.",
    review: "Ascolta prima di inviare",
    upload: "Invia un file audio",
    intercom: "Interfono",
    intercom_helper: "Apri un interfono e premi Inizia a parlare per parlare su quell'altoparlante.",
    intercom_labs: "Attiva Two-way audio in Impostazioni > Sistema > Laboratori per vedere il pulsante Inizia a parlare.",
    open_intercom: "Apri per parlare",
    menu: "Menu",
    err_no_voice: "Non ho sentito la voce. Riprova più vicino al microfono.",
    err_audio: "Non riesco a leggere questo audio. Prova con un altro file, oppure registra di nuovo.",
    err_too_large: "Il file audio è troppo grande.",
    err_unavailable: "Nessuno degli altoparlanti scelti è disponibile in questo momento.",
    err_too_short: "Troppo breve. Tieni premuto il pulsante mentre parli.",
    err_mic_denied: "L'accesso al microfono è bloccato. Consentilo nelle impostazioni del browser o dell'app.",
    err_mic_missing: "Nessun microfono trovato su questo dispositivo.",
    err_insecure:
      "I browser aprono il microfono solo in HTTPS. Apri Home Assistant in HTTPS, oppure invia un file audio registrato con il dispositivo.",
    err_insecure_app: " Nell'app iOS il microfono funziona anche in HTTP, attivando l'interfono nelle opzioni dell'integrazione.",
    err_not_set_up: "HA-nnounce non è configurato.",
    err_quiet_hours: "Gli orari di silenzio sono attivi e hanno escluso gli altoparlanti scelti.",
    err_tts_unavailable: "Nessun motore text-to-speech è configurato in Home Assistant.",
    err_tts_failed: "Impossibile generare la voce: {message}",
    err_no_speakers:
      "Ancora nessun altoparlante. Aggiungi l'integrazione dei tuoi altoparlanti (Google Cast, Sonos, ESPHome...), oppure sceglili nelle opzioni di HA-nnounce.",
    err_generic: "Invio non riuscito: {message}",
    err_app: "L'app non è riuscita a usare il microfono: {message}",
    editor_title: "Titolo",
    editor_icon: "Icona",
    editor_color: "Colore",
    editor_entities: "Altoparlanti",
    helper_entities: "Se vuoto, mostra tutti gli altoparlanti dell'integrazione.",
    editor_content: "Contenuto",
    editor_speaker_style: "Selettore altoparlanti",
    helper_speaker_style: "Automatico passa al selettore compatto con più di 6 altoparlanti.",
    style_auto: "Automatico",
    style_chips: "Chip",
    style_compact: "Compatto (dialog)",
    editor_show_volume: "Cursore del volume",
    editor_show_settings: "Pulsante delle opzioni",
    editor_review: "Ascolta prima di inviare",
    helper_review: "Ognuno può comunque cambiarlo nelle opzioni.",
  },
  de: {
    title: "Durchsage",
    panel_title: "Durchsagen",
    loading: "Laden…",
    no_selection: "Kein Lautsprecher gewählt",
    n_speakers: "{n} Lautsprecher",
    all: "Alle",
    speakers: "Lautsprecher",
    group: "Lautsprechergruppe",
    unavailable: "Nicht verfügbar",
    hint_idle: "Halten zum Sprechen oder tippen zum Starten",
    hint_choose: "Wähle mindestens einen Lautsprecher",
    hint_preparing: "Mikrofon wird geöffnet…",
    hint_hold: "{time} · Loslassen zum Senden",
    hint_toggle: "{time} · Tippen zum Senden",
    hint_review: "{time} · Anhören, dann senden oder verwerfen",
    hint_sending: "Wird gesendet…",
    sent: "Gesendet an {targets}",
    replayed: "Erneut abgespielt auf {targets}",
    sent_intercom: "An Gegensprechanlage gesendet",
    talk: "Sprechen",
    stop_send: "Stoppen und senden",
    play: "Anhören",
    stop: "Stopp",
    send: "Senden",
    discard: "Verwerfen",
    replay: "Letzte Durchsage wiederholen",
    settings: "Durchsage-Optionen",
    close: "Schließen",
    volume: "Lautstärke der Durchsage",
    volume_helper: "Die Durchsage wird in dieser Lautstärke abgespielt, danach kehrt jeder Lautsprecher zu seiner zurück.",
    volume_keep: "Eigene Lautstärke jedes Lautsprechers",
    chime: "Signalton vor der Durchsage",
    chime_preview: "Signalton anhören",
    chime_none: "Keiner",
    chime_ding_dong: "Ding-Dong",
    chime_soft: "Sanft",
    chime_three_tone: "3 Töne",
    chime_custom: "Eigener",
    mode_text: "Textmodus",
    mode_voice: "Sprachmodus",
    tts_label: "Durchsagetext",
    tts_placeholder: "Nachricht zum Vorlesen eingeben…",
    quiet_hours: "Ruhezeit",
    quiet_cap: "Max. {volume}",
    quiet_skip_pill: "Ruhe: {targets}",
    quiet_skipped: "Durch Ruhezeit stummgeschaltet",
    other_area: "Sonstige",
    choose_speakers: "Lautsprecher wählen",
    filter_speakers: "Nach Name oder Bereich filtern…",
    no_matches: "Keine passenden Lautsprecher",
    deselect_all: "Aufheben",
    keep_volume: "Lautstärke jedes Lautsprechers beibehalten",
    keep_volume_helper: "Aus: Die Durchsage nutzt die gewählte Lautstärke, danach kehrt jeder Lautsprecher zu seiner zurück.",
    review: "Vor dem Senden anhören",
    upload: "Audiodatei senden",
    intercom: "Gegensprechanlage",
    intercom_helper: "Öffne eine Gegensprechanlage und tippe auf Sprechen starten, um über diesen Lautsprecher zu sprechen.",
    intercom_labs: "Aktiviere Zwei-Wege-Audio unter Einstellungen > System > Labs, um die Sprechtaste zu sehen.",
    open_intercom: "Zum Sprechen öffnen",
    menu: "Menü",
    err_no_voice: "Keine Stimme erkannt. Versuche es näher am Mikrofon.",
    err_audio: "Dieses Audio kann nicht gelesen werden. Versuche eine andere Datei oder nimm erneut auf.",
    err_too_large: "Die Audiodatei ist zu groß.",
    err_unavailable: "Keiner der gewählten Lautsprecher ist derzeit verfügbar.",
    err_too_short: "Zu kurz. Halte die Taste gedrückt, während du sprichst.",
    err_mic_denied: "Der Mikrofonzugriff ist blockiert. Erlaube ihn in den Browser- oder App-Einstellungen.",
    err_mic_missing: "Auf diesem Gerät wurde kein Mikrofon gefunden.",
    err_insecure:
      "Browser öffnen das Mikrofon nur über HTTPS. Öffne Home Assistant über HTTPS oder sende eine auf diesem Gerät aufgenommene Audiodatei.",
    err_insecure_app: " Die iOS-App kann das Mikrofon auch über HTTP nutzen, wenn die Gegensprechanlage in den Integrationsoptionen aktiviert ist.",
    err_not_set_up: "HA-nnounce ist nicht eingerichtet.",
    err_quiet_hours: "Die Ruhezeit ist aktiv und hat alle gewählten Lautsprecher übersprungen.",
    err_tts_unavailable: "In Home Assistant ist kein Text-zu-Sprache-Dienst konfiguriert.",
    err_tts_failed: "Sprachausgabe fehlgeschlagen: {message}",
    err_no_speakers: "Noch keine Lautsprecher. Füge die Integration deiner Lautsprecher hinzu (Google Cast, Sonos, ESPHome...) oder wähle sie in den HA-nnounce-Optionen.",
    err_generic: "Durchsage konnte nicht gesendet werden: {message}",
    err_app: "Die App konnte das Mikrofon nicht verwenden: {message}",
    editor_title: "Titel",
    editor_icon: "Symbol",
    editor_color: "Farbe",
    editor_entities: "Lautsprecher",
    helper_entities: "Leer zeigt alle Lautsprecher der Integration.",
    editor_content: "Inhalt",
    editor_speaker_style: "Lautsprecherauswahl",
    helper_speaker_style: "Automatisch wechselt bei mehr als 6 Lautsprechern in einen kompakten Dialog.",
    style_auto: "Automatisch",
    style_chips: "Chips",
    style_compact: "Kompakt (Dialog)",
    editor_show_volume: "Lautstärkeregler",
    editor_show_settings: "Optionen-Schaltfläche",
    editor_review: "Vor dem Senden anhören",
    helper_review: "Jede Person kann dies weiterhin in den Optionen ändern.",
  },
  fr: {
    title: "Annonce",
    panel_title: "Annonces",
    loading: "Chargement…",
    no_selection: "Aucun haut-parleur choisi",
    n_speakers: "{n} haut-parleurs",
    all: "Tous",
    speakers: "Haut-parleurs",
    group: "Groupe de haut-parleurs",
    unavailable: "Indisponible",
    hint_idle: "Maintenez pour parler ou appuyez pour démarrer",
    hint_choose: "Choisissez au moins un haut-parleur",
    hint_preparing: "Ouverture du microphone…",
    hint_hold: "{time} · Relâchez pour envoyer",
    hint_toggle: "{time} · Appuyez pour envoyer",
    hint_review: "{time} · Écoutez, puis envoyez ou supprimez",
    hint_sending: "Envoi en cours…",
    sent: "Envoyé à {targets}",
    replayed: "Rediffusé sur {targets}",
    sent_intercom: "Envoyé à l'interphone",
    talk: "Parler",
    stop_send: "Arrêter et envoyer",
    play: "Écouter",
    stop: "Arrêter",
    send: "Envoyer",
    discard: "Supprimer",
    replay: "Répéter le dernier message",
    settings: "Options du message",
    close: "Fermer",
    volume: "Volume du message",
    volume_helper: "Le message est diffusé à ce volume, puis chaque haut-parleur revient au sien.",
    volume_keep: "Volume de chaque haut-parleur",
    chime: "Carillon avant le message",
    chime_preview: "Écouter le carillon",
    chime_none: "Aucun",
    chime_ding_dong: "Ding dong",
    chime_soft: "Doux",
    chime_three_tone: "3 notes",
    chime_custom: "Perso",
    mode_text: "Mode texte",
    mode_voice: "Mode voix",
    tts_label: "Message d'annonce",
    tts_placeholder: "Saisissez un message à annoncer…",
    quiet_hours: "Heures silencieuses",
    quiet_cap: "Max {volume}",
    quiet_skip_pill: "Silence : {targets}",
    quiet_skipped: "Exclu par les heures silencieuses",
    other_area: "Autres",
    choose_speakers: "Choisir les haut-parleurs",
    filter_speakers: "Filtrer par nom ou pièce…",
    no_matches: "Aucun haut-parleur trouvé",
    deselect_all: "Effacer",
    keep_volume: "Conserver le volume de chaque haut-parleur",
    keep_volume_helper: "Désactivé : le message utilise le volume choisi, puis chaque haut-parleur revient au sien.",
    review: "Écouter avant d'envoyer",
    upload: "Envoyer un fichier audio",
    intercom: "Interphone",
    intercom_helper: "Ouvrez un interphone et appuyez sur Commencer à parler pour parler sur ce haut-parleur.",
    intercom_labs: "Activez l'audio bidirectionnel dans Paramètres > Système > Labs pour voir le bouton Commencer à parler.",
    open_intercom: "Ouvrir pour parler",
    menu: "Menu",
    err_no_voice: "Aucune voix détectée. Réessayez plus près du microphone.",
    err_audio: "Impossible de lire cet audio. Essayez un autre fichier ou enregistrez à nouveau.",
    err_too_large: "Le fichier audio est trop volumineux.",
    err_unavailable: "Aucun des haut-parleurs choisis n'est disponible pour le moment.",
    err_too_short: "Trop court. Maintenez le bouton pendant que vous parlez.",
    err_mic_denied: "L'accès au microphone est bloqué. Autorisez-le dans les réglages du navigateur ou de l'application.",
    err_mic_missing: "Aucun microphone trouvé sur cet appareil.",
    err_insecure:
      "Les navigateurs n'ouvrent le microphone qu'en HTTPS. Ouvrez Home Assistant en HTTPS ou envoyez un fichier audio enregistré sur cet appareil.",
    err_insecure_app: " L'application iOS peut aussi utiliser le microphone en HTTP lorsque l'interphone est activé dans les options de l'intégration.",
    err_not_set_up: "HA-nnounce n'est pas configuré.",
    err_quiet_hours: "Les heures silencieuses sont actives et ont exclu les haut-parleurs choisis.",
    err_tts_unavailable: "Aucun moteur de synthèse vocale n'est configuré dans Home Assistant.",
    err_tts_failed: "Impossible de générer la voix : {message}",
    err_no_speakers: "Aucun haut-parleur pour le moment. Ajoutez l'intégration de vos haut-parleurs (Google Cast, Sonos, ESPHome...) ou choisissez-les dans les options de HA-nnounce.",
    err_generic: "Impossible d'envoyer le message : {message}",
    err_app: "L'application n'a pas pu utiliser le microphone : {message}",
    editor_title: "Titre",
    editor_icon: "Icône",
    editor_color: "Couleur",
    editor_entities: "Haut-parleurs",
    helper_entities: "Vide affiche tous les haut-parleurs de l'intégration.",
    editor_content: "Contenu",
    editor_speaker_style: "Sélecteur de haut-parleurs",
    helper_speaker_style: "Automatique passe au sélecteur compact au-delà de 6 haut-parleurs.",
    style_auto: "Automatique",
    style_chips: "Puces",
    style_compact: "Compact (fenêtre)",
    editor_show_volume: "Curseur de volume",
    editor_show_settings: "Bouton des options",
    editor_review: "Écouter avant d'envoyer",
    helper_review: "Chacun peut toujours modifier ce réglage dans les options.",
  },
  es: {
    title: "Anuncio",
    panel_title: "Anuncios",
    loading: "Cargando…",
    no_selection: "Ningún altavoz elegido",
    n_speakers: "{n} altavoces",
    all: "Todos",
    speakers: "Altavoces",
    group: "Grupo de altavoces",
    unavailable: "No disponible",
    hint_idle: "Mantén pulsado para hablar o toca para empezar",
    hint_choose: "Elige al menos un altavoz",
    hint_preparing: "Abriendo el micrófono…",
    hint_hold: "{time} · Suelta para enviar",
    hint_toggle: "{time} · Toca para enviar",
    hint_review: "{time} · Escucha, luego envía o descarta",
    hint_sending: "Enviando…",
    sent: "Enviado a {targets}",
    replayed: "Repetido en {targets}",
    sent_intercom: "Enviado al intercomunicador",
    talk: "Hablar",
    stop_send: "Detener y enviar",
    play: "Escuchar",
    stop: "Detener",
    send: "Enviar",
    discard: "Descartar",
    replay: "Repetir último mensaje",
    settings: "Opciones del mensaje",
    close: "Cerrar",
    volume: "Volumen del mensaje",
    volume_helper: "El mensaje se reproduce a este volumen y luego cada altavoz vuelve al suyo.",
    volume_keep: "Volumen de cada altavoz",
    chime: "Sonido antes del mensaje",
    chime_preview: "Escuchar sonido",
    chime_none: "Ninguno",
    chime_ding_dong: "Ding dong",
    chime_soft: "Suave",
    chime_three_tone: "3 tonos",
    chime_custom: "Pers.",
    mode_text: "Modo texto",
    mode_voice: "Modo voz",
    tts_label: "Mensaje del anuncio",
    tts_placeholder: "Escribe un mensaje para anunciar…",
    quiet_hours: "Horario de silencio",
    quiet_cap: "Máx. {volume}",
    quiet_skip_pill: "Silencio: {targets}",
    quiet_skipped: "Omitido por horario de silencio",
    other_area: "Otros",
    choose_speakers: "Elegir altavoces",
    filter_speakers: "Filtrar por nombre o área…",
    no_matches: "No se encontraron altavoces",
    deselect_all: "Quitar",
    keep_volume: "Mantener el volumen de cada altavoz",
    keep_volume_helper: "Desactivado: el mensaje usa el volumen elegido y luego cada altavoz vuelve al suyo.",
    review: "Escuchar antes de enviar",
    upload: "Enviar un archivo de audio",
    intercom: "Intercomunicador",
    intercom_helper: "Abre un intercomunicador y pulsa Empezar a hablar para hablar en ese altavoz.",
    intercom_labs: "Activa el audio bidireccional en Ajustes > Sistema > Labs para ver el botón Empezar a hablar.",
    open_intercom: "Abrir para hablar",
    menu: "Menú",
    err_no_voice: "No se escuchó ninguna voz. Inténtalo más cerca del micrófono.",
    err_audio: "No se puede leer este audio. Prueba con otro archivo o graba de nuevo.",
    err_too_large: "El archivo de audio es demasiado grande.",
    err_unavailable: "Ninguno de los altavoces elegidos está disponible ahora mismo.",
    err_too_short: "Demasiado corto. Mantén pulsado el botón mientras hablas.",
    err_mic_denied: "El acceso al micrófono está bloqueado. Permítelo en los ajustes del navegador o de la app.",
    err_mic_missing: "No se encontró ningún micrófono en este dispositivo.",
    err_insecure:
      "Los navegadores solo abren el micrófono por HTTPS. Abre Home Assistant por HTTPS o envía un archivo de audio grabado en este dispositivo.",
    err_insecure_app: " La app de iOS también puede usar el micrófono por HTTP si el intercomunicador está activado en las opciones de la integración.",
    err_not_set_up: "HA-nnounce no está configurado.",
    err_quiet_hours: "El horario de silencio está activo y ha omitido los altavoces elegidos.",
    err_tts_unavailable: "No hay ningún motor de texto a voz configurado en Home Assistant.",
    err_tts_failed: "No se pudo generar la voz: {message}",
    err_no_speakers: "Aún no hay altavoces. Añade la integración de tus altavoces (Google Cast, Sonos, ESPHome...) o elígelos en las opciones de HA-nnounce.",
    err_generic: "No se pudo enviar el mensaje: {message}",
    err_app: "La app no pudo usar el micrófono: {message}",
    editor_title: "Título",
    editor_icon: "Icono",
    editor_color: "Color",
    editor_entities: "Altavoces",
    helper_entities: "Vacío muestra todos los altavoces de la integración.",
    editor_content: "Contenido",
    editor_speaker_style: "Selector de altavoces",
    helper_speaker_style: "Automático cambia al selector compacto con más de 6 altavoces.",
    style_auto: "Automático",
    style_chips: "Chips",
    style_compact: "Compacto (diálogo)",
    editor_show_volume: "Control de volumen",
    editor_show_settings: "Botón de opciones",
    editor_review: "Escuchar antes de enviar",
    helper_review: "Cada persona puede cambiarlo igualmente en las opciones.",
  },
  nl: {
    title: "Omroep",
    panel_title: "Omroepen",
    loading: "Laden…",
    no_selection: "Geen luidspreker gekozen",
    n_speakers: "{n} luidsprekers",
    all: "Alle",
    speakers: "Luidsprekers",
    group: "Luidsprekergroep",
    unavailable: "Niet beschikbaar",
    hint_idle: "Houd ingedrukt om te spreken of tik om te starten",
    hint_choose: "Kies minstens een luidspreker",
    hint_preparing: "Microfoon openen…",
    hint_hold: "{time} · Laat los om te verzenden",
    hint_toggle: "{time} · Tik om te verzenden",
    hint_review: "{time} · Luister, verzend of verwijder",
    hint_sending: "Verzenden…",
    sent: "Verzonden naar {targets}",
    replayed: "Opnieuw afgespeeld op {targets}",
    sent_intercom: "Verzonden naar de intercom",
    talk: "Spreek",
    stop_send: "Stoppen en verzenden",
    play: "Luister",
    stop: "Stop",
    send: "Verzend",
    discard: "Verwijder",
    replay: "Laatste bericht herhalen",
    settings: "Berichtopties",
    close: "Sluiten",
    volume: "Berichtvolume",
    volume_helper: "Het bericht speelt op dit volume en daarna keert elke luidspreker terug naar zijn eigen volume.",
    volume_keep: "Eigen volume per luidspreker",
    chime: "Geluid voor het bericht",
    chime_preview: "Geluid beluisteren",
    chime_none: "Geen",
    chime_ding_dong: "Ding dong",
    chime_soft: "Zacht",
    chime_three_tone: "3 tonen",
    chime_custom: "Eigen",
    mode_text: "Tekstmodus",
    mode_voice: "Spraakmodus",
    tts_label: "Omroepbericht",
    tts_placeholder: "Typ een bericht om om te roepen…",
    quiet_hours: "Stille uren",
    quiet_cap: "Max. {volume}",
    quiet_skip_pill: "Stil: {targets}",
    quiet_skipped: "Overgeslagen door stille uren",
    other_area: "Overige",
    choose_speakers: "Kies luidsprekers",
    filter_speakers: "Filter op naam of ruimte…",
    no_matches: "Geen luidsprekers gevonden",
    deselect_all: "Wissen",
    keep_volume: "Eigen volume per luidspreker behouden",
    keep_volume_helper: "Uit: het bericht gebruikt het gekozen volume en elke luidspreker keert daarna terug naar het zijne.",
    review: "Luisteren voor verzenden",
    upload: "Audiobestand verzenden",
    intercom: "Intercom",
    intercom_helper: "Open een intercom en druk op Begin met spreken om via die luidspreker te spreken.",
    intercom_labs: "Schakel tweerichtingsaudio in via Instellingen > Systeem > Labs om de spreekknop te zien.",
    open_intercom: "Openen om te spreken",
    menu: "Menu",
    err_no_voice: "Geen stem gehoord. Probeer het dichter bij de microfoon.",
    err_audio: "Deze audio kan niet worden gelezen. Probeer een ander bestand of neem opnieuw op.",
    err_too_large: "Het audiobestand is te groot.",
    err_unavailable: "Geen van de gekozen luidsprekers is momenteel beschikbaar.",
    err_too_short: "Te kort. Houd de knop ingedrukt terwijl je spreekt.",
    err_mic_denied: "Toegang tot de microfoon is geblokkeerd. Sta dit toe in de browser- of app-instellingen.",
    err_mic_missing: "Geen microfoon gevonden op dit apparaat.",
    err_insecure:
      "Browsers openen de microfoon alleen via HTTPS. Open Home Assistant via HTTPS of verzend een audiobestand dat op dit apparaat is opgenomen.",
    err_insecure_app: " De iOS-app kan de microfoon ook via HTTP gebruiken zodra de intercom is ingeschakeld in de integratie-opties.",
    err_not_set_up: "HA-nnounce is niet ingesteld.",
    err_quiet_hours: "Stille uren zijn actief en hebben de gekozen luidsprekers overgeslagen.",
    err_tts_unavailable: "Er is geen tekst-naar-spraak-engine geconfigureerd in Home Assistant.",
    err_tts_failed: "Kon spraak niet genereren: {message}",
    err_no_speakers: "Nog geen luidsprekers. Voeg de integratie van je luidsprekers toe (Google Cast, Sonos, ESPHome...) of kies ze in de opties van HA-nnounce.",
    err_generic: "Kon het bericht niet verzenden: {message}",
    err_app: "De app kon de microfoon niet gebruiken: {message}",
    editor_title: "Titel",
    editor_icon: "Pictogram",
    editor_color: "Kleur",
    editor_entities: "Luidsprekers",
    helper_entities: "Leeg toont alle luidsprekers van de integratie.",
    editor_content: "Inhoud",
    editor_speaker_style: "Luidsprekerkiezer",
    helper_speaker_style: "Automatisch schakelt bij meer dan 6 luidsprekers naar een compact venster.",
    style_auto: "Automatisch",
    style_chips: "Chips",
    style_compact: "Compact (venster)",
    editor_show_volume: "Volumeregelaar",
    editor_show_settings: "Optiesknop",
    editor_review: "Luisteren voor verzenden",
    helper_review: "Iedereen kan dit nog steeds wijzigen in de opties.",
  },
  ro: {
    title: "Anunț",
    panel_title: "Anunțuri",
    loading: "Se încarcă…",
    no_selection: "Niciun difuzor ales",
    n_speakers: "{n} difuzoare",
    all: "Toate",
    speakers: "Difuzoare",
    group: "Grup de difuzoare",
    unavailable: "Indisponibil",
    hint_idle: "Ține apăsat pentru a vorbi sau atinge pentru a începe",
    hint_choose: "Alege cel puțin un difuzor",
    hint_preparing: "Se deschide microfonul…",
    hint_hold: "{time} · Eliberează pentru a trimite",
    hint_toggle: "{time} · Atinge pentru a trimite",
    hint_review: "{time} · Ascultă, apoi trimite sau renunță",
    hint_sending: "Se trimite…",
    sent: "Trimis către {targets}",
    replayed: "Redat din nou pe {targets}",
    sent_intercom: "Trimis către interfon",
    talk: "Vorbește",
    stop_send: "Oprește și trimite",
    play: "Ascultă",
    stop: "Oprește",
    send: "Trimite",
    discard: "Renunță",
    replay: "Redă din nou ultimul mesaj",
    settings: "Opțiuni mesaj",
    close: "Închide",
    volume: "Volumul mesajului",
    volume_helper: "Mesajul se redă la acest volum, apoi fiecare difuzor revine la volumul său.",
    volume_keep: "Volumul propriu al fiecărui difuzor",
    chime: "Sunet înainte de mesaj",
    chime_preview: "Previzualizează sunetul",
    chime_none: "Niciunul",
    chime_ding_dong: "Ding dong",
    chime_soft: "Discret",
    chime_three_tone: "3 tonuri",
    chime_custom: "Personalizat",
    mode_text: "Mod text",
    mode_voice: "Mod voce",
    tts_label: "Mesajul anunțului",
    tts_placeholder: "Scrie un mesaj de anunțat…",
    quiet_hours: "Ore de liniște",
    quiet_cap: "Max. {volume}",
    quiet_skip_pill: "Liniște: {targets}",
    quiet_skipped: "Redus la tăcere de orele de liniște",
    other_area: "Altele",
    choose_speakers: "Alege difuzoare",
    filter_speakers: "Filtrează după nume sau zonă…",
    no_matches: "Niciun difuzor potrivit",
    deselect_all: "Șterge",
    keep_volume: "Păstrează volumul fiecărui difuzor",
    keep_volume_helper: "Dezactivat: mesajul se redă la volumul ales, apoi fiecare difuzor revine la volumul său.",
    review: "Ascultă înainte de a trimite",
    upload: "Trimite un fișier audio",
    intercom: "Interfon",
    intercom_helper: "Deschide un interfon și apasă Începe să vorbești pentru a vorbi pe acel difuzor.",
    intercom_labs: "Activează Audio bidirecțional în Setări > Sistem > Labs pentru a vedea butonul Începe să vorbești.",
    open_intercom: "Deschide pentru a vorbi",
    menu: "Meniu",
    err_no_voice: "Nu s-a auzit nicio voce. Încearcă din nou mai aproape de microfon.",
    err_audio: "Acest audio nu poate fi citit. Încearcă alt fișier sau înregistrează din nou.",
    err_too_large: "Fișierul audio este prea mare.",
    err_unavailable: "Niciunul dintre difuzoarele alese nu este disponibil acum.",
    err_too_short: "Prea scurt. Ține apăsat butonul cât timp vorbești.",
    err_mic_denied: "Accesul la microfon este blocat. Permite-l din setările browserului sau ale aplicației.",
    err_mic_missing: "Nu s-a găsit niciun microfon pe acest dispozitiv.",
    err_insecure:
      "Browserele deschid microfonul doar prin HTTPS. Deschide Home Assistant prin HTTPS sau trimite un fișier audio înregistrat pe acest dispozitiv.",
    err_insecure_app: " Aplicația iOS poate folosi microfonul și prin HTTP după ce interfonul este activat în opțiunile integrării.",
    err_not_set_up: "HA-nnounce nu este configurat.",
    err_quiet_hours: "Orele de liniște sunt active și au omis toate difuzoarele selectate.",
    err_tts_unavailable: "Nu este configurat niciun motor de sinteză vocală în Home Assistant.",
    err_tts_failed: "Nu s-a putut genera vocea: {message}",
    err_no_speakers: "Încă nu există difuzoare. Adaugă integrarea difuzoarelor tale (Google Cast, Sonos, ESPHome...) sau alege-le în opțiunile HA-nnounce.",
    err_generic: "Nu s-a putut trimite mesajul: {message}",
    err_app: "Aplicația nu a putut folosi microfonul: {message}",
    editor_title: "Titlu",
    editor_icon: "Pictogramă",
    editor_color: "Culoare",
    editor_entities: "Difuzoare",
    helper_entities: "Gol afișează toate difuzoarele integrării.",
    editor_content: "Conținut",
    editor_speaker_style: "Selector de difuzoare",
    helper_speaker_style: "Automat trece la o fereastră compactă când există mai mult de 6 difuzoare.",
    style_auto: "Automat",
    style_chips: "Etichete",
    style_compact: "Compact (fereastră)",
    editor_show_volume: "Glisor de volum",
    editor_show_settings: "Buton de opțiuni",
    editor_review: "Ascultă înainte de a trimite",
    helper_review: "Fiecare persoană îl poate schimba în continuare din opțiuni.",
  },
};

/* Pure helpers, exported for the unit tests. */

export const languageOf = (hass) => {
  const lang = hass?.locale?.language || hass?.language || "en";
  if (STRINGS[lang]) return lang;
  return STRINGS[lang.split("-")[0]] ? lang.split("-")[0] : "en";
};

export const t = (hass, key, vars) => {
  let text = STRINGS[languageOf(hass)][key] ?? STRINGS.en[key] ?? key;
  for (const [name, value] of Object.entries(vars || {})) text = text.replaceAll(`{${name}}`, value);
  return text;
};

export const numberLocale = (hass) => {
  switch (hass?.locale?.number_format) {
    case "comma_decimal":
      return "en-US";
    case "decimal_comma":
      return "de";
    case "space_comma":
      return "fr";
    case "quote_decimal":
      return "de-CH";
    case "system":
      return undefined;
    default:
      return hass?.locale?.language || hass?.language;
  }
};

export const formatPercent = (hass, value) =>
  new Intl.NumberFormat(numberLocale(hass), {
    style: "percent",
    maximumFractionDigits: 0,
    useGrouping: hass?.locale?.number_format !== "none",
  }).format(value / 100);

export const formatClock = (hass, seconds) => {
  const total = Math.max(0, Math.floor(seconds));
  const locale = numberLocale(hass);
  const minutes = new Intl.NumberFormat(locale, { useGrouping: false }).format(Math.floor(total / 60));
  const rest = new Intl.NumberFormat(locale, { minimumIntegerDigits: 2, useGrouping: false }).format(total % 60);
  return `${minutes}:${rest}`;
};

export const formatTargets = (hass, names) => {
  if (!names.length) return "";
  if (names.length > 3) return t(hass, "n_speakers", { n: names.length });
  try {
    return new Intl.ListFormat(languageOf(hass), { style: "long", type: "conjunction" }).format(names);
  } catch (_err) {
    return names.join(", ");
  }
};

const HA_COLORS = new Set([
  "primary", "accent", "red", "pink", "purple", "deep-purple", "indigo", "blue", "light-blue", "cyan", "teal",
  "green", "light-green", "lime", "yellow", "amber", "orange", "deep-orange", "brown", "light-grey", "grey",
  "dark-grey", "blue-grey", "black", "white", "disabled",
]);

export const colorVar = (color) => {
  const name = color || DEFAULT_COLOR;
  if (HA_COLORS.has(name)) return `var(--${name}-color)`;
  // A CSS color written in the YAML (#hex, rgb()), never anything that could break out of the value
  return /^(#[0-9a-f]{3,8}|(rgb|rgba|hsl|hsla)\([0-9.,%\s]+\))$/i.test(name) ? name : `var(--${DEFAULT_COLOR}-color)`;
};

export const escapeHtml = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );

export const pickMimeType = (recorder = globalThis.MediaRecorder) => {
  if (!recorder?.isTypeSupported) return "";
  return (
    ["audio/webm;codecs=opus", "audio/ogg;codecs=opus", "audio/mp4", "audio/webm"].find((type) =>
      recorder.isTypeSupported(type)
    ) || ""
  );
};

export const fileExtension = (type) => {
  if (type.includes("mp4") || type.includes("aac")) return "m4a";
  if (type.includes("ogg")) return "ogg";
  if (type.includes("webm")) return "webm";
  if (type.includes("mpeg")) return "mp3";
  if (type.includes("wav")) return "wav";
  return "audio";
};

/* Keep the YAML short: drop defaults and empty values. */
export const CARD_DEFAULTS = {
  icon: DEFAULT_ICON,
  color: DEFAULT_COLOR,
  speaker_style: "auto",
  show_volume: true,
  show_settings: true,
  review: false,
};

export const formatSpeakerSummary = (hass, names) => {
  if (!names?.length) return t(hass, "choose_speakers");
  if (names.length <= 2) return names.join(", ");
  return `${names[0]}, ${names[1]} (+${names.length - 2})`;
};

export const isQuietActive = (hass, quiet, now = new Date()) => {
  if (!quiet?.enabled) return false;
  if (quiet.entity_id && hass?.states?.[quiet.entity_id]?.state === "on") return true;
  const start = quiet.start?.slice(0, 5);
  const end = quiet.end?.slice(0, 5);
  if (start && end && start !== end) {
    let hhmm;
    try {
      const tz = hass?.config?.time_zone;
      const parts = new Intl.DateTimeFormat("en-GB", {
        hour: "2-digit",
        minute: "2-digit",
        hourCycle: "h23",
        ...(tz ? { timeZone: tz } : {}),
      }).formatToParts(now);
      const h = parts.find((p) => p.type === "hour")?.value;
      const m = parts.find((p) => p.type === "minute")?.value;
      if (h && m) hhmm = `${h}:${m}`;
    } catch (_err) {
      // Fall back to local wall clock
    }
    if (!hhmm) {
      hhmm = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
    }
    return start < end ? hhmm >= start && hhmm < end : hhmm >= start || hhmm < end;
  }
  return Boolean(quiet.active);
};

export const groupSpeakersByArea = (speakers) => {
  const byKey = new Map();
  const ungrouped = [];
  for (const speaker of speakers || []) {
    const name = speaker.area;
    const key = speaker.area_id || name;
    if (!key || !name) {
      ungrouped.push(speaker);
      continue;
    }
    let entry = byKey.get(key);
    if (!entry) {
      entry = { key, name, icon: speaker.area_icon || "mdi:floor-plan", speakers: [] };
      byKey.set(key, entry);
    }
    entry.speakers.push(speaker);
  }
  return { areas: [...byKey.values()], ungrouped };
};

export const quickAreas = (speakers) => {
  const total = (speakers || []).length;
  return groupSpeakersByArea(speakers).areas.filter(
    (area) => area.speakers.length >= 2 && area.speakers.length < total
  );
};

export const cleanConfig = (config) => {
  const clean = { ...config };
  for (const [key, value] of Object.entries(CARD_DEFAULTS)) if (clean[key] === value) delete clean[key];
  for (const key of Object.keys(clean)) {
    const value = clean[key];
    if (value === "" || value === undefined || value === null || (Array.isArray(value) && !value.length)) delete clean[key];
  }
  return clean;
};

const readStore = () => {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch (_err) {
    return {};
  }
};

const writeStore = (patch) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ ...readStore(), ...patch }));
  } catch (_err) {
    // Private mode or blocked storage: preferences are only a convenience
  }
};

class AnnounceError extends Error {
  constructor(code, message) {
    super(message || code);
    this.code = code;
  }
}

/* Styles: Home Assistant tokens only; raw values appear only as fallbacks. */
const STYLES = `
  :host {
    display: block;
    --tile-color: var(--primary-color, #009ac7);
    --gha-recording: var(--red-color, #f44336);
    --gha-radius: var(--ha-card-features-border-radius, var(--feature-border-radius, var(--ha-border-radius-lg, 12px)));
  }
  [hidden] { display: none !important; }
  .visually-hidden {
    position: absolute; clip-path: inset(50%); overflow: hidden;
    width: 1px; height: 1px; margin: -1px; padding: 0; border: 0; white-space: nowrap;
  }
  ha-card { height: 100%; overflow: hidden; }
  button { font: inherit; color: inherit; background: none; border: none; margin: 0; padding: 0; cursor: pointer; -webkit-tap-highlight-color: transparent; }
  button:disabled { cursor: not-allowed; }
  .card {
    display: flex; flex-direction: column; gap: var(--ha-space-3, 12px);
    padding: var(--ha-space-2, 8px) var(--ha-space-4, 16px) var(--ha-space-4, 16px);
    container-type: inline-size;
    font-family: var(--ha-font-family-body, Roboto, Noto, sans-serif);
    color: var(--primary-text-color);
    -webkit-font-smoothing: antialiased;
  }
  :host([preview]) .card { pointer-events: none; }
  :host([page]) .card { gap: var(--ha-space-4, 16px); padding-bottom: var(--ha-space-6, 24px); }

  /* Tile header */
  .tile {
    display: flex; align-items: center; gap: 10px; min-height: 56px; box-sizing: border-box;
    margin: 0 calc(-1 * var(--ha-space-2, 8px)); padding: 0 var(--ha-space-2, 8px);
    border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px)); outline: none;
  }
  .tile.clickable { cursor: pointer; }
  .tile:focus-visible { box-shadow: inset 0 0 0 2px var(--tile-color); }
  .tile-icon {
    position: relative; flex: none; width: 36px; height: 36px; overflow: hidden;
    display: flex; align-items: center; justify-content: center;
    border-radius: var(--ha-tile-icon-border-radius, var(--ha-border-radius-pill, 9999px));
    color: var(--tile-color); --mdc-icon-size: 24px;
  }
  .tile-icon::before { content: ""; position: absolute; inset: 0; background: var(--tile-color); opacity: 0.2; transition: opacity 180ms ease-in-out; }
  .tile.clickable:hover .tile-icon::before { opacity: 0.35; }
  .tile-icon > * { position: relative; }
  .tile-info { flex: 1; min-width: 0; display: flex; flex-direction: column; justify-content: center; }
  .primary, .secondary { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .primary { font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500); line-height: 20px; letter-spacing: 0.1px; }
  .secondary { font-size: var(--ha-font-size-s, 12px); line-height: 16px; letter-spacing: 0.4px; color: var(--secondary-text-color); }
  .actions { display: flex; flex: none; margin-inline-end: -8px; }
  .icon-button {
    position: relative; width: 40px; height: 40px; border-radius: var(--ha-border-radius-pill, 9999px);
    display: inline-flex; align-items: center; justify-content: center;
    color: var(--secondary-text-color); --mdc-icon-size: 22px; outline: none;
  }
  .icon-button::before { content: ""; position: absolute; inset: 0; border-radius: inherit; background: var(--primary-text-color); opacity: 0; transition: opacity 150ms ease-in-out; }
  .icon-button:hover:not(:disabled)::before { opacity: 0.08; }
  .icon-button:focus-visible { box-shadow: 0 0 0 2px var(--tile-color); }
  .icon-button:disabled { color: var(--disabled-text-color, #bdbdbd); }
  .icon-button > * { position: relative; }

  /* Speakers: separated area strip, chips, compact selector row & dialog checklist */
  .picker { display: flex; flex-direction: column; gap: var(--ha-space-2, 8px); }
  .area-strip {
    display: flex; gap: 6px; overflow-x: auto; padding: 2px 0;
    scrollbar-width: none;
  }
  .area-strip::-webkit-scrollbar { display: none; }
  .area-chip {
    position: relative; flex: none; display: inline-flex; align-items: center; gap: 6px;
    height: 34px; padding: 0 11px 0 9px; box-sizing: border-box;
    border-radius: var(--ha-border-radius-md, 10px);
    border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, rgba(0, 0, 0, 0.12)));
    background: transparent;
    font-size: var(--ha-font-size-s, 13px); font-weight: var(--ha-font-weight-medium, 500);
    color: var(--primary-text-color); --mdc-icon-size: 16px; outline: none;
    user-select: none; -webkit-user-select: none;
  }
  .area-chip::before { content: ""; position: absolute; inset: 0; border-radius: inherit; background: var(--tile-color); opacity: 0; transition: opacity 150ms ease-in-out; pointer-events: none; }
  .area-chip::after { content: ""; position: absolute; inset: -3px 0; }
  .area-chip:hover:not(:disabled)::before { opacity: 0.08; }
  .area-chip[aria-checked="true"] { border-color: transparent; }
  .area-chip[aria-checked="true"]::before { opacity: 0.18; }
  .area-chip[aria-checked="mixed"] { border-color: var(--tile-color); }
  .area-chip[aria-checked="mixed"]::before { opacity: 0.08; }
  .area-chip ha-icon { position: relative; flex: none; color: var(--secondary-text-color); }
  .area-chip[aria-checked="true"] ha-icon, .area-chip[aria-checked="mixed"] ha-icon { color: var(--tile-color); }
  .area-chip span { position: relative; white-space: nowrap; }
  .area-chip .count { font-size: var(--ha-font-size-xs, 11px); color: var(--secondary-text-color); font-variant-numeric: tabular-nums; }
  .area-chip[aria-checked="true"] .count { color: var(--tile-color); }
  .area-chip:focus-visible { box-shadow: 0 0 0 2px var(--tile-color); }
  .area-chip:disabled { color: var(--disabled-text-color, #bdbdbd); border-style: dashed; cursor: default; }
  .area-chip:disabled ha-icon, .area-chip:disabled .count { color: var(--disabled-text-color, #bdbdbd); }

  .badges { display: flex; flex-wrap: wrap; gap: var(--ha-space-2, 8px); }
  .badge {
    position: relative; display: inline-flex; align-items: center; gap: 8px; max-width: 100%;
    height: 36px; min-width: 36px; padding: 0 14px 0 10px; box-sizing: border-box;
    border-radius: var(--ha-badge-border-radius, 18px);
    border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, rgba(0, 0, 0, 0.12)));
    background: var(--ha-card-background, var(--card-background-color, #fff));
    font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500); letter-spacing: 0.1px;
    color: var(--primary-text-color); --mdc-icon-size: 18px; outline: none;
    user-select: none; -webkit-user-select: none; -webkit-touch-callout: none;
  }
  .badge::before { content: ""; position: absolute; inset: 0; border-radius: inherit; background: var(--tile-color); opacity: 0; transition: opacity 150ms ease-in-out; pointer-events: none; }
  .badge::after { content: ""; position: absolute; inset: -3px 0; }
  .badge:hover:not(:disabled)::before { opacity: 0.08; }
  .badge[aria-checked="true"] { border-color: transparent; }
  .badge[aria-checked="true"]::before { opacity: 0.2; }
  .badge ha-icon { position: relative; flex: none; color: var(--secondary-text-color); }
  .badge[aria-checked="true"] ha-icon { color: var(--tile-color); }
  .badge span { position: relative; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .badge:focus-visible { box-shadow: 0 0 0 2px var(--tile-color); }
  .badge:disabled, .badge.quiet-skip { color: var(--disabled-text-color, #bdbdbd); border-style: dashed; cursor: default; }
  .badge:disabled ha-icon, .badge.quiet-skip ha-icon { color: var(--disabled-text-color, #bdbdbd); }

  .picker-row {
    position: relative; width: 100%; height: 42px; padding: 0 12px; box-sizing: border-box;
    display: flex; align-items: center; gap: 10px; border-radius: var(--gha-radius);
    font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500);
    color: var(--primary-text-color); --mdc-icon-size: 20px; text-align: start; overflow: hidden; outline: none;
  }
  .picker-row::before { content: ""; position: absolute; inset: 0; background: var(--disabled-color, #bdbdbd); opacity: 0.2; transition: opacity 180ms ease-in-out; pointer-events: none; }
  .picker-row:hover:not(:disabled)::before { opacity: 0.3; }
  .picker-row:focus-visible { box-shadow: 0 0 0 2px var(--tile-color); }
  .picker-row ha-icon { position: relative; flex: none; color: var(--secondary-text-color); }
  .picker-row .row-main { position: relative; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .picker-row .row-count { position: relative; flex: none; font-size: var(--ha-font-size-s, 12px); color: var(--secondary-text-color); font-variant-numeric: tabular-nums; }

  .sheet-search { display: block; padding: 4px 24px 12px; }
  .speakers-search {
    display: block; width: 100%; height: 40px; padding: 0 12px; box-sizing: border-box;
    border-radius: var(--ha-border-radius-md, 10px);
    border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, rgba(0, 0, 0, 0.12)));
    background: var(--primary-background-color, #fafafa); color: var(--primary-text-color);
    font: inherit; font-size: max(1rem, var(--ha-font-size-m, 14px)); outline: none;
  }
  .speakers-search::placeholder { color: var(--secondary-text-color); }
  .speakers-search:focus-visible { border-color: var(--tile-color); box-shadow: 0 0 0 1px var(--tile-color); }
  .speakers-list { padding: 0 0 12px; border-top: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12)); }
  .list-area-head {
    width: 100%; display: flex; align-items: center; gap: 8px; min-height: 36px; padding: 6px 24px; box-sizing: border-box;
    background: var(--primary-background-color, #fafafa);
    border-bottom: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
    color: var(--secondary-text-color); font-size: var(--ha-font-size-s, 12px); font-weight: var(--ha-font-weight-medium, 500);
    --mdc-icon-size: 16px; text-align: start; outline: none;
  }
  .list-area-head:focus-visible { box-shadow: inset 0 0 0 2px var(--tile-color); }
  .list-area-head .a-name { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .list-area-head .a-act { flex: none; font-size: var(--ha-font-size-xs, 11px); color: var(--tile-color); }
  .list-item {
    position: relative; width: 100%; display: flex; align-items: center; gap: 12px; min-height: 46px; padding: 4px 24px; box-sizing: border-box;
    border-bottom: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12));
    color: var(--primary-text-color); font-size: var(--ha-font-size-m, 14px); --mdc-icon-size: 20px; text-align: start; outline: none;
    user-select: none; -webkit-user-select: none; -webkit-touch-callout: none;
  }
  .list-item::before { content: ""; position: absolute; inset: 0; background: var(--primary-text-color); opacity: 0; transition: opacity 120ms ease-in-out; pointer-events: none; }
  .list-item:hover:not(:disabled)::before { opacity: 0.06; }
  .list-item:focus-visible { box-shadow: inset 0 0 0 2px var(--tile-color); }
  .list-item > * { position: relative; }
  .list-item > ha-icon { flex: none; color: var(--secondary-text-color); }
  .list-item[aria-checked="true"] > ha-icon { color: var(--tile-color); }
  .list-item:disabled { color: var(--disabled-text-color, #bdbdbd); cursor: default; }
  .list-item:disabled > ha-icon { color: var(--disabled-text-color, #bdbdbd); }
  .list-item .sp-meta { flex: 1; min-width: 0; display: flex; flex-direction: column; }
  .list-item .sp-name { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .list-item .sp-sub { font-size: var(--ha-font-size-xs, 11px); line-height: 15px; color: var(--secondary-text-color); }
  .list-item .chk {
    flex: none; width: 18px; height: 18px; border-radius: 4px; box-sizing: border-box;
    border: 2px solid var(--secondary-text-color);
    display: inline-flex; align-items: center; justify-content: center; --mdc-icon-size: 14px;
  }
  .list-item[aria-checked="true"] .chk { background: var(--tile-color); border-color: var(--tile-color); color: var(--text-primary-color, #fff); }
  .list-item:disabled .chk { border-color: var(--disabled-text-color, #bdbdbd); opacity: 0.45; }
  .list-item:not([aria-checked="true"]) .chk ha-icon { display: none; }
  .speakers-empty { padding: 20px 24px; font-size: var(--ha-font-size-m, 14px); color: var(--secondary-text-color); text-align: center; }

  /* Talk & text input */
  .talk { display: flex; flex-direction: column; align-items: center; gap: var(--ha-space-3, 12px); padding-top: var(--ha-space-2, 8px); }
  .talk.text-mode { align-items: stretch; padding-top: var(--ha-space-1, 4px); gap: var(--ha-space-2, 8px); }
  .tts-form { display: flex; flex-direction: column; gap: var(--ha-space-2, 8px); width: 100%; }
  .tts-grow { width: 100%; }
  .tts-input {
    display: block; width: 100%; height: auto; field-sizing: content;
    min-block-size: 42px; max-height: 260px; max-block-size: 12lh;
    padding: 9px 12px; box-sizing: border-box; resize: none;
    border-radius: var(--gha-radius);
    border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, rgba(0, 0, 0, 0.12)));
    background: var(--primary-background-color, #fafafa); color: var(--primary-text-color);
    font: inherit; font-size: max(1rem, var(--ha-font-size-m, 14px)); line-height: 22px;
    overflow-wrap: anywhere; outline: none;
  }
  .tts-input::placeholder { color: var(--secondary-text-color); }
  .tts-input:focus-visible { border-color: var(--tile-color); box-shadow: 0 0 0 1px var(--tile-color); }
  .tts-input:disabled { opacity: 0.6; }
  @supports not (field-sizing: content) {
    .tts-grow { display: grid; }
    .tts-grow::after, .tts-grow > .tts-input {
      grid-area: 1 / 1 / 2 / 2;
      font: inherit; font-size: max(1rem, var(--ha-font-size-m, 14px)); line-height: 22px;
      padding: 9px 12px; box-sizing: border-box;
      min-block-size: 42px; max-height: 260px;
      overflow-wrap: anywhere;
    }
    .tts-grow::after {
      content: attr(data-replicated-value) " ";
      border: var(--ha-card-border-width, 1px) solid transparent;
      white-space: pre-wrap; visibility: hidden; pointer-events: none;
    }
    .tts-grow > .tts-input { overflow-y: auto; }
  }
  .mic {
    position: relative; width: 88px; height: 88px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    color: var(--text-primary-color, #fff); --mdc-icon-size: 40px; outline: none;
    touch-action: none; user-select: none; -webkit-user-select: none; -webkit-touch-callout: none;
  }
  :host([page]) .mic { width: 120px; height: 120px; --mdc-icon-size: 52px; }
  .mic .disc { position: absolute; inset: 0; border-radius: 50%; background: var(--tile-color); box-shadow: var(--ha-box-shadow-s, 0 2px 6px rgba(0, 0, 0, 0.2)); transition: background-color 150ms ease-in-out, transform 150ms ease-in-out; }
  .mic .ring { position: absolute; inset: -12px; border-radius: 50%; background: var(--tile-color); opacity: 0; transform: scale(calc(0.85 + var(--level, 0) * 0.3)); transition: transform 90ms linear, opacity 150ms ease-in-out; }
  .mic ha-icon, .mic .spinner { position: relative; }
  .mic:hover:not(:disabled) .disc { transform: scale(1.03); }
  .mic:active:not(:disabled) .disc { transform: scale(0.97); }
  .mic:focus-visible .disc { box-shadow: 0 0 0 3px var(--card-background-color, #fff), 0 0 0 5px var(--tile-color); }
  .mic:disabled { color: var(--disabled-text-color, #bdbdbd); }
  .mic:disabled .disc { background: var(--disabled-color, #bdbdbd); box-shadow: none; opacity: 0.4; }
  .mic.recording .disc { background: var(--gha-recording); }
  .mic.recording .ring { background: var(--gha-recording); opacity: 0.2; }
  .mic.preparing .ring { opacity: 0.16; animation: pulse 1s ease-in-out infinite; }
  .mic.sending:disabled, .mic.review:disabled { color: var(--text-primary-color, #fff); }
  .mic.sending:disabled .disc, .mic.review:disabled .disc { background: var(--tile-color); opacity: 0.6; }
  @keyframes pulse { 50% { transform: scale(1.05); } }
  .spinner { width: 30px; height: 30px; border-radius: 50%; box-sizing: border-box; border: 3px solid currentColor; border-right-color: transparent; animation: spin 0.8s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .hint {
    display: flex; align-items: center; justify-content: center; gap: 6px; min-height: 20px; max-width: 100%;
    font-size: var(--ha-font-size-s, 12px); line-height: 16px; letter-spacing: 0.4px; text-align: center;
    color: var(--secondary-text-color); font-variant-numeric: tabular-nums; --mdc-icon-size: 18px;
  }
  .hint.success { color: var(--primary-text-color); font-size: var(--ha-font-size-m, 14px); line-height: 20px; }
  .hint.success ha-icon { color: var(--success-color, #43a047); flex: none; }

  /* Card features: 42px rows */
  .features { display: flex; flex-direction: column; gap: var(--ha-space-3, 12px); }
  .features:empty, .features:not(:has(> :not([hidden]))) { display: none; }
  .buttons { display: flex; gap: var(--ha-space-3, 12px); }
  .features > .button, .options > .button, .button.tts-send { flex: none; width: 100%; }
  .button {
    position: relative; overflow: hidden; z-index: 0; flex: 1 1 0; min-width: 0; height: 42px;
    display: flex; align-items: center; justify-content: center; gap: 8px; padding: 0 12px; box-sizing: border-box;
    border-radius: var(--gha-radius); font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500);
    color: var(--primary-text-color); --mdc-icon-size: 20px; outline: none;
  }
  .button::before { content: ""; position: absolute; inset: 0; background: var(--disabled-color, #bdbdbd); opacity: 0.2; transition: opacity 180ms ease-in-out; pointer-events: none; }
  .button:hover:not(:disabled)::before { opacity: 0.3; }
  .button.primary { color: var(--text-primary-color, #fff); }
  .button.primary::before { background: var(--tile-color); opacity: 1; }
  .button.primary:hover:not(:disabled)::before { opacity: 0.9; }
  .button:focus-visible { box-shadow: 0 0 0 2px var(--tile-color); }
  .button:disabled { color: var(--disabled-text-color, #bdbdbd); }
  .button > * { position: relative; }
  .button span { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

  /* Volume, like ha-control-slider */
  .volume { display: flex; flex-direction: column; gap: var(--ha-space-2, 8px); }
  .volume-head { display: flex; align-items: center; gap: 6px; font-size: var(--ha-font-size-s, 12px); line-height: 16px; letter-spacing: 0.4px; color: var(--secondary-text-color); --mdc-icon-size: 18px; }
  .volume-head > ha-icon { flex: none; color: var(--tile-color); }
  .volume-label { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .quiet-pill {
    position: relative; display: inline-flex; align-items: center; gap: 4px; flex: none; max-width: 48%;
    padding: 1px 8px; border-radius: var(--ha-border-radius-pill, 9999px); overflow: hidden;
    font-size: var(--ha-font-size-xs, 11px); font-weight: var(--ha-font-weight-medium, 500);
    line-height: 16px; color: var(--indigo-color, #3f51b5); --mdc-icon-size: 14px;
  }
  .quiet-pill::before { content: ""; position: absolute; inset: 0; background: var(--indigo-color, #3f51b5); opacity: 0.14; pointer-events: none; }
  .quiet-pill ha-icon { position: relative; flex: none; color: var(--indigo-color, #3f51b5); }
  .quiet-pill span { position: relative; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .slider { position: relative; flex: none; min-width: 0; height: 42px; border-radius: var(--gha-radius); overflow: hidden; }
  .slider::before { content: ""; position: absolute; inset: 0; background: var(--tile-color); opacity: 0.2; }
  .slider .fill { position: absolute; inset: 0 auto 0 0; width: var(--fill, 50%); background: var(--tile-color); }
  .slider .fill::after { content: ""; position: absolute; top: 50%; right: 8px; width: 4px; height: 16px; margin-top: -8px; border-radius: 2px; background: var(--text-primary-color, #fff); opacity: 0.8; }
  .slider .cap-mark { position: absolute; top: 0; bottom: 0; left: var(--cap, 25%); width: 2px; background: var(--indigo-color, #3f51b5); opacity: 0.75; pointer-events: none; }
  .slider .label { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; font-size: var(--ha-font-size-s, 12px); letter-spacing: 0.4px; color: var(--secondary-text-color); pointer-events: none; }
  .slider input { position: absolute; inset: 0; width: 100%; height: 100%; margin: 0; opacity: 0; cursor: pointer; -webkit-appearance: none; appearance: none; touch-action: pan-y; }
  .slider input::-webkit-slider-thumb { -webkit-appearance: none; width: 1px; height: 42px; }
  .slider input::-moz-range-thumb { width: 1px; height: 42px; border: none; }
  .slider:focus-within { box-shadow: 0 0 0 2px var(--tile-color); }
  .slider.off::before { background: var(--disabled-color, #bdbdbd); }
  .slider.off .fill { display: none; }
  .slider.off input { cursor: default; }
  .volume .value { flex: none; font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500); color: var(--primary-text-color); font-variant-numeric: tabular-nums; }

  /* Alerts, like ha-alert */
  .alert { position: relative; display: flex; padding: 12px; border-radius: var(--ha-border-radius-lg, 12px); overflow: hidden; --mdc-icon-size: 24px; }
  .alert::before { content: ""; position: absolute; inset: 0; background: var(--alert-color); opacity: 0.12; }
  .alert ha-icon { position: relative; flex: none; color: var(--alert-color); }
  .alert .text { position: relative; margin-inline: 8px; line-height: 20px; font-size: var(--ha-font-size-m, 14px); }
  .alert.info { --alert-color: var(--info-color, #039be5); }
  .alert.warning { --alert-color: var(--warning-color, #ffa600); }
  .alert.error { --alert-color: var(--error-color, #db4437); }

  /* Options */
  .options { display: flex; flex-direction: column; gap: var(--ha-space-4, 16px); }
  .field-head { display: flex; align-items: center; justify-content: space-between; gap: var(--ha-space-2, 8px); margin-bottom: var(--ha-space-2, 8px); }
  .field-head .field-label { margin-bottom: 0; }
  .field-label { font-size: var(--ha-font-size-m, 14px); line-height: 20px; margin-bottom: var(--ha-space-2, 8px); }
  .chime-preview { min-inline-size: 40px; min-block-size: 40px; margin-block: -10px; margin-inline-end: -8px; --mdc-icon-size: 20px; }
  .chime-preview[aria-disabled="true"] { color: var(--disabled-text-color, #bdbdbd); cursor: not-allowed; }
  .chime-preview[aria-disabled="true"]::before { opacity: 0; }
  .chime-preview.playing { color: var(--tile-color); }
  .chime-preview.playing::before { background: var(--tile-color); opacity: 0.16; }
  .segmented { position: relative; display: flex; gap: 4px; padding: 4px; height: 42px; box-sizing: border-box; border-radius: var(--gha-radius); }
  .segmented::before { content: ""; position: absolute; inset: 0; border-radius: inherit; background: var(--disabled-color, #bdbdbd); opacity: 0.2; pointer-events: none; }
  .option { position: relative; flex: 1; min-width: 0; border-radius: calc(var(--gha-radius) - 4px); font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-medium, 500); color: var(--primary-text-color); outline: none; }
  .segmented:has(:nth-child(5)) .option { flex: 1 1 auto; font-size: var(--ha-font-size-s, 13px); }
  .option::before { content: ""; position: absolute; inset: 0; border-radius: inherit; background: var(--tile-color); opacity: 0; transition: opacity 80ms ease-in-out; }
  .option:hover::before { opacity: 0.2; }
  .option[aria-checked="true"] { color: var(--text-primary-color, #fff); }
  .option[aria-checked="true"]::before { opacity: 1; }
  .option:focus-visible { box-shadow: 0 0 0 2px var(--tile-color); }
  .option span { position: relative; display: block; padding: 0 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .row { display: flex; align-items: center; gap: var(--ha-space-4, 16px); min-height: 42px; }
  .row .text { flex: 1; min-width: 0; }
  .row .label { font-size: var(--ha-font-size-m, 14px); line-height: 20px; }
  .row .helper { font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--secondary-text-color); margin-top: 2px; }
  .switch { position: relative; flex: none; width: 36px; height: 20px; border-radius: 10px; outline: none; }
  .switch::before { content: ""; position: absolute; inset: 0; border-radius: inherit; background: var(--disabled-color, #bdbdbd); transition: background-color 150ms ease-in-out; }
  .switch::after { content: ""; position: absolute; top: 3px; left: 3px; width: 14px; height: 14px; border-radius: 50%; background: var(--card-background-color, #fff); transition: transform 150ms ease-in-out; }
  .switch[aria-checked="true"]::before { background: var(--tile-color); }
  .switch[aria-checked="true"]::after { transform: translateX(16px); background: var(--text-primary-color, #fff); }
  .switch:focus-visible { box-shadow: 0 0 0 2px var(--card-background-color, #fff), 0 0 0 4px var(--tile-color); }
  .section { display: flex; flex-direction: column; gap: var(--ha-space-3, 12px); padding-top: var(--ha-space-4, 16px); border-top: 1px solid var(--divider-color, rgba(0, 0, 0, 0.12)); }
  .section-title { font-size: var(--ha-font-size-l, 16px); font-weight: var(--ha-font-weight-medium, 500); line-height: 24px; }
  .note { font-size: var(--ha-font-size-s, 12px); line-height: 16px; color: var(--secondary-text-color); }
  .intercoms { display: flex; flex-direction: column; gap: var(--ha-space-2, 8px); }
  .intercoms .tile { margin: 0; border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color, rgba(0, 0, 0, 0.12))); }

  /* Dialog, like ha-dialog; a bottom sheet on phones */
  dialog {
    width: min(580px, 95vw); max-height: min(80vh, 720px); padding: 0; border: none; overflow: hidden;
    border-radius: var(--ha-dialog-border-radius, var(--ha-border-radius-3xl, 24px));
    background: var(--ha-dialog-surface-background, var(--card-background-color, #fff));
    color: var(--primary-text-color); box-shadow: var(--ha-box-shadow-l, 0 16px 32px -6px rgba(0, 0, 0, 0.2));
    font-family: var(--ha-font-family-body, Roboto, Noto, sans-serif);
  }
  dialog[open] { display: flex; flex-direction: column; animation: dialog-in 200ms ease-out; }
  dialog::backdrop { background: rgba(0, 0, 0, 0.32); }
  @keyframes dialog-in { from { opacity: 0; transform: scale(0.96); } }
  .dialog-header { display: flex; align-items: center; gap: 8px; padding: 16px 12px 4px 24px; }
  .dialog-title { flex: 1; font-size: var(--ha-font-size-2xl, 24px); line-height: 1.2; font-weight: var(--ha-font-weight-normal, 400); }
  .dialog-content { padding: 12px 24px 24px; overflow: auto; outline: none; }
  @media (max-width: 870px), (max-height: 500px) {
    dialog {
      width: 100vw; max-width: 100vw; margin: auto 0 0; max-height: 90vh;
      border-radius: var(--ha-border-radius-2xl, 20px) var(--ha-border-radius-2xl, 20px) 0 0;
      padding-bottom: var(--safe-area-inset-bottom, env(safe-area-inset-bottom, 0px));
    }
    dialog[open] { animation-name: sheet-in; }
    @keyframes sheet-in { from { transform: translateY(40px); opacity: 0; } }
  }

  @container (max-width: 320px) {
    .mic { width: 76px; height: 76px; --mdc-icon-size: 34px; }
    .badge { padding: 0 12px 0 8px; }
  }
  @media (prefers-reduced-motion: reduce) {
    * { animation-duration: 1ms !important; transition-duration: 1ms !important; }
  }
  @media (forced-colors: active) {
    .icon-button:focus-visible, .badge:focus-visible, .area-chip:focus-visible, .picker-row:focus-visible, .list-area-head:focus-visible, .list-item:focus-visible, .button:focus-visible, .option:focus-visible, .switch:focus-visible, .tts-input:focus-visible, .speakers-search:focus-visible {
      outline: 2px solid ButtonText;
      outline-offset: 2px;
    }
  }
`;

const Base = globalThis.HTMLElement ?? class {};

/* The card. With the page attribute it fills the sidebar panel. */
export class HannounceCard extends Base {
  static getConfigElement() {
    return document.createElement(EDITOR_TYPE);
  }

  static getStubConfig() {
    return {};
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._info = undefined;
    this._selected = undefined;
    this._rec = "idle"; // idle, preparing, recording, review, sending
    this._recMode = "hold";
    this._badges = new Map();
    this._areaControls = new Map();
    this._dialogRows = new Map();
    this._dialogAreas = new Map();
    this._speakerQuery = "";
    const stored = readStore();
    this._prefs = {
      volume: stored.volume,
      keepVolume: stored.keepVolume,
      chime: stored.chime,
      review: stored.review,
      mode: stored.mode,
    };
    this._onKey = (ev) => {
      if (ev.key === "Escape" && (this._rec === "recording" || this._rec === "preparing")) this._cancel();
    };
  }

  setConfig(config) {
    if (!config || typeof config !== "object") throw new Error("Invalid configuration");
    if (config.entities !== undefined && (!Array.isArray(config.entities) || config.entities.some((e) => typeof e !== "string"))) {
      throw new Error("entities must be a list of media_player entity ids");
    }
    this._config = { ...config };
    this.style.setProperty("--tile-color", colorVar(this._config.color));
    if (this._built) {
      this._badgeKey = undefined;
      this._initSelection();
      this._render();
    }
  }

  set hass(hass) {
    const old = this._hass;
    this._hass = hass;
    if (!this._built) this._build();
    if (this._info === undefined && !this._loading) this._load();
    if (!old || this._changed(old, hass)) this._render();
  }

  get hass() {
    return this._hass;
  }

  set preview(value) {
    // The card picker and the editor show a preview: it looks real but does nothing
    this._preview = Boolean(value);
    this.toggleAttribute("preview", this._preview);
    if (this._built && this._hass) {
      this._initSelection();
      this._render();
    }
  }

  // Home Assistant sets a `layout` property on cards in sections: the panel uses an attribute instead
  get _page() {
    return this.hasAttribute("page");
  }

  connectedCallback() {
    if (this._hass && this._info) this._load();
    this._subscribe();
    this._startQuietTimer();
  }

  disconnectedCallback() {
    this._cancel();
    this._stopChimePreview();
    this._unsubscribe();
    clearInterval(this._quietTimer);
    this._quietTimer = undefined;
    this._el?.dialog.close();
    this._el?.speakersDialog.close();
  }

  _startQuietTimer() {
    clearInterval(this._quietTimer);
    this._quietTimer = setInterval(() => {
      if (!this._built || !this._hass || !this._info?.quiet?.enabled) return;
      const active = this._isQuietActive();
      if (active !== this._lastQuietActive) {
        this._lastQuietActive = active;
        this._renderBadges();
        this._renderHeader();
        this._renderRec();
        this._renderVolume();
      }
    }, 30000);
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  // Data

  _changed(old, hass) {
    if (old.language !== hass.language || old.locale !== hass.locale || old.themes !== hass.themes || old.entities !== hass.entities) {
      return true;
    }
    const quietEntity = this._info?.quiet?.entity_id;
    if (quietEntity && old.states[quietEntity] !== hass.states[quietEntity]) return true;
    return this._speakers().some((s) => old.states[s.entity_id] !== hass.states[s.entity_id]);
  }

  async _load() {
    this._loading = true;
    try {
      this._info = await this._hass.callWS({ type: `${DOMAIN}/info` });
      this._loadError = undefined;
    } catch (err) {
      this._info = null;
      this._loadError = err?.code === "not_set_up" || err?.code === "unknown_command" ? "not_set_up" : err?.message;
    }
    this._loading = false;
    if (this._info) {
      const defaults = this._info.defaults;
      this._prefs.volume ??= defaults.volume;
      this._prefs.keepVolume ??= !defaults.set_volume;
      if (!this._availableChimes().includes(this._prefs.chime)) this._prefs.chime = defaults.chime;
      this._badgeKey = undefined;
      this._dialogKey = undefined;
      this._chimeKey = undefined;
      this._lastQuietActive = this._isQuietActive();
      this._initSelection();
    }
    this._render();
    this._subscribe();
  }

  _subscribe() {
    if (this._unsub || !this._hass?.connection || !this.isConnected || !this._info) return;
    this._unsub = this._hass.connection
      .subscribeMessage((event) => this._onAnnounced(event), { type: `${DOMAIN}/subscribe` })
      .catch(() => undefined);
  }

  _unsubscribe() {
    const unsub = this._unsub;
    this._unsub = undefined;
    unsub?.then((fn) => fn?.()).catch(() => undefined);
  }

  _onAnnounced(event) {
    if (!this._info) return;
    this._info.last = event;
    this._renderHeader();
    if (this._waitingIntercom && event.source === "intercom") {
      clearTimeout(this._waitingIntercom);
      this._waitingIntercom = undefined;
      this._setRec("idle");
      this._success(t(this._hass, "sent", { targets: this._names(event.targets) }));
    }
  }

  _speakers() {
    const all = this._info?.speakers || [];
    const only = this._config.entities;
    if (Array.isArray(only) && only.length) {
      const known = new Map(all.map((s) => [s.entity_id, s]));
      return only.map(
        (id) => known.get(id) || { entity_id: id, name: this._hass?.states[id]?.attributes.friendly_name || id, area: null, group: false }
      );
    }
    return all;
  }

  _availableChimes() {
    const list = this._info?.chimes;
    if (Array.isArray(list) && list.length) return list.filter((c) => ALL_CHIMES.includes(c));
    return CHIMES;
  }

  _currentChime() {
    const chimes = this._availableChimes();
    if (chimes.includes(this._prefs.chime)) return this._prefs.chime;
    const fallback = this._info?.defaults?.chime;
    return chimes.includes(fallback) ? fallback : "ding_dong";
  }

  _isQuietActive() {
    return isQuietActive(this._hass, this._info?.quiet);
  }

  _quietAffects(speaker) {
    const quiet = this._info?.quiet;
    if (!quiet) return false;
    return !quiet.speakers?.length || quiet.speakers.includes(speaker.entity_id);
  }

  _quietSkipped(speaker) {
    const quiet = this._info?.quiet;
    return Boolean(this._isQuietActive() && quiet?.mode === "skip" && this._quietAffects(speaker));
  }

  _ttsAvailable() {
    return Boolean(this._info?.tts?.available);
  }

  _isTextMode() {
    if (!this._ttsAvailable()) return false;
    if (this._prefs.mode === "text") return true;
    if (this._prefs.mode === "voice") return false;
    return this._capturePath() === "none" && !this._preview;
  }

  _available(speaker) {
    const state = this._hass?.states[speaker.entity_id];
    return Boolean(state && state.state !== "unavailable" && state.state !== "unknown");
  }

  _selectable(speaker) {
    return this._available(speaker) && !this._quietSkipped(speaker);
  }

  _initSelection() {
    if (!this._info) return;
    const speakers = this._speakers();
    const ids = new Set(speakers.map((s) => s.entity_id));
    const stored = (readStore().targets || []).filter((id) => ids.has(id));
    if (this._selected) {
      this._selected = new Set([...this._selected].filter((id) => ids.has(id)));
    } else if (speakers.length === 1) {
      this._selected = new Set([speakers[0].entity_id]);
    } else {
      this._selected = new Set(stored);
    }
    if (this._preview && !this._selected.size) {
      const first = speakers.find((s) => this._selectable(s));
      if (first) this._selected = new Set([first.entity_id]);
    }
  }

  _targets() {
    const byId = new Map(this._speakers().map((s) => [s.entity_id, s]));
    return [...(this._selected || [])].filter((id) => byId.has(id) && this._selectable(byId.get(id)));
  }

  _names(ids) {
    const byId = new Map(this._speakers().map((s) => [s.entity_id, s.name]));
    return formatTargets(
      this._hass,
      (ids || []).map((id) => byId.get(id) || this._hass?.states[id]?.attributes.friendly_name || id)
    );
  }

  _reviewOn() {
    if (this._prefs.review !== undefined) return Boolean(this._prefs.review);
    return Boolean(this._config.review);
  }

  _volumeValue() {
    return this._prefs.keepVolume ? "keep" : String(this._prefs.volume ?? 60);
  }

  _capturePath() {
    if (window.isSecureContext && navigator.mediaDevices?.getUserMedia && window.MediaRecorder) return "browser";
    const external = this._hass?.auth?.external;
    const intercom = this._info?.intercom;
    if (external?.config?.webrtc?.hasCameraMicrophoneStream && intercom?.ready && intercom?.broadcast_entity_id) return "app";
    return "none";
  }

  _intercoms() {
    return Object.values(this._hass?.entities || {})
      .filter((e) => e.platform === DOMAIN && e.entity_id.startsWith("camera.") && !e.hidden)
      .sort((a, b) => (a.translation_key === "intercom_all" ? -1 : b.translation_key === "intercom_all" ? 1 : 0));
  }

  // DOM, built once and patched afterwards so focus and pointer capture survive

  _build() {
    this._built = true;
    this.shadowRoot.innerHTML = `
      <style>${STYLES}</style>
      <ha-card>
        <div class="card">
          <div class="tile">
            <div class="tile-icon"><ha-icon></ha-icon></div>
            <div class="tile-info"><span class="primary"></span><span class="secondary"></span></div>
            <div class="actions">
              <button class="icon-button mode-toggle" type="button" hidden><ha-icon icon="mdi:keyboard-outline"></ha-icon></button>
              <button class="icon-button replay" type="button"><ha-icon icon="mdi:replay"></ha-icon></button>
              <button class="icon-button settings" type="button" aria-haspopup="dialog"><ha-icon icon="mdi:tune-variant"></ha-icon></button>
            </div>
          </div>
          <div class="alert-slot"></div>
          <div class="picker" hidden>
            <div class="area-strip" role="group" hidden></div>
            <div class="badges" role="group" hidden></div>
            <button class="picker-row" type="button" aria-haspopup="dialog" hidden>
              <ha-icon icon="mdi:speaker"></ha-icon>
              <span class="row-main"></span>
              <span class="row-count"></span>
              <ha-icon icon="mdi:chevron-down"></ha-icon>
            </button>
          </div>
          <div class="talk">
            <button class="mic" type="button"><span class="ring"></span><span class="disc"></span><ha-icon icon="mdi:microphone"></ha-icon></button>
            <form class="tts-form" hidden>
              <label class="visually-hidden tts-label" for="tts-input"></label>
              <div class="tts-grow">
                <textarea id="tts-input" name="message" class="tts-input" rows="1" maxlength="1000" enterkeyhint="send" autocomplete="off"></textarea>
              </div>
              <button class="button primary tts-send" type="submit"><ha-icon icon="mdi:send"></ha-icon><span></span></button>
            </form>
            <div class="hint" aria-live="polite"><ha-icon icon="mdi:check-circle-outline" hidden></ha-icon><span></span></div>
          </div>
          <div class="features">
            <div class="buttons review" hidden>
              <button class="button play" type="button"><ha-icon icon="mdi:play"></ha-icon><span></span></button>
              <button class="button discard" type="button"><ha-icon icon="mdi:delete-outline"></ha-icon><span></span></button>
              <button class="button primary send" type="button"><ha-icon icon="mdi:send"></ha-icon><span></span></button>
            </div>
            <div class="volume">
              <div class="volume-head">
                <ha-icon icon="mdi:volume-high"></ha-icon>
                <span class="volume-label" id="volume-label"></span>
                <span class="quiet-pill" hidden><ha-icon icon="mdi:weather-night"></ha-icon><span></span></span>
                <span class="value"></span>
              </div>
              <div class="slider"><div class="fill"></div><div class="cap-mark" hidden></div><div class="label"></div><input type="range" min="5" max="100" step="5" aria-labelledby="volume-label" /></div>
            </div>
            <button class="button upload-feature" type="button" hidden><ha-icon icon="mdi:file-music-outline"></ha-icon><span></span></button>
          </div>
          <div class="section options-section" hidden><div class="section-title options-title"></div></div>
          <div class="section intercom-section" hidden>
            <div class="section-title intercom-title"></div>
            <div class="note intercom-note"></div>
            <div class="intercoms"></div>
          </div>
        </div>
      </ha-card>
      <dialog class="options-dialog" aria-labelledby="dialog-title">
        <div class="dialog-header">
          <span class="dialog-title" id="dialog-title"></span>
          <button class="icon-button close" type="button"><ha-icon icon="mdi:close"></ha-icon></button>
        </div>
        <div class="dialog-content" tabindex="-1" autofocus></div>
      </dialog>
      <dialog class="speakers-dialog" aria-labelledby="speakers-dialog-title">
        <div class="dialog-header">
          <span class="dialog-title speakers-dialog-title" id="speakers-dialog-title"></span>
          <button class="icon-button close-speakers" type="button"><ha-icon icon="mdi:close"></ha-icon></button>
        </div>
        <search class="sheet-search" hidden>
          <label class="visually-hidden speakers-search-label" for="speakers-search"></label>
          <input id="speakers-search" name="filter" class="speakers-search" type="search" autocomplete="off" />
        </search>
        <div class="dialog-content speakers-list" tabindex="-1"></div>
      </dialog>
      <input class="file" type="file" accept="audio/*" hidden />
    `;
    const $ = (selector) => this.shadowRoot.querySelector(selector);
    this._el = {
      tile: $(".tile"),
      tileIcon: $(".tile-icon ha-icon"),
      primary: $(".primary"),
      secondary: $(".secondary"),
      modeToggle: $(".mode-toggle"),
      modeToggleIcon: $(".mode-toggle ha-icon"),
      replay: $(".replay"),
      settings: $(".settings"),
      alert: $(".alert-slot"),
      picker: $(".picker"),
      areaStrip: $(".area-strip"),
      badges: $(".badges"),
      pickerRow: $(".picker-row"),
      pickerMain: $(".picker-row .row-main"),
      pickerCount: $(".picker-row .row-count"),
      talk: $(".talk"),
      mic: $(".mic"),
      micIcon: $(".mic ha-icon"),
      ttsForm: $(".tts-form"),
      ttsGrow: $(".tts-grow"),
      ttsLabel: $(".tts-label"),
      ttsInput: $(".tts-input"),
      ttsSend: $(".tts-send"),
      hint: $(".hint"),
      hintIcon: $(".hint ha-icon"),
      hintText: $(".hint span"),
      review: $(".review"),
      play: $(".play"),
      discard: $(".discard"),
      send: $(".send"),
      volume: $(".volume"),
      volumeIcon: $(".volume-head > ha-icon"),
      volumeLabel: $(".volume-label"),
      quietPill: $(".quiet-pill"),
      quietPillText: $(".quiet-pill span"),
      slider: $(".slider"),
      capMark: $(".slider .cap-mark"),
      sliderLabel: $(".slider .label"),
      range: $(".slider input"),
      value: $(".volume .value"),
      uploadFeature: $(".upload-feature"),
      optionsSection: $(".options-section"),
      optionsTitle: $(".options-title"),
      intercomSection: $(".intercom-section"),
      intercomTitle: $(".intercom-title"),
      intercomNote: $(".intercom-note"),
      intercoms: $(".intercoms"),
      dialog: $(".options-dialog"),
      dialogTitle: $(".options-dialog .dialog-title"),
      dialogContent: $(".options-dialog .dialog-content"),
      close: $(".close"),
      speakersDialog: $(".speakers-dialog"),
      speakersDialogTitle: $(".speakers-dialog-title"),
      closeSpeakers: $(".close-speakers"),
      sheetSearch: $(".sheet-search"),
      speakersSearchLabel: $(".speakers-search-label"),
      speakersSearch: $(".speakers-search"),
      speakersList: $(".speakers-list"),
      file: $(".file"),
    };
    this._options = this._buildOptions();
    this._placeOptions();
    this._wire();
  }

  _placeOptions() {
    const target = this._page ? this._el.optionsSection : this._el.dialogContent;
    if (this._options.root.parentElement !== target) target.appendChild(this._options.root);
  }

  _buildOptions() {
    const root = document.createElement("div");
    root.className = "options";
    root.innerHTML = `
      <div class="field">
        <div class="field-head">
          <div class="field-label chime-label" id="chime-label"></div>
          <button class="icon-button chime-preview" type="button"><ha-icon icon="mdi:play"></ha-icon></button>
        </div>
        <div class="segmented" role="radiogroup" aria-labelledby="chime-label"></div>
      </div>
      <div class="row">
        <div class="text"><div class="label keep-label" id="keep-label"></div><div class="helper keep-helper"></div></div>
        <button class="switch keep" type="button" role="switch" aria-labelledby="keep-label"></button>
      </div>
      <div class="row">
        <div class="text"><div class="label review-label" id="review-label"></div></div>
        <button class="switch review-switch" type="button" role="switch" aria-labelledby="review-label"></button>
      </div>
      <button class="button upload" type="button"><ha-icon icon="mdi:file-music-outline"></ha-icon><span></span></button>
    `;
    return {
      root,
      segmented: root.querySelector(".segmented"),
      chimeLabel: root.querySelector(".chime-label"),
      chimePreview: root.querySelector(".chime-preview"),
      chimePreviewIcon: root.querySelector(".chime-preview ha-icon"),
      keepLabel: root.querySelector(".keep-label"),
      keepHelper: root.querySelector(".keep-helper"),
      keep: root.querySelector(".keep"),
      reviewLabel: root.querySelector(".review-label"),
      review: root.querySelector(".review-switch"),
      upload: root.querySelector(".upload"),
    };
  }

  _wire() {
    const el = this._el;
    const opts = this._options;

    el.tile.addEventListener("click", (ev) => {
      if (!ev.target.closest(".actions")) this._openSpeakerInfo();
    });
    el.tile.addEventListener("keydown", (ev) => {
      if ((ev.key === "Enter" || ev.key === " ") && ev.target === el.tile) {
        ev.preventDefault();
        this._openSpeakerInfo();
      }
    });
    el.modeToggle.addEventListener("click", () => this._toggleMode());
    el.ttsForm.addEventListener("submit", (ev) => this._sendText(ev));
    el.ttsInput.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) {
        ev.preventDefault();
        if (ev.isComposing || ev.keyCode === 229) return;
        el.ttsForm.requestSubmit();
      }
    });
    if (!globalThis.CSS?.supports?.("field-sizing", "content")) {
      el.ttsInput.addEventListener("input", () => {
        el.ttsGrow.dataset.replicatedValue = el.ttsInput.value;
      });
    }
    el.replay.addEventListener("click", () => this._replay());
    el.settings.addEventListener("click", () => {
      this._renderOptions();
      el.dialog.showModal();
    });
    el.close.addEventListener("click", () => el.dialog.close());
    el.dialog.addEventListener("close", () => this._stopChimePreview());
    el.dialog.addEventListener("click", (ev) => {
      if (ev.target === el.dialog) el.dialog.close(); // a click on the scrim
    });

    // Speakers and areas: a tap selects, a long press or a right click opens the speaker
    el.areaStrip.addEventListener("click", (ev) => {
      const chip = ev.target.closest(".area-chip");
      if (!chip || chip.disabled) return;
      if (chip.dataset.id === "*") this._toggleSpeaker("*");
      else if (chip.dataset.area) this._toggleArea(chip.dataset.area);
    });
    el.pickerRow.addEventListener("click", () => {
      if (this._preview) return;
      this._speakerQuery = "";
      el.speakersSearch.value = "";
      this._renderSpeakersDialog();
      el.speakersDialog.showModal();
      if (!el.sheetSearch.hidden) el.speakersSearch.focus();
    });
    el.closeSpeakers.addEventListener("click", () => el.speakersDialog.close());
    el.speakersDialog.addEventListener("click", (ev) => {
      if (ev.target === el.speakersDialog) el.speakersDialog.close();
    });
    el.speakersSearch.addEventListener("input", () => {
      this._speakerQuery = el.speakersSearch.value;
      this._filterSpeakersDialog();
    });
    el.speakersList.addEventListener("click", (ev) => {
      const areaHead = ev.target.closest(".list-area-head[data-area]");
      if (areaHead) {
        this._toggleArea(areaHead.dataset.area);
        return;
      }
      const row = ev.target.closest(".list-item[data-id]");
      if (!row || row.disabled) return;
      if (this._longPressed) {
        this._longPressed = false;
        return;
      }
      this._toggleSpeaker(row.dataset.id);
    });
    el.speakersList.addEventListener("contextmenu", (ev) => {
      const row = ev.target.closest(".list-item[data-id]");
      if (!row) return;
      ev.preventDefault();
      this._moreInfo(row.dataset.id);
    });
    el.speakersList.addEventListener("pointerdown", (ev) => {
      const row = ev.target.closest(".list-item[data-id]");
      if (!row || ev.pointerType === "mouse") return;
      clearTimeout(this._pressTimer);
      this._pressTimer = setTimeout(() => {
        this._longPressed = true;
        this._moreInfo(row.dataset.id);
      }, LONG_PRESS_MS);
    });
    for (const type of ["pointerup", "pointercancel", "pointerleave"]) {
      el.speakersList.addEventListener(type, () => clearTimeout(this._pressTimer));
    }

    el.badges.addEventListener("click", (ev) => {
      const badge = ev.target.closest(".badge[data-id]");
      if (!badge) return;
      if (this._longPressed) {
        this._longPressed = false;
        return;
      }
      this._toggleSpeaker(badge.dataset.id);
    });
    el.badges.addEventListener("contextmenu", (ev) => {
      const badge = ev.target.closest(".badge[data-id]");
      if (!badge || badge.dataset.id === "*") return;
      ev.preventDefault();
      this._moreInfo(badge.dataset.id);
    });
    el.badges.addEventListener("pointerdown", (ev) => {
      const badge = ev.target.closest(".badge[data-id]");
      if (!badge || badge.dataset.id === "*" || ev.pointerType === "mouse") return;
      clearTimeout(this._pressTimer);
      this._pressTimer = setTimeout(() => {
        this._longPressed = true;
        this._moreInfo(badge.dataset.id);
      }, LONG_PRESS_MS);
    });
    for (const type of ["pointerup", "pointercancel", "pointerleave"]) {
      el.badges.addEventListener(type, () => clearTimeout(this._pressTimer));
    }

    el.mic.addEventListener("pointerdown", (ev) => this._micDown(ev));
    el.mic.addEventListener("pointerup", (ev) => this._micUp(ev));
    el.mic.addEventListener("pointercancel", (ev) => this._micUp(ev));
    el.mic.addEventListener("contextmenu", (ev) => ev.preventDefault());
    el.mic.addEventListener("keydown", (ev) => {
      if (ev.key !== "Enter" && ev.key !== " ") return;
      ev.preventDefault();
      if (ev.repeat) return;
      if (this._rec === "idle") {
        this._recMode = "toggle";
        this._begin();
      } else if (this._rec === "recording") {
        this._finish();
      }
    });

    el.play.addEventListener("click", () => this._togglePreview());
    el.discard.addEventListener("click", () => this._discard());
    el.send.addEventListener("click", () => this._sendPending());

    el.range.addEventListener("input", () => {
      this._prefs.volume = Number(el.range.value);
      this._renderVolume();
    });
    el.range.addEventListener("change", () => writeStore({ volume: this._prefs.volume }));

    const setChime = (chime) => {
      if (chime === "none" || this._chimePreview) this._stopChimePreview();
      this._prefs.chime = chime;
      writeStore({ chime });
      this._renderOptions();
    };
    opts.segmented.addEventListener("click", (ev) => {
      const button = ev.target.closest(".option[data-chime]");
      if (button) setChime(button.dataset.chime);
    });
    opts.chimePreview.addEventListener("click", () => {
      if (opts.chimePreview.getAttribute("aria-disabled") === "true") return;
      this._toggleChimePreview();
    });
    opts.segmented.addEventListener("keydown", (ev) => {
      let step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[ev.key];
      if (!step) return;
      ev.preventDefault();
      if (getComputedStyle(this).direction === "rtl" && (ev.key === "ArrowRight" || ev.key === "ArrowLeft")) step = -step;
      const chimes = this._availableChimes();
      const index = (chimes.indexOf(this._currentChime()) + step + chimes.length) % chimes.length;
      setChime(chimes[index]);
      opts.segmented.querySelectorAll(".option")[index]?.focus();
    });
    opts.keep.addEventListener("click", () => {
      this._prefs.keepVolume = !this._prefs.keepVolume;
      writeStore({ keepVolume: this._prefs.keepVolume });
      this._renderOptions();
      this._renderVolume();
    });
    opts.review.addEventListener("click", () => {
      this._prefs.review = !this._reviewOn();
      writeStore({ review: this._prefs.review });
      this._renderOptions();
    });
    const pickFile = () => el.file.click();
    opts.upload.addEventListener("click", pickFile);
    el.uploadFeature.addEventListener("click", pickFile);
    el.file.addEventListener("change", () => {
      const file = el.file.files?.[0];
      el.file.value = "";
      if (!file) return;
      if (el.dialog.open) el.dialog.close();
      this._send(file);
    });

    const openIntercom = (ev) => {
      const tile = ev.target.closest(".tile");
      if (!tile) return;
      if (ev.type === "keydown") {
        if (ev.key !== "Enter" && ev.key !== " ") return;
        ev.preventDefault();
      }
      this._moreInfo(tile.dataset.id);
    };
    el.intercoms.addEventListener("click", openIntercom);
    el.intercoms.addEventListener("keydown", openIntercom);
  }

  _render() {
    if (!this._built || !this._hass) return;
    const hass = this._hass;
    const el = this._el;
    this._placeOptions();
    el.tileIcon.setAttribute("icon", this._config.icon || DEFAULT_ICON);
    for (const [button, key] of [[el.replay, "replay"], [el.settings, "settings"], [el.close, "close"], [el.closeSpeakers, "close"]]) {
      button.title = t(hass, key);
      button.setAttribute("aria-label", t(hass, key));
    }
    el.settings.hidden = this._page || this._config.show_settings === false || !this._info;
    el.dialogTitle.textContent = t(hass, "settings");
    el.optionsTitle.textContent = t(hass, "settings");
    el.areaStrip.setAttribute("aria-label", t(hass, "speakers"));
    el.badges.setAttribute("aria-label", t(hass, "speakers"));
    el.speakersSearchLabel.textContent = t(hass, "filter_speakers");
    el.speakersSearch.placeholder = t(hass, "filter_speakers");
    el.play.querySelector("span").textContent = t(hass, this._audio ? "stop" : "play");
    el.discard.querySelector("span").textContent = t(hass, "discard");
    el.send.querySelector("span").textContent = t(hass, "send");
    el.ttsLabel.textContent = t(hass, "tts_label");
    el.ttsInput.placeholder = t(hass, "tts_placeholder");
    el.ttsSend.querySelector("span").textContent = t(hass, "send");
    el.uploadFeature.querySelector("span").textContent = t(hass, "upload");
    el.volumeLabel.textContent = t(hass, "volume");
    el.volume.title = t(hass, "volume_helper");
    this._renderHeader();
    this._renderAlert();
    this._renderBadges();
    this._renderRec();
    this._renderVolume();
    this._renderOptions();
    this._renderIntercoms();
  }

  _renderHeader() {
    if (!this._built || !this._hass) return;
    const el = this._el;
    const targets = this._targets();
    el.primary.textContent = this._config.title || t(this._hass, "title");
    let secondary = "";
    if (this._info === undefined) secondary = t(this._hass, "loading");
    else if (this._info && this._speakers().length) {
      secondary = targets.length ? this._names(targets) : t(this._hass, "no_selection");
      // A card named after its only speaker shows the speaker's state instead, like a tile card
      const title = (this._config.title || "").trim().toLowerCase();
      const stateObj = targets.length === 1 ? this._hass.states[targets[0]] : undefined;
      if (stateObj && title && title === secondary.toLowerCase()) {
        secondary = this._hass.formatEntityState?.(stateObj) ?? stateObj.state;
      }
    }
    el.secondary.textContent = secondary;
    const clickable = targets.length === 1 && !this._preview;
    el.tile.classList.toggle("clickable", clickable);
    if (clickable) {
      el.tile.setAttribute("role", "button");
      el.tile.setAttribute("tabindex", "0");
    } else {
      el.tile.removeAttribute("role");
      el.tile.removeAttribute("tabindex");
    }
    const textMode = this._isTextMode();
    const showModeToggle = Boolean(this._info && this._speakers().length && this._ttsAvailable() && !this._loadError);
    el.modeToggle.hidden = !showModeToggle;
    el.modeToggle.disabled = this._rec !== "idle";
    const modeLabel = t(this._hass, textMode ? "mode_voice" : "mode_text");
    el.modeToggle.title = modeLabel;
    el.modeToggle.setAttribute("aria-label", modeLabel);
    el.modeToggleIcon.setAttribute("icon", textMode ? "mdi:microphone" : "mdi:keyboard-outline");
    el.replay.hidden = !this._info?.last;
    el.replay.disabled = this._rec !== "idle";
  }

  _renderAlert() {
    const el = this._el;
    let kind;
    let text;
    if (this._loadError) {
      kind = "error";
      text = this._loadError === "not_set_up" ? t(this._hass, "err_not_set_up") : this._loadError;
    } else if (this._info && !this._speakers().length) {
      kind = "warning";
      text = t(this._hass, "err_no_speakers");
    } else if (this._info && this._capturePath() === "none" && !this._isTextMode() && !this._preview) {
      kind = "info";
      text = t(this._hass, "err_insecure");
      if (this._hass?.auth?.external && !this._info.intercom?.ready) text += t(this._hass, "err_insecure_app");
    }
    const key = kind ? `${kind}|${text}` : "";
    if (key === this._alertKey) return;
    this._alertKey = key;
    if (!kind) {
      el.alert.innerHTML = "";
    } else if (customElements.get("ha-alert")) {
      el.alert.innerHTML = `<ha-alert alert-type="${kind}">${escapeHtml(text)}</ha-alert>`;
    } else {
      const icon = { info: "mdi:information-outline", warning: "mdi:alert-outline", error: "mdi:alert-circle-outline" }[kind];
      el.alert.innerHTML = `<div class="alert ${kind}" role="alert"><ha-icon icon="${icon}"></ha-icon><div class="text">${escapeHtml(text)}</div></div>`;
    }
  }

  _isCompactPicker(speakers) {
    if (speakers.length <= 1) return false;
    const style = this._config.speaker_style || "auto";
    if (style === "compact") return true;
    if (style === "chips") return false;
    return speakers.length > COMPACT_THRESHOLD;
  }

  _makeSpeakerBadge(speaker) {
    const badge = document.createElement("button");
    badge.type = "button";
    badge.className = "badge";
    badge.setAttribute("role", "checkbox");
    badge.dataset.id = speaker.entity_id;
    badge.innerHTML = "<ha-icon></ha-icon><span></span>";
    badge.querySelector("span").textContent = speaker.name;
    this._badges.set(speaker.entity_id, { badge, speaker });
    return badge;
  }

  _makeAreaChip(id, name, icon, area) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "area-chip";
    chip.setAttribute("role", "checkbox");
    if (id === "*") chip.dataset.id = "*";
    else chip.dataset.area = id;
    chip.innerHTML = '<ha-icon></ha-icon><span class="name"></span><span class="count"></span>';
    chip.querySelector("ha-icon").setAttribute("icon", icon);
    chip.querySelector(".name").textContent = name;
    this._areaControls.set(id, { button: chip, count: chip.querySelector(".count"), area });
    return chip;
  }

  _renderBadges() {
    const el = this._el;
    const hass = this._hass;
    const speakers = this._speakers();
    const compact = this._isCompactPicker(speakers);
    const { areas } = groupSpeakersByArea(speakers);
    const stripAreas = compact
      ? areas.filter((a) => a.speakers.length < speakers.length)
      : quickAreas(speakers);
    const showAreaStrip = speakers.length > 1 && (compact || stripAreas.length > 0);
    // Rebuild only when the speaker list or layout changes, otherwise patch in-place so focus and scroll survive
    const key = `${compact}|${showAreaStrip}|${languageOf(hass)}|${speakers
      .map((s) => `${s.entity_id}:${s.name}:${s.group}:${s.area_id || s.area || ""}:${s.area_icon || ""}`)
      .join(",")}`;
    if (key !== this._badgeKey) {
      this._badgeKey = key;
      this._badges.clear();
      this._areaControls.clear();
      el.areaStrip.textContent = "";
      el.badges.textContent = "";
      if (showAreaStrip) {
        el.areaStrip.appendChild(
          this._makeAreaChip("*", t(hass, "all"), "mdi:checkbox-multiple-marked-outline", { speakers })
        );
        for (const area of stripAreas) {
          el.areaStrip.appendChild(this._makeAreaChip(area.key, area.name, area.icon, area));
        }
      }
      if (!compact) {
        if (speakers.length > 1 && !showAreaStrip) {
          el.badges.appendChild(this._makeSpeakerBadge({ entity_id: "*", name: t(hass, "all"), all: true }));
        }
        for (const speaker of speakers) el.badges.appendChild(this._makeSpeakerBadge(speaker));
      }
    }

    el.picker.hidden = !speakers.length;
    el.areaStrip.hidden = !showAreaStrip;
    el.badges.hidden = compact || !speakers.length;
    el.pickerRow.hidden = !compact;

    const selected = this._selected || new Set();
    const selectable = speakers.filter((s) => this._selectable(s));
    const chosen = selectable.filter((s) => selected.has(s.entity_id));

    for (const { button, count, area } of this._areaControls.values()) {
      const areaSelectable = area.speakers.filter((s) => this._selectable(s));
      const areaSelected = areaSelectable.filter((s) => selected.has(s.entity_id));
      const state =
        areaSelectable.length > 0 && areaSelected.length === areaSelectable.length
          ? "true"
          : areaSelected.length > 0
            ? "mixed"
            : "false";
      button.setAttribute("aria-checked", state);
      button.disabled = !areaSelectable.length;
      count.textContent = `${areaSelected.length}/${areaSelectable.length}`;
    }

    if (compact) {
      el.pickerMain.textContent = formatSpeakerSummary(
        hass,
        chosen.map((s) => s.name)
      );
      el.pickerCount.textContent = `${chosen.length}/${selectable.length}`;
    }

    for (const { badge, speaker } of this._badges.values()) {
      if (speaker.all) {
        const allOn = selectable.length > 0 && selectable.every((s) => selected.has(s.entity_id));
        badge.setAttribute("aria-checked", String(allOn));
        badge.disabled = !selectable.length;
        badge.querySelector("ha-icon").setAttribute("icon", "mdi:checkbox-multiple-marked-outline");
        continue;
      }
      const avail = this._available(speaker);
      const quietSkip = avail && this._quietSkipped(speaker);
      const on = avail && !quietSkip;
      badge.classList.toggle("quiet-skip", quietSkip);
      badge.setAttribute("aria-checked", String(on && selected.has(speaker.entity_id)));
      badge.disabled = !on;
      badge
        .querySelector("ha-icon")
        .setAttribute(
          "icon",
          !avail ? "mdi:speaker-off" : quietSkip ? "mdi:weather-night" : speaker.group ? "mdi:speaker-multiple" : "mdi:speaker"
        );
      badge.title = [
        speaker.area,
        speaker.group ? t(hass, "group") : null,
        !avail ? t(hass, "unavailable") : quietSkip ? t(hass, "quiet_skipped") : null,
      ]
        .filter(Boolean)
        .join(" · ");
    }

    if (el.speakersDialog.open) this._renderSpeakersDialog();
  }

  _makeDialogRow(speaker) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "list-item";
    row.setAttribute("role", "checkbox");
    row.dataset.id = speaker.entity_id;
    row.innerHTML =
      '<ha-icon></ha-icon><span class="sp-meta"><span class="sp-name"></span><span class="sp-sub" hidden></span></span>' +
      '<span class="chk"><ha-icon icon="mdi:check"></ha-icon></span>';
    row.querySelector(".sp-name").textContent = speaker.name;
    this._dialogRows.set(speaker.entity_id, {
      row,
      icon: row.querySelector(":scope > ha-icon"),
      sub: row.querySelector(".sp-sub"),
      speaker,
    });
    return row;
  }

  _renderSpeakersDialog() {
    const el = this._el;
    const hass = this._hass;
    const speakers = this._speakers();
    const { areas, ungrouped } = groupSpeakersByArea(speakers);
    const key = `${languageOf(hass)}|${speakers
      .map((s) => `${s.entity_id}:${s.name}:${s.group}:${s.area_id || s.area || ""}:${s.area_icon || ""}`)
      .join(",")}`;
    if (key !== this._dialogKey) {
      this._dialogKey = key;
      this._dialogRows.clear();
      this._dialogAreas.clear();
      el.speakersList.textContent = "";
      for (const area of areas) {
        const section = document.createElement("div");
        section.className = "dialog-area-section";
        const head = document.createElement("button");
        head.type = "button";
        head.className = "list-area-head";
        head.dataset.area = area.key;
        head.innerHTML = '<ha-icon></ha-icon><span class="a-name"></span><span class="a-act"></span>';
        head.querySelector("ha-icon").setAttribute("icon", area.icon);
        head.querySelector(".a-name").textContent = area.name;
        section.appendChild(head);
        for (const speaker of area.speakers) section.appendChild(this._makeDialogRow(speaker));
        this._dialogAreas.set(area.key, { section, head, act: head.querySelector(".a-act"), area });
        el.speakersList.appendChild(section);
      }
      if (ungrouped.length) {
        const section = document.createElement("div");
        section.className = "dialog-area-section";
        if (areas.length) {
          const head = document.createElement("div");
          head.className = "list-area-head";
          head.innerHTML = '<ha-icon icon="mdi:speaker-multiple"></ha-icon><span class="a-name"></span>';
          head.querySelector(".a-name").textContent = t(hass, "other_area");
          section.appendChild(head);
        }
        for (const speaker of ungrouped) section.appendChild(this._makeDialogRow(speaker));
        this._dialogAreas.set("__other__", { section, head: null, act: null, area: { name: "", speakers: ungrouped } });
        el.speakersList.appendChild(section);
      }
      const empty = document.createElement("div");
      empty.className = "speakers-empty";
      empty.hidden = true;
      empty.textContent = t(hass, "no_matches");
      el.speakersList.appendChild(empty);
      this._dialogEmpty = empty;
    }

    el.sheetSearch.hidden = speakers.length <= COMPACT_THRESHOLD;
    const selected = this._selected || new Set();
    const selectable = speakers.filter((s) => this._selectable(s));
    const chosen = selectable.filter((s) => selected.has(s.entity_id));
    el.speakersDialogTitle.textContent = `${t(hass, "speakers")} (${chosen.length}/${selectable.length})`;

    for (const { act, head, area } of this._dialogAreas.values()) {
      if (!head || !act) continue;
      const av = area.speakers.filter((s) => this._selectable(s));
      const allOn = av.length > 0 && av.every((s) => selected.has(s.entity_id));
      head.disabled = !av.length;
      act.textContent = !av.length ? "" : t(hass, allOn ? "deselect_all" : "all");
    }

    for (const { row, icon, sub, speaker } of this._dialogRows.values()) {
      const avail = this._available(speaker);
      const quietSkip = avail && this._quietSkipped(speaker);
      const on = avail && !quietSkip;
      row.setAttribute("aria-checked", String(on && selected.has(speaker.entity_id)));
      row.disabled = !on;
      icon.setAttribute(
        "icon",
        !avail ? "mdi:speaker-off" : quietSkip ? "mdi:weather-night" : speaker.group ? "mdi:speaker-multiple" : "mdi:speaker"
      );
      const note = !avail ? t(hass, "unavailable") : quietSkip ? t(hass, "quiet_skipped") : "";
      sub.textContent = note;
      sub.hidden = !note;
    }

    this._filterSpeakersDialog();
  }

  _filterSpeakersDialog() {
    const query = (this._speakerQuery || "").trim().toLowerCase();
    let visibleCount = 0;
    for (const { section, area } of this._dialogAreas.values()) {
      let areaVisible = 0;
      const areaMatch = query && (area.name || "").toLowerCase().includes(query);
      for (const speaker of area.speakers) {
        const entry = this._dialogRows.get(speaker.entity_id);
        if (!entry) continue;
        const match = !query || areaMatch || speaker.name.toLowerCase().includes(query);
        entry.row.hidden = !match;
        if (match) areaVisible++;
      }
      section.hidden = areaVisible === 0;
      visibleCount += areaVisible;
    }
    if (this._dialogEmpty) this._dialogEmpty.hidden = visibleCount > 0;
  }

  _renderRec() {
    if (!this._built || !this._hass) return;
    const el = this._el;
    const rec = this._rec;
    const hass = this._hass;
    const textMode = this._isTextMode();
    const noTargets = this._targets().length === 0;
    const blocked = !this._info || (this._capturePath() === "none" && !this._preview);
    el.talk.classList.toggle("text-mode", textMode);
    el.mic.hidden = textMode;
    el.ttsForm.hidden = !textMode;
    el.ttsInput.disabled = rec !== "idle" || noTargets;
    el.ttsSend.disabled = rec !== "idle" || noTargets;
    el.mic.className = `mic ${rec}`;
    el.mic.disabled = rec === "sending" || rec === "review" || (rec === "idle" && (noTargets || blocked));
    el.mic.setAttribute("aria-pressed", String(rec === "recording"));
    el.mic.setAttribute("aria-label", t(hass, rec === "recording" ? "stop_send" : "talk"));
    const busy = rec === "sending" || rec === "preparing";
    el.micIcon.hidden = busy;
    if (busy && !el.mic.querySelector(".spinner")) el.mic.insertAdjacentHTML("beforeend", '<span class="spinner"></span>');
    if (!busy) el.mic.querySelector(".spinner")?.remove();
    el.micIcon.setAttribute("icon", rec === "recording" ? "mdi:stop" : "mdi:microphone");
    el.review.hidden = rec !== "review";
    el.uploadFeature.hidden = !(this._info && !textMode && this._capturePath() === "none" && this._speakers().length && !this._preview);
    el.uploadFeature.disabled = rec !== "idle" || noTargets;
    if (this._options) this._options.upload.disabled = rec !== "idle" || noTargets;
    el.replay.disabled = rec !== "idle";
    el.modeToggle.disabled = rec !== "idle";
    // Nothing to talk to, or no microphone here (and not in text mode): the alert explains why
    this._el.talk.hidden =
      Boolean(this._loadError) ||
      (this._info !== undefined && !this._speakers().length) ||
      (Boolean(this._info) && !textMode && this._capturePath() === "none" && !this._preview);
    this._renderHint();
  }

  _renderHint() {
    const el = this._el;
    const hass = this._hass;
    const rec = this._rec;
    const textMode = this._isTextMode();
    let text = "";
    let success = false;
    if (this._successText && rec === "idle") {
      text = this._successText;
      success = true;
    } else if (rec === "idle") {
      if (this._info && this._speakers().length) {
        if (!this._targets().length) text = t(hass, "hint_choose");
        else if (!textMode && (this._preview || this._capturePath() !== "none")) text = t(hass, "hint_idle");
      }
    } else if (rec === "preparing") {
      text = t(hass, "hint_preparing");
    } else if (rec === "recording") {
      const key = this._capture?.kind === "app" || this._recMode === "toggle" ? "hint_toggle" : "hint_hold";
      text = t(hass, key, { time: formatClock(hass, this._elapsed()) });
    } else if (rec === "review") {
      text = t(hass, "hint_review", { time: formatClock(hass, this._pending?.duration || 0) });
    } else if (rec === "sending") {
      text = t(hass, "hint_sending");
    }
    el.hint.hidden = textMode && !text;
    el.hint.classList.toggle("success", success);
    el.hintIcon.hidden = !success;
    if (el.hintText.textContent !== text) el.hintText.textContent = text;
  }

  _renderVolume() {
    const el = this._el;
    const hass = this._hass;
    const keep = Boolean(this._prefs.keepVolume);
    const volume = this._prefs.volume ?? 60;
    const quiet = this._info?.quiet;
    const quietActive = this._isQuietActive();
    const isCap = quietActive && quiet?.mode === "cap_volume";
    const cap = quiet?.volume ?? 25;
    const selectedTargets = this._targets();
    const allSelectedCapped =
      isCap && (!quiet.speakers?.length || (selectedTargets.length > 0 && selectedTargets.every((id) => quiet.speakers.includes(id))));
    const displayVolume = !keep && allSelectedCapped ? Math.min(volume, cap) : volume;

    el.volume.hidden = this._config.show_volume === false || !this._info || !this._speakers().length;
    el.range.value = String(volume);
    el.range.disabled = keep;
    el.range.setAttribute("aria-valuetext", keep ? t(hass, "volume_keep") : formatPercent(hass, displayVolume));
    el.slider.classList.toggle("off", keep);
    el.slider.style.setProperty("--fill", `${displayVolume}%`);
    el.capMark.hidden = !(isCap && !keep);
    if (isCap) el.capMark.style.setProperty("--cap", `${cap}%`);
    el.sliderLabel.textContent = keep ? t(hass, "volume_keep") : "";
    el.value.textContent = keep ? "" : formatPercent(hass, displayVolume);
    el.value.hidden = keep;
    el.volumeIcon.setAttribute(
      "icon",
      keep ? "mdi:volume-equal" : displayVolume < 35 ? "mdi:volume-low" : displayVolume < 70 ? "mdi:volume-medium" : "mdi:volume-high"
    );

    if (quietActive) {
      let pill = "";
      if (isCap) {
        pill = t(hass, "quiet_cap", { volume: formatPercent(hass, cap) });
      } else {
        const skipped = this._speakers().filter((s) => this._quietSkipped(s));
        pill =
          skipped.length > 0 && skipped.length <= 2
            ? t(hass, "quiet_skip_pill", { targets: skipped.map((s) => s.name).join(", ") })
            : t(hass, "quiet_hours");
      }
      el.quietPillText.textContent = pill;
      el.quietPill.title = `${t(hass, "quiet_hours")} (${quiet.start}-${quiet.end})`;
      el.quietPill.hidden = false;
    } else {
      el.quietPill.hidden = true;
    }
  }

  _renderOptions() {
    const opts = this._options;
    const hass = this._hass;
    if (!opts || !hass) return;
    const chimes = this._availableChimes();
    const chimeKey = chimes.join(",");
    if (chimeKey !== this._chimeKey) {
      this._chimeKey = chimeKey;
      opts.segmented.innerHTML = chimes
        .map((c) => `<button class="option" type="button" role="radio" data-chime="${c}"><span></span></button>`)
        .join("");
    }
    const current = this._currentChime();
    opts.chimeLabel.textContent = t(hass, "chime");
    const playingChime = Boolean(this._chimePreview);
    const previewDisabled = current === "none";
    const previewLabel = t(hass, playingChime ? "stop" : "chime_preview");
    opts.chimePreview.setAttribute("aria-label", previewLabel);
    opts.chimePreview.title = previewLabel;
    opts.chimePreview.setAttribute("aria-disabled", String(previewDisabled));
    opts.chimePreview.classList.toggle("playing", playingChime);
    opts.chimePreviewIcon.setAttribute("icon", playingChime ? "mdi:stop" : "mdi:play");
    for (const button of opts.segmented.querySelectorAll(".option")) {
      const on = button.dataset.chime === current;
      button.querySelector("span").textContent = t(hass, `chime_${button.dataset.chime}`);
      button.setAttribute("aria-checked", String(on));
      button.tabIndex = on ? 0 : -1;
    }
    opts.keepLabel.textContent = t(hass, "keep_volume");
    opts.keepHelper.textContent = t(hass, "keep_volume_helper");
    opts.keep.setAttribute("aria-checked", String(Boolean(this._prefs.keepVolume)));
    opts.reviewLabel.textContent = t(hass, "review");
    opts.review.setAttribute("aria-checked", String(this._reviewOn()));
    opts.upload.querySelector("span").textContent = t(hass, "upload");
    this._el.optionsSection.hidden = !this._page || !this._info || !this._speakers().length;
  }

  _renderIntercoms() {
    const el = this._el;
    const hass = this._hass;
    const intercoms = this._page ? this._intercoms() : [];
    el.intercomSection.hidden = !intercoms.length;
    if (!intercoms.length) return;
    el.intercomTitle.textContent = t(hass, "intercom");
    el.intercomNote.textContent = t(hass, "intercom_helper") + (this._info?.intercom?.labs === false ? ` ${t(hass, "intercom_labs")}` : "");
    const html = intercoms
      .map((entry) => {
        const name = hass.states[entry.entity_id]?.attributes.friendly_name || entry.entity_id;
        const icon = entry.translation_key === "intercom_all" ? "mdi:bullhorn" : "mdi:account-voice";
        return (
          `<div class="tile clickable" role="button" tabindex="0" data-id="${escapeHtml(entry.entity_id)}">` +
          `<div class="tile-icon"><ha-icon icon="${icon}"></ha-icon></div>` +
          `<div class="tile-info"><span class="primary">${escapeHtml(name)}</span>` +
          `<span class="secondary">${escapeHtml(t(hass, "open_intercom"))}</span></div></div>`
        );
      })
      .join("");
    if (html !== this._intercomHtml) {
      this._intercomHtml = html;
      el.intercoms.innerHTML = html;
    }
  }

  _setRec(state) {
    this._rec = state;
    if (state !== "idle") this._clearSuccess();
    if (state !== "recording") this.style.setProperty("--level", "0");
    this._renderRec();
    this._renderHeader();
  }

  _success(text) {
    clearTimeout(this._successTimer);
    this._successText = text;
    this._renderHint();
    this._successTimer = setTimeout(() => this._clearSuccess(), SUCCESS_MS);
  }

  _clearSuccess() {
    clearTimeout(this._successTimer);
    if (this._successText === undefined) return;
    this._successText = undefined;
    if (this._built) this._renderHint();
  }

  _toast(message) {
    this.dispatchEvent(new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true }));
  }

  _moreInfo(entityId) {
    if (!entityId || this._preview) return;
    this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId }, bubbles: true, composed: true }));
  }

  _openSpeakerInfo() {
    const targets = this._targets();
    if (targets.length === 1) this._moreInfo(targets[0]);
  }

  _toggleMode() {
    if (!this._ttsAvailable() || this._rec !== "idle" || this._preview) return;
    const next = this._isTextMode() ? "voice" : "text";
    this._prefs.mode = next;
    writeStore({ mode: next });
    this._renderHeader();
    this._renderAlert();
    this._renderRec();
    if (next === "text") this._el.ttsInput.focus();
  }

  _toggleArea(areaKey) {
    if (!this._selected || this._preview) return;
    const entry = this._areaControls.get(areaKey) || this._dialogAreas.get(areaKey);
    if (!entry) return;
    const selectable = entry.area.speakers.filter((s) => this._selectable(s)).map((s) => s.entity_id);
    if (!selectable.length) return;
    const allOn = selectable.every((id) => this._selected.has(id));
    for (const id of selectable) {
      if (allOn) this._selected.delete(id);
      else this._selected.add(id);
    }
    writeStore({ targets: [...this._selected] });
    this._renderBadges();
    this._renderHeader();
    this._renderRec();
    this._renderVolume();
  }

  _toggleSpeaker(id) {
    if (!this._selected || this._preview) return;
    if (id === "*") {
      const selectable = this._speakers().filter((s) => this._selectable(s)).map((s) => s.entity_id);
      const allOn = selectable.every((s) => this._selected.has(s));
      this._selected = new Set(allOn ? [] : selectable);
    } else if (this._selected.has(id)) {
      this._selected.delete(id);
    } else {
      this._selected.add(id);
    }
    writeStore({ targets: [...this._selected] });
    this._renderBadges();
    this._renderHeader();
    this._renderRec();
    this._renderVolume();
  }

  // Talk button: hold to talk, or tap to start and tap again to send

  _micDown(ev) {
    if ((ev.button !== undefined && ev.button !== 0) || this._el.mic.disabled) return;
    ev.preventDefault();
    try {
      this._el.mic.setPointerCapture(ev.pointerId);
    } catch (_err) {
      // not supported
    }
    this._pressedAt = performance.now();
    if (this._rec === "idle") {
      this._recMode = "hold";
      this._begin();
    } else if (this._rec === "recording" && this._recMode === "toggle") {
      this._finishOnRelease = true;
    }
  }

  _micUp(ev) {
    if (this._pressedAt === undefined) return;
    const held = performance.now() - this._pressedAt;
    this._pressedAt = undefined;
    if (ev.type === "pointercancel" && this._rec !== "recording" && this._rec !== "preparing") return;
    if (this._finishOnRelease) {
      this._finishOnRelease = false;
      this._finish();
      return;
    }
    if (this._recMode !== "hold") return;
    if (held < HOLD_MS) {
      this._recMode = "toggle"; // a tap keeps recording until the next tap
      this._renderHint();
    } else if (this._rec === "preparing") {
      this._finishWhenReady = true;
    } else if (this._rec === "recording") {
      this._finish();
    }
  }

  _elapsed() {
    return this._capture ? (performance.now() - this._capture.startedAt) / 1000 : 0;
  }

  async _begin() {
    const targets = this._targets();
    if (!targets.length || this._preview) return;
    const path = this._capturePath();
    if (path === "none") return;
    this._finishWhenReady = false;
    this._setRec("preparing");
    window.addEventListener("keydown", this._onKey);
    try {
      if (path === "app") await this._beginApp(targets);
      else await this._beginBrowser();
    } catch (err) {
      window.removeEventListener("keydown", this._onKey);
      this._cleanupCapture();
      this._setRec("idle");
      this._showError(err);
      return;
    }
    if (this._rec !== "preparing") {
      this._cleanupCapture(); // cancelled while the microphone was opening
      return;
    }
    this._setRec("recording");
    this._startTimer();
    if (this._finishWhenReady) this._finish();
  }

  async _beginBrowser() {
    const enhance = this._info?.defaults?.voice_enhancement !== false;
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: enhance,
        noiseSuppression: enhance,
        autoGainControl: enhance,
        channelCount: 1,
      },
    });
    const mimeType = pickMimeType();
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType, audioBitsPerSecond: 64000 } : undefined);
    const chunks = [];
    recorder.addEventListener("dataavailable", (ev) => {
      if (ev.data?.size) chunks.push(ev.data);
    });
    const capture = { kind: "browser", stream, recorder, chunks, mimeType: recorder.mimeType || mimeType, startedAt: performance.now() };
    this._capture = capture;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const context = new AudioCtx();
      const analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      context.createMediaStreamSource(stream).connect(analyser);
      capture.context = context;
      const data = new Float32Array(analyser.fftSize);
      const tick = () => {
        if (this._capture !== capture) return;
        analyser.getFloatTimeDomainData(data);
        let sum = 0;
        for (const v of data) sum += v * v;
        // A CSS variable, so the level never re-renders the card
        this.style.setProperty("--level", Math.min(1, Math.sqrt(Math.sqrt(sum / data.length)) * 1.6).toFixed(2));
        capture.frame = requestAnimationFrame(tick);
      };
      capture.frame = requestAnimationFrame(tick);
    } catch (_err) {
      // The level meter is only decoration
    }
    recorder.start(250);
    capture.startedAt = performance.now();
  }

  async _beginApp(targets) {
    const external = this._hass.auth.external;
    const volume = this._volumeValue();
    const route = await this._hass.callWS({
      type: `${DOMAIN}/route`,
      targets,
      volume: volume === "keep" ? "keep" : Number(volume),
      chime: this._currentChime(),
    });
    const capture = { kind: "app", startedAt: performance.now() };
    this._capture = capture;
    let reply;
    try {
      reply = await external.sendMessage({
        type: "webrtc/stream/start",
        payload: { stream_type: "microphone", entity_id: route.entity_id },
      });
    } catch (err) {
      throw new AnnounceError(err?.code === "microphone_denied" ? "mic_denied" : "app", err?.message || err?.code);
    }
    capture.sessionId = reply?.session_id;
    capture.onStopped = (ev) => {
      if (ev.detail?.session_id !== capture.sessionId || this._capture !== capture) return;
      this._cleanupCapture();
      this._setRec("idle");
      this._showError(new AnnounceError(ev.detail.code === "microphone_denied" ? "mic_denied" : "app", ev.detail.message || ev.detail.code));
    };
    window.addEventListener("webrtc-stream-stopped", capture.onStopped);
    capture.startedAt = performance.now();
  }

  _startTimer() {
    clearInterval(this._timer);
    const capture = this._capture;
    const max = this._info?.defaults?.max_duration || 60;
    const tick = () => {
      if (this._capture !== capture || this._rec !== "recording") {
        clearInterval(this._timer);
        return;
      }
      this._renderHint();
      if (this._elapsed() >= max) this._finish();
    };
    tick();
    this._timer = setInterval(tick, 250);
  }

  async _finish() {
    if (this._rec === "preparing") {
      this._finishWhenReady = true;
      return;
    }
    if (this._rec !== "recording" || !this._capture) return;
    clearInterval(this._timer);
    window.removeEventListener("keydown", this._onKey);
    const capture = this._capture;
    const seconds = this._elapsed();

    if (capture.kind === "app") {
      this._hass.auth.external.fireMessage({ type: "webrtc/stream/stop", payload: { session_id: capture.sessionId } });
      this._cleanupCapture();
      if (seconds < MIN_SECONDS) {
        this._setRec("idle");
        this._toast(t(this._hass, "err_too_short"));
        return;
      }
      this._setRec("sending");
      // The integration announces the message when the app closes the stream
      this._waitingIntercom = setTimeout(() => {
        this._waitingIntercom = undefined;
        this._setRec("idle");
        this._success(t(this._hass, "sent_intercom"));
      }, 12000);
      return;
    }

    this._setRec("sending");
    await new Promise((resolve) => {
      capture.recorder.addEventListener("stop", resolve, { once: true });
      try {
        capture.recorder.requestData?.();
        capture.recorder.stop();
      } catch (_err) {
        resolve();
      }
    });
    const blob = new Blob(capture.chunks, { type: capture.mimeType || "audio/webm" });
    this._cleanupCapture();
    if (seconds < MIN_SECONDS || blob.size === 0) {
      this._setRec("idle");
      this._toast(t(this._hass, "err_too_short"));
      return;
    }
    if (this._reviewOn()) {
      this._pending = { blob, url: URL.createObjectURL(blob), duration: seconds };
      this._setRec("review");
      this._el.send.focus();
      return;
    }
    await this._send(blob);
  }

  _cancel() {
    clearInterval(this._timer);
    window.removeEventListener("keydown", this._onKey);
    const capture = this._capture;
    if (capture?.kind === "app" && capture.sessionId) {
      this._hass?.auth?.external?.fireMessage({ type: "webrtc/stream/stop", payload: { session_id: capture.sessionId } });
    }
    if (capture?.kind === "browser") {
      try {
        capture.recorder.stop();
      } catch (_err) {
        // already stopped
      }
    }
    this._cleanupCapture();
    this._discard();
    if (this._rec === "recording" || this._rec === "preparing") this._setRec("idle");
  }

  _cleanupCapture() {
    const capture = this._capture;
    this._capture = undefined;
    if (!capture) return;
    if (capture.frame) cancelAnimationFrame(capture.frame);
    capture.stream?.getTracks().forEach((track) => track.stop());
    capture.context?.close?.().catch(() => undefined);
    if (capture.onStopped) window.removeEventListener("webrtc-stream-stopped", capture.onStopped);
    this.style.setProperty("--level", "0");
  }

  // Listen before sending

  _togglePreview() {
    if (!this._pending) return;
    if (this._audio) {
      this._audio.pause();
      this._audio = undefined;
      this._renderPlay(false);
      return;
    }
    const audio = new Audio(this._pending.url);
    this._audio = audio;
    audio.addEventListener("ended", () => {
      if (this._audio === audio) {
        this._audio = undefined;
        this._renderPlay(false);
      }
    });
    audio.play().catch(() => {
      this._audio = undefined;
      this._renderPlay(false);
    });
    this._renderPlay(true);
  }

  _renderPlay(playing) {
    if (!this._built) return;
    this._el.play.querySelector("ha-icon").setAttribute("icon", playing ? "mdi:stop" : "mdi:play");
    this._el.play.querySelector("span").textContent = t(this._hass, playing ? "stop" : "play");
  }

  _toggleChimePreview() {
    if (this._chimePreview) {
      this._stopChimePreview();
      return;
    }
    const chime = this._currentChime();
    if (chime === "none") return;
    if (chime === "custom") {
      this._playCustomChimePreview();
      return;
    }
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    try {
      const ctx = new AudioCtx();
      const samples = renderChimeSamples(chime, ctx.sampleRate);
      if (!samples) {
        ctx.close?.().catch(() => undefined);
        return;
      }
      const buffer = ctx.createBuffer(1, samples.length, ctx.sampleRate);
      buffer.getChannelData(0).set(samples);
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(ctx.destination);
      const preview = { ctx, source };
      this._chimePreview = preview;
      source.addEventListener("ended", () => {
        if (this._chimePreview === preview) this._stopChimePreview();
      });
      ctx.resume?.().catch(() => undefined);
      source.start();
      this._renderOptions();
    } catch (_err) {
      this._stopChimePreview();
    }
  }

  async _playCustomChimePreview() {
    const controller = new AbortController();
    const preview = { controller };
    this._chimePreview = preview;
    this._renderOptions();
    try {
      const response = await this._hass.fetchWithAuth(CHIME_URL, { signal: controller.signal });
      if (!response.ok || this._chimePreview !== preview) {
        if (this._chimePreview === preview) this._stopChimePreview();
        return;
      }
      const blob = await response.blob();
      if (this._chimePreview !== preview) return;
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      preview.url = url;
      preview.audio = audio;
      const done = () => {
        if (this._chimePreview === preview) this._stopChimePreview();
      };
      audio.addEventListener("ended", done, { once: true });
      audio.addEventListener("error", done, { once: true });
      await audio.play();
    } catch (_err) {
      if (this._chimePreview === preview) this._stopChimePreview();
    }
  }

  _stopChimePreview() {
    const preview = this._chimePreview;
    this._chimePreview = undefined;
    if (!preview) return;
    preview.controller?.abort();
    if (preview.audio) {
      preview.audio.pause();
      preview.audio.src = "";
    }
    if (preview.url) URL.revokeObjectURL(preview.url);
    try {
      preview.source?.stop();
    } catch (_err) {
      // already stopped
    }
    preview.ctx?.close?.().catch(() => undefined);
    if (this._built && this._hass) this._renderOptions();
  }

  _discard() {
    this._audio?.pause();
    this._audio = undefined;
    if (this._pending) URL.revokeObjectURL(this._pending.url);
    this._pending = undefined;
    if (this._rec === "review") this._setRec("idle");
    this._renderPlay(false);
  }

  async _sendPending() {
    const pending = this._pending;
    if (!pending) return;
    this._audio?.pause();
    this._audio = undefined;
    this._pending = undefined;
    URL.revokeObjectURL(pending.url);
    this._renderPlay(false);
    await this._send(pending.blob);
  }

  // Sending

  async _send(blob) {
    const targets = this._targets();
    if (!targets.length) {
      this._setRec("idle");
      return;
    }
    this._setRec("sending");
    const form = new FormData();
    const type = blob.type || "audio/webm";
    form.append("audio", blob, blob.name || `message.${fileExtension(type)}`);
    form.append("targets", JSON.stringify(targets));
    form.append("volume", this._volumeValue());
    form.append("chime", this._currentChime());
    try {
      const response = await this._hass.fetchWithAuth(UPLOAD_URL, { method: "POST", body: form });
      let data = {};
      try {
        data = await response.json();
      } catch (_err) {
        // not JSON
      }
      if (!response.ok) throw new AnnounceError(data.code || String(response.status), data.message || response.statusText);
      if (this._info) this._info.last = data;
      this._setRec("idle");
      this._success(t(this._hass, "sent", { targets: this._names(data.targets) }));
    } catch (err) {
      this._setRec("idle");
      this._showError(err);
    }
  }

  async _sendText(ev) {
    ev.preventDefault();
    if (this._rec !== "idle" || this._preview) return;
    const message = this._el.ttsInput.value.trim();
    if (!message) {
      this._el.ttsInput.focus();
      return;
    }
    const targets = this._targets();
    if (!targets.length) return;
    this._setRec("sending");
    const volume = this._volumeValue();
    try {
      const data = await this._hass.callWS({
        type: `${DOMAIN}/say`,
        message,
        targets,
        volume: volume === "keep" ? "keep" : Number(volume),
        chime: this._currentChime(),
      });
      this._el.ttsInput.value = "";
      if (this._el.ttsGrow) this._el.ttsGrow.dataset.replicatedValue = "";
      if (this._info) this._info.last = data;
      this._setRec("idle");
      this._success(t(this._hass, "sent", { targets: this._names(data.targets) }));
    } catch (err) {
      this._setRec("idle");
      this._showError(err);
    }
  }

  async _replay() {
    // The integration's own action, so it shows in the logbook like any other
    const targets = this._targets();
    const volume = this._volumeValue();
    const data = volume === "keep" ? {} : { volume: Number(volume) };
    const target = targets.length ? { entity_id: targets } : undefined;
    try {
      const result = await this._hass.callService(DOMAIN, "replay", data, target, true, true);
      const used = result?.response?.targets || targets;
      this._success(t(this._hass, "replayed", { targets: this._names(used) }));
    } catch (err) {
      this._showError(err);
    }
  }

  _showError(err) {
    const name = err?.name;
    let text;
    if (name === "NotAllowedError" || name === "SecurityError" || err?.code === "mic_denied") text = t(this._hass, "err_mic_denied");
    else if (name === "NotFoundError" || name === "OverconstrainedError") text = t(this._hass, "err_mic_missing");
    else if (err?.code === "no_voice") text = t(this._hass, "err_no_voice");
    else if (err?.code === "audio_error") text = t(this._hass, "err_audio");
    else if (err?.code === "too_large" || err?.code === "413") text = t(this._hass, "err_too_large");
    else if (err?.code === "no_targets") text = t(this._hass, "err_unavailable");
    else if (err?.code === "quiet_hours") text = t(this._hass, "err_quiet_hours");
    else if (err?.code === "tts_unavailable") text = t(this._hass, "err_tts_unavailable");
    else if (err?.code === "tts_failed") text = t(this._hass, "err_tts_failed", { message: err.message });
    else if (err?.code === "app") text = t(this._hass, "err_app", { message: err.message });
    else if (err?.code === "not_set_up") text = t(this._hass, "err_not_set_up");
    else text = t(this._hass, "err_generic", { message: err?.message || String(err) });
    this._toast(text);
  }
}

/* Visual editor */

async function loadHaForm() {
  if (customElements.get("ha-form")) return;
  const helpers = await window.loadCardHelpers?.();
  const card = await helpers?.createCardElement({ type: "entities", entities: [] });
  await card?.constructor?.getConfigElement?.();
}

export class HannounceCardEditor extends Base {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._loadSpeakers();
    this._render();
  }

  connectedCallback() {
    loadHaForm()
      .then(() => customElements.whenDefined("ha-form"))
      .then(() => this._render());
  }

  async _loadSpeakers() {
    try {
      const info = await this._hass.callWS({ type: `${DOMAIN}/info` });
      this._speakerIds = info.speakers.map((s) => s.entity_id);
    } catch (_err) {
      this._speakerIds = undefined;
    }
    this._render();
  }

  _schema() {
    // Only the speakers of the integration, picked from a list: no entity id to type
    const entity = { multiple: true, filter: { domain: "media_player" } };
    if (this._speakerIds?.length) entity.include_entities = this._speakerIds;
    return [
      { name: "title", selector: { text: {} } },
      {
        type: "grid",
        name: "",
        schema: [
          { name: "icon", selector: { icon: { placeholder: DEFAULT_ICON } } },
          { name: "color", selector: { ui_color: { default_color: DEFAULT_COLOR, include_none: false, include_state: false } } },
        ],
      },
      { name: "entities", selector: { entity } },
      {
        name: "content",
        type: "expandable",
        flatten: true,
        title: t(this._hass, "editor_content"),
        schema: [
          {
            name: "speaker_style",
            selector: {
              select: {
                mode: "dropdown",
                options: [
                  { value: "auto", label: t(this._hass, "style_auto") },
                  { value: "chips", label: t(this._hass, "style_chips") },
                  { value: "compact", label: t(this._hass, "style_compact") },
                ],
              },
            },
          },
          { name: "show_volume", selector: { boolean: {} } },
          { name: "show_settings", selector: { boolean: {} } },
          { name: "review", selector: { boolean: {} } },
        ],
      },
    ];
  }

  _render() {
    if (!this._hass || !this._config || !customElements.get("ha-form")) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.addEventListener("value-changed", (ev) => {
        const config = cleanConfig({ ...ev.detail.value });
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = { ...CARD_DEFAULTS, ...this._config };
    this._form.schema = this._schema();
    this._form.computeLabel = (schema) => t(this._hass, `editor_${schema.name}`);
    this._form.computeHelper = (schema) => {
      const key = `helper_${schema.name}`;
      const text = t(this._hass, key);
      return text === key ? undefined : text;
    };
  }
}

/* Sidebar panel: the card at full page, with the options and the intercoms inline */
export class HannouncePanel extends Base {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>
        [hidden] { display: none !important; }
        :host { display: block; min-height: 100vh; background: var(--primary-background-color); color: var(--primary-text-color); font-family: var(--ha-font-family-body, Roboto, Noto, sans-serif); }
        .toolbar {
          display: flex; align-items: center; gap: 4px; height: var(--header-height, 56px); padding: 0 12px;
          background: var(--app-header-background-color, var(--primary-background-color)); color: var(--app-header-text-color, var(--primary-text-color));
          border-bottom: var(--app-header-border-bottom, 1px solid var(--divider-color, rgba(0, 0, 0, 0.12)));
          padding-top: var(--safe-area-inset-top, env(safe-area-inset-top, 0px));
        }
        .title { font-size: var(--ha-font-size-xl, 20px); font-weight: var(--ha-font-weight-normal, 400); margin-inline-start: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .menu { width: 48px; height: 48px; border-radius: 50%; border: none; background: none; color: inherit; cursor: pointer; display: flex; align-items: center; justify-content: center; --mdc-icon-size: 24px; outline: none; }
        .menu:focus-visible { box-shadow: 0 0 0 2px var(--primary-color); }
        .content { max-width: 600px; margin: 0 auto; padding: var(--ha-space-4, 16px) var(--ha-space-4, 16px) calc(var(--ha-space-6, 24px) + var(--safe-area-inset-bottom, env(safe-area-inset-bottom, 0px))); box-sizing: border-box; }
      </style>
      <div class="toolbar"><button class="menu" type="button" hidden><ha-icon icon="mdi:menu"></ha-icon></button><div class="title"></div></div>
      <div class="content"></div>
    `;
    this.shadowRoot.querySelector(".menu").addEventListener("click", () => {
      this.dispatchEvent(new CustomEvent("hass-toggle-menu", { bubbles: true, composed: true }));
    });
  }

  _ensureCard() {
    if (this._card) return;
    this._card = document.createElement(CARD_TYPE);
    this._card.setAttribute("page", "");
    this._card.setConfig({});
    this.shadowRoot.querySelector(".content").appendChild(this._card);
  }

  set hass(hass) {
    this._ensureCard();
    this._card.hass = hass;
    this.shadowRoot.querySelector(".title").textContent = t(hass, "panel_title");
    this.shadowRoot.querySelector(".menu").setAttribute("aria-label", t(hass, "menu"));
  }

  set narrow(narrow) {
    this.shadowRoot.querySelector(".menu").hidden = !narrow;
  }

  set panel(_panel) {}

  set route(_route) {}
}

/* Registration, once Home Assistant has swapped in its element registry */
if (globalThis.window?.customElements) {
  const define = () => {
    const registry = window.customElements;
    if (!registry.get(CARD_TYPE)) registry.define(CARD_TYPE, HannounceCard);
    if (!registry.get(EDITOR_TYPE)) registry.define(EDITOR_TYPE, HannounceCardEditor);
    if (!registry.get(PANEL_TYPE)) registry.define(PANEL_TYPE, HannouncePanel);
  };
  if (window.customElements.get("home-assistant") || window.customElements.get("hc-main")) {
    define();
  } else {
    Promise.race([
      window.customElements.whenDefined("home-assistant"),
      window.customElements.whenDefined("hc-main"),
      new Promise((resolve) => setTimeout(resolve, 30000)),
    ]).then(define);
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === CARD_TYPE)) {
    window.customCards.push({
      type: CARD_TYPE,
      name: "HA-nnounce",
      description: "Record your voice and play it on your speakers: Google Home, Nest, Sonos and more.",
      preview: true,
      documentationURL: "https://github.com/fabioscarparo/ha-nnounce",
    });
  }

  console.info(`%c HA-NNOUNCE %c ${VERSION} `, "color: #fff; background: #4285f4; font-weight: 500", "");
}
