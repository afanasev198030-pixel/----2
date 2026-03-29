Создай второй экран для системы цифрового брокера:
экран полной декларации в режиме read-only with targeted correction.

Главная идея

Это не экран тотальной проверки всех полей и не обычная большая editable-форма.
Это экран, где пользователь открывает уже собранную и почти готовую декларацию, чтобы:
 • быстро просмотреть полный состав данных,
 • при необходимости открыть источник конкретного поля,
 • точечно скорректировать только отдельные значения,
 • не перегружаться постоянными input-полями,
 • сохранять ощущение, что документ уже готов, а не требует ручного заполнения.

UX-принцип:
read first, edit second

Интерфейс должен транслировать:
 • декларация уже собрана системой,
 • все поля по умолчанию отображаются как готовый результат,
 • редактирование включается только по действию пользователя,
 • источник данных доступен по клику,
 • проблемные поля выделены, но не доминируют,
 • основная структура спокойная, плотная, enterprise-level.

⸻

Что это за экран

Это secondary screen, который открывается из ready-to-send dashboard.
Он нужен для:
 • полной визуальной сверки декларации,
 • точечных правок,
 • просмотра источников,
 • работы со сложными или нестандартными кейсами,
 • аудита и контроля.

Это не должен быть основной экран первого сценария.

⸻

Layout

Сделай desktop screen 1440–1600 px.

Структура экрана:
 1. Sticky top header
 2. Compact page summary bar
 3. Main layout with 3 areas
 • left: section navigation / quick filters
 • center: full declaration content
 • right: contextual source / edit panel
 4. Sticky bottom action bar

⸻

1. Sticky top header

Сделай спокойный enterprise header.

Слева:
 • back button to dashboard
 • page title: Полная декларация
 • case id: DC-2026-001245

По центру:
 • small overall status badge:
 • Готово к отправке
 • или Есть замечания
 • last updated timestamp

Справа:

actions:
 • Назад к обзору
 • PDF
 • XML
 • Подписать ЭЦП
 • Отправить

Важно:
даже на экране полной декларации пользователь должен чувствовать, что это часть release flow, а не отдельный хаотичный редактор.

⸻

2. Compact summary bar under header

Сразу под header добавь компактную summary strip.

Покажи:
 • Заполнено 148/148
 • Критических ошибок 0
 • Предупреждений 2
 • Ручных изменений 3
 • Документы 5
 • XML готов

Добавь быстрые action pills:
 • Показать только проблемные поля
 • Показать ручные изменения
 • Показать только пустые
 • Перейти к следующему замечанию

Эта панель должна быть компактной и полезной для быстрого navigation workflow.

⸻

3. Left panel — navigation and filters

Слева сделай узкую вертикальную панель шириной около 250–280 px.

Верх панели:

title: Навигация

Ниже:

Список секций декларации:
 • Общие сведения
 • Декларант / отправитель / получатель
 • Коммерческие данные
 • Транспорт
 • Финансовые сведения
 • Товарные позиции
 • Документы
 • Дополнительные сведения

У каждой секции покажи:
 • количество полей,
 • число проблемных полей, если есть.

Пример:
 • Общие сведения (12)
 • Коммерческие данные (8) · 1
 • Товарные позиции (12) · 2

Ниже добавь quick filters:
 • Все поля
 • Только проблемные
 • Только ручные
 • Только AI
 • Только пустые

Ниже add a small legend:
 • AI
 • подтверждено
 • ручное
 • предупреждение
 • ошибка
 • конфликт

⸻

4. Center area — full declaration content

Это основная часть экрана.

Очень важно:
не делай страницу как сплошную editable-форму с input-полями.
Сделай ее как читабельную, структурированную, mostly read-only declaration view.

Верх контентной зоны:

controls:
 • toggle: Рабочий вид / Печатная форма
 • search field: Поиск по графам и значениям
 • dropdown filter: Все поля
 • button: Следующее замечание

⸻

5. Structure of declaration

Раздели декларацию на секции в виде accordion/cards.

Каждая секция должна иметь:
 • title,
 • short status summary,
 • grid/list of fields.

Example section header

Коммерческие данные
 • Заполнено 8/8
 • 1 предупреждение
 • 0 ошибок

⸻
6. Field design — core requirement

Каждое поле должно выглядеть как read-only field row/card, а не input по умолчанию.

Base field structure
 • label: Графа 22. Валюта и сумма по счету
 • value: USD 12 540,00
 • metadata row:
 • AI
 • Инвойс
 • стр.1
 • 92%
 • inline actions on the right:
 • source icon
 • edit icon
 • history icon

⸻

7. Field states

Очень важно показать разные типы состояний поля.

A. Normal AI field

Пример:
 • label: Графа 1. Тип декларации
 • value: ИМ 40
 • metadata: AI · Контракт · 98%
 • visual style: clean, neutral, subtle AI badge

B. Review recommended field

Пример:
 • label: Графа 15. Страна отправления
 • value: Китай
 • metadata: AI · Инвойс · 76% · Требует проверки
 • visual style: soft amber accent

C. Conflict field

Пример:
 • label: Графа 22. Валюта и сумма
 • value: USD 12 540,00
 • metadata: Конфликт · 2 источника
 • visual style: warning/conflict style, but still elegant

D. Manual override field

Пример:
 • label: Графа 24. Характер сделки
 • value: 010
 • metadata: Изменено вручную · Пользователь
 • visual style: blue-gray manual change state

E. Empty required field

Пример:
 • label: Графа 20. Условия поставки
 • value: —
 • metadata: Пусто · Обязательное поле
 • inline helper text:
Значение не найдено в текущем комплекте документов
 • CTA:
 • Найти
 • Ввести вручную
 • visual style: clear blocking state

⸻

8. Editing model

Покажи, что редактирование здесь точечное, а не массовое.

По клику на edit icon поле не превращается прямо на месте в огромный input.
Вместо этого справа открывается contextual side panel.

То есть:
 • default = read-only
 • click edit = open side drawer for this field only

⸻

9. Right contextual panel

Справа сделай открытую panel/drawer шириной около 440–500 px.

Пусть она показывает details для выбранного поля:
Графа 22. Валюта и сумма по счету

Panel structure

Header
 • title: Поле декларации
 • selected field name
 • close icon

Current value block
 • value: USD 12 540,00
 • status: Конфликт
 • source count: 2 источника

Main source block
 • invoice_01.pdf
 • Инвойс
 • стр. 1
 • Таблица итогов

Source preview block
Покажи stylized preview card of pdf fragment with highlighted area.

Alternatives block
 • contract_2026.pdf — USD 12 500,00
 • proforma_01.pdf — USD 12 540,00

Why selected block
 • Найдено точное совпадение
 • Значение соответствует валюте документа
 • Есть альтернативный источник с расхождением

Edit actions block
Buttons:
 • Выбрать альтернативу
 • Ввести вручную
 • Исправить источник
 • Заменить документ
 • Повторно извлечь

History block
Timeline:
 • 14:10 AI заполнил значение
 • 14:18 пользователь открыл источник
 • 14:22 значение изменено вручную

⸻

10. Goods section

В центре обязательно покажи секцию Товарные позиции.

Но здесь она должна быть тоже mostly read-only and structured.

Table preview

Columns:
 • №
 • Описание
 • Код ТН ВЭД
 • Кол-во
 • Вес
 • Стоимость
 • Страна
 • Статус

Покажи 3–4 строки:
 • one OK
 • one review required
 • one conflict/manual

По клику на строку справа должен тоже открываться source/edit panel.

⸻

11. Printing view hint

Покажи переключатель:
 • Рабочий вид
 • Печатная форма

Активен Рабочий вид.

Но визуально намекни, что пользователь может перейти в официальный вид декларации для финального просмотра.

⸻

12. Sticky bottom action bar

Внизу добавь sticky action bar.

Покажи:
 • 0 критических ошибок
 • 2 предупреждения
 • 3 ручных изменения

Справа действия:
 • Следующее замечание
 • Показать проблемные
 • Назад к обзору
 • Подписать и отправить

Эта панель должна поддерживать workflow, но не быть слишком тяжелой.

⸻

13. Visual style

Стиль:
 • premium enterprise SaaS
 • light theme
 • soft neutral backgrounds
 • white / very lightly tinted cards
 • subtle borders
 • rounded corners 12–16 px
 • soft shadows
 • compact typography
 • high information density
 • calm hierarchy
 • minimal noise
 • serious B2B tone

Важно:
экран должен выглядеть как готовый документ с возможностью локальной коррекции, а не как хаотичный конструктор формы.

⸻

14. UX feeling to communicate
Пользователь должен почувствовать:
 • декларация уже собрана,
 • система уверена в результате,
 • всё можно быстро просмотреть,
 • редактирование не навязано,
 • исправления делаются только точечно,
 • источники прозрачны и доступны,
 • это профессиональный инструмент высокого уровня автоматизации.

⸻

15. Components to emphasize

Сделай качественно:
 • read-only field cards/rows
 • metadata lines under values
 • section headers with status counts
 • right contextual edit/source panel
 • row states for fields
 • goods table
 • summary strip
 • sticky bottom workflow bar
 • elegant status badges

⸻

16. Final outcome

Сгенерируй один high-fidelity desktop screen:

“Полная декларация”

в режиме:
 • mostly read-only,
 • structured by sections,
 • point correction only,
 • source/details panel open on the right,
 • enterprise release workflow preserved.

Экран должен явно показывать:
 • это вторичный режим после ready-to-send dashboard,
 • полная декларация доступна для контроля,
 • редактирование локальное,
 • вся страница не превращена в input-form.
