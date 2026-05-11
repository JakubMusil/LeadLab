# Návrh: podmínková pravidla pro fáze, přechody, Streamline entity a pole záznamů

## 1. Cíl návrhu

Cílem je rozšířit systém podmínek tak, aby neřešil pouze jednoduchou validaci přechodu mezi fázemi, ale aby dokázal popsat celý rozhodovací proces nad záznamem v pipeline.

Pravidla by měla umět:

- vyhodnocovat podmínky před vstupem do fáze,
- vyhodnocovat podmínky během práce v jedné fázi,
- větvit scénáře uvnitř jedné fáze,
- řetězit více podmínek za sebou,
- reagovat na entity a aktivity ze Streamline feedu,
- reagovat na konkrétní tooly ze Streamline toolbaru,
- reagovat na úpravy standardních polí záznamu,
- reagovat na úpravy polí definovaných pro konkrétní kategorii,
- blokovat akci,
- zobrazit upozornění,
- doporučit další krok,
- vytvořit požadavek na doplnění dat,
- připravit pozdější napojení na automatizace.

## 2. Základní princip

Pravidla budou navázaná na kontext záznamu.

Kontext pravidla může obsahovat:

- firmu,
- uživatele,
- záznam,
- kategorii záznamu,
- aktuální fázi,
- cílovou fázi,
- standardní pole záznamu,
- kategoriová pole,
- aktivitu ze Streamline feedu,
- typ Streamline entity,
- konkrétní Streamline tool,
- změněné pole,
- starou hodnotu,
- novou hodnotu,
- čas události,
- autora změny.

Pravidlo by nemělo být pouze technickou podmínkou typu `field == value`. Mělo by reprezentovat obchodní logiku:

- „Nelze přesunout do fáze Hotovo, dokud není doplněný předávací protokol.“
- „Pokud ve fázi Realizace vznikne aktivita Reklamace, aktivuj reklamační větev.“
- „Pokud se změní pole Typ realizace na Montáž, vyžaduj fotodokumentaci.“
- „Pokud je v kategorii Servis povinné pole Servisní protokol prázdné, blokuj dokončení.“

## 3. Rozsah pravidel

### 3.1 Pravidla pro přechod mezi fázemi

Tato pravidla se vyhodnocují při pokusu o změnu fáze záznamu.

Použití:

- blokace přechodu,
- upozornění před přechodem,
- doporučení jiné cílové fáze,
- kontrola povinných polí,
- kontrola aktivit ve Streamline feedu,
- kontrola checklistů,
- kontrola příloh,
- kontrola dokončených úkolů.

Příklad:

- Při přechodu z „Realizace“ do „Hotovo“ musí existovat:
  - alespoň jedna aktivita typu `file_upload`,
  - dokončený checklist „Předání“,
  - vyplněné kategoriové pole „Datum předání“.

### 3.2 Pravidla uvnitř jedné fáze

Tato pravidla se vyhodnocují během práce ve fázi, nejen při přesunu do další fáze.

Použití:

- aktivace větve podle změny pole,
- průběžné upozornění na chybějící data,
- odemčení dalšího kroku po splnění předchozího,
- doporučení, co má uživatel udělat dál,
- automatické označení fáze jako připravené k dokončení.

Příklad:

- Ve fázi „Realizace“:
  - pokud se pole „Typ realizace“ změní na „Montáž“, aktivuje se montážní větev,
  - montážní větev vyžaduje fotky, checklist a montážní protokol,
  - po dokončení checklistu se zobrazí doporučení „Přesuňte záznam do Hotovo“.

### 3.3 Pravidla pro vstup do fáze

Tato pravidla se vyhodnocují při vstupu do fáze.

Použití:

- vytvoření seznamu povinností pro danou fázi,
- aktivace správného scénáře,
- kontrola, zda je fáze pro daný záznam relevantní,
- upozornění na chybějící vstupní data.

Příklad:

- Při vstupu do fáze „Nabídka“:
  - pokud záznam nemá zákazníka, zobrazit blokující chybu,
  - pokud nemá vyplněnou hodnotu zakázky, zobrazit upozornění,
  - pokud existuje aktivní návrh nabídky, doporučit pokračovat v něm.

### 3.4 Pravidla pro odchod z fáze

Tato pravidla se vyhodnocují při opuštění fáze.

Použití:

- kontrola dokončení všech povinností,
- kontrola povinných aktivit,
- validace polí,
- rozhodnutí, zda je vhodnější jiná cílová fáze.

Příklad:

- Při odchodu z fáze „Servis“:
  - pokud je `reklamace = ano`, doporučit fázi „Reklamace“,
  - pokud chybí servisní protokol, blokovat přechod,
  - pokud chybí fotodokumentace, zobrazit varování.

## 4. Řetězení podmínek

Řetězení znamená, že splnění jedné podmínky může aktivovat další krok nebo další sadu podmínek.

### 4.1 Typy řetězení

#### Lineární řetězení

Kroky jdou pevně za sebou.

Příklad:

1. Vyplnit typ realizace.
2. Podle typu realizace doplnit povinná pole.
3. Nahrát požadované přílohy.
4. Dokončit checklist.
5. Přesunout do další fáze.

#### Podmíněné řetězení

Další krok závisí na výsledku předchozí podmínky.

Příklad:

1. Změní se pole „Typ realizace“.
2. Pokud je hodnota „Montáž“, aktivuje se montážní větev.
3. Pokud je hodnota „Servis“, aktivuje se servisní větev.
4. Pokud je hodnota „Bez práce v terénu“, aktivuje se zjednodušená větev.

#### Reaktivní řetězení

Řetěz se spouští událostí.

Příklad:

1. Uživatel přidá do Streamline feedu aktivitu „Reklamace“.
2. Systém aktivuje reklamační větev.
3. Zobrazí povinná reklamační pole.
4. Blokuje dokončení záznamu, dokud není reklamace uzavřená.

### 4.2 Doporučený model řetězení

Každý krok v řetězci by měl mít:

- identifikátor,
- název,
- popis pro uživatele,
- aktivační podmínku,
- validační podmínku,
- výsledek při splnění,
- výsledek při nesplnění,
- návazný krok při splnění,
- návazný krok při nesplnění,
- prioritu,
- viditelnost v UI.

### 4.3 Výsledky kroku

Krok může vyvolat:

- blokaci,
- upozornění,
- informativní hlášku,
- doporučení,
- aktivaci větve,
- deaktivaci větve,
- označení povinnosti jako splněné,
- požadavek na doplnění pole,
- požadavek na aktivitu ve Streamline feedu,
- požadavek na přílohu,
- požadavek na dokončení checklistu,
- návrh změny fáze.

## 5. Větvení podmínek v rámci jedné fáze

Větvení umožňuje, aby jedna fáze měla více možných scénářů průchodu.

### 5.1 Scénář fáze

Scénář je varianta práce uvnitř fáze.

Scénář by měl obsahovat:

- název,
- popis,
- aktivační podmínku,
- seznam požadavků,
- seznam blokací,
- doporučené další kroky,
- doporučenou další fázi,
- podmínky ukončení scénáře,
- prioritu při souběhu více scénářů.

### 5.2 Příklad scénářů ve fázi Realizace

#### Scénář: Standardní montáž

Aktivace:

- kategoriové pole `typ_realizace = montaz`.

Požadavky:

- vyplnit datum montáže,
- nahrát minimálně jednu fotku,
- dokončit montážní checklist,
- přidat předávací protokol.

Blokace:

- nelze přejít do „Hotovo“, pokud chybí fotka,
- nelze přejít do „Hotovo“, pokud není dokončený checklist,
- nelze přejít do „Hotovo“, pokud chybí protokol.

Doporučení:

- po splnění všech požadavků doporučit přesun do „Hotovo“.

#### Scénář: Servis

Aktivace:

- kategoriové pole `typ_realizace = servis`.

Požadavky:

- vyplnit servisního technika,
- doplnit servisní protokol,
- uvést výsledek servisního zásahu.

Blokace:

- nelze uzavřít bez servisního protokolu.

Upozornění:

- pokud chybí fotky, zobrazit varování, ale neblokovat.

#### Scénář: Reklamace

Aktivace:

- změna pole `vznikla_reklamace = ano`,
- nebo přidání Streamline aktivity/toolu typu „Reklamace“,
- nebo změna stavu úkolu reklamace na otevřený.

Požadavky:

- vyplnit důvod reklamace,
- určit odpovědnou osobu,
- stanovit termín vyřešení,
- přidat reklamační komunikaci nebo přílohu.

Blokace:

- nelze přejít do „Hotovo“, dokud není reklamace uzavřená.

Doporučení:

- doporučit cílovou fázi „Reklamace“,
- po uzavření reklamace doporučit návrat do předchozí fáze nebo přesun do „Hotovo“.

## 6. Vazba pravidel na Streamline feed

Streamline feed je důležitý zdroj událostí, protože obsahuje aktivity kolem záznamu a dalších entit.

Pravidla by měla umět pracovat s tím, že určitá aktivita:

- existuje,
- neexistuje,
- byla vytvořená,
- byla upravená,
- byla dokončená,
- byla vytvořená konkrétním uživatelem,
- vznikla v určitém časovém období,
- patří ke konkrétní entitě,
- byla vytvořená konkrétním tool typem.

### 6.1 Podporované Streamline entity

Pravidla by měla být navázatelná minimálně na entity:

- Record,
- Customer,
- Proposal,
- Task.

Do budoucna by model měl umožnit přidat další entity bez změny logiky pravidel.

### 6.2 Typy vazby na Streamline entity

#### Vazba na aktuální záznam

Pravidlo sleduje pouze aktivity přímo na záznamu.

Příklad:

- záznam musí mít alespoň jednu přílohu,
- záznam musí mít komentář s předávací informací,
- záznam musí mít dokončený checklist.

#### Vazba na související zákazníka

Pravidlo sleduje aktivity na zákazníkovi navázaném na záznam.

Příklad:

- pokud u zákazníka existuje otevřená stížnost, nedoporučovat dokončení zakázky,
- pokud u zákazníka chybí poslední kontakt, zobrazit upozornění.

#### Vazba na související nabídku

Pravidlo sleduje aktivity na nabídce/proposalu.

Příklad:

- nelze přejít do „Realizace“, pokud nabídka není podepsaná,
- pokud byla nabídka odmítnutá, doporučit uzavření jako prohrané.

#### Vazba na související úkol

Pravidlo sleduje úkoly a checklisty.

Příklad:

- nelze uzavřít fázi, dokud existuje otevřený blokující úkol,
- pokud je dokončený úkol „Kontrola kvality“, odemknout další krok.

### 6.3 Vazba na konkrétní Streamline tool

Protože toolbar je řízený backendovým registry, pravidla by neměla natvrdo znát frontendové komponenty. Měla by se vázat na stabilní identifikátor toolu nebo activity typu.

Příklady toolů/aktivit:

- komentář,
- hovor,
- meeting,
- e-mail,
- SMS,
- WhatsApp,
- hlasová poznámka,
- upload souboru,
- checklist,
- změna stavu,
- událost úkolu,
- AI souhrn,
- vlastní pluginový tool.

Možné podmínky:

- „existuje alespoň jedna aktivita vytvořená tool typem `file_upload`“,
- „poslední aktivita toolu `call` je mladší než 7 dní“,
- „existuje dokončený checklist vytvořený tool typem `checklist`“,
- „neexistuje otevřená aktivita typu `complaint`“,
- „aktivita typu `proposal_signed` existuje na související nabídce“.

### 6.4 Události ze Streamline feedu

Pravidla by měla být vyhodnotitelná při těchto událostech:

- vytvoření aktivity,
- úprava aktivity,
- smazání nebo skrytí aktivity,
- dokončení checklist itemu,
- znovuotevření checklist itemu,
- přidání přílohy,
- změna stavu úkolu,
- přidání reakce,
- vytvoření AI souhrnu,
- přidání pluginové aktivity.

### 6.5 Příklady pravidel nad feedem

#### Povinná fotodokumentace

- Kontext: záznam ve fázi „Realizace“.
- Podmínka: k záznamu existuje aktivita typu `file_upload` s přílohou typu obrázek.
- Výsledek:
  - pokud ano, splnit požadavek „Fotodokumentace“,
  - pokud ne, blokovat přesun do „Hotovo“.

#### Povinný kontakt se zákazníkem

- Kontext: záznam ve fázi „Nabídka“.
- Podmínka: na zákazníkovi existuje aktivita typu `call`, `email`, `meeting`, `sms` nebo `whatsapp` za posledních 14 dní.
- Výsledek:
  - pokud ano, pokračovat,
  - pokud ne, zobrazit upozornění „Zákazník nebyl nedávno kontaktován“.

#### Reklamační větev

- Kontext: záznam ve fázi „Realizace“.
- Podmínka: v feedu záznamu existuje aktivita typu `complaint`.
- Výsledek:
  - aktivovat reklamační scénář,
  - zobrazit povinná reklamační pole,
  - blokovat dokončení, dokud není reklamace vyřešená.

## 7. Vazba pravidel na standardní pole záznamu

Pravidla by měla umět reagovat na změny standardních polí záznamu.

### 7.1 Příklady standardních polí

Standardní pole mohou být například:

- název záznamu,
- zákazník,
- hodnota,
- měna,
- odpovědná osoba,
- priorita,
- zdroj,
- datum začátku,
- datum konce,
- poznámka,
- štítky,
- kategorie,
- fáze,
- stav,
- pravděpodobnost,
- skóre,
- datum další akce.

### 7.2 Typy podmínek nad poli

Podmínky by měly podporovat:

- je vyplněno,
- není vyplněno,
- rovná se,
- nerovná se,
- obsahuje,
- neobsahuje,
- je větší než,
- je menší než,
- je mezi hodnotami,
- změnilo se,
- změnilo se z hodnoty,
- změnilo se na hodnotu,
- změnilo konkrétní uživatel,
- změnilo se v určité fázi,
- změnilo se v určitém časovém okně.

### 7.3 Pravidla spouštěná změnou pole

Změna pole může:

- aktivovat scénář,
- deaktivovat scénář,
- přepočítat splněné požadavky,
- zobrazit upozornění,
- vytvořit požadavek na doplnění dalšího pole,
- změnit doporučený další krok,
- zablokovat budoucí přechod.

Příklad:

- Pokud se pole `hodnota` změní nad 500 000 Kč:
  - vyžaduj schválení manažerem,
  - aktivuj scénář „Vyšší hodnota“,
  - blokuj přechod do „Podepsáno“, dokud není schválení dokončené.

### 7.4 Příklady pravidel nad standardními poli

#### Povinný zákazník

- Událost: pokus o přechod do fáze „Nabídka“.
- Podmínka: pole `customer` je vyplněné.
- Výsledek:
  - pokud ne, blokovat přechod.

#### Schválení vysoké hodnoty

- Událost: změna pole `value`.
- Podmínka: hodnota je vyšší než stanovený limit.
- Výsledek:
  - aktivovat scénář schválení,
  - vyžadovat manažerský souhlas,
  - blokovat přesun do finální fáze.

#### Kontrola termínu

- Událost: pokus o opuštění fáze.
- Podmínka: datum konce není v minulosti, pokud záznam není uzavřený.
- Výsledek:
  - zobrazit upozornění nebo blokaci podle konfigurace.

## 8. Vazba pravidel na pole definovaná pro konkrétní kategorii

Kategorie mají vlastní sadu polí. Pravidla musí umět pracovat nejen se standardními poli záznamu, ale i s poli zapnutými nebo definovanými pro konkrétní kategorii.

### 8.1 Princip kategoriových polí

Kategoriové pole je pole, které:

- patří do konkrétní kategorie,
- může být viditelné jen pro některé kategorie,
- může být povinné jen v některých kategoriích,
- může mít vlastní typ,
- může mít vlastní validaci,
- může být použité jako aktivační podmínka scénáře.

### 8.2 Typy kategoriových polí

Pravidla by měla počítat s typy:

- text,
- dlouhý text,
- číslo,
- částka,
- datum,
- čas,
- datum a čas,
- boolean,
- výběr jedné hodnoty,
- výběr více hodnot,
- uživatel,
- tým,
- zákazník,
- soubor,
- URL,
- e-mail,
- telefon,
- vazba na jinou entitu.

### 8.3 Pravidla nad kategoriovými poli

Možné podmínky:

- pole je vyplněné,
- pole je povinné v této fázi,
- pole má konkrétní hodnotu,
- pole změnilo hodnotu,
- hodnota pole aktivuje scénář,
- hodnota pole deaktivuje scénář,
- pole je vyplněné až po určité události,
- pole je vyplněné konkrétní rolí,
- hodnota pole odpovídá pravidlu pro kategorii.

### 8.4 Příklady kategoriových pravidel

#### Kategorie Servis

Pole:

- typ zásahu,
- servisní technik,
- servisní protokol,
- výsledek zásahu,
- potřeba další návštěvy.

Pravidla:

- pokud `typ_zasahu = oprava`, vyžaduj servisní protokol,
- pokud `potreba_dalsi_navstevy = ano`, doporuč vytvořit navazující úkol,
- pokud chybí `servisni_technik`, blokuj přechod do „Dokončeno“.

#### Kategorie Montáž

Pole:

- datum montáže,
- montážní tým,
- fotodokumentace,
- předávací protokol,
- podpis zákazníka.

Pravidla:

- pokud je záznam ve fázi „Realizace“, vyžaduj datum montáže,
- pokud se přechází do „Hotovo“, vyžaduj fotodokumentaci,
- pokud chybí podpis zákazníka, zobraz upozornění nebo blokaci podle nastavení.

#### Kategorie Onboarding

Pole:

- typ onboardingu,
- kickoff meeting,
- školení dokončeno,
- přístupové údaje předány,
- spokojenost zákazníka.

Pravidla:

- pokud `typ_onboardingu = enterprise`, vyžaduj kickoff meeting,
- pokud školení není dokončeno, blokuj přechod do „Dokončeno“,
- pokud spokojenost zákazníka je nízká, aktivuj retenční větev.

## 9. Datový model návrhu

### 9.1 Entita ConditionRule

Reprezentuje jedno pravidlo.

Pole:

- `id`,
- `firm_id`,
- `name`,
- `description`,
- `enabled`,
- `scope_type`,
- `category_id`,
- `stage_id`,
- `source_stage_id`,
- `target_stage_id`,
- `trigger_type`,
- `condition_tree`,
- `effect`,
- `severity`,
- `priority`,
- `created_by`,
- `updated_by`,
- `created_at`,
- `updated_at`.

### 9.2 Entita ConditionGroup

Reprezentuje skupinu podmínek.

Pole:

- `operator`: `AND` nebo `OR`,
- `negated`,
- `children`,
- `label`.

### 9.3 Entita ConditionNode

Reprezentuje jednu konkrétní podmínku.

Pole:

- `source_type`,
- `source_ref`,
- `operator`,
- `value`,
- `value_type`,
- `time_window`,
- `entity_type`,
- `tool_type`,
- `field_key`,
- `category_field_key`.

### 9.4 Entita StageScenario

Reprezentuje větev uvnitř fáze.

Pole:

- `id`,
- `firm_id`,
- `category_id`,
- `stage_id`,
- `name`,
- `description`,
- `activation_condition`,
- `requirements`,
- `completion_condition`,
- `recommended_next_stage_id`,
- `priority`,
- `enabled`.

### 9.5 Entita StageRequirement

Reprezentuje konkrétní povinnost v rámci scénáře.

Pole:

- `id`,
- `scenario_id`,
- `name`,
- `description`,
- `requirement_type`,
- `condition`,
- `blocking`,
- `visible_to_user`,
- `sort_order`.

### 9.6 Entita RuleEvaluationLog

Reprezentuje audit vyhodnocení pravidla.

Pole:

- `id`,
- `firm_id`,
- `record_id`,
- `rule_id`,
- `scenario_id`,
- `trigger_type`,
- `input_context`,
- `result`,
- `messages`,
- `evaluated_by`,
- `evaluated_at`.

## 10. Typy triggerů

Pravidla by měla podporovat následující trigger typy:

- `record.created`,
- `record.updated`,
- `record.field_changed`,
- `record.category_field_changed`,
- `record.stage_change_requested`,
- `record.stage_changed`,
- `stage.entered`,
- `stage.left`,
- `streamline.activity_created`,
- `streamline.activity_updated`,
- `streamline.activity_deleted`,
- `streamline.checklist_item_completed`,
- `streamline.checklist_item_reopened`,
- `streamline.file_uploaded`,
- `task.completed`,
- `task.reopened`,
- `proposal.signed`,
- `proposal.rejected`,
- `manual.evaluation_requested`.

## 11. Typy výsledků pravidel

Pravidlo může vrátit jeden nebo více výsledků.

### 11.1 Blokace

Blokace zabrání dokončení akce.

Použití:

- nelze změnit fázi,
- nelze uzavřít záznam,
- nelze potvrdit scénář,
- nelze pokračovat bez povinného pole.

### 11.2 Upozornění

Upozornění akci neblokuje, ale informuje uživatele.

Použití:

- chybí doporučená aktivita,
- zákazník nebyl kontaktován,
- termín je rizikový,
- chybí nepovinná dokumentace.

### 11.3 Doporučení

Doporučení navrhuje další krok.

Použití:

- doporučit další fázi,
- doporučit vytvoření úkolu,
- doporučit doplnění pole,
- doporučit přidání aktivity.

### 11.4 Aktivace scénáře

Pravidlo aktivuje konkrétní větev.

Použití:

- reklamační scénář,
- montážní scénář,
- servisní scénář,
- schvalovací scénář.

### 11.5 Splnění požadavku

Pravidlo označí povinnost jako splněnou.

Použití:

- požadovaná fotka existuje,
- checklist je dokončený,
- protokol je doplněný,
- nabídka je podepsaná.

## 12. UI návrh

### 12.1 Jednoduchý režim

Jednoduchý režim by měl pokrýt nejčastější scénáře bez technického builderu.

Uživatel vybírá:

- kdy se pravidlo spouští,
- pro jakou kategorii platí,
- pro jakou fázi platí,
- co má být splněno,
- zda pravidlo blokuje nebo jen upozorňuje.

Příklady voleb:

- „Před přechodem do fáze vyžaduj pole.“
- „Před dokončením vyžaduj aktivitu.“
- „Pokud se pole změní na hodnotu, aktivuj scénář.“
- „Pokud existuje aktivita ve feedu, zobraz upozornění.“

### 12.2 Pokročilý režim

Pokročilý režim umožní:

- vnořené skupiny AND/OR,
- více zdrojů podmínek,
- práci s časovými okny,
- scénáře v rámci fáze,
- doporučené přechody,
- vazby na Streamline tooly,
- vazby na kategoriová pole,
- audit a testovací vyhodnocení.

### 12.3 Zobrazení ve fázi záznamu

Na detailu záznamu by měl být panel „Požadavky fáze“.

Panel ukazuje:

- aktivní scénář,
- splněné požadavky,
- nesplněné požadavky,
- blokující položky,
- upozornění,
- doporučený další krok,
- důvod, proč nelze přejít dál.

### 12.4 Zobrazení při změně fáze

Při pokusu o změnu fáze se zobrazí:

- seznam blokací,
- seznam upozornění,
- tlačítko pro doplnění chybějících údajů,
- odkaz na relevantní pole,
- odkaz na relevantní Streamline aktivitu nebo tool,
- doporučená alternativní fáze.

### 12.5 Editor scénářů fáze

Editor scénářů by měl umožnit:

- vytvořit scénář,
- nastavit aktivační podmínku,
- přidat požadavky,
- určit, co je blokující,
- určit doporučenou další fázi,
- seřadit scénáře podle priority,
- otestovat scénář na konkrétním záznamu.

## 13. Backend pracovní úkony

### 13.1 Analýza domény

- [x] Zmapovat existující modely kategorií, fází a polí.
- [x] Zmapovat existující ukládání standardních polí záznamu.
- [x] Zmapovat existující ukládání kategoriových polí.
- [x] Zmapovat existující Streamline activity model.
- [x] Zmapovat registry Streamline toolů.
- [x] Zmapovat existující události při změně fáze.
- [x] Zmapovat existující audit log a activity log.
- [x] Zmapovat oprávnění pro správu kategorií a záznamů.

### 13.2 Návrh datového modelu

- [x] Navrhnout model pro pravidla.
- [x] Navrhnout model pro skupiny podmínek.
- [x] Navrhnout model pro scénáře fáze.
- [x] Navrhnout model pro požadavky scénáře.
- [x] Navrhnout model pro log vyhodnocení.
- [x] Navrhnout vazbu pravidel na firmu.
- [x] Navrhnout vazbu pravidel na kategorii.
- [x] Navrhnout vazbu pravidel na fázi.
- [x] Navrhnout vazbu pravidel na Streamline entity.
- [x] Navrhnout vazbu pravidel na Streamline tool typ.
- [x] Navrhnout vazbu pravidel na standardní pole.
- [x] Navrhnout vazbu pravidel na kategoriová pole.
- [x] Navrhnout prioritu pravidel.
- [x] Navrhnout zapnutí/vypnutí pravidel.

Návrh navazuje na existující automatizační architekturu (`AutomationRule`, `AutomationRun`) a na současný model dat pro pipeline, aktivity a Streamline entity.

**Model pro pravidla (`ConditionRule`)**

- rozšířit pattern `AutomationRule` o scope (`firm`, `category`, volitelně `stage`, `source_stage`, `target_stage`),
- zavést `priority` (deterministické řazení vyhodnocení) a `enabled` (rychlé zapnutí/vypnutí bez ztráty historie),
- podmínky ukládat jako `condition_tree` v JSON (MVP bez samostatných DB tabulek pro uzly),
- doplnit výstup pravidla (`effect`, `severity`, `effect_config`) pro blokace, upozornění a doporučení.

**Model pro skupiny podmínek (`ConditionGroup` + `ConditionNode`)**

- reprezentovat jako vnořenou JSON strukturu v `condition_tree` (`AND` / `OR` / `NOT`),
- `ConditionNode` musí nést `source_type`, `operator`, `value`, volitelně `time_window`,
- zdroje podmínek: standardní pole záznamu, kategoriové pole, aktivita, Streamline entita, související entita.

**Model pro scénáře fáze (`StageScenario`)**

- `firm` + `category` + `stage` jako povinný scope,
- `activation_condition` + `completion_condition` jako JSON strom podmínek,
- `recommended_next_stage` (volitelně), `priority`, `enabled`,
- scénáře se vyhodnocují v pořadí priority a mohou běžet souběžně (pokud to konfigurace nezakáže).

**Model pro požadavky scénáře (`StageRequirement`)**

- FK na `StageScenario`,
- `requirement_type`, `condition`, `blocking`, `visible_to_user`, `sort_order`,
- nesplněné `blocking=true` požadavky blokují přechod fáze, ostatní pouze upozorňují.

**Model pro log vyhodnocení (`RuleEvaluationLog`)**

- auditní, append-only log navázaný na `firm` a volitelně na `record`, `rule`, `scenario`, `requirement`,
- ukládat `trigger_type`, `input_context`, `result`, `messages`, `recommendations`, `error_message`, `evaluated_at`,
- `evaluated_by` ponechat nullable (část vyhodnocení běží asynchronně bez interaktivního uživatele).

**Vazby a mapování zdrojů**

- **firma/kategorie/fáze**: scope přes FK (`firm`, `category`, `stage` + `source_stage`/`target_stage` pro stage transition),
- **Streamline entity**: mapovat přes polymorfní vazbu aktivit (`Activity.record/customer/proposal/task`) a `entity_type`,
- **Streamline tool typ**: mapovat na `Activity.type` (bez paralelního tool registru v DB),
- **standardní pole**: `PipelineRecord` (`status`, `value`, `currency`, `current_stage`, `assigned_to`, `extra_data.*`),
- **kategoriová pole**: `CategoryField.field_key` + `value_type` + `validation_rules` (validace operátorů podle typu).

**Priorita, zapnutí/vypnutí, indexy**

- primární pořadí vyhodnocení: `priority ASC`, sekundárně `created_at ASC`,
- aktivní pravidla filtrovat přes `enabled=True`,
- navržené indexy pro výkon: `(firm, enabled, trigger_type, priority)`, `(firm, category, enabled)`, `(firm, stage, trigger_type)`.

**Kompatibilita s aktuálním backendem (ověřeno)**

- základ pro pravidla/log existuje: `crm/models.py` (`AutomationRule`, `AutomationRun`),
- stage změna dnes probíhá v `crm/api.py:update_record` a je vhodný integrační bod pro pre/post evaluaci,
- evaluace triggerů už běží přes Celery task `crm/tasks.py:evaluate_automation_rules`,
- aktivity mají polymorfní vazbu a canonical `entity_type`, což pokrývá požadované Streamline entity bez nového schématu.

### 13.3 Migrace

- [x] Přidat tabulku pravidel.
- [x] Přidat tabulku scénářů.
- [x] Přidat tabulku požadavků scénáře.
- [x] Přidat tabulku logu vyhodnocení.
- [x] Přidat indexy pro firmu, kategorii a fázi.
- [x] Přidat indexy pro record trigger vyhodnocení.
- [x] Přidat indexy pro Streamline activity vyhodnocení.
- [x] Přidat bezpečné defaulty.
- [x] Připravit rollback migrace.

### 13.4 Evaluátor pravidel

- [x] Vytvořit službu pro sestavení kontextu pravidla.
- [x] Vytvořit službu pro vyhodnocení stromu podmínek.
- [x] Přidat podporu `AND`.
- [x] Přidat podporu `OR`.
- [x] Přidat podporu negace.
- [x] Přidat podporu vnořených skupin.
- [x] Přidat podporu standardních polí.
- [x] Přidat podporu kategoriových polí.
- [x] Přidat podporu Streamline aktivit.
- [x] Přidat podporu Streamline tool typů.
- [x] Přidat podporu časových oken.
- [x] Přidat podporu změny hodnoty z/do.
- [x] Přidat podporu existence související entity.
- [x] Přidat podporu výstupů pravidla.
- [x] Přidat deterministické řazení podle priority.
- [x] Přidat ochranu proti nekonečnému řetězení.

### 13.5 Napojení na změnu fáze

- [x] Najít místo, kde se zpracovává změna fáze záznamu.
- [x] Před změnou fáze sestavit evaluation context.
- [x] Vyhodnotit pravidla typu `record.stage_change_requested`.
- [x] Vrátit blokace jako validační chyby.
- [x] Vrátit upozornění jako neblokující výsledek.
- [x] Zapsat log vyhodnocení.
- [x] Po úspěšné změně fáze vyhodnotit pravidla typu `record.stage_changed`.
- [x] Aktualizovat aktivní scénář záznamu, pokud je potřeba.

### 13.6 Napojení na změny standardních polí

- [x] Detekovat změněná standardní pole při update záznamu.
- [x] Uložit starou a novou hodnotu do evaluation contextu.
- [x] Vyhodnotit pravidla typu `record.field_changed`.
- [x] Aktivovat nebo deaktivovat scénáře podle výsledku.
- [x] Přepočítat požadavky fáze.
- [x] Zapsat log vyhodnocení.

### 13.7 Napojení na změny kategoriových polí

- [x] Detekovat změny kategoriových polí.
- [x] Ověřit, že pole patří ke kategorii záznamu.
- [x] Sestavit context s `category_field_key`.
- [x] Vyhodnotit pravidla typu `record.category_field_changed`.
- [x] Zohlednit povinnost pole podle fáze.
- [x] Aktualizovat požadavky scénáře.
- [x] Zapsat log vyhodnocení.

### 13.8 Napojení na Streamline feed

- [x] Najít místo vytvoření Streamline aktivity.
- [x] Při vytvoření aktivity sestavit evaluation context.
- [x] Doplnit entity type.
- [x] Doplnit activity type.
- [x] Doplnit tool type.
- [x] Doplnit vazbu na record/customer/proposal/task.
- [x] Vyhodnotit pravidla typu `streamline.activity_created`.
- [x] Vyhodnotit pravidla pro konkrétní tool.
- [x] Aktualizovat splněné požadavky.
- [x] Aktivovat scénáře podle aktivity.
- [x] Zapsat log vyhodnocení.

### 13.9 API endpointy

- [x] Přidat endpoint pro seznam pravidel.
- [x] Přidat endpoint pro detail pravidla.
- [x] Přidat endpoint pro vytvoření pravidla.
- [x] Přidat endpoint pro úpravu pravidla.
- [x] Přidat endpoint pro smazání nebo deaktivaci pravidla.
- [x] Přidat endpoint pro seznam scénářů fáze.
- [x] Přidat endpoint pro vytvoření scénáře.
- [x] Přidat endpoint pro úpravu scénáře.
- [x] Přidat endpoint pro požadavky scénáře.
- [x] Přidat endpoint pro testovací vyhodnocení pravidla.
- [x] Přidat endpoint pro požadavky aktuální fáze záznamu.
- [x] Přidat endpoint pro log vyhodnocení.

### 13.10 Oprávnění

- [x] Určit, kdo může pravidla zobrazit.
- [x] Určit, kdo může pravidla upravovat.
- [x] Určit, kdo může scénáře upravovat.
- [x] Určit, kdo vidí log vyhodnocení.
- [x] Zajistit, že pravidla nepřekročí firm scope.
- [x] Zajistit, že pravidla neodhalí data bez oprávnění.
- [x] Auditovat změny pravidel.

### 13.11 Testy backendu

- [x] Otestovat jednoduché pravidlo nad standardním polem.
- [x] Otestovat pravidlo nad kategoriovým polem.
- [x] Otestovat pravidlo nad Streamline aktivitou.
- [x] Otestovat pravidlo nad konkrétním Streamline tool typem.
- [x] Otestovat blokaci změny fáze.
- [x] Otestovat neblokující upozornění.
- [x] Otestovat aktivaci scénáře.
- [x] Otestovat řetězení kroků.
- [x] Otestovat větvení podle hodnoty pole.
- [x] Otestovat více aktivních scénářů a prioritu.
- [x] Otestovat audit log.
- [x] Otestovat oprávnění.

## 14. Frontend pracovní úkony

### 14.1 Analýza UI

- [x] Zmapovat detail záznamu.
- [x] Zmapovat nastavení pipeline kategorií.
- [x] Zmapovat nastavení fází.
- [x] Zmapovat zobrazení kategoriových polí.
- [x] Zmapovat práci se Streamline feedem.
- [x] Zmapovat existující modaly a formulářové komponenty.

### 14.2 Panel požadavků fáze

- [x] Navrhnout komponentu pro zobrazení aktivního scénáře.
- [x] Zobrazit splněné požadavky.
- [x] Zobrazit nesplněné požadavky.
- [x] Zobrazit blokující požadavky.
- [x] Zobrazit upozornění.
- [x] Zobrazit doporučený další krok.
- [x] Přidat odkazy na relevantní pole.
- [x] Přidat odkazy na relevantní Streamline aktivity.
- [x] Přidat prázdný stav.
- [x] Přidat loading stav.
- [x] Přidat error stav.

### 14.3 Validace při změně fáze

- [x] Při drag-and-drop změně fáze volat validační endpoint.
- [x] Při změně fáze z detailu záznamu volat validační endpoint.
- [x] Pokud existuje blokace, vrátit záznam do původní fáze.
- [x] Zobrazit modal s blokacemi.
- [x] Zobrazit neblokující upozornění.
- [x] Umožnit pokračování, pokud jsou pouze upozornění.
- [x] Umožnit rychlé doplnění chybějícího pole.
- [x] Umožnit rychlé vytvoření požadované Streamline aktivity.

### 14.4 Editor pravidel

- [x] Přidat seznam pravidel v nastavení pipeline.
- [x] Přidat filtrování podle kategorie.
- [x] Přidat filtrování podle fáze.
- [x] Přidat filtrování podle triggeru.
- [x] Přidat stav zapnuto/vypnuto.
- [x] Přidat vytvoření pravidla.
- [x] Přidat úpravu pravidla.
- [x] Přidat deaktivaci pravidla.
- [x] Přidat kopírování pravidla.
- [x] Přidat testovací vyhodnocení.

### 14.5 Builder podmínek

- [x] Přidat výběr zdroje podmínky.
- [x] Podporovat zdroj „standardní pole záznamu“.
- [x] Podporovat zdroj „kategoriové pole“.
- [x] Podporovat zdroj „Streamline aktivita“.
- [x] Podporovat zdroj „Streamline tool“.
- [x] Podporovat zdroj „související entita“.
- [x] Přidat výběr operátoru.
- [x] Přidat výběr hodnoty.
- [x] Přidat podporu časového okna.
- [x] Přidat skupiny AND/OR.
- [x] Přidat vnořené skupiny.
- [x] Přidat validaci neúplných podmínek.
- [x] Přidat čitelný preview text pravidla.

### 14.6 Editor scénářů fáze

- [x] Přidat seznam scénářů pro fázi.
- [x] Přidat vytvoření scénáře.
- [x] Přidat aktivační podmínku scénáře.
- [x] Přidat seznam požadavků scénáře.
- [x] Přidat nastavení blokujícího požadavku.
- [x] Přidat doporučenou další fázi.
- [x] Přidat prioritu scénáře.
- [x] Přidat zapnutí/vypnutí scénáře.
- [x] Přidat preview na testovacím záznamu.

### 14.7 Napojení na Streamline

- [x] Zobrazovat požadované Streamline aktivity v panelu požadavků.
- [x] Nabídnout rychlé vytvoření chybějící aktivity.
- [x] Otevřít správný Streamline tool podle požadavku.
- [x] Zobrazit, která aktivita požadavek splnila.
- [x] Zobrazit, která aktivita aktivovala scénář.
- [x] Podporovat tooly z backend registry bez frontend hardcodování.

### 14.8 Napojení na kategoriová pole

- [x] Načíst dostupná pole pro kategorii.
- [x] Nabídnout kategoriová pole v builderu.
- [x] Zobrazit názvy polí čitelně pro uživatele.
- [x] Ověřit typ pole před výběrem operátoru.
- [x] Umožnit rychlou úpravu chybějícího pole z validačního modalu.
- [x] Zobrazit pravidla relevantní pouze pro vybranou kategorii.

### 14.9 Testy frontendu

- [x] Otestovat render panelu požadavků.
- [x] Otestovat splněné a nesplněné požadavky.
- [x] Otestovat blokaci změny fáze.
- [x] Otestovat upozornění bez blokace.
- [x] Otestovat builder pravidla.
- [x] Otestovat výběr standardního pole.
- [x] Otestovat výběr kategoriového pole.
- [x] Otestovat výběr Streamline toolu.
- [x] Otestovat editor scénářů.
- [x] Otestovat prázdné a chybové stavy.

## 15. Postup implementace po etapách

### Etapa 1: Datový základ a jednoduchá validace

- [x] Přidat základní model pravidel.
- [x] Přidat jednoduchý condition tree.
- [x] Podporovat `AND` a `OR`.
- [x] Podporovat standardní pole záznamu.
- [x] Napojit pravidla na změnu fáze.
- [x] Vrátit blokace do API.
- [x] Přidat základní backend testy.

Výsledek:

- Systém umí blokovat přechod mezi fázemi podle standardních polí.

### Etapa 2: Kategoriová pole

- [x] Přidat zdroj podmínek pro kategoriová pole.
- [x] Přidat validaci typů kategoriových polí.
- [x] Přidat pravidla pro změnu kategoriového pole.
- [x] Přidat testy kategoriových polí.
- [x] Doplnit UI výběr kategoriového pole.

Výsledek:

- Pravidla lze vázat na pole definovaná pro konkrétní kategorii.

### Etapa 3: Streamline feed

- [x] Přidat zdroj podmínek pro Streamline activity.
- [x] Přidat zdroj podmínek pro Streamline tool type.
- [x] Napojit vytvoření aktivity na vyhodnocení pravidel.
- [x] Podporovat vazbu na Record, Customer, Proposal a Task.
- [x] Přidat testy aktivit.
- [x] Doplnit UI pro výběr Streamline toolu.

Výsledek:

- Pravidla lze splnit nebo aktivovat pomocí aktivit ve Streamline feedu.

### Etapa 4: Scénáře uvnitř fáze

- [x] Přidat model scénářů fáze.
- [x] Přidat aktivační podmínky scénářů.
- [x] Přidat požadavky scénáře.
- [x] Přidat výpočet aktivního scénáře.
- [x] Přidat panel požadavků fáze.
- [x] Přidat editor scénářů.

Výsledek:

- Jedna fáze může mít více větví podle dat a aktivit.

### Etapa 5: Řetězení

- [x] Přidat návazné kroky.
- [x] Přidat stav splnění kroků.
- [x] Přidat ochranu proti cyklům.
- [x] Přidat priority.
- [x] Přidat audit řetězení.
- [x] Doplnit testy řetězení.

Výsledek:

- Splnění jedné podmínky může aktivovat další krok nebo další sadu podmínek.

### Etapa 6: Pokročilé UI a testovací režim

- [x] Přidat pokročilý builder.
- [x] Přidat vnořené skupiny.
- [x] Přidat preview čitelné věty.
- [x] Přidat testovací vyhodnocení na konkrétním záznamu.
- [x] Přidat log vyhodnocení do administrace.
- [x] Přidat šablony pravidel.

Výsledek:

- Administrátor může bezpečně vytvářet i složitější pravidla.


### Etapa 7: Interaktivní grafická mindmapa pravidel

- [x] Navrhnout normalizovaný vizualizační model pro pravidla, scénáře, požadavky, condition tree a návazné kroky.
- [x] Přidat čitelnou stromovou vizualizaci condition tree jako doplněk ke stávajícímu formulářovému builderu.
- [x] Přidat přehledový diagram vazeb pravidlo → scénář → požadavek → návazný krok.
- [x] Napojit vizualizaci do nastavení pipeline jako samostatný režim nebo záložku bez nahrazení současných editorů.
- [x] Přidat interaktivní práci s uzly: výběr, sbalení/rozbalení, kontext detailu, později přímé úpravy.
- [x] Přidat vizuální správu návazných hran `next_step_on_met` a `next_step_on_unmet` s validací cyklů a scénářového kontextu.
- [x] Přidat zoom, pan, automatické rozvržení, filtrování a fallback pro velké nebo nečitelné grafy.
- [x] Propojit graf s testovacím vyhodnocením a logem vyhodnocení tak, aby bylo vidět, které větve se splnily nebo nesplnily.
- [x] Doplnit unit testy normalizace dat, renderu prázdných/složitých grafů, interakcí a synchronizace s formulářem.
- [x] Doplnit uživatelskou nápovědu, klávesové ovládání a přístupnost.

Výsledek:

- Administrátor uvidí složité podmínky, scénáře a návaznosti jako interaktivní mapu, která zjednoduší pochopení a bezpečnou správu workflow.

## 16. Rizika a otevřené otázky

### 16.1 Rizika

- Pravidla mohou být pro uživatele příliš složitá.
- Volné větvení může vést k nečitelným workflow.
- Řetězení může vytvořit cykly.
- Vyhodnocení nad feedem může být náročné na výkon.
- Pluginové Streamline tooly mohou mít rozdílnou strukturu dat.
- Kategoriová pole mohou měnit typ nebo být odstraněna.
- Blokace mohou uživatele brzdit, pokud nejsou dobře vysvětlené.
- Grafická mindmapa může být u velkých sad pravidel nepřehledná nebo pomalá.
- Přímé editace v grafu mohou vytvořit druhý zdroj pravdy vedle formulářového editoru, pokud nebude synchronizace jednoznačná.

### 16.2 Opatření

- Začít jednoduchým režimem.
- Pokročilý builder schovat za pokročilé nastavení.
- Každé pravidlo musí mít lidsky čitelné vysvětlení.
- Přidat testovací vyhodnocení pravidla.
- Přidat audit log.
- Přidat ochranu proti cyklům.
- Přidat jasné priority.
- Při odstranění pole upozornit na pravidla, která ho používají.
- Grafickou mindmapu zavádět postupně: nejdříve pouze read-only vizualizace, poté řízené editace.
- Zachovat formulářový editor jako primární fallback a graf napojit na stejný stav/store.
- U velkých grafů povinně použít filtrování podle kategorie/fáze, sbalování větví, zoom/pan a výkonnostní limity.

### 16.3 Otevřené otázky

- Má být možné pravidlo ručně obejít s oprávněním manažera?
- Mají mít upozornění možnost „pokračovat i tak“?
- Budou scénáře ukládané na záznamu, nebo se budou vždy dopočítávat?
- Jak se bude řešit souběh více aktivních scénářů?
- Má mít každý scénář vlastní doporučenou cílovou fázi?
- Mají pravidla spouštět i automatické akce, nebo pouze validace a doporučení?
- Jak budou pluginové Streamline tooly deklarovat, jaká data poskytují pro pravidla?
- Jak se bude verzovat změna pravidel kvůli auditu?

## 17. Doporučené MVP

Pro první praktickou verzi doporučuji:

- pravidla navázaná na kategorii a fázi,
- trigger při pokusu o změnu fáze,
- podmínky nad standardními poli,
- podmínky nad kategoriovými poli,
- jednoduchá kontrola existence Streamline aktivity podle tool typu,
- `AND`/`OR` bez hlubokého vnoření,
- blokace a upozornění,
- panel požadavků fáze,
- jednoduchý editor pravidel,
- backend testy pro všechny zdroje podmínek.

Do další verze přesunout:

- plné větvení scénářů,
- hluboké vnořování podmínek,
- řetězení kroků,
- doporučené cílové fáze,
- pravidla nad souvisejícími entitami,
- testovací sandbox pravidel,
- pluginové rozšíření builderu.

## 18. Shrnutí

Rozšíření pravidel o Streamline entity, Streamline tooly, standardní pole záznamu a kategoriová pole dává velký smysl. Z pravidel se tím stane praktický workflow mechanismus, který nebude pouze kontrolovat přechod mezi fázemi, ale bude řídit práci uvnitř fáze.

Nejdůležitější je navrhnout datový model dostatečně obecně:

- pravidla jako strom podmínek,
- scénáře jako větve uvnitř fáze,
- požadavky jako konkrétní splnitelné položky,
- Streamline aktivity jako zdroj důkazů,
- pole záznamu a kategoriová pole jako zdroj obchodních rozhodnutí.

Implementaci je vhodné dělit do etap, aby první verze přinesla hodnotu rychle, ale zároveň neuzavřela cestu k pokročilému větvení a řetězení.

## 19. Průběžný pracovní postup

### 2026-05-11 16:10 UTC

- Prostudován aktuální stav `podminky.md` a navázáno přesně na poslední otevřený bod záznamu 15:42 UTC.
- Další krok byl maximalizovaně delegován subagentovi (ověření minimálního navazujícího kroku) a závěr byl ručně konceptuálně zvalidován proti sekci 19.
- Provedena baseline validace frontend scope před novým zápisem: `npm run check-locales`, `npm run build-only` a `npm run test:unit -- --run src/components/__tests__/PipelineFlowDiagram.spec.ts` prochází (po `npm ci` v `frontend-spa`).
- Spuštěn `parallel_validation` pro stav větve před novou změnou; nástroj vrátil `No changes detected`.
- Hotovo: navazující validační krok je provedený a průběžný stav je zapsán do dokumentu dle pravidel sekce 19.
- Následuje: spustit `parallel_validation` nad tímto dokumentačním diffem, vytvořit řádný PR a po jeho otevření navázat dalším implementačním krokem podle aktuálních priorit v `podminky.md`.

### 2026-05-11 15:42 UTC

- Prostudován aktuální stav `podminky.md` a navázáno dalším praktickým krokem na etapu 20.3.6 (UX polish pro flow diagram) po uzavření předchozího scope sekce 21.
- Další krok byl maximalizovaně delegován podagentovi (identifikace nejmenšího navazujícího nedodělku) a návrh následně ručně konceptuálně zvalidován nad `PipelineFlowDiagram.vue` a existujícími testy/lokalizacemi.
- Baseline validace před změnami ve `frontend-spa`:
  - `npm run check-locales` prochází,
  - `npm run build-only` původně padal na chybějícím `vite`; po `npm ci` opakovaně prochází,
  - cílené `npm run test:unit -- --run src/components/__tests__/PipelineFlowDiagram.spec.ts` prochází.
- Implementace navazujícího kroku:
  - `frontend-spa/src/components/PipelineFlowDiagram.vue`: doplněný přepínač in-app nápovědy legendy + panel s kontextem uzlů, stavů, vazeb a ovládání.
  - `frontend-spa/src/locales/{cs,en,de,pl}.json`: doplněné i18n klíče pro nové texty nápovědy.
  - `frontend-spa/src/components/__tests__/PipelineFlowDiagram.spec.ts`: nový unit test pro otevření/zavření nápovědného panelu.
- Post-change validace prochází: `npm run check-locales`, `npm run build-only`, `npm run test:unit -- --run src/components/__tests__/PipelineFlowDiagram.spec.ts`.
- Hotovo: etapa 20 má navazující UX krok splněný o čitelnou in-app nápovědu přímo v diagramu.
- Následuje: spustit `parallel_validation`, zapracovat případné relevantní připomínky, provést finální commit/push a vytvořit řádný PR.

### 2026-05-11 15:38 UTC

- Navázáno na krok 15:24 UTC: proběhla post-change validace a finální review/security kolo navazujícího scope sekce 21.
- Cílená validace po změnách ve `frontend-spa`:
  - `npm run check-locales` prochází,
  - `npm run build-only` opakovaně prochází.
- Spuštěn `parallel_validation` (code review + CodeQL):
  - první běh vrátil jednu připomínku ke konzistenci názvu i18n klíče pro installation scénář; připomínka zapracována (sjednocení na `rulesTemplateScenarioInstallationStandardInstallation`),
  - opakovaný běh je čistý: review bez připomínek, CodeQL bez alertů.
- Hotovo: navazující implementační krok sekce 21 je funkčně i konceptuálně ověřený a připravený k PR finalizaci.
- Následuje: provést finální commit/push aktualizací z tohoto validačního kola, vytvořit řádný PR a v PR shrnutí uvést, že scope je frontend-only (doménové šablony/scénářové štítky).

### 2026-05-11 15:24 UTC

- Prostudován aktuální stav `podminky.md`; checklist etap zůstává uzavřený, proto navázáno dalším praktickým krokem v sekci 21 (zpřesnění doménových šablon o scénářový kontext).
- Další krok byl maximalizovaně delegován podagentovi (gap analýza nejmenšího navazujícího scope) a návrh následně ručně konceptuálně zvalidován nad `ruleTemplates.ts` a `PipelineSettingsView.vue`.
- Baseline validace před změnami ve `frontend-spa`:
  - `npm run check-locales` prochází,
  - `npm run build-only` původně padal na chybějícím `vite` v prostředí; po `npm ci` opakovaný běh prochází.
- Implementace navazující na sekci 21:
  - `frontend-spa/src/constants/ruleTemplates.ts`: šablony doménových pravidel nyní obsahují volitelné metadata `scenarioLabelKey` pro scénářové seskupení.
  - `frontend-spa/src/views/PipelineSettingsView.vue`: katalog šablon zobrazuje u doménových presetů i scénářový štítek.
  - `frontend-spa/src/locales/{cs,en,de,pl}.json`: doplněné i18n klíče pro scénáře „První kontakt“, „Standardní montáž“ a „Incident management“.
- Hotovo: sekce 21 je prakticky lépe propsaná do UI, protože doménové preset šablony už nesou i čitelný scénářový kontext.
- Následuje: spustit post-change validaci (`check-locales`, `build-only`), provést `parallel_validation`, zapsat závěrečné shrnutí a vytvořit řádný PR.

### 2026-05-11 13:45 UTC

- Navázáno na krok 13:32 UTC: proběhla post-change validace a finální kontrola navazujícího scope sekce 21.
- Cílená validace po změnách ve `frontend-spa`:
  - `npm run check-locales` prochází,
  - `npm run build-only` opakovaně prochází,
  - cílený unit test `npm run test:unit -- --run src/utils/__tests__/conditionTreeVisualization.spec.ts` prochází (`6/6`).
- Spuštěn `parallel_validation` (code review + CodeQL):
  - CodeQL bez alertů,
  - review připomínky zapracovány tam, kde dávaly smysl (centralizace keyword mapy, dokumentovaný fallback filtrů, normalizace slugů bez diakritiky, zpřesnění PL lokalizačního textu).
- Hotovo: doménové šablony pravidel jsou implementované, lokalizované, validované a průběžně zapsané v dokumentu.
- Následuje: provést finální commit/push aktualizací z tohoto kola, vytvořit řádný PR a v PR shrnutí uvést baseline omezení plného `test:unit` mimo tento scope.

### 2026-05-11 13:32 UTC

- Prostudován aktuální stav `podminky.md`; protože checklist etap 13–15 je uzavřený, navázáno implementačně na novou sekci 21 (doménové šablony pravidel/scénářů).
- Scope byl nejdříve maximalizovaně delegován podagentovi (gap analýza navazujícího minimálního kroku + soubory + validace), následně proběhla ruční konceptuální validace návrhu nad `ruleTemplates.ts` a `PipelineSettingsView.vue`.
- Baseline validace před změnami ve `frontend-spa`:
  - po `npm ci` prochází `npm run check-locales` a `npm run build-only`,
  - plný `npm run test:unit -- --run` dál padá na pre-existing unhandled chybách mimo tento scope (`SettingsView.spec.ts` a dashboard testy; opakovaný známý baseline problém).
- Implementace navazující na sekci 21:
  - `frontend-spa/src/constants/ruleTemplates.ts`: rozšířené šablony o doménové metadata (`domain`, `domainLabelKey`) a doplněné nové preset šablony pro Call centrum, Montážní firmu a IT servis.
  - `frontend-spa/src/views/PipelineSettingsView.vue`: seznam šablon nyní zobrazuje doménové štítky a filtruje nabídku podle vybrané kategorie (heuristika přes slug; bez shody fallback na všechny šablony).
  - `frontend-spa/src/locales/{cs,en,de,pl}.json`: doplněné i18n klíče pro doménové štítky a nové názvy/popisné texty šablon.
- Hotovo: sekce 21 je nyní promítnutá i do prakticky použitelných předvoleb přímo v editoru pravidel.
- Následuje: spustit cílenou post-change validaci (`check-locales`, `build-only`, relevantní unit testy), následně `parallel_validation`, zapsat finální shrnutí kroku a vytvořit řádný PR.

### 2026-05-11 13:22 UTC

- Navázáno na poslední otevřený bod etapy 7 (`1284`) a scope byl nejdříve delegován podagentovi pro gap analýzu test coverage; následně proběhla ruční konceptuální validace závěrů nad aktuálním stavem `PipelineFlowDiagram` + utilit.
- Baseline validace před změnami ve `frontend-spa`: po `npm ci` prochází `npm run check-locales`; `npm run build-only && npm run test:unit -- --run` končí na známých pre-existing chybách v jiných dashboard testech (nezpůsobeno tímto krokem).
- Doplněny unit testy normalizace dat:
  - `frontend-spa/src/utils/__tests__/pipelineFlowVisualization.spec.ts`: nové scénáře pro fallback aliasy `effect_config` (`stage_scenario_id`) a ochranu proti nevalidnímu `scenario` ID.
  - `frontend-spa/src/utils/__tests__/conditionTreeVisualization.spec.ts`: normalizace poškozených child uzlů skupiny na bezpečné defaultní group uzly.
- Doplněny unit testy interakcí a synchronizace grafu s formulářovým stavem:
  - `frontend-spa/src/components/__tests__/PipelineFlowDiagram.spec.ts`: synchronizace `initialCategoryId`/`initialStageId` po změně props (simulace změny formuláře) a reset vybraného detailu při aktualizaci requirements, která odebere vybraný uzel.
- Post-change validace pro změněný scope prochází: `npm run test:unit -- --run src/components/__tests__/PipelineFlowDiagram.spec.ts src/utils/__tests__/pipelineFlowVisualization.spec.ts src/utils/__tests__/conditionTreeVisualization.spec.ts` (`33/33`).
- Hotovo: poslední otevřený checkbox etapy 7 je splněn.
- Následuje: spustit `parallel_validation`, zapsat finální shrnutí kroku a vytvořit řádný PR.

### 2026-05-11 12:58 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na zbývající otevřené body etapy 7 (1284/1285), s prioritou minimálního kroku pro nápovědu/klávesové ovládání/přístupnost bez přehlcení uživatele.
- Scope dalšího kroku byl maximalizovaně delegován podagentovi (gap analýza přístupnosti + testovatelnosti), následně proběhla ruční konceptuální validace návrhu nad `PipelineFlowDiagram.vue` a souvisejícími testy.
- Baseline validace před změnami ve `frontend-spa`: po `npm ci` prochází `npm run check-locales`, `npm run build-only` a cílené `npm run test:unit -- src/utils/__tests__/pipelineFlowVisualization.spec.ts src/components/__tests__/PipelineFlowDiagram.spec.ts`.
- Frontend implementace přístupnosti a nápovědy:
  - `frontend-spa/src/components/PipelineFlowDiagram.vue` nyní používá explicitní `aria-label` pro všechny filtry (kategorie/fáze/trigger/stav/typ uzlu),
  - do viewport hlavičky byla doplněna čitelná klávesová nápověda (`+`/`=` zoom in, `-` zoom out, `Enter`/`Space` výběr uzlu),
  - tlačítko sbalení/rozbalení scénáře nyní používá dynamický `aria-label` pro expand/collapse akci.
- Lokalizace doplněny ve `frontend-spa/src/locales/{cs,en,de,pl}.json` pro nové A11y labely a text nápovědy.
- Rozšířeny unit testy `frontend-spa/src/components/__tests__/PipelineFlowDiagram.spec.ts`:
  - přepnutí filtrů na stabilní přístupné selektory přes `aria-label` (místo indexovaných `select[n]`),
  - doplněn test klávesové volby uzlu přes `Space`,
  - doplněna kontrola dynamického `aria-label` u collapse/expand tlačítka scénáře.
- Post-change validace prochází: `npm run check-locales`, `npm run build-only`, `npm run test:unit -- src/components/__tests__/PipelineFlowDiagram.spec.ts src/utils/__tests__/pipelineFlowVisualization.spec.ts`.
- Hotovo: checkbox etapy 7 pro „uživatelskou nápovědu, klávesové ovládání a přístupnost“ je nyní splněný.
- Následuje: dokončit poslední otevřený bod etapy 7 (`1284`) cíleným rozšířením unit testů synchronizace grafu s formulářem v `PipelineSettingsView`.

### 2026-05-11 12:46 UTC

- Navázáno na krok 12:41 UTC: zapracovány navazující review připomínky k čitelnosti helperů a interních metadat v `PipelineFlowDiagram.vue` + `pipelineFlowVisualization.ts` + `PipelineSettingsView.vue`.
- Úpravy zahrnují:
  - vytažení helperů `extractRequirementId` / `extractFulfillmentStatus` + explicitní type guard pro status větve,
  - jasné označení interního trigger kódu (`_triggerCode`) a oddělení interních metadat od zobrazovaných hodnot přes helper `displayableMetaEntries`,
  - doplnění vysvětlujících komentářů k záměrnému exact-match filtrování triggerů z dropdownu.
- Ověřeno po každém kole: `npm run test:unit -- src/components/__tests__/PipelineFlowDiagram.spec.ts src/utils/__tests__/pipelineFlowVisualization.spec.ts` a `npm run build-only` prochází.
- `parallel_validation` už v závěru session hlásí vyčerpání validačního budgetu; poslední dostupné běhy v této session vracely CodeQL bez alertů a pouze stylistické review připomínky, které jsou v tomto kroku zapracované.
- Hotovo: implementační scope tohoto kroku zůstává funkčně i konceptuálně validní a reflektuje požadavek na uživatelsky čitelné (lokalizované) triggery.
- Následuje: v další navazující iteraci dokončit zbývající otevřené body etapy 7 (rozšíření testového pokrytí synchronizace s formulářem, nápověda/klávesové ovládání/přístupnost).

### 2026-05-11 12:41 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na otevřený bod etapy 7 pro napojení grafu na testovací vyhodnocení a log vyhodnocení.
- Další krok byl maximalizovaně delegován podagentovi (gap analýza scope + mapování trigger UX problémů), následně proběhla ruční konceptuální validace závěrů přímo nad `PipelineSettingsView.vue`, `PipelineFlowDiagram.vue`, `pipelineFlowVisualization.ts` a backend kontrakty v `crm/models.py`/`crm/api.py`.
- Baseline validace před změnami ve `frontend-spa` po `npm ci`: `npm run check-locales`, `npm run build-only` a cílené `npm run test:unit -- src/utils/__tests__/pipelineFlowVisualization.spec.ts src/components/__tests__/PipelineFlowDiagram.spec.ts` prochází.
- Frontend implementace uživatelsky čitelných triggerů:
  - přidán sdílený mapovací modul `frontend-spa/src/constants/triggerTypes.ts` (reálné backend trigger typy + lokalizované labely),
  - formulář pravidla, filtry pravidel, filtry logu a filtr triggeru v diagramu nyní používají výběr z přeložených možností místo volného textu s interními kódy,
  - seznam pravidel, tabulka logu a badge/meta v diagramu nyní zobrazují lokalizované názvy triggerů.
- Frontend implementace napojení grafu na test/log vyhodnocení:
  - `PipelineSettingsView.vue` předává do diagramu výstupy testovací evaluace (`outputs` + `testedRuleId`) a aktuálně načtené `ruleEvaluationLogs`,
  - `PipelineFlowDiagram.vue` zvýrazňuje testovaný rule uzel stavem matched/unmatched a requirement uzly stavem větve met/unmet/pending podle `requirement.chain_evaluated` logu.
- Doplněny i18n klíče pro nové trigger labely a stavy vyhodnocení ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Rozšířeny testy:
  - `frontend-spa/src/components/__tests__/PipelineFlowDiagram.spec.ts` o lokalizované trigger labely a vizualizační stavy z test eval/logu,
  - `frontend-spa/src/utils/__tests__/pipelineFlowVisualization.spec.ts` upraven pro přesné filtrování triggeru dle vybrané hodnoty.
- Post-change validace prochází: `npm run check-locales`, `npm run build-only`, `npm run test:unit -- src/utils/__tests__/pipelineFlowVisualization.spec.ts src/components/__tests__/PipelineFlowDiagram.spec.ts`.
- Hotovo: etapa 7 má nyní splněný bod propojení grafu s testovacím vyhodnocením a eval logem, včetně uživatelsky čitelného výběru triggerů.
- Následuje: doplnit zbývající otevřené body etapy 7 (rozšíření unit test pokrytí synchronizace s formulářem, nápověda/klávesové ovládání/přístupnost), následně spustit `parallel_validation` a připravit finální PR souhrn.

### 2026-05-11 12:22 UTC

- Navázáno na krok 12:15 UTC a spuštěna opakovaná validační kola `parallel_validation` po zapracování review připomínek.
- Zapracované review úpravy v `frontend-spa/src/components/PipelineFlowDiagram.vue`:
  - odstraněn duplicitní watcher výběru uzlu,
  - sjednocen formát zoom labelu mezi lokalizacemi,
  - vytaženy konstanty pro krok pan a precision factor zoomu,
  - doplněny stabilní `data-testid`/`data-*` atributy pro zoom/fallback metriky.
- Zapracované review úpravy v `frontend-spa/src/components/__tests__/PipelineFlowDiagram.spec.ts`:
  - testy přepnuty na locale-independent selektory přes `data-testid`,
  - zoom assertions sjednoceny na procentní datový formát,
  - fallback assertion ověřuje přímo `data-hidden-count`.
- Průběžně ověřeno po každém kroku: `npm run build-only` + cílené `npm run test:unit -- src/utils/__tests__/pipelineFlowVisualization.spec.ts src/components/__tests__/PipelineFlowDiagram.spec.ts` prochází.
- Poslední běh `parallel_validation`: code review OK s drobnou připomínkou k očekávané hodnotě hidden count (ponecháno beze změny, protože model limitu záměrně počítá všechny viditelné uzly včetně rule+scenario), CodeQL vypršel na timeoutu a nástroj explicitně nedoporučuje další opakování.
- Následuje: uzavřít tento krok PR souhrnem a navázat dalším otevřeným bodem etapy 7 (napojení grafu na testovací vyhodnocení a log vyhodnocení).

### 2026-05-11 12:15 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na první otevřený bod etapy 7 po dokončení návazných hran: zoom/pan/auto-layout/fallback.
- Další krok byl maximalizovaně delegován podagentovi (gap analýza minimálního scope + acceptance checks), následně proběhla ruční konceptuální validace návrhu proti aktuálním souborům `frontend-spa/src/components/PipelineFlowDiagram.vue` a `frontend-spa/src/components/__tests__/PipelineFlowDiagram.spec.ts`.
- Baseline validace před změnami ve `frontend-spa` po `npm ci`: `npm run check-locales`, `npm run build-only` a cílené `npm run test:unit -- src/utils/__tests__/pipelineFlowVisualization.spec.ts src/components/__tests__/PipelineFlowDiagram.spec.ts` prochází.
- Frontend implementace etapy 7:
  - `frontend-spa/src/components/PipelineFlowDiagram.vue` rozšířen o viewport s ovládáním zoom (`+/-`, Ctrl/Cmd + kolečko), pan (klávesnice + scroll), reset a centrování výběru.
  - Přidáno automatické rozvržení hustoty uzlů přes adaptivní grid dle velikosti grafu a fallback režim pro velké grafy (limit renderovaných uzlů + jasná výzva k filtrování).
  - Zachováno existující filtrování dle kategorie/fáze/triggeru/stavu/typu uzlu a detail uzlu.
- Doplněny i18n klíče pro nové ovládání a nápovědu v `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Rozšířeny unit testy v `frontend-spa/src/components/__tests__/PipelineFlowDiagram.spec.ts` o zoom ovládání, klávesové zkratky viewportu, stav akce centrování a fallback render limit pro velké grafy.
- Hotovo: checkbox etapy 7 pro „zoom/pan/automatické rozvržení/fallback“ je nyní splněný.
- Následuje: navázat dalším otevřeným bodem etapy 7 (napojení grafu na testovací vyhodnocení a log vyhodnocení) a průběžně doplnit další testy + přístupnost.

### 2026-05-11 11:24 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na první otevřený bod po 7C: vizuální správa návazných hran `next_step_on_met`/`next_step_on_unmet` s validačními guardy.
- Scope návrhu byl maximalizovaně delegován podagentovi (rychlá gap analýza + návrh minimálních souborů/testů) a následně proběhla ruční konceptuální validace skutečného stavu nad `frontend-spa/src/utils/pipelineFlowVisualization.ts` a `frontend-spa/src/components/PipelineFlowDiagram.vue`.
- Baseline validace před změnami: po `npm ci` ve `frontend-spa` prochází `npm run check-locales`, `npm run build-only` a cílené `npm run test:unit -- src/utils/__tests__/pipelineFlowVisualization.spec.ts src/components/__tests__/PipelineFlowDiagram.spec.ts`.
- Frontend implementace návazných hran:
  - `frontend-spa/src/utils/pipelineFlowVisualization.ts` nově vrací diagnostiku návazných hran (`requirementLinkDiagnostics`) a validuje chybějící cíl, cross-scenario vazby a cykly (včetně blokace nevalidních hran v diagramu),
  - v utilitě byla zároveň opravena hierarchická vazba tak, aby `next_step_on_*` hrany nepřepisovaly parent/depth stromu uzlů,
  - `frontend-spa/src/components/PipelineFlowDiagram.vue` přidává sekci „návazné vazby požadavků“ s přehledem met/unmet větví a vizuálním stavem validní/nevalidní.
- Doplněny unit testy:
  - `frontend-spa/src/utils/__tests__/pipelineFlowVisualization.spec.ts` rozšířen o scénáře missing target, cross-scenario a cycle,
  - `frontend-spa/src/components/__tests__/PipelineFlowDiagram.spec.ts` rozšířen o render diagnostiky nevalidní návazné vazby.
- Doplněny i18n klíče pro nové UI/validační texty ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Hotovo: checkbox etapy 7 pro vizuální správu návazných hran s validací cyklů a scénářového kontextu je nyní splněný.
- Následuje: navázat dalším otevřeným bodem etapy 7 (zoom/pan/auto-layout/fallback), poté doplnit vazbu na testovací vyhodnocení a auditní log.

### 2026-05-11 11:15 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na první otevřený interaktivní bod etapy 7C: výběr uzlu + detail kontextu (s ponecháním existujícího collapse/expand).
- Další krok byl maximalizovaně delegován podagentovi (návrh minimálního scope, souborů, testů a edge-case kritérií), následně proběhla ruční konceptuální validace návrhu proti aktuálním souborům (`frontend-spa/src/components/PipelineFlowDiagram.vue`, `frontend-spa/src/utils/pipelineFlowVisualization.ts`, `frontend-spa/src/components/__tests__/PipelineFlowDiagram.spec.ts`).
- Baseline validace před úpravami: po `npm ci` ve `frontend-spa` prochází `npm run check-locales`, `npm run build-only` a cílené `npm run test:unit -- src/utils/__tests__/pipelineFlowVisualization.spec.ts src/components/__tests__/PipelineFlowDiagram.spec.ts`.
- Frontend implementace 7C v `frontend-spa/src/components/PipelineFlowDiagram.vue`: přidán interaktivní výběr uzlu (click/keyboard), vizuální zvýraznění vybraného uzlu, automatické čištění výběru při změně filtrů a nový detail panel uzlu (typ, source ID, parent/children, vazby).
- Doplněny i18n klíče pro detail panel ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Rozšířeny testy v `frontend-spa/src/components/__tests__/PipelineFlowDiagram.spec.ts` o scénáře pro výběr uzlu, zobrazení detailu a zrušení výběru.
- Hotovo: interaktivní práce s uzly (výběr + kontext detailu + existující sbalení/rozbalení) je implementovaná a checkbox etapy 7 je aktualizován na splněný.
- Následuje: navázat bodem 7C/7D pro vizuální správu návazných hran `next_step_on_met`/`next_step_on_unmet` s validačními guardy scénáře/cyklů a poté přidat zoom/pan/auto-layout.

### 2026-05-11 10:38 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na poslední otevřený krok etapy 7C s novým prioritním požadavkem: před pokračováním opravit kontrasty/třídy v light i dark verzi pro condition-related UI.
- Další krok byl maximalizovaně delegován podagentovi (audit kontrastů a mapování konkrétních tříd v `ConditionBuilder.vue`, `ConditionTreeViewer.vue`, `PipelineFlowDiagram.vue` a condition sekcích `PipelineSettingsView.vue`), následně proběhla ruční konceptuální validace návrhu a ruční implementace.
- Baseline validace před změnami:
  - `frontend-spa`: po `npm ci` prochází `npm run check-locales` a `npm run build-only`,
  - `npm run test:unit` je v aktuálním repozitáři pre-existing nestabilní kvůli unhandled dashboard chybám mimo tento scope (existující baseline problém).
- Frontend úpravy kontrastů/čitelnosti:
  - `frontend-spa/src/components/ConditionBuilder.vue`: doplněny dark varianty pro obal, vstupy/selecty, texty, odstranění uzlů a pomocné vizuální prvky.
  - `frontend-spa/src/components/ConditionTreeViewer.vue`: doplněny dark varianty pro loading/error/empty stavy, collapse tlačítka, badge typů uzlů, labely a text uzlů.
  - `frontend-spa/src/components/PipelineFlowDiagram.vue`: upraveny kontrastní barvy uzlů/hran (včetně `nodeClass`), legenda, filtry, card meta prvky a edge sekce pro light/dark režim.
  - `frontend-spa/src/views/PipelineSettingsView.vue` (condition části): doplněny dark varianty a čitelné textové barvy pro formuláře pravidel, filtry, test pravidla, log vyhodnocení, scénáře, požadavky a preview.
- Hotovo: priorita „kontrasty a třídy v light/dark verzi pro podmínky“ je pokrytá v hlavních condition UI částech, kde byly vstupy a metadata dříve špatně čitelné.
- Následuje: provést post-change validační běhy (`check-locales`, `build-only`, cílené `test:unit` pro condition scope), spustit `parallel_validation`, zapracovat případné připomínky a pak navázat implementací dalšího otevřeného kroku etapy 7C.

### 2026-05-11 10:30 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na otevřený bod etapy 7B: přehledový diagram vazeb pravidlo → scénář → požadavek → návazný krok.
- Další krok byl maximalizovaně delegován podagentovi (mapování minimálního scope, integrační body, testy a rizika) a následně byla implementace ještě jednou delegovaně zrevidována; relevantní připomínky k trigger/effect rozlišení, aktivační podmínce scénáře a doporučené další fázi byly zapracovány.
- Před úpravami proběhla baseline validace frontendu po `npm ci`: `npm run check-locales`, `npm run build-only` a cílené unit testy pro existující vizualizační/store scope procházejí.
- Frontend implementace etapy 7B:
  - přidána utility vrstva `frontend-spa/src/utils/pipelineFlowVisualization.ts` pro normalizaci read-only flow modelu pravidel, scénářů, požadavků a hran `next_step_on_met` / `next_step_on_unmet`,
  - přidán komponent `frontend-spa/src/components/PipelineFlowDiagram.vue` s filtry podle kategorie, fáze, triggeru, aktivního stavu a typu uzlu, barevným rozlišením efektu/triggeru, collapse/expand scénářů a seznamem směrových vazeb,
  - `frontend-spa/src/views/PipelineSettingsView.vue` nově načítá požadavky všech scénářů vybrané fáze a zobrazuje diagram v nastavení pipeline bez nahrazení existujících editorů,
  - frontend typy `StageRequirementOut/In/PatchIn` doplněny o `next_step_on_met_id` a `next_step_on_unmet_id`,
  - doplněny i18n klíče ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Doplněny unit testy `frontend-spa/src/utils/__tests__/pipelineFlowVisualization.spec.ts`, `frontend-spa/src/components/__tests__/PipelineFlowDiagram.spec.ts` a rozšířen test store `stageScenarios.spec.ts`.
- Post-change validace prochází: `npm run check-locales`, cílené `npm run test:unit -- src/utils/__tests__/pipelineFlowVisualization.spec.ts src/components/__tests__/PipelineFlowDiagram.spec.ts src/stores/__tests__/stageScenarios.spec.ts` a `npm run build-only`.
- Doplňkový `npm run type-check` nadále padá na existujících chybách mimo tento scope (např. `InviteMemberWizard.vue`, `RecordShareModal.vue`, `RecordsView.vue`); nové soubory diagramu nejsou mezi hlášenými chybami.
- Hotovo: v etapě 7 je nyní splněný bod přehledového diagramu vazeb pravidlo → scénář → požadavek → návazný krok.
- Následuje: spustit `parallel_validation`, zapracovat případné připomínky a navázat další částí etapy 7C (interaktivní výběr uzlu a detail uzlu).

### 2026-05-11 09:52 UTC

- Prostudován aktuální stav `podminky.md` a potvrzen navazující implementační scope: začít etapou 7A (read-only strom condition tree + napojení do pipeline nastavení).
- Další krok byl maximalizovaně delegován podagentovi (mapování integračních bodů, minimální bezpečný rozsah, testovací matice) a následně ručně zvalidován přímo nad `frontend-spa/src/views/PipelineSettingsView.vue` a existujícími testy/lokalizacemi.
- Před úpravami proběhla baseline validace dostupných frontend checků: `npm run check-locales` prochází, `npm run build-only` v sandboxu padá na chybějícím `vite` (`not found`) ještě před scope změny.
- Následně po instalaci frontend závislostí (`npm ci`) byla validační sada znovu spuštěna a `check-locales`, `build-only` i cílené `test:unit` pro nový scope procházejí.
- Funkční implementace etapy 7A:
  - přidána utility vrstva `frontend-spa/src/utils/conditionTreeVisualization.ts` pro normalizaci `condition_tree` a sestavení read-only vizualizačního modelu (uzly/hrany),
  - přidán nový read-only komponent `frontend-spa/src/components/ConditionTreeViewer.vue` se stromovým renderem a sbalením/rozbalením skupin,
  - `frontend-spa/src/views/PipelineSettingsView.vue` rozšířen o samostatný režim „Builder / Strom“ v editoru pravidla bez nahrazení stávajícího builderu/JSON režimu.
- Doplněny unit testy pro normalizační utilitu a stromový viewer (`frontend-spa/src/utils/__tests__/conditionTreeVisualization.spec.ts`, `frontend-spa/src/components/__tests__/ConditionTreeViewer.spec.ts`).
- Doplněny i18n klíče pro nové UI texty ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Hotovo: v etapě 7 jsou nyní splněné body pro stromovou vizualizaci condition tree a její napojení do pipeline nastavení.
- Následuje: dokončit cílenou validační sadu (build/test), zapracovat případné připomínky z `parallel_validation` a navázat bodem 7B (přehledový diagram vazeb pravidlo → scénář → požadavek → návazný krok).

### 2026-05-11 09:21 UTC

- Prostudován aktuální stav `podminky.md` a potvrzeno, že etapy 1–6 jsou v dokumentu vedené jako dokončené; nové zadání navazuje návrhem další fáze pro grafickou správu složitých podmínek.
- Návrh mindmapy byl delegován na podagenta (analýza dokumentu, aktuálního frontendového stavu a rizik) a následně ručně zvalidován proti `podminky.md` a dostupným frontend skriptům.
- Do sekce 15 byla doplněna nová etapa 7 pro interaktivní grafickou mindmapu pravidel, scénářů, požadavků a návazných kroků.
- Do sekce 16 byla doplněna rizika a opatření související s nečitelností velkých grafů, výkonem a synchronizací grafu s formulářovým editorem.
- Doplněna nová sekce 20 s podrobným návrhem řešení: read-only vizualizace, flow diagram, interaktivní navigace, řízené editace, napojení na testovací vyhodnocení/audit a validační kritéria.
- Závěrečná validace proběhla přes `parallel_validation`: code review bez připomínek, CodeQL přeskočen jako triviální dokumentační změna.
- Hotovo: další fáze práce je popsána jako konkrétní implementační plán v dokumentu.
- Následuje: v navazujícím implementačním scope začít normalizačními utilitami a read-only vizualizací condition tree, poté pokračovat přehledovým flow diagramem.

### 2026-05-11 09:15 UTC

- Prostudován aktuální stav `podminky.md` a potvrzeno, že checklistové body etap 14/15 zůstávají splněné; navázáno na otevřený finální krok z 09:09 UTC.
- Kontrolní audit dalšího postupu byl maximalizovaně delegován na podagenta (rekapitulace hotového stavu + minimální navazující kroky) a následně proběhla ruční konceptuální validace závěrů přímo nad repozitářem.
- Ověřen stav pracovního stromu (`git status`): branch je čistá, bez necommitnutých změn.
- Spuštěna `parallel_validation`; nástroj v aktuálním stavu větve vrátil `No changes detected`, tedy bez nových validačních připomínek.
- Hotovo: potvrzen finalizační stav a připraven navazující dokumentační zápis pro řádné PR uzavření tohoto kroku.
- Následuje: vytvořit řádný pull request s tímto průběžným záznamem a po jeho otevření navázat dalším implementačním scope dle nového zadání.

### 2026-05-11 09:09 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na poslední krok z 08:48 UTC (dostupná validace + příprava finálního PR).
- Další validační krok byl maximalizovaně delegován na podagenta (spuštění frontend/backend checků a sumarizace pádů), následně proběhla ruční konceptuální i funkční validace zjištění přímo nad `crm/api.py` a `crm/tests.py`.
- Opraven backend regresní bug v kontext builderu (`crm/api.py`): lookup vlastníka firmy byl přepnut z neplatného `Membership.role` na aktuální M2M model (`roles__code="owner"`), což odstraňuje pád `FieldError` při update záznamu.
- Opraveny regresní backend testy v `crm/tests.py` (`ConditionRulesApiEndpointsTest`): sjednocení fixture uživatele (`self.owner`), doplnění importu `RequirementType`, oprava create payloadu `StageRequirement` (včetně `firm`) a oprava aktivity na správné pole `user` místo neexistujícího `created_by`.
- Provedena post-change funkční validace:
  - `python manage.py test crm.tests.ConditionRulesApiEndpointsTest.test_active_requirements_payload_contains_activity_links crm.tests.ConditionRulesApiEndpointsTest.test_stage_requirement_rejects_cyclic_chaining_links crm.tests.RecordUpdateAPITest.test_patch_status_creates_activity` prochází (`3/3`),
  - `frontend-spa`: `npm run check-locales`, `npm run build-only`, `npm run test:unit -- src/stores/__tests__/ruleEvaluationLogs.spec.ts src/stores/__tests__/stageScenarios.spec.ts src/views/__tests__/RecordDetailView.spec.ts` prochází (`10/10`).
- Hotovo: validační krok navazující na 08:48 UTC je dokončený, identifikované regresní chyby jsou opravené a cílené checky opět procházejí.
- Následuje: spustit `parallel_validation`, zapracovat případné relevantní připomínky a vytvořit řádný finální PR.

### 2026-05-11 08:48 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na tři otevřené body etapy 5 (`návazné kroky`, `stav splnění kroků`, `audit řetězení`).
- Další kroky byly maximalizovaně delegovány na podagenta (gap analýza backend implementace + návrh minimálního cohesive scope) a následně proběhla ruční konceptuální validace návrhu proti aktuálním souborům `crm/models.py`, `crm/api.py`, `crm/tests.py`.
- Backend implementace etapy 5 v `crm/models.py` + migraci `crm/migrations/0011_stagerequirement_chaining_links.py`: přidány návazné kroky mezi požadavky (`next_step_on_met`, `next_step_on_unmet`) pro explicitní řetězení kroků scénáře.
- Backend API implementace etapy 5 v `crm/api.py`: rozšířena schema `StageRequirement*` o návazné kroky, přidána validace odkazů v rámci stejného scénáře (včetně ochrany proti cyklům), doplněn výpočet `is_active_step` + `fulfillment_status` v payloadu aktivních požadavků a audit změn řetězení přes `RuleEvaluationLog` (`requirement.chain_evaluated`).
- Backend testy etapy 5 v `crm/tests.py`: rozšířeno pokrytí endpointů scénářů/požadavků o řetězení kroků, stav splnění kroků v payloadu a auditní logy; doplněna regresní kontrola zamítnutí cyklického řetězení.
- Baseline i post-change běh backend testů v sandboxu aktuálně blokuje pre-existing limit prostředí (`django` není nainstalované), bez možnosti lokálního ověření běhu test suite v tomto runtime.
- Hotovo: otevřené body etapy 5 (`návazné kroky`, `stav splnění kroků`, `audit řetězení`) jsou implementované a označené jako splněné.
- Následuje: provést dostupnou validační kontrolu v aktuálním prostředí, spustit `parallel_validation`, zapracovat případné připomínky a připravit finální PR souhrn.

### 2026-05-11 08:09 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na poslední otevřený bod etapy 6 (`šablony pravidel`).
- Další kroky byly maximalizovaně delegovány na podagenty (baseline validace + gap analýza implementačního scope + nezávislý návrh frontend-only varianty) a následně proběhla ruční konceptuální validace návrhů proti aktuálním souborům.
- Frontend implementace etapy 6 v `frontend-spa/src/views/PipelineSettingsView.vue`: přidána sekce šablon pravidel s možností otevřít/skrýt katalog, použít předpřipravenou šablonu a předvyplnit formulář pravidla přes existující builder/create flow (bez hardcodovaného backend endpointu).
- Doplněny šablony pro praktické scénáře (`owner required`, `contact recommended`, `high value gate`, `recent activity gate`, `review recommendation`) včetně normalizace condition tree/effect config do existujícího formuláře.
- Doplněny i18n klíče pro nový UI flow ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Provedena post-change validace: `npm run check-locales`, `npm run build-only` a cílené unit testy (`ruleEvaluationLogs.spec.ts`, `stageScenarios.spec.ts`) procházejí.
- Provedena bezpečnostní/review validace přes `parallel_validation` (CodeQL bez alertů, review připomínky zapracovány v rámci template konfigurace).
- Hotovo: bod etapy 6 „Přidat šablony pravidel“ je dokončený a označený jako splněný.
- Následuje: pokračovat dalšími otevřenými body etapy 5 (`návazné kroky`, `stav splnění kroků`, `audit řetězení`) ve stejném režimu delegace + ruční konceptuální/funkční validace.

### 2026-05-11 07:38 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na první otevřený bod etapy 6 (`log vyhodnocení do administrace`).
- Další krok byl maximalizovaně delegován na podagenta (gap analýza realizovatelného scope + mapování backend/frontend integračních bodů) a následně proběhla ruční konceptuální validace návrhu.
- Před úpravami proběhla baseline validace frontendu: `npm run check-locales`, `npm run build-only` a referenční unit test `src/stores/__tests__/stageScenarios.spec.ts` procházejí.
- Frontend implementace etapy 6 v `frontend-spa/src/stores/ruleEvaluationLogs.ts`: přidán nový store pro endpoint `/api/v1/crm/rule-evaluation-logs` s filtrováním (`trigger_type`, `result`, `record_id`, `rule_id`) a stránkováním (`page`, `page_size`, `hasMore`).
- Frontend implementace etapy 6 v `frontend-spa/src/views/PipelineSettingsView.vue`: doplněna administrativní sekce logu vyhodnocení pravidel (filtry, loading/error/empty stavy, tabulka záznamů a stránkování další/předchozí).
- Frontend testy etapy 6 v `frontend-spa/src/stores/__tests__/ruleEvaluationLogs.spec.ts`: pokryto načtení logu s filtry, chybový stav i reset store.
- Doplněny i18n klíče pro nový UI flow ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Hotovo: bod etapy 6 „Přidat log vyhodnocení do administrace“ je dokončený a označený jako splněný.
- Následuje: provést post-change validaci (`check-locales`, `build-only`, cílené unit testy), navázat bezpečnostní/review validací a pokračovat dalším otevřeným bodem etapy 6 (`šablony pravidel`).

### 2026-05-11 07:21 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na dokončené etapy 13.x/14.x; cílem bylo sjednotit souhrnnou etapovou sekci 15 se skutečně implementovaným stavem.
- Další krok byl maximalizovaně delegován na podagenta (kontrola gapů mezi sekcemi 13/14 a etapovými checkboxy v sekci 15) a následně proběhla ruční konceptuální validace závěrů přímo nad dokumentem.
- Aktualizována sekce 15: etapy 1–4 jsou nyní plně označené jako dokončené; v etapě 5 označena dokončená ochrana proti cyklům, priority a testy řetězení; v etapě 6 označeny dokončené body builder/vnořené skupiny/preview/testovací vyhodnocení.
- Hotovo: souhrnný plán etap v `podminky.md` nyní odpovídá reálnému stavu implementace uvedenému v detailních sekcích backendu/frontendu.
- Následuje: navázat implementací zbývajících otevřených bodů etapy 5 (`návazné kroky`, `stav splnění kroků`, `audit řetězení`) a etapy 6 (`log vyhodnocení do administrace`, `šablony pravidel`) ve stejném režimu delegace + ruční konceptuální/funkční validace.

### 2026-05-11 07:16 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na poslední dva otevřené body frontend etapy 14.9 (testy renderu panelu požadavků + splněné/nesplněné požadavky).
- Další krok byl maximalizovaně delegován na podagenta (gap analýza minimálního test scope v `RecordDetailView.vue`) a následně proběhla ruční konceptuální validace návrhu testů.
- Před úpravami proběhla baseline validace frontendu: po instalaci závislostí (`npm ci`) prochází `check-locales`, `build-only` i referenční existující unit test (`StreamlineFilterDropdown.spec.ts`).
- Frontend test implementace 14.9 v `frontend-spa/src/views/__tests__/RecordDetailView.spec.ts`: přidány cílené testy pro render panelu požadavků fáze (včetně prázdného stavu) a pro rozlišení splněných/nesplněných požadavků (sekce unmet/met, badge blokace/upozornění, vazba na `satisfied_by_activity_id`).
- Provedena post-change validace: nové cílené testy procházejí (`2/2`), `check-locales` prochází a `build-only` prochází.
- Hotovo: v etapě 14.9 jsou nyní dokončeny i zbývající dva body pro render panelu požadavků a rozlišení splněných/nesplněných požadavků.
- Následuje: navázat další otevřenou frontend/backlog etapou podle pořadí v `podminky.md` ve stejném režimu delegace + ruční konceptuální/funkční validace.

### 2026-05-11 07:10 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na otevřenou frontend etapu 14.9 (testy frontendu).
- Další krok byl maximalizovaně delegován na podagenta (gap analýza minimálního pokrytí 14.9) a následně proběhla ruční konceptuální validace návrhu test scope.
- Před úpravami proběhla baseline validace frontendu: po instalaci závislostí (`npm ci`) prochází `check-locales` i referenční existující unit test (`StreamlineFilterDropdown.spec.ts`).
- Frontend test implementace 14.9 v `frontend-spa/src/components/__tests__/ConditionBuilder.spec.ts`: pokryto chování builderu pro výběr standardního pole, kategoriového pole (včetně resetu `operator/value`) a Streamline toolu, plus guard na disable operátoru bez validního kategoriového pole.
- Frontend test implementace 14.9 v `frontend-spa/src/stores/__tests__/records.spec.ts`: pokryta normalizace block/warning issue payloadu a stage-change flow ve store (`patchStage` rollback + `stage_change_evaluation`, `updateRecord` warning payload).
- Frontend test implementace 14.9 v `frontend-spa/src/stores/__tests__/stageScenarios.spec.ts`: pokryty scénářové CRUD toky, načtení requirementů, preview endpoint a prázdné/chybové stavy store.
- Provedena post-change validace: nové cílené testy procházejí (`12/12`), `check-locales` prochází a frontend `build-only` prochází.
- Hotovo: v etapě 14.9 jsou nyní dokončené body pro blokaci/upozornění při změně fáze, builder + výběr polí/toolu, editor scénářů a prázdné/chybové stavy.
- Následuje: dokončit zbývající body 14.9 pro render panelu požadavků a rozlišení splněných/nesplněných požadavků (cílené testy `RecordDetailView`).

### 2026-05-11 06:49 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na otevřenou frontend etapu 14.8 (napojení na kategoriová pole).
- Další krok byl maximalizovaně delegován na podagenta (gap analýza 14.8 v `ConditionBuilder.vue`, `PipelineSettingsView.vue`, `RecordDetailView.vue`) a následně proběhla ruční konceptuální validace zjištění.
- Před úpravami proběhla baseline validace dostupných checků: frontend `check-locales` prochází; frontend `build-only` padá na pre-existing chybějícím nástroji `vite`; backend cílené testy nelze spustit kvůli chybějící závislosti `django` v sandboxu.
- Frontend implementace 14.8 v `frontend-spa/src/components/ConditionBuilder.vue`: výběr operátoru je nyní typově vázán na vybrané kategoriové pole (operátory se nabídnou až po výběru pole), při změně kategoriového pole se resetuje operátor/hodnota, aby nevznikla nevalidní kombinace.
- Frontend implementace 14.8 v `frontend-spa/src/views/PipelineSettingsView.vue`: preview condition tree nyní pro `category_field` zobrazuje čitelný label pole místo interního `field_key`; načítání pravidel je pevně svázáno s vybranou kategorií v kontextu detailu kategorie.
- Frontend implementace 14.8 v `frontend-spa/src/views/RecordDetailView.vue`: akce „opravit pole“ ve validačním modalu při změně fáze nově pro podporovaná pole rovnou otevírá rychlou inline editaci.
- Hotovo: etapa 14.8 je nyní kompletně dokončená a všechny checkboxy v této sekci jsou označené jako splněné.
- Následuje: navázat další otevřenou frontend etapou 14.9 (testy frontendu) ve stejném režimu delegace + ruční konceptuální/funkční validace.

### 2026-05-11 06:28 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na první otevřenou frontend etapu 14.7 (napojení na Streamline).
- Další krok byl maximalizovaně delegován na podagenta (gap analýza 14.7 + mapování integračních bodů v `RecordDetailView.vue`, `crm/api.py`, `crm/tests.py`) a následně proběhla ruční konceptuální validace návrhu.
- Před úpravami proběhla baseline validace dostupných checků: frontend `check-locales` prochází; frontend `build-only` padá na pre-existing chybějícím nástroji `vite`; backend cílené testy nelze spustit kvůli chybějící závislosti `django` v sandboxu.
- Backend implementace 14.7: v `crm/condition_rules.py` byl rozšířen condition context aktivit o `id`; v `crm/api.py` byl payload `/api/v1/crm/records/{id}/active-stage-requirements` doplněn o `scenario_activated_by_activity_id` a u požadavků o `satisfied_by_activity_id`, včetně deterministického dohledání odpovídající Streamline aktivity podle condition tree.
- Backend testy rozšířeny v `crm/tests.py` (`ConditionRulesApiEndpointsTest`) o regresní kontroly nových polí v payloadu `active-stage-requirements` včetně scénáře, kde aktivita současně aktivuje scénář i splní požadavek.
- Frontend implementace 14.7 v `frontend-spa/src/views/RecordDetailView.vue`: panel požadavků fáze nyní zobrazuje aktivitu, která aktivovala scénář, a aktivitu, která splnila požadavek; u nesplněných aktivitních požadavků přidáno „Rychle vytvořit aktivitu“ s otevřením správného Streamline toolu podle backend metadata (bez hardcodování toolů).
- Frontend implementace 14.7 doplněna o refresh panelu požadavků po `@activity-added` ze `StreamlineCreateModal`, aby se splnění požadavků propsalo okamžitě.
- Doplněny i18n klíče pro nový 14.7 UI flow ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Provedena post-change validace: frontend `check-locales` prochází; frontend `build-only` i backend cílené testy nadále blokují stejné pre-existing limity prostředí (`vite`, `django`).
- Hotovo: etapa 14.7 je nyní kompletně dokončená a všechny checkboxy v této sekci jsou označené jako splněné.
- Následuje: navázat další otevřenou frontend etapou 14.8 (napojení na kategoriová pole) ve stejném režimu delegace + ruční konceptuální/funkční validace.

### 2026-05-11 06:03 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na otevřenou frontend etapu 14.6 (editor scénářů fáze).
- Další krok byl maximalizovaně delegován na podagenta (gap analýza 14.6 + mapování backend/frontend integračních bodů v `crm/api.py`, `crm/tests.py`, `PipelineSettingsView.vue`, `conditionRules.ts`), následně proběhla ruční konceptuální validace návrhu.
- Před úpravami proběhla baseline validace dostupných checků: frontend `check-locales` prochází; frontend `type-check`/`build-only` padají na pre-existing chybějících nástrojích (`vue-tsc`, `vite`); backend `flake8`/`manage.py test` nelze spustit kvůli chybějícím závislostem (`flake8`, `django`) v sandboxu.
- Backend implementace 14.6: v `crm/api.py` doplněny endpointy pro DELETE scénáře fáze a CRUD požadavků scénáře (`POST/PATCH/DELETE /scenarios/{scenario_id}/requirements`) včetně nových schema vstupů `StageRequirementIn` a `StageRequirementPatchIn`.
- Backend testy rozšířeny v `crm/tests.py` (`ConditionRulesApiEndpointsTest`) o pokrytí PATCH/DELETE scénáře a CRUD flow požadavků scénáře, včetně validace změny `blocking` a návazného payloadu `active-stage-requirements`.
- Frontend implementace 14.6: přidán nový store `frontend-spa/src/stores/stageScenarios.ts` (list/create/update/delete scénářů, list/create/update/delete požadavků, preview přes testovací záznam).
- Frontend implementace 14.6 ve `frontend-spa/src/views/PipelineSettingsView.vue`: doplněna sekce editoru scénářů fáze (výběr fáze, seznam scénářů, create/edit/delete, aktivační podmínka přes `ConditionBuilder`, doporučená další fáze, priorita, zapnutí/vypnutí), editor požadavků scénáře (seznam + create/edit/delete + blocking toggle) a preview na testovacím záznamu.
- Doplněny nové i18n klíče pro scénáře/požadavky/preview ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Po delegované validační revizi a code-review připomínkách doplněny korekce: chybějící locale klíče pro tlačítka update, oddělení inline handleru editace scénáře do samostatné funkce, zpřesnění integer vstupů (`step=1`) a drobný cleanup redundantní kontroly 204 v `stageScenarios` store.
- Hotovo: etapa 14.6 je nyní kompletně dokončená a všechny checkboxy v této sekci jsou označené jako splněné.
- Následuje: navázat další otevřenou frontend etapou 14.7 (napojení na Streamline) ve stejném režimu delegace + ruční konceptuální/funkční validace.

### 2026-05-11 05:51 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na otevřenou frontend etapu 14.5 (builder podmínek).
- Další krok byl maximalizovaně delegován na podagenta (detailní mapování 14.5 proti `PipelineSettingsView.vue`, `conditionRules.ts`, `crm/condition_rules.py`), následně proběhla ruční konceptuální validace návrhu a implementace.
- Před úpravami proběhla baseline validace ve frontendu: `check-locales` prochází; `type-check` a `build-only` padají na pre-existing chybějících nástrojích v sandboxu (`vue-tsc`, `vite`).
- Funkční implementace 14.5: přidán nový rekurzivní komponent `frontend-spa/src/components/ConditionBuilder.vue` s podporou výběru zdroje podmínky (standardní pole, kategoriové pole, Streamline aktivita/tool, související entita), operátoru, hodnoty, časového okna, skupin `AND/OR` a vnořených skupin.
- Integrace builderu do `frontend-spa/src/views/PipelineSettingsView.vue`: pravidlový formulář nyní umí přepínat mezi vizuálním builderem a JSON režimem, validuje neúplné podmínky před uložením a zobrazuje čitelný preview text pravidla.
- Následná validační revize byla znovu delegována podagentovi (konceptuální + funkční kontrola) a zapracována korekce typového mapování hodnot pro `streamline_activity/streamline_tool` (`eq/neq` nyní boolean selektor), cleanup hodnot při přepínání operátoru a doplnění validace neplatného `source_type`.
- Doplněny i18n klíče pro nový builder flow ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Hotovo: etapa 14.5 je nyní kompletně dokončená a všechny checkboxy v této sekci jsou označené jako splněné.
- Následuje: navázat další otevřenou frontend etapou 14.6 (editor scénářů fáze) ve stejném delegovaném režimu s ruční konceptuální/funkční validací.

### 2026-05-10 21:24 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na zbývající otevřené body 14.4 (vytvoření/úprava/deaktivace/kopírování/testovací vyhodnocení pravidla).
- Další krok byl maximalizovaně delegován na podagenta pro mapování API kontraktů a UI integračních bodů (`PipelineSettingsView.vue`, `conditionRules.ts`), následně proběhla ruční implementace a druhá konceptuální validační revize změn.
- Funkční implementace ve store `frontend-spa/src/stores/conditionRules.ts`: doplněny typy a metody `createRule`, `createRuleFromExisting` (helper kopie přes create payload), `deactivateRule`, `testEvaluation` + odpovídající payload/output typy.
- Funkční implementace ve view `frontend-spa/src/views/PipelineSettingsView.vue`: doplněn editor pravidla (create/edit), akce nad položkou (deactivate/copy), testovací vyhodnocení nad konkrétním pravidlem (rule_id + record_id) a navazující toast/error handling.
- Doplněny nové i18n klíče pro celý nový UI flow ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Provedena konceptuální/funkční validace v rámci scope: mapování payloadů odpovídá endpointům `POST/PATCH/DELETE /condition-rules` a `POST /condition-rules/test-evaluation/run`; změny jsou omezené na frontend + dokumentaci.
- Hotovo: etapa 14.4 je nyní kompletně dokončená včetně create/edit/deactivate/copy/test-evaluation.
- Následuje: navázat další otevřenou frontend etapou 14.5 (builder podmínek) ve stejném delegovaném režimu s ruční validační kontrolou.

### 2026-05-10 20:56 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na první otevřené body etapy 14.4 (editor pravidel: seznam + filtry + stav zapnuto/vypnuto).
- Další krok byl maximalizovaně delegován na podagenta (mapování integračních bodů backend API/frontend UI pro `condition-rules`) a po implementaci proběhla ještě druhá nezávislá delegovaná validační revize změn; následně proběhla ruční konceptuální kontrola.
- Před úpravami proběhla baseline validace: dostupné checky v prostředí hlásí pre-existing limity závislostí (`vue-tsc`, `run-s`, `vitest`, `vite`, `flake8`, `django`, `pip-audit` nejsou v sandboxu dostupné), takže plné lint/test/build běhy neběžely; `frontend check-locales` byl dostupný.
- Funkční implementace 14.4 v `frontend-spa/src/stores/conditionRules.ts`: přidán nový store pro načítání seznamu pravidel přes `/api/v1/crm/condition-rules` s query filtry (`category_id`, `stage_id`, `trigger_type`, `is_active`) a PATCH update pravidla (toggle `is_active`).
- Funkční implementace 14.4 v `frontend-spa/src/views/PipelineSettingsView.vue`: přidána sekce „Pravidla podmínek“ v nastavení pipeline se seznamem pravidel, filtry podle kategorie/fáze/triggeru/stavu, loading/error/empty stavy a přepínání zapnuto/vypnuto přímo v seznamu.
- Doplněny nové i18n klíče pro pravidla a filtry ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Provedena post-change validace: `frontend check-locales` prochází; ostatní frontend/backend checky nadále blokují stejné pre-existing limity prostředí (chybějící nástroje/závislosti), bez nové regresní informace vůči tomuto scope.
- Po code review doplněna čistící úprava: odstraněno duplicitní načítání seznamu pravidel (sjednocení přes watcher `selectedCategoryId`) a upraven rendering triggeru z `break-all` na `break-words`.
- Opakovaný běh `parallel_validation`: CodeQL bez alertů; dvě review poznámky ke grantům byly vyhodnoceny jako false-positive (načítání grantů je nadále zajištěno watcherem při změně kategorie a explicitním reloadem po operacích s granty).
- Hotovo: v etapě 14.4 jsou nyní dokončené body pro seznam pravidel, filtrování podle kategorie/fáze/triggeru a stav zapnuto/vypnuto.
- Následuje: navázat zbývajícími body 14.4 (vytvoření, úprava, deaktivace, kopírování, testovací vyhodnocení pravidla) ve stejném režimu delegace + ruční konceptuální/funkční validace.

### 2026-05-10 20:13 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na poslední otevřenou frontend etapu 14.3 (validace při změně fáze).
- Další krok byl maximalizovaně delegován na podagenta (mapování všech toků změny fáze v `RecordsView.vue` a `RecordDetailView.vue`, včetně rozboru payloadu `stage_change_evaluation`) a následně proběhla ruční konceptuální validace proti aktuálním souborům (`frontend-spa/src/stores/records.ts`, `frontend-spa/src/views/RecordsView.vue`, `frontend-spa/src/views/RecordDetailView.vue`, `crm/api.py`).
- Před úpravami proběhla baseline validace: frontend `check-locales` prochází, frontend `type-check` padá na pre-existing chybách mimo scope; backend `pip-audit` hlásí pre-existing `twisted 25.5.0 / CVE-2026-42304`, `flake8` i plný `manage.py test` mají pre-existing nálezy mimo tento scope.
- Funkční implementace 14.3 ve store `records.ts`: `updateRecord` i `patchStage` nyní vrací strukturovaná data `stageChangeEvaluation` a `code` (včetně error větve `stage_change_blocked`) tak, aby UI mohlo odlišit blokace a upozornění.
- Funkční implementace 14.3 v `RecordsView.vue`: drag-and-drop i terminal move flow nově zobrazují validační modal pro blokace/upozornění; při blokaci je záznam vrácen do původní fáze přes existující rollback v `patchStage`, při upozornění zůstává přesun zachován a uživatel může pokračovat.
- Funkční implementace 14.3 v `RecordDetailView.vue`: změna fáze z detailu nově zpracovává `stage_change_evaluation`, zobrazuje modal s blokacemi/upozorněními a nabízí rychlé akce „doplnit pole“ / „vytvořit požadovanou aktivitu“ přes relevantní metadata v `effect_config`.
- Doplněny nové i18n klíče validačního modalu ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Provedena cílená validace po změnách: frontend `check-locales` a `build-only` procházejí; cílené backend testy `RecordUpdateAPITest.test_stage_change_blocked_returns_400_and_logs` a `RecordUpdateAPITest.test_stage_change_warning_returns_200_with_evaluation` procházejí.
- Doplňková validační revize (`parallel_validation`) proběhla úspěšně bez CodeQL alertů; připomínky code review (duplicitní normalizace issue payloadu, typová přesnost `effect_config`, drobné čistění UI handlerů) byly zapracovány.
- Frontend `type-check` a `test:unit` nadále padají na pre-existing chybách mimo scope (stejně jako před touto změnou), bez vazby na implementovaný rozsah 14.3.
- Hotovo: etapa 14.3 je nyní kompletně dokončená a všechny checkboxy v této sekci jsou označené jako splněné.
- Následuje: navázat etapou 14.4 (editor pravidel) ve stejném režimu delegace + ruční konceptuální/funkční validace.

### 2026-05-10 20:08 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na poslední otevřené body 14.2 (odkazy na relevantní pole a relevantní Streamline aktivity).
- Další krok byl maximalizovaně delegován na podagenta (gap analýza 14.2 v `RecordDetailView.vue` a mapování integračních bodů) a následně proběhla ruční konceptuální validace návrhu proti aktuálním souborům (`crm/api.py`, `crm/condition_rules.py`, `RecordDetailView.vue`).
- Před úpravami proběhla baseline validace CI příkazů: frontend `check-locales`, `test:unit`, `build-only` procházejí; frontend `type-check`/`lint` i backend `flake8`/plný `manage.py test` mají pre-existing chyby mimo scope.
- Funkční implementace backendu: `_refresh_active_stage_scenario` nyní pro každý požadavek vrací odvozené metadata `relevant_field_key`, `relevant_activity_type`, `relevant_tool_type` (extrahované z condition tree), aby frontend mohl zobrazit kontextové odkazy bez dalšího privilegovaného API.
- Funkční implementace frontendu v `RecordDetailView.vue`: panel požadavků fáze nyní zobrazuje odkazy „Přejít na pole“ a „Přejít na aktivity“ (pro splněné i nesplněné položky), umí scrollnout/zdůraznit relevantní pipeline pole a filtrovat/posunout na relevantní Streamline aktivity.
- Doplněny i18n klíče odkazů ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Rozšířeny backend testy v `crm/tests.py` o kontrolu nových referenčních metadat v `active-stage-requirements` payloadu a o regresní kontrolu mapování kategoriového pole.
- Hotovo: v etapě 14.2 jsou dokončeny i zbývající body pro odkazy na relevantní pole a relevantní Streamline aktivity.
- Následuje: pokračovat etapou 14.3 (validace při změně fáze) ve stejném režimu delegace + ruční konceptuální/funkční validace.

### 2026-05-10 19:50 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na otevřenou frontend etapu 14.2 (panel požadavků fáze).
- Další krok byl maximalizovaně delegován na podagenty (analýza integračních míst ve `frontend-spa/src/views/RecordDetailView.vue` + ověření schema `StageScenarioOut`) a následně proběhla ruční konceptuální validace návrhů proti aktuálním souborům (`RecordDetailView.vue`, `crm/api.py`, locale soubory).
- Před úpravami proběhla baseline validace prostředí: `check-locales` prochází; ostatní frontend/backend checky aktuálně padají na chybějících závislostech v sandboxu (`vue-tsc`, `run-s`, `vitest`, `vite`, `django`, `flake8`) ještě před scope změny.
- Funkční implementace 14.2 v `RecordDetailView.vue`: přidán panel požadavků fáze s načtením endpointu `/api/v1/crm/records/{id}/active-stage-requirements`, zobrazením aktivního scénáře, rozdělením na splněné/nesplněné požadavky, zvýrazněním blokací a upozornění a doplněním doporučeného dalšího kroku podle `recommended_next_stage_id`.
- Následná validační revize (delegovaná na podagenta) odhalila permission riziko při čtení scénářů přes endpoint vyžadující `CATEGORY_MANAGE`; fix aplikován rozšířením payloadu `/records/{id}/active-stage-requirements` o metadata aktivního scénáře (`active_stage_scenario_name`, `recommended_next_stage_id`, `recommended_next_stage_name`) a frontend byl přepnut na tento payload bez dalšího privileged API volání.
- Po code review byl doplněn tvrdší filtr viditelnosti požadavků (`visible_to_user === true`), aby se v panelu nikdy nezobrazily neexplicitně viditelné položky.
- Rozšířen backend test `ConditionRulesApiEndpointsTest` pro kontrolu nových polí endpointu `active-stage-requirements`.
- Doplňeny všechny potřebné i18n klíče panelu ve `frontend-spa/src/locales/{cs,en,de,pl}.json`.
- Provedena cílená validace po změnách: `python manage.py test crm.tests.ConditionRulesApiEndpointsTest` prochází (`4/4`), frontend `check-locales` a `build-only` procházejí; frontend `type-check` stále padá na pre-existing chybách mimo scope.
- Hotovo: v etapě 14.2 jsou nyní dokončené body pro komponentu aktivního scénáře, splněné/nesplněné/blokující/upozornění, doporučený další krok a empty/loading/error stavy.
- Následuje: navázat zbývajícími body 14.2 (odkazy na relevantní pole a Streamline aktivity), následně pokračovat etapou 14.3 (validace při změně fáze) ve stejném režimu delegace + ruční konceptuální/funkční validace.

### 2026-05-10 19:28 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na další otevřený bod 13.11 (backend test matrix).
- Další krok byl maximalizovaně delegován na podagenta (gap analýza pokrytí 13.11 + návrh minimálních doplňujících testů) a následně proběhla ruční konceptuální validace návrhu proti aktuálním souborům (`crm/tests.py`, `crm/api.py`).
- Před úpravami proběhla baseline validace prostředí: frontend `check-locales` a `build-only` procházejí; frontend `type-check`/`lint`/`test:unit` mají pre-existing chyby mimo scope; backend `pip-audit` hlásí pre-existing `twisted 25.5.0 / CVE-2026-42304`; backend `flake8` a plný `manage.py test` mají pre-existing nálezy mimo tento scope.
- Funkční doplnění backend testů v `crm/tests.py`: přidány regresní scénáře pro konkrétní Streamline `tool_type`, pro větvení aktivního scénáře podle hodnoty pole s preferencí vyšší priority a pro řetězení triggerů (blokace `record.stage_change_requested` nevyvolá `record.stage_changed`).
- Provedena funkční validace nových testů cíleným během: `RecordUpdateAPITest.test_stage_change_block_does_not_trigger_stage_changed_rules`, `RecordUpdateAPITest.test_patch_standard_field_change_prefers_higher_priority_matching_scenario`, `ConditionRulesTest.test_streamline_tool_source_supports_explicit_tool_type` procházejí.
- Doplňkový běh fokusované sady condition-engine testů potvrdil pre-existing chybu mimo scope (`FieldError` v `_build_record_automation_context` při filtru membership podle `role`), bez vazby na nově přidané testy.
- Hotovo: bod 13.11 je nyní kompletně dokončený.
- Následuje: navázat frontend částí 14.2 (panel požadavků fáze) stejným režimem delegace + ruční konceptuální/funkční validace.

### 2026-05-10 18:46 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na otevřený bod 13.10 (oprávnění).
- Další krok byl maximalizovaně delegován na podagenta (gap analýza + návrh minimální implementace) a následně proběhla ruční konceptuální validace proti aktuálním souborům (`crm/api.py`, `firms/models.py`, `crm/tests.py`).
- Před úpravami proběhla baseline validace prostředí: backend cílené testy `ConditionRulesApiEndpointsTest` procházejí; frontend checky padají na pre-existing TypeScript chybách mimo tento scope; backend flake8 obsahuje pre-existing nálezy mimo rozsah změny.
- Funkční implementace oprávnění/auditu v API: endpointy condition-rules/scenarios/logs zůstávají explicitně za `Permission.CATEGORY_MANAGE` a nově jsou pokryté negativními testy pro worker roli (403), aby nedocházelo k odhalení dat bez oprávnění.
- Doplněn audit změn pravidel: při create/update/deactivate `ConditionRule` se nyní zapisuje `PermissionAuditLog` s akcemi `condition_rule.created`, `condition_rule.updated`, `condition_rule.deactivated` a payloadem změn.
- Rozšířen katalog akcí `PermissionAuditLog.ACTION_CHOICES` o condition-rule audit události.
- Rozšířeny backend testy `ConditionRulesApiEndpointsTest` o kontrolu audit trailu a o negativní permission scénáře pro list rules/scenarios/logs.
- Hotovo: bod 13.10 je nyní kompletně dokončený.
- Následuje: navázat etapou 13.11 (doplnit širší backend test matrix pro standardní pole, kategoriová pole, Streamline activity/tool a audit/permission regresní scénáře).

### 2026-05-10 18:22 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na poslední otevřený bod 13.9 (API endpointy).
- Další krok byl maximalizovaně delegován na dva podagenty (implementační mapa endpointů + nezávislá riziková revize) a následně proběhla ruční konceptuální validace návrhů proti aktuálním souborům (`crm/api.py`, `crm/models.py`, `crm/tests.py`).
- Funkční implementace 13.9 v `crm/api.py`: doplněny endpointy pro CRUD pravidel (`/condition-rules`), scénáře fáze (`/categories/{category_id}/stages/{stage_id}/scenarios`), seznam požadavků scénáře (`/scenarios/{scenario_id}/requirements`), testovací vyhodnocení (`/condition-rules/test-evaluation`), požadavky aktuální fáze (`/records/{record_id}/active-stage-requirements`) a log vyhodnocení (`/rule-evaluation-logs`).
- Endpointy používají existující firm-scope a oprávnění (`require_permission`) a navazují na existující condition-engine helpery (`_refresh_active_stage_scenario`, `_serialize_stage_rule_output`, `RecordConditionContextBuilder` / `evaluate_condition_rule_outputs`).
- Rozšířeny integrační backend testy v `crm/tests.py` (`ConditionRulesApiEndpointsTest`) pro rule CRUD + deaktivaci, scénáře/požadavky, testovací evaluaci a log endpoint.
- Hotovo: bod 13.9 je nyní kompletně dokončený.
- Následuje: navázat etapou 13.10 (oprávnění) a zpřesnit permission model pro čtení/upravy pravidel, scénářů a logů, včetně navazujících testů.

### 2026-05-10 17:36 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na poslední otevřený bod 13.8 (napojení na Streamline feed).
- Další krok byl maximalizovaně delegován na dva podagenty (implementační analýza + nezávislá konceptuální revize) a následně proběhla ruční validace návrhů proti aktuálním souborům (`crm/api.py`, `crm/condition_rules.py`, `crm/tests.py`).
- Funkční implementace: `create_activity` nyní po vytvoření Streamline aktivity vyvolá post-create hook pro trigger `streamline.activity_created`, fail-open vyhodnotí pravidla, zapíše `RuleEvaluationLog` a neblokuje samotné vytvoření aktivity při chybě evaluace.
- Doplněny nové helpery pro Streamline evaluaci (`_build_streamline_activity_condition_context`, `_get_applicable_streamline_activity_rules`, `_evaluate_streamline_activity_trigger`, `_resolve_records_for_streamline_activity`) včetně kontextu se `streamline_event` (`entity_type`, `type`, `tool_type`) a vazeb na `record/customer/proposal/task`.
- Napojeno přepočítání scénářů/požadavků po aktivitě i pro nepřímé vazby (customer/proposal/task): `_refresh_active_stage_scenario` nově umí přijmout doplňkové activity snapshoty, takže se aktualizuje `active_stage_requirements` i při aktivitě mimo `record.activities`.
- Rozšířeny integrační backend testy `ActivityCreateAPITest` pro evaluaci/logování `streamline.activity_created`, refresh požadavků pro vazby customer/proposal/task a fail-open chování při chybě evaluátoru.
- Hotovo: bod 13.8 je nyní kompletně dokončený.
- Následuje: navázat etapou 13.9 (API endpointy pro správu pravidel/scénářů a log vyhodnocení) ve stejném režimu delegace + ruční konceptuální/funkční validace.

### 2026-05-10 17:12 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na poslední otevřený bod 13.7 (napojení na změny kategoriových polí).
- Další krok byl maximalizovaně delegován na dva podagenty (implementační návrh + nezávislá validační revize) a následně proběhla ruční konceptuální validace návrhů proti aktuálním souborům (`crm/api.py`, `crm/condition_rules.py`, `crm/tests.py`).
- Funkční implementace: `update_record` nyní detekuje změny kategoriových polí z `extra_data` (včetně legacy fallbacku), fail-closed validuje klíče proti `CategoryField` aktuální kategorie a vyhodnocuje trigger `record.category_field_changed`.
- Doplněny nové helpery pro kategoriové změny (`_build_category_field_change_condition_context`, `_get_applicable_category_field_change_rules`, `_evaluate_category_field_change_trigger`, logování výstupů/chyb do `RuleEvaluationLog`), včetně contextu s `category_field_key`.
- Doplněna robustní evaluace v `ConditionTreeEvaluator`: kontrola `source_type` i pro `field_changes` mapu a podpora `change.category_field_key`, aby nedocházelo k false-positive matchům.
- Napojeno zohlednění povinností pole podle fáze: po změně kategoriových polí se nyní přepočítává aktivní scénář/požadavky (`active_stage_requirements`) přes `_refresh_active_stage_scenario`.
- Rozšířeny integrační a regresní backend testy v `RecordUpdateAPITest` a `ConditionRulesTest` pro evaluaci/logování/no-op změny/invalid klíč i refresh stage requirementů.
- Hotovo: bod 13.7 je nyní kompletně dokončený.
- Následuje: navázat etapou 13.8 (napojení na Streamline feed) ve stejném režimu delegace + ruční konceptuální/funkční validace.

### 2026-05-10 16:46 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na poslední otevřený bod 13.6 (`Přepočítat požadavky fáze`).
- Další krok byl maximalizovaně delegován na dva podagenty (implementační návrh + nezávislá validační revize) a následně proběhla ruční konceptuální validace návrhů proti aktuálním souborům (`crm/api.py`, `crm/condition_rules.py`, `crm/tests.py`).
- Funkční implementace: `_refresh_active_stage_scenario` nyní při výpočtu aktivního scénáře zároveň přepočítává požadavky scénáře přes `ConditionTreeEvaluator` a ukládá je do `record.extra_data["active_stage_requirements"]` (včetně `id`, `requirement_type`, `blocking`, `visible_to_user`, `is_met`).
- Doplněno čištění `active_stage_requirements` při neaktivním/neexistujícím scénáři, aby v `extra_data` nezůstávala zastaralá data.
- Rozšířeny integrační backend testy `RecordUpdateAPITest` o pokrytí přepočtu požadavků po změně standardního pole a o regresi pro správné čištění zastaralých requirement dat.
- Po paralelní validaci (review + CodeQL) doplněn robustní fix pro čištění orphan dat bez `KeyError` a přidán regresní test pro stav, kdy je přítomné pouze `active_stage_requirements` bez `active_stage_scenario_id`.
- Hotovo: bod 13.6 je nyní kompletně dokončený.
- Následuje: navázat etapou 13.7 (napojení na změny kategoriových polí) ve stejném režimu delegace + ruční konceptuální/funkční validace.

### 2026-05-10 15:52 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na poslední dokončený bod 13.5; jako další krok byla zvolena implementace první části 13.6 (`record.field_changed`).
- Další analýza byla maximalizovaně delegována na dva podagenty (hlavní implementační rozpad + nezávislá riziková revize) a následně proběhla ruční konceptuální validace návrhů proti aktuálním souborům (`crm/api.py`, `crm/condition_rules.py`, `crm/tests.py`).
- Funkční implementace: `update_record` nyní detekuje změněná standardní pole (včetně FK `_id` polí), skládá old/new change kontext a vyhodnocuje pravidla triggeru `record.field_changed` přes `evaluate_condition_rule_outputs(...)`.
- Doplněno logování výsledků vyhodnocení změn standardních polí do `RuleEvaluationLog` (včetně mapování `effect` -> `result`, fail-safe error logu a serializace warning/block výstupů do API odpovědi `field_change_evaluation`).
- Doplněna vazba na scénáře: po změně standardních polí bez stage change se nyní obnovuje aktivní scénář (`active_stage_scenario_id`) přes `_refresh_active_stage_scenario`.
- Rozšířeny integrační backend testy `RecordUpdateAPITest` o scénáře: vyhodnocení+log při změně standardního pole, no-op update bez evaluace a refresh aktivního scénáře po změně standardního pole.
- Následuje: dokončit zbývající bod 13.6 (`Přepočítat požadavky fáze`) a navázat etapou 13.7 (změny kategoriových polí) ve stejném režimu delegace + ruční konceptuální/funkční validace.

### 2026-05-10 13:32 UTC

- Navázáno na poslední otevřený bod 13.4 („Přidat ochranu proti nekonečnému řetězení“) po opětovném prostudování `podminky.md` a aktuální implementace v `crm/condition_rules.py`.
- Analytický návrh byl maximalizovaně delegován samostatnému podagentovi (návrh minimální implementace + edge cases + testy), poté proběhla ruční konceptuální validace návrhu proti aktuálním zdrojům.
- Funkční implementace: `ConditionTreeEvaluator` nyní používá interní evaluaci s ochranou proti cyklům (`active_node_ids` podle `id()` uzlu) a při detekci self-reference/nepřímého cyklu vyhodnocuje fail-closed (`False`), bez omezení validního zanoření.
- Doplněny regresní backend testy `ConditionRulesTest` pro self-referenční skupinu, nepřímý cyklus mezi skupinami a reuse stejného podstromu bez cyklu.
- Výsledek: bod 13.4 „Přidat ochranu proti nekonečnému řetězení“ je dokončen a checkbox je aktualizovaný na splněný.
- Následuje: navázat etapou 13.5 (napojení evaluace na `record.stage_change_requested`/`record.stage_changed`) a začít integračním bodem změny fáze v `crm/api.py`.

### 2026-05-10 13:35 UTC

- Pro další krok byla zvolena realizace zbývajících bodů 13.4: podpora existence související entity, podpora výstupů pravidla a deterministické řazení podle priority.
- Další analýza byla maximalizovaně delegována na dva podagenty (implementační návrh + nezávislá validační revize); následně proběhla ruční konceptuální validace návrhů proti aktuálním souborům (`crm/condition_rules.py`, `crm/tests.py`, `podminky.md`).
- Funkční implementace: `ConditionTreeEvaluator` nově podporuje `source_type=related_entity` s `entity_type` (`customer`, `company`, `contact_person`, `assigned_to`, `category`, `current_stage`/`stage`, `parent`) a operátory `exists`/`not_exists`/`missing`/`eq`/`neq`.
- Doplněna podpora výstupů pravidla přes `evaluate_condition_rule_outputs(...)`, která vrací efekt pravidla (`effect`, `severity`, `effect_config`) pouze pro aktivní pravidla se splněnou podmínkou.
- Přidáno deterministické řazení evaluace pravidel (`priority`, `created_at`, `id`) v helperu `_sort_rules_for_evaluation(...)`.
- Rozšířeny backend testy `ConditionRulesTest` o scénáře pro `related_entity` (validní/invalidní entity) a o testy výstupů pravidla + deterministického pořadí při shodné prioritě.
- Následuje: dokončit zbývající bod 13.4 (ochrana proti nekonečnému řetězení) a potom navázat etapou 13.5 (napojení na stage-change flow).

### 2026-05-10 12:33 UTC

- Pro další krok byla zvolena realizace zbývajícího bodu 13.4 „podpora změny hodnoty z/do“.
- Další analýza byla delegována podagentovi (návrh minimální implementace + testovací scénáře), následně proběhla ruční konceptuální validace proti aktuálním souborům (`crm/condition_rules.py`, `crm/tests.py`).
- Funkční implementace: `ConditionTreeEvaluator` nově podporuje `source_type` `field_change` a `category_field_change` s operátory `changed`, `changed_from`, `changed_to`; `RecordConditionContextBuilder` nyní vrací i `change` kontext (`field_key`, `source_type`, `old_value`, `new_value`).
- Doplněny backend testy `ConditionRulesTest` pro nové operátory i fail-closed scénář při neshodě změněného pole.
- Následná nezávislá validační kontrola podagentem odhalila edge case porovnání `None` vs `"None"`; fix aplikován v `_values_equal` a doplněny regresní testy (beze změny hodnoty + `None` vs string).
- Výsledek: bod 13.4 „Přidat podporu změny hodnoty z/do“ je dokončen a checkbox je aktualizovaný na splněný.
- Následuje: pokračovat implementací zbývajících bodů 13.4 (podpora existence související entity a výstupů pravidla), poté navázat body 13.5 (napojení na stage-change flow).

### 2026-05-10 11:45 UTC

- Znovu prostudován `podminky.md` a navázáno na předchozí krok 13.4; jako další implementační cíl byly vybrány zbývající body pro kategoriová pole, Streamline aktivity/tool typy a časová okna.
- Další krok byl maximalizovaně delegován: samostatný podagent připravil implementační mapu (konkrétní soubory/funkce + testovací scénáře), následně proběhla ruční kontrola návrhu proti aktuálním souborům (`crm/condition_rules.py`, `crm/models.py`, `crm/tests.py`).
- Funkční implementace: `RecordConditionContextBuilder` nyní doplňuje `category_fields` a snapshot `activities`; `ConditionTreeEvaluator` nově podporuje `source_type` pro `category_field`, `activity`, `streamline_activity`, `streamline_tool` včetně `time_window` (`last_hours`/`last_days`).
- Doplněny a rozšířeny backend testy v `ConditionRulesTest` pro nové větve evaluátoru (kategoriové pole, aktivita + entity/tool filtr, časové okno, alias `streamline_activity`).
- Proběhla nezávislá validační kontrola druhým podagentem (konceptuální + funkční), následně bylo doplněno ještě pokrytí `streamline_activity` aliasu a `last_days` do testů.
- Ověření funkčnosti: cílená sada `python manage.py test crm.tests.ConditionRulesTest` prochází (`7/7`).
- Výsledek: vybrané body 13.4 (kategoriová pole, Streamline aktivity, Streamline tool typy, časová okna) jsou dokončené a checkboxy jsou aktualizované na splněné.
- Následuje: pokračovat v 13.4 implementací podpory změny hodnoty z/do, existence související entity a výstupů pravidla; poté navázat napojením na stage-change flow v 13.5.

### 2026-05-10 11:20 UTC

- Navázáno na předchozí krok (13.4) a nejdříve byl znovu prostudován celý `podminky.md` včetně posledních záznamů v pracovním logu.
- Další realizace byla maximálně delegována: podagent připravil návrh konkrétní implementace (context builder + evaluator + testy), následně proběhla ruční konceptuální validace návrhu proti aktuálním souborům (`crm/models.py`, `crm/api.py`, `crm/tasks.py`, `crm/tests.py`).
- Funkční krok 13.4 byl implementován: přidán modul `crm/condition_rules.py` (`RecordConditionContextBuilder`, `ConditionTreeEvaluator`) se zanořeným `AND`/`OR`, negací (`NOT`/`negated`) a podporou standardních polí záznamu.
- Integrace bez rozbití existující logiky: do `_build_record_automation_context` v `crm/api.py` byl doplněn klíč `condition_context`; v `crm/tasks.py` přibyl helper `evaluate_condition_tree`.
- Doplněny backend testy v `crm/tests.py` pro context builder a evaluator (včetně vnořených skupin, negace, fail-closed chování při chybějícím poli a numerického porovnání).
- Provedena následná nezávislá validační kontrola dalším podagentem (konceptuální + funkční revize) a zapracována korekce fail-closed logiky: prázdná `OR` skupina nyní vyhodnocuje na `False`.
- Po paralelní validaci (review + CodeQL) byla doplněna ještě robustnější obsluha `group` uzlu bez explicitního operátoru (default `AND`) a komentář k fail-closed identitě prázdných skupin.
- Výsledek: vybrané body 13.4 (context builder, evaluator, AND/OR/negace/vnořené skupiny/standardní pole) jsou dokončené a checkboxy aktualizované na splněné.
- Následuje: pokračovat etapou 13.4 o podporu kategoriových polí, Streamline aktivit/tool typů a časových oken; poté navázat přímým napojením do stage-change flow v 13.5.

### 2026-05-10 09:32 UTC

- Prostudován navazující rozsah v `podminky.md` a potvrzen další krok: dokončit sekci 13.2 (návrh datového modelu).
- Návrh byl delegován na podagenta (backend model mapping) a následně znovu delegován na validačního podagenta pro konceptuální/implementační kontrolu.
- Výstupy podagentů byly ručně ověřeny proti aktuálním souborům (`crm/models.py`, `crm/api.py`, `crm/tasks.py`) a sladěny s reálnými integračními body.
- Výsledek: 13.2 je doplněna konkrétním návrhem modelů, vazeb, priority/indexů a všechny checkboxy 13.2 jsou označeny jako splněné.
- Následuje: navázat etapou 13.3 (návrh migrací tabulek + indexů + rollback strategie) ve stejném režimu delegace + ruční validace.

### 2026-05-10 05:49 UTC

- Prostudován celý návrh a potvrzen další proveditelný krok: dokončit analytické mapování pro backend (13.1) a frontend (14.1).
- Kroky byly delegovány na podagenty (samostatně backend + frontend), následně ručně ověřeny proti zdrojovým souborům.
- Výsledek: sekce 13.1 a 14.1 jsou dokončeny a checkboxy byly aktualizovány jako splněné.
- Validace prostředí před úpravami:
  - frontend checks aktuálně padají na pre-existing TypeScript chybách mimo tento dokument,
  - backend checks aktuálně padají na `pip-audit` nálezu `twisted 25.5.0 / CVE-2026-42304` (fix verze `26.4.0rc2`).
- Následuje: navázat návrhem datového modelu (13.2) a připravit první konkrétní návrh struktur pro pravidla, scénáře a log vyhodnocení.

### 2026-05-10 10:31 UTC

- Pro další krok byla zvolena realizace 13.3 (migrace) podle předchozího postupu uvedeného v dokumentu.
- Návrh byl maximálně delegován: samostatný podagent připravil konkrétní návrh modelů/migrace a druhý podagent provedl nezávislou validační kontrolu návrhu.
- Konceptuální validace: výstupy podagentů byly ručně porovnány s aktuálními modely (`crm/models.py`, `firms/models.py`) a upraveny na kompatibilní naming (`is_active`, `created_by` na `AUTH_USER_MODEL`, nullable vazby logu).
- Funkční validace: implementovány modely `ConditionRule`, `StageScenario`, `StageRequirement`, `RuleEvaluationLog` a vytvořena reverzibilní migrace `crm/migrations/0010_conditionrule_stagescenario_stagerequirement_and_more.py` včetně indexů pro firm/category/stage/trigger/activity a log evaluací.
- Výsledek: checklist 13.3 je dokončený a označený jako splněný.
- Následuje: navázat etapou 13.4 (evaluátor pravidel) – začít službou pro sestavení kontextu pravidla a základním vyhodnocením `AND`/`OR` nad `condition_tree`.

### 2026-05-10 14:00 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na poslední dokončený bod 13.4; jako další krok byla zvolena implementace celé sekce 13.5 (napojení evaluace na stage-change flow).
- Návrh řešení byl maximálně delegován samostatnému podagentovi (návrh minimální implementace + edge cases + testovací scénáře), následně proběhla ruční konceptuální validace návrhu proti aktuálním souborům (`crm/api.py`, `crm/condition_rules.py`, `crm/models.py`, `crm/tests.py`).
- Funkční implementace: v `update_record` je nyní pre-evaluace triggeru `record.stage_change_requested` s fail-closed blokací, post-evaluace `record.stage_changed`, návrat blokací/upozornění ve `stage_change_evaluation` a logování výsledků do `RuleEvaluationLog`.
- Doplněna scope-validace pravidel (`firm`/`category`/`stage`/`stage_transition`) pro stage-change trigger a serializace výstupů pravidel do API odpovědi.
- Doplněna aktualizace aktivního scénáře po úspěšné změně fáze (`active_stage_scenario_id` v `record.extra_data`) podle `StageScenario.activation_condition` a priority.
- Přidány integrační testy `RecordUpdateAPITest` pro: blokaci stage změny, neblokující warning, post-change evaluaci a scénář, a negativní scénář bez stage změny.
- Funkční validace: nové cílené testy prošly (`4/4`); současně je potvrzeno, že v repozitáři existují pre-existing baseline selhání v plném běhu testů/lintu mimo rozsah této změny.
- Výsledek: checklist 13.5 je dokončený a označený jako splněný.
- Následuje: pokračovat etapou 13.6 (detekce změn standardních polí + trigger `record.field_changed` + logování + vazba na scénáře/požadavky).

### 2026-05-11 13:25 UTC

- Prostudován aktuální stav `podminky.md` a navázáno na požadavek doplnit praktické šablony typických pravidel i scénářů pro konkrétní obory.
- Scope byl maximálně delegován subagentovi (návrh šablon + jednotná struktura), následně proběhla ruční konceptuální validace proti stávající terminologii dokumentu (`Aktivace`, `Požadavky`, `Blokace`, `Doporučení`).
- Připraven obsah nové sekce se šablonami pro call centrum, montážní firmu a IT servis tak, aby šel použít jako výchozí stavebnice pro admin konfiguraci.
- Následuje: provést finální kontrolu návaznosti textu, zvalidovat diff a připravit řádný PR se shrnutím.

## 20. Další fáze: Interaktivní grafická mindmapa podmínek

### 20.1 Cíl

Nastavení podmínek už podporuje pravidla, scénáře, požadavky, řetězení a audit, ale při větším počtu pravidel je obtížné rychle pochopit jejich souvislosti. Další fáze proto zavede interaktivní grafickou mindmapu, která nebude nahrazovat existující formulářové editory, ale doplní je o vizuální pohled na strom podmínek a vazby mezi pravidly, scénáři a požadavky.

Mindmapa má odpovědět hlavně na otázky:

- Která pravidla ovlivňují vybranou kategorii a fázi?
- Které scénáře se mohou aktivovat a proč?
- Jaké požadavky jsou navázané na scénář?
- Kam vede splnění nebo nesplnění požadavku?
- Která podmínka v testovacím vyhodnocení prošla a která ne?
- Kde existují neaktivní, neúplné nebo potenciálně konfliktní větve?

### 20.2 Princip řešení

Mindmapa bude pracovat nad stejnými daty jako současné UI:

- `ConditionRule` jako vstupní pravidla s triggerem, efektem a condition tree,
- `StageScenario` jako větve práce ve fázi,
- `StageRequirement` jako konkrétní povinnosti a návazné kroky,
- `RuleEvaluationLog` jako zdroj auditní a testovací stopy,
- existující Pinia stores a API endpointy bez nového paralelního modelu pravidel.

Frontend si nad těmito daty vytvoří normalizovaný vizualizační model:

- uzel pravidla,
- uzel skupiny `AND`/`OR`,
- uzel jednoduché podmínky,
- uzel scénáře,
- uzel požadavku,
- hranu aktivace scénáře,
- hranu splnění/nesplnění návazného kroku,
- hranu auditní/testovací stopy.

Rozvržení a stav zobrazení (pozice, zoom, sbalené větve, lokální výběr uzlu) mají být nejdříve pouze frontend stav. Perzistence layoutu se má řešit až tehdy, pokud se ukáže jako uživatelsky nutná.

### 20.3 Doporučený rozsah práce

#### 20.3.1 Fáze A: Read-only vizualizace condition tree

- Přidat helper pro převod condition tree na vizualizační uzly a hrany.
- Vykreslit strom podmínky pro jedno pravidlo nebo aktivační podmínku scénáře.
- Odlišit skupiny `AND`/`OR`, negaci, typ zdroje, operátor, hodnotu a časové okno.
- Přidat prázdný, loading a error stav.
- Přidat možnost sbalit/rozbalit vnořené skupiny.
- Zachovat rychlý návrat do existujícího formulářového/JSON editoru.
- Otestovat jednoduchou podmínku, vnořené skupiny, neúplné uzly a prázdný strom.

#### 20.3.2 Fáze B: Přehled vazeb pravidlo → scénář → požadavek

- Přidat diagram pro vybranou kategorii/fázi v nastavení pipeline.
- Zobrazit aktivní i neaktivní pravidla s barevným rozlišením triggeru a efektu.
- Zobrazit scénáře podle priority a aktivační podmínky.
- Zobrazit požadavky scénáře, jejich blocking/warning charakter a doporučenou další fázi.
- Zobrazit návaznosti `next_step_on_met` a `next_step_on_unmet` jako směrové hrany.
- Přidat filtry pro kategorii, fázi, trigger, aktivní stav a typ uzlu.
- Otestovat diagram bez dat, s jedním scénářem, s větvením i s řetězením požadavků.

#### 20.3.3 Fáze C: Interaktivní navigace a detail uzlu

- Přidat výběr uzlu kliknutím a panel detailu vedle grafu.
- V detailu zobrazit lidsky čitelný popis, technické ID, zdrojová data a dostupné akce.
- Přidat přeskok z uzlu do existujícího editoru pravidla, scénáře nebo požadavku.
- Přidat zvýraznění souvisejících hran a sousedních uzlů.
- Přidat zoom, pan, centrování vybraného uzlu a reset pohledu.
- Přidat klávesovou navigaci mezi uzly a základní ARIA popisy.

#### 20.3.4 Fáze D: Řízené editace v grafu

- Přímé editace povolit až po stabilizaci read-only režimu.
- Začít bezpečnými akcemi: přejmenování popisu, zapnutí/vypnutí pravidla, změna priority scénáře, otevření editoru požadavku.
- Poté přidat manipulaci s condition tree: přidat podmínku, přidat skupinu, změnit `AND`/`OR`, odstranit uzel.
- Poté přidat manipulaci s návaznými hranami požadavků.
- Každá editace musí používat stejnou validaci jako formulářový editor a API.
- Při nevalidním grafu zobrazit chybu přímo u uzlu/hrany a zakázat uložení.
- Formulářový editor zůstává autoritativní fallback pro složité nebo nejasné úpravy.

#### 20.3.5 Fáze E: Napojení na testovací vyhodnocení a audit

- Umožnit spustit testovací vyhodnocení a výsledek promítnout do grafu.
- Zvýraznit splněné, nesplněné a nevyhodnocené uzly.
- U pravidel a scénářů zobrazit poslední relevantní záznamy z `RuleEvaluationLog`.
- V detailu uzlu ukázat důvod výsledku a případný související záznam/aktivitu.
- Přidat režim „replay“, který ukáže postup aktivace scénáře a návazných požadavků.

#### 20.3.6 Fáze F: Výkon, škálování a UX polish

- Přidat automatické hierarchické rozvržení grafu bez povinné externí knihovny.
- Pro velké grafy zavést limit počtu uzlů v jednom pohledu a jasnou výzvu k filtrování.
- Přidat sbalování scénářů, skupin a dokončených požadavků.
- Přidat minimapu nebo přehledovou navigaci pouze pokud zoom/pan nestačí.
- Ověřit kontrast barev, čitelnost v tmavém režimu a ovládání klávesnicí.
- Doplnit krátkou in-app nápovědu s legendou barev, hran a ikon.

### 20.4 Technické zásady

- Nepřidávat druhý backendový model pravidel jen pro graf.
- Nepřidávat těžkou grafovou knihovnu, dokud nebude jasné, že vlastní SVG/Vue řešení nestačí.
- Normalizaci dat držet v samostatných utilitách, aby byla dobře testovatelná.
- Diagramové komponenty oddělit od API volání; data mají dostávat přes props/store.
- Všechny editace vést přes existující stores a endpointy.
- Stav layoutu nejdříve držet lokálně; perzistenci řešit samostatnou pozdější fází.
- Přístupnost a fallback na formulářový editor jsou povinné, ne volitelné.

### 20.5 Validace

Minimální validační sada pro tuto fázi:

- unit test normalizace condition tree na uzly/hrany,
- unit test normalizace scénářů a požadavků včetně `next_step_on_met`/`next_step_on_unmet`,
- render test prázdného grafu, jednoduchého grafu a hluboce vnořeného grafu,
- test výběru uzlu a zobrazení detailu,
- test sbalení/rozbalení větve,
- test synchronizace grafu po změně ve formulářovém editoru,
- test zamítnutí nevalidní editace, pokud bude povolen edit režim,
- `npm run check-locales`, `npm run build-only` a relevantní `npm run test:unit` ve `frontend-spa`,
- bezpečnostní/review validace před PR.

### 20.6 Rizika a opatření

- Riziko: velký graf bude nečitelný. Opatření: filtry, sbalování, limity uzlů, zoom/pan a oddělené pohledy pro condition tree a flow diagram.
- Riziko: editace v grafu se rozejde s formulářem. Opatření: jeden sdílený store, stejné validační funkce a formulář jako fallback.
- Riziko: uživatel nepochopí význam barev a hran. Opatření: legenda, tooltips, detail uzlu a jednoduché názvosloví.
- Riziko: výkon u firem s mnoha pravidly. Opatření: načítat a renderovat graf podle vybrané kategorie/fáze, ne celý systém najednou.
- Riziko: grafová knihovna přinese zbytečnou závislost. Opatření: první iteraci udělat pomocí Vue + SVG a nové knihovny zvažovat až podle konkrétních limitů.

### 20.7 Doporučené pořadí implementace

1. Normalizační utility a unit testy.
2. Read-only strom jedné podmínky.
3. Přehledový flow diagram pro kategorii/fázi.
4. Navigace, detail uzlu, zvýraznění souvislostí.
5. Napojení na testovací vyhodnocení a auditní logy.
6. Až poté řízené editace v grafu.
7. Výkonnostní optimalizace, přístupnost a UX nápověda.

### 20.8 Kritérium dokončení fáze

Fáze je dokončená, když administrátor dokáže v nastavení pipeline otevřít grafický pohled, vybrat kategorii/fázi, zobrazit pravidla, scénáře, požadavky a návazné kroky, bezpečně přejít z grafu do existujícího editoru a při testovacím vyhodnocení vidět, které části logiky byly splněné nebo nesplněné.

## 21. Šablony typických pravidel a scénářů podle domény

### 21.1 Call centrum

#### Typická pravidla

- Blokovat přechod do fáze „Kvalifikace“, pokud není vyplněný telefon ani e-mail.
- Blokovat uzavření leadu jako „Nedosažitelný“, pokud nejsou alespoň 3 pokusy o kontakt.
- Zobrazit upozornění, pokud u leadu chybí termín dalšího kontaktu po neúspěšném hovoru.
- Doporučit předání senior operátorovi, pokud je priorita leadu vysoká.

#### Scénář: První kontakt

Aktivace:

- záznam vstoupí do fáze Nový lead,
- není evidovaný úspěšný kontakt.

Požadavky:

- vyplnit kontaktní údaj (telefon nebo e-mail),
- zapsat výsledek pokusu o kontakt,
- nastavit další krok (callback, e-mail, uzavření).

Blokace:

- nelze přesunout do další fáze bez záznamu o kontaktu.

Doporučení:

- po dvou neúspěšných pokusech doporučit jiný komunikační kanál.

### 21.2 Montážní firma

#### Typická pravidla

- Blokovat přechod do „Realizace“, pokud není potvrzen termín montáže.
- Blokovat dokončení zakázky, pokud chybí fotodokumentace po realizaci.
- Blokovat přechod do „Hotovo“, pokud není dokončen montážní checklist.
- Zobrazit upozornění při evidenci vícepráce bez schválení odpovědnou osobou.

#### Scénář: Standardní montáž

Aktivace:

- `typ_realizace = montáž`,
- záznam je ve fázi Příprava realizace nebo Realizace.

Požadavky:

- potvrdit termín montáže,
- přiřadit montážní tým,
- nahrát fotky před a po montáži,
- doplnit předávací protokol.

Blokace:

- nelze uzavřít realizaci bez fotodokumentace a protokolu.

Doporučení:

- po splnění všech požadavků doporučit přesun do fáze „Hotovo“.

### 21.3 IT servis

#### Typická pravidla

- Blokovat zahájení řešení incidentu bez nastavené priority.
- Blokovat uzavření incidentu bez popisu řešení a potvrzení obnovy služby.
- Blokovat produkční změnu bez schválení změnového zásahu.
- Zobrazit upozornění, pokud ticket s vysokým dopadem není eskalován včas.

#### Scénář: Incident management

Aktivace:

- vytvořen nový ticket typu Incident,
- ticket přejde do fáze „V řešení“.

Požadavky:

- vyplnit dopad a prioritu incidentu,
- vést průběžný servisní log,
- uvést workaround nebo finální fix.

Blokace:

- nelze uzavřít ticket bez popisu příčiny a způsobu nápravy.

Doporučení:

- při opakovaném incidentu doporučit založení problem ticketu a post-mortem analýzu.
