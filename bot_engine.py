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
    update_user_points, is_subscription_active
)

active_bots = {}

# 2. حالات الإدخال (FSM) للبوتات المصنوعة
class BotSettings(StatesGroup):
    waiting_for_new_welcome = State()
    waiting_for_mybot_msg = State()
    waiting_for_translation_text = State() # لانتظار النص المراد ترجمته
    waiting_for_support_ticket = State() # لانتظار محتوى التذكرة
    waiting_for_store_order = State() # لانتظار طلبات المتجر

# قائمة التحكم الخاصة بالمالك (ثابتة لجميع أنواع البوتات)
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
    builder.row(
        types.InlineKeyboardButton(text="❓ تعليمات الاستخدام", callback_data="bot_guide")
    )
    builder.adjust(2)
    return builder.as_markup()

# 🚀 المحرك الأساسي لتشغيل البوتات بأنواعها (SaaS Engine)
async def start_custom_bot(bot_id, token, owner_id, bot_type="communication"):
    try:
        storage = MemoryStorage()
        bot = Bot(token=token)
        dp = Dispatcher(storage=storage)

        # ضبط قائمة الأوامر تلقائياً فور التشغيل
        await bot.set_my_commands([
            types.BotCommand(command="start", description="بدء البوت"),
            types.BotCommand(command="admin", description="لوحة تحكم المالك"),
            types.BotCommand(command="help", description="طلب المساعدة")
        ])

        # --- [1] نظام الحظر الصارم ---
        @dp.message(lambda msg: is_user_banned(bot_id, msg.from_user.id))
        async def banned_user_handler(message: types.Message):
            return 

        # --- [2] أوامر المالك العامة (إعدادات البوت) ---
        @dp.callback_query(F.data == "change_welcome", F.from_user.id == owner_id)
        async def ask_new_welcome(callback: types.CallbackQuery, state: FSMContext):
            await callback.message.answer("📝 أرسل الآن رسالة الترحيب الجديدة التي ستظهر لمستخدمي بوتك:")
            await state.set_state(BotSettings.waiting_for_new_welcome)
            await callback.answer()

        @dp.message(F.from_user.id == owner_id, BotSettings.waiting_for_new_welcome)
        async def set_new_welcome(message: types.Message, state: FSMContext):
            if message.text:
                update_welcome_msg(bot_id, message.text) 
                await message.answer("✅ تم تحديث رسالة الترحيب بنجاح!")
                await state.clear()
            else:
                await message.answer("⚠️ يرجى إرسال نص فقط لرسالة الترحيب.")

        # --- [3] معالج البداية للمستخدمين (Start Handler) ---
        @dp.message(Command("start"), F.from_user.id != owner_id)
        async def user_start_handler(message: types.Message):
            bot_db_update_user(bot_id, message.from_user.id) # تسجيل المستخدم فوراً
            welcome = get_welcome_msg(bot_id)
            
            # بناء لوحة مفاتيح مخصصة بناءً على نوع البوت (Template System)
            kb = InlineKeyboardBuilder()
            if bot_type == "store":
                kb.row(types.InlineKeyboardButton(text="🛒 تصفح المنتجات", callback_data="view_products"))
                kb.row(types.InlineKeyboardButton(text="📦 حالة طلبي", callback_data="order_status"))
            elif bot_type == "support":
                kb.row(types.InlineKeyboardButton(text="🎧 فتح تذكرة دعم", callback_data="open_ticket"))
                kb.row(types.InlineKeyboardButton(text="📊 متابعة التذاكر", callback_data="my_tickets"))
            elif bot_type == "translation":
                kb.row(types.InlineKeyboardButton(text="🌐 ترجمة نص الآن", callback_data="start_translate"))
                kb.row(types.InlineKeyboardButton(text="⚙️ إعدادات اللغة", callback_data="select_lang"))
            elif bot_type == "education":
                kb.row(types.InlineKeyboardButton(text="📚 تصفح الدروس", callback_data="view_lessons"))
                kb.row(types.InlineKeyboardButton(text="📝 اختبار سريع", callback_data="take_quiz"))
            
            kb.row(types.InlineKeyboardButton(text="📩 تواصل مع الإدارة", callback_data="contact_owner"))
            
            await message.answer(
                f"{welcome}\n\n🤖 **هذا البوت متخصص في:** {bot_type}", 
                reply_markup=kb.as_markup(),
                parse_mode="Markdown"
            )

        # --- [4] منطق البوتات التخصصي (SaaS Logic - Templates) ---

        # أ. بوت الترجمة (Translation System)
        @dp.callback_query(F.data == "start_translate")
        async def start_translation_flow(callback: types.CallbackQuery, state: FSMContext):
            await callback.message.answer("🌐 أرسل الآن النص الذي تريد ترجمته (عربي ↔️ إنجليزي):")
            await state.set_state(BotSettings.waiting_for_translation_text)
            await callback.answer()

        @dp.message(BotSettings.waiting_for_translation_text)
        async def process_translation(message: types.Message, state: FSMContext):
            # هنا سيتم لاحقاً دمج Google Translate API
            await message.answer(f"🔄 جاري ترجمة: `{message.text}`\n\n*(هذه الميزة ستفعل بالكامل في الخطوة القادمة)*", parse_mode="Markdown")
            await state.clear()

        # ب. بوت المتجر (Store System)
        @dp.callback_query(F.data == "view_products")
        async def store_view_products(callback: types.CallbackQuery):
            await callback.message.answer("📦 قائمة المنتجات حالياً فارغة، سيقوم المالك بإضافتها قريباً.")
            await callback.answer()

        # ج. بوت الدعم الفني (Support System)
        @dp.callback_query(F.data == "open_ticket")
        async def open_support_ticket(callback: types.CallbackQuery, state: FSMContext):
            await callback.message.answer("🎧 يرجى كتابة تفاصيل مشكلتك أو استفسارك في رسالة واحدة:")
            await state.set_state(BotSettings.waiting_for_support_ticket)
            await callback.answer()

        @dp.message(BotSettings.waiting_for_support_ticket)
        async def save_ticket(message: types.Message, state: FSMContext):
            bot_db_update_user(bot_id, message.from_user.id)
            # إرسال التذكرة للمالك كرسالة تواصل
            info = f"🎫 **تذكرة دعم جديدة:**\n👤 من: `{message.from_user.id}`\n---\n{message.text}"
            await bot.send_message(owner_id, info, parse_mode="Markdown")
            await message.answer("✅ تم إرسال تذكرتك بنجاح، سيقوم الدعم بالرد عليك هنا.")
            await state.clear()

        # د. زر التواصل المباشر (Contact Owner)
        @dp.callback_query(F.data == "contact_owner")
        async def initiate_contact(callback: types.CallbackQuery):
            await callback.message.answer("📩 أرسل الآن أي رسالة (نص، صورة، صوت) وسيتم تحويلها لمالك البوت فوراً.")
            await callback.answer()

        # --- [5] نظام التواصل الشامل (حل مشكلة عدم وصول الرسائل) ---
        # تم تعديل الفلتر ليدعم كافة أنواع المحتوى (ContentType) ويستثني الأوامر فقط
        @dp.message(F.chat.type == "private", F.from_user.id != owner_id, ~F.text.startswith("/"))
        async def global_forward_handler(message: types.Message):
            # تسجيل المستخدم لضمان ظهوره في الإحصائيات والإذاعة
            bot_db_update_user(bot_id, message.from_user.id)
            
            try:
                # 1. إرسال رأس الرسالة (Header) لتعريف المالك بالمرسل
                header = (
                    f"📩 **رسالة جديدة واردة:**\n"
                    f"👤 الاسم: {message.from_user.full_name}\n"
                    f"🆔 المعرف: `{message.from_user.id}`\n"
                    f"🔗 اليوزر: @{message.from_user.username if message.from_user.username else 'لا يوجد'}\n"
                    f"---"
                )
                await bot.send_message(owner_id, header, parse_mode="Markdown")
                
                # 2. نسخ الرسالة الأصلية للمالك (Copy تدعم كافة الوسائط)
                await bot.copy_message(chat_id=owner_id, from_chat_id=message.chat.id, message_id=message.message_id)
                
                await message.answer("✅ تم إرسال رسالتك للمالك، انتظر الرد.")
                update_user_points(message.from_user.id, 1) # مكافأة التفاعل
            except Exception as e:
                print(f"Forward Error: {e}")
                await message.answer("❌ عذراً، المالك لم يقم بتفعيل استقبال الرسائل في هذا البوت بعد.")

        # --- [6] لوحة تحكم المالك والردود الذكية ---
        @dp.message(F.from_user.id == owner_id)
        async def owner_main_handler(message: types.Message):
            # عرض لوحة التحكم
            if message.text in ["/start", "/admin"]:
                return await message.answer(
                    f"🎮 أهلاً بك يا صاحب بوت الـ **{bot_type}** في لوحة التحكم:", 
                    reply_markup=owner_admin_menu()
                )

            # منطق الرد واستخراج الـ ID من الرسائل السابقة
            if message.reply_to_message:
                try:
                    target_id = None
                    # استخراج الـ ID من الـ Header أو من خاصية التوجيه
                    if message.reply_to_message.forward_from:
                        target_id = message.reply_to_message.forward_from.id
                    elif message.reply_to_message.text and "🆔 المعرف:" in message.reply_to_message.text:
                        target_id = int(message.reply_to_message.text.split("`")[1])

                    if target_id:
                        # الأوامر السريعة بالرد
                        if message.text == "حظر":
                            ban_user_db(bot_id, target_id)
                            return await message.answer(f"🚫 تم حظر المستخدم `{target_id}`.")
                        if message.text == "فك حظر":
                            unban_user_db(bot_id, target_id)
                            return await message.answer(f"✅ تم فك الحظر عن `{target_id}`.")
                        
                        # إرسال الرد للمستخدم
                        await bot.copy_message(chat_id=target_id, from_chat_id=message.chat.id, message_id=message.message_id)
                        await message.answer("🚀 تم إرسال ردك للمستخدم بنجاح.")
                    else:
                        await message.answer("❌ لم أتمكن من العثور على معرّف المستخدم للرد عليه.")
                except Exception as e:
                    await message.answer(f"❌ خطأ في الإرسال: {e}")

        # --- [7] وظائف الإدارة (إذاعة، إحصائيات، محظورين) ---
        @dp.callback_query(F.data == "mybot_broadcast", F.from_user.id == owner_id)
        async def prepare_mybot_broadcast(callback: types.CallbackQuery, state: FSMContext):
            # فحص الاشتراك للسماح بالإذاعة (ميزة VIP للبوتات المصنوعة)
            if not is_subscription_active(owner_id):
                return await callback.answer("⚠️ ميزة الإذاعة متاحة فقط للبوتات التي تمت ترقيتها لـ VIP.", show_alert=True)
            
            await callback.message.answer("📢 أرسل الآن الرسالة (نص، صورة، فيديو) التي تريد إذاعتها لجميع مستخدمي بوتك:")
            await state.set_state(BotSettings.waiting_for_mybot_msg)
            await callback.answer()

        @dp.message(F.from_user.id == owner_id, StateFilter(BotSettings.waiting_for_mybot_msg))
        async def execute_mybot_broadcast(message: types.Message, state: FSMContext):
            users = get_bot_users_for_broadcast(bot_id)
            success_count = 0
            for u_id in users:
                try:
                    await bot.copy_message(chat_id=u_id, from_chat_id=message.chat.id, message_id=message.message_id)
                    success_count += 1
                except: continue
            await message.answer(f"✅ تم الانتهاء! وصلت الرسالة لـ **{success_count}** مستخدم.")
            await state.clear()

        @dp.callback_query(F.data == "ban_list", F.from_user.id == owner_id)
        async def show_bot_banned(callback: types.CallbackQuery):
            banned = get_banned_users(bot_id)
            text = "🚫 **قائمة المحظورين في بوتك:**\n\n" + "\n".join([f"`{u}`" for u in banned]) if banned else "لا يوجد محظورين حالياً."
            await callback.message.answer(text, parse_mode="Markdown")
            await callback.answer()

        @dp.callback_query(F.data == "mybot_stats")
        async def show_bot_stats_handler(callback: types.CallbackQuery):
            count = get_bot_stats(bot_id) 
            await callback.message.answer(f"📊 **إحصائيات بوتك:**\n\n👥 عدد المستخدمين: **{count}**", parse_mode="Markdown")
            await callback.answer()

        @dp.callback_query(F.data == "bot_guide")
        async def show_bot_guide_handler(callback: types.CallbackQuery):
            guide = (
                "📖 **دليل إدارة بوت الـ {bot_type}:**\n\n"
                "1️⃣ **للرد:** قم بالرد (Reply) على رسالة إشعار المستخدم واكتب ردك.\n"
                "2️⃣ **للحظر:** رد على رسالته بكلمة 'حظر'.\n"
                "3️⃣ **لفك الحظر:** رد على رسالته بكلمة 'فك حظر'.\n"
                "4️⃣ **للإذاعة:** استخدم زر الإذاعة في لوحة التحكم (للمشتركين VIP).\n"
                "5️⃣ **تغيير الترحيب:** يمكنك تعديل النص الذي يظهر للمشتركين الجدد."
            ).format(bot_type=bot_type)
            await callback.message.answer(guide, parse_mode="Markdown")
            await callback.answer()

        # تسجيل البوت في الذاكرة والبدء بالاستماع
        active_bots[bot_id] = {"bot": bot, "dp": dp}
        print(f"🚀 البوت {bot_id} (نوع: {bot_type}) انطلق بنجاح للمالك {owner_id}!")
        
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    except Exception as e:
        print(f"❌ خطأ فادح في محرك البوت {bot_id}: {e}")

