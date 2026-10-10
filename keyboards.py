from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_user_greeting_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Пропустить ⏩", callback_data="user_skip_reason")
            ]
        ]
    )

def get_review_kb(app_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Принять ✅", callback_data=f"rev:approve:{app_id}"),
                InlineKeyboardButton(text="Отклонить ❌", callback_data=f"rev:reject:{app_id}")
            ]
        ]
    )

def get_join_kb(invite_link: str, group_name: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"Вступить в «{group_name}» 🚀", url=invite_link)
            ]
        ]
    )

def get_admin_main_kb(pending_count: int = 0) -> InlineKeyboardMarkup:
    badge = f" ({pending_count})" if pending_count > 0 else ""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"📥 Заявки на вступление{badge}", callback_data="admin_view_apps")
            ],
            [
                InlineKeyboardButton(text="👤 Назначить проверяющего", callback_data="admin_set_reviewer")
            ],
            [
                InlineKeyboardButton(text="👥 Настроить группу", callback_data="admin_set_group")
            ],
            [
                InlineKeyboardButton(text="✏️ Изменить название группы", callback_data="admin_set_name")
            ],
            [
                InlineKeyboardButton(text="📊 Статистика заявок", callback_data="admin_stats")
            ],
            [
                InlineKeyboardButton(text="⚙️ Текущие настройки", callback_data="admin_current_settings")
            ]
        ]
    )

def get_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")
            ]
        ]
    )
