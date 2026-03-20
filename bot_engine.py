import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# استيراد القوالب المستقلة
from templates.communication import register_communication_handlers
from templates.translation import register_translation_handlers
from templates.store import register_store_handlers
from templates.support import register_support_handlers

from database import (
    bot_db_update_user, get_bot_stats, ban_user_db, 
    is_user_banned, update_welcome_msg, get_welcome_msg, 
    get_bot_users_for_broadcast, get_banned_users, unban_user_db,
    update_user_points, is_subscription_active
)

active_bots = {}

class BotSettings(StatesGroup):
    waiting_for_new_welcome = State()
    waiting_for_mybot_msg = State()
    waiting_for_translation_text = State() 
    waiting_for_support_ticket = State() 

def owner_admin_menu():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📊 إحصائيات بوتي", callback_data="mybot_stats"),
        types.InlineKeyboardButton(text="📢 إذاعة للمشتركين", callback_data="mybot_broadcast")
    )
    builder.row(
        types.InlineKeyboardButton(text="📝 تغيير الترحيب", callback_data="change_welcome"),
        types.InlineKeyboardButton(text="🚫 قائمة المحظورين", callback_data="ban_list")
    )
    builder.row(types.InlineKeyboardButton(text="❓ التعليمات", callback_data="bot_guide"))
    builder.adjust(2)
    return builder.as_markup()

async def start_custom_bot(bot_id, token, owner_id, bot_type="communication"):
    # نظام الذاكرة لربط الرسائل بالهوية (يعمل عبر كافة القوالب)
    msg_user_map = {} 

    try:
        storage = MemoryStorage()
        bot = Bot(token=token)
        dp = Dispatcher(storage=storage)

        await bot.set_my_commands([
            types.BotCommand(command="start", description="بدء البوت"),
            types.BotCommand(command="admin", description="لوحة التحكم")
        ])

        # --- [1] نظام الحظر العام ---
        @dp.message(lambda msg: is_user_banned(bot_id, msg.from_user.id))
        async def banned_user_handler(message: types.Message): return 

        # --- [2] معالج البداية (Router) بناءً على النوع ---
        @dp.message(Command("start"), F.from_user.id != owner_id)
        async def user_start_handler(message: types.Message):
            bot_db_update_user(bot_id, message.from_user.id)
            welcome = get_welcome_msg(bot_id)
            kb = InlineKeyboardBuilder()
            
            # عرض الأزرار حسب النوع
            if bot_type == "translation":
                kb.row(types.InlineKeyboardButton(text="🌐 ترجمة نص", callback_data="start_translate"))
            elif bot_type == "store":
                kb.row(types.InlineKeyboardButton(text="🛒 المتجر", callback_data="view_products"))
                kb.row(types.InlineKeyboardButton(text="📦 طلبي", callback_data="order_status"))
            elif bot_type == "support":
                kb.row(types.InlineKeyboardButton(text="🎧 فتح تذكرة", callback_data="open_ticket"))
            
            kb.row(types.InlineKeyboardButton(text="📩 تواصل معنا", callback_data="contact_owner"))
            await message.answer(f"{welcome}\n\n🤖 نوع البوت: {bot_type}", reply_markup=kb.as_markup())

        # --- [3] التحميل الديناميكي للقوالب (Modular Loading) ---
        if bot_type == "translation":
            register_translation_handlers(dp, bot_id, owner_id, BotSettings)
        elif bot_type == "store":
            register_store_handlers(dp, bot_id, owner_id)
        elif bot_type == "support":
            register_support_handlers(dp, bot_id, owner_id, BotSettings, msg_user_map)
        
        # دائماً نقوم بتسجيل معالج التواصل كخيار احتياطي ولزر "تواصل معنا"
        register_communication_handlers(dp, bot_id, owner_id, msg_user_map)

        # --- [4] لوحة تحكم المالك (عامة) ---
        @dp.message(F.from_user.id == owner_id)
        async def owner_main_handler(message: types.Message):
            if message.text in ["/start", "/admin"]:
                return await message.answer(f"🎮 لوحة تحكم {bot_type}:", reply_markup=owner_admin_menu())

            if message.reply_to_message:
                target_id = msg_user_map.get(message.reply_to_message.message_id)
                if target_id:
                    # أوامر الحظر بالرد
                    if message.text == "حظر":
                        ban_user_db(bot_id, target_id); return await message.answer("🚫 تم الحظر.")
                    
                    await bot.copy_message(chat_id=target_id, from_chat_id=message.chat.id, message_id=message.message_id)
                    await message.answer("🚀 تم إرسال الرد.")
                else:
                    await message.answer("❌ لا يمكن العثور على هوية المستخدم.")

        # --- [5] الدوال الإدارية (إذاعة، إحصائيات) ---
        @dp.callback_query(F.data == "mybot_broadcast", F.from_user.id == owner_id)
        async def ask_broad(callback: types.CallbackQuery, state: FSMContext):
            if not is_subscription_active(owner_id): return await callback.answer("⚠️ خاص بالـ VIP.", show_alert=True)
            await callback.message.answer("📢 أرسل الإذاعة:"); await state.set_state(BotSettings.waiting_for_mybot_msg); await callback.answer()

        @dp.message(F.from_user.id == owner_id, StateFilter(BotSettings.waiting_for_mybot_msg))
        async def run_broad(message: types.Message, state: FSMContext):
            users = get_bot_users_for_broadcast(bot_id); s = 0
            for u in users:
                try: await bot.copy_message(chat_id=u, from_chat_id=message.chat.id, message_id=message.message_id); s += 1
                except: continue
            await message.answer(f"✅ وصلت لـ {s} مستخدم."); await state.clear()

        @dp.callback_query(F.data == "mybot_stats")
        async def show_stats(callback: types.CallbackQuery):
            await callback.message.answer(f"📊 المشتركين: {get_bot_stats(bot_id)}"); await callback.answer()

        active_bots[bot_id] = {"bot": bot, "dp": dp}
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    except Exception as e: print(f"❌ خطأ في بوت {bot_id}: {e}")
