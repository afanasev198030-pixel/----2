import asyncio
from collections import defaultdict
from typing import Dict, List, Tuple, Optional
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services import CoreApiClient, FileServiceClient, AiServiceClient


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Handle /start command with clear onboarding."""
    builder = InlineKeyboardBuilder()
    builder.button(text="🌐 Открыть веб-версию", url="http://141.105.65.148/")
    builder.button(text="📖 Инструкция", callback_data="show_instructions")
    
    await message.answer(
        "👋 **Добро пожаловать в Digital Broker Bot!**\n\n"
        "Я помогу вам с таможенным оформлением:\n"
        "• Автоматически обрабатывать документы\n"
        "• Заполнять декларации\n"
        "• Подбирать коды ТН ВЭД\n"
        "• Отвечать на вопросы по оформлению\n\n"
        "Чтобы начать — привяжите ваш аккаунт:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )


@router.callback_query(F.data == "show_instructions")
async def show_instructions(callback: CallbackQuery):
    """Show detailed instructions."""
    await callback.message.edit_text(
        "🔑 **Как привязать аккаунт к боту:**\n\n"
        "1. Перейдите по кнопке ниже в веб-версию\n"
        "2. Зайдите в **Настройки → Telegram**\n"
        "3. Нажмите кнопку **«Сгенерировать токен для бота»**\n"
        "4. Скопируйте токен\n"
        "5. Вернитесь сюда и отправьте токен в чат\n\n"
        "После этого я сразу вас подключу и вы сможете использовать все функции.",
        parse_mode="Markdown"
    )
    await callback.answer("Инструкция показана")

router = Router()
core_api = CoreApiClient()
file_service = FileServiceClient()
ai_service = AiServiceClient()

_user_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)
_pending_files: Dict[int, List[Tuple[bytes, str, str]]] = {}
_summary_tasks: Dict[int, asyncio.Task] = {}
_status_messages: Dict[int, Message] = {}

DEBOUNCE_SECONDS = 2.5


class UploadState(StatesGroup):
    collecting_files = State()


def _done_keyboard(count: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"✅ Начать AI-парсинг ({count} файл(ов))",
            callback_data="start_parsing",
        )
    ]])


async def _send_summary(uid: int, state: FSMContext):
    """Debounced: send/update the single summary message after all files arrive."""
    status_msg = _status_messages.get(uid)
    if not status_msg:
        return

    state_data = await state.get_data()
    declaration_id = state_data.get("declaration_id", "")
    filenames = state_data.get("filenames", [])
    count = len(filenames)

    if count == 0:
        return

    file_list = "\n".join(f"  📄 {fn}" for fn in filenames)
    text = (
        f"📋 Декларация: ...{declaration_id[-8:]}\n\n"
        f"Загружено файлов: {count}\n{file_list}\n\n"
        "Нажмите кнопку, когда все файлы загружены:"
    )

    try:
        await status_msg.edit_text(text, reply_markup=_done_keyboard(count))
    except Exception:
        pass


async def _schedule_summary(uid: int, state: FSMContext):
    """Cancel previous debounce timer and start a new one."""
    old_task = _summary_tasks.pop(uid, None)
    if old_task and not old_task.done():
        old_task.cancel()

    async def _delayed():
        await asyncio.sleep(DEBOUNCE_SECONDS)
        await _send_summary(uid, state)

    _summary_tasks[uid] = asyncio.create_task(_delayed())


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    args = message.text.split()
    if len(args) > 1:
        token = args[1]
        success = await core_api.link_account(token, str(message.from_user.id))
        if success:
            await message.answer(
                "✅ Аккаунт успешно привязан!\n"
                "Теперь вы можете отправлять мне документы (PDF, Excel) для создания деклараций.\n"
                "Отправьте все файлы, затем нажмите «Начать AI-парсинг»."
            )
        else:
            await message.answer("❌ Ошибка привязки. Возможно, ссылка устарела.")
    else:
        user = await core_api.get_user(str(message.from_user.id))
        if user:
            await message.answer(
                f"Привет, {user.get('full_name', 'Пользователь')}! Я бот Digital Broker.\n\n"
                "📎 Отправьте документы (PDF, Excel) — можно несколько сразу.\n"
                "После загрузки нажмите кнопку «Начать AI-парсинг».\n"
                "Все файлы попадут в одну декларацию."
            )
        else:
            await message.answer(
                "Привет! Я бот Digital Broker.\n"
                "Пожалуйста, привяжите свой аккаунт через веб-интерфейс."
            )


@router.message(F.document)
async def handle_document(message: Message, bot: Bot, state: FSMContext):
    user = await core_api.get_user(str(message.from_user.id))
    if not user:
        await message.answer("Сначала привяжите аккаунт через веб-интерфейс.")
        return

    doc = message.document

    await core_api.log_action(
        user["id"], "telegram_document_received",
        {"filename": doc.file_name, "mime_type": doc.mime_type},
    )

    if not doc.file_name.lower().endswith(('.pdf', '.xls', '.xlsx')):
        await message.answer("Пожалуйста, отправьте PDF или Excel файл.")
        return

    uid = message.from_user.id

    file_info = await bot.get_file(doc.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    file_bytes = downloaded_file.read()

    content_type = (
        "application/pdf"
        if doc.file_name.lower().endswith('.pdf')
        else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    file_key = await file_service.upload_file(file_bytes, doc.file_name, content_type)
    if not file_key:
        await message.answer(f"❌ Ошибка при загрузке {doc.file_name}.")
        return

    async with _user_locks[uid]:
        state_data = await state.get_data()
        declaration_id = state_data.get("declaration_id")
        filenames = state_data.get("filenames", [])

        if not declaration_id:
            declaration_id = await core_api.create_declaration(user["id"], user["company_id"])
            if not declaration_id:
                await message.answer("❌ Ошибка при создании декларации.")
                return

        attached = await core_api.attach_document(user["id"], declaration_id, file_key, doc.file_name)
        if not attached:
            await message.answer(f"❌ Ошибка при прикреплении {doc.file_name}.")
            return

        if uid not in _pending_files:
            _pending_files[uid] = []
        _pending_files[uid].append((file_bytes, doc.file_name, content_type))

        filenames.append(doc.file_name)

        await state.set_state(UploadState.collecting_files)
        await state.update_data(
            declaration_id=declaration_id,
            user_id=user["id"],
            filenames=filenames,
        )

        count = len(filenames)

        if uid not in _status_messages:
            status_msg = await message.answer(f"⏳ Получаю файлы... ({count})")
            _status_messages[uid] = status_msg
        else:
            try:
                await _status_messages[uid].edit_text(f"⏳ Получаю файлы... ({count})")
            except Exception:
                pass

        await _schedule_summary(uid, state)


@router.callback_query(F.data == "start_parsing")
async def on_start_parsing(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()

    state_data = await state.get_data()
    declaration_id = state_data.get("declaration_id")
    filenames = state_data.get("filenames", [])

    uid = callback.from_user.id

    old_task = _summary_tasks.pop(uid, None)
    if old_task and not old_task.done():
        old_task.cancel()
    _status_messages.pop(uid, None)

    files_to_parse = _pending_files.pop(uid, [])

    if not declaration_id or not files_to_parse:
        await callback.message.edit_text("❌ Нет файлов для парсинга. Отправьте документы заново.")
        await state.clear()
        return

    file_list = "\n".join(f"  📄 {fn}" for fn in filenames)
    await callback.message.edit_text(
        f"⏳ AI-парсинг {len(files_to_parse)} файл(ов)...\n\n{file_list}\n\n"
        "Это может занять 1–3 минуты."
    )

    user_id = state_data.get("user_id")
    await state.clear()

    parsed_data = await ai_service.parse_smart_batch(declaration_id, files_to_parse)

    if not parsed_data:
        await callback.message.edit_text(
            "⚠️ AI-парсинг завершился с ошибкой.\n"
            "Декларация и документы сохранены — попробуйте парсинг из веб-интерфейса."
        )
        return

    applied = await core_api.apply_parsed(user_id, declaration_id, parsed_data)

    items_count = len(parsed_data.get("items", []))
    confidence = parsed_data.get("confidence", 0)

    if applied:
        await callback.message.edit_text(
            f"✅ Декларация заполнена!\n\n"
            f"📋 Декларация: ...{declaration_id[-8:]}\n"
            f"📄 Файлов: {len(files_to_parse)}\n"
            f"📦 Товарных позиций: {items_count}\n"
            f"🎯 Уверенность AI: {confidence:.0%}\n\n"
            "Проверьте и отредактируйте в веб-интерфейсе."
        )
    else:
        await callback.message.edit_text(
            f"⚠️ Парсинг прошёл (позиций: {items_count}), но не удалось сохранить.\n"
            "Попробуйте применить парсинг из веб-интерфейса."
        )


@router.message(F.text, UploadState.collecting_files)
async def handle_text_during_upload(message: Message, state: FSMContext):
    state_data = await state.get_data()
    count = len(state_data.get("filenames", []))
    await message.answer(
        f"Вы загружаете документы ({count} файл(ов)).\n"
        "Отправьте ещё файлы или нажмите кнопку «Начать AI-парсинг» выше.",
    )


@router.message(F.text)
async def handle_text(message: Message):
    telegram_id = str(message.from_user.id)
    user = await core_api.get_user(telegram_id)

    if not user:
        await message.answer(
            "👋 **Добро пожаловать в Digital Broker Bot!**\n\n"
            "Чтобы начать использовать бота, нужно привязать ваш аккаунт.\n\n"
            "🔑 **Как это сделать:**\n"
            "1. Зайдите в веб-версию → Настройки → Telegram\n"
            "2. Нажмите кнопку «Сгенерировать токен для бота»\n"
            "3. Скопируйте токен\n"
            "4. Отправьте его мне в этом чате\n\n"
            "📌 Отправьте токен сейчас, и я сразу вас подключу.",
            parse_mode="Markdown"
        )
        return

    await core_api.log_action(user["id"], "telegram_message_received", {"text": message.text})

    msg = await message.answer("⏳ Думаю...")

    session_id = str(message.from_user.id)

    response = await ai_service.chat(
        user_id=user["id"],
        message=message.text,
        session_id=session_id,
    )

    await core_api.log_action(user["id"], "telegram_bot_replied", {"text": response})

    await msg.edit_text(response)


@router.message(F.text.startswith(("sk-", "token-")))
async def handle_auth_token(message: Message):
    """Handle authentication token sent by user."""
    token = message.text.strip()
    telegram_id = str(message.from_user.id)
    
    await core_api.log_action(telegram_id, "telegram_token_received", {"token_length": len(token)})
    
    success = await core_api.link_account(token, telegram_id)
    
    if success:
        await message.answer(
            "✅ **Аккаунт успешно привязан!**\n\n"
            "Теперь вы можете использовать бота:\n"
            "• Отправляйте документы (PDF, Excel) — я их обработаю\n"
            "• Спрашивайте статус ваших деклараций\n"
            "• Задавайте вопросы по ТН ВЭД и правилам\n\n"
            "Просто пишите сообщения или отправляйте файлы.",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            "❌ **Не удалось привязать аккаунт.**\n\n"
            "Возможно токен уже использован или истёк.\n"
            "Пожалуйста, сгенерируйте новый токен в веб-интерфейсе:\n"
            "Настройки → Telegram → «Сгенерировать токен»",
            parse_mode="Markdown"
        )
