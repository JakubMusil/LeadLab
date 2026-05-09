# Freelo – Design Book

> Kompletní designový manuál webové prezentace Freelo.io klonu. Dokument popisuje vizuální identitu, barevný systém, typografii, komponenty, layout a responzivní chování.

---

## 1. Úvod

Tento Design Book slouží jako jednotný referenční manuál pro design a vývoj webové prezentace Freelo. Cílem je zajistit konzistenci napříč všemi stránkami a komponentami, usnadnit onboarding nových členů týmu a poskytnout jasná pravidla pro jakékoliv budoucí úpravy či rozšíření.

Freelo je projektový nástroj zaměřený na týmovou spolupráci, organizaci úkolů a komunikaci. Design prezentace odráží hodnoty produktu: profesionalitu, přehlednost, lidskost a důvěru. Vizuální styl kombinuje tmavě modrou primární barvu vyjadřující spolehlivost s zelenou sekundární barvou symbolizující produktivitu a růst. Celková estetika je čistá, vzdušná a moderna, s důrazem na čitelnost a intuitivní orientaci.

Prezentace je postavena na technologickém stacku Next.js (App Router), Tailwind CSS, SCSS Modules a ikonové knihovně Lucide React. Typograficky staví na fontu Inter, který byl zvolen pro svou vynikající čitelnost na obrazovkách a neutrální, profesionální vzhled.

---

## 2. Barevný systém

### 2.1 Primární paleta

Primární paleta tvoří základní vizuální identitu projektu. Tmavě modrá barva dominuje v nadpisech, logu, navigaci a klíčových interaktivních prvcích. Zelená barva funguje jako akcent pro CTA tlačítka, úspěchové stavy a zvýraznění.

| Název | Hex | SCSS proměnná | Použití |
|---|---|---|---|
| Primární modrá | `#254896` | `$blue-primary` | Logo, nadpisy, odkazy, aktivní stavy |
| Primární modrá – tmavá | `#1d3a7a` | `$blue-dark` | Hlavní nadpisy, header logo, silný text |
| Primární modrá – světlá | `#3d62b0` | `$blue-light` | Sekundární zvýraznění |
| Primární modrá – akcent | `#5a7ec9` | `$blue-accent` | Drobné akcenty, dekorace |
| Sekundární zelená | `#52b774` | `$secondary` / `$green-primary` | CTA tlačítka, úspěchové ikony, badge |
| Sekundární zelená – hover | `#449d62` | `$secondary-hover` | Hover stavy zelených tlačítek |
| Sekundární zelená – tmavá | `#3a8a58` | `$secondary-dark` | Ikony v kartách (Organizace práce) |

### 2.2 Pozadí a povrchy

Pozadí jednotlivých sekcí střídá čistě bílou s jemně modrými odstíny, což vytváří vizuální hloubku a pomáhá oddělit obsahové bloky bez použití tvrdých čar nebo stínů.

| Název | Hex | SCSS proměnná | Použití |
|---|---|---|---|
| Bílá | `#ffffff` | `$white` | Většina sekcí, karty, dropdowny |
| Modré pozadí | `#edf1fa` | `$blue-bg` | Hero gradient, Almanach sekce, platformní karty |
| Modré pozadí – alt | `#f0f4fc` | `$blue-bg-alt` | Alternativní světlé pozadí |
| Světle modrá | `#e8edf8` | `$light-blue-bg` | Feature karta (Finance a čas) |
| Světle zelená | `#e8f5ee` | `$green-bg` / `$secondary-light` | Feature karty (Přehled a plánování, Organizace práce) |
| Světle růžová | `#fce4ec` | `$pink-bg` | Feature karta (Spolupráce a komunikace) |
| Růžový akcent | `#e91e63` | `$pink-accent` | Ikona v růžové kartě |

### 2.3 Šedá škála

Šedá škála slouží pro body text, deaktivní prvky, okraje a podpůrné vizuální prvky. Důležité je zachovat dostatečný kontrast vůči pozadí pro přístupnost (WCAG AA minimum).

| Název | Hex | SCSS proměnná | Použití |
|---|---|---|---|
| Tmavý text | `#374151` | – | Navigační odkazy, body text |
| Střední šedá | `#6b7280` | `$gray-text` | Popisky, podtituly, sekundární text |
| Světlá šedá | `#9ca3af` | `$gray-light` | Copyright, legální odkazy, deaktivní text |
| Šedý okraj | `#e5e7eb` | `$gray-border` | Okraje karet, oddělovače, mockup prvky |
| Podtext hero | `#4a5568` | – | Hero podtitul |

### 2.4 Gradienty

| Název | Definice | Použití |
|---|---|---|
| Hero gradient | `linear-gradient(180deg, $blue-bg 0%, $white 70%)` | Pozadí hero sekce |
| Demo gradient | `linear-gradient(135deg, $blue-bg, #dce8f8)` | Pozadí Online ukázka sekce |
| CTA gradient | `linear-gradient(180deg, $white, $blue-bg)` | Pozadí CTA sekce |
| Mockup obsah | `linear-gradient(135deg, #f8fafc, #eef3fb)` | Pozadí uvnitř desktop mockupu |
| Mobilní obsah | `linear-gradient(180deg, #f0f7ff, #fff)` | Pozadí uvnitř mobilního mockupu |

---

## 3. Typografie

### 3.1 Font

| Vlastnost | Hodnota |
|---|---|
| Primární font | **Inter** (Google Fonts) |
| Záložní font | system-ui, -apple-system, sans-serif |
| Proměnná CSS | `--font-inter` |
| Načtení | `next/font/google` s subsety `latin`, `latin-ext` |

Inter byl zvolen jako primární typografický pilíř celé prezentace. Jedná se o open-source bezpatkový font navržený speciálně pro čtení na obrazovkách, s výraznými a dobře rozlišitelnými znaky ve všech velikostech. Podpora latin-ext zaručuje správné vykreslování českých diakritických znaků (háčky a čárky).

### 3.2 Velikosti písma a váhy

| Element | Velikost | Váha | Barva | Řádkování |
|---|---|---|---|---|
| H1 – Hero nadpis | 52px | 800 (ExtraBold) | `$blue-dark` | 1.1 |
| H2 – Sekční nadpis | 32px | 700 (Bold) | `$blue-dark` | – |
| H3 – Karta nadpis | 20px | 700 (Bold) | `$blue-dark` | – |
| H3 – Almanach karta | 17px | 700 (Bold) | `$blue-dark` | – |
| H3 – Webinář nadpis | 18px | 700 (Bold) | `$blue-dark` | – |
| H4 – Footer nadpis | 14px | 700 (Bold) | `$blue-dark` | – |
| Body – Hero podtitul | 19px | 400 | `#4a5568` | 1.65 |
| Body – běžný text | 15px | 400 | `$gray-text` | – |
| Body – seznamy | 14px | 400 | `$gray-text` | – |
| Nav – odkazy | 14.5px | 500 | `#374151` | – |
| Dropdown – odkazy | 14px | 500 | `#374151` | – |
| Offcanvas – odkazy | 15px | 500 | `#374151` | – |
| Offcanvas – sub-odkazy | 14px | 400 | `$gray-text` | – |
| Top bar – text | 13px | 400 | `rgba(255,255,255,0.85)` | – |
| Top bar – badge | 11px | 700 | `$white` | – |
| CTA nadpis | 36px | 700 (Bold) | `$blue-dark` | – |
| Logo – text | 26px | 800 (ExtraBold) | `$blue-dark` | – |
| Platform – název | 22px | 600 (SemiBold) | `$blue-dark` | – |
| Testimonial – citát | 22px | 400 (Italic) | `$blue-dark` | 1.7 |
| Copyright / legální | 13px | 400 | `$gray-light` | – |
| Feature text | 14px | 600 (SemiBold) | `$blue-dark` | 1.3 |
| Date chip | 13px | 600 (SemiBold) | `$blue-primary` | – |

### 3.3 Responzivní typografie

Při šířce viewportu ≤ 768px se hero nadpis zmenšuje z 52px na 32px, aby se zajistila čitelnost a správné zalamování na menších obrazovkách. Ostatní nadpisy zůstávají ve své výchozí velikosti, ale kontejnerové omezení přirozeně vynucuje zalamování.

### 3.4 Typografické konvence

- Nadpisy používají letter-spacing: -0.5px (H1) pro vizuální zhutnění a moderní vzhled.
- Footer nadpisy jsou psány velkými písmeny (text-transform: uppercase) s letter-spacing: 0.5px.
- Badge „Novinka" v top baru je uppercase se zvětšeným letter-spacing.
- Citace v sekci Social Proof je kurzívou (font-style: italic) s dekorativním uvozovkovým znakem „\201C" (0.75em, Georgia, zelená barva).

---

## 4. Layout a grid

### 4.1 Kontejner

| Vlastnost | Hodnota |
|---|---|
| Maximální šířka | 1360px |
| Horizontální padding | 32px (2rem) |
| Margin | 0 auto (centrování) |
| Šířka | 100% |

SCSS mixin `@container` definuje tyto vlastnosti a je použit napříč všemi sekcemi pro zajištění konzistence. Kontejner vymezuje obsahovou zónu, zatímco barevné pozadí sekcí se roztahuje přes celou šířku viewportu.

### 4.2 Sekce a vertikální rytmus

Každá sekce má konzistentní vertikální padding 80px (top i bottom), s výjimkami uvedenými níže. Tento rytmus vytváří pravidelný, dýchající vertikální prostor mezi obsahovými bloky.

| Sekce | Padding | Poznámka |
|---|---|---|
| Top bar | 10px 0 | Kompaktní informační páska |
| Header | výška 70px | Sticky, s border-bottom |
| Hero | 90px 0 70px | Větší horní padding pro vzdušnost |
| Social Proof | 80px 0 | Standard |
| Online Demo | 80px 0 | Standard |
| Features | 80px 0 | Standard |
| Almanach | 80px 0 | Standard |
| Webináře | 80px 0 | Standard |
| Platforma | 80px 0 | Standard |
| CTA | 100px 0 | Větší padding pro důraz |
| Footer – horní část | 64px top | Následováno border-bottom |
| Footer – spodní část | 20px 0 | Kompaktní legální páska |

### 4.3 Grid systémy

Jednotlivé sekce využívají různé gridové konfigurace podle potřeby obsahu:

| Sekce | Grid | Mezera (gap) | Poznámka |
|---|---|---|---|
| Features | 2 sloupce | 24px | Karty na šířku |
| Almanach | 3 sloupce | 24px | 2 sloupce ≤1024px, 1 sloupec ≤768px |
| Webináře | 2 sloupce | 24px | 1 sloupec ≤1024px |
| Platforma | 2 sloupce (mob) / 4 sloupce (≥768px) | 16–24px | Responzivní breakpoint uvnitř gridu |
| Social Proof – loga | Flexbox, wrap | 40px vert. / 56px horiz. | Centrované logo pole |
| Footer – navigace | Flexbox | 48px | Wrap ≤1024px, column ≤768px |

### 4.4 Rozložení sekcí s dvousloupcovým obsahem

Sekce Hero, Online Demo a CTA používají dvousloupcový flexbox layout:

| Sekce | Směr | Gap | Rozdělení |
|---|---|---|---|
| Hero | Řádek (vlevo text, vpravo obrázek) | 60px | Obsah: max-width 520px, Obrázek: flex: 1 |
| Online Demo | Řádek (vlevo text, vpravo obrázek) | 60px | Obsah: flex: 1, Obrázek: flex: 1, max-width 480px |
| CTA | Řádek (vlevo text, vpravo ilustrace) | 60px | Obsah: flex: 1, Ilustrace: 280×260px fixní |

Při viewportu ≤ 1024px se všechny tyto sekce překlápí do vertikálního (sloupcového) uspořádání.

---

## 5. Komponenty

### 5.1 Tlačítka

V prezentaci se vyskytují dva hlavní typy tlačítek, definované jako SCSS mixin pro snadné opakované použití.

#### 5.1.1 Primární tlačítko (`@mixin btn-primary`)

Primární tlačítko se používá pro hlavní výzvy k akci (CTA). Vizuálně dominantní díky zelené barvě a jemnému stínu.

| Vlastnost | Hodnota |
|---|---|
| Pozadí | `$secondary` (#52b774) |
| Barva textu | `$white` (#ffffff) |
| Váha písma | 700 (Bold) |
| Border-radius | 8px |
| Padding | 12px 28px (výchozí) |
| Font-size | 15px (výchozí) |
| Stín | `0 2px 8px rgba($secondary, 0.3)` |
| Hover pozadí | `$secondary-hover` (#449d62) |
| Hover transform | `translateY(-2px)` |
| Hover stín | `0 4px 16px rgba($secondary, 0.4)` |
| Active transform | `translateY(0)` |
| Active stín | `0 1px 4px rgba($secondary, 0.2)` |
| Transition | `all 0.2s ease` |
| Border | none |

**Varianty velikostí:**

| Umístění | Padding | Font-size |
|---|---|---|
| Header CTA | 10px 20px | 13px |
| Hero „Začít zdarma" | 14px 32px | 16px |
| Demo „Začít zdarma" | 12px 28px | 15px |
| CTA sekce „Začít zdarma" | 14px 36px | 16px |
| Offcanvas CTA | 12px 20px | 14px, width: 100% |

#### 5.1.2 Sekundární tlačítko (`@mixin btn-secondary`)

Sekundární tlačítko se používá pro alternativní akce a odkazy. Vizuálně je podřízené primárnímu tlačítku.

| Vlastnost | Hodnota |
|---|---|
| Pozadí | transparent |
| Barva textu | `$blue-primary` (#254896) |
| Váha písma | 600 (SemiBold) |
| Border-radius | 8px |
| Padding | 12px 28px (výchozí) |
| Font-size | 15px (výchozí) |
| Border | 2px solid `$blue-primary` |
| Hover pozadí | `rgba($blue-primary, 0.06)` |
| Hover transform | `translateY(-1px)` |
| Active transform | `translateY(0)` |
| Transition | `all 0.2s ease` |

**Varianty velikostí:**

| Umístění | Padding | Font-size |
|---|---|---|
| Hero „Online ukázka" | 14px 32px | 16px |
| Webinář „Registrovat se" | 8px 20px | 13px |

### 5.2 Navigace – Desktop

#### 5.2.1 Hlavní navigační lišta

Hlavní navigace je horizontální flexbox s mezerou 4px mezi položkami. Každý odkaz má padding 8px 12px, border-radius 6px a na hover se zvýrazní modrou barvou a jemným modrým pozadím `rgba($blue-primary, 0.04)`.

#### 5.2.2 Dropdown menu

Dropdown menu se zobrazuje při hover nad nadřazenou položkou. Má pozici absolutní vzhledem k nadřazenému `.navItem`, je posunut o 8px dolů (transform) a postupně se proliná (opacity + visibility + transform transition 0.2s ease).

| Vlastnost | Hodnota |
|---|---|
| Min-width | 260px |
| Pozice | Absolute, top: 100%, left: 0 |
| Pozadí | `$white` |
| Border-radius | 12px |
| Stín | `0 4px 24px rgba(0,0,0,0.1), 0 1px 4px rgba(0,0,0,0.06)` |
| Padding | 8px |
| Z-index | 200 |
| Transition | `all 0.2s ease` |
| Výchozí stav | `opacity: 0; visibility: hidden; transform: translateY(8px)` |
| Hover stav | `opacity: 1; visibility: visible; transform: translateY(0)` |

**Dropdown položka:**

| Vlastnost | Hodnota |
|---|---|
| Display | Flex |
| Gap (ikona – text) | 12px |
| Padding | 10px 14px |
| Font-size | 14px |
| Font-weight | 500 |
| Barva | #374151 |
| Border-radius | 8px |
| Hover pozadí | `$blue-bg` |
| Hover barva | `$blue-primary` |
| Ikona velikost | 18×18px |
| Ikona barva | `$blue-primary` (opacity: 0.7, hover: 1) |

**ChevronDown šipka** v nadřazeném odkazu se při hover rotuje o 180° (`transform: rotate(180deg)`) s transition 0.2s ease.

#### 5.2.3 Navigační struktura

| Nadřazená položka | Sub-položky | Ikony |
|---|---|---|
| Produkt | Funkce, Integrace, AI, Zabezpečení, Roadmap, Mobilní a desktop aplikace, Changelog, Nápověda, API | LayoutGrid, Puzzle, Zap, Shield, Map, MonitorSmartphone, FileText, BookOpen, Code |
| Oborová řešení | Agentury, Stavebnictví, Konzultace, Vzdělávání, Neziskovky | Building2, HardHat, Briefcase, GraduationCap, HeartHandshake |
| Ceník | – (přímý odkaz) | – |
| Reference | Zákazníci, Případové studie, Příběhy | Star, Quote, Palette |
| Vzdělávání | Webináře, Školení, Blog, Návody | BookOpen, GraduationCap, FileText, Play |
| O nás | O Freelu, Tým, Kariéra, Novinky | Info, Users, Briefcase, TrendingUp |

### 5.3 Navigace – Mobilní (Offcanvas)

Na viewportu ≤ 768px se desktop navigace skrývá a zobrazuje se hamburger ikona. Po kliknutí se otevírá offcanvas panel z pravé strany.

#### 5.3.1 Hamburger tlačítko

| Vlastnost | Hodnota |
|---|---|
| Display | None (desktop) / Flex (≤768px) |
| Barva | `$blue-dark` |
| Velikost ikony | 24×24px (Menu icon) |
| Padding | 6px |
| Border-radius | 6px |
| Hover pozadí | `rgba($blue-primary, 0.06)` |

#### 5.3.2 Overlay (zatemnění pozadí)

| Vlastnost | Hodnota |
|---|---|
| Pozice | Fixed, inset: 0 |
| Pozadí | `rgba(0, 0, 0, 0.4)` |
| Z-index | 998 |
| Výchozí stav | `opacity: 0; visibility: hidden` |
| Aktivní stav | `opacity: 1; visibility: visible` |
| Transition | `opacity 0.3s ease, visibility 0.3s ease` |

#### 5.3.3 Offcanvas panel

| Vlastnost | Hodnota |
|---|---|
| Pozice | Fixed, top: 0, right: 0 |
| Šířka | 320px (max-width: 85vw) |
| Výška | 100vh |
| Pozadí | `$white` |
| Z-index | 999 |
| Výchozí transform | `translateX(100%)` |
| Otevřený transform | `translateX(0)` |
| Transition | `transform 0.3s ease` |
| Stín | `-4px 0 24px rgba(0,0,0,0.15)` |
| Overflow | y: auto |

**Offcanvas header:** Flex, space-between, padding 16px 20px, border-bottom. Název „Menu" (18px, Bold, `$blue-dark`). Zavírací tlačítko (X ikona, 24px) s hover efektem.

**Offcanvas navigace:** Akordeónové rozbalení pod-položek. Nadřazené položky jsou `<button>` s ChevronDown ikonou, která se rotuje 180° při rozbalení. Pod-položky mají odsazení padding-left: 36px a šedou barvu textu.

**Offcanvas CTA:** Celošířkové primární tlačítko „Přejít do aplikace" ve spodní části panelu, oddělené border-top.

### 5.4 Karty

#### 5.4.1 Feature karta

Čtyři karty v sekci „Chytré funkce pro lepší výsledky". Každá má odlišnou barvu pozadí a ikony.

| Vlastnost | Hodnota |
|---|---|
| Border-radius | 16px |
| Padding | 32px |
| Hover transform | `translateY(-4px)` |
| Hover stín | `0 12px 40px rgba(0,0,0,0.08)` |
| Transition | `transform 0.2s ease, box-shadow 0.2s ease` |

**Barevné varianty:**

| Název | Pozadí karty | Pozadí ikony | Barva ikony |
|---|---|---|---|
| Organizace práce | `$secondary-light` (#e8f5ee) | `$secondary-dark` (#3a8a58) | white |
| Spolupráce a komunikace | `$pink-bg` (#fce4ec) | `$pink-accent` (#e91e63) | white |
| Přehled a plánování | `$green-bg` (#e8f5ee) | `$green-primary` (#52b774) | white |
| Finance a čas | `$light-blue-bg` (#e8edf8) | `$blue-primary` (#254896) | white |

**Ikona:** 48×48px, border-radius 12px, flex-center. SVG ikona 24×24px, bílá barva.

**Seznam položek:** Odrážky realizované pomocí CSS pseudo-elementu `::before` (5px kruh, barva `$blue-primary`, pozice left: 0, top: 8px), s padding-left: 16px.

#### 5.4.2 Almanach karta

Šest karet v 3×2 gridu. Odkazové karty (`<a>`) s ikonou, nadpisem a popisem.

| Vlastnost | Hodnota |
|---|---|
| Pozadí | `$white` |
| Border-radius | 16px |
| Padding | 28px 24px |
| Display | Flex, column, align-items: flex-start |
| Hover transform | `translateY(-4px)` |
| Hover stín | `0 12px 40px rgba($blue-primary, 0.12)` |
| Transition | `transform 0.2s ease, box-shadow 0.2s ease` |

**Ikona kontejner:** 48×48px, border-radius 12px, pozadí `$blue-bg`, SVG ikona 24×24px, barva `$blue-primary`.

**Almanach karty:**

| Název | Ikona |
|---|---|
| Agentury a studia | Building2 |
| Stavebnictví | HardHat |
| Konzultanti | Briefcase |
| Vzdělávací instituce | GraduationCap |
| Neziskové organizace | HeartHandshake |
| Vědomostní báze | BookOpen |

#### 5.4.3 Webinář karta

| Vlastnost | Hodnota |
|---|---|
| Border | 2px solid `$gray-border` |
| Border-radius | 16px |
| Padding | 28px |
| Hover border | `$blue-primary` |
| Hover stín | `0 4px 20px rgba($blue-primary, 0.1)` |
| Transition | `border-color 0.2s, box-shadow 0.2s` |

**Ikona kontejner:** 44×44px, border-radius 10px, pozadí `rgba($blue-primary, 0.1)`, SVG 22×22px, barva `$blue-primary`.

**Date chip:** Pozadí `$blue-bg`, barva `$blue-primary`, padding 6px 14px, border-radius 20px, font-size 13px, font-weight 600.

#### 5.4.4 Platformní karta

| Vlastnost | Hodnota |
|---|---|
| Pozadí | `$blue-bg` |
| Border-radius | 24px |
| Padding | 32px 24px |
| Display | Flex, column, align-items: center |
| Gap | 24px |
| Hover stín | `0 8px 30px rgba($blue-primary, 0.15)` |
| Hover transform | `translateY(-4px)` |

**Ikona kontejner:** 64×64px, border-radius 18px, pozadí `$white`, stín `0 1px 8px rgba(0,0,0,0.08)` (hover: `0 2px 14px rgba(0,0,0,0.12)`), SVG 32×32px, barva `$blue-dark`.

### 5.5 Logo

Logo se skládá ze SVG ikony (34×34px obdélník s border-radius 8px, pozadí `$blue-primary`) a textu „freelo" (26px, font-weight 800, barva `$blue-dark`).

**SVG ikona obsahuje:**
- Modrý obdélník (34×34px, rx=8, fill=#254896)
- Bílý oblouk (cesta s stroke white, strokeWidth 2.5, strokeLinecap round)
- Zelený oblouk (cesta s stroke #52b774, strokeWidth 2.5)
- Bílý kruh (cx=17, cy=12, r=2, fill white)

### 5.6 Top bar

Informační páska v horní části stránky s tmavě modrým pozadím.

| Vlastnost | Hodnota |
|---|---|
| Pozadí | `$blue-dark` (#1d3a7a) |
| Padding | 10px 0 |
| Font-size | 13px |
| Zarovnání | Centrované |

**Badge „Novinka":** Zelené pozadí (`$secondary`), bílý text, font-weight 700, padding 2px 8px, border-radius 4px, font-size 11px, uppercase, letter-spacing zvětšený. Následován odkazem s barvou `rgba(255,255,255,0.85)` (hover: #fff).

### 5.7 Hero sekce – Mockupy

Hero sekce obsahuje CSS-only mockupy aplikace (desktop a mobil), které vizuálně demonstrují produkt.

#### Desktop mockup

| Vlastnost | Hodnota |
|---|---|
| Border-radius | 12px |
| Stín | `0 20px 60px rgba($blue-dark, 0.15)` |
| Pozadí | `$white` |
| Topbar | Pozadí #f1f5f9, padding 8px 12px, 3 barevné tečky (červená, žlutá, zelená) 10×10px |
| Obsah | Grid 2 sloupce, gap 12px, padding 20px, pozadí gradient |
| Mock karta | Bílý, border-radius 8px, padding 14px, border 1px solid $gray-border |

#### Mobilní mockup

| Vlastnost | Hodnota |
|---|---|
| Pozice | Absolutní, bottom: -20px, right: -20px |
| Šířka | 140px |
| Border-radius | 16px |
| Stín | `0 10px 40px rgba($blue-dark, 0.2)` |
| Border | 4px solid #1f2937 |
| Notch | Pozadí #1f2937, výška 20px, kamera 8px kruh |

#### Hero charakter (maskot)

| Vlastnost | Hodnota |
|---|---|
| Pozice | Absolutní, bottom: 60px, left: -40px |
| Velikost | 140×140px |
| Fit | object-fit: contain |

### 5.8 Feature ikony (Hero)

Tři malé ikony v hero sekci pod CTA tlačítky demonstrující klíčové vlastnosti produktu.

| Vlastnost | Hodnota |
|---|---|
| Kontejner | Flex, gap 28px, flex-wrap |
| Ikona kruh | 38×38px, border-radius 50%, pozadí `rgba($blue-primary, 0.08)` |
| SVG velikost | 18×18px, barva `$blue-primary` |
| Text | 14px, font-weight 600, barva `$blue-dark`, white-space: nowrap |
| Na ≤1024px | white-space: normal, flex-wrap: wrap, justify-content: center |

### 5.9 Social Proof – Loga

Klientská loga jsou zobrazena jako flexbox kontejner s centrovaným zarovnáním a obalením.

| Vlastnost | Hodnota |
|---|---|
| Velikost loga | 150×64px |
| Opacita | 0.5 (default), 0.9 (hover) |
| Gap | 40px vertikální, 56px horizontální |
| Font placeholder | 19px, font-weight 800, barva #94a3b8, uppercase, letter-spacing 1.5px |

### 5.10 Testimonial (citace)

| Vlastnost | Hodnota |
|---|---|
| Max-width | 820px |
| Zarovnání | Centrované |
| Citát | 22px, italic, barva `$blue-dark`, line-height 1.7, padding 0 30px |
| Uvozovka dekorace | „\201C", 72px, Georgia, zelená barva, pozice absolutní |
| Autor | 14px, `$gray-text`, jméno tučně v `$blue-dark` |

### 5.11 Footer

#### Horní část

| Vlastnost | Hodnota |
|---|---|
| Pozadí | `$white` |
| Padding-top | 64px |
| Padding-bottom | 48px (s border-bottom) |

**Footer navigace:** 4 sloupce (Produkt, Řešení, Podpora, O nás), flex gap 48px. Nadpisy: 14px, Bold, uppercase, letter-spacing 0.5px, `$blue-dark`. Odkazy: 14px, `$gray-text`, margin-bottom 12px, hover barva `$blue-primary`.

**Pravý panel:** Logo (120px SVG) + sociální ikony (36×36px kruhy, `$blue-bg`, barva `$blue-primary`, hover: pozadí `$blue-primary`, barva white, translateY(-2px)) + kontaktní údaje (13px, `$gray-text`, hover `$blue-primary`).

#### Spodní lišta

| Vlastnost | Hodnota |
|---|---|
| Padding | 20px 0 |
| Zarovnání | Space-between (desktop), column (≤1024px) |
| Copyright | 13px, `$gray-light` |
| Legální odkazy | 13px, `$gray-light`, gap 24px, hover `$blue-primary` |

---

## 6. Ikony

### 6.1 Knihovna

Projekt využívá ikonovou knihovnu **Lucide React** – open-source, stromově zatříděnou sadu ikon postavenou na Feather Icons, s konzistentní 24×24px mřížkou a stroke-based stylem.

### 6.2 Seznam použitých ikon

| Ikona | Komponenta | Velikost | Barva |
|---|---|---|---|
| Menu | Hamburger tlačítko | 24px | `$blue-dark` |
| X | Offcanvas zavřít | 24px | `$gray-text` |
| ChevronDown | Navigační dropdown | 14–16px | Dědí z rodiče |
| ChevronRight | (importováno, nepoužito) | – | – |
| Check | Demo sekce – seznam | 14px | white (v zeleném kruhu) |
| CheckCircle2 | Hero – feature ikona | 18px | `$blue-primary` |
| MessageCircle | Hero – feature ikona | 18px | `$blue-primary` |
| BarChart3 | Hero feature / Features | 18–24px | `$blue-primary` / white |
| FolderOpen | Features karta | 24px | white |
| Users | Features karta / O nás | 24px / 16px | white / `$blue-primary` |
| DollarSign | Features karta | 24px | white |
| LayoutGrid | Dropdown – Produkt | 16–18px | `$blue-primary` |
| Puzzle | Dropdown – Produkt | 16–18px | `$blue-primary` |
| Zap | Dropdown – Produkt / Webinář | 16–22px | `$blue-primary` |
| Shield | Dropdown – Produkt | 16–18px | `$blue-primary` |
| Map | Dropdown – Produkt | 16–18px | `$blue-primary` |
| MonitorSmartphone | Dropdown – Produkt | 16–18px | `$blue-primary` |
| FileText | Dropdown / Features | 16–18px | `$blue-primary` |
| BookOpen | Dropdown / Almanach | 16–24px | `$blue-primary` |
| Code | Dropdown – Produkt | 16–18px | `$blue-primary` |
| Building2 | Dropdown / Almanach | 16–24px | `$blue-primary` |
| HardHat | Dropdown / Almanach | 16–24px | `$blue-primary` |
| Briefcase | Dropdown / Almanach | 16–24px | `$blue-primary` |
| GraduationCap | Dropdown / Almanach | 16–24px | `$blue-primary` |
| HeartHandshake | Dropdown / Almanach | 16–24px | `$blue-primary` |
| Star | Dropdown – Reference | 16–18px | `$blue-primary` |
| Quote | Dropdown – Reference | 16–18px | `$blue-primary` |
| Palette | Dropdown – Reference | 16–18px | `$blue-primary` |
| Info | Dropdown – O nás | 16–18px | `$blue-primary` |
| TrendingUp | Dropdown – O nás | 16–18px | `$blue-primary` |
| Play | Dropdown / Webinář / Footer (YouTube) | 16–22px / 18px | `$blue-primary` / `$blue-primary` |
| Apple | Platforma – iOS | 32px | `$blue-dark` |
| Smartphone | Platforma – Android | 32px | `$blue-dark` |
| Monitor | Platforma – Desktop | 32px | `$blue-dark` |
| Globe | Platforma – Web | 32px | `$blue-dark` |
| Facebook | Footer – sociální | 18px | `$blue-primary` (hover: white) |
| Linkedin | Footer – sociální | 18px | `$blue-primary` (hover: white) |
| Twitter | Footer – sociální | 18px | `$blue-primary` (hover: white) |
| Instagram | Footer – sociální | 18px | `$blue-primary` (hover: white) |

---

## 7. Responzivní design

### 7.1 Breakpointy

Projekt definuje dva hlavní breakpointy:

| Breakpoint | Šířka | Typické zařízení |
|---|---|---|
| Tablet | ≤ 1024px | iPad landscape, menší notebooky |
| Mobil | ≤ 768px | iPhone, Android telefony, iPad portrait |

### 7.2 Změny při ≤ 1024px

Při tomto breakpointu dochází k překlopení dvousloupcových sekcí do vertikálního uspořádání a ke snížení počtu sloupců v gridech:

- **Hero:** Flex-direction column, text centrovaný, tlačítka centrovaná, feature ikony wrap
- **Feature text:** white-space změníno z `nowrap` na `normal`
- **Features grid:** 2 sloupce → 1 sloupec
- **Online Demo:** Flex-direction column
- **Almanach grid:** 3 sloupce → 2 sloupce
- **Webináře grid:** 2 sloupce → 1 sloupec
- **CTA:** Flex-direction column, text centrovaný
- **Footer Inner:** Flex-direction column, gap 40px
- **Footer Nav:** Flex-wrap, gap 32px
- **Footer Side:** align-items: flex-start
- **Footer Contact:** align-items: flex-start
- **Footer Bottom Inner:** Flex-direction column, gap 12px, text centrovaný

### 7.3 Změny při ≤ 768px

Při tomto breakpointu se aktivuje mobilní navigace:

- **Desktop navigace:** `display: none`
- **Header CTA tlačítko:** `display: none`
- **Hamburger tlačítko:** `display: flex`
- **Hero nadpis:** 52px → 32px
- **Platform grid:** gap 16px
- **Almanach grid:** 2 sloupce → 1 sloupec
- **Footer Nav:** Flex-direction column, gap 24px
- **Footer Bottom:** padding 16px 0
- **Footer Legal Links:** Flex-direction column, gap 8px

---

## 8. Interakce a animace

### 8.1 Transition hodnoty

Všechny interaktivní prvky v prezentaci používají jemné, rychlé transitions, které poskytují okamžitou vizuální zpětnou vazbu bez zpomalení interakce.

| Typ | Duration | Easing | Použití |
|---|---|---|---|
| Rychlá | 0.15s | ease | Barva odkazů, pozadí dropdown položek |
| Standard | 0.2s | ease | Tlačítka (hover, active), karty (hover), navigace |
| Pomalejší | 0.3s | ease | Offcanvas panel, overlay, barva/viditelnost |

### 8.2 Hover efekty

| Element | Efekt |
|---|---|
| Primární tlačítko | Pozadí tmavne, translateY(-2px), zvětšení stínu |
| Sekundární tlačítko | Jemné modré pozadí, translateY(-1px) |
| Feature karta | translateY(-4px), zvýrazněný stín |
| Almanach karta | translateY(-4px), modrý stín |
| Platform karta | translateY(-4px), modrý stín |
| Webinář karta | Modrý border, jemný modrý stín |
| Navigační odkaz | Barva → `$blue-primary`, jemné modré pozadí |
| Dropdown položka | Pozadí `$blue-bg`, barva `$blue-primary` |
| Sociální ikona | Pozadí `$blue-primary`, barva white, translateY(-2px) |
| Footer odkaz | Barva → `$blue-primary` |
| Logo (Social Proof) | Opacita 0.5 → 0.9 |
| ChevronDown | Rotate 180° |

### 8.3 Offcanvas animace

Offcanvas panel se zasouvá z pravé strany pomocí `transform: translateX(100%)` → `translateX(0)`. Overlay současně prolíná z `opacity: 0` do `opacity: 1`. Při otevření se na `<body>` aplikuje `overflow: hidden`, aby se zabránilo skrolování pozadí.

### 8.4 Akordeón (Offcanvas)

Pod-položky v mobilním menu se rozbalují/sbalují kliknutím na nadřazenou položku. Stav je řízen React `useState` s `expandedItem` proměnnou. ChevronDown ikona se rotuje 180° při rozbalení. Pod-položky mají `display: none` / `display: block` přepínání přes CSS třídu `.offcanvasExpanded`.

---

## 9. Stavy a accessibility

### 9.1 Základní stavy interaktivních prvků

| Stav | Prostředek | Příklad |
|---|---|---|
| Default | Výchozí vzhled | – |
| Hover | `:hover` CSS pseudo-třída | Zvýraznění odkazů, tlačítek, karet |
| Active | `:active` CSS pseudo-třída | Tlačítka – translateY(0), zmenšený stín |
| Focus | Browser default (doporučeno `:focus-visible`) | Navigační odkazy, tlačítka |
| Expanded | React state + CSS třída | Offcanvas akordeón |

### 9.2 Accessibility

- Hamburger tlačítko má `aria-label="Otevřít menu"`
- Zavírací tlačítko offcanvas má `aria-label="Zavřít menu"`
- Sociální ikony mají `aria-label` atributy (Facebook, LinkedIn, YouTube, Instagram, Twitter)
- Obrázky mají `alt` texty v českém jazyce
- Jazyk dokumentu je nastaven na `lang="cs"`
- Kontrastní poměr textu na pozadí odpovídá WCAG AA standardu (ověřeno pro primární kombinace)
- `suppressHydrationWarning` na `<html>` elementu pro Next.js kompatibilitu

---

## 10. Technický stack

| Technologie | Verze / Typ | Účel |
|---|---|---|
| Next.js | App Router | Framework pro React s SSR/SSG |
| React | 18+ | UI knihovna |
| TypeScript | – | Typová bezpečnost |
| Tailwind CSS | – | Utility-first CSS framework |
| SCSS Modules | `.module.scss` | Komponentové stylování s CSS variables |
| Lucide React | – | Ikony (stroke-based, 24px grid) |
| Inter (Google Fonts) | – | Primární typografie |
| `next/font` | – | Optimalizované načítání fontů |

### 10.1 Architektura souborů

```
src/
├── app/
│   ├── page.tsx           # Hlavní stránka – všechny sekce
│   ├── layout.tsx         # Root layout – metadata, font, body
│   ├── globals.css        # Globální CSS (Tailwind directives)
│   └── freelo.module.scss # SCSS modul – veškeré styly
public/
├── hero-character.png     # Maskot v hero sekci
├── team-photo.png         # Týmová fotka v Demo sekci
└── bird-cta.png           # Ptáček ilustrace v CTA sekci
```

### 10.2 React stavová správa

| Proměnná | Typ | Účel |
|---|---|---|
| `menuOpen` | `boolean` | Řízení viditelnosti offcanvas menu |
| `expandedItem` | `string \| null` | Řízení rozbaleného akordeónu v offcanvas |

---

## 11. Šetrné hodnoty (Design tokens)

Pro snadné přenesení designu do jiných platforem (Figma, jiné frameworky) shrnujeme klíčové design tokeny:

### Barvy

```
--color-primary:        #254896
--color-primary-dark:   #1d3a7a
--color-primary-light:  #3d62b0
--color-primary-accent: #5a7ec9
--color-primary-bg:     #edf1fa

--color-secondary:        #52b774
--color-secondary-hover:  #449d62
--color-secondary-dark:   #3a8a58
--color-secondary-light:  #e8f5ee

--color-pink-bg:     #fce4ec
--color-pink-accent: #e91e63

--color-light-blue-bg: #e8edf8

--color-gray-text:   #6b7280
--color-gray-light:  #9ca3af
--color-gray-border: #e5e7eb

--color-white: #ffffff
```

### Mezery (Spacing)

```
--space-xs:   4px
--space-sm:   8px
--space-md:   12px
--space-lg:   16px
--space-xl:   24px
--space-2xl:  32px
--space-3xl:  48px
--space-4xl:  64px
--space-5xl:  80px
--space-6xl:  100px
```

### Border-radius

```
--radius-sm:  4px   (badge)
--radius-md:  6px   (navigační odkazy, hamburger)
--radius-lg:  8px   (tlačítka, dropdown položky, mockup karty)
--radius-xl:  10px  (webinář ikona)
--radius-2xl: 12px  (dropdown, feature ikona, desktop mockup, team photo)
--radius-3xl: 16px  (karty, mobilní mockup)
--radius-4xl: 18px  (platform ikona kontejner)
--radius-5xl: 20px  (date chip)
--radius-6xl: 24px  (platform karta)
--radius-full: 50%   (kruhové ikony, tečky, sociální ikony)
```

### Stíny

```
--shadow-sm:    0 1px 4px rgba(0,0,0,0.06)
--shadow-md:    0 2px 8px rgba(#52b774, 0.3)
--shadow-lg:    0 4px 20px rgba(#254896, 0.1)
--shadow-xl:    0 8px 30px rgba(#254896, 0.15)
--shadow-2xl:   0 12px 40px rgba(0,0,0,0.08)
--shadow-card:  0 4px 24px rgba(0,0,0,0.1), 0 1px 4px rgba(0,0,0,0.06)
--shadow-hero:  0 20px 60px rgba(#1d3a7a, 0.15)
--shadow-mockup: 0 10px 40px rgba(#1d3a7a, 0.2)
--shadow-offcanvas: -4px 0 24px rgba(0,0,0,0.15)
```

---

## 12. Poznámky k implementaci

### 12.1 Přístup ke stylování

Projekt kombinuje dva stylovací přístupy: SCSS Modules pro hlavní strukturu a komponenty a Tailwind CSS pro rychlé utility třídy. Všechny vlastní styly jsou soustředěny v `freelo.module.scss`, který používá SCSS proměnné, mixiny a vnořování pro čitelnost a udržovatelnost. CSS třídy jsou automaticky scopované modulem, což zabraňuje konfliktům jmen.

### 12.2 Obrazové assety

Tři obrázky jsou načítány z `/public` složky pomocí komponenty `<Image>` z Next.js, která zajišťuje automatickou optimalizaci (lazy loading, responsive sizes, formát WebP/AVIF). Placeholder obrázky log v Social Proof sekci jsou realizovány jako textové prvky s CSS stylingem.

### 12.3 Body overflow

Při otevření mobilního menu se na `document.body` nastavuje `overflow: hidden`, což zabraňuje skrolování pozadí. Při zavření menu se overflow resetuje na prázdný řetězec, čímž se obnoví výchozí chování. Toto je implementováno v `toggleMenu` funkci.

### 12.4 Sticky header

Header je nastaven jako `position: sticky; top: 0; z-index: 100`, takže zůstává viditelný při skrolování. Tím je navigace vždy přístupná bez nutnosti skrolovat nahoru.

### 12.5 Budoucí rozšíření

Případné rozšíření design systému by mělo dodržovat následující principy:
- Nové barvy přidávat jako SCSS proměnné a odpovídající CSS custom properties
- Nové komponenty stylovat v rámci existujícího SCSS modulu nebo vytvořit nový modul
- Respektovat zavedené spacing a radius tokeny
- Dodržovat transition duration 0.2s ease jako standard
- Zajístit responzivní chování na obou breakpointech (1024px a 768px)
- Udržovat WCAG AA kontrastní poměry pro všechny nové barvy a textové kombinace
