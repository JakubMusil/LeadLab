# Plan: Formuláře ze sidebar nástrojů v modálním okně

## Současný stav

`EntitySidebarActionPicker` vykresluje vše inline ve slidepanelu (bočním panelu):

1. **Step 1** – seznam tlačítek akcí (komentář, hovor, schůzka, e-mail, úkol…)
2. **Step 2** – formulář se nahradí za seznam tlačítek přímo v bočním panelu

Toto komplikuje UX: formulář zabírá celý panel a nutí uživatele scrollovat; navíc na užších obrazovkách je prostor výrazně omezený.

---

## Navržená změna

Zachovat **Step 1** (grid tlačítek) v bočním panelu trvale. Po kliknutí na akci otevřít formulář v **modálním okně** – stejným stylem jako existující `ActivityEditModal.vue`.

---

## Detailní postup implementace

### 1. Vytvořit nový komponent `StreamlineCreateModal.vue`

Extrahovat celou sekci **Step 2** z `EntitySidebarActionPicker` do nového modálního komponentu.

Komponent bude přijímat props:
- `modelValue: boolean` – otevřeno / zavřeno (v-model)
- `actionType: string` – zvolená akce (např. `'comment'`, `'task'`, `'email_out'`…)
- `entityType` – stejný typ jako EntitySidebarActionPicker
- `entityId: string`
- `teamMembers?: MentionUser[]`
- `attachmentUploadUrl?: string`

Komponent bude emitovat:
- `update:modelValue` – pro v-model
- `activity-added` – po úspěšném odeslání
- `task-created`
- `file-uploaded`

Struktura modálu odpovídá vzoru z `ActivityEditModal.vue`:
- Teleport do `<body>`
- Overlay s `backdrop-blur-sm`
- Karta s animovaným přechodem (scale + fade)
- Hlavička s ikonou, názvem akce a křížkem pro zavření
- Scrollovatelné tělo s formulářem
- Footer s tlačítky Zrušit / Odeslat

### 2. Přesunout logiku formuláře do nového komponentu

Přesunout z `EntitySidebarActionPicker` do `StreamlineCreateModal`:
- Veškerý stav formuláře (`sidebarExtraFields`, `sidebarBoolFields`, `sidebarActivityText`, …)
- Task-specific stav (`sidebarTaskTitle`, `sidebarTaskDueDate`, `sidebarTaskAssigneeId`, …)
- Proposal stav (`sidebarProposalTitle`, `sidebarProposalCurrency`)
- Unified message composer (channel/direction picker)
- Submit handlery (`sidebarAddActivity`, `sidebarAddTask`, `sidebarAddProposal`, …)
- Speciální compose komponenty (`VoiceMemoRecorder`, `FileUploadComposer`)
- Schema helpers (`sidebarSchemaPropsTop`, `sidebarSchemaPropsBottom`, …)

### 3. Zjednodušit `EntitySidebarActionPicker`

Po extrakci bude komponenta obsahovat jen:
- Načítání toolbar nástrojů (`loadToolbar`)
- Skupinové vykreslení tlačítek akcí (Step 1 grid)
- `ref` na `modalActionType` a `modalOpen`
- Instanci nového `<StreamlineCreateModal>` s předanými props a event handlery

```vue
<EntitySidebarActionPicker>
  <!-- stále viditelný seznam tlačítek -->
  <button @click="openModal('comment')">Komentář</button>
  ...

  <!-- nový modál -->
  <StreamlineCreateModal
    v-model="modalOpen"
    :action-type="modalActionType"
    :entity-type="entityType"
    :entity-id="entityId"
    :team-members="teamMembers"
    :attachment-upload-url="attachmentUploadUrl"
    @activity-added="emit('activity-added')"
    @task-created="emit('task-created')"
    @file-uploaded="(f) => emit('file-uploaded', f)"
  />
</EntitySidebarActionPicker>
```

### 4. Aktualizovat ostatní entity views (volitelné)

`EntitySidebarActionPicker` je používán v:
- `LeadDetailView.vue`
- `CustomerDetailView.vue`
- `RealizationDetailView.vue`
- `ManagementDetailView.vue`
- `TaskDetailView.vue`

Změna je transparentní – props a emitované události zůstávají stejné, takže není nutná žádná změna v nadřazených komponentách.

---

## Dopad na UX

| Oblast | Před | Po |
|---|---|---|
| Boční panel (sidebar) | Formulář nahradí grid tlačítek | Grid tlačítek vždy viditelný |
| Prostor pro formulář | Omezený šířkou panelu | Modál max-w-lg, scrollovatelný |
| Přechod | Inline zobrazení | Plynulá animace scale + fade |
| Zavření | Tlačítko „← Zpět" | Overlay klik / X tlačítko / Escape |
| Konzistence | Odlišné od edit modálu | Shodný vzor s `ActivityEditModal` |

---

## Odhad složitosti

Extrakce logiky je rozsáhlá (cca 500+ řádků kódu), ale jde převážně o mechanické přesunutí.  
Rizikem je korektní předání event emitů a reaktivního stavu. Doporučuji implementovat po částech s průběžným testováním.
