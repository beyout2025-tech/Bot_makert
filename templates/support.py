# templates/support.py
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from database import bot_db_update_user

router = Router()

def register_support_handlers(dp: Router, bot_id, owner_id, BotSettings, msg_user_map):
    
    @router.callback_query(F.data == "open_ticket")
    async def open_ticket(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.answer("🎧 يرجى كتابة تفاصيل مشكلتك وسيقوم فريق الدعم بالرد عليك:")
        await state.set_state(BotSettings.waiting_for_support_ticket)
        await callback.answer()

    @router.message(StateFilter(BotSettings.waiting_for_support_ticket))
    async def process_ticket(message: types.Message, state: FSMContext):
        bot_db_update_user(bot_id, message.from_user.id)
        # إرسال التذكرة للمالك بنظام الإشعار المطور
        info = f"🎫 **تذكرة دعم جديدة:**\n👤 من: `{message.from_user.id}`\n---\n{message.text}"
        sent_msg = await message.bot.send_message(owner_id, info, parse_mode="Markdown")
        msg_user_map[sent_msg.message_id] = message.from_user.id # ربط التذكرة بالرد الذكي
        
        await message.answer("✅ تم فتح التذكرة بنجاح، انتظر رد الإدارة.")
        await state.clear()

    dp.include_router(router)
