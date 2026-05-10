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

- [ ] Detekovat změny kategoriových polí.
- [ ] Ověřit, že pole patří ke kategorii záznamu.
- [ ] Sestavit context s `category_field_key`.
- [ ] Vyhodnotit pravidla typu `record.category_field_changed`.
- [ ] Zohlednit povinnost pole podle fáze.
- [ ] Aktualizovat požadavky scénáře.
- [ ] Zapsat log vyhodnocení.

### 13.8 Napojení na Streamline feed

- [ ] Najít místo vytvoření Streamline aktivity.
- [ ] Při vytvoření aktivity sestavit evaluation context.
- [ ] Doplnit entity type.
- [ ] Doplnit activity type.
- [ ] Doplnit tool type.
- [ ] Doplnit vazbu na record/customer/proposal/task.
- [ ] Vyhodnotit pravidla typu `streamline.activity_created`.
- [ ] Vyhodnotit pravidla pro konkrétní tool.
- [ ] Aktualizovat splněné požadavky.
- [ ] Aktivovat scénáře podle aktivity.
- [ ] Zapsat log vyhodnocení.

### 13.9 API endpointy

- [ ] Přidat endpoint pro seznam pravidel.
- [ ] Přidat endpoint pro detail pravidla.
- [ ] Přidat endpoint pro vytvoření pravidla.
- [ ] Přidat endpoint pro úpravu pravidla.
- [ ] Přidat endpoint pro smazání nebo deaktivaci pravidla.
- [ ] Přidat endpoint pro seznam scénářů fáze.
- [ ] Přidat endpoint pro vytvoření scénáře.
- [ ] Přidat endpoint pro úpravu scénáře.
- [ ] Přidat endpoint pro požadavky scénáře.
- [ ] Přidat endpoint pro testovací vyhodnocení pravidla.
- [ ] Přidat endpoint pro požadavky aktuální fáze záznamu.
- [ ] Přidat endpoint pro log vyhodnocení.

### 13.10 Oprávnění

- [ ] Určit, kdo může pravidla zobrazit.
- [ ] Určit, kdo může pravidla upravovat.
- [ ] Určit, kdo může scénáře upravovat.
- [ ] Určit, kdo vidí log vyhodnocení.
- [ ] Zajistit, že pravidla nepřekročí firm scope.
- [ ] Zajistit, že pravidla neodhalí data bez oprávnění.
- [ ] Auditovat změny pravidel.

### 13.11 Testy backendu

- [ ] Otestovat jednoduché pravidlo nad standardním polem.
- [ ] Otestovat pravidlo nad kategoriovým polem.
- [ ] Otestovat pravidlo nad Streamline aktivitou.
- [ ] Otestovat pravidlo nad konkrétním Streamline tool typem.
- [ ] Otestovat blokaci změny fáze.
- [ ] Otestovat neblokující upozornění.
- [ ] Otestovat aktivaci scénáře.
- [ ] Otestovat řetězení kroků.
- [ ] Otestovat větvení podle hodnoty pole.
- [ ] Otestovat více aktivních scénářů a prioritu.
- [ ] Otestovat audit log.
- [ ] Otestovat oprávnění.

## 14. Frontend pracovní úkony

### 14.1 Analýza UI

- [x] Zmapovat detail záznamu.
- [x] Zmapovat nastavení pipeline kategorií.
- [x] Zmapovat nastavení fází.
- [x] Zmapovat zobrazení kategoriových polí.
- [x] Zmapovat práci se Streamline feedem.
- [x] Zmapovat existující modaly a formulářové komponenty.

### 14.2 Panel požadavků fáze

- [ ] Navrhnout komponentu pro zobrazení aktivního scénáře.
- [ ] Zobrazit splněné požadavky.
- [ ] Zobrazit nesplněné požadavky.
- [ ] Zobrazit blokující požadavky.
- [ ] Zobrazit upozornění.
- [ ] Zobrazit doporučený další krok.
- [ ] Přidat odkazy na relevantní pole.
- [ ] Přidat odkazy na relevantní Streamline aktivity.
- [ ] Přidat prázdný stav.
- [ ] Přidat loading stav.
- [ ] Přidat error stav.

### 14.3 Validace při změně fáze

- [ ] Při drag-and-drop změně fáze volat validační endpoint.
- [ ] Při změně fáze z detailu záznamu volat validační endpoint.
- [ ] Pokud existuje blokace, vrátit záznam do původní fáze.
- [ ] Zobrazit modal s blokacemi.
- [ ] Zobrazit neblokující upozornění.
- [ ] Umožnit pokračování, pokud jsou pouze upozornění.
- [ ] Umožnit rychlé doplnění chybějícího pole.
- [ ] Umožnit rychlé vytvoření požadované Streamline aktivity.

### 14.4 Editor pravidel

- [ ] Přidat seznam pravidel v nastavení pipeline.
- [ ] Přidat filtrování podle kategorie.
- [ ] Přidat filtrování podle fáze.
- [ ] Přidat filtrování podle triggeru.
- [ ] Přidat stav zapnuto/vypnuto.
- [ ] Přidat vytvoření pravidla.
- [ ] Přidat úpravu pravidla.
- [ ] Přidat deaktivaci pravidla.
- [ ] Přidat kopírování pravidla.
- [ ] Přidat testovací vyhodnocení.

### 14.5 Builder podmínek

- [ ] Přidat výběr zdroje podmínky.
- [ ] Podporovat zdroj „standardní pole záznamu“.
- [ ] Podporovat zdroj „kategoriové pole“.
- [ ] Podporovat zdroj „Streamline aktivita“.
- [ ] Podporovat zdroj „Streamline tool“.
- [ ] Podporovat zdroj „související entita“.
- [ ] Přidat výběr operátoru.
- [ ] Přidat výběr hodnoty.
- [ ] Přidat podporu časového okna.
- [ ] Přidat skupiny AND/OR.
- [ ] Přidat vnořené skupiny.
- [ ] Přidat validaci neúplných podmínek.
- [ ] Přidat čitelný preview text pravidla.

### 14.6 Editor scénářů fáze

- [ ] Přidat seznam scénářů pro fázi.
- [ ] Přidat vytvoření scénáře.
- [ ] Přidat aktivační podmínku scénáře.
- [ ] Přidat seznam požadavků scénáře.
- [ ] Přidat nastavení blokujícího požadavku.
- [ ] Přidat doporučenou další fázi.
- [ ] Přidat prioritu scénáře.
- [ ] Přidat zapnutí/vypnutí scénáře.
- [ ] Přidat preview na testovacím záznamu.

### 14.7 Napojení na Streamline

- [ ] Zobrazovat požadované Streamline aktivity v panelu požadavků.
- [ ] Nabídnout rychlé vytvoření chybějící aktivity.
- [ ] Otevřít správný Streamline tool podle požadavku.
- [ ] Zobrazit, která aktivita požadavek splnila.
- [ ] Zobrazit, která aktivita aktivovala scénář.
- [ ] Podporovat tooly z backend registry bez frontend hardcodování.

### 14.8 Napojení na kategoriová pole

- [ ] Načíst dostupná pole pro kategorii.
- [ ] Nabídnout kategoriová pole v builderu.
- [ ] Zobrazit názvy polí čitelně pro uživatele.
- [ ] Ověřit typ pole před výběrem operátoru.
- [ ] Umožnit rychlou úpravu chybějícího pole z validačního modalu.
- [ ] Zobrazit pravidla relevantní pouze pro vybranou kategorii.

### 14.9 Testy frontendu

- [ ] Otestovat render panelu požadavků.
- [ ] Otestovat splněné a nesplněné požadavky.
- [ ] Otestovat blokaci změny fáze.
- [ ] Otestovat upozornění bez blokace.
- [ ] Otestovat builder pravidla.
- [ ] Otestovat výběr standardního pole.
- [ ] Otestovat výběr kategoriového pole.
- [ ] Otestovat výběr Streamline toolu.
- [ ] Otestovat editor scénářů.
- [ ] Otestovat prázdné a chybové stavy.

## 15. Postup implementace po etapách

### Etapa 1: Datový základ a jednoduchá validace

- [ ] Přidat základní model pravidel.
- [ ] Přidat jednoduchý condition tree.
- [ ] Podporovat `AND` a `OR`.
- [ ] Podporovat standardní pole záznamu.
- [ ] Napojit pravidla na změnu fáze.
- [ ] Vrátit blokace do API.
- [ ] Přidat základní backend testy.

Výsledek:

- Systém umí blokovat přechod mezi fázemi podle standardních polí.

### Etapa 2: Kategoriová pole

- [ ] Přidat zdroj podmínek pro kategoriová pole.
- [ ] Přidat validaci typů kategoriových polí.
- [ ] Přidat pravidla pro změnu kategoriového pole.
- [ ] Přidat testy kategoriových polí.
- [ ] Doplnit UI výběr kategoriového pole.

Výsledek:

- Pravidla lze vázat na pole definovaná pro konkrétní kategorii.

### Etapa 3: Streamline feed

- [ ] Přidat zdroj podmínek pro Streamline activity.
- [ ] Přidat zdroj podmínek pro Streamline tool type.
- [ ] Napojit vytvoření aktivity na vyhodnocení pravidel.
- [ ] Podporovat vazbu na Record, Customer, Proposal a Task.
- [ ] Přidat testy aktivit.
- [ ] Doplnit UI pro výběr Streamline toolu.

Výsledek:

- Pravidla lze splnit nebo aktivovat pomocí aktivit ve Streamline feedu.

### Etapa 4: Scénáře uvnitř fáze

- [ ] Přidat model scénářů fáze.
- [ ] Přidat aktivační podmínky scénářů.
- [ ] Přidat požadavky scénáře.
- [ ] Přidat výpočet aktivního scénáře.
- [ ] Přidat panel požadavků fáze.
- [ ] Přidat editor scénářů.

Výsledek:

- Jedna fáze může mít více větví podle dat a aktivit.

### Etapa 5: Řetězení

- [ ] Přidat návazné kroky.
- [ ] Přidat stav splnění kroků.
- [ ] Přidat ochranu proti cyklům.
- [ ] Přidat priority.
- [ ] Přidat audit řetězení.
- [ ] Doplnit testy řetězení.

Výsledek:

- Splnění jedné podmínky může aktivovat další krok nebo další sadu podmínek.

### Etapa 6: Pokročilé UI a testovací režim

- [ ] Přidat pokročilý builder.
- [ ] Přidat vnořené skupiny.
- [ ] Přidat preview čitelné věty.
- [ ] Přidat testovací vyhodnocení na konkrétním záznamu.
- [ ] Přidat log vyhodnocení do administrace.
- [ ] Přidat šablony pravidel.

Výsledek:

- Administrátor může bezpečně vytvářet i složitější pravidla.

## 16. Rizika a otevřené otázky

### 16.1 Rizika

- Pravidla mohou být pro uživatele příliš složitá.
- Volné větvení může vést k nečitelným workflow.
- Řetězení může vytvořit cykly.
- Vyhodnocení nad feedem může být náročné na výkon.
- Pluginové Streamline tooly mohou mít rozdílnou strukturu dat.
- Kategoriová pole mohou měnit typ nebo být odstraněna.
- Blokace mohou uživatele brzdit, pokud nejsou dobře vysvětlené.

### 16.2 Opatření

- Začít jednoduchým režimem.
- Pokročilý builder schovat za pokročilé nastavení.
- Každé pravidlo musí mít lidsky čitelné vysvětlení.
- Přidat testovací vyhodnocení pravidla.
- Přidat audit log.
- Přidat ochranu proti cyklům.
- Přidat jasné priority.
- Při odstranění pole upozornit na pravidla, která ho používají.

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
