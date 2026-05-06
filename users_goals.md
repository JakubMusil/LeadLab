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
| **Owner** | Plný přístup, nemůže být odebrán. Jediný kdo může smazat firmu, transferovat vlastnictví, spravovat billing. | `*` (super-set, fixní) |
| **Admin** | Spravuje členy, role, kategorie, integrace. | vše kromě `firm.delete`, `firm.transfer`, `billing.manage` |
| **Manager** *(nová)* | Spravuje vlastní tým + jeho záznamy. | `team.manage(own)`, `record.* (scope=team)`, `category.view`, `report.view` |
| **Member** *(přejmenovaný `Worker`)* | Standardní obchodník/uživatel. Default scope = `own`, lze rozšířit. | `record.* (scope=own|category)`, `activity.create`, `proposal.create` |
| **Guest** *(nová)* | Read-only host (např. externí auditor). | `record.view (scope=category|record)` |

> Owner a Admin jsou `is_system=True` a nelze je smazat ani editovat sadu permissions. Custom role lze vytvářet libovolně, ale nesmí dostat `firm.delete`/`billing.manage`.

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
- Přidán `PermissionMatrixTests` do `firms/tests.py` (45 testů pokrývajících celou matici role × permission)
- Všechny existující testy prošly (90 tests OK)

**Co bude následovat:**
- Fáze 2: datový model `Role`, `Permission`, `RolePermission`, `Team`, `TeamMembership` + datová migrace + admin registrace


- [ ] 8 fází zmergováno do `main` a release `v2.0-permissions` vystaven.
- [ ] Všechny stávající testy zelené v obou módech (`PERMISSIONS_V2_ENABLED ∈ {True, False}` během fází 4–7, pak pouze True).
- [ ] Pokrytí: `firms/permissions.py` ≥ 95 %, `crm/permissions.py` ≥ 90 %.
- [ ] e2e scénáře (5 use-cases ze sekce 5) procházejí v CI.
- [ ] Dokumentace v `docs/permissions/` kompletní + screenshoty UI.
- [ ] Audit log dostupný v UI (Settings → Audit) i přes API.
- [ ] Žádná regrese v existujících integracích (Fakturoid, webhooks, plugins).
