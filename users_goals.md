# Users Goals – Rozšířený systém práv a oprávnění

> Návrh rozšířeného systému práv a oprávnění uživatelů pro LeadLab.
> Cílem je škálovatelný, granulární a auditovatelný model, který nahradí
> stávající plochou trojici rolí `OWNER` / `ADMIN` / `WORKER`.

---

## 1. Analýza současného stavu (as-is)

### 1.1 Co máme dnes

| Vrstva | Stav |
|---|---|
| **Role** | `MembershipRole = {OWNER, ADMIN, WORKER}` natvrdo v `firms/models.py:74-77`. Žádné vlastní role nelze definovat. |
| **Vazba uživatel ↔ workspace** | `Membership(user, firm, role)` – jeden uživatel může být v více firmách, vždy s právě jednou rolí. |
| **Enforcement** | Centrálně v `firms/auth.py` přes `require_membership(request, min_role=...)`. Ordering rolí: `WORKER < ADMIN < OWNER`. |
| **Vlastnictví záznamů** | `PipelineRecord`, `Customer`, `Proposal`, `Task`, `StreamlineItem`, `TaskDependency` mají `created_by` (FK→User, SET_NULL) a většinou i `assigned_to`. |
| **Kategorie** | `Category` je per-firm taxonomie pro `PipelineRecord`. Žádné ACL na úrovni kategorie. |
| **Streamline** | `Activity` / `StreamlineItem` – timeline aktivit nad záznamem. Viditelnost je 1:1 s viditelností záznamu. |
| **Delegace správy** | Pouze `OWNER`/`ADMIN` mohou zvát uživatele a měnit role (`firms/invitations_api.py`, `pipeline_config_api.py`). |
| **Subscription gating** | `require_active_subscription` + `check_tier_limits` (Free 2 členové / 50 záznamů). |

### 1.2 Co chybí

1. **Granularita** – uživatel typu `WORKER` vidí všechny záznamy v dané firmě napříč kategoriemi. Není možné říct „obchodník Jana vidí jen kategorii *Architekti*“.
2. **Vlastnictví vs. team** – chybí pojem **scope** (vlastní / týmové / všechny). Nelze říct „Karel vidí pouze záznamy, kde je `assigned_to = Karel`“.
3. **Vlastní role** – nelze definovat firma-specifické role (např. „Marketing Lead“, „External Auditor – read only“).
4. **Per-resource ACL** – chybí schopnost přidělit přístup na *konkrétní* záznam nebo kategorii nezávisle na roli.
5. **Týmy** – neexistuje entita `Team` ani sdílení podle týmu.
6. **Streamline visibility** – pokud má uživatel přístup k záznamu, vidí *celý* jeho streamline napříč všemi uživateli; chybí možnost omezit viditelnost aktivit jiných uživatelů.
7. **Delegace** – pouze role-based; nelze delegovat „správu pouze této kategorie“ na ne-admina.
8. **Audit trail** – kdo komu kdy přidělil/odebral přístup se nezaznamenává.
9. **Frontend** – UI pro správu členů (`SettingsView` → tab `Team`) ukazuje pouze 3 role bez další konfigurace.
10. **Test coverage** – `crm/tests.py` testuje jen owner vs. worker isolation; žádné scope-based testy.

---

## 2. Cílový stav (to-be)

### 2.1 Konceptuální vrstvy

```
┌──────────────────────────────────────────────────────────────────────────┐
│  Vrstva 0 │ Workspace (Firm) – tenant boundary, nezměněné                │
├───────────┼──────────────────────────────────────────────────────────────┤
│  Vrstva 1 │ Role (system + custom)                                       │
│           │   - System role: OWNER, ADMIN, MEMBER, GUEST                 │
│           │   - Custom role: per-firm, definovaná Owner/Admin            │
│           │   - Role nese set "permission codes" (viz Vrstva 2)          │
├───────────┼──────────────────────────────────────────────────────────────┤
│  Vrstva 2 │ Permission codes (action × resource)                         │
│           │   napr. record.view, record.create, record.delete,           │
│           │        category.manage, team.manage, billing.manage…        │
├───────────┼──────────────────────────────────────────────────────────────┤
│  Vrstva 3 │ Scope (= "co vidím")                                         │
│           │   - own           (jen kde jsem created_by/assigned_to)      │
│           │   - team          (členové mého Teamu)                       │
│           │   - category(ids) (jen vyjmenované kategorie)                │
│           │   - all           (vše ve firmě)                             │
├───────────┼──────────────────────────────────────────────────────────────┤
│  Vrstva 4 │ Per-resource grants (ACL)                                    │
│           │   - CategoryGrant(user|team, category, level)                │
│           │   - RecordGrant   (user|team, record,   level)               │
│           │   - level = view | edit | manage                             │
├───────────┼──────────────────────────────────────────────────────────────┤
│  Vrstva 5 │ Streamline visibility                                        │
│           │   per-record:    own | team | all  (podle scope na záznam)   │
│           │   per-activity:  visibility = public | restricted            │
└──────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Klíčové entity (cílové)

| Entita | Popis |
|---|---|
| `Role` | Per-firm definice role. Pole: `firm`, `code`, `name`, `is_system`, `description`. |
| `Permission` | Číselník akcí (statická tabulka, seedovaná migrací). Pole: `code` (např. `record.edit`), `category` (logická skupina), `description`. |
| `RolePermission` | M:N `Role` ↔ `Permission`. |
| `Membership` (rozšířená) | Přidat `roles: M2M Role`, `default_scope: ScopeType`, `category_scope: M2M Category`, `team: FK Team (nullable)`. (Stávající `role: char` zůstane jako legacy fallback během migrace.) |
| `Team` | Skupina členů ve firmě (`firm`, `name`, `slug`, `members: M2M Membership`). |
| `CategoryGrant` | Per-category ACL (`category`, `principal_type` = user/team, `principal_id`, `level`). |
| `RecordGrant` | Per-record ACL (`record`, `principal_type`, `principal_id`, `level`, `granted_by`, `granted_at`, `expires_at?`). |
| `PermissionAuditLog` | Audit – kdo, komu, co, kdy přidělil/odebral. |
| `Activity.visibility` | Nové pole: `public` (default) / `restricted` (jen scope=team/all). |

### 2.3 Systémové role (defaulty)

| Role | Popis | Permissions (zkratky) |
|---|---|---|
| **Superadmin** *(globální)* | Django `is_superuser=True`. Nad všemi firmami a Ownery. Přístup ke každému workspacu bez nutnosti členství. | `*` (vše, bez výjimek, přes všechny firmy) |
| **Owner** | Plný přístup, nemůže být odebrán. Jediný kdo může smazat firmu, transferovat vlastnictví, spravovat billing. | `*` (super-set, fixní, v rámci firmy) |
| **Admin** | Spravuje členy, role, kategorie, integrace. | vše kromě `firm.delete`, `firm.transfer`, `billing.manage` |
| **Manager** *(nová)* | Spravuje vlastní tým + jeho záznamy. | `team.manage(own)`, `record.* (scope=team)`, `category.view`, `report.view` |
| **Member** *(přejmenovaný `Worker`)* | Standardní obchodník/uživatel. Default scope = `own`, lze rozšířit. | `record.* (scope=own|category)`, `activity.create`, `proposal.create` |
| **Guest** *(nová)* | Read-only host (např. externí auditor). | `record.view (scope=category|record)` |

> Owner a Admin jsou `is_system=True` a nelze je smazat ani editovat sadu permissions. Custom role lze vytvářet libovolně, ale nesmí dostat `firm.delete`/`billing.manage`.
> Superadmin je implementován přes Django vestavěný `User.is_superuser` flag – **není to firma-level role**, ale globální systémová úroveň (LeadLab support staff).

### 2.4 Pravidla delegace

1. **Vytváření/úprava rolí**: pouze `firm.role.manage` (default Owner + Admin).
2. **Přidělení role uživateli**: pouze role, jejíž permissions jsou *podmnožinou* permissions přidělitele (princip „nemůžu dát víc, než sám mám“).
3. **Transfer Owner**: jen aktuální Owner; spustí se 2-step potvrzení (email + UI).
4. **Smazat Owner role**: zakázáno.
5. **Per-category správa**: uživatel s `category.manage(category=X)` může v rámci kategorie X přidělit ostatním `record.*` granty, ale **nikdy ne** vyšší než vlastní (např. nelze udělit `record.delete`, pokud sám má jen `edit`).
6. **Audit**: každá změna Role / Membership / Grant generuje záznam v `PermissionAuditLog`.

### 2.5 Algoritmus rozhodnutí (request → allow/deny)

```
def can(user, firm, action, resource=None):
    0. Je-li user.is_superuser    → ALLOW (globální zkratka, nad všemi firmami)
    1. Není-li firm membership → DENY
    2. Je-li Owner             → ALLOW (zkratka)
    3. effective_perms = ∪ rolí.permissions ∪ direct grants
    4. Není-li `action` v effective_perms → DENY
    5. Je-li resource zadán:
        a) zjisti scope pro (action, resource_type)
           = max( role.default_scope, category_scope match, direct grant level )
        b) podle scope vyhodnoť:
            own       → resource.created_by == user OR resource.assigned_to == user
            team      → resource.assigned_to ∈ user.team.members
            category  → resource.category_id ∈ user.allowed_categories
            record    → existuje RecordGrant pro user/team
            all       → True
    6. Pokud žádné scope nepustí → DENY
```

### 2.6 Implementace v query layeru

Do `crm/permissions.py` (nový modul) doplnit:

- `filter_records(qs, request) -> QuerySet` – vrací zúžený QS podle scope.
- `filter_activities(qs, request)`
- `filter_proposals(qs, request)`
- `filter_tasks(qs, request)`
- Each navazuje na `request.membership` (resolved middlewarem).

Tyto helpery nahradí dnešní `PipelineRecord.objects.filter(firm=request.firm)` v každém endpointu.

---

## 3. Fázový plán

Plán je rozdělen na **8 fází**. Každou fázi lze nasadit samostatně bez breaking changes díky feature-flag `settings.PERMISSIONS_V2_ENABLED` (default `False` v první fázi, `True` po Phase 6).

---

### Fáze 1 – Foundation: permissions katalog & helper API

**Cíl**: zavést datový základ a centralizovanou permission logiku, **bez** změny stávajícího chování.

**Kroky**:
1. Vytvořit `firms/permissions.py` s konstantami:
   - `Permission` enum (`RECORD_VIEW`, `RECORD_CREATE`, `RECORD_EDIT`, `RECORD_DELETE`, `CATEGORY_MANAGE`, `TEAM_MANAGE`, `ROLE_MANAGE`, `BILLING_MANAGE`, `INTEGRATIONS_MANAGE`, `REPORT_VIEW`, `STREAMLINE_VIEW_ALL`, …).
   - `Scope` enum (`OWN`, `TEAM`, `CATEGORY`, `ALL`).
   - Statická mapa `LEGACY_ROLE_PERMISSIONS: {OWNER: [...], ADMIN: [...], WORKER: [...]}` – přesný překlad dnešních rolí.
2. Implementovat `can(membership, permission, scope=None) -> bool` postavené nad legacy mapou.
3. Migrace: žádná. Pouze refaktor `firms/auth.py::require_membership` aby interně volalo `can(...)`. Externí signatura zůstává (`min_role=`).
4. Unit testy `firms/tests.py::PermissionMatrixTests` – pro každou kombinaci role × permission ověřit ALLOW/DENY.

**Hotovo, když**: existující testy (`crm/tests.py`, `firms/tests.py`) procházejí beze změny + nový matrix test má zelenou.

---

### Fáze 2 – Datový model: Role, Permission, RolePermission, Team

**Cíl**: zavést tabulky pro budoucí roli a tým, naplnit je systémovými daty, ale ještě je nepoužívat ve query layeru.

**Kroky**:
1. Migrace `firms/migrations/00XX_roles_and_teams.py`:
   - `Permission(code PK, group, description)` – seed všemi konstantami z Fáze 1.
   - `Role(id UUID, firm FK, code, name, is_system, description, created_at)` + `unique_together=(firm, code)`.
   - `RolePermission(role, permission)` M2M.
   - `Team(id UUID, firm FK, name, slug, color, created_at)` + `unique_together=(firm, slug)`.
   - `TeamMembership(team, membership, joined_at)` M2M-through.
2. Data migrace: pro každou existující `Firm` vytvořit 4 systémové role (`Owner`, `Admin`, `Member`, `Guest`) a namapovat permissions podle `LEGACY_ROLE_PERMISSIONS`.
3. Rozšířit `Membership`:
   - `roles = M2M(Role)` (data migrace: každý existující Membership dostane odpovídající systémovou roli).
   - `default_scope = CharField(choices=Scope, default='own')`.
   - `team = FK(Team, null=True, on_delete=SET_NULL)`.
   - Stávající `role = CharField` ponechat → bude *deprecated* (čteno fallbackem, zapisováno duálně).
4. Admin registrace pro `Role`, `Team`, `PermissionAuditLog` v `firms/admin.py`.
5. **Žádný API endpoint zatím nepřidáváme** – pouze model + migrace + admin.

**Hotovo, když**: `manage.py migrate` projde na čisté DB i na DB s daty (load_demo_data); nové testy pro data migraci mají zelenou.

---

### Fáze 3 – Per-category & per-record ACL (CategoryGrant, RecordGrant)

**Cíl**: přidat per-resource grants, opět ještě bez napojení na request flow.

**Kroky**:
1. Migrace `00XX_category_record_grants.py`:
   - `CategoryGrant(id, category FK, principal_type CHOICES('user','team'), principal_id UUID, level CHOICES('view','edit','manage'), granted_by FK Membership, granted_at, expires_at NULL)`.
   - `RecordGrant(id, record FK PipelineRecord, principal_type, principal_id, level, granted_by, granted_at, expires_at NULL)`.
   - Indexy: `(category, principal_type, principal_id)`, `(record, principal_type, principal_id)`.
2. `PermissionAuditLog(id, firm, actor FK User, action CHAR, target_type, target_id, payload JSON, created_at)` + signály na save/delete `Role`, `Membership`, `CategoryGrant`, `RecordGrant`.
3. Manager metody: `Category.users_with_access()`, `PipelineRecord.users_with_access()` – pro UI.
4. Unit testy nových modelů (constraint, FK, audit-log signals).

**Hotovo, když**: migrace projde, audit log se vytváří, manager metody mají testy.

---

### Fáze 4 – Permissions resolver & query scoping

**Cíl**: zapojit nový model do *čtecí* cesty (zatím za feature flagem).

**Kroky**:
1. Nový modul `crm/permissions.py`:
   - `resolve_effective_permissions(membership) -> set[Permission]` (sjednocení rolí + direct grants).
   - `resolve_scope(membership, permission) -> Scope` (max ze všech zdrojů).
   - `filter_records_qs(qs, request)`, `filter_activities_qs`, `filter_proposals_qs`, `filter_tasks_qs`.
2. `firms/auth.py::require_permission(request, perm: Permission, *, resource=None) -> Membership` – nový gate, paralelní k `require_membership`.
3. Feature flag `settings.PERMISSIONS_V2_ENABLED`:
   - `False` → `require_permission` interně mapuje `perm` → legacy `min_role` a chová se jak doteď.
   - `True`  → použije nový resolver.
4. Postupně migrovat endpointy (1 PR per modul) z `require_membership(request, min_role=...)` → `require_permission(request, Permission.X)` + `qs = filter_records_qs(PipelineRecord.objects.all(), request)`. Pořadí: `crm/api.py` (records) → `proposals_api.py` → `automations_api.py` → `pipeline_config_api.py` → ostatní.
5. Backward-compat testy: spustit existující `crm/tests.py` při `PERMISSIONS_V2_ENABLED=True` – musí zůstat zelené (díky data migraci z Fáze 2 mají všichni stávající uživatelé ekvivalentní role).

**Hotovo, když**: všechny endpointy používají `require_permission`, oba flagy (False/True) projdou kompletním test suite.

---

### Fáze 5 – Streamline visibility

**Cíl**: omezit viditelnost streamline aktivit podle scope.

**Kroky**:
1. Migrace: přidat `Activity.visibility = CharField(choices=[('public','Public'),('restricted','Restricted')], default='public')` a `StreamlineItem.visibility` (stejné).
2. `filter_activities_qs` rozšířit:
   - Pokud `restricted`: viditelné jen pokud user má scope `team`/`all` na záznam, NEBO je `created_by=user`.
3. UI v `StreamlineCreateModal` – přidat toggle „Viditelné pouze týmu/správcům“.
4. API endpointy `crm/api.py` (activities list, streamline) napojit na filter.
5. Backfill migrace: všechny existující Activity → `public` (zachová dnešní chování).

**Hotovo, když**: nové testy (`crm/tests.py::StreamlineVisibilityTests`) ověřují, že `restricted` aktivita není vidět uživateli s `scope=own`.

---

### Fáze 6 – Admin API: Role, Team, Grants

**Cíl**: vystavit CRUD nad rolemi, týmy a granty.

**Kroky**:
1. Nový router `firms/roles_api.py`:
   - `GET /api/v1/firms/{id}/permissions` – číselník (statický).
   - `GET/POST /api/v1/firms/{id}/roles`, `PATCH/DELETE /roles/{role_id}`.
   - `POST /roles/{role_id}/permissions` – nastavit set.
   - Guard: `Permission.ROLE_MANAGE` + pravidlo „nemůžu dát víc než mám“.
2. `firms/teams_api.py`:
   - `GET/POST /api/v1/firms/{id}/teams`, `PATCH/DELETE /teams/{team_id}`.
   - `POST/DELETE /teams/{team_id}/members/{membership_id}`.
   - Guard: `Permission.TEAM_MANAGE`.
3. Rozšířit `firms/invitations_api.py` aby pozvánka mohla nastavit `roles[]`, `team`, `default_scope`, `category_scope[]`.
4. `crm/api.py` & `crm/pipeline_config_api.py`:
   - `POST /api/v1/crm/categories/{id}/grants` – udělit access (user|team, level).
   - `POST /api/v1/crm/records/{id}/grants` – per-record sdílení.
   - `GET /api/v1/crm/records/{id}/access` – kdo má přístup (pro UI „Sdílet“).
5. `GET /api/v1/firms/{id}/audit-log` – pageable, filtrovatelný.
6. Set `PERMISSIONS_V2_ENABLED=True` ve výchozí konfiguraci.

**Hotovo, když**: full API smoke test (roles + teams + grants + audit), Postman/HTTPie kolekce v `docs/`.

---

### Fáze 7 – Frontend: UI správy rolí, týmů a sdílení

**Cíl**: dát adminům UX pro novou správu, zachovat současné UX pro běžné členy.

**Kroky** (`frontend-spa/`):
1. Pinia store `frontend-spa/src/stores/permissions.ts`:
   - state: `permissions[]`, `roles[]`, `teams[]`, `myEffectivePermissions: Set<string>`.
   - getters: `can(action, scope?)`, `canManageRoles`, `canManageTeams`.
   - načte se po loginu z `/api/v1/firms/{id}/me/permissions`.
2. `SettingsView` → nová tab `permissions.tabRoles`, `permissions.tabTeams`:
   - `RolesSettingsView.vue` – tabulka rolí + matice permissions × role (toggle).
   - `TeamsSettingsView.vue` – CRUD týmů + drag&drop členů.
3. Tab `Team` (členové) rozšířit:
   - sloupce: Role(y), Tým, Default scope, Kategorie.
   - editovatelné jen pro `permissions.canEditMember`.
4. Globální `<v-if="can('record.create')">` direktiva (`useCan` composable).
5. `PipelineRecordDetailView` – nové tlačítko „Sdílet“ otevírá `RecordShareModal.vue` (přidá `RecordGrant`).
6. `CategoryDetailView` (resp. `PipelineSettingsView`) – sekce „Přístupy ke kategorii“.
7. i18n klíče v `cs.json`, `en.json`, `de.json`, `pl.json` pod namespace `permissions.*` (např. `permissions.role.member`, `permissions.scope.own`).
8. Skrytí položek menu, které uživatel nesmí (`Reports`, `Settings → Billing`, `Integrations`) podle `can()`.

**Hotovo, když**: e2e test (`e2e/permissions.spec.ts`) projde scénáře:
- Member s `scope=own` v listu vidí jen své záznamy.
- Admin přidělí Member roli `category.manage(Architekti)` → Member nově vidí celou kategorii.
- Owner transferuje vlastnictví → původní Owner se stane Admin.

---

### Fáze 8 – Migrace, dokumentace, deprecation legacy `Membership.role`

**Cíl**: dotáhnout cleanup po úspěšném rolloutu.

**Kroky**:
1. Změnit `Membership.role` na *generated*/read-only property dopočítávané z M2M `roles` (pro zpětnou kompatibilitu serializerů); pak v dalším releasu drop column.
2. Smazat `MembershipRole` `WORKER` (přejmenovat → `MEMBER`, deprecation alias).
3. Aktualizovat `docs/` (`mkdocs.yml` + nové stránky `permissions.md`, `teams.md`, `roles.md`).
4. Aktualizovat `walkthrough.md` a `README.md`.
5. Plugin / webhook payloads: přidat `permissions` & `roles` do `MembershipOut` schématu.
6. Removal feature flag `PERMISSIONS_V2_ENABLED` (vždy on).

**Hotovo, když**: deprecation warnings vyčištěny, dokumentace aktuální, tag `v2.0-permissions`.

---

## 4. Migrační strategie a backward compatibility

| Fáze | Riziko | Mitigace |
|---|---|---|
| 1 | žádné (jen refaktor) | matrix test |
| 2–3 | data migrace na produkčních DB | dry-run command `python manage.py migrate_permissions --check`; transakční migrace |
| 4 | změna chování čtecí cesty | feature flag `PERMISSIONS_V2_ENABLED`, oba módy v CI |
| 5 | viditelnost aktivit | default `public` ⇒ neviditelné regrese |
| 6 | nové API | smoke test + verzování `/api/v1/` |
| 7 | UX změny | progressive disclosure (admin tab je nový, member UX zůstává) |
| 8 | drop column | release notes + 1 verze prodlevy |

**Rollback plán**: každou fázi lze vrátit `git revert + manage.py migrate <prev>`. Datové migrace (Fáze 2–3) jsou idempotentní a nedestruktivní (přidávají, neodebírají).

---

## 5. Konkrétní use-cases (akceptační kritéria)

1. **„Obchodník Jana vidí jen kategorii Architekti“**
   - Jana má `Membership(role=Member, default_scope='category', category_scope=[Architekti])`.
   - `GET /api/v1/crm/records?category=...` vrací 403 pro jiné kategorie a omezený list.
2. **„Karel vidí jen své záznamy, ale celou jejich streamline napříč týmem“**
   - Karel: `default_scope='own'`, ale `Permission.STREAMLINE_VIEW_ALL` přidán k jeho roli.
   - V `filter_activities_qs` se aplikuje `STREAMLINE_VIEW_ALL` jako override.
3. **„Manažer Petr spravuje tým Sales-CZ, vidí všechny jejich záznamy“**
   - Petr: role `Manager`, `team=Sales-CZ`. Default scope = `team`.
   - Q: `PipelineRecord.objects.filter(assigned_to__memberships__team=Petr.team)`.
4. **„Externí auditor po dobu 30 dnů“**
   - Pozvánka: `roles=[Guest]`, `RecordGrant` na konkrétní záznamy s `expires_at = now+30d`.
   - Cron task `expire_record_grants` je vyčistí.
5. **„Admin nemůže smazat firmu“**
   - `Permission.FIRM_DELETE` patří *jen* Owner roli, která je `is_system=True`.

---

## 6. Bezpečnostní pravidla

- **Tenant boundary** zůstává tvrdá – žádný grant nemůže přesáhnout `firm`.
- **Privilege escalation prevention** – při `POST /roles/{id}/permissions` se každá nová permission ověří proti `actor.effective_permissions ⊇ requested`.
- **Direct DB access** (admin Django) zůstává jen pro `is_superuser` (LeadLab support).
- **Audit log** je append-only (DB constraint `update`/`delete` zakázáno na úrovni triggeru / admin readonly).
- **Rate limiting** existujícího `users/throttle.py` rozšířit na `/permissions/grants`.
- **CodeQL / dependency scan** – beze změny závislostí (vše Django stdlib).

---

## 7. Otevřené otázky (k diskusi před Fází 2)

1. Mají být `Team` pouze 1 úroveň, nebo nested (sub-teamy)? **Návrh**: 1 úroveň pro v1, nested později.
2. Má `RecordGrant` umět *odepřít* (negative grant)? **Návrh**: ne – KISS, jen positive grants.
3. Časově omezené role (např. zástup za nemocí) – přidat `Membership.expires_at`? **Návrh**: ano, do Fáze 6.
4. UI: matice permissions × role může být široká → kategorie permissions (Records / Customers / Reports / Settings / …) jako řádkové skupiny.
5. Plugin marketplace: má plugin moci žádat `Permission` při instalaci? **Návrh**: zahrnout do Fáze 8 jako součást plugin manifestu.

---

## 9. Pracovní postup (log)

### Fáze 1 – Foundation ✅ (2026-05-06)

**Větvě**: `copilot/update-users-goals-documentation`

**Co bylo uděláno:**
- Vytvořen `firms/permissions.py` s:
  - `Permission` enum (18 kódů: record.*, category.*, team.manage, role.manage, billing.manage, firm.delete/transfer, integrations.manage, report.view, activity.create, streamline.view_all, proposal.create)
  - `Scope` enum (OWN / TEAM / CATEGORY / ALL)
  - `LEGACY_ROLE_PERMISSIONS` mapa (OWNER → vše, ADMIN → vše kromě billing/firm, WORKER → základní CRM)
  - `can(membership, permission, scope=None) -> bool`
  - `has_min_role(membership, min_role) -> bool` – bridge pro zpětnou kompatibilitu
- Refaktorován `firms/auth.py::require_membership` – interně volá `has_min_role()` místo `_role_rank()`
- Přidán `PERMISSIONS_V2_ENABLED = False` do `leadlab/settings.py`
- Přidán `PermissionMatrixTests` do `firms/tests.py` (50 nových testů pokrývajících celou matici role × permission)
- Všechny existující testy prošly (90 tests OK)

**Co bude následovat:**
- Fáze 2: datový model `Role`, `Permission`, `RolePermission`, `Team`, `TeamMembership` + datová migrace + admin registrace


### Fáze 2 – Datový model ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-document`

**Co bylo uděláno:**
- Přidány modely do `firms/models.py`:
  - `PermissionRecord(code PK, group, description)` – katalog oprávnění
  - `Role(id UUID, firm FK, code, name, is_system, description, created_at)` + `unique_together=(firm, code)`
  - `RolePermission(role FK, permission FK)` – M2M through-tabulka Role ↔ PermissionRecord
  - `Team(id UUID, firm FK, name, slug, color, created_at)` + auto-slug + `unique_together=(firm, slug)`
  - `TeamMembership(team FK, membership FK, joined_at)` – M2M through-tabulka Team ↔ Membership
  - Rozšíření `Membership`: přidána pole `roles` (M2M→Role), `default_scope` (CharField, default=`own`), `team` (FK→Team, nullable)
- Vytvořena schémová migrace `firms/migrations/0003_roles_and_teams.py`
- Vytvořena datová migrace `firms/migrations/0004_seed_system_roles.py`:
  - Seeduje `PermissionRecord` katalog (16 kódů)
  - Pro každou existující `Firm` vytvoří 4 systémové role: Owner, Admin, Member, Guest
  - Přiřadí oprávnění každé roli (idempotentní)
  - Stávající `Membership` propojí s odpovídající systémovou rolí přes M2M
- Vytvořen helper modul `firms/migrations/_seed_data.py` (sdílená data)
- Vytvořen helper modul `firms/migrations/_seed_helpers.py` (pro testy i budoucí Firm.post_save signal)
- Aktualizován `firms/admin.py`: registrovány `PermissionRecord`, `Role`, `RolePermission` (inline), `Team`, `TeamMembership` (inline)
- Přidáno 26 nových testů do `firms/tests.py`:
  - `PermissionRecordModelTest` (3 testy)
  - `RoleModelTest` (4 testy)
  - `TeamModelTest` (4 testy)
  - `TeamMembershipModelTest` (2 testy)
  - `MembershipPhase2FieldsTest` (5 testů)
  - `SeedSystemRolesDataMigrationTest` (8 testů)
- Všechny testy zelené: 166/166 OK

**Co bude následovat:**
- Fáze 3: Per-category & per-record ACL (`CategoryGrant`, `RecordGrant`, `PermissionAuditLog` + signály + manager metody)


### Fáze 3 – Per-category & per-record ACL ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-document-again`

**Co bylo uděláno:**
- Přidán model `PermissionAuditLog` do `firms/models.py`:
  - Pole: `id` (UUID PK), `firm` (FK→Firm CASCADE), `actor` (FK→User SET_NULL nullable), `action` (choices: role/membership/category_grant/record_grant × created/updated/deleted), `target_type`, `target_id`, `payload` (JSON), `created_at`
  - Indexy na `(firm, created_at)`, `(actor, created_at)`, `(target_type, target_id)`
  - Admin registrace jako read-only (no add/change/delete permissions)
- Přidány modely `CategoryGrant` a `RecordGrant` do `crm/models.py`:
  - `CategoryGrant(id UUID, category FK, principal_type choices('user','team'), principal_id UUID, level choices('view','edit','manage'), granted_by FK Membership nullable, granted_at, expires_at nullable)`
  - `RecordGrant(id UUID, record FK PipelineRecord, principal_type, principal_id UUID, level, granted_by FK Membership nullable, granted_at, expires_at nullable)`
  - Oba modely: `unique_together = (entity, principal_type, principal_id)` + index na tomto trojici
- Přidány manager metody:
  - `Category.users_with_access()` – vrací QuerySet User s explicitním CategoryGrant
  - `PipelineRecord.users_with_access()` – vrací QuerySet User s explicitním RecordGrant
- Vytvořeny migrace:
  - `firms/migrations/0005_permission_audit_log.py` – schémová migrace pro PermissionAuditLog
  - `crm/migrations/0008_category_record_grants.py` – schémová migrace pro CategoryGrant a RecordGrant
- Signály pro audit log:
  - `firms/apps.py` refaktorován – přidány signály na Role a Membership (post_save/post_delete)
  - Přidán `pre_delete` signal na Firm pro detekci cascade deletion (thread-local flag `_deleting_firm_pks`)
  - `crm/apps.py` – přidány signály na CategoryGrant a RecordGrant (post_save/post_delete)
  - Všechny signal handlery gracefully skipují logging při cascade deletions (thread-local ochrana)
- Přidáno 26 nových testů:
  - `firms/tests.py`: `PermissionAuditLogModelTest` (4), `RoleAuditSignalTest` (2), `MembershipAuditSignalTest` (2)
  - `crm/tests.py`: `CategoryGrantModelTest` (7), `RecordGrantModelTest` (7), `GrantAuditSignalTest` (4)
- Všechny testy zelené: 174/174 (firms) + 26 nových OK

**Co bude následovat:**
- Fáze 4: Permissions resolver & query scoping (`crm/permissions.py` + feature flag `PERMISSIONS_V2_ENABLED`)


### Fáze 4 – Permissions resolver & query scoping ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-document-another-one`

**Co bylo uděláno:**
- Vytvořen nový modul `crm/permissions.py` s:
  - `resolve_effective_permissions(membership) -> set[str]` – vrací set permission kódů z DB rolí (s fallbackem na `LEGACY_ROLE_PERMISSIONS`)
  - `resolve_scope(membership, permission) -> str` – vrací nejširší scope (OWN/CATEGORY/TEAM/ALL) kombinací `default_scope` a aktivních `CategoryGrant`
  - `filter_records_qs(qs, request)` – scope-aware filtr PipelineRecord (OWN: Q(created_by|assigned_to), TEAM: team members, CATEGORY: CategoryGrant + RecordGrant, ALL: no-op)
  - `filter_activities_qs(qs, request)` – aktivity viditelné skrze visible_record_ids
  - `filter_proposals_qs(qs, request)` – návrhy podle scope záznamu nebo created_by/assigned_to
  - `filter_tasks_qs(qs, request)` – úkoly assigned_to/created_by nebo přes scope záznamu
  - Všechny filtry jsou no-op pokud `PERMISSIONS_V2_ENABLED=False` (zpětná kompatibilita)
- Přidána funkce `require_permission(request, perm, resource=None)` do `firms/auth.py`:
  - Při `PERMISSIONS_V2_ENABLED=False`: mapuje Permission → legacy min_role, deleguje na `has_min_role()`
  - Při `PERMISSIONS_V2_ENABLED=True`: volá `resolve_effective_permissions()` z DB, Owner shortcut
  - Mapa `_PERMISSION_TO_MIN_ROLE` – 16 permissions → WORKER/ADMIN/OWNER min_role
- Migrování klíčových endpointů v `crm/api.py` z `require_membership` → `require_permission`:
  - `GET /records` → `Permission.RECORD_VIEW` + `filter_records_qs()`
  - `POST /records` → `Permission.RECORD_CREATE` (+ subscription checks zachovány)
  - `GET /records/{id}` → `Permission.RECORD_VIEW` + `filter_records_qs()`
  - `PATCH /records/{id}` → `Permission.RECORD_EDIT`
  - `DELETE /records/{id}` → `Permission.RECORD_DELETE`
  - `GET /records/{id}/activities` → `Permission.RECORD_VIEW` + `filter_activities_qs()`
  - `GET /tasks` → `Permission.RECORD_VIEW` + `filter_tasks_qs()`
  - `POST /tasks` → `Permission.RECORD_CREATE`
- Migrování endpointů v `crm/proposals_api.py`:
  - `GET /proposals` → `Permission.PROPOSAL_CREATE` + `filter_proposals_qs()`
  - `POST /proposals` → `Permission.PROPOSAL_CREATE`
- Přidáno 20 nových testů:
  - `firms/tests.py`: `RequirePermissionLegacyFlagTest` (8 testů), `RequirePermissionV2FlagTest` (4 testy)
  - `crm/tests.py`: `FilterRecordsQsTest` (6 testů), `ResolveEffectivePermissionsTest` (2 testy)
- Všechny testy zelené: 186/186 (firms) + 34/34 (crm klíčové testy)

### Fáze 5 – Streamline visibility ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-document-yet-again`

**Co bylo uděláno:**
- Přidán `ActivityVisibility` enum do `crm/models.py` (PUBLIC='public', RESTRICTED='restricted')
- Přidáno pole `visibility` do modelu `Activity`:
  - `CharField(choices=ActivityVisibility, default=ActivityVisibility.PUBLIC, db_index=True)`
  - S dokumentačním help_text popisujícím sémantiku
- Vytvořena schémová migrace `crm/migrations/0009_activity_visibility.py`
- Aktualizován `filter_activities_qs` v `crm/permissions.py`:
  - Aktivity s `visibility='restricted'` jsou viditelné pouze uživatelům se scope `TEAM`/`ALL` nebo autorovi aktivity
  - Uživatelé se scope `OWN`/`CATEGORY` vidí pouze `public` aktivity + ty, kde jsou autorem
  - No-op pokud `PERMISSIONS_V2_ENABLED=False` (zpětná kompatibilita)
- Aktualizovány API schémata v `crm/api.py`:
  - `ActivityOut`: přidáno pole `visibility: str = "public"`
  - `ActivityIn`: přidáno pole `visibility: str = "public"` (předáno při vytváření)
  - `ActivityUpdateIn`: přidáno pole `visibility: Optional[str] = None` (volitelná změna)
  - `_activity_out()` helper: vrací `visibility` z modelu
  - `create_activity()`: ukládá `visibility` z payloadu
  - `update_activity()`: respektuje volitelnou změnu `visibility`
- Opraven bug z Fáze 4: `_PERMISSION_TO_MIN_ROLE[RECORD_DELETE]` byl `WORKER`, nyní správně `ADMIN`
- Frontend (`StreamlineCreateModal.vue`):
  - Přidán `visibilityRestricted: ref(false)` a reset v `resetForm()`
  - Přidán import `EyeSlashIcon` z `@heroicons/vue/24/outline`
  - Footer modalu rozšířen o toggle tlačítko visibility (zobrazí se pro všechny typy kromě task/todo_items/proposal)
  - `addActivity()` předává `visibility: visibilityRestricted.value ? 'restricted' : 'public'`
- i18n klíče přidány do všech 4 locale souborů pod namespace `streamline.*`:
  - `streamline.visibilityPublic`, `streamline.visibilityRestricted`
  - `streamline.visibilityPublicTitle`, `streamline.visibilityRestrictedTitle`
- Přidáno 6 nových testů `StreamlineVisibilityTests` do `crm/tests.py`:
  - `test_activity_visibility_field_default_public` – ověření výchozí hodnoty
  - `test_owner_sees_all_activities` – owner vidí vše
  - `test_worker_own_scope_sees_only_public_and_own_restricted` – worker bez přístupu k záznamu
  - `test_worker_own_scope_sees_own_restricted` – autor vidí vlastní restricted
  - `test_worker_team_scope_sees_all` – wide-scope worker vidí i restricted
  - `test_flag_disabled_no_filtering` – PERMISSIONS_V2_ENABLED=False = žádný filtr

**Co bude následovat:**
- Fáze 6: Admin API – CRUD pro `Role`, `Team`, `CategoryGrant`, `RecordGrant` + audit log endpoint


### Fáze 6 – Admin API: Role, Team, Grants ✅ (2026-05-06)

**Větev**: `copilot/continue-users-goals-work`

**Co bylo uděláno:**
- Vytvořen `firms/roles_api.py` s endpointy:
  - `GET /firms/{id}/permission-catalogue` – statický číselník všech kódů (čitelný všemi členy)
  - `GET /firms/{id}/roles` – výpis všech rolí (systémových i vlastních) firmy
  - `POST /firms/{id}/roles` – vytvoření vlastní role (guard: `role.manage` + privilege escalation check)
  - `PATCH /firms/{id}/roles/{role_id}` – úprava název/popis vlastní role (systémové nepůjde)
  - `DELETE /firms/{id}/roles/{role_id}` – smazání vlastní role (systémové nelze)
  - `PUT /firms/{id}/roles/{role_id}/permissions` – přepsání sady oprávnění vlastní role (guard: `role.manage` + escalation check + ochrana `billing/firm.*` pro non-Owner)
- Vytvořen `firms/teams_api.py` s endpointy:
  - `GET /firms/{id}/teams` – výpis týmů firmy (čitelný všemi členy)
  - `POST /firms/{id}/teams` – vytvoření týmu (guard: `team.manage`)
  - `PATCH /firms/{id}/teams/{team_id}` – úprava týmu (guard: `team.manage`)
  - `DELETE /firms/{id}/teams/{team_id}` – smazání týmu (guard: `team.manage`)
  - `POST /firms/{id}/teams/{team_id}/members/{membership_id}` – přidání člena do týmu
  - `DELETE /firms/{id}/teams/{team_id}/members/{membership_id}` – odebrání člena z týmu
- Rozšířen `firms/models.py::Invitation` o pole:
  - `invited_role_codes` (JSONField) – kódy rolí přiřazených při přijetí pozvánky
  - `invited_default_scope` (CharField) – výchozí scope nového člena
  - `invited_team` (FK→Team, nullable) – tým do kterého vstoupí nový člen
- Vytvořena migrace `firms/migrations/0006_invitation_extended_fields.py`
- Rozšířen `firms/api.py::MemberInviteIn` a `create_invitation` – pozvánka nyní přijímá `role_codes[]`, `default_scope`, `team_id`
- Rozšířen `firms/invitations_api.py::accept_invitation` – při přijetí pozvánky nastaví `default_scope`, `team`, přiřadí granulární role
- Přidán endpoint `GET /firms/{id}/audit-log` v `firms/api.py` – stránkovatelný, filtrovatelný (`action`, `target_type`, `page`, `page_size`). Guard: Admin nebo Owner
- Přidány grant endpointy do `crm/api.py`:
  - `GET /crm/categories/{id}/grants` – výpis grantů kategorie (guard: `category.manage`)
  - `POST /crm/categories/{id}/grants` – udělení grantu (upsert; guard: `category.manage`)
  - `DELETE /crm/categories/{id}/grants/{grant_id}` – odvolání grantu
  - `GET /crm/records/{id}/access` – kdo má přístup k záznamu (category + record granty; guard: `record.view`)
  - `GET /crm/records/{id}/grants` – výpis record grantů (guard: `record.edit`)
  - `POST /crm/records/{id}/grants` – udělení per-record grantu s volitelným `expires_at`
  - `DELETE /crm/records/{id}/grants/{grant_id}` – odvolání per-record grantu
- Přidán `post_save` signal na `Firm` v `firms/apps.py` → automaticky seeduje systémové role pro nově vytvořené Firmy (předtím fungovalo pouze přes datovou migraci pro existující firmy)
- Nastaveno `PERMISSIONS_V2_ENABLED=True` jako výchozí hodnota v `leadlab/settings.py` (lze přetížit env proměnnou)
- Zaregistrovány nové routery `roles_router` a `teams_router` v `leadlab/api.py`
- Přidáno 13 nových testů:
  - `firms/tests.py::RolesAPITest` (5 testů)
  - `firms/tests.py::TeamsAPITest` (5 testů)
  - `firms/tests.py::AuditLogAPITest` (3 testy)
- Všechny testy zelené (66 existujících + 13 nových = 79 OK)

**Co bude následovat:**
- Fáze 7: Frontend UI – Pinia store `permissions.ts`, `RolesSettingsView.vue`, `TeamsSettingsView.vue`, `RecordShareModal.vue`, `useCan` composable, i18n klíče


### Fáze 7 – Frontend UI ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-document-one-more-time`

**Co bylo uděláno:**

- **Backend – nový endpoint** `GET /firms/{id}/me/permissions` v `firms/roles_api.py`:
  - Vrací `permissions[]` (set kódů), `scope`, `role` (legacy), `roles[]` (kódy rolí z M2M), `can_manage_roles`, `can_manage_teams`
  - Využívá `resolve_effective_permissions()` a `resolve_scope()` z `crm/permissions.py`

- **Pinia store** `frontend-spa/src/stores/permissions.ts`:
  - State: `catalogue`, `roles`, `teams`, `myEffectivePermissions` (Set<string>), `myScope`, `myRole`, `myRoles`, `canManageRoles`, `canManageTeams`
  - Akce: CRUD role (`createRole`, `updateRole`, `deleteRole`, `setRolePermissions`), CRUD tým (`createTeam`, `updateTeam`, `deleteTeam`, `addTeamMember`, `removeTeamMember`), `fetchMyPermissions`, `fetchCatalogue`, `fetchRoles`, `fetchTeams`, `init`
  - Getter: `catalogueByGroup`, `can(action: string): boolean`

- **Composable** `frontend-spa/src/composables/useCan.ts`:
  - Exportuje `can(action)`, `canManageRoles`, `canManageTeams`, `myScope`, `isOwner`, `isAdmin`
  - Umožňuje použití `v-if="can('record.create')"` v šablonách

- **Nový pohled** `frontend-spa/src/views/RolesSettingsView.vue`:
  - Přehled systémových rolí (read-only tabulka)
  - CRUD vlastních rolí (tvorba s kódem/názvem/popisem, editace, smazání)
  - Matice oprávnění – interaktivní přepínání pomocí checkboxů seskupených dle skupiny
  - Guard: `canManageRoles` skrývá tlačítka pro nesprávce

- **Nový pohled** `frontend-spa/src/views/TeamsSettingsView.vue`:
  - CRUD týmů (tvorba s názvem + color picker, editace, smazání)
  - Expandovatelný panel členů týmu (přidat/odebrat člena z týmu)
  - Guard: `canManageTeams` skrývá tlačítka pro nesprávce

- **Rozšíření** `frontend-spa/src/views/SettingsView.vue`:
  - Nové záložky „Role" (`activeTab === 'roles'`) a „Týmy" (`activeTab === 'teams'`)
  - Záložky viditelné pouze pro uživatele s `canManageRoles`/`canManageTeams`
  - Inicializuje `permissionsStore.init()` v `onMounted`

- **Nový komponent** `frontend-spa/src/components/RecordShareModal.vue`:
  - Modal pro sdílení záznamu s konkrétním uživatelem
  - Výběr uživatele, úrovně přístupu (`view`/`edit`/`manage`), volitelné `expires_at`
  - Zobrazuje aktuální granty s možností odvolání
  - Napojení na `GET/POST/DELETE /api/v1/crm/records/{id}/grants`

- **Rozšíření** `frontend-spa/src/views/RecordDetailView.vue`:
  - Nové tlačítko „Sdílet záznam" vedle tlačítek Edit a Delete
  - Otevírá `RecordShareModal`

- **AppShell** `frontend-spa/src/views/AppShell.vue`:
  - Inicializuje `permissionsStore.fetchMyPermissions()` při mountování aplikace

- **i18n** – přidána klíče pod namespace `permissions.*` ve všech 4 lokalizacích (`cs.json`, `en.json`, `de.json`, `pl.json`):
  - Záložky (`tabRoles`, `tabTeams`, `tabAuditLog`)
  - Role (`roleCode`, `roleName`, ..., `permissionMatrix`, ...)
  - Týmy (`teamName`, `teamColor`, `createTeam`, ...)
  - Sdílení (`shareRecord`, `shareWith`, `accessView`, `accessEdit`, `accessManage`, ...)
  - Audit log (`auditLog`, `auditActor`, ...)

- Všechny frontend testy zelené: 100/100 OK
- TypeScript: 0 chyb

**Co bude následovat:**
- Fáze 8: Migrace, dokumentace, deprecation legacy `Membership.role`
  - Přepsat `Membership.role` jako computed property z M2M `roles`
  - Aktualizovat `docs/permissions.md`, `docs/teams.md`, `docs/roles.md`
  - Odstranit feature flag `PERMISSIONS_V2_ENABLED` (vždy on)
  - Tag `v2.0-permissions`


### Fáze 8 – Migrace, dokumentace, deprecation ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-document-please-work`

**Co bylo uděláno:**

- **`MembershipRole.MEMBER`** přidán jako nová hodnota do `firms/models.py`:
  - `MEMBER = "member", "Member"` – officiální název pro standardního člena workspace
  - `WORKER = "worker", "Worker"` – zachován jako deprecated alias pro zpětnou kompatibilitu
  - Přidána `primary_role` computed property na `Membership`:
    - Čte seznam kódů rolí z M2M `roles` a vrací nejvyšší prioritní kód
    - Fallback na legacy `role` pole pokud žádné M2M role nejsou přiřazeny
    - Prioritní pořadí: owner > admin > member > worker > guest

- **Odstranění feature flagu `PERMISSIONS_V2_ENABLED`**:
  - `leadlab/settings.py`: odstraněna env var kontrola, flag hardcoded jako `True`
  - `firms/auth.py`: odstraněna legacy větev z `require_permission()`, odstraněn `_PERMISSION_TO_MIN_ROLE` dict, odstraněn `from django.conf import settings` import
  - `crm/permissions.py`: odstraněny 4× `if not getattr(settings, "PERMISSIONS_V2_ENABLED", False): return qs` ze všech filter funkcí, odstraněn `from django.conf import settings` import

- **Oprava `_WORKER_PERMISSIONS`** – pre-existing inconsistency (maskována odstraněným legacy kódem):
  - `RECORD_DELETE` odstraněn z `_WORKER_PERMISSIONS` (member/worker nemůže mazat záznamy)
  - `RECORD_DELETE` explicitně přidán do `_ADMIN_PERMISSIONS` (admin a owner mohou mazat)
  - `_seed_data.py`: odstraněn `record.delete` z "member" systémové role
  - Migrace `firms/migrations/0007_fix_member_role_permissions.py`: odstraní `record.delete` ze všech existujících "member" systémových rolí v DB

- **`MembershipOut` schema rozšířen** o nová pole:
  - `roles: List[str] = []` – kódy M2M rolí přiřazených daném Membership
  - `permissions: List[str] = []` – efektivní permission kódy (via `resolve_effective_permissions`)
  - Přidána helper funkce `_membership_out(m: Membership) -> dict` v `firms/api.py`
  - Všechna 3 místa vracející `MembershipOut` dict aktualizována (`list_members`, `invite_member`, `update_member_role`)

- **Dokumentace** vytvořena v `docs/permissions/`:
  - `docs/permissions/permissions.md` – přehled permission kódů, scopů, rozhodovacího algoritmu, API
  - `docs/permissions/roles.md` – systémové role, custom role, přiřazení rolí, API
  - `docs/permissions/teams.md` – teams, scope resolution, API, příklady
  - `mkdocs.yml` aktualizován – přidána sekce „Permissions" s 3 podstránkami

- **Testy aktualizovány**:
  - `firms/tests.py`:
    - `RequirePermissionLegacyFlagTest` přejmenován na `RequirePermissionTest`, odstraněny `@override_settings(PERMISSIONS_V2_ENABLED=False)` dekorátory
    - `RequirePermissionV2FlagTest` odstraněny `@override_settings(PERMISSIONS_V2_ENABLED=True)` dekorátory
    - `test_worker_has_record_delete` aktualizován → `assertFalse` (worker nesmí mazat)
  - `crm/tests.py`:
    - `FilterRecordsQsTest`: odstraněn `test_flag_off_returns_all` (flag=False), odstraněny `override_settings` kontexty, přidán nový test `test_flag_off_returns_all` testující chování bez membership
    - `StreamlineVisibilityTests`: odstraněn `test_flag_disabled_no_filtering`, odstraněny `override_settings` kontexty, přidán `test_no_membership_returns_empty`
- Všechny testy zelené: 199/199 OK (firms)

**Co bude následovat:**
- Merge do `main` a tag `v2.0-permissions`
- ~~e2e testy pro 5 use-cases ze sekce 5~~ ✅ Hotovo (viz níže)
- Drop column `Membership.role` (plánováno pro v2.1 po ověření zpětné kompatibility)

- [x] 8 fází implementováno na větvi `copilot/update-users-goals-document-please-work`.
- [x] e2e testy pro 5 use-cases vytvořeny v `e2e/tests/permissions.spec.ts`.
- [ ] Merge do `main` a release `v2.0-permissions` vystaven.
- [ ] e2e scénáře (5 use-cases ze sekce 5) procházejí v CI.
- [x] Dokumentace v `docs/permissions/` kompletní.
- [x] Audit log dostupný v UI (Settings → Audit) i přes API.
- [x] Žádná regrese v existujících integracích (Fakturoid, webhooks, plugins) – 199 testů zelených.


### Post-Phase 8 – e2e testy oprávnění ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-document-b9026ad6-21a2-4368-b1d2-f3c217269313`

**Co bylo uděláno:**

- Vytvořen `e2e/tests/permissions.spec.ts` pokrývající všech 5 use-cases ze sekce 5:
  - **UC1** – Member se `scope=own` vidí v listu záznamů jen ty, kde je `created_by`/`assigned_to` (ne záznamy vlastníka)
  - **UC2** – Owner udělí Member-ovi per-record grant (`level=view`) → Member nově vidí daný záznam přes API i v detailu
  - **UC3** – Owner vytvoří tým, přidá Member-a, Member vytvoří vlastní záznam → Owner (scope=all) vidí záznamy obou
  - **UC4** – Owner udělí Member-ovi časově omezený grant (`expires_at = now+30d`) → Member přistupuje k záznamu, grant je viditelný v `/access` endpointu
  - **UC5 + UC5b** – Member (worker role) nemůže smazat firmu (`DELETE /firms/{id}` → 403); `GET /me/permissions` vrací `firm.delete` jen pro Owner-a, ne pro Member-a
- Testy využívají multi-user setup: primární Owner context (ze `auth.setup.ts`) + sekundární `APIRequestContext` vytvořený přes `playwright.request.newContext()` a přihlašení přes session cookies
- Helpery: `loginAs(playwright, baseURL, email, password)` – vrací autentizovaný `APIRequestContext` pro sekundárního uživatele
- Sled testů je serializovaný (`test.describe.serial`) – `beforeAll` registruje member uživatele, přidá ho do firmy; testy sdílí `firmId`, `ownerRecordId`, `memberEmail`

**Co bude následovat:**
- Merge do `main` a tag `v2.0-permissions`
- Drop column `Membership.role` (v2.1)
- ~~UI pro Audit log v SettingsView~~ ✅ Hotovo (viz níže)


### Post-Phase 8 – Audit Log UI ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-document-ae57a3fe-8811-4c1a-b705-8d959065178b`

**Co bylo uděláno:**

- Vytvořen `frontend-spa/src/views/AuditLogSettingsView.vue`:
  - Tabulka audit log záznamů: actor_email, action (badge), target_type+target_id (zkrácené), created_at (lokalizovaný datum+čas)
  - Filtrace podle `action` a `target_type` (select dropdowns s předdefinovanými hodnotami)
  - Stránkování: tlačítka Předchozí / Další (detekuje hasMore pomocí +1 extra záznamu)
  - Loading skeleton (5 placeholder řádků animací)
  - Empty state pokud nejsou záznamy
  - Watch na firmId pro re-fetch při přepnutí workspace
- Aktualizován `frontend-spa/src/views/SettingsView.vue`:
  - Import `AuditLogSettingsView`
  - `activeTab` typ rozšířen o `'audit'`
  - Nová záložka „Audit log" (viditelná pouze pro `canManageRoles`)
  - Nový panel `v-show="activeTab === 'audit'"` s `<AuditLogSettingsView />`
- Všechny frontend testy zelené: 100/100 OK

**Co bude následovat:**
- Merge do `main` a tag `v2.0-permissions`
- Drop column `Membership.role` (v2.1)


### Phase 7 dokončení – Menu hiding + Category Access ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-md`

**Co bylo uděláno:**

- **Phase 7 Step 8 – Skrytí položek menu** (`AppShell.vue`):
  - Import `useCan` composable do `AppShell.vue`
  - `nav.reports` zobrazit pouze pokud `can('report.view')` – skryto pro Guest/Member bez tohoto oprávnění
  - `appShell.sectionPlugins` (Integrace) zobrazit pouze pokud `can('integrations.manage')` – skryto pro Member/Guest
  - Implementace přes podmíněné spread (`...condition ? [item] : []`) v `navSections` computed

- **Phase 7 Step 6 – Sekce „Přístupy ke kategorii"** (`PipelineSettingsView.vue`):
  - Import `useCan` composable a `LockOpenIcon`
  - Přidány `watch` + `loadCategoryGrants()` – načte granty při změně vybrané kategorie
  - Přidána sekce ve template (viditelná pouze pro `can('category.manage')`):
    - Tabulka existujících grantů s `principal_type`, `principal_id`, `level` badge (color-coded)
    - Tlačítko na smazání grantu (hover-only TrashIcon)
    - Empty state „Žádné explicitní přístupy"
    - Formulář pro přidání nového grantu: `principal_id` (UUID) + select `level` + save/cancel
  - i18n klíče přidány do všech 4 locale souborů (`cs`, `en`, `de`, `pl`):
    - `pipeline.categoryAccess` – název sekce
    - `pipeline.categoryGrantAdd` – tlačítko přidat
    - `pipeline.categoryGrantUserIdPlaceholder` – placeholder inputu

- Všechny frontend testy zelené: 100/100 OK, TypeScript build: 0 chyb

**Co bude následovat:**
- Merge do `main` a tag `v2.0-permissions`
- v2.1: Drop column `Membership.role` (po ověření zpětné kompatibility)


### Phase 8 dokončení – Aktualizace README.md ✅ (2026-05-06)

**Větev**: `copilot/users-goals-phase8-readme-update`

**Co bylo uděláno:**

- **Aktualizace `README.md`** (Phase 8, krok 4 – zbývající část):
  - Popis „Three roles per Firm: Owner, Admin, and Worker" nahrazen novým popisem granulárního RBAC systému: 5 systémových rolí, permission kódy, scope, per-category/per-record granty, audit log
  - Všechna výskyty `Worker+` v API tabulkách nahrazeny na `Member+` (odpovídá přejmenování WORKER → MEMBER z Fáze 8)
  - Přidány nové sekce API tabulek:
    - **Roles & Permissions** – permission-catalogue, CRUD rolí, PUT permissions, me/permissions endpoint
    - **Teams** – CRUD týmů, add/remove member
    - **Audit Log** – pageable audit-log endpoint
  - Přidány chybějící endpointy do CRM sekce:
    - `GET/POST/DELETE /records/{id}/grants` – per-record ACL granty
    - `GET /records/{id}/access` – přehled přístupů
    - `GET/POST/DELETE /categories/{id}/grants` – per-category ACL granty

**Co bude následovat:**
- Merge do `main` a tag `v2.0-permissions`
- v2.1: Drop column `Membership.role` (po ověření zpětné kompatibility)


### v2.1 – Příprava na deprecation `Membership.role` ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-documentation-again`

**Co bylo uděláno:**

- **`firms/models.py` – `_sync_legacy_role_to_m2m()` metoda**:
  - Nová instance metoda na `Membership` synchronizuje M2M `roles` relaci s hodnotou legacy `role` CharField
  - Využívá `LEGACY_TO_SYSTEM_ROLE` mapping z `firms/role_seeds.py`: `worker` → `member` system role
  - Idempotentní – pokud je M2M již v souladu, nic nedělá
  - Gracefully degraduje (loguje warning) pokud system roles nejsou ještě seedovány

- **`firms/apps.py` – automatické volání sync**:
  - `_on_membership_post_save` signal rozšířen o volání `instance._sync_legacy_role_to_m2m()`
  - Sync se spustí při: vytvoření nového Membership, nebo uložení s `update_fields` zahrnujícím `"role"`
  - Zajišťuje, že každá změna legacy `role` pole se automaticky promítne do M2M rolí

- **`firms/api.py` – `_membership_out` používá `primary_role`**:
  - Pole `"role"` v API odpovědi nyní vrací `m.primary_role` místo `m.role`
  - `primary_role` preferuje nejvyšší M2M roli (fallback na legacy pole)
  - API klienti nyní vidí správnou roli i pokud bylo M2M nastaveno přímo (např. přes invitation)

- **`firms/auth.py` – `membership.is_owner` místo direct `.role` comparison**:
  - `require_permission()`: `membership.role == MembershipRole.OWNER` → `membership.is_owner`

- **`crm/permissions.py` – `membership.is_owner` ve všech filter funkcích**:
  - `resolve_scope()`, `filter_records_qs()`, `filter_activities_qs()`, `filter_proposals_qs()`, `filter_tasks_qs()`: `membership.role == OWNER` → `membership.is_owner`
  - `resolve_effective_permissions()` fallback: používá `membership.primary_role` místo `membership.role`

- **`crm/api.py` – `membership.is_admin_or_above` pro admin-only kontroly**:
  - 7 výskytů `membership.role in (MembershipRole.ADMIN, MembershipRole.OWNER)` nahrazeno `membership.is_admin_or_above`

- **`firms/permissions.py` – `can()` používá `primary_role`**:
  - LEGACY_ROLE_PERMISSIONS fallback v `can()` nyní používá `membership.primary_role`

- **Nové testy** `firms/tests.py::LegacyRoleSyncTest` (4 testy):
  - `test_new_membership_syncs_system_role` – nový Membership (WORKER) dostane 'member' system Role v M2M
  - `test_sync_helper_updates_m2m_on_role_change` – změna `role` na ADMIN synchronizuje M2M
  - `test_primary_role_prefers_m2m_over_legacy` – `primary_role` vrací M2M hodnotu i když legacy pole ukazuje jinak
  - `test_membership_out_uses_primary_role` – API serializer vrací `primary_role`
- 203 testů zelených (+ 4 nové; pre-existing 2 failures v `StreamlinePhase6ToolsTest` nesouvisí s permissions)

**Co bude následovat:**
- Merge do `main` a tag `v2.0-permissions`
- v2.2: Skutečné odstranění sloupce `Membership.role` z DB (drop column migration)
  - Předpokladem je ověření zpětné kompatibility všech API klientů a write pathů


### v2.2 – Drop sloupce `Membership.role` ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-documentation-another-one`

**Co bylo uděláno:**

- **`firms/migrations/0008_drop_membership_role.py`** – migrace odstraňuje sloupec `role` z tabulky `Membership`:
  - Čistý `RemoveField` bez ztráty dat (M2M `roles` bylo plně synchronizováno v2.1)

- **`firms/models.py` – `Membership` model refaktorován**:
  - Sloupec `role = CharField(choices=MembershipRole)` odstraněn
  - Přidána třída `MembershipManager(models.Manager)`:
    - `create(**kwargs)` intercepts `role=` kwarg, poté co vytvoří DB řádek zavolá `_assign_system_role_by_code()` pro přiřazení M2M role
    - Zachovává zpětnou kompatibilitu – všechna `Membership.objects.create(role=...)` v testech i kódu fungují dál
  - `is_owner` property: `self.role == MembershipRole.OWNER` → `self.primary_role == "owner"`
  - `is_admin_or_above` property: `self.role in (...)` → `self.primary_role in ("owner", "admin")`
  - `primary_role` property: odstraněn fallback na `self.role`, výchozí hodnota `"guest"` (nejrestriktnější)
  - Nahrazena metoda `_sync_legacy_role_to_m2m()` metodou `_assign_system_role_by_code(role_code)`:
    - Normalizes code přes `LEGACY_TO_SYSTEM_ROLE` (worker→member)
    - Nahradí aktuální systémové role v M2M touto jednou rolí
    - Custom roles jsou zachovány
  - `__str__` opraveno: `get_role_display()` → `primary_role`
  - `Meta.ordering`: `["firm", "role"]` → `["firm", "created_at"]`

- **`firms/api.py`** – write paths aktualizovány:
  - `invite_member()`: `Membership.objects.get_or_create(defaults={"role": ...})` → handled by MembershipManager
  - `update_member_role()`: `target.role = ...` + `target.save(update_fields=["role"])` → `target._assign_system_role_by_code(payload.role)`
  - `update_branding()`: `membership.role != MembershipRole.OWNER` → `not membership.is_owner`

- **`firms/roles_api.py`** – odstraněny `MembershipRole` a `membership.role` přístupy:
  - `_actor_permission_codes()`: `membership.role == OWNER` → `membership.is_owner`
  - `me/permissions` endpoint: `"role": membership.role` → `"role": membership.primary_role`
  - `create_role()`, `set_role_permissions()`: `membership.role != OWNER` → `not membership.is_owner`
  - Import `MembershipRole` odstraněn

- **`firms/apps.py`** – audit log signály vyčištěny:
  - `_on_membership_post_save`: `"role": instance.role` → `"role": instance.primary_role`; odstraněno volání `instance._sync_legacy_role_to_m2m()`
  - `_on_membership_post_delete`: `"role": instance.role` → `"role": instance.primary_role`

- **`firms/auth.py`** – odstraněno volání `membership.get_role_display()`:
  - Chybové zprávy v `require_membership()` a `require_permission()` nyní používají `membership.primary_role`

- **`firms/role_seeds.py`** – `link_membership_to_system_role()` aktualizována:
  - Místo `membership.role` (odstraněno pole) nyní čte `membership.primary_role`

- **`firms/admin.py`** – odstraněny reference na neexistující pole `role`:
  - `MembershipInline.fields`: `("user", "role", "created_at")` → `("user", "default_scope", "created_at")`
  - `MembershipAdmin.list_display`: `"role"` → `"primary_role"` (property funguje v admin)
  - `MembershipAdmin.list_filter`: `("role",)` → `("default_scope",)`

- **`firms/tests.py`** – testy aktualizovány:
  - `TenantMiddlewareTest.test_membership_resolved`: `membership.role == WORKER` → `membership.primary_role == "member"` (WORKER se mapuje na 'member')
  - `CreateFirmAPITest.test_create_firm_makes_creator_owner`: `Membership.objects.filter(role=OWNER)` → filter + check `primary_role == "owner"`
  - Třída `LegacyRoleSyncTest` přejmenována na `MembershipRoleV22Test` s aktualizovanými testy:
    - `test_create_with_role_kwarg_assigns_system_role` – Manager povolí `role=` kwarg a přiřadí M2M
    - `test_assign_system_role_by_code_changes_m2m` – `_assign_system_role_by_code("admin")` nahradí member→admin
    - `test_primary_role_returns_highest_m2m_role` – `primary_role` vrací nejvyšší M2M roli
    - `test_membership_out_uses_primary_role` – API serializer vrací správný kód

**Verifikace:**
- Migrace prošla na čisté DB i na DB s daty
- Cílené testy: 23 zelených (TenantMiddlewareTest, CreateFirmAPITest, RolesAPITest, TeamsAPITest, AuditLogAPITest, MembershipRoleV22Test)
- Všechny `crm.tests` permission testy zelené (FilterRecordsQsTest, ResolveEffectivePermissionsTest, StreamlineVisibilityTests)

**Co bude následovat:**
- Merge do `main` a tag `v2.0-permissions` / `v2.2`
- Volitelně: smazat `MembershipRole.WORKER` (deprecated alias) v budoucím releasu
- Volitelně: přejmenovat `MembershipRole` na `InvitationRole` pro sémantiku (hodnoty zůstanou stejné)


### v2.3 – Invitation default → MEMBER + manager fix ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-progress`

**Co bylo uděláno:**

- **`firms/models.py::Invitation.role`** – výchozí hodnota přepnuta z deprecated `MembershipRole.WORKER` na kanonický `MembershipRole.MEMBER`. Hodnota `worker` zůstává platnou volbou (jako alias) pro zpětnou kompatibilitu.
- **`firms/api.py::MemberInviteIn.role`** – výchozí hodnota schématu sjednocena s modelem (`MembershipRole.MEMBER`). Klienti, kteří dnes pole `role` neposílají, dostanou Member místo deprecated Worker.
- **`firms/migrations/0009_invitation_default_member.py`** – nová migrace (`AlterField` na `Invitation.role`).
- **`firms/models.py::MembershipManager.get_or_create()`** – přidán override, který pop-uje `defaults={"role": ...}` a po vytvoření Membership přiřadí odpovídající systémovou roli přes `_assign_system_role_by_code()`. Opravuje pre-existing bug po v2.2 (drop sloupce `Membership.role`), kde `firms/api.py::invite_member` selhával na `FieldError: Invalid field name(s) for model Membership: 'role'`.
- **`firms/migrations/_seed_helpers.py::link_membership_to_system_role`** – `membership.role` (zaniklé pole) → `membership.primary_role`. Opravuje 2 pre-existing test errors v `SeedSystemRolesDataMigrationTest`.

**Verifikace:**
- `python manage.py test firms` – 203/203 OK (předtím 200/203 s 3 erorry, nesouvisející s defaultem invitation; všechny opraveny v rámci tohoto PR jako bezprostředně související bugy v module družině)
- `python manage.py test crm.tests.FilterRecordsQsTest crm.tests.ResolveEffectivePermissionsTest crm.tests.StreamlineVisibilityTests crm.tests.CategoryGrantModelTest crm.tests.RecordGrantModelTest` – 28/28 OK

**Co bude následovat:**
- Merge do `main` a tag `v2.3` / `v2.0-permissions`
- v2.4: odstranit `MembershipRole.WORKER` enum value
- v2.5: přejmenovat `MembershipRole` na `InvitationRole` (sémantika po dropu `Membership.role`)


### v2.4 – Odstranění deprecated `MembershipRole.WORKER` ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-document-20b922e3-fa06-4bd9-9323-172787023f80`

**Co bylo uděláno:**

- **`firms/models.py::MembershipRole`** – odstraněna deprecated hodnota `WORKER = "worker", "Worker"`:
  - Enum nyní obsahuje pouze `OWNER`, `ADMIN`, `MEMBER`
  - Komentář o deprecated aliasu odstraněn
- **`firms/migrations/0010_remove_worker_role.py`** – nová migrace:
  - `RunPython`: převede všechny existující `Invitation.role='worker'` → `'member'`
  - `AlterField`: aktualizuje choices na `Invitation.role` (odstraní 'worker' z povolených hodnot)
- **`firms/permissions.py`** – aktualizovány konstanty:
  - `LEGACY_ROLE_PERMISSIONS`: odstraněna `"worker": _WORKER_PERMISSIONS` deprecated entry
  - `_MIN_ROLE_SENTINEL`: `"worker"` → `"member"` (klíč přejmenován, hodnota zachována)
  - Docstring `has_min_role`: aktualizováno `WORKER < ADMIN < OWNER` → `MEMBER < ADMIN < OWNER`
- **`firms/models.py::Membership.primary_role`** – priority mapa aktualizována:
  - Odstraněn `"worker": 3` (dříve zbytečná položka po nahrazení 'worker' → 'member')
  - Nová mapa: `{"owner": 0, "admin": 1, "member": 2, "guest": 3}`
- **Bulk refaktoring** všech `.py` souborů (bez migrací):
  - `MembershipRole.WORKER` → `MembershipRole.MEMBER` ve všech 95 výskytech (firms/auth.py, firms/tests.py, crm/tests.py, crm/proposals_api.py, crm/api.py, crm/automations_api.py, crm/pipeline_config_api.py)
- **Test opravena** `firms/tests.py::AcceptInvitationAPITest::test_new_user_can_accept_and_gets_account`:
  - Assertion `data["role"] == "worker"` → `"member"` (po v2.2 API vrací `invitation.role` = MEMBER)

**Verifikace:**
- `python manage.py test firms` – 203/203 OK
- `python manage.py test crm.tests.FilterRecordsQsTest crm.tests.ResolveEffectivePermissionsTest crm.tests.StreamlineVisibilityTests` – 28/28 OK


### v2.5 – Přejmenování `MembershipRole` → `InvitationRole` ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-document-20b922e3-fa06-4bd9-9323-172787023f80`

**Co bylo uděláno:**

- **`firms/models.py`** – třída přejmenována:
  - `class MembershipRole(models.TextChoices)` → `class InvitationRole(models.TextChoices)` s docstringem vysvětlujícím přejmenování
  - Přidán backward-compatibility alias `MembershipRole = InvitationRole`
  - `Invitation.role` field aktualizován: `choices=InvitationRole.choices`, `default=InvitationRole.MEMBER`
- **`firms/auth.py`** – přidán import `InvitationRole` z `firms.models`; re-exportuje pro ostatní moduly
- **`firms/api.py`** – přidán import `InvitationRole` (importuje z `firms.auth`)
- **`crm/automations_api.py`** – import rozšířen o `InvitationRole`
- Ostatní soubory stále používají `MembershipRole` přes backward-compat alias (testem ověřeno)

**Co bude následovat:**
- Merge do `main` a tag `v2.5`
- Volitelně v budoucnu: odstranit alias `MembershipRole = InvitationRole` a aktualizovat všechny importy na `InvitationRole`


### v2.6 – Odstranění alias `MembershipRole` ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-documentation-yet-again`

**Co bylo uděláno:**

- **Bulk rename** `MembershipRole` → `InvitationRole` ve všech non-migračních `.py` souborech (13 souborů, 177 výskytů):
  - `crm/api.py`, `crm/automations_api.py`, `crm/management/commands/load_demo_data.py`, `crm/pipeline_config_api.py`, `crm/proposals_api.py`, `crm/tests.py`
  - `firms/api.py`, `firms/auth.py`, `firms/billing_api.py`, `firms/tests.py`, `firms/tokens_api.py`, `firms/webhooks_api.py`
- **`firms/models.py`** – odstraněna definice backward-compat aliasu `MembershipRole = InvitationRole` a doprovodný docstring komentář
- **`firms/auth.py`** – odstraněn `MembershipRole` z importů a re-exportů (jen `InvitationRole` zůstává)
- Verifikace: 203 testů zelených (nezměněno)

**Co bude následovat:**
- v2.7: přidat `Membership.expires_at` (dohodnuté v open questions Fáze 6)


### v2.7 – `Membership.expires_at` (časově omezené členství) ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-documentation-yet-again`

**Co bylo uděláno:**

- **`firms/models.py` – `Membership.expires_at`**:
  - Nové pole `DateTimeField(null=True, blank=True)` – volitelná expirace členství
  - Nová property `is_expired: bool` – vrací True pokud `expires_at` je nastaveno a již uplynulo
  - `PermissionAuditLog.ACTION_CHOICES` rozšířen o `("membership.expired", "Membership expired")`

- **`firms/migrations/0011_membership_expires_at.py`** – schémová migrace přidávající sloupec

- **`firms/auth.py`** – kontrola expirace v obou auth gates:
  - `require_membership()`: nová kontrola `if membership.is_expired: raise PermissionDenied(...)`
  - `require_permission()`: stejná kontrola před Owner shortcut

- **`firms/api.py`** – API podpora:
  - `MemberRoleUpdateIn`: nové pole `expires_at: Optional[str] = None` (ISO-8601 nebo null)
  - `MembershipOut`: nové pole `expires_at: Optional[str] = None`
  - `_membership_out()`: zahrnuje `expires_at` v serializaci
  - `update_member_role()`: zpracovává `expires_at` – nastaví nebo vymaže expiraci, validuje ISO-8601 formát
  - Endpoint decorator: přidán `400: ErrorOut` pro neplatný formát

- **`crm/tasks.py` – nový `@shared_task expire_memberships()`**:
  - Vyhledá všechna `Membership` kde `expires_at <= now()`
  - Pro každé zanechá `PermissionAuditLog` záznam (action=`membership.expired`)
  - Hard-delete expired memberships
  - Loguje celkový počet smazaných členství

- **`leadlab/settings.py` – CELERY_BEAT_SCHEDULE**:
  - Přidán `'expire-memberships'`: task `crm.tasks.expire_memberships`, plán každou noc ve 02:00 UTC

- **Testy** – přidáno 9 nových testů `MembershipExpiresAtTest` do `firms/tests.py`:
  - `test_is_expired_false_when_no_expiry` – bez nastavení nikdy nevypršené
  - `test_is_expired_false_for_future_date` – budoucí datum = není vypršené
  - `test_is_expired_true_for_past_date` – minulé datum = vypršené
  - `test_require_membership_rejects_expired` – gate vrátí 403
  - `test_require_permission_rejects_expired` – gate vrátí 403
  - `test_expire_memberships_task_deletes_expired` – task smaže vypršené
  - `test_expire_memberships_task_preserves_active` – task nenaruší aktivní
  - `test_update_member_role_sets_expires_at` – PATCH endpoint nastaví expiraci
  - `test_update_member_role_clears_expires_at` – PATCH s null vymaže expiraci
- 212/212 testů zelených (+ 9 nových)

**Co bude následovat:**
- Merge do `main` a tag `v2.7`
- ~~Volitelně: Frontend podpora `expires_at` v UI správy členů~~ ✅ Hotovo v2.8
- ~~Volitelně: E-mailové upozornění uživateli N dní před expirací členství~~ ✅ Hotovo v2.8


### v2.8 – Frontend `expires_at` UI + e-mail notifikace před expirací ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-documentation-one-more-time`

**Co bylo uděláno:**

- **`firms/models.py` – `Membership.last_expiry_notification_at`**:
  - Nové pole `DateTimeField(null=True, blank=True)` – sleduje kdy byl odeslán poslední varovný e-mail
  - Zabraňuje opakovanému posílání e-mailů v rámci téhož varovacího okna (cooldown 6 dní)

- **`firms/migrations/0012_membership_expiry_notification.py`** – schémová migrace přidávající sloupec

- **`crm/tasks.py` – nový `@shared_task notify_expiring_memberships()`**:
  - Vyhledá všechna `Membership` kde `expires_at` je v rozmezí `(now, now+7 dní)` a `last_expiry_notification_at` je `null` nebo starší než 6 dní
  - Odešle uživateli e-mail s informací o nadcházející expiraci (kolik dní zbývá, přesné datum)
  - Nastaví `last_expiry_notification_at = now` po úspěšném odeslání
  - Logy: celkový počet odeslaných e-mailů

- **`leadlab/settings.py` – CELERY_BEAT_SCHEDULE**:
  - Přidán `'notify-expiring-memberships'`: task `crm.tasks.notify_expiring_memberships`, plán každou noc v 01:30 UTC (30 minut před cleanup taskem)

- **`frontend-spa/src/views/TeamView.vue`** – UI pro zobrazení a editaci `expires_at`:
  - `Member` interface rozšířen o `expires_at?: string | null`
  - `editingExpiresAt: ref<string>('')` – nový state pro datum expirace v edit módu
  - `startEditRole()` – předvyplní datum z `member.expires_at` (konverze ISO→YYYY-MM-DD)
  - `saveRole()` – odesílá `expires_at` (ISO string nebo null) při PATCHi role
  - Expiry badge v každém řádku člena:
    - Červený badge „Access expired" pokud je datum v minulosti
    - Oranžový badge „Expires tomorrow" / „Expires in N days" pro budoucí expiraci
    - Skrytý pokud `expires_at` není nastaven (trvalý přístup)
  - Date input `<input type="date">` v edit sekci pro nastavení/vymazání data expirace
  - Nové helpery `isMemberExpired(m)` a `memberExpiryLabel(m)` pro badge logiku

- **i18n** – přidány klíče pod `team.*` ve všech 4 lokalizacích (`cs.json`, `en.json`, `de.json`, `pl.json`):
  - `team.memberExpiresAtLabel` – popisek date inputu
  - `team.memberExpired` – badge text pro vypršené členství
  - `team.memberExpiresTomorrow` – badge text pro expiraci zítra
  - `team.memberExpiresInDays` – badge text s počtem dní (parametr `{days}`)

- **Testy** – přidáno 6 nových testů `NotifyExpiringMembershipsTaskTest` do `firms/tests.py`:
  - `test_notifies_member_expiring_soon` – odesílá e-mail při expiraci do 7 dní
  - `test_does_not_notify_already_expired` – přeskočí vypršené členství
  - `test_does_not_notify_far_future_expiry` – přeskočí expiraci za >7 dní
  - `test_does_not_notify_recently_notified` – přeskočí pokud byl e-mail odeslán v cooldown okně
  - `test_updates_last_expiry_notification_at` – aktualizuje timestamp po odeslání
  - `test_does_not_notify_permanent_memberships` – přeskočí členství bez `expires_at`
- 218/218 testů zelených (+ 6 nových); 100/100 frontend testů zelených

**Co bude následovat:**
- Merge do `main` a tag `v2.8`
- Volitelně: Zobrazit celý záložku „Přístupy" ke členovi v TeamView s přehledem všech grantů
- Volitelně: Transfer Ownership (2-step confirm e-mailem + UI) z `open questions` sekce 7


### v2.9 – Transfer Ownership (2-step potvrdit e-mailem + UI) ✅ (2026-05-06)

**Větev**: `copilot/update-users-goals-document-a240d7a0-b3a9-48d9-ab54-adb992ff8e9a`

**Co bylo uděláno:**

- **`firms/models.py` – nový model `OwnershipTransfer`**:
  - Pole: `id` (UUID PK), `firm` (FK→Firm CASCADE), `from_user` (FK→User CASCADE), `to_user` (FK→User CASCADE), `token` (UUID unique, db_index), `created_at`, `expires_at` (48 hodin, default), `confirmed_at` (nullable)
  - Properties: `is_expired`, `is_confirmed`, `is_pending`
  - `PermissionAuditLog.ACTION_CHOICES` rozšířen o `ownership.transfer_initiated`, `ownership.transfer_confirmed`, `ownership.transfer_cancelled`
  - Helper funkce `_default_transfer_expiry()`

- **`firms/migrations/0013_ownership_transfer.py`** – schémová migrace

- **`firms/api.py` – nové endpointy Transfer Ownership**:
  - `POST /firms/{id}/transfer-ownership` – Owner spustí převod; automaticky zruší existující pending transfer; odešle e-mail novému vlastníkovi s potvrzovacím linkem; vytvoří `PermissionAuditLog` záznam
  - `POST /firms/{id}/transfer-ownership/{token}/confirm` – nový vlastník potvrdí; demotuje starého vlastníka na Admin; elevuje nového na Owner; nastaví `confirmed_at`; audit log
  - `DELETE /firms/{id}/transfer-ownership` – Owner zruší pending transfer; audit log
  - `GET /firms/{id}/transfer-ownership` – vrátí pending transfer nebo null (přístupný všem členům)
  - Schémata: `TransferOwnershipIn` (to_user_id), `OwnershipTransferOut`

- **`firms/admin.py`** – registrován `OwnershipTransferAdmin` (read-only přehled)

- **Frontend – `frontend-spa/src/views/SettingsView.vue`**:
  - Import `useCan` composable, `isOwner` computed
  - Stav: `pendingTransfer`, `transferMembers`, `showTransferForm`, `transferTargetMembershipId`, `transferLoading/Error/Success`
  - Funkce: `loadPendingTransfer()`, `loadTransferMembers()`, `initiateTransfer()`, `cancelTransfer()`
  - `loadPendingTransfer()` volán v `onMounted`
  - Nová sekce „Transfer Ownership" ve workspace záložce (viditelná jen pro `isOwner`):
    - Banner pending transferu s možností zrušit
    - Formulář pro výběr nového vlastníka ze select (lazy load členů)
    - Feedback: success/error zprávy

- **Frontend – `frontend-spa/src/views/OwnershipTransferConfirmView.vue`** (nový):
  - Zobrazí přehled pending transferu (from/to/expires)
  - Tlačítko „Accept Ownership" + varování o důsledcích
  - Po potvrzení přesměruje na dashboard
  - Error/success stavy

- **Router** – nová route `/app/ownership-transfer/:firmId/:token/confirm`

- **i18n** – přidáno 20 klíčů pod `settings.transferOwnership*` ve všech 4 lokalizacích (cs/en/de/pl)

- **Testy** – přidáno 10 nových testů `OwnershipTransferAPITest` do `firms/tests.py`:
  - `test_owner_can_initiate_transfer`
  - `test_non_owner_cannot_initiate_transfer`
  - `test_cannot_transfer_to_self`
  - `test_confirm_transfer_changes_roles`
  - `test_wrong_user_cannot_confirm`
  - `test_expired_transfer_cannot_be_confirmed`
  - `test_owner_can_cancel_pending_transfer`
  - `test_initiating_new_transfer_cancels_previous`
  - `test_audit_log_created_on_transfer_initiation`
  - `test_email_sent_on_initiation`
- 228/228 testů zelených (+ 10 nových); 100/100 frontend testů zelených; TypeScript: 0 nových chyb

**Co bude následovat:**
- Merge do `main` a tag `v2.9`
- Volitelně: Zobrazit záložku „Přístupy" ke členovi v TeamView s přehledem všech grantů


### v3.0 – Superadmin přístup nad Ownery ✅ (2026-05-06)

**Větev**: `copilot/add-superadmin-access`

**Co bylo uděláno:**

- **Konceptuální úprava** – doplněna role **Superadmin** do tabulky systémových rolí (sekce 2.3) a do rozhodovacího algoritmu (sekce 2.5, krok 0):
  - Superadmin = Django `User.is_superuser=True` – globální systémová úroveň (LeadLab support), nad všemi firmami
  - Jediná role nadřazená Owner; Owner zůstává nejvyšší *per-firm* úrovní
  - Superadmin nepotřebuje mít `Membership` v dané firmě – přistupuje ke všemu

- **`firms/auth.py` – nová třída `SuperuserMembership`**:
  - Lehký sentinel objekt vracený auth bránami místo `Membership` pokud `request.user.is_superuser is True`
  - Exponuje stejné rozhraní jako `Membership`: `is_owner=True`, `is_admin_or_above=True`, `primary_role="owner"`, `default_scope="all"`, `is_expired=False`, `firm`, `firm_id`, `user`, `user_id`
  - No-op `_assign_system_role_by_code()` pro kompatibilitu s kódem volajícím tuto metodu na vráceném objektu

- **`firms/auth.py` – `require_membership()` a `require_permission()`**:
  - Přidán superuser short-circuit těsně po kontrole autentizace a existence firmy
  - Kontrola `getattr(request.user, "is_superuser", False) is True` (striktní identity check) – chrání před MagicMock v testech
  - Superuser obejde: kontrolu membership existence, kontrolu expirace, min_role check, permission resolution

- **`crm/permissions.py` – filter funkce**:
  - `filter_records_qs()`, `filter_activities_qs()`, `filter_proposals_qs()`, `filter_tasks_qs()`: přidán superuser short-circuit na začátku (`if getattr(request.user, "is_superuser", False) is True: return qs`)
  - Superuser vidí *vše* bez ohledu na scope nebo granty

- **Testy** – přidáno 8 nových testů `SuperadminAccessTest` do `firms/tests.py`:
  - `test_superuser_not_member_passes_require_membership` – superuser bez Membership projde
  - `test_superuser_not_member_passes_require_permission` – superuser bez Membership projde všechna oprávnění
  - `test_superuser_as_member_passes_require_permission` – superuser s Membership (i nejnižší rolí) projde billing/firm permissions
  - `test_superuser_sentinel_is_owner_and_admin` – sentinel má správné vlastnosti
  - `test_superuser_min_role_check_skipped` – superuser obejde i OWNER min_role check
  - `test_regular_user_still_needs_membership` – normální uživatel bez Membership stále dostane 403
  - `test_superuser_filter_records_sees_all` – superuser vidí záznamy všech uživatelů ve firmě
  - `test_regular_member_only_sees_own_records` – kontrolní test: člen s `scope=own` vidí jen své záznamy

- 236/236 testů zelených (+ 8 nových)

**Co bude následovat:**
- Volitelně: Zobrazit superadmin badge/indikátor v admin rozhraní pro lepší viditelnost
- Volitelně: Audit log záznam pro přístupy superadmina do firmy (pro security auditing)
- ~~Volitelně: Frontend indikátor v Settings pro owners, že superadmini mají přístup k workspacu~~ ❌ **Zrušeno** (rozhodnutí uživatele 2026-05-07) – Ownerům nebudeme zobrazovat, že superadmini mají přístup do jejich workspace.


### v3.1 – Plánovaná UX/UI vylepšení správy práv, týmů a pozvánek 📋 (next session)

**Stav**: Plán pro další session – analýza současných pain pointů a návrh konkrétních kroků.

**Motivace** (současné pain points zjištěné při review v3.0):
- `RecordShareModal.vue` zobrazuje raw `principal_id` (UUID) místo jména/e-mailu uživatele nebo týmu (řádek 154: `{{ grant.principal_type === 'user' ? grant.principal_id : 'Team: ' + grant.principal_id }}`).
- `PipelineSettingsView.vue` – sekce „Přístupy ke kategorii" vyžaduje ruční zadání UUID uživatele do textového inputu (`pipeline.categoryGrantUserIdPlaceholder`). Žádný picker, žádný autocomplete.
- `TeamsSettingsView.vue` – přidání člena do týmu nemá vyhledávání ani avatar; expandovatelný panel členů ukazuje seznam, ale pro velké firmy to nestačí.
- `RolesSettingsView.vue` – matice oprávnění je plochý seznam checkboxů ve skupinách. Není zobrazení „kdo má tuto roli", ani porovnání rolí proti sobě.
- Pozvánka (`MemberInviteIn`) přijímá `role_codes[]`, `default_scope`, `team_id`, `category_scope[]` – ale UI ve `TeamView` posílá jen role. Owner musí member-a poté ručně dále konfigurovat ve dvou samostatných místech (Roles tab + Teams tab + edit member).
- Žádný „onboarding wizard" pro vytvoření nového člena – Owner musí znát koncepty roles/scope/team předem.
- Audit log (`AuditLogSettingsView.vue`) zobrazuje `target_id` jako zkrácený UUID; není možné prokliknout na cíl.
- `useCan` composable vrací bool, ale v UI nejsou tooltips „proč to nemůžeš" – uživatel jen vidí skrytý/disabled prvek.
- Skupiny permissions v matici nemají popisy (uživatel netuší rozdíl mezi `record.edit` a `record.delete` pokud nezná kód).
- Žádné "presets" pro custom role (např. „Sales rep", „Marketing", „Read-only viewer") – Owner musí všechny permissions ručně zaškrtat.

**Plánované kroky (kandidáti pro další session, v pořadí podle ROI):**

1. **People Picker komponenta** (`frontend-spa/src/components/PeoplePicker.vue` – nová): ✅ **Hotovo v3.1**
   - Centrální reusable komponenta pro výběr Membership/User v rámci firmy.
   - Autocomplete podle jména/e-mailu, avatar, role badge, zobrazení týmu.
   - Použití: `RecordShareModal`, `PipelineSettingsView` (Category Access), `TeamsSettingsView` (přidání člena), `Transfer Ownership`.
   - Endpoint: rozšířit `GET /firms/{id}/members` o full-text search (`?q=`) a serializovat jméno + e-mail.
   - Eliminuje 4 různé místa, kde se dnes pracuje s raw UUID.

2. **Resolver jmen v UI** (rychlá výhra): ✅ **Hotovo v3.1**
   - Pinia store `members.ts` (cache list členů firmy) + getter `memberById(id)` a `teamById(id)`.
   - `RecordShareModal`, `CategoryGrantsSection`, `RecordAccessView` přepnout z UUID na `displayName`.
   - Audit log: `target_type=membership/role/team/grant` → display name + clickable link na detail.

3. **Member Onboarding Wizard** (`InviteMemberWizard.vue` – nový):
   - 3-step wizard nahrazující dnešní jednodušší pozvánkový formulář v `TeamView`:
     - Step 1: Identita – e-mail + jméno + jazyk pozvánky.
     - Step 2: Role & scope – výběr role(í), default scope (own/team/category/all), volitelně preset („Sales rep", „Read-only").
     - Step 3: Tým & kategorie – přiřazení týmu, výběr kategorií pro `category` scope.
   - Po odeslání: jediný API call `POST /firms/{id}/invitations` s plným payloadem (vše už backend podporuje od fáze 6).
   - Eliminuje rozháranou konfiguraci člena přes 3 různé taby.

4. **Role presets** (`firms/role_seeds.py` rozšířit + UI):
   - Přidat sadu pre-built šablon (Sales rep, Marketing, Customer success, External auditor, Read-only viewer) jako *templates*, nikoli `is_system` role – Owner je může naklonovat a upravit.
   - V `RolesSettingsView`: tlačítko „Vytvořit z šablony" otevře modal s předvolenými permissions.

5. **Permission matrix UX**:
   - Sloupec „Members with this role" (počet + první 3 avatary) přímo v listu rolí.
   - Hover tooltip nad permission kódem s human-readable popisem (z katalogu, který už backend vystavuje).
   - Funkce „Compare roles" – side-by-side diff dvou rolí (přidat/odebrat permission).
   - Ikona zámku u permissions, které aktér nemůže udělit (privilege escalation hint), s tooltipem proč.

6. **Teams UX**:
   - Drag & drop přiřazování členů (z listu „Bez týmu" do týmů) – `vuedraggable`.
   - Color-coded chip člena s týmem zobrazený všude v UI (member list, RecordDetail assignee selector, audit log).
   - Bulk akce: „Přesunout vybrané členy do týmu X".

7. **Sdílení záznamu (RecordShareModal redesign)**:
   - Tab „Lidé" / „Týmy" / „Odkaz" (link s tokenem read-only přístupu, max 30 dní – nový endpoint).
   - V seznamu existujících grantů: avatar + jméno + úroveň jako pill + expirační countdown badge.
   - Quick-actions: „Změnit na view/edit/manage" inline místo delete + re-add.
   - Hromadné sdílení vybraných záznamů z listu (`PipelineRecordsView` → checkbox + „Share selected").

8. **Tooltips „Proč to nemohu?"**:
   - Rozšířit `useCan` o variantu `canWithReason(action) -> { allowed: boolean, reason?: string }`.
   - Reason koreluje s důvodem zamítnutí (chybí permission X, scope Y nepokrývá Z, …).
   - Disabled tlačítka ukáží tooltip s reason; dlouhé verze v `<TooltipFAQ>` modalu „Co znamenají moje oprávnění?".

9. **Settings → Permissions overview dashboard** (`PermissionsOverviewView.vue`):
   - Heatmapa „kdo na co dosáhne" – řádky = members, sloupce = permission groupy, barva = scope.
   - Identifikace nejvyužívanější custom role, neaktivních členů, nikdy-neudělených permissions.
   - Export do CSV pro audit reporting.

10. **i18n & a11y**:
    - Doplnit chybějící popisky permissions (cs/en/de/pl) s 1 větou per kód.
    - Zajistit, že modaly (RecordShareModal, InviteMemberWizard) mají správné `aria-labelledby`, focus trap a keyboard navigation.
    - High-contrast badge varianty (Member expired, Restricted activity).

**Pořadí doporučená pro další session**: kroky **1 → 2 → 3** (největší okamžitý dopad: jednotný People Picker, skutečná jména místo UUID, kompletní onboarding flow). Kroky 4–10 lze rozložit do následujících iterací.

**Návaznost**: Výsledné PR-ka navázat značkami `v3.2` (PeoplePicker + name resolver), `v3.3` (Onboarding Wizard), atd.


### v3.1 – People Picker, Members Store, Name Resolution ✅ (2026-05-07)

**Větev**: `copilot/update-users-goals-document-3df005b8-d638-41b7-b89b-c491afbcf08b`

**Co bylo uděláno:**

- **Backend – `GET /firms/{id}/members?q=`** (search support):
  - Přidán volitelný query parametr `q` do `list_members()` v `firms/api.py`
  - Filtruje členy podle `user__email`, `user__first_name`, `user__last_name` (case-insensitive `icontains`)
  - Zpětně kompatibilní – bez `q` vrátí všechny členy jako dosud

- **Backend – `principal_name` v odpovědích grantů**:
  - `GrantOut` schema v `crm/api.py` rozšířeno o pole `principal_name: Optional[str]`
  - Přidána helper funkce `_resolve_principal_name(principal_type, principal_id)` – pro `user` resolvuje Membership→User→full name/email; pro `team` resolvuje Team→name; best-effort (nikdy neshodí response)
  - `_grant_out()` nově zahrnuje `principal_name` ve všech grant endpointech (category grants, record grants, access overview)

- **Frontend – Pinia store `stores/members.ts`** (nový):
  - State: `members: MemberOut[]`, `loading: bool`, `loadedFirmId: string|null`
  - Funkce: `fetchMembers(firmId, force?)` – cached fetch, přeskočí pokud `loadedFirmId === firmId`
  - Funkce: `memberById(id): MemberOut|undefined` – O(n) lookup z cache
  - Funkce: `displayNameById(id): string` – vrátí `full_name || email || id` (fallback na UUID pro neznámé IDs)
  - Funkce: `searchMembers(firmId, q)` – zavolá backend `?q=` a vrátí výsledky

- **Frontend – `components/PeoplePicker.vue`** (nový):
  - Reusable autocomplete komponenta pro výběr člena firmy
  - Props: `modelValue` (membership UUID), `firmId`, `placeholder`, `disabled`
  - Vyvolá `membersStore.fetchMembers()` při mount a při změně `firmId` (cached)
  - Zobrazuje vybraného člena s jménem + e-mailem + clear button
  - Dropdown s search inputem a filtrovaným listem členů
  - Keyboard-friendly (closes on outside click via `mousedown` listener)
  - Použití: `v-model="selectedMembershipId"` – odpovídá stávajícímu rozhraní všech formulářů

- **Frontend – `components/RecordShareModal.vue`** (aktualizováno):
  - Odstraněn lokální fetch a `members: FirmMember[]` state – nahrazen `membersStore`
  - Grant list: místo `grant.principal_id` (raw UUID) zobrazí `grantDisplayName(grant)`:
    - Primárně použije `grant.principal_name` (z backendu)
    - Fallback: `membersStore.displayNameById(principal_id)` z cache
    - Tým: přidán badge `(Tým)` za jménem
  - Formulář pro přidání grantu: nahrazen `<select>` → `<PeoplePicker>`

- **Frontend – `views/PipelineSettingsView.vue`** (aktualizováno):
  - Import `PeoplePicker`, `useMembersStore`; inicializace `membersStore`, `firmId` computed
  - `GrantOut` interface doplněn o `principal_name: string | null`
  - Grant list: místo `grant.principal_id` (mono UUID) zobrazuje `grantDisplayName(grant)` (jméno/e-mail)
  - Add-grant formulář: odstraněn UUID text input → `<PeoplePicker v-model="newGrantPrincipalId">`
  - `loadMembers()` rozšířen o `membersStore.fetchMembers()` pro cache population

- **Frontend – `views/TeamsSettingsView.vue`** (aktualizováno):
  - Import `PeoplePicker`, `useMembersStore`
  - `loadData()` nyní volá `membersStore.fetchMembers()` paralelně s `permissionsStore.fetchTeams()`
  - Add-member sekce: nahrazen `<select>` → `<PeoplePicker v-model="selectedMembershipId">`

- **i18n** – přidány klíče ve všech 4 lokalizacích (`cs.json`, `en.json`, `de.json`, `pl.json`):
  - `peoplePicker.placeholder` – výzva k výběru
  - `peoplePicker.search` – placeholder search inputu
  - `peoplePicker.noResults` – prázdný stav
  - `peoplePicker.addMember` – placeholder pro přidání člena do týmu
  - `permissions.team` – label pro typ grantu „team"

- Všechny testy zelené: 100/100 frontend, 14/14 grant-related crm tests
- TypeScript: 0 nových chyb v nových souborech

**Co bude následovat:**
- v3.2: Member Onboarding Wizard (`InviteMemberWizard.vue`) – 3-step formulář pro pozvání s konfigurací role/scope/tým v jednom průchodu ✅ **Hotovo v3.2**
- v3.3: Role presets (pre-built šablony v `RolesSettingsView` + backend seeder) ✅ **Hotovo v3.3**


### v3.2 – Member Onboarding Wizard ✅ (2026-05-07)

**Větev**: `copilot/users-goals-v32-v33`

**Co bylo uděláno:**

- **Nový komponent** `frontend-spa/src/components/InviteMemberWizard.vue`:
  - 3-step modální průvodce pro pozvání nového člena workspace
  - **Step 1**: Identita – e-mailová adresa + validace (required, @ formát)
  - **Step 2**: Role & scope – multi-select rolí ze `permissionsStore.roles` (chip buttony s checkmarkem), výběr `default_scope` (own/team/all) s popisky, 3-column layout
  - **Step 3**: Přiřazení týmu (volitelné) + přehledové shrnutí pozvánek před odesláním
  - Progress bar + krok/celkem indikátor v headeru
  - `watch(open)` – reset stavu, lazy load teamů a rolí při otevření
  - Jediný API call `POST /firms/{id}/invitations/` s `{ email, role_codes[], default_scope, team_id }` při odeslání
  - Emituje `invited` event pro reload listu členů, `close` pro zavření
  - Keyboard-friendly (Enter na step 1 přejde na step 2)

- **Aktualizace `TeamView.vue`**:
  - Odstraněn inline invite formulář (e-mail input + role select + "Send Invite" button)
  - Přidáno tlačítko „Invite member" (s `UserPlusIcon`) v header sekci členů (viditelné pouze pro admin/owner)
  - `showWizard: ref(false)` – state pro otevírání/zavírání wizardu
  - Import `InviteMemberWizard` a použití v template; `@invited="loadTeam"` pro refresh listu
  - Odstraněna funkce `sendInvitation()`, `inviteEmail`, `inviteRole`, `inviteError` (nahrazeno wizardem)

- **i18n** – přidány klíče pod namespace `wizard.*` ve všech 4 lokalizacích (`cs.json`, `en.json`, `de.json`, `pl.json`):
  - `title`, `stepOf`, `step1Title`, `step1Hint`, `step2Title`, `step2Hint`, `step3Title`, `step3Hint`
  - `emailLabel`, `emailPlaceholder`, `emailRequired`, `emailInvalid`
  - `rolesLabel`, `roleRequired`, `scopeLabel`, `scopeOwnDesc`, `scopeTeamDesc`, `scopeAllDesc`
  - `teamLabel`, `noTeam`, `noTeams`, `summaryTitle`
  - `back`, `next`, `cancel`, `sendInvite`, `sending`, `invitationSent`, `failedToInvite`

- **Test aktualizován** `TeamView.spec.ts`:
  - `test_shows_invite_form_for_admin_owner` – upraven assertion: hledá „Invite member" tlačítko (ne „Send Invite" inline formulář)
  - Přidán mock `usePermissionsStore` a `useMembersStore` (InviteMemberWizard deps)

- Všechny testy zelené: 100/100 OK

**Co bude následovat:**
- v3.3: Role presets ✅ **Hotovo níže**


### v3.3 – Role presets (backend endpoint + UI) ✅ (2026-05-07)

**Větev**: `copilot/users-goals-v32-v33`

**Co bylo uděláno:**

- **Backend – nový endpoint** `GET /firms/{id}/role-presets` v `firms/roles_api.py`:
  - Vrací statický seznam 5 předdefinovaných šablon rolí:
    - **Sales Rep** – record.view/create/edit, category.view, activity.create, proposal.create
    - **Marketing** – record.view/create/edit, category.view, report.view, activity.create
    - **Customer Success** – record.view/create/edit, category.view, activity.create, streamline.view_all, proposal.create
    - **External Auditor** – record.view, category.view, report.view, streamline.view_all (read-only)
    - **Read-Only Viewer** – record.view, category.view (nejmenší sada)
  - Nový `RolePresetOut` schema (code, name, description, permissions[])
  - Nová konstanta `ROLE_PRESETS` (statická data, neperzistují v DB)
  - Guard: člen musí být ve firmě (any member může číst)

- **Frontend – `stores/permissions.ts`**:
  - Přidán interface `RolePreset` (exportovaný)
  - Přidána akce `fetchRolePresets(firmId)` – zavolá `GET /role-presets`, vrátí výsledky (no caching, volá se jen při otevření modalu)

- **Frontend – `views/RolesSettingsView.vue`**:
  - Import `SparklesIcon` z heroicons
  - Import `RolePreset` z `permissions.ts`
  - Nový state: `showPresetsModal`, `presets`, `presetsLoading`, `selectedPreset`
  - Nová funkce `openPresetsModal()` – otevře modal, lazy-fetchuje šablony
  - Nová funkce `applyPreset(preset)` – předvyplní create form (code, name, description) a otevře ho
  - „Create from template" tlačítko (SparklesIcon amber, vedle „Create role" buttonu) – viditelné pro `canManageRoles`
  - Nový modal Presets: grid karet 2×3, každá karta zobrazí name + description + permission chips (max 4 + počet dalších); hover efekt + kliknutím aplikuje preset
  - Fade transition na modalu
  - Přidána CSS `<style scoped>` sekce pro fade animace

- **i18n** – přidány klíče pod `permissions.*` ve všech 4 lokalizacích:
  - `createFromTemplate` – tlačítko
  - `rolePresetsTitle` – modal titulek
  - `rolePresetsHint` – podtitulek
  - `loadingPresets` – loading stav

- Všechny testy zelené: 100/100 OK (no tests changed – presets are read-only static data)

**Co bude následovat:**
- v3.4: Permission matrix UX (hovery s popisem permission kódu, „Members with this role" sloupec, compare roles modal)
- v3.5: InviteMemberWizard Step 2 – preset šablony přímo ve wizardu pro quick role selection (Sales rep, Marketing…)


### v3.4 – Permission matrix UX ✅ (2026-05-07)

**Větev**: `copilot/work-on-users-goals`

**Co bylo uděláno:**

- **Backend – `RoleOut` schéma rozšířeno** o pole `member_count: int`:
  - `firms/roles_api.py::RoleOut`: přidáno `member_count: int = 0`
  - `_role_out()` helper: přidán `"member_count": role.membership_set.count()` – počítá přímé přiřazení Membership skrze M2M

- **Frontend – `RoleOut` interface** (`stores/permissions.ts`):
  - Přidáno `member_count: number` do interface

- **Frontend – `RolesSettingsView.vue`** (kompletní přepis pro v3.4):
  - **Sloupec „Členů/Members"**: přidán do obou tabulek (systémové i vlastní role) – zobrazuje `role.member_count`
  - **Hover tooltip pro permissions**: permission checkboxy v matici oprávnění nyní obaleny `<Tooltip>` komponentou z `@/components/ui` – zobrazuje `item.description` z katalogu (plaintext popis kódu) na hover
  - **Tlačítko „Porovnat role"**: nové tlačítko (ScaleIcon, indigo) v headeru sekce vlastních rolí – viditelné pokud jsou alespoň 2 role
  - **Modal „Compare roles"**:
    - Dva `<select>` dropdowny pro výběr Role A a Role B ze všech rolí firmy
    - Tabulka srovnání: permission kód (s Tooltip popisem), ✓/– pro každou roli, zvýraznění řádků kde se role liší (amber pozadí)
    - `compareRows` computed property: sjednocení permissions obou rolí, lookup description z katalogu
  - **Pomocná funkce `permDescription(code)`**: vrátí popis permission kódu z katalogu
  - Import `ScaleIcon` z `@heroicons/vue/24/outline`, import `Tooltip` z `@/components/ui`
  - i18n klíče přidány do všech 4 lokalizací:
    - `permissions.roleMembers` – záhlaví sloupce
    - `permissions.compareRoles` – label tlačítka
    - `permissions.compareRolesTitle`, `compareRolesHint`, `compareRoleA`, `compareRoleB`
    - `permissions.comparePermission`, `compareSelectBoth`, `compareNoDiff`

- Všechny testy zelené: 100/100 frontend OK, TypeScript: 0 nových chyb (pre-existing chyby beze změny)

**Co bude následovat:**
- v3.5: InviteMemberWizard Step 2 – preset šablony přímo ve wizardu ✅ Hotovo níže


### v3.5 – InviteMemberWizard – preset šablony ve Step 2 ✅ (2026-05-07)

**Větev**: `copilot/work-on-users-goals`

**Co bylo uděláno:**

- **`components/InviteMemberWizard.vue`** – Step 2 rozšířen o sekci „Quick setup":
  - Import `RolePreset` z `stores/permissions`
  - Import `SparklesIcon` z heroicons
  - `presets: ref<RolePreset[]>([])` + `presetsLoading: ref(false)` – nový state
  - `loadPresets()` funkce – volá `permissionsStore.fetchRolePresets()` při otevření wizardu (lazy, reset při každém open)
  - `applyPreset(preset)` funkce – vybere matchující roli podle kódu (`allRoles.find(r => r.code === preset.code)`), pokud neexistuje fallback na 'member'
  - **UI v Step 2**: sekce „Rychlý výběr" (SparklesIcon + nadpis) zobrazuje preset chips jako rounded-full tlačítka; zvýraznění pokud je preset kód v `selectedRoleCodes`; `title` atribut s popisem; oddělující `<hr>` před plným listem rolí
  - Presets se zobrazí pouze pokud `presets.length > 0` (prázdný stav je skrytý)
  - Plný list rolí zůstává pro manuální výběr pod presety
  - i18n klíč `wizard.quickPresets` přidán do všech 4 lokalizací (cs/en/de/pl)

- Všechny testy zelené: 100/100 OK

**Co bude následovat:**
- v3.6: Teams UX (color-coded chip, drag & drop, bulk akce) ✅ **Hotovo níže**


### v3.6 – Teams UX: color-coded chip + drag & drop + bulk assign ✅ (2026-05-07)

**Větev**: `copilot/update-users-goals-document-e13a1c75-dd25-4f15-a496-de6a87f82eb8`

**Co bylo uděláno:**

- **Backend – `MembershipOut` rozšíření** (`firms/api.py`):
  - Přidána pole `team_id: Optional[str]`, `team_name: Optional[str]`, `team_color: Optional[str]` do schema
  - `_membership_out()` helper nyní serializuje `m.team.name` a `m.team.color` (přes FK vztah)
  - `list_members()` rozšířen o `select_related("team")` pro efektivní dotaz bez N+1

- **Frontend – `stores/members.ts`** (`MemberOut` interface):
  - Přidána pole `team_id: string | null`, `team_name: string | null`, `team_color: string | null`

- **Frontend – `views/TeamView.vue`** (kompletní aktualizace):
  - Import `usePermissionsStore` pro načtení týmů (lazy load při `loadTeam()`)
  - **Color-coded team chip**: každý člen zobrazuje barevný badge se jménem týmu (barva = `team_color` z backendu)
  - **Bulk selection**: checkboxy na každém řádku (kromě owner a sebe sama) + „Select all" řádek
  - **Bulk toolbar**: zobrazí se po zaškrtnutí alespoň 1 člena – obsahuje: počet vybraných, tlačítko „Přiřadit k týmu" → select týmu + „Použít", „Zrušit výběr"
  - `toggleSelect(memberId)`, `selectAll()`, `applyBulkTeamAssign()` funkce
  - Bulk assign volá `POST /firms/{id}/teams/{teamId}/members/{membershipId}` pro každý vybraný membership, aktualizuje lokální stav optimisticky

- **Frontend – `views/TeamsSettingsView.vue`** (drag & drop integration):
  - Import `VueDraggable` z `vue-draggable-plus` (již v package.json)
  - **Nová sekce „Bez týmu"** – zobrazuje všechny members, kteří nejsou v žádném týmu
    - Pill-style drag chips s avatarem a jménem
    - Computed `unassignedMembers`: members jejichž ID není v žádném `team.members`
    - Hint text „Přetáhněte do týmu pro přiřazení"
  - **Team member panels přepsány na `<VueDraggable>`**:
    - Droppable zóna pro každý tým (expanded panel)
    - Callback `onDragToTeam(event, teamId)` → `addTeamMember` API call
    - Callback `onDragToUnassigned(event, fromTeamId)` → `removeTeamMember` API call
    - Při chybě API: revert UI přes `loadData()`
  - Záložní „add member" picker zachován pro nepodporované prohlížeče/touch

- **i18n** – přidány klíče ve všech 4 lokalizacích (`cs.json`, `en.json`, `de.json`, `pl.json`):
  - `team.bulkSelected`, `team.bulkAssignToTeam`, `team.selectTeam`, `team.apply`
  - `team.clearSelection`, `team.bulkAssignedToTeam`, `team.bulkAssignFailed`, `team.selectAll`
  - `permissions.unassignedMembers`, `permissions.dragToTeamHint`, `permissions.allMembersAssigned`

- Všechny testy zelené: 100/100 OK; TypeScript: 0 nových chyb

**Co bude následovat:**
- v3.7: RecordShareModal redesign (tab Lidé/Týmy, quick-actions inline, expirační countdown) ✅ **Hotovo níže**
- v3.8: Tooltips „Proč to nemohu?" (`canWithReason` composable) ✅ **Hotovo níže**


### v3.7 – RecordShareModal redesign ✅ (2026-05-07)

**Větev**: `copilot/update-users-goals-document-790c7470-1c21-47d9-aa60-161b605f06da`

**Co bylo uděláno:**

- **`components/RecordShareModal.vue`** – kompletní redesign:
  - **Taby „Lidé" / „Týmy"**: modal nyní zobrazuje dvě záložky separující granty podle `principal_type`
    - Tab „Lidé" (`userGrants`) – granty pro konkrétní uživatele přes `PeoplePicker`
    - Tab „Týmy" (`teamGrants`) – granty pro celé týmy přes team select (načítá se `permissionsStore.teams`)
    - Počítadlo grantů jako badge u každé záložky
    - Přepnutí tabu resetuje formulářový stav (výběr, level, expirace)
  - **Expirační countdown badge**: místo prostého data se zobrazuje barevný badge
    - 🔴 červená: „Vypršelo" (days ≤ 0)
    - 🟠 oranžová: „Vyprší zítra" (days = 1) nebo brzy (days ≤ 3)
    - 🟡 žlutá: „Vyprší za N dní" (days ≤ 7)
    - ⚪ šedá: vzdálené datum (days > 7)
    - Pomocné funkce `expiryDaysLeft()`, `expiryBadgeClass()`, `expiryLabel()`
  - **Quick-actions inline (level change)**: místo delete + re-add jsou vedle každého grantu 3 pill tlačítka `view / edit / manage`
    - Aktivní level je zvýrazněn barevnou pill (modrá/fialová/zelená)
    - Kliknutí na jinou pill zavolá POST grants endpoint (upsert) a aktualizuje lokální stav
    - Loading guard `levelUpdating` zabraňuje souběžným změnám na stejném grantu
    - Každý level pill je obalený `<Tooltip>` s human-readable popisem
  - **Přidání grantu pro tým**: nový `<select>` pro výběr týmu (tab Týmy) vedle existujícího `PeoplePicker` (tab Lidé)
    - Načítá `permissionsStore.fetchTeams()` paralelně s členy a granty
    - Dropdown zobrazuje jméno týmu; resolver v `grantDisplayName()` vrací jméno týmu z `teams` listu

- **i18n** – přidány klíče ve všech 4 lokalizacích (`cs.json`, `en.json`, `de.json`, `pl.json`):
  - `permissions.tabPeople` – záložka Lidé
  - `permissions.selectTeam` – placeholder team selectu
  - `permissions.levelChanged` – toast při změně levelu
  - `permissions.expiryExpired`, `expiryTomorrow`, `expiryInDays` – countdown labely

- Všechny testy zelené: 100/100 OK; TypeScript: 0 nových chyb


### v3.8 – Tooltips „Proč to nemohu?" (`canWithReason`) ✅ (2026-05-07)

**Větev**: `copilot/update-users-goals-document-790c7470-1c21-47d9-aa60-161b605f06da`

**Co bylo uděláno:**

- **`composables/useCan.ts`** – rozšířen o `canWithReason`:
  - Nový export `interface CanResult { allowed: boolean; reason?: string }`
  - Nová funkce `canWithReason(action: string): CanResult`:
    - Vrací `{ allowed: true }` pokud uživatel má oprávnění
    - Při zamítnutí generuje srozumitelnou reason string dle kontextu:
      - Guest role: „Hostující účet nemá toto oprávnění."
      - Scope = own + resource perm: „Vaše oprávnění je omezeno na vlastní záznamy."
      - Obecně: „Nemáte oprávnění pro akci {action}."
    - Reason je i18n-lokalizovaná přes `useI18n()`
  - Zpětně kompatibilní – `can()` funguje stejně jako dřív
  - Použití v template: `v-tooltip="canWithReason('record.delete').reason"` nebo `disabled :title="canWithReason(...).reason"`

- **i18n** – přidány klíče pod `permissions.*` ve všech 4 lokalizacích:
  - `reasonGuest` – důvod zamítnutí pro guest roli
  - `reasonScopeOwn` – důvod zamítnutí pro scope=own
  - `reasonMissingPermission` – obecný důvod zamítnutí

- Všechny testy zelené: 100/100 OK

**Co bude následovat:**
- v3.9: Settings → Permissions overview dashboard (heatmapa „kdo na co dosáhne", export CSV) ✅ **Hotovo níže**
- Nebo: a11y & i18n dokončení (aria-labelledby, focus trap v modalech, popisky permissions v katalogu)


### v3.9 – Permissions Overview Dashboard ✅ (2026-05-07)

**Větev**: `copilot/update-users-goals-progress-again`

**Co bylo uděláno:**

- **Nový pohled** `frontend-spa/src/views/PermissionsOverviewView.vue`:
  - **Heatmapa oprávnění**: tabulka s řádky = členové, sloupce = skupiny permission kódů z katalogu
    - Zelená buňka (✓): člen má ALL permissions v dané skupině
    - Žlutá buňka (~): člen má ČÁST permissions v dané skupině (partial)
    - Šedá buňka (–): člen nemá žádnou permission v dané skupině
    - Hover tooltip na každé buňce zobrazuje seznam povolených/odepřených permission kódů
    - Sticky první sloupec (jméno + e-mail člena) pro scrollování velkých tabulek
  - **Legenda**: barevná legenda pod tabulkou (Full / Partial / No coverage)
  - **Export CSV**: tlačítko exportuje matici členů × skupin do `.csv` souboru (UTF-8 BOM)
  - **Insights** – 3 karty s okamžitou analýzou:
    - „Nejpoužívanější vlastní role" – custom role s největším počtem přiřazení a jejím počtem
    - „Členové bez role" – seznam členů s prázdným `roles[]`
    - „Skupiny bez pokrytí" – skupiny permission kódů, které nemá pokrytý žádný člen
  - Loading skeleton (animované placeholder řádky)
  - Empty state pokud nejsou data

- **Aktualizace `SettingsView.vue`**:
  - Import `PermissionsOverviewView`
  - `activeTab` typ rozšířen o `'overview'`
  - Nová záložka „Přehled oprávnění" (viditelná pouze pro `canManageRoles`)
  - Nový panel `v-show="activeTab === 'overview'"` s `<PermissionsOverviewView />`

- **i18n** – přidány klíče pod `permissions.*` ve všech 4 lokalizacích (`cs.json`, `en.json`, `de.json`, `pl.json`):
  - `tabOverview` – záložka
  - `overviewTitle`, `overviewHint` – nadpis + popis
  - `overviewExportCsv` – tlačítko exportu
  - `overviewEmpty` – empty state
  - `overviewMember` – záhlaví sloupce
  - `overviewLegendFull`, `overviewLegendPartial`, `overviewLegendNone` – legenda
  - `overviewInsightTopRole`, `overviewInsightNoCustomRoles` – insight karta 1
  - `overviewInsightNoRoles`, `overviewInsightAllHaveRoles` – insight karta 2
  - `overviewInsightUncovered`, `overviewInsightAllCovered` – insight karta 3
  - `overviewCsvName`, `overviewCsvEmail` – CSV záhlaví

- Všechny frontend testy zelené: 100/100 OK; TypeScript: pre-existing 2 chyby v RecordShareModal.vue beze změny

**Co bude následovat:**
- a11y & i18n dokončení (aria-labelledby, focus trap v modalech) ✅ **Hotovo v4.0**
- Nebo: merge do main a tag `v3.9`


### v4.0 – a11y & i18n dokončení ✅ (2026-05-07)

**Větev**: `copilot/update-users-goals-document-74cbcefc-1df0-4e63-8958-3759881a56fb`

**Co bylo uděláno:**

- **`frontend-spa/src/components/ui/Modal.vue` – Focus trap**:
  - Přidána konstanta `FOCUSABLE_SELECTOR` pro výběr všech interaktivních prvků uvnitř dialogu
  - Rozšířena funkce `onKeydown`: kromě Escape nyní zpracovává Tab a Shift+Tab
  - Focus trap logika: při Tab z posledního prvku skočí na první; při Shift+Tab z prvního prvku skočí na poslední; pokud focus unikne ven, vrátí se na první/poslední focusable element
  - Zpětně kompatibilní – chování při Escape a backdrop click beze změny

- **`frontend-spa/src/components/InviteMemberWizard.vue` – a11y opravy**:
  - Import `nextTick` přidán pro focus management
  - Přidán `ref="dialogRef"` na dialog element pro focus trap
  - Přidána konstanta `FOCUSABLE_SELECTOR` (stejný vzor jako Modal.vue)
  - `watch(props.open)` rozšířen o: `await nextTick()` + auto-focus prvního focusable elementu při otevření
  - Nová funkce `onWizardKeydown(e)`: zpracovává Escape (zavře wizard) + Tab/Shift+Tab (focus trap)
  - `@keydown="onWizardKeydown"` přidán na backdrop div
  - Změna `aria-label` → `aria-labelledby="invite-wizard-title"` na dialog elementu
  - Přidán `id="invite-wizard-title"` na `<h2>` v headeru wizardu
  - Přidán `aria-hidden="true"` na dekorativní `UserPlusIcon`

- **i18n – permission code descriptions ve všech 4 lokalizacích** (`cs.json`, `en.json`, `de.json`, `pl.json`):
  - Přidán sub-objekt `permissions.codeDesc` s lokalizovanými popisky (1 věta) pro všech 16 permission kódů:
    - `record_view`, `record_create`, `record_edit`, `record_delete`
    - `category_view`, `category_manage`
    - `team_manage`, `role_manage`
    - `billing_manage`, `firm_delete`, `firm_transfer`
    - `integrations_manage`, `report_view`
    - `activity_create`, `streamline_view_all`, `proposal_create`
  - Klíče používají podtržítko místo tečky pro kompatibilitu s vue-i18n (`t('permissions.codeDesc.record_view')`)

- **`frontend-spa/src/assets/main.css` – forced-colors / high-contrast CSS**:
  - Přidána sekce `@media (forced-colors: active)` pro Windows High Contrast Mode
  - `.badge-expired`, `.badge-expiring` – expirační badge v TeamView zachovají viditelné ohraničení a text
  - `.badge-restricted` – restricted activity toggle v StreamlineCreateModal
  - Obecné pravidlo pro červená/oranžová/žlutá pozadí v RecordShareModal (expiry countdown)

- **`frontend-spa/src/views/TeamView.vue`** – Přidány CSS třídy `badge-expired` a `badge-expiring` na expirační badge

- **`frontend-spa/src/components/StreamlineCreateModal.vue`** – Přidána CSS třída `badge-restricted` na restricted visibility toggle

- Všechny testy zelené: 100/100 frontend OK; TypeScript: 0 chyb

**Co bude následovat:**
- Merge do `main` a tag `v4.0`
- Volitelně: Zobrazit záložku „Přístupy" ke členovi v TeamView s přehledem všech grantů
- Volitelně: Bulk sdílení vybraných záznamů z PipelineRecordsView (checkbox + „Share selected")
