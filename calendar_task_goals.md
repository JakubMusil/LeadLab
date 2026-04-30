# Calendar / Task unification — návrh a plán

## Stanovisko k návrhu

Návrh je dobrý a v podstatě **dotahuje to, co už v datovém modelu napůl je**. Klíčový princip:

> **Task = co se má stát (závazek, agenda, kalendář).
> Activity = co se stalo / co bylo zalogováno (immutable timeline).**

Dnes je to rozmazané: `meeting_scheduled` je „forward-looking" Activity, ale Activity z principu nemá stav ani termín, takže ji nelze „vyřídit", připomenout, přiřadit watcherům, opakovat, schvalovat. Všechno tohle už `Task` umí — duplikujeme tedy půl světa do Activity metadat. Sjednocení pod Task je správný směr.

### Co by sjednocení získalo

- **Jeden zdroj pravdy pro kalendář** — kalendář vrací prostě `Task.objects.filter(due_date__range=..., assigned_to=user)`, místo skládání ze dvou tabulek (Tasks + Activities s `metadata.start_at`).
- **Jednotná „agenda uživatele"** — co vidím / co mám / co sleduji — je dotaz nad `Task` (přes `assigned_to`, `watchers`, `created_by`).
- **Reuse hotové infrastruktury** — `TaskReminder`, recurrence, approval, custom fields, time-tracking, public share, notifikace, oprávnění, automatizace nad `task.*` triggery (už existují v `AutomationTrigger`).
- **Symetrie** — vyřeší se chybějící `call_scheduled` zdarma (je to jen Task s druhem „call").

### Na co si dát pozor (a v čem návrh trochu poladit)

1. **„Vyřízeno vypršením lhůty automaticky" — ano, ale ne jako `DONE`.**
   `done` znamená „uživatel to udělal a potvrdil". Když Task vyprší beze změny, neznamená to, že schůzka proběhla. Zavedl bych nový terminální stav `EXPIRED` (nebo `AUTO_CLOSED`) v `TaskStatus`. Tím se zachová sémantika a v reportech půjde rozlišit „dokončeno" vs „uplynulo bez akce". UI to může schovat stejně jako `done`.

2. **Po vypršení vyzvat k „outcome"** (volitelné, ale silné UX).
   Místo tichého auto-close u kalendářních tasků (call/meeting): když nadejde `due_date`, otevřít prompt „Proběhlo? → log `call`/`meeting` Activity s poznámkou / Přeplánovat / Nekonalo se". Auto-EXPIRED nastane, jen když uživatel nereaguje do X hodin/dnů.

3. **Activity nezrušit, ale degradovat na čistý log.**
   Vznik Tasku typu „Call scheduled" by měl emitovat Activity (např. `call_scheduled` / `meeting_scheduled`) s FK na ten Task — to už dnes funguje (Activity.task). Vyřízení / auto-expirace pak emituje další Activity (`task_completed` nebo nový `task_expired`). Timeline tak zůstane úplný a immutable.

4. **Nenahrazovat `meeting`/`call` (proběhlé) Tasky.**
   Logování *proběhlé* schůzky/hovoru zůstává Activity — žádný závazek, žádný kalendář. Task vzniká **jen** pro „scheduled" varianty.

5. **Migrace existujících `meeting_scheduled` Activit.**
   Data migrace: pro každou existující `meeting_scheduled` Activity vyrobit odpovídající Task (`due_date = metadata.start_at`, `kind = meeting`, navázaný na stejnou entitu) a Activity přelinkovat na něj přes `Activity.task`. Activity zůstane v timeline pro historii.

---

## Navržené ideální řešení

### 1. Datový model — minimální rozšíření `Task`

- Přidat `Task.kind` (TextChoices): `GENERIC` (default), `CALL`, `MEETING`, `EMAIL_FOLLOWUP`, případně další. Determinuje ikonu, formulář, výchozí délku, výchozí Activity typ.
- Přidat `Task.scheduled_end` (alias / využít existující `due_date_end`) jako konec slotu pro kalendář — `due_date_end` už existuje, použít ho.
- Přidat strukturovaná pole pro kalendář (nebo nechat v `metadata`):
  - `location` (CharField, blank)
  - `attendees` (JSONField list — interní user IDs + externí e-maily)
  - `provider_event_id`, `ics_url` (pro budoucí Google/Outlook sync) — zatím v `metadata` stačí.
- Rozšířit `TaskStatus` o `EXPIRED` (terminální, `is_completed=False`, ale „uzavřeno"). Volitelně `AUTO_DONE` pokud chcete „prošlo bez problému = hotovo".
- `Task.auto_close_on_expiry` (BooleanField, default podle `kind` — `True` pro CALL/MEETING).

### 2. Activity — doplnit chybějící typy a vyčistit roli

- Doplnit `ActivityType.CALL_SCHEDULED` a (volitelně) `TASK_EXPIRED`, `TASK_AUTO_CLOSED`.
- `MeetingScheduledTool` / nový `CallScheduledTool` v `crm/streamline/tools.py` upravit tak, aby **vytvořily Task** (kind=meeting/call) a zároveň zalogovaly Activity navázanou přes `Activity.task`. UI tool zůstane stejný, jen pod kapotou vznikne i Task.
- Toolbar v `EntitySidebarActionPicker.vue` se nemění z hlediska uživatele.

### 3. Auto-expirace — Celery beat job

- Nový periodický task v `crm/tasks.py`: každých např. 15 minut projde `Task.objects.filter(status__in=[TODO, IN_PROGRESS], auto_close_on_expiry=True, due_date__lt=now() - grace_period)` a:
  - Nastaví `status=EXPIRED`, `completed_at=now()` (jako „uzavřeno", ne „done").
  - Emituje Activity `task_expired` (nebo `task_auto_closed`).
  - Pošle notifikaci `assigned_to` + watcherům s odkazem „Co se stalo? Zalogovat výsledek / Přeplánovat".
- `grace_period` konfigurovatelné per `kind` (call: 2 h, meeting: 24 h).

### 4. API & dotazy — zjednodušení

- **Kalendářní endpoint:** jeden dotaz nad `Task` filtrovaný `due_date` rangem + `assigned_to__in=[user] | watchers=user`. Žádné mergování s Activity.
- **„Moje agenda"**: stejný princip, agregace podle dne/týdne, řazení dle `due_date`.
- **Timeline entity (Lead/Customer/...)**: beze změny — pořád čte Activity, jen některé Activity nově odkazují na Task.

### 5. Frontend (high level)

- `ActivityTimeline.vue` u typů `meeting_scheduled` / `call_scheduled` přidat odznak stavu z napojeného Tasku (`Plánováno` / `Hotovo` / `Vypršelo`) + tlačítko „Vyřídit / Přeplánovat".
- Kalendářní view (pokud zatím není plný kalendář) — přepnout na zdroj `Task` místo `Activity`.

### 6. Migrace stávajících dat

- Datová migrace: pro každou `Activity(type='meeting_scheduled')` bez navázaného Tasku vytvořit `Task(kind=MEETING, title=…, due_date=metadata.start_at, due_date_end=metadata.end_at, …)` a nastavit `Activity.task_id`. Idempotentní (používat hash provider_event_id pokud existuje).

### 7. Co výslovně **nedělat**

- Nepřejmenovávat ani nemazat existující `Activity.type='meeting_scheduled'` — zůstává jako log-typ. Mění se jen to, že vedle něj vzniká i Task.
- Neudělat z **každé** Activity Task. Tasky jen pro typy, které mají termín a vyžadují akci uživatele (whitelist: `call_scheduled`, `meeting_scheduled`, případně `signature_requested`, `approval_requested`, `email_followup`).
- Nepoužívat `done` pro auto-expiraci — sémanticky lžeme.

---

### Shrnutí v jedné větě

**Ano, sjednotit „naplánované akce" pod `Task` jako rodičovský objekt je správně** — kalendář a osobní agenda se tím radikálně zjednoduší a získáte zadarmo reminders/recurrence/approval. Klíčové je ale: (a) zachovat Activity jako immutable log (a navázat ji přes existující `Activity.task` FK), (b) nepoužít `done` pro vypršení, ale přidat stav `EXPIRED`, a (c) ideálně po expiraci ještě uživatele vyzvat k zalogování výsledku, místo tichého zavření.
