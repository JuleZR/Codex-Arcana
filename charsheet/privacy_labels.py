"""Recipient-facing German labels for the generic privacy collector."""

import re


PHRASES = {
    "username": "Benutzername", "email": "E-Mail-Adresse",
    "first_name": "Vorname", "last_name": "Nachname",
    "is_active": "Aktiv", "is_staff": "Administrationszugang",
    "is_superuser": "Uneingeschränkte Administration",
    "date_joined": "Konto erstellt am", "last_login": "Letzte Anmeldung",
    "created_at": "Erstellt am", "updated_at": "Zuletzt geändert am",
    "creator": "Erstellt durch", "invited_by": "Eingeladen durch",
    "owner": "Zugehöriges Konto / Charakter", "user": "Benutzerkonto",
    "initiated_by_user": "Veranlasst durch", "actor_user": "Handelnde Person",
    "ip_address": "IP-Adresse", "user_agent": "Browserkennung",
    "attempt_time": "Anmeldezeitpunkt", "logout_time": "Abmeldezeitpunkt",
    "action_time": "Aktionszeitpunkt", "action_flag": "Aktionsart",
    "registration_key": "Öffentlicher WebAuthn-Schlüssel (Base64)",
    "registration_identifier": "Registrierungskennung (Base64)",
    "auth.User": "Benutzerkonten",
    "admin.LogEntry": "Administrative Aktivitäten des Kontos",
    "axes.AccessLog": "Anmeldeprotokolle",
    "axes.AccessAttempt": "Anmeldeversuche",
    "axes.AccessFailureLog": "Fehlgeschlagene Anmeldungen",
    "sessions.Session": "Gespeicherte Sitzungen",
    "char_picture": "Charakterbild",
    "current_experience": "Verfügbare Erfahrungspunkte",
    "overall_experience": "Gesamte Erfahrungspunkte",
    "used_experience": "Verwendete Erfahrungspunkte",
    "is_mother_tongue": "Muttersprache",
    "is_npc": "Nichtspielercharakter",
    "is_archived": "Archiviert",
    "order_index": "Reihenfolge",
    "date_joined": "Konto erstellt am",
    "source_ip": "IP-Adresse des Zugriffs",
    "two_factor_enabled": "Zwei-Faktor-Authentifizierung aktiviert",
    "int_bonus_languages_enabled": "Kostenlose Sprachen durch Intelligenz",
    "sign_count": "Anzahl der Sicherheitsbestätigungen",
    "paid_ep": "Bezahlte Erfahrungspunkte",
    "invested_cp": "Investierte Charakterpunkte",
    "gw_override": "Individuelle Vorgabe für den Geisteswiderstand",
    "vw_override": "Individuelle Vorgabe für den Verteidigungswert",
    "sr_override": "Individuelle Vorgabe für die Schadensreduktion",
    "sr": "Schadensreduktion", "rs": "Rüstungsschutz",
    "st": "Stärke", "h2": "Zweihändig",
    "CharacterDiaryEntry": "Charaktertagebuch",
    "Character": "Charaktere",
    "UserSettings": "Kontoeinstellungen",
    "CharacterItem": "Inventargegenstände",
    "AuthenticationThrottle": "Begrenzungen von Zugriffsversuchen",
    "charsheet.AuthenticationThrottle": "Begrenzungen von Zugriffsversuchen",
    "GameGroupCreature": "Eigene Kreaturen im Gruppenspiel",
    "GameGroup": "Spielgruppen", "GameGroupRole": "Gruppenrollen",
    "GameGroupInvitation": "Einladungen zu Spielgruppen",
    "GameGroupMembership": "Mitgliedschaften in Spielgruppen",
    "GameGroupTable": "Eigene Gruppentabellen",
    "GameGroupCreatureVampirePower": "Vampirkräfte eigener Gruppenkreaturen",
    "GameGroupCreatureVampireTrait": "Vampirmerkmale eigener Gruppenkreaturen",
    "ItemTransfer": "Gegenstandsübertragungen",
    "ItemOwnershipEvent": "Eigentumsgeschichte von Gegenständen",
    "ItemPermissionGrant": "Berechtigungen an Gegenständen",
    "ItemTransferNotification": "Benachrichtigungen zu Gegenständen",
    "selected_object_id": "Geprüfte ausgewählte Zuordnung",
    "metadata": "Zusätzliche Angaben zum Sicherheitsereignis",
    "label": "Gespeicherte Bezeichnung",
    "session_count": "Anzahl betroffener Sitzungen",
    "user_permissions": "Direkt erteilte Zugriffsberechtigungen",
    "groups": "Zugeordnete Berechtigungsgruppen",
    "attempts": "Gezählte Zugriffsversuche",
    "blocked_until": "Zugriff begrenzt bis",
    "window_started_at": "Beginn des Zählzeitraums",
    "AccountSecurityEvent": "Sicherheitsereignisse des Kontos",
    "PasskeyCredential": "Registrierte Passkeys",
    "TwoFactorRecoveryCode": "Wiederherstellungscodes (ohne Geheimnisse)",
}

VALUE_LABELS = {
    "login_succeeded": "Erfolgreiche Anmeldung",
    "login_failed": "Fehlgeschlagener Anmeldeversuch",
    "password_changed": "Passwort geändert",
    "password_reset": "Passwort zurückgesetzt",
    "email_changed": "E-Mail-Adresse geändert",
    "email_verified": "E-Mail-Adresse bestätigt",
    "two_factor_enabled": "Zwei-Faktor-Anmeldung aktiviert",
    "two_factor_disabled": "Zwei-Faktor-Anmeldung deaktiviert",
    "recovery_codes_regenerated": "Wiederherstellungscodes neu erstellt",
    "passkey_added": "Passkey hinzugefügt",
    "passkey_removed": "Passkey entfernt",
    "other_sessions_logged_out": "Andere Sitzungen abgemeldet",
    "session_terminated": "Sitzung beendet",
    "account_deactivated": "Konto deaktiviert",
    "account_reactivated": "Konto reaktiviert",
    "deletion_requested": "Kontolöschung angefordert",
    "passkey": "Passkey-Anmeldung", "two_factor": "Zwei-Faktor-Anmeldung",
    "recovery_code": "Wiederherstellungscode",
    "verification_resend": "Erneuter E-Mail-Bestätigungsversand",
    "password_reset_confirm": "Bestätigung einer Passwortzurücksetzung",
}

# Compose readable labels for the many similarly named game/stat fields.
WORDS = dict(pair.split("=", 1) for pair in """
absolute=absolut acquisition=Erwerb active=aktiv flag=Kennzeichen age=Alter
allows=erlaubt duplicate=Mehrfachauswahl alternative=alternativ group=Gruppe
image=Bild text=Text amount=Anzahl appearance=Aussehen append=anhängen
notes=Notizen to=zu damage=Schaden arcane=arkan power=Kraft increase=Erhöhung
armor=Rüstung encumbrance=Behinderung override=individuelle_Vorgabe min=minimal
total=gesamt zone=Zone overrides=individuelle_Vorgaben aspect=Aspekt
attack=Angriff type=Art value=Wert backed=gesichert up=gesichert base=Basis
trait=Merkmal bonus=Bonus source=Herkunft calendar=Kalender day=Tag
system=System can=darf write=schreiben capacity=Kapazität carry=Traglast
load=Last enabled=aktiviert character=Charakter creature=Kreatur
item=Gegenstand
effect=Wirkung specialization=Spezialisierung charisma=Charisma
mod=Modifikator
charsheet=Charakterbogen design=Gestaltung collapsed=eingeklappt combat=Kampf
fly=Flug speed=Geschwindigkeit swimming=Schwimmen command=Kommando
condition=Bedingung set=Gruppe configuration=Einstellungen
constitution=Konstitution country=Land of=von origin=Herkunft
crafter=Hersteller
level=Stufe creation=Erstellung name=Name cult=Kult current=aktuell
aggravated=schwerwiegend lethal=tödlich phase=Phase stun=Betäubung
custom=individuell description=Beschreibung fluff=Hintergrund g=G-Fähigkeit
ability=Fähigkeit god=Gottheit dice=Würfel faces=Seiten flat=fest
operator=Rechenoperator dddice=3D-Würfel box=Würfelbox room=Raum theme=Design
definition=Definition device=Gerät dexterity=Geschicklichkeit
display=Anzeige verification=Bestätigung address=Adresse sent=versandt
at=am email=E-Mail verified=bestätigt entity=Wesen entry=Eintrag date=Datum
equip=Ausrüstung locked=gesperrt equipped=ausgerüstet event=Ereignis
eye=Augen color=Farbe field=Feld key=Zuordnung first=erster kind=Art
formula=Formel gender=Geschlecht grant=Gewährung granted=gewährt by=durch
for=für granting=gewährend technique=Technik finalized=abgeschlossen
owner=Eigentümer hair=Haare height=Größe hidden=verborgen
identified=identifiziert
ignore=ignorieren critical=kritisch fumble=Patzer table=Tabelle
initialized=initialisiert initiative=Initiative intelligence=Intelligenz
is=ist fixed=fest magic=magisch last=zuletzt opened=geöffnet used=verwendet
layout=Anordnung learned=erlernt lesson=Lerneinheit levels=Stufen
summary=Zusammenfassung march=Marsch max=maximal advantage=Vorteile
disadvantage=Nachteile points=Punkte metadata=Zusatzangaben mode=Modus
money=Vermögen movement=Bewegung mana=Mana cost=Kosten note=Notiz
natural=natürlich order=Reihenfolge original=ursprünglich overall=gesamt
ownership=Eigentum version=Version password=Passwort changed=geändert
path=Pfad patron=Schutzmacht perception=Wahrnehmung personal=persönlich
fame=Ruhm point=Punkte rank=Rang pick=Auswahl price=Preis print=Druck
compact=kompakt include=enthalten inventory=Inventar priority=Priorität
provenance=Herkunft purchased=erworben steps=Schritte without=ohne
weakness=Schwäche purchases=Erwerbungen quality=Qualität race=Volk
religion=Religion reputation=Ruf revealed=offengelegt rules=Regeln rune=Rune
sacrifice=Opfer scale=Skalierung divisor=Teiler scaling=Skalierung
school=Schule selected=ausgewählt skill=Fertigkeit content=Inhalt
special=besonders derived=abgeleitet stat=Wert category=Kategorie
object=Objekt proficiency=Beherrschung resource=Ressource
specification=Ausprägung semantic=regelbezogen choice=Auswahl label=Bezeichnung
sheet=Bogen relevant=relevant shield=Schild parade=Parade show=anzeigen
as=als size=Größe class=Klasse modifier=Modifikator skin=Haut slot=Platz
slots=Plätze sort=Sortierung binding=Bindung selection=Auswahl
completed=abgeschlossen option=Option spell=Zauber spent=verwendet
learning=Lernen sprint=Sprint stack=Stapel behavior=Verhalten state=Zustand
step=Schritt stored=gespeichert strength=Stärke structure=Struktur
target=Ziel domain=Bereich theme=Design toggle=Umschalten inverted=umgekehrt
toggleable=umschaltbar tracks=berücksichtigt tradition=Tradition
training=Ausbildung transports=Übertragungswege two=Zwei factor=Faktor
uses=verwendet divine=göttlich vampire=Vampir cycle=Zyklus animal=Tier
blood=Blut baptism=Taufe confirmed=bestätigt loss=Verlust count=Anzahl
intelligent=intelligent qualifying=regelwirksam kill=Tötung pending=ausstehend
starvation=Bluthunger regeneration=Regeneration sacrament=Sakrament
rounds=Runden remaining=verbleibend visibility=Sichtbarkeit bought=abgekauft
off=aufgehoben weapon=Waffe maneuver=Manöver wield=Führung weight=Gewicht
willpower=Willenskraft wound=Wunde user=Benutzer account=Konto
settings=Einstellungen
security=Sicherheit credential=Registrierung diary=Tagebuch log=Protokoll
quickslot=Schnellzugriff draft=Entwurf template=Vorlage language=Sprache
transfer=Übertragung notification=Benachrichtigung invitation=Einladung
membership=Mitgliedschaft role=Rolle permission=Berechtigung token=Kennzeichen
point=Punkte group=Gruppe creation=Erstellung recovery=Wiederherstellung
code=Code prerequisite=Voraussetzung alchemy=Alchemie alchemist=Alchemist
recipe=Rezept custom=individuell journal=Tagebuch layout=Anordnung
advanced=erweitert almanac=Almanach arcanas=Arkana artefact=Artefakt
attribute=Attribut bonuss=Bonus brews=Gebräue career=Laufbahn
connector=Verknüpfung created=erstellt daemonic=dämonisch defense=Abwehr
deviation=Abweichung disclosures=Offenlegungen down=abwärts druid=Druide
extra=zusätzlich failure=Fehlschlag fear=Furcht identification=Identifikation
identifications=Identifikationen kraftbestie=Kraftbestie mastery=Meisterschaft
masterys=Meisterschaften mw=Mindestwurf organization=Organisation
passkey=Passkey resistance=Widerstand round=Runde settingss=Einstellungen
shaman=Schamane specs=Ausprägungen starting=anfänglich success=Erfolg
swarm=Schwarm thresholds=Schwellenwerte updated=geändert
temporary=vorübergehend
sender=Absender recipient=Empfänger initiated=veranlasst actor=Akteur
from=von to=zu grantee=Berechtigter granted=gewährt expires=läuft_ab
accepted=angenommen declined=abgelehnt cancelled=abgebrochen status=Status
message=Nachricht snapshot=gespeicherter_Stand title=Titel quantity=Menge
reason=Grund details=Einzelheiten read=gelesen revoked=widerrufen
invited=eingeladen notification=Benachrichtigung screen=Spielleiterschirm
html=Text id=Kennung rs=Rüstungsschutz st=Stärke h2=zweihändig
attachment=Dateianhang
game=Spiel
""".split())


def german_label(name):
    if name in PHRASES:
        return PHRASES[name]
    # Model names are CamelCase, field names use underscores.
    words = re.sub(r"([a-z])([A-Z])", r"\1 \2", name.rsplit('.', 1)[-1])
    translated = []
    for word in words.replace('_', ' ').split():
        key = word.lower()
        value = WORDS.get(key)
        if value is None and key.endswith('s'):
            value = WORDS.get(key[:-1])
        translated.append((value or word).replace('_', ' '))
    return ' '.join(translated).capitalize()
