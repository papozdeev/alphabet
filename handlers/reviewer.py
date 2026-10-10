import html
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramAPIError

import database as db
from keyboards import get_join_kb

router = Router()

@router.callback_query(F.data.startswith("rev:"))
async def handle_review_decision(callback: CallbackQuery, bot: Bot):
    reviewer = callback.from_user
    
    # Решение может принять либо назначенный проверяющий, либо главный администратор
    if not await db.can_review(reviewer.id, reviewer.username):
        await callback.answer("⛔ У вас нет прав для принятия решений по этой заявке.", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        return

    action = parts[1]
    app_id = int(parts[2])

    app = await db.get_application(app_id)
    if not app:
        await callback.answer("Заявка не найдена!", show_alert=True)
        return

    if app["status"] != "pending":
        await callback.answer(f"Эта заявка уже обработана (Статус: {app['status']})!", show_alert=True)
        return

    user_id = app["user_id"]
    username = app["username"]
    full_name = app["full_name"]
    group_name = await db.get_setting("group_name", "алфавит")
    gn_escaped = html.escape(group_name)
    user_mention = f"@{username}" if username else f"<a href='tg://user?id={user_id}'>{html.escape(full_name)}</a>"
    reviewer_mention = f"@{reviewer.username}" if reviewer.username else reviewer.full_name

    if action == "approve":
        group_id_str = await db.get_setting("group_id")
        invite_link_url = None
        warning_text = ""

        if group_id_str:
            try:
                group_id = int(group_id_str)
                
                # Если пользователь подал заявку через Telegram Join Request
                try:
                    await bot.approve_chat_join_request(chat_id=group_id, user_id=user_id)
                except Exception:
                    pass

                # Создаем персональную ссылку на 1 человека
                invite = await bot.create_chat_invite_link(
                    chat_id=group_id,
                    member_limit=1,
                    name=f"Заявка #{app_id} для {user_id}"
                )
                invite_link_url = invite.invite_link
            except TelegramAPIError as e:
                warning_text = (
                    f"\n\n⚠️ <i>Предупреждение: бот не смог создать ссылку: {html.escape(str(e))}. "
                    f"Проверьте права администратора бота в группе!</i>"
                )
            except Exception as e:
                warning_text = f"\n\n⚠️ <i>Ошибка при создании ссылки: {html.escape(str(e))}</i>"
        else:
            warning_text = (
                f"\n\n⚠️ <i>Предупреждение: ID группы не настроен! "
                f"Настройте группу через /admin или добавьте бота в группу и напишите /setup_group.</i>"
            )

        user_message_text = (
            f"🎉 <b>Поздравляю, {user_mention}!</b>\n\n"
            f"Тебя приняли и ты успешно добавлен в закрытую группу <b>«{gn_escaped}»</b>!"
        )
        
        user_kb = None
        if invite_link_url:
            user_message_text += f"\n\nВот твоя персональная ссылка для вступления:\n{invite_link_url}"
            user_kb = get_join_kb(invite_link_url, group_name)

        try:
            await bot.send_message(
                chat_id=user_id,
                text=user_message_text,
                parse_mode="HTML",
                reply_markup=user_kb
            )
        except Exception as e:
            warning_text += f"\n\n⚠️ <i>Не удалось отправить сообщение пользователю: {html.escape(str(e))}</i>"

        await db.update_application_status(
            app_id=app_id,
            status="approved",
            reviewed_by=reviewer.id,
            reviewed_by_name=reviewer.full_name
        )

        reason_display = f"\nПричина: «{html.escape(app['reason'])}»" if app['reason'] else "\nПричина: не указана"
        new_text = (
            f"📋 <b>Заявка #{app_id}</b>\n"
            f"Пользователь: {user_mention}{reason_display}\n\n"
            f"✅ <b>ПРИНЯТА</b> (Проверил(а): {html.escape(reviewer_mention)})"
            f"{warning_text}"
        )

        await callback.message.edit_text(
            text=new_text,
            parse_mode="HTML",
            reply_markup=None
        )
        await callback.answer("✅ Заявка принята!")

    elif action == "reject":
        try:
            await bot.send_message(
                chat_id=user_id,
                text="К сожалению, вашу заявку на вступление в группу отклонили."
            )
        except Exception as e:
            print(f"Не удалось отправить уведомление пользователю {user_id}: {e}")

        await db.update_application_status(
            app_id=app_id,
            status="rejected",
            reviewed_by=reviewer.id,
            reviewed_by_name=reviewer.full_name
        )

        reason_display = f"\nПричина: «{html.escape(app['reason'])}»" if app['reason'] else "\nПричина: не указана"
        new_text = (
            f"📋 <b>Заявка #{app_id}</b>\n"
            f"Пользователь: {user_mention}{reason_display}\n\n"
            f"❌ <b>ОТКЛОНЕНА</b> (Проверил(а): {html.escape(reviewer_mention)})"
        )

        await callback.message.edit_text(
            text=new_text,
            parse_mode="HTML",
            reply_markup=None
        )
        await callback.answer("❌ Заявка отклонена.")
