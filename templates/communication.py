# templates/communication.py
from aiogram import Router, types, F
from database import bot_db_update_user, update_user_points

router = Router()

def register_communication_handlers(dp: Router, bot_id, owner_id, msg_user_map):
    
    @router.message(F.chat.type == "private", F.from_user.id != owner_id, ~F.text.startswith("/"))
    async def forward_to_owner(message: types.Message):
        bot_db_update_user(bot_id, message.from_user.id)
        try:
            # نظام الإشعار الذكي لحل مشكلة الرد
            header = (f"📩 **رسالة جديدة واردة:**\n👤 الاسم: {message.from_user.full_name}\n"
                      f"🆔 المعرف: `{message.from_user.id}`\n---")
            
            header_msg = await message.bot.send_message(owner_id, header, parse_mode="Markdown")
            msg_user_map[header_msg.message_id] = message.from_user.id
            
            content_msg = await message.bot.copy_message(chat_id=owner_id, from_chat_id=message.chat.id, message_id=message.message_id)
            msg_user_map[content_msg.message_id] = message.from_user.id
            
            await message.answer("✅ تم إرسال رسالتك للمالك، انتظر الرد.")
            update_user_points(message.from_user.id, 1)
        except:
            await message.answer("❌ عذراً، تعذر إرسال الرسالة للمالك حالياً.")

    dp.include_router(router)
