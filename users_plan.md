# Users views plán (krok 2)

## Cíl
Připravit 2 nové view ve stylu Record views:
- **Users list** (`/app/users`)
- **Users detail** (`/app/users/:membershipId`)

S důrazem na využití existujícího permission systému (`useCan`, role/scope z `permissions` store) a bez zavádění nového backend API v této fázi.

## Konkrétní plán

### 1) Users list view (MVP)
- Vytvořit nový frontend view `UsersListView.vue`.
- Načítat členy firmy z existujícího `useMembersStore` podle aktivní firmy (`useFirmStore.activeFirm`).
- Přidat filtry:
  - `search` (jméno + email),
  - `role`,
  - `team`,
  - stav členství (`active` / `expired` / `all`).
- Zobrazit tabulku s klíčovými sloupci:
  - jméno, email, role, tým, expirace.
- Přidat akci „Detail“ s připraveným odkazem na `/app/users/:membershipId` (`:membershipId` = `membership.id`).
- Omezit přístup přes permission systém:
  - povolit owner/manager/superadmin,
  - nebo uživatele s relevantním permission (`team.manage` / `role.manage`).

### 2) Users detail view
- Vytvořit `UsersDetailView.vue` ve stylu Record detail:
  - pravý panel: základní profil člena (jméno, email, role, tým, expirace, scope/permissions snapshot),
  - levý panel: kompletní timeline aktivit daného uživatele napříč entitami (record/customer/proposal/task) a streamline,
  - filtrování timeline podle typů aktivit/entit jako u Record detailu,
  - akce dle oprávnění (edit role/team/expiry podle permission systému).
- Znovu použít existující stores a permission guard.
- Route: `/app/users/:membershipId`.

## Průběžný pracovní log
- 2026-05-09:
  - Prošel jsem stav repozitáře a navázal na `users_plan.md`.
  - Spustil jsem existující CI příkazy před změnami:
    - Frontend: `check-locales` prošel, `type-check` padá na pre-existing TS chybách v jiných souborech.
    - Backend: instalace závislostí proběhla, `flake8` padá na pre-existing style/import problémech mimo tuto změnu.
  - Implementoval jsem nový view `UsersDetailView.vue` a route `/app/users/:membershipId`.
  - Do detailu jsem napojil existující stores/endpointy bez zavádění nového backend API.
  - Ověření po změnách:
    - `npx eslint src/views/UsersDetailView.vue src/router/index.ts` ✅
    - `npm run build-only` ✅
    - `npm run type-check` ❌ (pre-existing chyby mimo tuto změnu; bez nových chyb v `UsersDetailView.vue`)
  - Na základě review upraveno načítání timeline tak, aby se nespouštěly extrémní sekvenční requesty (chunkované načítání po malých dávkách paralelních stránek).
  - Zapracovány drobné stabilizační úpravy v detailu (bezpečnější převod expirace na ISO, čistší podmínky při ukládání týmu).
  - Přidána kontrola výsledku při odebírání člena z původního týmu, aby nedošlo k nekonzistentnímu stavu při přesunu mezi týmy.
  - UI detailu sjednoceno do češtiny a odstraněna interní technická poznámka z uživatelsky viditelné části.
  - Pokračování:
    - Spuštěny kontroly před dalšími úpravami:
      - Frontend: `check-locales` ✅, `type-check` ❌ (pre-existing TS chyby mimo scope), `lint` ❌ (pre-existing lint chyby), `test:unit` ❌ (100 testů pass, ale pre-existing unhandled errors), `build-only` ✅.
      - Backend: `flake8` ❌ (pre-existing style/import chyby), `manage.py test` ❌ (pre-existing test failures v jiných částech systému).
    - Doplněn i18n namespace `usersView` ve všech locale souborech (`cs/en/de/pl`).
    - `UsersListView.vue` převeden na `t(...)` texty (headery, filtry, tabulka, stavy, chyby).
    - `UsersDetailView.vue` převeden na `t(...)` texty (hlavička, timeline, profil, akce, grants/permissions snapshot, success/error hlášky).
  - Ověření po změnách:
      - `node scripts/check-locales.mjs` ✅
      - `npx eslint src/views/UsersListView.vue src/views/UsersDetailView.vue` ✅
      - `npm run build-only` ✅
      - `npm run type-check` ❌ (pre-existing chyby mimo scope)
- 2026-05-09 (pokračování):
  - Proveden další baseline check před úpravami:
    - Frontend: `check-locales` ✅, `build-only` ✅, `type-check` ❌ (pre-existing), `lint` ❌ (pre-existing), `test:unit` ❌ (pre-existing).
    - Backend: `flake8` ❌ (pre-existing), `manage.py test` ❌ (pre-existing).
  - Přidán nový backend endpoint `GET /api/v1/crm/reports/users/{membership_id}/timeline`:
    - vrací timeline pro konkrétního člena firmy napříč entitami (record/customer/proposal/task),
    - podporuje stránkování (`page`, `page_size`) a filtry (`type`, `entity_type`),
    - respektuje tenant izolaci a existující activity scope filtr (`filter_activities_qs`).
  - Přidány integrační backend testy pro nový endpoint:
    - základní dostupnost, filtr entity, filtr typu aktivity, tenant izolace, 404 pro neexistující membership.
  - `UsersDetailView.vue` přepojen z workaroundu přes `/crm/reports/activities` na nový cílený endpoint timeline.
  - Následuje:
    - spustit cílené validace změněných souborů a případně doladit nalezené problémy,
    - dokončit checklist, spustit `parallel_validation`,
    - připravit řádný PR s rekapitulací.
  - Cílené ověření po implementaci:
    - `python manage.py test crm.tests.ActivityFeedAPITest crm.tests.UserTimelineReportAPITest` ✅
    - `npx eslint src/views/UsersDetailView.vue` ✅
    - `npm run build-only` ✅
    - `flake8 crm/api.py crm/tests.py` ❌ (soubor `crm/api.py` má rozsáhlé pre-existing style nálezy mimo scope této změny).
  - Po code review z `parallel_validation` doplněna pojmenovaná konstanta `USER_TIMELINE_PAGE_SIZE` v `UsersDetailView.vue`.
  - Připraveno k vytvoření řádného PR.

## Co je hotovo
- Vytvořen plán pro oba view (Users list + Users detail) ve stylu Record views.
- Vytvořen nový view `frontend-spa/src/views/UsersListView.vue` jako základ listu:
  - načítání members přes `useMembersStore` a aktivní firmu,
  - filtry `search`, `role`, `team`, `stav členství`,
  - tabulka sloupců jméno/email/role/tým/expirace,
  - permission guard přes `useCan` + kontrolu owner/manager/superadmin,
  - připravený odkaz do detailu uživatele (`/app/users/:membershipId`).
- Přidána route `/app/users` do `frontend-spa/src/router/index.ts`.
- Práce byla delegována na subagenta a následně zkontrolována.
- Přidán nový view `frontend-spa/src/views/UsersDetailView.vue`:
  - detail člena (jméno/email/role/tým/expirace),
  - permission snapshot (`permissions` z membership),
  - grants snapshot přes existující endpoint `/api/v1/firms/{id}/members/{membership_id}/grants`,
  - akce dle oprávnění (`role.manage`/`team.manage`) pro úpravu role, expirace a týmu,
  - timeline aktivit s filtry (typ entity / typ aktivity) načítaná z existujícího report endpointu.
- Přidána route `/app/users/:membershipId` do `frontend-spa/src/router/index.ts`.
- Doladěny i18n texty pro Users list/detail:
  - nový namespace `usersView` v `frontend-spa/src/locales/{cs,en,de,pl}.json`,
  - odstraněny hardcoded texty z `UsersListView.vue` a `UsersDetailView.vue`,
  - sjednocena textace a fallbacky (`usersView.common.notSet`) napříč oběma view.
- Přidán cílený backend endpoint pro user timeline:
  - `GET /api/v1/crm/reports/users/{membership_id}/timeline`,
  - vrací aktivity uživatele napříč entitami + názvy navázaných entit,
  - podporuje `page`, `page_size`, `type`, `entity_type`,
  - `UsersDetailView.vue` je na endpoint napojen.
- Přidány integrační testy pro nový endpoint v `crm/tests.py`.

## Co bude příště
- Zvážit doplnění odpovědi endpointu o celkový počet položek (pro přesnější UX pagination indikaci).
- Zvážit doplnění přímých odkazů z timeline i pro customer/proposal/task položky (nejen record).
- Po stabilizaci odstranit/starat se o případné technické dluhy v `reports/activities`, pokud už nebude potřeba pro tento use-case.
