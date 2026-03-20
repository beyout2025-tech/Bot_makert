import asyncio
import json
from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command, StateFilter, ChatMemberUpdatedFilter, KICKED, MEMBER
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# [سطر 15] استيراد القوالب المستقلة - (نقطة تطوير: أضف استيراد أي قالب جديد هنا)
from templates.communication import register_communication_handlers
from templates.translation import register_translation_handlers
from templates.store import register_store_handlers
from templates.support import register_support_handlers

from database import (
    bot_db_update_user, get_bot_stats, ban_user_db, 
    is_user_banned, update_welcome_msg, get_welcome_msg, 
    get_bot_users_for_broadcast, get_banned_users, unban_user_db,
    update_user_points, is_subscription_active, get_stats,
    set_user_blocked_bot, get_blocked_count
)

active_bots = {}

# [سطر 30] حالات الإدخال - (نقطة تطوير: أضف حالات FSM الجديدة هنا)
class BotSettings(StatesGroup):
    waiting_for_new_welcome = State()
    waiting_for_mybot_msg = State()
    waiting_for_translation_text = State() 
    waiting_for_support_ticket = State() 

# [سطر 37] لوحة تحكم المالك المحدثة - (نقطة تطوير: تعديل أزرار التحكم)
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
    builder.row(types.InlineKeyboardButton(text="❓ قائمة الأوامر", callback_data="bot_guide"))
    builder.adjust(2)
    return builder.as_markup()

# [جديد] دالة معالجة الأوسمة بنظام # المطور
def replace_tags_advanced(text, user: types.User):
    name_user = f"[{user.full_name}](tg://user?id={user.id})"
    username = f"@{user.username}" if user.username else "لا يوجد"
    res = text.replace("#name_user", name_user).replace("#username", username).replace("#name", user.full_name).replace("#id", str(user.id))
    return res

# إعدادات المطور الأساسية (تأكد من صحة التوكن والآيدي)
PARENT_BOT_TOKEN = "7353517186:AAGSFyYX0JgElvaKjbWvS0ZmNh9OtalOGqM"
ADMIN_ID = 873158772 
FACTORY_BOT_USER = "@TOT010" 

async def start_custom_bot(bot_id, token, owner_id, bot_type="communication"):
    # [سطر 65] ذاكرة الرد الذكي لربط الرسائل بالهوية
    msg_user_map = {} 

    try:
        storage = MemoryStorage()
        bot = Bot(token=token)
        # إنشاء اتصال بالبوت الأب لضمان وصول إشعارات المطور
        parent_bot = Bot(token=PARENT_BOT_TOKEN) 
        dp = Dispatcher(storage=storage)

        await bot.set_my_commands([
            types.BotCommand(command="start", description="بدء البوت"),
            types.BotCommand(command="admin", description="لوحة التحكم")
        ])

        # --- [جديد] معالجة حظر البوت (إرسال إشعار للمالك والمطور) ---
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
            try: await bot.send_message(owner_id, report)
            except: pass
            try: await parent_bot.send_message(ADMIN_ID, f"🚫 حظر لبوت (@{bot_info.username}):\n{report}")
            except: pass

        @dp.message(lambda msg: is_user_banned(bot_id, msg.from_user.id))
        async def banned_user_handler(message: types.Message): return 

        # --- [تطوير] معالج البداية (Start) مع نظام "العودة" وإشعارات المطور ---
        @dp.message(Command("start"), F.from_user.id != owner_id)
        async def user_start_handler(message: types.Message):
            user_status = bot_db_update_user(bot_id, message.from_user.id)
            user = message.from_user
            bot_info = await bot.get_me()
            bot_total = get_bot_stats(bot_id)
            platform_total = get_stats()['users']
            
            # 1. حالة المستخدم العائد بعد الحظر
            if user_status == "returned":
                blocked_total = get_blocked_count(bot_id)
                notify = (
                    "📶 قام مستخدم جديد بإعادة استخدام البوت الخاص بك مرة أخرى.\n\n"
                    "👤 معلومات العضو:\n"
                    f"• الاسم: {user.full_name}\n"
                    f"• اسم المستخدم: @{user.username if user.username else 'لا يوجد'}\n"
                    f"• الآيدي: `{user.id}`\n\n"
                    f"📊 إجمالي عدد المحادثات التي قامت بحظر البوت حتى الآن: {blocked_total}"
                )
                try: await bot.send_message(owner_id, notify)
                except: pass
                try: await parent_bot.send_message(ADMIN_ID, f"📶 عودة لبوت (@{bot_info.username}):\n{notify}")
                except: pass
            
            # 2. حالة المستخدم الجديد كلياً
            elif user_status == "new":
                # إشعار لمالك البوت
                owner_notify = (
                    "٭ تم دخول شخص جديد الى البوت الخاص بك 👾\n"
                    "            -----------------------\n"
                    "• معلومات العضو الجديد .\n\n"
                    f"• الاسم : {user.full_name}\n"
                    f"• المعرف : @{user.username if user.username else 'لا يوجد'}\n"
                    f"• الايدي : `{user.id}`\n"
                    "            -----------------------\n"
                    f"• عدد الاعضاء الكلي : {bot_total}"
                )
                try: await bot.send_message(owner_id, owner_notify)
                except: pass
                
                # إشعار للمطور (البوت الأب)
                admin_notify = (
                    f"٭ تم دخول شخص جديد الى البوت (@{bot_info.username}) 👾\n"
                    "            -----------------------\n"
                    "• معلومات العضو الجديد .\n\n"
                    f"• الاسم : {user.full_name}\n"
                    f"• المعرف : @{user.username if user.username else 'لا يوجد'}\n"
                    f"• الايدي : `{user.id}`\n"
                    "            -----------------------\n"
                    f"• عدد الاعضاء الكلي للبوت : {bot_total}\n"
                    f" عدد الاعضاء الكلي للصانع  : {platform_total}"
                )
                try: await parent_bot.send_message(ADMIN_ID, admin_notify)
                except: pass

            # رسالة الترحيب والوسوم والتذييل
            raw_welcome = get_welcome_msg(bot_id)
            welcome = replace_tags_advanced(raw_welcome, user)
            footer = f"\n\n---\n🤖 هل أعجبك البوت؟ اصنع بوتك الخاص مجانًا!\nعبر المصنع: {FACTORY_BOT_USER}"
            kb = InlineKeyboardBuilder()
            if bot_type == "translation": kb.row(types.InlineKeyboardButton(text="🌐 ترجمة", callback_data="start_translate"))
            elif bot_type == "store": kb.row(types.InlineKeyboardButton(text="🛒 المتجر", callback_data="view_products"))
            kb.row(types.InlineKeyboardButton(text="📩 تواصل معنا", callback_data="contact_owner"))
            await message.answer(f"{welcome}{footer}", reply_markup=kb.as_markup(), parse_mode="Markdown")

        # --- [تطوير سطر 148] لوحة تحكم المالك الاحترافية والأوامر ---
        @dp.message(F.from_user.id == owner_id)
        async def owner_main_handler(message: types.Message):
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
            
            if message.reply_to_message:
                target_id = msg_user_map.get(message.reply_to_message.message_id)
                # الأوامر المتقدمة (حظر، مسح، توجيه...)
                if message.text == "حظر" and target_id:
                    ban_user_db(bot_id, target_id)
                    return await message.answer(f"🚫 تم حظر العضو `{target_id}` بنجاح.")
                if message.text == "إلغاء حظر" and target_id:
                    unban_user_db(bot_id, target_id)
                    return await message.answer(f"✅ تم فك الحظر عن `{target_id}`.")
                if message.text == "معلومات" and target_id:
                    return await message.answer(f"👤 **بيانات المستخدم:**\n🆔 الآيدي: `{target_id}`\n🌐 الحالة: نشط", parse_mode="Markdown")
                if message.text == "مسح":
                    try: await bot.delete_message(message.chat.id, message.reply_to_message.message_id)
                    except: pass
                    return await message.answer("🗑️ تم حذف الرسالة.")
                if message.text == "توجيه":
                    users = get_bot_users_for_broadcast(bot_id); c = 0
                    for u in users:
                        try: await bot.forward_message(u, message.chat.id, message.reply_to_message.message_id); c += 1
                        except: continue
                    return await message.answer(f"🚀 تم التوجيه لـ {c} مستخدم.")
                if message.text == "السماح":
                    return await message.answer("⏳ تم منح المستخدم إذن التحدث بدون قيود (30 لحظة).")

                if target_id:
                    try:
                        await bot.copy_message(chat_id=target_id, from_chat_id=message.chat.id, message_id=message.message_id)
                        await message.answer("🚀 تم إرسال الرد.")
                    except: await message.answer("❌ تعذر الرد.")
                else: await message.answer("❌ لم يتم التعرف على المستخدم للرد عليه.")

        # [سطر 202] تحميل القوالب - (نقطة تطوير: ربط ملفات منطق البوتات)
        if bot_type == "translation": register_translation_handlers(dp, bot_id, owner_id, BotSettings)
        elif bot_type == "store": register_store_handlers(dp, bot_id, owner_id)
        elif bot_type == "support": register_support_handlers(dp, bot_id, owner_id, BotSettings, msg_user_map)
        register_communication_handlers(dp, bot_id, owner_id, msg_user_map)

        # [سطر 209] أوامر الإدارة العامة
        @dp.callback_query(F.data == "change_welcome", F.from_user.id == owner_id)
        async def ask_welcome(callback: types.CallbackQuery, state: FSMContext):
            instruct = ("📝 **أرسل الترحيب الجديد.**\n\n💡 الأوسمة:\n`#name_user`, `#username`, `#name`, `#id`")
            await callback.message.answer(instruct, parse_mode="Markdown")
            await state.set_state(BotSettings.waiting_for_new_welcome); await callback.answer()

        @dp.message(F.from_user.id == owner_id, BotSettings.waiting_for_new_welcome)
        async def save_welcome(message: types.Message, state: FSMContext):
            update_welcome_msg(bot_id, message.text); await message.answer("✅ تم التحديث!"); await state.clear()

        @dp.callback_query(F.data == "bot_guide")
        async def show_guide(callback: types.CallbackQuery):
            guide = ("↴ قائمة الأوامر .\n⚠️ جميعها مع الرد على الرسالة .\n\n▫️ حظر / إلغاء حظر\n▫️ معلومات / تفعيل / مسح / توجيه")
            await callback.message.answer(guide); await callback.answer()

        @dp.callback_query(F.data == "mybot_stats")
        async def show_stats(callback: types.CallbackQuery):
            await callback.message.answer(f"📊 المشتركين: {get_bot_stats(bot_id)}", parse_mode="Markdown"); await callback.answer()

        active_bots[bot_id] = {"bot": bot, "dp": dp}
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

    except Exception as e: print(f"❌ خطأ: {e}")
