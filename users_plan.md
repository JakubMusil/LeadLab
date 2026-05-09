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

## Co bude příště
- Doplnit backend endpoint pro plnohodnotnou user timeline napříč všemi entitami (record/customer/proposal/task) bez workaroundu přes report feed.
- Rozšířit timeline o stránkování/počty podle uživatele přímo na backendu (efektivnější načítání).
- Doladit i18n texty pro Users detail a sjednotit textaci s ostatními view.
