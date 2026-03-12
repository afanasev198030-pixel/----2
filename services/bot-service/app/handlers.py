import io
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.services import CoreApiClient, FileServiceClient, AiServiceClient

router = Router()
core_api = CoreApiClient()
file_service = FileServiceClient()
ai_service = AiServiceClient()

class UploadState(StatesGroup):
    waiting_for_files = State()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    args = message.text.split()
    if len(args) > 1:
        token = args[1]
        success = await core_api.link_account(token, str(message.from_user.id))
        if success:
            await message.answer("✅ Аккаунт успешно привязан! Теперь вы можете отправлять мне документы (PDF, Excel) для создания деклараций.")
        else:
            await message.answer("❌ Ошибка привязки. Возможно, ссылка устарела.")
    else:
        user = await core_api.get_user(str(message.from_user.id))
        if user:
            await message.answer(f"Привет, {user.get('full_name', 'Пользователь')}! Я бот Digital Broker.\nОтправьте мне документы (PDF, Excel) для парсинга.")
        else:
            await message.answer("Привет! Я бот Digital Broker. Пожалуйста, привяжите свой аккаунт через веб-интерфейс.")

@router.message(F.document)
async def handle_document(message: Message, bot: Bot):
    user = await core_api.get_user(str(message.from_user.id))
    if not user:
        await message.answer("Сначала привяжите аккаунт через веб-интерфейс.")
        return

    doc = message.document
    
    # Log user action
    await core_api.log_action(user["id"], "telegram_document_received", {"filename": doc.file_name, "mime_type": doc.mime_type})

    if not doc.file_name.lower().endswith(('.pdf', '.xls', '.xlsx')):
        await message.answer("Пожалуйста, отправьте PDF или Excel файл.")
        return

    msg = await message.answer("⏳ Скачиваю документ...")
    
    # Download file
    file_info = await bot.get_file(doc.file_id)
    downloaded_file = await bot.download_file(file_info.file_path)
    file_bytes = downloaded_file.read()
    
    await msg.edit_text("⏳ Загружаю в хранилище...")
    
    # Upload to file-service
    content_type = "application/pdf" if doc.file_name.lower().endswith('.pdf') else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    file_id = await file_service.upload_file(file_bytes, doc.file_name, content_type)
    
    if not file_id:
        await msg.edit_text("❌ Ошибка при загрузке файла.")
        return
        
    await msg.edit_text("⏳ Создаю черновик декларации...")
    
    # Create declaration
    declaration_id = await core_api.create_declaration(user["id"], user["company_id"])
    if not declaration_id:
        await msg.edit_text("❌ Ошибка при создании декларации.")
        return
        
    # Attach document
    await core_api.attach_document(user["id"], declaration_id, file_id, doc.file_name)
    
    await msg.edit_text("⏳ Запускаю AI-парсинг...")
    
    # Trigger smart parsing
    # We do this asynchronously to not block the bot
    import asyncio
    asyncio.create_task(ai_service.parse_smart(declaration_id, [file_id]))
    
    await msg.edit_text(f"✅ Документ принят в работу!\nДекларация создана. AI уже извлекает данные.\nВы можете проверить результат в веб-интерфейсе.")

@router.message(F.text)
async def handle_text(message: Message):
    user = await core_api.get_user(str(message.from_user.id))
    if not user:
        await message.answer("Сначала привяжите аккаунт через веб-интерфейс.")
        return

    # Log user action
    await core_api.log_action(user["id"], "telegram_message_received", {"text": message.text})

    msg = await message.answer("⏳ Думаю...")
    
    # Session ID is just the user's telegram ID for simplicity
    session_id = str(message.from_user.id)
    
    response = await ai_service.chat(
        user_id=user["id"],
        message=message.text,
        session_id=session_id
    )
    
    # Log bot response
    await core_api.log_action(user["id"], "telegram_bot_replied", {"text": response})
    
    await msg.edit_text(response)
