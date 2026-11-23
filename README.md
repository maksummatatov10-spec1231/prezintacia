# prezintacia — тулкит для презентаций + две готовые презентации

## 📦 Готовые презентации

### «Кукла из воздушного пластилина» (правки по пунктам заказчика)
| Файл | Для чего |
|---|---|
| [`presentations/kukla-iz-vozdushnogo-plastilina.pptx`](presentations/kukla-iz-vozdushnogo-plastilina.pptx) | PowerPoint, 19 слайдов: живой фон-видео (петля) + статичная подложка, фото автора с куклой на 18-м, плавные переходы, 0 замечаний проверки |
| [`presentations/kukla-iz-vozdushnogo-plastilina.html`](presentations/kukla-iz-vozdushnogo-plastilina.html) | Один HTML-файл для телефона: живой фон на CSS, свайпы, чёрный экран (B), заметки докладчика (N) |

**Скачать из релиза [v1.1-kukla](https://github.com/maksummatatov10-spec1231/prezintacia/releases/tag/v1.1-kukla):** [HTML](https://github.com/maksummatatov10-spec1231/prezintacia/releases/download/v1.1-kukla/kukla-iz-vozdushnogo-plastilina.html) · [PPTX](https://github.com/maksummatatov10-spec1231/prezintacia/releases/download/v1.1-kukla/kukla-iz-vozdushnogo-plastilina.pptx)

Пересобрать из исходника (`input/kukla-iz-vozdushnogo-plastilina.pptx` — файл заказчика, не меняется):
```bash
python tools/deck_kukla/build_deck.py     # PPTX: рот чёрный на 13–15, фото на 18, видео-фон, 0 ошибок
python tools/deck_kukla/make_html.py      # HTML для телефона с живым фоном
python tools/paint_bg.py out/paint.mp4    # сам видео-фон (бесшовная петля, 4 краски)
```

### «Как появилась Древняя Греция» (детская практическая презентация)
| Файл | Для чего |
|---|---|
| [`presentations/drevnyaya-gretsiya.pptx`](presentations/drevnyaya-gretsiya.pptx) | PowerPoint: 20 слайдов, анимации, переходы, кликабельная викторина, встроенные шрифты, заметки докладчика |
| [`presentations/drevnyaya-gretsiya.html`](presentations/drevnyaya-gretsiya.html) | Один HTML-файл, работает офлайн. На компьютере — 16:9 с анимациями, на телефоне — своя вертикальная раскладка, свайпы, увеличение карт, викторина |

**Скачать из релиза [v1.0-greece](https://github.com/maksummatatov10-spec1231/prezintacia/releases/tag/v1.0-greece):** [HTML](https://github.com/maksummatatov10-spec1231/prezintacia/releases/download/v1.0-greece/drevnyaya-gretsiya.html) · [PPTX](https://github.com/maksummatatov10-spec1231/prezintacia/releases/download/v1.0-greece/drevnyaya-gretsiya.pptx)

HTML откройте в браузере телефона (Chrome или Safari): после скачивания интернет не нужен. В просмотрщике без JavaScript (например, «Файлы» на iPhone) все слайды показываются подряд, по вертикали.

Файлы в релизах обновляются автоматически: workflow `.github/workflows/release-presentations.yml` срабатывает при каждом изменении `presentations/` и заново прикрепляет оба PPTX и оба HTML к их релизам (v1.0-greece и v1.1-kukla).

## ⚡ Установка окружения (1 команда)
```bash
./setup_env.sh            # Python venv + LibreOffice (WASM) + headless Chromium + шрифты Google Fonts + самопроверка
./setup_env.sh --assets   # + исходники карт и иконок (только чтобы пересобрать картинки практической презентации)
```
Нужен доступ только к pypi.org, registry.npmjs.org и github.com. Не требуются apt, sudo или установленный Office: PPTX рендерится LibreOffice, скомпилированным в WebAssembly. Повторный запуск идёт около 2 с: скрипт докачивает только недостающее.

## 🧰 Инструменты (`tools/*.py`)
Каждый запуск создаёт папку `checks/runs/<время>-<инструмент>-<файл>/`, а копия последней лежит в **`checks/latest/`**. В папке:
- скриншоты PNG/JPG и контакт-лист;
- `summary.md` — отчёт;
- `log.txt` — лог с миллисекундами;
- `result.json` — данные.

| Инструмент | Что делает | Пример |
|---|---|---|
| `analyze.py` | структура за ~0,2 с: слайды, фигуры (id, имя, размеры в см), текст, шрифты, картинки (dpi, обрезка), анимации | `python tools/analyze.py deck.pptx --slide 3` |
| `check.py` | полная проверка: скриншоты всех слайдов, контакт-лист, lint (см. ниже); для HTML — снимки компьютер + телефон и аудит вёрстки | `python tools/check.py deck.pptx` |
| `snap.py` | **скриншот чего угодно**: pptx/docx/xlsx/pdf/html/svg/URL/HTML-строка/папка картинок | `python tools/snap.py deck.pptx --slides 2,5-7` |
| `snapd.py` | тёплый Chromium-демон: скриншот за 50–300 мс | `python tools/snapd.py shot page.html -o a.png` |
| `edit.py` | 27 точных операций над pptx + картинки «до / после / разница» | см. ниже |
| `pptx2html.py` | **любой** pptx → один HTML для телефона (свайпы, заметки под слайдом) | `python tools/pptx2html.py deck.pptx` |
| `fonts.py` | какие шрифты в pptx, каких не хватает, установка из Google Fonts за ~1 с, встраивание в pptx | `python tools/fonts.py check deck.pptx` |
| `img.py` | info (dpi на слайде), crop, cover (кадр с точки интереса), fit, optimize/webp, sheet, diff, contrast | `python tools/img.py cover pic.jpg --size 1920x1080 --focus 0.6,0.4` |
| `bench.py` | замер скорости каждого шага | `python tools/bench.py deck.pptx --html deck.html` |

### `edit.py` — правки «мгновенно и точно»
```bash
python tools/edit.py deck.pptx --list 3                     # фигуры слайда 3: id, имена, размеры
python tools/edit.py deck.pptx -o deck_v2.pptx \
  --do "move slide=2 shape='Picture 3' x=2cm y=10%" \
  --do "resize slide=2 shape=id:5 w=12cm keep_aspect=true" \
  --do "zoom slide=4 shape=picture:1 factor=1.4 focus=0.35,0.5" \
  --do "crop slide=4 shape=picture:1 left=10% right=5%" \
  --do "fit slide=5 shape='Рисунок 2' mode=cover focus=0.5,0.3" \
  --do "replace_image slide=6 shape=picture:1 src=new.jpg" \
  --do "font slide=1 shape=title size=48 bold=true color=#1F4E79" \
  --do "replace_text old='2023' new='2024'"
python tools/edit.py deck.pptx --ops changes.yaml -o deck_v2.pptx   # список правок в YAML/JSON
```
**Операции:**
- фигуры: `move` `resize` `scale` `set_box` `rotate` `align` `distribute` `z` `duplicate_shape` `delete`;
- картинки: `crop` `fit` `zoom` `pan` `replace_image` `add_image`;
- текст: `set_text` `replace_text` `font`;
- оформление: `fill` `background`;
- слайды: `move_slide` `duplicate_slide` `delete_slide` `hide_slide` `notes` `transition`.

**Выбор фигуры:**
- `id:7`;
- `'Имя'` — точное имя, затем начало имени, затем часть имени;
- `text:фрагмент`;
- `picture:2`;
- `title`;
- `idx:0`.

**Единицы:** `cm`, `mm`, `in`, `pt`, `px`, `%` (от ширины или высоты слайда), EMU.

Скорость: сами операции занимают миллисекунды. После правки перерисовываются только изменённые слайды (инкрементальный кэш).

### Что проверяет `check.py` (lint)
- переполнение текста (по настоящим метрикам шрифта);
- наложения в зоне контента;
- выход за край слайда;
- мелкий шрифт (< 14 pt);
- слишком много слов;
- низкое разрешение картинок (< 96 dpi);
- растянутые картинки;
- контраст текста (< 3:1);
- отсутствующие и подменённые шрифты.

У каждой проблемы есть подсказка, как её исправить.

## 🏛 Практическая презентация — исходники
- `deck/greece/slides.py` — единая модель 20 слайдов. Из неё строятся и PPTX, и HTML.
- `deck/greece/render_pptx.py` и `deck/greece/render_html.py` — рендеры в PPTX и HTML.
- `deck/greece/assets.py` — карты (Natural Earth), иконки (Fluent Emoji), орнамент, шрифты.
- Сборка: `python deck/greece/build.py` пересобирает PPTX и HTML и проверяет их скриншотами (около 30 с).

## 📚 Как делать презентации хорошо, быстро и круто
Шпаргалка по итогам поиска, с источниками: [`docs/guide.md`](docs/guide.md).

## Лицензии и источники
- Иллюстрации нарисованы ИИ для этой презентации.
- Фото: «Маска Агамемнона» (Wikimedia Commons) и фреска «Дельфины» из Кносса (общественное достояние).
- Карты: Natural Earth (общественное достояние).
- Иконки: Microsoft Fluent Emoji (MIT).
- Шрифты: Nunito и Comfortaa (SIL OFL, тексты лицензий лежат в `deck/greece/assets/fonts/`).
