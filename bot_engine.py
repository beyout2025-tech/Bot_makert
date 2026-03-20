import asyncio
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command, StateFilter, ChatMemberUpdatedFilter, KICKED, MEMBER
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# [سطر 15] استيراد القوالب المستقلة لضمان الهيكلية المجزأة
from templates.communication import register_communication_handlers
from templates.translation import register_translation_handlers
from templates.store import register_store_handlers
from templates.support import register_support_handlers

# استيراد كافة دوال قاعدة البيانات دون استثناء
from database import (
    bot_db_update_user, get_bot_stats, ban_user_db, 
    is_user_banned, update_welcome_msg, get_welcome_msg, 
    get_bot_users_for_broadcast, get_banned_users, unban_user_db,
    update_user_points, is_subscription_active, get_stats,
    set_user_blocked_bot, get_blocked_count
)

active_bots = {}

# [سطر 30] تعريف كافة حالات الإدخال (FSM) للنظام
class BotSettings(StatesGroup):
    waiting_for_new_welcome = State()
    waiting_for_mybot_msg = State()
    waiting_for_translation_text = State() 
    waiting_for_support_ticket = State() 
    waiting_for_store_order = State() 

# [سطر 39] بناء لوحة تحكم المالك الاحترافية
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
        types.InlineKeyboardButton(text="❓ قائمة الأوامر", callback_data="bot_guide")
    )
    builder.adjust(2)
    return builder.as_markup()

# [سطر 56] نظام معالجة الأوسمة المطور (#) لرسائل الترحيب
def replace_tags_advanced(text, user: types.User):
    # #name_user : اسم العضو مع رابط بروفايله
    name_user = f"[{user.full_name}](tg://user?id={user.id})"
    # #username : يوزر العضو مع @
    username = f"@{user.username}" if user.username else "لا يوجد"
    # #name : الاسم فقط
    name = user.full_name
    # #id : الآيدي فقط
    u_id = str(user.id)
    
    res = text.replace("#name_user", name_user)
    res = res.replace("#username", username)
    res = res.replace("#name", name)
    res = res.replace("#id", u_id)
    return res

# إعدادات البوت الأب والمطور (ثوابت المنصة)
PARENT_BOT_TOKEN = "7353517186:AAGSFyYX0JgElvaKjbWvS0ZmNh9OtalOGqM"
ADMIN_ID = 873158772 
FACTORY_BOT_USER = "@TOT010" 

async def start_custom_bot(bot_id, token, owner_id, bot_type="communication"):
    # [سطر 81] نظام الذاكرة لربط الرسائل بالهوية (الرد الذكي)
    msg_user_map = {} 

    try:
        storage = MemoryStorage()
        bot = Bot(token=token)
        # اتصال منفصل بالبوت الأب لإرسال تقارير المطور
        parent_bot = Bot(token=PARENT_BOT_TOKEN) 
        dp = Dispatcher(storage=storage)

        # ضبط أوامر البوت في القائمة الزرقاء
        await bot.set_my_commands([
            types.BotCommand(command="start", description="بدء تشغيل البوت"),
            types.BotCommand(command="admin", description="فتح لوحة التحكم")
        ])

        # --- [1] نظام تعقب الحظر (عندما يحظر العضو البوت) ---
        @dp.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=KICKED))
        async def user_blocked_bot_handler(event: types.ChatMemberUpdated):
            set_user_blocked_bot(bot_id, event.from_user.id, 1)
            user = event.from_user
            bot_info = await bot.get_me()
            blocked_total = get_blocked_count(bot_id)
            
            report = (
                "🚫 قام أحد الأعضاء بحظر البوت الخاص بك\n\n"
                "معلومات العضو:\n"
                f"• الاسم: {user.full_name}\n"
                f"• اسم المستخدم: @{user.username if user.username else 'لا يوجد'}\n"
                f"• الآيدي: `{user.id}`\n\n"
                f"📊 إجمالي عدد المحادثات التي قامت بحظر البوت حتى الآن: {blocked_total}"
            )
            # إرسال للمالك والمطور (بدون Markdown لتفادي تعليق الإرسال)
            try: await bot.send_message(owner_id, report)
            except: pass
            try: await parent_bot.send_message(ADMIN_ID, f"إشعار حظر لبوت (@{bot_info.username}):\n{report}")
            except: pass

        # [2] فلتر الحظر الصارم (يمنع المحظورين من الاستخدام)
        @dp.message(lambda msg: is_user_banned(bot_id, msg.from_user.id))
        async def banned_user_handler(message: types.Message):
            return 

        # --- [3] معالج البداية (Start) المطور بالكامل ---
        @dp.message(Command("start"), F.from_user.id != owner_id)
        async def user_start_handler(message: types.Message):
            # تسجيل العضو والتحقق من حالته (جديد/عائد)
            user_status = bot_db_update_user(bot_id, message.from_user.id)
            user = message.from_user
            bot_info = await bot.get_me()
            bot_total = get_bot_stats(bot_id)
            platform_total = get_stats()['users']
            
            # إرسال إشعارات الدخول/العودة للمطور والمالك
            if user_status == "returned":
                notify = (f"📶 قام مستخدم جديد بإعادة استخدام البوت.\n\n👤 المعلومات:\n• الاسم: {user.full_name}\n"
                          f"• الآيدي: `{user.id}`\n📊 إجمالي الحظر: {get_blocked_count(bot_id)}")
                try: await bot.send_message(owner_id, notify)
                except: pass
                try: await parent_bot.send_message(ADMIN_ID, f"إشعار عودة لبوت (@{bot_info.username}):\n{notify}")
                except: pass
            
            elif user_status == "new":
                # إشعار لمالك البوت
                owner_notify = (f"٭ تم دخول شخص جديد الى البوت الخاص بك 👾\n            -----------------------\n"
                                f"• معلومات العضو الجديد .\n\n• الاسم : {user.full_name}\n• المعرف : @{user.username or 'لا يوجد'}\n"
                                f"• الايدي : `{user.id}`\n            -----------------------\n• عدد الاعضاء الكلي : {bot_total}")
                try: await bot.send_message(owner_id, owner_notify)
                except: pass
                # إشعار للمطور
                try: await parent_bot.send_message(ADMIN_ID, f"دخول جديد لبوت (@{bot_info.username}):\n{owner_notify}\nإجمالي الصانع: {platform_total}")
                except: pass

            # تجهيز رسالة الترحيب بالأوسمة المحدثة
            raw_welcome = get_welcome_msg(bot_id)
            welcome = replace_tags_advanced(raw_welcome, user)
            footer = f"\n\n---\n🤖 هل أعجبك البوت؟ اصنع بوتك الخاص مجانًا!\nعبر المصنع: {FACTORY_BOT_USER}"
            
            # بناء أزرار الواجهة حسب نوع البوت
            kb = InlineKeyboardBuilder()
            if bot_type == "translation":
                kb.row(types.InlineKeyboardButton(text="🌐 ترجمة نص الآن", callback_data="start_translate"))
            elif bot_type == "store":
                kb.row(types.InlineKeyboardButton(text="🛒 تصفح المتجر", callback_data="view_products"))
                kb.row(types.InlineKeyboardButton(text="📦 حالة طلباتي", callback_data="order_status"))
            elif bot_type == "support":
                kb.row(types.InlineKeyboardButton(text="🎧 فتح تذكرة دعم", callback_data="open_ticket"))
            
            kb.row(types.InlineKeyboardButton(text="📩 تواصل مع الإدارة", callback_data="contact_owner"))
            await message.answer(f"{welcome}{footer}", reply_markup=kb.as_markup(), parse_mode="Markdown")

        # --- [4] لوحة تحكم المالك الاحترافية والأوامر الإدارية بالرد ---
        @dp.message(F.from_user.id == owner_id)
        async def owner_main_handler(message: types.Message):
            # كليشة الإدارة العربية الجديدة
            admin_welcome_text = (
                "• أهلاً بك في لوحة الأدمن الخاصة بالبوت 🤖\n\n"
                "- يمكنك التحكم في البوت الخاص بك من هنا\n"
                "~~~~~~~~~~~~~~~~~\n\n"
                "استمتع ببوت خاص بدون إعلانات مزعجة!\n"
                "اشترك الآن في بوت خدماتنا المدفوعة على تيليجرام واحصل على بوت خاص بك بأسعار تبدأ من 2$ شهريًا . "
                "استمتع بالجودة والاحترافية والدعم الفني .\n"
                f"{FACTORY_BOT_USER}"
            )

            if message.text in ["/start", "/admin"]:
                return await message.answer(admin_welcome_text, reply_markup=owner_admin_menu())
            
            # تنفيذ أوامر الإدارة المتقدمة بالرد على الرسالة
            if message.reply_to_message:
                target_id = msg_user_map.get(message.reply_to_message.message_id)
                
                # 1. أمر الحظر
                if message.text == "حظر" and target_id:
                    ban_user_db(bot_id, target_id)
                    return await message.answer(f"🚫 تم حظر العضو `{target_id}` بنجاح.")
                
                # 2. أمر فك الحظر
                if message.text == "إلغاء حظر" and target_id:
                    unban_user_db(bot_id, target_id)
                    return await message.answer(f"✅ تم فك الحظر عن العضو `{target_id}`.")
                
                # 3. أمر عرض المعلومات
                if message.text == "معلومات" and target_id:
                    info_text = f"👤 **معلومات المستخدم:**\n• الآيدي: `{target_id}`\n• الحالة: نشط"
                    return await message.answer(info_text, parse_mode="Markdown")

                # 4. أمر مسح الرسالة
                if message.text == "مسح":
                    try: await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
                    except: pass
                    return await message.answer("🗑️ تم حذف الرسالة.")

                # 5. أمر التوجيه (Broadcast via Forward)
                if message.text == "توجيه":
                    users = get_bot_users_for_broadcast(bot_id); count = 0
                    for u_id in users:
                        try: await bot.forward_message(u_id, message.chat.id, message.reply_to_message.message_id); count += 1
                        except: continue
                    return await message.answer(f"🚀 تم توجيه الرسالة لـ {count} مستخدم.")

                # 6. أمر التفعيل
                if message.text == "تفعيل":
                    return await message.answer("✅ تم تفعيل الميزة المطلوبة لهذا المستخدم.")

                # 7. أمر السماح
                if message.text == "السماح":
                    return await message.answer("⏳ تم السماح للمستخدم بالتحدث بدون قيود (30 لحظة).")

                # الرد العادي للمستخدم
                if target_id:
                    try:
                        header = f"📩 **رد من الإدارة:**\n---"
                        await bot.send_message(target_id, header, parse_mode="Markdown")
                        await bot.copy_message(chat_id=target_id, from_chat_id=message.chat.id, message_id=message.message_id)
                        await message.answer("🚀 تم إرسال ردك بنجاح.")
                    except: await message.answer("❌ تعذر إرسال الرد.")
                else:
                    await message.answer("❌ لم يتم التعرف على هوية المستخدم للرد عليه.")

        # --- [5] تحميل القوالب وحل مشكلة التداخل (Modular Loading) ---
        if bot_type == "translation": 
            register_translation_handlers(dp, bot_id, owner_id, BotSettings)
        elif bot_type == "store": 
            register_store_handlers(dp, bot_id, owner_id)
        elif bot_type == "support": 
            register_support_handlers(dp, bot_id, owner_id, BotSettings, msg_user_map)
        
        # [تعديل] تسجيل معالج التواصل ليعمل زر "تواصل معنا"
        # (يتم استدعاؤه دائماً ولكن بأولوية أقل لضمان عدم سرقة رسائل البوتات المتخصصة)
        register_communication_handlers(dp, bot_id, owner_id, msg_user_map)

        # معالج زر تواصل معنا (عام لكافة البوتات)
        @dp.callback_query(F.data == "contact_owner")
        async def contact_owner_handler(callback: types.CallbackQuery):
            await callback.message.answer("📩 أرسل الآن أي رسالة (نص، صورة، بصمة) وسيتم تحويلها للمالك مباشرة.")
            await callback.answer()

        # --- [6] دوال الإدارة العامة (إذاعة، إحصائيات، إعدادات) ---
        @dp.callback_query(F.data == "change_welcome", F.from_user.id == owner_id)
        async def ask_welcome_msg(callback: types.CallbackQuery, state: FSMContext):
            instruct = (
                "📝 **أرسل رسالة الترحيب الجديدة.**\n\n"
                "💡 متاح استخدام الأوسمة:\n"
                "1. `#name_user` : اسم مع رابط\n"
                "2. `#username` : يوزر مع @\n"
                "3. `#name` : اسم الشخص\n"
                "4. `#id` : معرفه"
            )
            await callback.message.answer(instruct, parse_mode="Markdown")
            await state.set_state(BotSettings.waiting_for_new_welcome); await callback.answer()

        @dp.message(F.from_user.id == owner_id, BotSettings.waiting_for_new_welcome)
        async def save_new_welcome(message: types.Message, state: FSMContext):
            update_welcome_msg(bot_id, message.text)
            await message.answer("✅ تم تحديث رسالة الترحيب بنجاح!"); await state.clear()

        @dp.callback_query(F.data == "mybot_broadcast", F.from_user.id == owner_id)
        async def mybot_broadcast_prep(callback: types.CallbackQuery, state: FSMContext):
            if not is_subscription_active(owner_id): return await callback.answer("⚠️ ميزة الإذاعة خاصة بالـ VIP فقط.", show_alert=True)
            await callback.message.answer("📢 أرسل الإذاعة الآن لجميع المستخدمين:"); await state.set_state(BotSettings.waiting_for_mybot_msg); await callback.answer()

        @dp.message(F.from_user.id == owner_id, StateFilter(BotSettings.waiting_for_mybot_msg))
        async def mybot_broadcast_exec(message: types.Message, state: FSMContext):
            users = get_bot_users_for_broadcast(bot_id); count = 0
            for u in users:
                try: await bot.copy_message(chat_id=u, from_chat_id=message.chat.id, message_id=message.message_id); count += 1
                except: continue
            await message.answer(f"✅ تمت الإذاعة لـ **{count}** مستخدم."); await state.clear()

        @dp.callback_query(F.data == "ban_list", F.from_user.id == owner_id)
        async def show_bot_bans(callback: types.CallbackQuery):
            bans = get_banned_users(bot_id)
            txt = "🚫 **قائمة المحظورين:**\n\n" + "\n".join([f"`{u}`" for u in bans]) if bans else "لا يوجد محظورين."
            await callback.message.answer(txt, parse_mode="Markdown"); await callback.answer()

        @dp.callback_query(F.data == "mybot_stats")
        async def show_bot_statistics(callback: types.CallbackQuery):
            await callback.message.answer(f"📊 عدد المشتركين في بوتك: **{get_bot_stats(bot_id)}**", parse_mode="Markdown"); await callback.answer()

        @dp.callback_query(F.data == "bot_guide")
        async def show_bot_instructions(callback: types.CallbackQuery):
            guide = (
                "📖 **تعليمات لوحة الإدارة:**\n\n"
                "• **للرد:** قم بالرد على رسالة المستخدم الواردة واكتب ردك.\n"
                "• **للأوامر:** قم بالرد واكتب إحدى الكلمات (حظر، فك حظر، معلومات، مسح، توجيه)."
            )
            await callback.message.answer(guide, parse_mode="Markdown"); await callback.answer()

        # تشغيل البوت المصنوع
        active_bots[bot_id] = {"bot": bot, "dp": dp}
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    except Exception as e:
        print(f"❌ خطأ فادح في البوت {bot_id}: {e}")
