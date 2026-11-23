"""make_html.py — the deck as ONE self-contained HTML for a phone / any browser.

Same content as the .pptx (19 slides), but rebuilt for a screen:
* background: the same paint-blob picture as the PPTX, drifting slowly (one GPU transform, no blur)
  with prefers-reduced-motion;
* 16:9 stage scaled to the screen; on a portrait phone the slide sits on top with the speaker notes below;
* navigation: swipe, keys (→ ← space, F full screen, N notes window, B black screen), dots, #hash deep links;
* window.DECK API + ?static=1 so the screenshot/lint tools work on it exactly like on the generated deck.

    python work/kukla/make_html.py     → presentations/kukla-iz-vozdushnogo-plastilina.html
"""
from __future__ import annotations

import base64
import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMG = ROOT / "tools/deck_kukla/html/img"
OUT = ROOT / "presentations/kukla-iz-vozdushnogo-plastilina.html"

C = dict(navy="#2A1A17", ink="#2A1A17", muted="#7A5F57", red="#C8312A", gold="#F4C430", cream="#FFF6E6",
         card="#FFFBF4", sand="#FFE7D2", green="#2A8040", pill="#FFF3D6", soft="#FBD9CC")

# ----------------------------------------------------------------------------- text content
S = []


def add(html: str, notes: str, title: str, bg: str = ""):
    S.append(dict(h=html, n=notes, t=title, bg=bg))


def icon(name: str, cls: str = "ic") -> str:
    return f'<i class="{cls} a-{name}"></i>'


add(f"""<div class="pad cover">
  <p class="eyebrow">«ШАГ В БУДУЩЕЕ ОСЕТИИ»<br>XXVIII КОНКУРС «БАРЫНЯ»</p>
  <h1 class="big">Кукла из<br>воздушного<br>пластилина</h1>
  <p class="lead">Современный материал продолжает традиции декоративно-прикладного искусства</p>
  <p class="meta"><b>Автор:</b> Лолаева Камилла Вадимовна, 12 лет, 6 класс<br>
  ГБОУ «Центр образования „Диалог“» · Руководитель: Гавалиди М. Г.<br>
  Секция «Дизайн и архитектура» · Владикавказ, 2026</p>
</div>
<div class="cover-art"><i class="a-circle"></i><div class="glow"></div><img class="doll" src="IMG:doll" alt="Кукла «Барыня» из воздушного пластилина"></div>""",
    "Вслух можно зачитать название, тему и представить себя и руководителя.",
    "Кукла из воздушного пластилина")

add(f"""<div class="pad">
  <p class="eyebrow">АКТУАЛЬНОСТЬ</p>
  <h2>Проблема и актуальность материала</h2>
  <div class="qmark">?</div>
  <div class="rows wide">
    <div class="card"><p class="tag red">ПРОБЛЕМА</p><p>Поделки из обычного пластилина часто теряют форму, пачкаются и легко мнутся.</p></div>
    <div class="card"><p class="tag red">НОВОЕ РЕШЕНИЕ</p><p>Сегодня появился воздушный пластилин — лёгкий и яркий материал, который сохнет сам.</p></div>
  </div>
  <div class="band"><p class="tag gold">ВОПРОС ИССЛЕДОВАНИЯ</p>
    <p class="bandtxt">Получится ли слепить из него куклу, которая надолго сохранит форму?</p></div>
</div>""",
    "Сначала — проблема: обычный пластилин мягкий, пачкается и легко мнётся. Воздушный застывает сам. "
    "Отсюда вопрос исследования — получится ли кукла, которая надолго сохранит форму.",
    "Проблема и актуальность материала")

add(f"""<div class="pad">
  <p class="eyebrow">ИССЛЕДОВАНИЕ</p>
  <h2>Цель, задачи и гипотеза</h2>
  <div class="card goal"><div class="gicon"><span></span></div>
    <div><p class="tag red">ЦЕЛЬ</p><p class="strong">Изучить воздушный пластилин и создать куклу в традициях
    декоративно-прикладного искусства.</p></div></div>
  <div class="split">
    <div class="card"><p class="tag red">ЗАДАЧИ</p>
      <ol class="num"><li>Узнать о ДПИ и месте куклы в нём</li><li>Изучить историю кукол и свойства материала</li>
      <li>Сделать куклу по эскизу</li><li>Провести опрос ровесников</li></ol></div>
    <div class="card hyp"><p class="tag brown">ГИПОТЕЗА</p><p class="strong">Кукла получится лёгкой и надолго сохранит форму.</p></div>
  </div>
</div>""",
    "Цель — изучить материал и сделать куклу в традициях ДПИ. Четыре задачи: ДПИ, история кукол и свойства, "
    "сама кукла по эскизу, опрос ровесников. Гипотеза: кукла получится лёгкой и надолго сохранит форму.",
    "Цель, задачи и гипотеза")

add(f"""<div class="pad">
  <p class="eyebrow">ТРАДИЦИИ</p>
  <h2>Что такое ДПИ?</h2>
  <p class="lead">Декоративно-прикладное искусство — это создание красивых вещей, которые при этом приносят пользу в быту.</p>
  <p class="small">Это посуда, вышивка, игрушки, украшения и элементы интерьера.</p>
  <div class="tiles">{"".join(f'<div class="tile"><img src="IMG:dpi_{n}" alt="{t}"><span>{t}</span></div>' for n, t in (("plate","Посуда"),("embroidery","Вышивка"),("matryoshka","Игрушки"),("beads","Украшения"),("vase","Интерьер")))}</div>
  <p class="small">В них соединяются практичность и художественный образ.</p>
</div>""",
    "ДПИ — это красивые вещи, которые приносят пользу в быту: посуда, вышивка, игрушки, украшения, интерьер. "
    "В них соединяются практичность и художественный образ.",
    "Что такое ДПИ?")

add(f"""<div class="pad">
  <p class="eyebrow">ИСТОРИЯ</p>
  <h2>История куклы: как менялись игрушки</h2>
  <img class="timeline" src="IMG:timeline" alt="Волнистая линия времени с четырьмя точками">
  <div class="tl">
    <div><b>С древних времён</b><span>Простые фигурки из глины, дерева, соломы и ткани</span></div>
    <div><b>Со временем</b><span>Менялись материалы и мастера, но кукла оставалась близкой человеку</span></div>
    <div><b>Позже</b><span>Более сложные и нарядные игрушки</span></div>
    <div><b>Сегодня</b><span>Лёгкие и яркие куклы из воздушного пластилина</span></div>
  </div>
  <div class="band red"><p class="bandtxt">Кукла — настоящее зеркало эпохи: по ней видно, как жили и во что верили люди.</p></div>
</div>""",
    "Кукла — зеркало эпохи. Сначала простые фигурки из глины, дерева, соломы и ткани. Потом сложнее и наряднее. "
    "Сегодня — лёгкие куклы из воздушного пластилина.",
    "История куклы: как менялись игрушки")

add(f"""<div class="pad two">
  <div>
    <p class="eyebrow">НАРОДНАЯ ТРАДИЦИЯ</p>
    <h2>Дымковская игрушка и образ «Барыни»</h2>
    <p class="lead">В русской народной культуре ярко проявилась традиция яркой игрушки — например, дымковская игрушка.</p>
    <p class="small">Её узнают по белому фону, плавным формам и ярким геометрическим узорам.</p>
    <div class="band red"><p class="bandtxt">Опираясь на традиции народной игрушки, я создала образ — «Барыню».</p></div>
  </div>
  <img class="art" src="IMG:dymkovo" alt="Дымковские игрушки: барыня, кавалер, дети">
</div>""",
    "Дымковская игрушка — белый фон, плавные формы, яркие геометрические узоры. Опираясь на эти традиции, "
    "я создала образ «Барыни».",
    "Дымковская игрушка и образ «Барыни»")

add(f"""<div class="pad two">
  <div>
    <p class="eyebrow">МАТЕРИАЛ</p>
    <h2>Воздушный пластилин: свойства и состав</h2>
    <p class="tag red">СВОЙСТВА</p><p class="small">Воздушный пластилин мягкий, лёгкий и приятный на ощупь, не липнет к рукам и застывает на воздухе.</p>
    <p class="tag red">СОСТАВ</p><p class="small">В его основе — вода, полимерные связующие компоненты и безопасные красители/наполнители (точные пропорции зависят от производителя).</p>
    <p class="tag red">РЕЗУЛЬТАТ</p><p class="small">Благодаря такому составу фигурка после высыхания становится лёгкой и упругой.</p>
  </div>
  <div class="diagram">
    <div class="pill p1">Вода</div><div class="pill p2">Полимерные связующие</div>
    <img class="doll2" src="IMG:doll" alt="Кукла «Барыня» — состав материала">
    <div class="pill p3">Безопасные красители</div><div class="pill p4">Наполнители</div>
  </div>
</div>""",
    "Воздушный пластилин мягкий, лёгкий, не липнет к рукам и застывает на воздухе. В основе — вода, "
    "полимерные связующие, безопасные красители и наполнители. Поэтому фигурка получается лёгкой и упругой.",
    "Воздушный пластилин: свойства и состав")

add(f"""<div class="pad">
  <p class="eyebrow">СРАВНЕНИЕ</p>
  <h2>Обычный и воздушный пластилин</h2>
  <table class="cmp">
    <tr><th></th><th>Обычный пластилин</th><th class="on">Воздушный пластилин</th></tr>
    <tr><td class="row">Вес</td><td>Тяжелее</td><td class="on">Заметно легче</td></tr>
    <tr><td class="row">Руки</td><td>Может пачкать руки</td><td class="on">Не липнет к рукам</td></tr>
    <tr><td class="row">Форма</td><td>Остаётся мягким или деформируется от тепла</td><td class="on">Быстрее принимает форму и фиксируется после высыхания</td></tr>
    <tr><td class="row">Перелепливание</td><td>Зато можно перелепливать сколько угодно раз</td><td class="on">Требует аккуратности до высыхания</td></tr>
  </table>
</div>""",
    "Сравниваем по четырём признакам: вес, руки, форма, перелепливание. Воздушный легче, не пачкает руки, "
    "быстрее держит форму, но требует аккуратности до высыхания.",
    "Обычный и воздушный пластилин")

add(f"""<div class="pad">
  <p class="eyebrow">ПРАКТИКА</p>
  <h2>Подготовка к созданию куклы</h2>
  <p class="small">Для работы я подготовила всё необходимое:</p>
  <div class="tiles tools">{"".join(f'<div class="tile"><img src="IMG:tool_{n}" alt="{t}"><span>{t}</span></div>' for n, t in (("bottle","Бутылка 0,5 л"),("scissors","Ножницы"),("tape","Малярный скотч"),("clay","Воздушный пластилин"),("sticks","Стеки и зубочистки"),("wipes","Влажные салфетки")))}</div>
  <div class="band gold"><p class="bandtxt">Салфетки нужны, чтобы вовремя вытирать руки и поддерживать порядок на столе.</p></div>
</div>""",
    "Для работы нужны бутылка 0,5 л, ножницы, малярный скотч, воздушный пластилин, стеки и зубочистки, "
    "влажные салфетки — чтобы вовремя вытирать руки и держать стол в порядке.",
    "Подготовка к созданию куклы")


def step(n: int, title: str, text: str, img: str, notes: str, big: str = ""):
    dots = "".join(f'<i class="{"done" if k < n - 1 else ("now" if k == n - 1 else "")}">{k + 1}</i>' for k in range(6))
    add(f"""<div class="pad step">
      <p class="eyebrow">ШАГ {n} ИЗ 6</p>
      <h2>{title}</h2>
      <p class="lead">{text}</p>
      {f'<p class="hint">{big}</p>' if big else ''}
      <div class="dots">{dots}</div>
    </div>
    <div class="shot"><img src="IMG:{img}" alt="{title}"></div>""", notes, f"Шаг {n}. {title}")


step(1, "Подготовить бутылку",
     "Срезаем верх бутылки объёмом 0,5 л и аккуратно заклеиваем острый край малярным скотчем, чтобы не порезаться.",
     "step10", "Бутылка — каркас куклы: она держит форму и делает фигурку лёгкой. Верх срезаем и обязательно "
     "заклеиваем острый край малярным скотчем.")
step(2, "Обклеить основу",
     "Покрываем бутылку белым пластилином снизу вверх и тщательно разглаживаем поверхность.",
     "step11", "Пластилин наносим снизу вверх, тонким ровным слоем и разглаживаем: от этого зависит, "
     "насколько аккуратной будет кукла.")
step(3, "Добавить конечности",
     "Лепим верхнюю часть тела, руки и голову, затем плотно скрепляем детали между собой.",
     "step12", "Верхняя часть тела, руки и голова лепятся отдельно и плотно прижимаются к основе, "
     "чтобы после высыхания ничего не отвалилось.")
step(4, "Добавить детали на голову",
     "Делаем глаза-точки, нос, румяна на щеках, рот и причёску.",
     "step13", "Глаза-точки, нос, румяна, рот и причёска — именно они делают куклу живой и узнаваемой.")
step(5, "Добавить аксессуары",
     "Лепим зелёный берет с серой пуговкой, воротник и сумочку и аккуратно прикрепляем их к кукле.",
     "step14", "Зелёный берет с серой пуговкой, воротник и сумочку лепим отдельно и прикрепляем к кукле — "
     "так образ становится нарядным.")
step(6, "Финальные штрихи",
     "Добавляем на платье узор из тонких линий и кружков — образ становится завершённым.",
     "step15", "Узор из тонких линий и кружков на платье — и образ «Барыни» завершён.")

add(f"""<div class="pad result">
  <div>
    <p class="eyebrow">РЕЗУЛЬТАТ</p>
    <h2>Готовая кукла и её характеристики</h2>
    <div class="stats">
      <div class="stat"><b>≈ 22 см</b><span>высота куклы</span></div>
      <div class="stat"><b>≈ 40 г</b><span>вес куклы</span></div>
      <div class="stat"><b>12–24 ч</b><span>сушка в сухом месте</span></div>
    </div>
    <p class="small">Сохнет она примерно 12–24 часа в сухом месте: тонкие детали схватываются быстрее, а более объёмные участки сохнут дольше.</p>
    <p class="tag green">КАК ИСПОЛЬЗОВАТЬ</p>
    <div class="chips"><span class="c1">Сувенир на полку</span><span class="c2">Магнит</span><span class="c3">Подарок близким</span></div>
  </div>
</div>
<div class="shot tall"><img src="IMG:step15" alt="Готовая кукла «Барыня»"></div>""",
    "Кукла высотой около 22 см, весит около 40 г, сохнет 12–24 часа. Её можно поставить на полку как сувенир, "
    "сделать магнитом или подарить близким.",
    "Готовая кукла и её характеристики")

add(f"""<div class="pad">
  <p class="eyebrow">ОПРОС</p>
  <h2>Опрос ровесников</h2>
  <p class="small">Я провела опрос среди 10 ровесников.</p>
  {"".join(f'<div class="qrow"><i class="qic a-{ic}"></i><span class="qt">{t}</span><span class="bv">{bar}</span><b>{v}</b></div>' for ic, t, bar, v in (
      ("bottle", "Уже лепили из воздушного пластилина", '<i class="g"></i>'*7 + '<i class="e"></i>'*3, "7 из 10"),
      ("stick", "Лепили только из обычного", '<i class="y"></i>'*3 + '<i class="e"></i>'*7, "3 из 10"),
      ("check", "Знают, что он застывает", '<i class="g"></i>'*10, "10 из 10"),
      ("thumb", "Хотят научиться лепить такую куклу", '<i class="g"></i>'*10, "10 из 10")))}
  <div class="band gold note"><i class="bulb"></i><p class="bandtxt"><b>Вывод:</b> интерес к материалу высокий, а пошаговый пример наглядно показывает, как сделать куклу.</p></div>
</div>""",
    "Я опросила 10 ровесников. Семь уже лепили из воздушного пластилина, трое — только из обычного. "
    "Все десять знают, что он застывает, и все десять хотят научиться лепить такую куклу. Интерес высокий.",
    "Опрос ровесников")

add(f"""<div class="pad two">
  <div>
    <p class="eyebrow">ИТОГИ</p>
    <h2>Итоги исследования и гипотеза</h2>
    <p class="tag red">В ХОДЕ РАБОТЫ Я</p>
    <ul class="checks">{"".join(f"<li>{t}</li>" for t in ("изучила традиции ДПИ", "изучила историю кукол", "изучила свойства воздушного пластилина", "сделала куклу по эскизу", "провела опрос ровесников"))}</ul>
    <div class="card hyp big-card"><p class="tag bread">ГИПОТЕЗА ПОДТВЕРДИЛАСЬ</p>
      <p class="strong">Кукла из воздушного пластилина получилась лёгкой (около 40 г) и надёжно сохранила форму после высыхания.</p></div>
  </div>
  <figure class="photo"><img src="IMG:girl" alt="Камилла с готовой куклой «Барыней»" title="Камилла с готовой «Барыней»"></figure>
</div>""",
    "Всё, что было в задачах, выполнено. Гипотеза подтвердилась: кукла получилась лёгкой, около 40 г, "
    "и надёжно сохранила форму после высыхания.",
    "Итоги исследования и гипотеза")

add(f"""<div class="pad final">
  <h1 class="thanks">Спасибо за внимание!</h1>
  <img class="group" src="IMG:group" alt="Восемь кукол «Барынь» в дымковских узорах">
</div>""", "Поблагодарить слушателей и пригласить к вопросам.", "Спасибо за внимание!", bg="dark")


# ----------------------------------------------------------------------------- CSS / JS
CSS = """
:root{--ink:#2A1A17;--mute:#7A5F57;--red:#C8312A;--gold:#F4C430;--green:#2A8040;--card:#FFFBF4;--doc:16/9}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
html,body{height:100%;overflow:hidden;background:#1b1210;font-family:Nunito,"Segoe UI",system-ui,-apple-system,sans-serif;color:var(--ink)}
img{display:block;max-width:100%}
/* ---------- animated paint background: ONE image, drifted by a cheap GPU transform (phone-friendly) */
.paint{position:fixed;inset:-6%;z-index:0;background:#FFF5E3 url(IMG:paint) center/cover no-repeat;
 animation:drift 68s ease-in-out infinite alternate;will-change:transform;transform-origin:50% 50%}
@keyframes drift{0%{transform:scale(1.06) translate3d(0,0,0)}
  50%{transform:scale(1.12) translate3d(-1.4%,1.2%,0)}
  100%{transform:scale(1.07) translate3d(1.6%,-1.2%,0)}}
/* ---------- slides */
.slide{position:fixed;inset:0;display:none;place-items:center;z-index:1}
.slide.on{display:grid}
.stage{position:relative;width:min(100vw,calc(100vh*16/9));aspect-ratio:16/9;background:var(--doc);overflow:hidden;container-type:size;
 box-shadow:0 30px 80px rgba(42,26,23,.28);border-radius:2px}
.stage .bgc{position:absolute;inset:0;background:#FFF5E3 url(IMG:paint) center/cover no-repeat;animation:drift 68s ease-in-out infinite alternate;will-change:transform}
.slide[data-bg=dark] .stage{background:#751713}
.slide[data-bg=dark] .bgc{background:radial-gradient(120% 100% at 18% 8%,#8E1D17 0,#751713 58%,#5C100D 100%)}
.pad{position:relative;height:100%;padding:6.2% 5.4%;display:flex;flex-direction:column;gap:1.6%}
.stage>.pad{position:absolute;inset:0}
.eyebrow{font-size:1.02em;font-weight:800;letter-spacing:.14em;color:var(--red);text-transform:uppercase;line-height:1.45}
h1.big{font-family:Lora,Georgia,serif;font-size:4.6em;line-height:1.02;font-weight:700;letter-spacing:-.01em}
h2{font-family:Lora,Georgia,serif;font-size:2.55em;line-height:1.12;font-weight:700}
.lead{font-size:1.5em;line-height:1.4;font-weight:600;max-width:22ch}
.small{font-size:1.22em;line-height:1.45;color:#3a2a26}
.meta{font-size:1.06em;line-height:1.6;color:var(--mute)}
.meta b{color:var(--ink)}
.tag{font-size:.95em;font-weight:800;letter-spacing:.12em;text-transform:uppercase;margin-top:1.2%}
.tag.red{color:var(--red)}.tag.gold{color:var(--gold)}.tag.green{color:var(--green)}.tag.brown{color:#5C463F}.tag.bread{color:#FFEBDD}
.card{background:var(--card);border-radius:1.4em;padding:3.2% 3.6%;box-shadow:0 18px 40px rgba(42,26,23,.06)}
.strong{font-weight:800;font-size:1.45em;line-height:1.35}
.rows{display:flex;flex-direction:column;gap:3%}
.rows.wide{width:74%;margin-left:auto}
.rows .card p:not(.tag){font-size:1.32em;line-height:1.4}
.rows .card{padding:2.6% 3%;border:1px solid #F6E4D6}
.qmark{position:absolute;left:5.4%;top:22%;width:16.5%;aspect-ratio:1;border-radius:50%;background:var(--gold);display:grid;place-items:center;
 font-family:Lora,Georgia,serif;font-size:6.2em;font-weight:700;color:#2A1A17}
.band{background:#2A1A17;color:#fff;border-radius:1.1em;padding:2.1% 2.6%;margin-top:auto}
.band .bandtxt{font-size:1.42em;font-weight:800;line-height:1.35}
.band.red{background:var(--red)}.band.gold{background:var(--gold);color:#2A1A17}
.split{display:grid;grid-template-columns:1.35fr 1fr;gap:3%;margin-top:2%}
.goal{display:flex;gap:3%;align-items:center;margin-top:2%}
.gicon{width:2.6em;height:2.6em;border-radius:50%;background:var(--red);display:grid;place-items:center;flex:none}
.gicon span{width:.95em;height:.95em;border-radius:50%;background:#fff;box-shadow:0 0 0 .28em var(--red),0 0 0 .42em #fff}
ol.num{list-style:none;counter-reset:n;display:flex;flex-direction:column;gap:.5em;margin-top:2%}
ol.num li{counter-increment:n;display:flex;gap:.7em;align-items:center;font-size:1.28em;line-height:1.3}
ol.num li:before{content:counter(n);flex:none;width:1.55em;height:1.55em;border-radius:50%;background:var(--red);color:#fff;
 display:grid;place-items:center;font-size:.82em;font-weight:900}
.hyp{background:var(--gold)}
.hyp .tag{color:#5a3d00}
.tiles{display:grid;grid-template-columns:repeat(5,1fr);gap:2.4%;margin-top:auto}
.tiles.tools{grid-template-columns:repeat(6,1fr);margin:3% 0 auto}
.tile{background:var(--card);border-radius:1.1em;padding:6% 4%;display:flex;flex-direction:column;align-items:center;gap:.7em;
 box-shadow:0 12px 28px rgba(42,26,23,.06);border:1px solid #F6E4D6}
.tile img{width:58%;aspect-ratio:1;object-fit:contain}
.tiles.tools .tile img{width:46%}
.tile span{font-size:1.02em;font-weight:700;text-align:center;line-height:1.2}
.timeline{width:100%;margin:1% 0 0;opacity:.95}
.tl{display:grid;grid-template-columns:repeat(4,1fr);gap:2%;margin-top:-2%}
.tl b{display:block;font-family:Lora,Georgia,serif;font-size:1.3em;margin-bottom:.3em}
.tl span{font-size:1em;line-height:1.3;color:#4a3733}
.two{display:grid;grid-template-columns:minmax(0,1.04fr) minmax(0,1fr);gap:4%;align-items:stretch}
.two>div{min-width:0}
.two .art{width:100%;align-self:center;border-radius:1.2em}
.diagram{position:relative;background:#FBD9CC;border-radius:1.3em;display:grid;place-items:center;overflow:hidden}
.doll2{position:absolute;left:50%;top:54%;transform:translate(-50%,-50%);height:74%;width:auto;max-width:56%}
.pill{position:absolute;background:#fff;border-radius:99px;padding:.42em .75em;font-size:.82em;line-height:1.12;font-weight:800;
 text-align:center;max-width:44%;
 box-shadow:0 10px 24px rgba(42,26,23,.08)}
.p1{left:6%;top:6%}.p2{right:4%;top:9%}.p3{left:3%;bottom:8%}.p4{right:4%;bottom:7%}
table.cmp{width:100%;border-collapse:separate;border-spacing:0 0.55em;margin-top:2%}
table.cmp th{font-size:1.1em;padding:.55em 1em;text-align:left;border-radius:.8em}
table.cmp th:nth-child(2){background:#5C463F;color:#fff}
table.cmp th:nth-child(3){background:var(--red);color:#fff}
table.cmp td{font-size:1.14em;line-height:1.3;padding:.62em 1em;background:white}
table.cmp td.row{background:none;color:var(--red);font-weight:800;font-size:1.05em;padding-left:0}
table.cmp td.on{background:#fff;box-shadow:inset 0 0 0 1px #F3C9BF;border-radius:.7em}
.pad.step{justify-content:flex-start}
.pad.step .pad{padding:0}
.pad.step h2{margin-top:.2em}
.pad.step .lead{margin-top:1.6%;max-width:31ch}
.pad.step{padding-right:36%}
.cover{padding-right:40%}
.hint{margin-top:1.2%;font-size:1.15em;color:var(--mute)}
.dots{position:absolute;left:5.4%;bottom:6.4%;display:flex;gap:.6em}
.dots i{width:2.1em;height:2.1em;border-radius:50%;background:#F3E2CE;color:#7A5F57;box-shadow:0 2px 6px rgba(42,26,23,.06);display:grid;place-items:center;font-style:normal;font-weight:900;font-size:1em}
.dots i.done{background:var(--green);color:#fff}.dots i.now{background:var(--red);color:#fff}
.shot{position:absolute;right:3.6%;top:5.5%;bottom:5.5%;width:29%;border-radius:1.2em;overflow:hidden;box-shadow:0 24px 50px rgba(42,26,23,.14)}
.shot img{width:100%;height:100%;object-fit:cover}
.shot.tall{width:33%}
.pad.result{padding-right:36%}
.result .stats{display:flex;gap:1.6%;margin:2.4% 0 1.6%}
.stat{flex:1;min-width:0;background:var(--card);border-radius:1.1em;padding:2.6% 2.8%;box-shadow:0 14px 30px rgba(42,26,23,.06)}
.stat b{display:block;font-family:Lora,Georgia,serif;font-size:1.78em;color:var(--red);line-height:1;white-space:nowrap}
.stat span{font-size:1.02em;color:var(--mute)}
.chips{display:flex;gap:1.6%;margin-top:1.6%;flex-wrap:wrap}
.chips span{border-radius:99px;padding:.55em .95em;font-size:.95em;font-weight:800;white-space:nowrap}
.pad.result .small{font-size:1.12em}
.c1{background:var(--gold);color:#2A1A17}.c2{background:#F3BDB4;color:#2A1A17}.c3{background:var(--green);color:#fff}
.qrow{display:flex;align-items:center;gap:2%;padding:.55em 0;border-bottom:1px solid #EEDCCB}
.qrow:last-of-type{border-bottom:0}
.qic{width:2.2em;height:2.2em;border-radius:50%;background:var(--red);flex:none}
.qt{font-size:1.24em;font-weight:700;flex:1}
.bv{display:flex;gap:.28em}
.bv i{width:1.15em;height:1.15em;border-radius:50%}
.bv i.g{background:var(--green)}.bv i.y{background:var(--gold)}.bv i.e{background:#EBD9C3}
.qrow b{font-size:1.2em;min-width:4.6em;text-align:right}
.band.note{display:flex;gap:1.6%;align-items:center;margin-top:auto}
.band.note .bandtxt{font-size:1.24em}
.bulb{width:1.7em;height:1.7em;border-radius:50%;background:#2A1A17;flex:none}
ul.checks{list-style:none;display:flex;flex-direction:column;gap:.65em;margin-top:1.6%}
ul.checks li{display:flex;gap:.7em;align-items:center;font-size:1.26em;font-weight:600}
ul.checks li:before{content:"";width:1.5em;height:1.5em;border-radius:50%;background:var(--green);flex:none;
 box-shadow:inset 0 0 0 .0 #fff;background-image:linear-gradient(var(--green),var(--green))}
ul.checks li:after{content:"✓";position:absolute}
.big-card{background:#C8553D;color:#fff;margin-top:3%;padding:3.4% 3.8%}
.big-card .strong{font-size:1.34em;margin-top:.5em}
.photo{margin:0;min-height:0;display:flex;flex-direction:column;justify-content:center}
.photo img{width:100%;height:100%;max-height:100%;object-fit:cover;object-position:50% 42%;border-radius:1.3em;
 box-shadow:0 24px 50px rgba(42,26,23,.18)}
.cover{justify-content:center;padding-right:44%}
.cover .lead{margin-top:1.4%;max-width:26ch;font-size:1.38em}
.cover .meta{margin-top:2.4%}
.cover-art{position:absolute;inset:0;pointer-events:none}
.cover-art .a-circle{position:absolute;right:6%;top:10%;width:38%;aspect-ratio:1;border-radius:50%;background:#F5A99D;opacity:.85}
.cover-art .doll{position:absolute;right:9%;top:7%;height:88%;width:auto;filter:drop-shadow(0 26px 40px rgba(42,26,23,.22))}
.final{align-items:center;justify-content:center;gap:3%}
.thanks{font-family:Lora,Georgia,serif;color:#fff;font-size:3.9em;text-align:center}
.group{width:86%;margin:0 auto}
/* ---------- phone / portrait: the slide on top, notes below */
.notes{display:none}
@media (orientation:portrait),(max-width:820px){
  html,body{overflow:auto}
  .slide{position:relative;inset:auto;display:none;grid-template-rows:auto 1fr}
  .slide.on{display:grid}
  .stage{width:100vw;box-shadow:none;border-radius:0}
  .notes{display:flex;flex-direction:column;align-content:start;gap:10px;padding:18px 18px 86px;background:#150e0c;
   color:#F3E7DE;min-height:calc(100dvh - 56.25vw)}
  .notes .rot{font:700 13px Nunito,sans-serif;color:#C8A79A;letter-spacing:.02em}
  #nav .dotsnav{display:none}#cnt{white-space:nowrap}
  .notes h3{font:800 20px/1.25 Nunito,sans-serif;margin-bottom:8px}
  .notes p{font-size:16px;line-height:1.5;color:#E8DCD4}
  .stage{font-size:clamp(4.5px,1.15vw,22px)}
  #nav{display:flex}
}
@media (orientation:landscape) and (min-aspect-ratio:3/2){.stage{font-size:clamp(8px,1.15vw,26px)}}
@media (prefers-reduced-motion:reduce){.paint,.paint i{animation:none!important}}
/* screenshots / print: freeze the background so capture is instant and pixel-identical */
html.static *,html.static *:before,html.static *:after{animation:none!important;transition:none!important}
html.static .paint{transform:scale(1.08)}
html.static #nav,html.static #bar,html.static #toast{opacity:0;pointer-events:none}
/* ---------- chrome */
#bar{position:fixed;left:0;top:0;height:3px;background:var(--red);z-index:12;transition:width .3s}
#nav{position:fixed;left:50%;bottom:max(10px,env(safe-area-inset-bottom));transform:translateX(-50%);z-index:12;display:flex;gap:6px;
 align-items:center;background:rgba(42,26,23,.72);backdrop-filter:blur(10px);padding:6px 8px;border-radius:99px;color:#fff;
 font:800 13px Nunito,sans-serif;opacity:1;transition:opacity .5s}
#nav button{border:0;background:rgba(255,255,255,.14);color:#fff;min-width:34px;height:30px;border-radius:99px;font:800 15px Nunito,sans-serif;cursor:pointer}
#nav .dotsnav{display:flex;gap:4px;margin:0 4px}
#nav .dotsnav i{width:7px;height:7px;border-radius:50%;background:rgba(255,255,255,.34);cursor:pointer}
#nav .dotsnav i.on{background:var(--gold);transform:scale(1.25)}
.idle #nav{opacity:0;pointer-events:none}
#black{position:fixed;inset:0;background:#000;z-index:40;display:none}#black.on{display:block}
#toast{position:fixed;left:50%;bottom:60px;transform:translateX(-50%);z-index:13;background:rgba(42,26,23,.9);color:#fff;
 font:800 13px Nunito,sans-serif;padding:8px 14px;border-radius:10px;opacity:0;transition:opacity .4s;white-space:nowrap}
#toast.on{opacity:1}
.nojs .slide{position:relative;display:grid;inset:auto;max-width:1100px;margin:12px auto}
.nojs #nav,.nojs #bar,.nojs .notes{display:none}
@media print{.paint,#nav,#bar,#toast{display:none!important}.slide{position:relative;display:grid;inset:auto;break-after:page}}
"""

JS = """
document.documentElement.classList.remove('nojs');
const q=new URLSearchParams(location.search),STATIC=q.has('static')||q.has('print');
if(STATIC)document.documentElement.classList.add('static');
const sl=[...document.querySelectorAll('.slide')],N=sl.length,bar=document.getElementById('bar');
const dots=[...document.querySelectorAll('#nav .dotsnav i')],cnt=document.getElementById('cnt');
let cur=-1,idleT=0;
function go(i,o){i=Math.max(0,Math.min(N-1,i));sl.forEach((s,k)=>s.classList.toggle('on',k===i));cur=i;
 bar.style.width=((i+1)/N*100)+'%';dots.forEach((d,k)=>d.classList.toggle('on',k===i));cnt.textContent=(i+1)+' / '+N;
 if(!o||!o.instant){sl[i].animate?sl[i].animate([{opacity:0,transform:'translateY(6px)'},{opacity:1,transform:'none'}],{duration:320,easing:'ease-out'}):0}
 try{history.replaceState(null,'','#'+(i+1))}catch(e){}
 const im=sl[i].querySelector('img');return im&&im.decode?im.decode().catch(()=>0):Promise.resolve();}
function next(){go(cur+1)}function prev(){go(cur-1)}
document.getElementById('p').onclick=e=>{e.stopPropagation();prev()};
document.getElementById('x').onclick=e=>{e.stopPropagation();next()};
document.getElementById('f').onclick=e=>{e.stopPropagation();const d=document.documentElement;
 (document.fullscreenElement?document.exitFullscreen():(d.requestFullscreen||d.webkitRequestFullscreen||(()=>{})).call(d)).catch&&0;};
dots.forEach((d,k)=>d.onclick=e=>{e.stopPropagation();go(k)});
const black=document.getElementById('black'),toast=document.getElementById('toast');
let nw=null;
function say(t){toast.textContent=t;toast.classList.add('on');clearTimeout(say.t);say.t=setTimeout(()=>toast.classList.remove('on'),3000)}
const NOTES=JSON.parse(document.getElementById('notes-data').textContent);
const NP=`<!doctype html><html lang=ru><head><meta charset=utf-8><title>Заметки докладчика</title><style>
body{margin:0;background:#150e0c;color:#F3E7DE;font:18px/1.55 Nunito,system-ui,sans-serif;display:flex;flex-direction:column;height:100vh}
header,footer{display:flex;gap:14px;align-items:center;padding:12px 20px;background:#2A1A17;font-weight:800}
#c{background:#F4C430;color:#2A1A17;border-radius:99px;padding:3px 12px}#t{margin-left:auto;font-size:24px;font-variant-numeric:tabular-nums}
main{flex:1;overflow:auto;padding:18px 26px}h1{font:700 30px/1.2 Lora,Georgia,serif;margin:0 0 14px}
#n{font-size:24px;line-height:1.6}#x{flex:1;color:#9d8a82;font-size:16px}
button{font:800 17px system-ui;border:0;border-radius:12px;padding:10px 18px;cursor:pointer}#p{background:#ffffff22;color:#fff}
#nx{background:#F4C430;color:#2A1A17}</style></head><body><header><span id=c></span><span>Заметки докладчика</span>
<span id=t>0:00</span></header><main><h1 id=h></h1><div id=n></div></main><footer><span id=x></span>
<button id=p>‹ Назад</button><button id=nx>Дальше ›</button></footer></body></html>`;
let nt0=0;
function syncNotes(){if(!nw||nw.closed)return;const d=nw.document,c=NOTES[cur];if(!c)return;
 d.getElementById('c').textContent=(cur+1)+' / '+N;d.getElementById('h').textContent=c.t;d.getElementById('n').textContent=c.n;
 d.getElementById('x').textContent=cur+1<N?'Дальше: '+NOTES[cur+1].t:'Это последний слайд';}
function openNotes(){if(nw&&!nw.closed){nw.focus();return}
 nw=window.open('','deck-notes','width=860,height=620');
 if(!nw){say('Браузер заблокировал окно заметок — разрешите всплывающие окна');return}
 nw.document.open();nw.document.write(NP);nw.document.close();nt0=Date.now();
 nw.document.addEventListener('keydown',onKey);
 nw.document.getElementById('p').onclick=prev;nw.document.getElementById('nx').onclick=next;syncNotes();}
setInterval(()=>{if(nw&&!nw.closed){const t=Math.floor((Date.now()-nt0)/1000);
 nw.document.getElementById('t').textContent=Math.floor(t/60)+':'+String(t%60).padStart(2,'0')}},1000);
function onKey(e){
 if(['ArrowRight','PageDown',' ','Enter','ArrowDown'].includes(e.key)){e.preventDefault();black.classList.remove('on');next()}
 else if(['ArrowLeft','PageUp','Backspace','ArrowUp'].includes(e.key)){e.preventDefault();black.classList.remove('on');prev()}
 else if(e.key==='Home')go(0);else if(e.key==='End')go(N-1);
 else if(e.key==='f'||e.key==='F'||e.key==='а'||e.code==='KeyF'){document.getElementById('f').click()}
 else if(e.code==='KeyB'||e.key==='b'||e.key==='и'||e.key==='.'){black.classList.toggle('on')}
 else if(e.code==='KeyN'||e.key==='n'||e.key==='т'){openNotes()}}
addEventListener('keydown',onKey);
black.onclick=()=>black.classList.remove('on');
// touch: horizontal swipe = next/prev, but a vertical swipe scrolls the notes on a phone
let tx=0,ty=0,tt=0;
addEventListener('touchstart',e=>{tx=e.touches[0].clientX;ty=e.touches[0].clientY;tt=Date.now()},{passive:true});
addEventListener('touchend',e=>{const dx=e.changedTouches[0].clientX-tx,dy=e.changedTouches[0].clientY-ty;
 if(Date.now()-tt<900&&Math.abs(dx)>46&&Math.abs(dx)>Math.abs(dy)*1.7){dx<0?next():prev()}},{passive:true});
// click zones (landscape): left 22% back, right 22% forward
addEventListener('click',e=>{if(e.target.closest('button,i,.dots,.notes,a'))return;
 const w=innerWidth;if(innerWidth<821&&innerHeight>innerWidth)return;
 if(e.clientX>w*0.78)next();else if(e.clientX<w*0.22)prev();else if(innerHeight>innerWidth)next()});
// idle chrome
let hid=false;
function wake(){document.body.classList.remove('idle');clearTimeout(idleT);idleT=setTimeout(()=>document.body.classList.add('idle'),2600)}
['mousemove','touchstart','keydown','click'].forEach(t=>addEventListener(t,wake,{passive:true}));wake();
addEventListener('hashchange',()=>{const n=parseInt(location.hash.slice(1));if(n>=1&&n<=N)go(n-1,{instant:1})});
const start=parseInt(location.hash.slice(1))||1;
go(start-1,{instant:1});
if(!STATIC)setTimeout(()=>say('Свайп или ← → · F — весь экран · N — заметки · B — чёрный экран'),1200);
window.DECK={get count(){return N},get index(){return cur},go:(i,o)=>go(i,o||{instant:1}),replay(){go(cur,{instant:1})},
 revealAll(){},audit(){const a=[];const s=sl[cur];if(!s)return a;
  s.querySelectorAll('.pad *').forEach(el=>{const r=el.getBoundingClientRect(),p=s.querySelector('.stage').getBoundingClientRect();
   if(r.width&&r.height&&(r.right>p.right+1||r.bottom>p.bottom+1||r.left<p.left-1))a.push((el.className||el.tagName)+' выходит за слайд')});return a}};
"""


def embed(s: str) -> str:
    """IMG:name → data URI (one offline file)."""
    def rep(m):
        p = IMG / f"{m.group(1)}.webp"
        return "data:image/webp;base64," + base64.b64encode(p.read_bytes()).decode()
    return re.sub(r"IMG:([a-z0-9_]+)", rep, s)


def main() -> int:
    t0 = time.time()
    body = []
    for i, s in enumerate(S, 1):
        body.append(f'<section class="slide" data-bg="{s["bg"]}" aria-label="{s["t"]}">'
                    f'<div class="stage"><div class="bgc"></div>{s["h"]}</div>'
                    f'<div class="notes"><span class="rot">Поверните телефон — слайд на весь экран</span>'
                    f'<h3>{i} / {len(S)} · {s["t"]}</h3><p>{s["n"]}</p></div></section>')
    notes = json.dumps([{"t": s["t"], "n": s["n"]} for s in S], ensure_ascii=False)
    nav = "".join('<i class=""></i>' for _ in S)
    notes_json = notes.replace("</", "<\\/")
    html_doc = f"""<!doctype html><html lang="ru" class="nojs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="generator" content="pptkit-deck"><meta name="theme-color" content="#2A1A17">
<title>Кукла из воздушного пластилина — презентация</title>
<style>{CSS}</style></head><body>
<div class="paint" aria-hidden="true"></div>
<div id="bar"></div>
{"".join(body)}
<div id="nav"><button id="p" aria-label="Назад">‹</button><span class="dotsnav">{nav}</span>
<span id="cnt">1 / {len(S)}</span><button id="x" aria-label="Вперёд">›</button>
<button id="f" aria-label="Во весь экран">⤢</button></div>
<div id="black"></div><div id="toast"></div>
<script type="application/json" id="notes-data">{notes_json}</script>
<script>{JS}</script></body></html>"""
    html_doc = embed(html_doc)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html_doc, encoding="utf-8")
    print(f"→ {OUT}  {OUT.stat().st_size/1024:.0f} KB  ({time.time()-t0:.1f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
