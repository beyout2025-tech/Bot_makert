import asyncio
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# 1. استيراد كافة دوال قاعدة البيانات المحدثة
from database import (
    bot_db_update_user, get_bot_stats, ban_user_db, 
    is_user_banned, update_welcome_msg, get_welcome_msg, 
    get_bot_users_for_broadcast, get_banned_users, unban_user_db,
    update_user_points
)

active_bots = {}

# 2. حالات الإدخال (FSM) للبوتات المصنوعة
class BotSettings(StatesGroup):
    waiting_for_new_welcome = State()
    waiting_for_mybot_msg = State()
    waiting_for_translation = State() # للترجمة
    waiting_for_support_ticket = State() # للدعم الفني

# قائمة التحكم الخاصة بالمالك (ثابتة لجميع أنواع البوتات)
def owner_admin_menu():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📊 إحصائيات بوي", callback_data="mybot_stats"),
        types.InlineKeyboardButton(text="📢 إذاعة للمشتركين", callback_data="mybot_broadcast")
    )
    builder.row(
        types.InlineKeyboardButton(text="📝 تغيير الترحيب", callback_data="change_welcome"),
        types.InlineKeyboardButton(text="🚫 قائمة المحظورين", callback_data="ban_list")
    )
    builder.row(
        types.InlineKeyboardButton(text="❓ تعليمات الاستخدام", callback_data="bot_guide")
    )
    builder.adjust(2)
    return builder.as_markup()

# 🚀 المحرك الأساسي لتشغيل البوتات بأنواعها
async def start_custom_bot(bot_id, token, owner_id, bot_type="communication"):
    try:
        storage = MemoryStorage()
        bot = Bot(token=token)
        dp = Dispatcher(storage=storage)

        # ضبط قائمة الأوامر
        await bot.set_my_commands([
            types.BotCommand(command="start", description="بدء البوت"),
            types.BotCommand(command="admin", description="لوحة تحكم المالك")
        ])

        # --- [1] نظام الحظر ---
        @dp.message(lambda msg: is_user_banned(bot_id, msg.from_user.id))
        async def banned_user_handler(message: types.Message):
            return 

        # --- [2] أوامر المالك العامة ---
        @dp.callback_query(F.data == "change_welcome", F.from_user.id == owner_id)
        async def ask_new_welcome(callback: types.CallbackQuery, state: FSMContext):
            await callback.message.answer("📝 أرسل الآن رسالة الترحيب الجديدة:")
            await state.set_state(BotSettings.waiting_for_new_welcome)
            await callback.answer()

        @dp.message(F.from_user.id == owner_id, BotSettings.waiting_for_new_welcome)
        async def set_new_welcome(message: types.Message, state: FSMContext):
            update_welcome_msg(bot_id, message.text) 
            await message.answer("✅ تم تحديث رسالة الترحيب بنجاح!")
            await state.clear()

        # --- [3] منطق البداية المشترك (Start) ---
        @dp.message(Command("start"), ~F.from_user.id == owner_id)
        async def user_start_handler(message: types.Message):
            bot_db_update_user(bot_id, message.from_user.id)
            welcome = get_welcome_msg(bot_id)
            
            # تخصيص واجهة البداية بناءً على نوع البوت
            kb = InlineKeyboardBuilder()
            if bot_type == "store":
                kb.row(types.InlineKeyboardButton(text="🛒 تصفح المنتجات", callback_data="view_products"))
            elif bot_type == "support":
                kb.row(types.InlineKeyboardButton(text="🎧 فتح تذكرة دعم", callback_data="open_ticket"))
            elif bot_type == "translation":
                kb.row(types.InlineKeyboardButton(text="🌐 اختر اللغة", callback_data="select_lang"))
            
            kb.row(types.InlineKeyboardButton(text="📩 تواصل مع الإدارة", callback_data="contact_owner"))
            
            await message.answer(f"{welcome}\n\n🤖 نوع هذا البوت: {bot_type}", reply_markup=kb.as_markup())

        # --- [4] منطق البوتات التخصصي (SaaS Logic) ---

        # أ. بوت الترجمة (مثال مبسط للترجمة)
        @dp.callback_query(F.data == "select_lang")
        async def lang_selector(callback: types.CallbackQuery):
            kb = InlineKeyboardBuilder()
            kb.row(types.InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en"))
            kb.row(types.InlineKeyboardButton(text="🇸🇦 العربية", callback_data="lang_ar"))
            await callback.message.answer("🌐 اختر اللغة التي تود الترجمة إليها:", reply_markup=kb.as_markup())
            await callback.answer()

        # ب. بوت المتجر (عرض منتجات)
        @dp.callback_query(F.data == "view_products")
        async def store_products(callback: types.CallbackQuery):
            await callback.message.answer("📦 المنتجات المتوفرة حالياً قيد التجهيز من قبل المالك.")
            await callback.answer()

        # ج. بوت الدعم الفني (Tickets)
        @dp.callback_query(F.data == "open_ticket")
        async def create_ticket(callback: types.CallbackQuery, state: FSMContext):
            await callback.message.answer("🎧 صف مشكلتك بوضوح وسيقوم الدعم بالرد عليك:")
            await state.set_state(BotSettings.waiting_for_support_ticket)
            await callback.answer()

        # --- [5] نظام التواصل المطور (حل مشكلة الخصوصية) ---
        @dp.message(F.chat.type == "private", ~F.from_user.id == owner_id)
        async def forward_to_owner(message: types.Message):
            bot_db_update_user(bot_id, message.from_user.id)
            # تم استبدال forward بـ copy_message + إضافة معلومات المرسل لتجنب None
            try:
                info_text = f"📩 رسالة من: `{message.from_user.id}`\n👤 الاسم: {message.from_user.full_name}\n---\n"
                await bot.send_message(owner_id, info_text, parse_mode="Markdown")
                await bot.copy_message(chat_id=owner_id, from_chat_id=message.chat.id, message_id=message.message_id)
                await message.answer("✅ تم إرسال رسالتك للمالك.")
                # منح نقاط للمستخدم عند التواصل لتحفيزه
                update_user_points(message.from_user.id, 1)
            except:
                await message.answer("❌ حدث خطأ في التواصل مع المالك.")

        # --- [6] لوحة تحكم المالك والردود ---
        @dp.message(F.from_user.id == owner_id)
        async def owner_handler(message: types.Message):
            if message.text in ["/start", "/admin"]:
                return await message.answer("🎮 لوحة تحكم المالك:", reply_markup=owner_admin_menu())

            # الرد الذكي باستخدام ID المستخدم من الرسالة السابقة
            if message.reply_to_message:
                # محاولة استخراج ID المستخدم من النص (إذا كان المالك يرد على رسالة الإشعار)
                try:
                    target_id = None
                    if message.reply_to_message.forward_from:
                        target_id = message.reply_to_message.forward_from.id
                    elif "رسالة من:" in str(message.reply_to_message.text):
                        target_id = int(message.reply_to_message.text.split("`")[1])

                    if target_id:
                        if message.text == "حظر":
                            ban_user_db(bot_id, target_id)
                            return await message.answer(f"🚫 تم حظر {target_id}")
                        if message.text == "فك حظر":
                            unban_user_db(bot_id, target_id)
                            return await message.answer(f"✅ تم فك حظر {target_id}")
                        
                        await bot.copy_message(chat_id=target_id, from_chat_id=message.chat.id, message_id=message.message_id)
                        await message.answer("🚀 تم إرسال الرد.")
                    else:
                        await message.answer("❌ لا يمكنني العثور على ID المستخدم للرد عليه.")
                except:
                    await message.answer("❌ فشل تحديد المستخدم.")

        # --- [7] الإذاعة والإحصائيات والمحظورين ---
        @dp.callback_query(F.data == "mybot_broadcast", F.from_user.id == owner_id)
        async def start_mybot_broadcast(callback: types.CallbackQuery, state: FSMContext):
            await callback.message.answer("📣 أرسل رسالة الإذاعة:")
            await state.set_state(BotSettings.waiting_for_mybot_msg)
            await callback.answer()

        @dp.message(F.from_user.id == owner_id, StateFilter(BotSettings.waiting_for_mybot_msg))
        async def perform_mybot_broadcast(message: types.Message, state: FSMContext):
            users = get_bot_users_for_broadcast(bot_id)
            success = 0
            for u_id in users:
                try:
                    await bot.copy_message(chat_id=u_id, from_chat_id=message.chat.id, message_id=message.message_id)
                    success += 1
                except: continue
            await message.answer(f"✅ تم الإرسال إلى {success} مستخدم.")
            await state.clear()

        @dp.callback_query(F.data == "ban_list", F.from_user.id == owner_id)
        async def show_banned_list(callback: types.CallbackQuery):
            banned = get_banned_users(bot_id)
            text = "🚫 قائمة المحظورين:\n\n" + "\n".join([f"`{u}`" for u in banned]) if banned else "لا يوجد محظورين."
            await callback.message.answer(text, parse_mode="Markdown")
            await callback.answer()

        @dp.callback_query(F.data == "mybot_stats")
        async def show_mybot_stats(callback: types.CallbackQuery):
            stats = get_bot_stats(bot_id) 
            await callback.message.answer(f"📊 المشتركين: {stats}")
            await callback.answer()

        @dp.callback_query(F.data == "bot_guide")
        async def show_guide(callback: types.CallbackQuery):
            await callback.message.answer("📖 للرد: قم بعمل Reply على إشعار الرسالة واكتب ردك.\nللحظر: اكتب 'حظر' بالرد.")
            await callback.answer()

        # تشغيل البوت
        active_bots[bot_id] = {"bot": bot, "dp": dp}
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    except Exception as e:
        print(f"❌ خطأ فادح في البوت {bot_id}: {e}")
