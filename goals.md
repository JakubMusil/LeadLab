# Streamline & Sidebar UX Goals

Tento dokument je živý plán postavený na základě návrhu tří souvisejících UX
vylepšení streamline / activity timeline + sidebar composeru + IMAP/SMTP
pluginu. Položky jsou řazené dle priority. Hotové úkoly se odškrtávají
(`- [x]`), neodevzdané zůstávají `- [ ]`.

---

## 1) Filtr typů aktivit do dropdownu + per‑user nastavení

**Koncept**
- Bar filtru nahradit jedním tlačítkem „Filtr aktivit" (ikona + počet
  aktivních / celkem). Po kliknutí dropdown se sekcemi a checkboxy.
- Tři vrstvy konfigurace:
  1. **Default per parent type** — pro každý nadřazený objekt
     (Lead / Realization / Management / Task / Proposal …) backend definuje,
     které typy jsou „důležité" a defaultně zaškrtnuté. Zbytek (logy,
     `system_note`, `tag_added/removed`, `entity_change`, `ai_summary`,
     `pinned/unpinned` …) je defaultně **odškrtnuté**.
  2. **Per‑user override** — uživatel si v dropdownu zaškrtne/odškrtne
     typy a volba se uloží do jeho profilu. Platí napříč všemi výpisy
     streamline (globální nastavení uživatele), ne per objekt.
  3. **Per‑view ad‑hoc** — aktuální session filtr (např. „chci teď vidět
     jen e‑maily"). Nepřepisuje uložené nastavení, jen dočasné.

**Kategorizace typů (pro hezký dropdown)**
Do `StreamlineTool` přidat dvě metadata:
- `category` (výčet: `communication`, `task`, `commerce`, `system`, `ai`, `meta`)
- `default_visibility` (`important` / `secondary`) — `important` =
  defaultně viditelné

Sekce v dropdownu:
- **Komunikace** (Comment, Email, SMS, WhatsApp, Chat, Call, Meeting, Mention)
- **Úkoly & schvalování** (Task*, Approval*, Checklist, TimeLogged, DueDate …)
- **Obchod** (Proposal*, Invoice, Payment, Signature*)
- **Systémové logy** (StatusChange, EntityChange, Priority, Assignee, Tag*,
  Pinned, SystemNote)
- **AI** (AiSummary, AiSuggestedAction)

Nahoře dropdownu „Vybrat vše / Jen důležité / Žádné" a dole „Uložit jako
moje výchozí".

**Backend úkoly**
- [x] Přidat `category` a `default_visibility` na `StreamlineTool` (base).
- [x] Přiřadit metadata všem registrovaným toolům v `crm/streamline/tools.py`.
- [x] Rozšířit `ToolOut` v `crm/streamline/api.py` o `category` a
      `default_visibility`.
- [x] Nový model `UserStreamlinePreference` (user FK, `visible_activity_types`
      JSON list nebo `null` — `null` = použij per-tool defaulty, jinak je
      uložená sada použita verbatim, `Reset to defaults` ji vyprázdní).
- [x] Endpointy `GET/PUT /api/v1/users/me/streamline-preferences/`.
- [x] Migrace + testy.

**Frontend úkoly (SPA)**
- [x] Komponenta `StreamlineFilterDropdown` (button + popover s checkboxy
      po sekcích, ikony z `tool.icon`).
- [x] Pinia store `streamlinePreferences` (1× při loginu, persist do BE).
- [x] Indikátor počtu skrytých položek („3 skryté" badge na buttonu).
- [x] Tlačítka „Vybrat vše / Jen důležité / Žádné / Resetovat na výchozí".
      (Auto-save při každé změně — žádné explicitní „Save as default" už
      není potřeba, protože dropdown JE uložený stav.)
- [x] Nahradit stávající chip-bar v `ActivityTimeline.vue` tímto dropdownem.
- [x] i18n překlady `streamlineFilter.*` pro en/cs/de/pl.
- [x] Unit testy pro store (6) i komponentu (8).

---

## 2) Sjednocení duplicitních komunikačních toolů v sidebaru

**Problém dnes**
Sidebar/composer má 6 samostatných tlačítek: Email odeslaný/přijatý,
SMS odeslaná/přijatá, WhatsApp odeslaná/přijatá. Opticky šum, ostatní akce
se tlačí dolů.

**Návrh**
Jediné tlačítko **„Zpráva"** otevře unifikovaný composer s:
- Dropdown **Kanál**: E‑mail / SMS / WhatsApp / Chat / IM…
- Toggle **Směr**: Odchozí ↔ Příchozí (default Odchozí; Příchozí slouží pro
  zpětně logované zprávy).
- Pole se dynamicky mění podle kanálu (převzato z `get_schema()` jednotlivých
  toolů, jen sloučeno pod jednu UI „obálku").

**Backend úkoly**
- [x] V `StreamlineTool` přidat metadata `channel`
      (`email`/`sms`/`whatsapp`/`chat`/`none`) a `direction`
      (`in`/`out`/`none`).
- [x] Vrátit obojí přes `ToolOut` i `EntityToolbarOut`.
- [x] Aktivity zůstávají uložené pod existujícími `activity_type`
      (`email_in`, `email_out`, …) — žádná datová migrace.
- [x] Testy ověřující, že 6 messaging toolů + chat nese správnou
      `channel`/`direction` kombinaci a ostatní toolby mají `none`.

**Frontend úkoly**
- [x] Nový sidebar item „Zpráva" s unified composerem (synthetic
      `'message'` pseudo-tool, generovaný ze záznamů s `channel != 'none'`).
- [x] Mapování (kanál + směr) → konkrétní `activity_type` přes
      `resolvedMessageTool` computed; submit posílá konkrétní typ
      (`email_out`, `sms_in`, …), nikdy ne `'message'`.
- [x] Skrýt 6 stávajících tlačítek v sidebaru pro všechny entity.
- [x] Channel `chat` nemá toggle směru (`direction` je v jeho schema).
- [x] i18n překlady (`leadDetail.typeMessage`, `leadDetail.toolHelp.message`,
      `messageComposer.*`) pro en/cs/de/pl.
- [x] Unit testy pro composer (6 testů: skrytí tlačítek, chybějící
      messaging tools, picker, resolution, chat skip-direction, submit
      používá resolved type).

---

## 3) IMAP/SMTP plugin pro automatické přiřazování e‑mailů

**Princip**
- Firma si v nastavení pluginu zadá:
  - IMAP server + creds + složky ke čtení (Inbox, Sent) — pro **příchozí
    i odchozí** detekci.
  - Volitelně SMTP — pouze pro **odesílání** z LeadLabu (composer
    „Email odchozí" ho použije).
  - Frekvenci pollu (default 5 min) nebo IMAP IDLE pro real‑time.
- Každý objekt v CRM má **unikátní klíč** (např. `[LL-A8F3K2]` nebo
  doménový `lead-A8F3K2@reply.firma.cz`).
- Plugin při načtení e‑mailu:
  1. Hledá klíč v `Subject`, `In-Reply-To`/`References`, těle (regex).
  2. Pokud najde → vytvoří `Activity` typu `email_in`/`email_out`
     navázanou na správnou entitu (přes existující `EmailIn/OutTool`).
  3. Pokud nenajde → fallback na **e‑mail odesílatele/příjemce** → match
     proti `Contact`/`Lead`.
  4. Jinak → uloží do „Nepřiřazené e‑maily" inboxu, kde uživatel ručně
     přiřadí (drag & drop / select objektu). Po přiřazení se klíč může
     i zpětně doplnit do threadu.

**Backend úkoly (MVP)**
- [ ] Model `IncomingMailbox` (firm, host, port, ssl, username,
      password_encrypted, last_uid_seen, folder_in, folder_sent,
      polling_interval, enabled).
- [ ] Model `UnassignedEmail` (mailbox, message_id, headers, raw_body,
      parsed_text, attachments, received_at, suggested_entity_id, status).
- [ ] Celery periodic task `poll_imap_mailboxes`.
- [ ] Matcher pipeline: `KeyTagMatcher` → `ReplyAddressMatcher` →
      `ContactEmailMatcher` → `Unassigned`.
- [ ] Composer odchozí pošty doplňuje token do hlavičky
      (`X-LeadLab-Ref`) a do patičky („Vaše reference: LL-A8F3K2").
- [ ] Šifrování credentials (Fernet/`django-fernet-fields`).
- [ ] `UNIQUE(mailbox, message_id)` proti duplicitám.
- [ ] Přílohy přes existující file pipeline.

**V2 / V3** (mimo MVP)
- [ ] IDLE/push, SMTP odesílání z LL, OAuth (Google/Microsoft).
- [ ] Reply‑address routing, ML návrhy přiřazení.
- [ ] Bidirectional sync (read state), threading view.

---

## Pořadí prací

1. **Bod 1** — nejvyšší poměr přínos/úsilí, čistě UI + 1 model. Hned uklidí
   stránku.
2. **Bod 2** — navazuje na metadata `channel`/`direction`, žádná data migrace.
3. **Bod 3** — samostatný plugin, větší rozsah, nezávislý na 1+2.

---

_Aktualizováno průběžně agentem v této session._
