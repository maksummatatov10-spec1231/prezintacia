# Как делать презентации хорошо, быстро и круто — шпаргалка

Это выжимка из поиска в интернете (ноябрь 2026). Каждый пункт уже работает в тулките: `tools/check.py` проверяет его автоматически, либо по нему собрана практическая презентация.

## 1. Одна мысль — один слайд
- На каждом слайде одна главная мысль. Заголовок — это и есть эта мысль. Если в заголовке появилось «и», слайд пора делить на два ([presenti.ai](https://presenti.ai/blog/ppt-designer-tips/), [presentations.ai](https://www.presentations.ai/blog/presentation-design-best-practices)).
- Правила 4×4, 5×5 и 7×7 — это потолок, а не цель. Лучше меньше слов и одна сильная картинка ([presentations.ai](https://www.presentations.ai/blog/presentation-design-best-practices)).
- Тест «прищурься»: отойдите от экрана и прищурьтесь. Первым должен бросаться в глаза главный элемент слайда. Если это не так, перестройте иерархию ([presentations.ai](https://www.presentations.ai/blog/presentation-design-best-practices)).

## 2. Иерархия: размер, жирность, цвет, воздух
- Самое важное — самое крупное.
- На блок текста выделяем жирным одну фразу.
- Акцентный цвет только на одном главном элементе.
- Свободное место тоже работает: элемент с запасом пространства вокруг выглядит важнее ([presenti.ai](https://presenti.ai/blog/ppt-designer-tips/)).
- Два шрифта, три цвета, одинаковые поля ([presenti.ai](https://presenti.ai/blog/ppt-designer-tips/)).
- Правило 10-20-30 (10 слайдов, 20 минут, шрифт от 30 pt) хорошо помогает держать фокус ([ai-media-studio](https://www.ai-media-studio.com/blog/presentation-design-tips)).

## 3. Для детей
- Минимум текста. Рассказывает учитель, а слайд показывает: на нём одна большая картинка.
- Подпись ставим под картинкой, а не поверх неё.
- Не больше 4–5 объектов на слайде ([nsportal: памятка](https://nsportal.ru/detskiy-sad/raznoe/2021/03/14/pamyatka-pravila-sozdaniya-prezentatsii-dlya-detey)).
- Шрифт крупный: заголовки от 24–32 pt, текст от 22–24 pt.
- Не смешиваем много шрифтов. Светлый текст на тёмном фоне и наоборот ([nsportal](https://nsportal.ru/detskii-sad/vospitatelnaya-rabota/2019/10/06/pravila-sozdaniya-prezentatsii-dlya-detey), [atschool](https://atschool.com.ua/ru/kak-sdelat-prezentaciyu-dlya-shkoly-v-canva/)).
- Картинки чёткие и крупные: 50–70 % слайда. Фон светлый, яркие цвета только для акцентов ([presentaciumblog](https://presentaciumblog.ru/kak-sdelat-prezentacziyu-dlya-detej-yarkie-czveta-bolshie-kartinki-i-prostoj-tekst/)).
- Маленькую картинку нельзя растягивать на весь слайд. Рисунки и фото не смешиваем, всё делаем в одном стиле ([nsportal](https://nsportal.ru/detskiy-sad/raznoe/2017/10/27/zolotoe-pravilo-lyuboy-prezentatsii)).
- Подаём материал историей с героем. Дети должны участвовать: вопросы, викторина ([nsportal](https://nsportal.ru/detskiy-sad/raznoe/2017/10/27/zolotoe-pravilo-lyuboy-prezentatsii)).
- Анимации простые: появление и выезд. Никаких вращений и «прыжков» ([masterrvdesigners](https://www.masterrvdesigners.com/blog/top-presentation-design-ideas/)).

## 4. Как это применено в «Как появилась Древняя Греция»
| Принцип | Как сделано |
|---|---|
| Один слайд — одна мысль | 20 слайдов: крючок → география → лента времени → эпохи по одной → викторина → итоги |
| Большая картинка | 10 иллюстраций в одном стиле на весь слайд, 2 настоящих фото в рамке с подписью снизу |
| Герой | Совёнок Афи (птица богини Афины) комментирует каждый слайд |
| Иерархия | Заголовок Nunito Black 34–60 pt, текст Nunito, акценты терракотой, остальное приглушено |
| Палитра | Синий Эгейского моря, терракота, золото, крем: 3 основных цвета + 2 акцента |
| Участие | 3 вопроса викторины с кликом (✓/✗ и объяснение), вопрос для обсуждения в конце |
| Читаемость | Проверка `check.py`: контраст ≥ 3:1, шрифт ≥ 14 pt, нет переполнений и выходов за край |
| Телефон | HTML-версия: на узком экране отдельная вертикальная раскладка, свайпы, увеличение карт |

## 5. Быстрый рабочий цикл
1. `python tools/analyze.py deck.pptx` — структура за ~0,2 с: слайды, фигуры, шрифты, картинки, dpi.
2. `python tools/check.py deck.pptx` — скриншоты всех слайдов, контакт-лист и список проблем с подсказками.
3. `python tools/edit.py deck.pptx --do "…" -o deck_v2.pptx` — правки и картинки «до/после/разница».
4. Повторить шаг 2 до «✅ Проблем не найдено».
5. `python tools/pptx2html.py deck_v2.pptx` — версия для телефона.
