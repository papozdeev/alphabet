import html
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ChatMemberAdministrator, ChatMemberOwner
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import Command

import database as db
from keyboards import get_admin_main_kb, get_cancel_kb, get_review_kb
from config import ADMIN_IDS, ADMIN_USERNAMES

router = Router()

class AdminSettingsState(StatesGroup):
    waiting_for_reviewer = State()
    waiting_for_group_id = State()
    waiting_for_group_name = State()

async def get_admin_dashboard_text(bot: Bot) -> str:
    reviewer_id_str = await db.get_setting("reviewer_id", "Не назначен")
    group_id_str = await db.get_setting("group_id", "Не настроена")
    group_name = await db.get_setting("group_name", "алфавит")

    reviewer_info = reviewer_id_str
    if reviewer_id_str.isdigit():
        try:
            chat = await bot.get_chat(int(reviewer_id_str))
            mention = f"@{chat.username}" if chat.username else chat.full_name
            reviewer_info = f"{reviewer_id_str} ({mention})"
        except Exception:
            reviewer_info = f"{reviewer_id_str}"

    group_info = group_id_str
    if (group_id_str.startswith("-") and group_id_str[1:].isdigit()) or group_id_str.isdigit():
        try:
            gchat = await bot.get_chat(int(group_id_str))
            group_info = f"{group_id_str} («{gchat.title}»)"
        except Exception:
            group_info = f"{group_id_str}"

    stats = await db.get_stats()
    usernames_str = ", ".join([f"@{u}" for u in ADMIN_USERNAMES]) if ADMIN_USERNAMES else "Не указаны"

    text = (
        f"⚙️ <b>Панель управления менеджером группы</b>\n\n"
        f"🏷 <b>Название группы:</b> «{html.escape(group_name)}»\n"
        f"👑 <b>Главный администратор:</b> {usernames_str}\n"
        f"👤 <b>Назначенный проверяющий заявок:</b> {reviewer_info}\n"
        f"👥 <b>Целевая группа:</b> {group_info}\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Всего заявок: {stats['total']}\n"
        f"• Ожидают проверки: <b>{stats['pending']}</b>\n"
        f"• Принято: {stats['approved']}\n"
        f"• Отклонено: {stats['rejected']}\n\n"
        f"<i>💡 Проверяющий назначается кнопкой ниже. Все заявки приходят ему, а вы можете просматривать их в любой момент через кнопку «Заявки на вступление».</i>"
    )
    return text

@router.message(Command("admin"))
async def cmd_admin(message: Message, bot: Bot, state: FSMContext):
    await db.record_superadmin_id_if_matching(message.from_user.id, message.from_user.username)
    
    if not db.is_superadmin(message.from_user.id, message.from_user.username) and not await db.is_reviewer(message.from_user.id):
        await message.answer("⛔ У вас нет доступа к панели администратора.")
        return

    await state.clear()
    stats = await db.get_stats()
    text = await get_admin_dashboard_text(bot)
    await message.answer(
        text=text,
        parse_mode="HTML",
        reply_markup=get_admin_main_kb(stats["pending"])
    )

@router.callback_query(F.data == "admin_view_apps")
async def process_view_applications(callback: CallbackQuery, bot: Bot):
    pending_apps = await db.get_all_pending_applications()
    
    if not pending_apps:
        await callback.answer("Нет ожидающих заявок!", show_alert=True)
        return

    await callback.answer()
    await callback.message.answer(f"📋 <b>Список ожидающих заявок ({len(pending_apps)}):</b>", parse_mode="HTML")
    
    # Показываем до 10 последних заявок с кнопками для просмотра/управления
    for app in pending_apps[:10]:
        u_mention = f"@{app['username']}" if app['username'] else f"<a href='tg://user?id={app['user_id']}'>{html.escape(app['full_name'])}</a>"
        r_text = f"«{html.escape(app['reason'])}»" if app['reason'] else "<i>не указана</i>"
        text = (
            f"📥 <b>Заявка #{app['id']}</b>\n"
            f"👤 От: {u_mention} (ID: <code>{app['user_id']}</code>)\n"
            f"📅 Дата: {app['created_at']}\n"
            f"💬 Причина: {r_text}"
        )
        await callback.message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=get_review_kb(app['id'])
        )

@router.message(Command("setup_group"))
async def cmd_setup_group(message: Message, bot: Bot):
    if message.chat.type in ["group", "supergroup"]:
        member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        is_user_group_admin = isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))
        is_bot_admin = db.is_superadmin(message.from_user.id, message.from_user.username)
        
        if is_user_group_admin or is_bot_admin:
            await db.set_setting("group_id", str(message.chat.id))
            if message.chat.title:
                await db.set_setting("group_name", message.chat.title)
            await message.reply(
                f"✅ Группа <b>«{html.escape(message.chat.title)}»</b> успешно привязана к боту!\n"
                f"ID группы: <code>{message.chat.id}</code>\n"
                f"Убедитесь, что бот назначен администратором группы с правом создания ссылок.",
                parse_mode="HTML"
            )
        else:
            await message.reply("⛔ Настроить группу может только администратор группы.")

@router.callback_query(F.data == "admin_cancel")
async def process_cancel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    stats = await db.get_stats()
    text = await get_admin_dashboard_text(bot)
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_admin_main_kb(stats["pending"])
    )
    await callback.answer("Действие отменено.")

@router.callback_query(F.data == "admin_current_settings")
async def process_current_settings(callback: CallbackQuery, bot: Bot):
    stats = await db.get_stats()
    text = await get_admin_dashboard_text(bot)
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_admin_main_kb(stats["pending"])
    )
    await callback.answer()

@router.callback_query(F.data == "admin_stats")
async def process_stats(callback: CallbackQuery):
    stats = await db.get_stats()
    text = (
        f"📊 <b>Подробная статистика заявок:</b>\n\n"
        f"• Всего заявок: <b>{stats['total']}</b>\n"
        f"• Ожидают решения: <b>{stats['pending']}</b>\n"
        f"• Одобрено: <b>{stats['approved']}</b>\n"
        f"• Отклонено: <b>{stats['rejected']}</b>"
    )
    await callback.answer()
    await callback.message.edit_text(
        text=text,
        parse_mode="HTML",
        reply_markup=get_admin_main_kb(stats["pending"])
    )

@router.callback_query(F.data == "admin_set_reviewer")
async def process_set_reviewer_btn(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSettingsState.waiting_for_reviewer)
    await callback.message.edit_text(
        "👤 <b>Назначение проверяющего:</b>\n\n"
        "Отправьте мне <b>Telegram ID</b> проверяющего пользователя (число, например: <code>123456789</code>) "
        "или перешлите любое сообщение от него.\n\n"
        "<i>Подсказка: пользователь может узнать свой ID в боте @userinfobot. Именно этому человеку будут приходить заявки с кнопками «Принять» и «Отклонить».</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_kb()
    )
    await callback.answer()

@router.message(AdminSettingsState.waiting_for_reviewer)
async def process_reviewer_input(message: Message, state: FSMContext, bot: Bot):
    target_id = None
    
    if message.forward_from:
        target_id = message.forward_from.id
    elif message.text and message.text.strip().isdigit():
        target_id = int(message.text.strip())

    if not target_id:
        await message.answer(
            "⚠️ Пожалуйста, введите числовой Telegram ID или перешлите сообщение от пользователя:",
            reply_markup=get_cancel_kb()
        )
        return

    await db.set_setting("reviewer_id", str(target_id))
    await state.clear()

    user_name = str(target_id)
    try:
        chat = await bot.get_chat(target_id)
        user_name = f"@{chat.username}" if chat.username else chat.full_name
        group_name = await db.get_setting("group_name", "алфавит")
        await bot.send_message(
            chat_id=target_id,
            text=f"🔔 <b>Внимание!</b> Вы были назначены проверяющим заявок на вступление в группу «{html.escape(group_name)}». Теперь все заявки будут приходить вам.",
            parse_mode="HTML"
        )
    except Exception:
        pass

    stats = await db.get_stats()
    text = (
        f"✅ <b>Проверяющий успешно назначен!</b>\n\n"
        f"Проверяющий: <code>{target_id}</code> ({user_name})\n"
        f"Теперь именно ему будут поступать все заявки на вступление."
    )
    await message.answer(text=text, parse_mode="HTML", reply_markup=get_admin_main_kb(stats["pending"]))

@router.callback_query(F.data == "admin_set_group")
async def process_set_group_btn(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSettingsState.waiting_for_group_id)
    await callback.message.edit_text(
        "👥 <b>Настройка группы:</b>\n\n"
        "Способ 1: Введите ID группы (обычно начинается с <code>-100...</code>).\n\n"
        "Способ 2: Добавьте бота в нужную группу, сделайте его <b>администратором</b> и прямо в группе напишите команду <code>/setup_group</code>.\n\n"
        "Введите ID группы сейчас или нажмите «Отмена»:",
        parse_mode="HTML",
        reply_markup=get_cancel_kb()
    )
    await callback.answer()

@router.message(AdminSettingsState.waiting_for_group_id)
async def process_group_id_input(message: Message, state: FSMContext, bot: Bot):
    val = message.text.strip()
    is_valid = (val.startswith("-") and val[1:].isdigit()) or val.isdigit()
    if not is_valid:
        await message.answer(
            "⚠️ Некорректный ID группы. Обычно он выглядит как <code>-1001234567890</code>. Попробуйте еще раз:",
            parse_mode="HTML",
            reply_markup=get_cancel_kb()
        )
        return

    await db.set_setting("group_id", val)
    await state.clear()

    group_title = val
    try:
        gchat = await bot.get_chat(int(val))
        group_title = f"«{gchat.title}»"
    except Exception:
        pass

    stats = await db.get_stats()
    await message.answer(
        f"✅ Целевая группа успешно сохранена: <b>{group_title}</b> (ID: <code>{val}</code>)\n"
        f"Не забудьте выдать боту права администратора в этой группе!",
        parse_mode="HTML",
        reply_markup=get_admin_main_kb(stats["pending"])
    )

@router.callback_query(F.data == "admin_set_name")
async def process_set_name_btn(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSettingsState.waiting_for_group_name)
    await callback.message.edit_text(
        "✏️ Введите новое название группы (по умолчанию: <b>алфавит</b>):",
        parse_mode="HTML",
        reply_markup=get_cancel_kb()
    )
    await callback.answer()

@router.message(AdminSettingsState.waiting_for_group_name)
async def process_group_name_input(message: Message, state: FSMContext):
    new_name = message.text.strip()
    if not new_name:
        return

    await db.set_setting("group_name", new_name)
    await state.clear()
    stats = await db.get_stats()
    await message.answer(
        f"✅ Название группы изменено на: <b>«{html.escape(new_name)}»</b>",
        parse_mode="HTML",
        reply_markup=get_admin_main_kb(stats["pending"])
    )
