# Oznámení — plán a průběh úprav

## Checklist

- [x] Zmapovat stávající tok oznámení (API payloady, frontend rendering, i18n) a potvrdit příčinu chyby `mark-read`
- [x] Opravit backend endpoint `/api/v1/crm/notifications/mark-read`, aby správně přijímal `{ ids: [...] }` i prázdné tělo pro „označit vše“
- [x] Přidat cílené backend testy pro oba režimy endpointu (`ids` i prázdné tělo)
- [x] Přidat permalink proklik z oznámení na relevantní objekt (záznam, úkol, zákazník, nabídka) podle payloadu
- [x] Zlepšit UX panelu oznámení (klikatelné položky, ARIA popisy, jasnější CTA)
- [x] Doplnit překlady (cs/en/de/pl) pro nové texty notifikací
- [x] Spustit cílené testy/build po změnách a zapsat výsledky
- [x] Finalní kontrola, shrnutí a uzavření všech bodů

## Průběžné poznámky

- Chyba `list_type` byla způsobena tím, že endpoint očekával přímo `List[str]` místo objektu `{ ids: [...] }`.
- Backend nyní používá body schema `MarkNotificationsReadIn`.
- Ve frontendu je přidaný permalink routing podle typu notifikace:
  - `record.created` / `record.updated` → `/app/records/:id`
  - `activity.created` → podle `entity_type` (`record`/`customer`/`proposal`/`task`)
  - `task.completed` / `task.expired` / `task.outcome_prompt` → `/app/tasks/:id`
  - `record.deleted` zůstává bez prokliku
- Validace po změnách:
  - ✅ `python3 manage.py test crm.tests.NotificationsMarkReadAPITest --keepdb` (2/2)
  - ✅ `npm run build-only`
  - ℹ️ `npm run type-check` stále padá na pre-existujících TypeScript chybách mimo scope této úpravy.
- Zapracováno i následné review:
  - odstraněn default objekt v signatuře endpointu `mark-read`
  - odstraněno opakované vyhodnocování `notifLink()` v template (předpočítané `notificationsWithLinks`)
