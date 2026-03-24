Создай третий экран / компонент для системы цифрового брокера:
Targeted field correction / source resolution drawer
для точечного исправления одного поля декларации.
Главная идея
Это не отдельная полная страница декларации, а контекстный интерфейс локального исправления одного поля.
Он открывается:
из ready-to-send dashboard,
из полной декларации,
из списка исключений,
из товарной позиции.
Назначение:
показать текущее значение поля,
показать, откуда система его взяла,
показать альтернативные варианты,
дать возможность быстро выбрать другой источник,
ввести значение вручную,
исправить источник,
заменить документ,
сохранить историю изменений.
Это должен быть очень аккуратный, точный, explainable, enterprise drawer/modal, который поддерживает идею:
исправляем только одно исключение, а не редактируем всю декларацию.
Формат компонента
Сделай desktop right-side drawer или large contextual modal.
Предпочтительный вариант: right drawer, ширина 440–520 px.
Экран должен ощущаться как:
focused problem-solving interface,
high-trust correction tool,
локальная операция внутри общего release workflow.
Сценарий
Пользователь открыл проблемное поле:
Графа 22. Валюта и сумма по счету
Система предлагает текущее значение:
USD 12 540,00
Но поле имеет статус:
конфликт,
или низкая уверенность,
или отсутствует значение,
или пользователь хочет вручную скорректировать поле.
Drawer должен помочь быстро принять решение без ухода в сложный поток.
Layout
Структура drawer:
Header
Current field state
Main source
Source preview
Alternative values
Why the value was selected
Correction actions
Change history
Sticky footer actions
1. Header
Верхняя часть drawer:
title: Поле декларации
field name: Графа 22. Валюта и сумма по счету
close icon
Дополнительно можно показать small breadcrumb:
Декларация / Коммерческие данные / Графа 22
Header должен быть compact and premium.
2. Current field state block
Первый блок должен четко показать:
текущее значение,
статус,
тип происхождения,
confidence / issue level.
Пример:
current value: USD 12 540,00
status badge: Конфликт
source count: 2 источника
confidence: 92%
Или другой вариант состояния:
Требует проверки
Низкая уверенность
Пусто
Изменено вручную
Этот блок должен быть very clear and easy to scan.
3. Main source block
Покажи, откуда система взяла текущее значение.
Состав блока:
document name: invoice_01.pdf
document type: Инвойс
page: 1
location: Таблица итогов
extraction type: AI extracted
Можно добавить small metadata:
Источник выбран автоматически
Совпадение по формату и контексту
4. Source preview block
Это один из ключевых UX-элементов.
Сделай stylized preview card:
mockup page fragment of a PDF or scanned document
highlighted rectangle around the extracted value
small zoom controls / open document action
Важно показать:
конкретный участок документа,
что именно было извлечено,
визуальную связь между документом и полем.
Пусть preview выглядит clean, elegant, and contextual.
Можно добавить small link/button:
Открыть документ полностью
5. Alternative values block
Покажи, что система нашла альтернативы.
Сделай отдельный блок:
Альтернативные значения
Примеры:
contract_2026.pdf — USD 12 500,00
proforma_01.pdf — USD 12 540,00
История клиента — USD 12 540,00
Для каждой альтернативы покажи:
source name
value
small helper text:
Контракт
Предварительный документ
Историческое значение
button or radio control:
Выбрать
Одна из альтернатив может быть marked as recommended.
6. Why selected block
Добавь explainability block:
Почему выбрано это значение
Покажи 3–4 bullet points, например:
Найдено точное совпадение в итоговом блоке инвойса
Значение соответствует валюте документа
Формат совпадает с ожидаемым для поля
Обнаружен альтернативный источник с расхождением
Этот блок должен быть коротким, понятным, не overly technical.
7. Correction actions block
Это самый важный рабочий блок.
Сделай четкую группу действий:
Main correction options:
Выбрать альтернативу
Ввести вручную
Исправить источник
Заменить документ
Повторно извлечь
Можно визуально разделить действия по типам:
change value,
change source,
rerun extraction.
8. Manual input state
Покажи внутри drawer подблок/таб для ручного ввода.
Пример:
Ввести вручную
input field with current/new value
optional reason field:
Причина изменения
helper text:
Поле будет отмечено как измененное вручную
Buttons:
Применить
Отмена
Важно показать, что manual override — это controlled action with audit trail.
9. Change source state
Покажи подблок для выбора другого источника.
Например:
Исправить источник
Options:
выбрать другой найденный источник;
отметить другой фрагмент документа;
выбрать другой документ;
заменить текущий файл новой версией.
Можно показать compact list:
Использовать контракт
Использовать проформу
Загрузить новую версию инвойса
10. Replace document action
Добавь небольшой upload / replace pattern.
Например:
Заменить документ
current file: invoice_01.pdf
action: Upload new version
helper text:
После замены система может пересчитать связанные поля
Это особенно важно для сценария “исправить причину, а не только значение”.
11. Change history block
Внизу drawer сделай mini timeline:
История изменений
Пример:
14:10 — AI заполнил значение из invoice_01.pdf
14:18 — пользователь открыл источник
14:22 — пользователь выбрал альтернативу из contract_2026.pdf
14:23 — поле обновлено
История должна выглядеть audit-friendly and compact.
12. Sticky footer
Внизу drawer сделай sticky footer с основными действиями.
Варианты кнопок:
Primary:
Применить изменение
Secondary:
Сбросить к AI
Отмена
Если состояние conflict resolution:
primary button can be Выбрать и применить
Если состояние manual entry:
primary button can be Сохранить вручную
Footer должен быть clear and workflow-focused.
13. Visual style
Стиль:
premium enterprise SaaS
light theme
calm, high-trust, professional
soft background
white cards / layered panels
subtle borders
soft shadows
rounded corners 12–16 px
compact typography
precise spacing
strong visual hierarchy
no playful visuals
Status colors:
conflict: amber/red mix but elegant
warning: soft amber
manual: blue-gray
AI/default: soft accent
success: subtle green
Drawer должен выглядеть как серьезный инструмент принятия решения по одному полю.
14. UX feeling
Пользователь должен почувствовать:
я решаю одну конкретную проблему,
мне прозрачно показано, откуда взялось значение,
я могу быстро исправить поле,
я могу исправить не только значение, но и причину ошибки,
правка локальна и безопасна,
история будет сохранена.
15. Components to emphasize
Особенно качественно проработай:
current value/status block
source preview card with highlight
alternative value rows
explainability bullets
correction action group
manual override mini-form
source replacement pattern
audit timeline
sticky footer CTA
16. Final outcome
Сгенерируй один polished high-fidelity drawer/modal screen для сценария:
“Точечное исправление поля / выбор источника”
Компонент должен быть готов для использования:
из ready-to-send dashboard,
из полной декларации,
из списка исключений,
из карточки товарной позиции.
Он должен визуально и функционально поддерживать общую концепцию:
AI заполняет почти всё сам, пользователь исправляет только исключения.