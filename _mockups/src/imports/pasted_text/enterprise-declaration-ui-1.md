Создай desktop UI экрана enterprise-системы цифрового брокера для работы с таможенной декларацией.
Стиль интерфейса: modern enterprise, premium, clean, high-density, professional, AI-assisted workflow.
Экран должен выглядеть как рабочее место специалиста по проверке автозаполненной декларации, а не как обычная форма.
Общая идея экрана
Пользователь загрузил комплект документов.
Система распознала документы, извлекла данные и автоматически заполнила поля декларации.
Теперь пользователь должен:
увидеть результат заполнения,
посмотреть источник каждого значения,
проверить спорные поля,
исправить ошибки,
увидеть недостающие документы,
пройти чек-лист готовности,
выгрузить PDF/XML,
подписать ЭЦП,
отправить декларацию в таможню.
Layout
Сделай desktop-first layout, ширина 1440–1600 px.
Структура экрана:
Sticky top header
Left sidebar with documents
Center workspace with declaration
Right contextual panel with source details
Sticky bottom review bar
1. Sticky top header
Верхняя панель должна выглядеть статусно и по-enterprise.
Слева:
Back button
Case ID: DC-2026-001245
Client: ООО Альфа Импорт
По центру:
Status badge: Требует проверки
Last update timestamp
Progress metrics:
Заполнено 132/148
Требует проверки 6
Ошибки 2
Документы отсутствуют 1
Справа:
Primary and secondary actions:
Проверить
PDF
XML
Подписать ЭЦП
Отправить
Кнопки должны выглядеть enterprise-level: clean, compact, modern, slightly rounded, not playful.
2. Left sidebar — documents
Слева сделай фиксированную боковую панель шириной около 300 px.
Header панели:
title: Документы
search field
small filter chips:
Все
Использованные
Проблемные
Отсутствуют
Ниже список документов в виде compact cards/list items.
Примеры карточек:
document item 1
invoice_01.pdf
type: Инвойс
status: Распознан
helper text: Используется в 12 полях
small action icons
document item 2
contract_2026.pdf
type: Контракт
status: Распознан
helper text: Используется в 7 полях
document item 3
packing_list.pdf
type: Упаковочный лист
status: Частично распознан
helper text: 1 сомнительный фрагмент
document item 4
Сертификат происхождения
status: Отсутствует
CTA: Загрузить
Сделай хороший визуальный язык для статусов документов:
recognized
partially recognized
missing
warning
problematic
3. Center workspace
Это главная часть экрана.
Сверху внутри workspace добавь tabs:
Обзор
Декларация
Товарные позиции
Документы и требования
Проверки
История
Активная вкладка: Декларация
Под tabs добавь secondary toolbar:
toggle: Рабочий вид / Печатная форма
search field: Поиск по графам и значениям
filter dropdown: Все поля
button: Следующее проблемное поле
4. Declaration content
Главная область должна отображать декларацию в виде структурированных секций, а не как длинный бланк.
Сделай 3–4 раскрытые секции.
Section 1: Общие сведения
Header секции:
title Общие сведения
mini status summary:
Заполнено 10/12
На проверке 1
Ошибки 1
Внутри секции размести field cards в two-column grid.
Example field card 1
label: Графа 1. Тип декларации
value: ИМ 40
metadata row: AI · Документ: контракт · 98% · Подтверждено
actions:
source icon
edit icon
history icon
Example field card 2
label: Графа 15. Страна отправления
value: Китай
metadata row: AI · Инвойс · стр.1 · 76% · Требует проверки
should have warning accent
Example field card 3
label: Графа 22. Валюта и сумма по счету
value: USD 12 540,00
metadata row: AI · Инвойс · стр.1 · 92% · Конфликт
should have conflict state
Example field card 4
label: Графа 24. Характер сделки
value: 010
metadata row: Введено вручную · Пользователь
manual state
Section 2: Декларант / отправитель / получатель
Покажи 4–6 полей:
Декларант
Отправитель
Получатель
ИНН / реквизиты
Адрес
Сделай mix of statuses:
some confirmed
one requiring review
one manually updated
Section 3: Коммерческие данные
Поля:
номер инвойса
дата инвойса
номер контракта
условия поставки
валюта
общая стоимость
Одно поле должно быть в error state:
empty required field
show inline message and CTA
Example:
Графа 20. Условия поставки
Value empty
Badges: Пусто · Обязательное поле
Inline text: Значение не найдено в текущем комплекте документов
Buttons: Найти в документах, Ввести вручную
Section 4: Товарные позиции preview
В центральной зоне покажи preview таблицы товарных позиций.
Columns:
№
Описание
Код ТН ВЭД
Кол-во
Вес
Стоимость
Страна
Статус
2–3 строки.
Statuses:
one row На проверке
one row ОК
one row Конфликт
5. Right contextual panel — source of field
Справа сделай открытую contextual panel шириной примерно 460 px.
Она должна показывать детали по выбранному полю: Графа 22. Валюта и сумма по счету
Структура панели:
Header
title: Источник значения
selected field name
close icon
Current value block
current value: USD 12 540,00
status: Требует проверки
type: AI
confidence: 92%
Main source block
document: invoice_01.pdf
type: Инвойс
page: 1
location: Таблица итогов
Document preview block
Сделай preview card со stylized pdf fragment preview.
Нужно показать page mockup с highlighted rectangle where value was extracted.
Why selected block
Bullets:
Найдено прямое совпадение в итоговом блоке инвойса
Формат соответствует ожидаемому
Совпадает с валютой документа
Alternatives block
List 2–3 alternatives:
contract_2026.pdf — USD 12 500,00
proforma_01.pdf — USD 12 540,00
История клиента — USD 12 540,00
Actions block
Buttons:
Подтвердить
Выбрать альтернативу
Ввести вручную
Заменить документ
Повторно извлечь
History block
Timeline:
14:10 AI заполнил значение
14:18 пользователь открыл источник
14:22 значение было изменено вручную
Панель должна выглядеть информационно насыщенно, но очень аккуратно.
6. Sticky bottom review bar
Внизу экрана добавь sticky summary bar.
Содержимое:
2 критические ошибки
4 требуют подтверждения
1 отсутствует документ
7 ручных изменений
Справа кнопки:
Показать только ошибки
Только ручные
Только конфликты
Следующее проблемное поле
Бар должен быть тонким, современным, заметным, но не тяжелым.
7. Visual style
Очень важно: интерфейс должен быть дорогим, современным, чистым, спокойным, enterprise SaaS.
Используй:
soft neutral background
white or lightly tinted cards
subtle borders
rounded corners 14–18 px
soft shadows
high information density
compact typography
premium spacing system
clean iconography
minimal noise
Нужна отдельная визуальная логика для AI-состояний:
AI fields: soft accent badge
needs review: amber
error: red
manual change: blue/gray
confirmed: green or neutral success style
conflict: distinct warning/conflict style
Не делай интерфейс слишком ярким или consumer-like.
Это должен быть профессиональный B2B продукт для таможенной и логистической работы.
8. UX quality requirements
Интерфейс должен сразу транслировать:
доверие,
контроль,
прослеживаемость,
объяснимость AI,
юридическую значимость процесса.
Пользователь должен сразу понимать:
какие поля заполнил AI,
насколько AI уверен,
откуда значение было взято,
какие поля нужно проверить,
что блокирует отправку.
9. Components to emphasize
Особенно качественно проработай:
field card states
document list items
status badges
right source drawer
progress indicators
sticky action bars
goods table rows
inline validation messages
action buttons hierarchy
10. Final outcome
Сгенерируй один complete high-fidelity screen:
desktop dashboard-style page,
active tab Декларация,
left documents sidebar,
center declaration sections with multiple field states,
right source details panel open,
bottom review bar visible.
Экран должен быть готов как основа для enterprise design system и дальнейшего UX проектирования.