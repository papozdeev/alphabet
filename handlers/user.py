import html
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.filters import CommandStart

import database as db
from keyboards import get_user_greeting_kb, get_review_kb, get_admin_main_kb
from config import ADMIN_IDS

router = Router()

class UserApplicationState(StatesGroup):
    waiting_for_reason = State()

def get_user_mention(user) -> str:
    if user.username:
        return f"@{user.username}"
    return f"<a href='tg://user?id={user.id}'>{html.escape(user.full_name)}</a>"

async def notify_reviewer(bot: Bot, app_id: int, user, reason: str | None, group_name: str):
    reviewer_id_str = await db.get_setting("reviewer_id")
    superadmin_id_str = await db.get_setting("superadmin_id")
    target_recipients = []
    
    # Заявка отправляется именно назначенному проверяющему
    if reviewer_id_str and reviewer_id_str.isdigit():
        target_recipients.append(int(reviewer_id_str))
    else:
        # Если проверяющий еще не назначен, предупреждаем главного администратора
        if superadmin_id_str and superadmin_id_str.isdigit():
            target_recipients.append(int(superadmin_id_str))
        else:
            target_recipients.extend(ADMIN_IDS)

    user_mention = get_user_mention(user)
    gn_escaped = html.escape(group_name)

    if reason:
        reason_escaped = html.escape(reason)
        text = (
            f"📥 <b>Новая заявка на вступление #{app_id}</b>\n\n"
            f"{user_mention} хочет чтобы его приняли в «{gn_escaped}» "
            f"и указал(а) причину:\n«{reason_escaped}»"
        )
    else:
        text = (
            f"📥 <b>Новая заявка на вступление #{app_id}</b>\n\n"
            f"{user_mention} хочет чтобы его приняли в «{gn_escaped}» "
            f"и не указал(а) причину."
        )

    # Если проверяющий не назначен, добавляем примечание для админа
    if not reviewer_id_str or not reviewer_id_str.isdigit():
        text += "\n\n⚠️ <i>(Проверяющий еще не назначен в /admin. Заявку можете рассмотреть вы или назначить проверяющего)</i>"

    sent = False
    for recipient_id in target_recipients:
        try:
            await bot.send_message(
                chat_id=recipient_id,
                text=text,
                parse_mode="HTML",
                reply_markup=get_review_kb(app_id)
            )
            sent = True
        except Exception as e:
            print(f"Не удалось отправить уведомление получателю {recipient_id}: {e}")

    return sent

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    if message.chat.type != "private":
        return

    # Запоминаем ID супер-админа, но НЕ назначаем его проверяющим автоматически
    await db.record_superadmin_id_if_matching(message.from_user.id, message.from_user.username)

    # Если заходит главный администратор
    if db.is_superadmin(message.from_user.id, message.from_user.username):
        pending_apps = await db.get_all_pending_applications()
        gn = await db.get_setting("group_name", "алфавит")
        rev_id = await db.get_setting("reviewer_id", "Не назначен")
        
        await message.answer(
            f"👑 <b>Здравствуйте, {get_user_mention(message.from_user)}!</b>\n\n"
            f"Вы являетесь <b>главным администратором</b> бота закрытой группы «{html.escape(gn)}».\n\n"
            f"👤 <b>Текущий проверяющий заявок:</b> <code>{rev_id}</code>\n"
            f"📥 <b>Ожидающих заявок сейчас:</b> <b>{len(pending_apps)}</b>\n\n"
            f"Нажмите /admin для панели управления или просмотра всех заявок.",
            parse_mode="HTML",
            reply_markup=get_admin_main_kb(len(pending_apps))
        )
        return

    # Если заходит назначенный проверяющий
    if await db.is_reviewer(message.from_user.id):
        pending_apps = await db.get_all_pending_applications()
        await message.answer(
            f"👋 <b>Здравствуйте, {get_user_mention(message.from_user)}!</b>\n\n"
            f"Вы назначены проверяющим заявок в группу «алфавит».\n"
            f"Ожидающих заявок: <b>{len(pending_apps)}</b>\n"
            f"Вам будут приходить все новые заявки с кнопками «Принять» и «Отклонить».",
            parse_mode="HTML"
        )
        return

    group_name = await db.get_setting("group_name", "алфавит")
    pending_app = await db.get_pending_application_by_user(message.from_user.id)

    if pending_app:
        await message.answer(
            f"⏳ Твоя заявка на вступление в «{html.escape(group_name)}» уже находится на рассмотрении.\n"
            f"Пожалуйста, ожидай решения."
        )
        return

    await state.set_state(UserApplicationState.waiting_for_reason)

    user_mention = get_user_mention(message.from_user)
    gn_escaped = html.escape(group_name)

    welcome_text = (
        f"Привет, {user_mention}!\n\n"
        f"Напиши причину, по которой ты хочешь чтобы тебя добавили в «{gn_escaped}», "
        f"или нажми на кнопку ниже, чтобы пропустить."
    )

    await message.answer(
        text=welcome_text,
        parse_mode="HTML",
        reply_markup=get_user_greeting_kb()
    )

@router.callback_query(F.data == "user_skip_reason")
async def process_skip_reason(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user = callback.from_user
    group_name = await db.get_setting("group_name", "алфавит")

    pending_app = await db.get_pending_application_by_user(user.id)
    if pending_app:
        await callback.answer("У вас уже есть активная заявка на рассмотрении!", show_alert=True)
        await state.clear()
        return

    await state.clear()

    app_id = await db.create_application(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        reason=None
    )

    await notify_reviewer(bot, app_id, user, reason=None, group_name=group_name)

    await callback.answer()
    await callback.message.edit_text(
        "✅ Твоя заявка отправлена на рассмотрение (без указания причины).\n"
        "Ожидай ответа!"
    )

@router.message(UserApplicationState.waiting_for_reason, F.text)
async def process_reason_text(message: Message, state: FSMContext, bot: Bot):
    if message.text.startswith("/"):
        return

    user = message.from_user
    group_name = await db.get_setting("group_name", "алфавит")

    pending_app = await db.get_pending_application_by_user(user.id)
    if pending_app:
        await message.answer(
            "⏳ Твоя заявка уже находится на рассмотрении. Ожидай ответа!"
        )
        await state.clear()
        return

    reason = message.text.strip()
    await state.clear()

    app_id = await db.create_application(
        user_id=user.id,
        username=user.username,
        full_name=user.full_name,
        reason=reason
    )

    await notify_reviewer(bot, app_id, user, reason=reason, group_name=group_name)

    await message.answer(
        "✅ Спасибо! Твоя заявка отправлена на рассмотрение.\n"
        "Ожидай ответа!"
    )
