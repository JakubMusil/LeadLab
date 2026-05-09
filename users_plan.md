# Users views plán (krok 1)

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

### 2) Users detail view (následující krok)
- Vytvořit `UsersDetailView.vue` ve stylu Record detail:
  - pravý panel: základní profil člena (jméno, email, role, tým, expirace, scope/permissions snapshot),
  - levý panel: kompletní timeline aktivit daného uživatele napříč entitami (record/customer/proposal/task) a streamline,
  - filtrování timeline podle typů aktivit/entit jako u Record detailu,
  - akce dle oprávnění (edit role/team/expiry podle permission systému).
- Znovu použít existující stores a permission guard.
- Route: `/app/users/:membershipId`.

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

## Co bude příště
- Implementace `UsersDetailView.vue` + route `/app/users/:membershipId`.
- Napojení detailu na konkrétní membership data a endpoint pro kompletní aktivity uživatele napříč entitami a streamline.
- Přidání jemnějších akcí dle oprávnění (edit role/team/expiry) a UI stavů (forbidden/readonly) podle permission systému.
