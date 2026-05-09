# Dashboard Revize — Cíle & Plán

## Filozofie
Dashboard ≠ reporty. Dashboard = **co dělám teď, kdo vede, jak si stojím**.
Každý widget musí mít buď **akční tlačítko**, nebo **motivační efekt**.
Statické grafy patří do ReportsView / AnalyticsView.

---

## Fáze 1 — Backend: 3 nové API endpointy ✅ HOTOVO

| Endpoint | Popis |
|---|---|
| `GET /api/v1/crm/dashboard/focus-next` | Jeden nejlepší záznam ke kontaktu hned teď |
| `GET /api/v1/crm/dashboard/recent-wins?days=30` | Poslední won záznamy (pro oslavu výher) |
| `GET /api/v1/crm/dashboard/my-goals` | Počty aktivit dnes vs. streak data |

Soubor: `crm/api.py`

---

## Fáze 2 — Frontend: 3 nové widget komponenty ✅ HOTOVO

| Widget ID | Soubor | Popis |
|---|---|---|
| `focus_next` | `FocusNextWidget.vue` | Jeden best-fit záznam ke kontaktu + skip |
| `recent_wins` | `RecentWinsWidget.vue` | Poslední výhry týmu s hodnotou + emoji |
| `daily_goals` | `DailyGoalsWidget.vue` | Kruhový progress ring + streak + denní cíl |

---

## Fáze 3 — Gamifikace stávajících widgetů ✅ HOTOVO

- `ActivityHeatmapWidget`: přidán "personal best" chip (🏆 Rekord: X aktivit za den)
- `TeamLeaderboardWidget`: zlatý/stříbrný/bronzový chip pro top 3 + emoji medaile
- `MyDayWidget`: prázdný stav s celebration (🎉) + motivační hláška

---

## Fáze 4 — Revize výchozího layoutu ✅ HOTOVO

Výchozí viditelnost widgetů přepracována v `stores/dashboard.ts`:

```
Viditelné by default (9 widgetů):
  my_day (12)
  focus_next (6) | daily_goals (6)
  quick_create_record (6) | upcoming_checkpoints (6)
  my_top_records (12)
  stale_records (6) | recent_wins (6)
  activity_heatmap (6) | team_leaderboard (6)
  setup_progress (12)

Skryté by default (report/stat widgety):
  stat_cards, pipeline_chart, recent_activity, status_breakdown,
  category_overview, stage_funnel, record_status_chart,
  pipeline_trend, win_loss
```

---

## Fáze 5 — i18n ✅ HOTOVO

Přidány klíče do všech 4 lokalit (cs, en, de, sk) pro:
- `focusNext.*` — nový widget
- `recentWins.*` — nový widget
- `dailyGoals.*` — nový widget
- `lbMedal*` — žebříček gamifikace
- `heatmapPersonalBest` — osobní rekord

---

## Co bylo uděláno (v tomto PR)

- [x] Vytvořen tento soubor `dashboard_goals.md`
- [x] 3 nové backend endpointy v `crm/api.py`
- [x] 3 nové Vue widget komponenty
- [x] Gamifikace: heatmap personal best, leaderboard medaile, my_day celebration
- [x] Výchozí layout přepracován — analytické widgety skryty by default
- [x] i18n klíče ve všech 4 lokalitách

---

## Čím budeme dále pokračovat (příští session)

1. **Widget `benchmarks`** — cross-tenant anonymní percentily
   - Backend: `GET /api/v1/crm/benchmarks` s pre-computed agregáty
   - Frontend: `BenchmarksWidget.vue` — 3 percentilové karty
   - Citlivost: nulová (jde o anonymní globální průměry)

2. **DashboardTour aktualizace** — nový onboarding tour pro nové widgety
   - Popisy v češtině/angličtině pro focus_next, daily_goals, recent_wins

3. **Quick-action button v StaleRecordsWidget** — inline "Zalogovat aktivitu" tlačítko
   - Bez navigace — mini modal přímo z widgetu

4. **MyTopRecords přejmenovat** na "Moje priority" + výchozí sort `stale`

5. **Daily goals backend persistence** — ukládání denního cíle uživatele (zatím fixní 10)
   - `PATCH /api/v1/crm/me/preferences` s `daily_activity_goal`
