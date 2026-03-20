import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command, StateFilter
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

# استيراد دوال قاعدة البيانات الضرورية
from database import (
    bot_db_update_user, get_bot_stats, ban_user_db, 
    is_user_banned, update_welcome_msg, get_welcome_msg, 
    get_bot_users_for_broadcast
)

active_bots = {}

# حالات الإدخال الخاصة بالبوتات المصنوعة
class BotSettings(StatesGroup):
    waiting_for_new_welcome = State()
    waiting_for_mybot_msg = State()

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

async def start_custom_bot(bot_id, token, owner_id):
    """تشغيل نسخة بوت تواصل احترافية ومستقلة تماماً"""
    try:
        storage = MemoryStorage()
        bot = Bot(token=token)
        dp = Dispatcher(storage=storage)

        # 1. التحقق من الحظر قبل أي إجراء
        @dp.message(lambda msg: is_user_banned(bot_id, msg.from_user.id))
        async def banned_user_handler(message: types.Message):
            return 

        # 2. تغيير الترحيب (طلب الرسالة)
        @dp.callback_query(F.data == "change_welcome", F.from_user.id == owner_id)
        async def ask_new_welcome(callback: types.CallbackQuery, state: FSMContext):
            await callback.message.answer("📝 أرسل الآن رسالة الترحيب الجديدة التي ستظهر للمستخدمين عند دخولهم البوت:")
            await state.set_state(BotSettings.waiting_for_new_welcome)
            await callback.answer()

        # 3. استقبال الترحيب الجديد وحفظه
        @dp.message(F.from_user.id == owner_id, BotSettings.waiting_for_new_welcome)
        async def set_new_welcome(message: types.Message, state: FSMContext):
            update_welcome_msg(bot_id, message.text) 
            await message.answer("✅ تم تحديث رسالة الترحيب بنجاح!")
            await state.clear()

        # 4. معالج الدخول للمستخدمين (استخدام الرسالة المخزنة)
        @dp.message(Command("start"), ~F.from_user.id == owner_id)
        async def user_start_handler(message: types.Message):
            bot_db_update_user(bot_id, message.from_user.id)
            welcome = get_welcome_msg(bot_id)
            await message.answer(welcome)

        # 5. معالج رسائل المستخدمين (تحويل للمالك)
        @dp.message(F.chat.type == "private", ~F.from_user.id == owner_id)
        async def forward_to_owner(message: types.Message):
            bot_db_update_user(bot_id, message.from_user.id)
            await bot.forward_message(chat_id=owner_id, from_chat_id=message.chat.id, message_id=message.message_id)
            await message.answer("✅ تم إرسال رسالتك للمالك، انتظر الرد.")

        # 6. معالج أوامر المالك والردود والحظر
        @dp.message(F.from_user.id == owner_id)
        async def owner_handler(message: types.Message):
            # فتح لوحة التحكم
            if message.text == "/admin":
                return await message.answer("🎮 أهلاً بك في لوحة تحكم بوتك الخاص:", reply_markup=owner_admin_menu())

            # منطق الحظر بالرد
            if message.reply_to_message and message.text == "حظر":
                if message.reply_to_message.forward_from:
                    target_id = message.reply_to_message.forward_from.id
                    ban_user_db(bot_id, target_id) 
                    await message.answer(f"🚫 تم حظر المستخدم {target_id} بنجاح.")
                else:
                    await message.answer("❌ لا يمكنني تحديد المستخدم (بسبب خصوصية إعادة التوجيه لديه).")
                return

            # منطق الرد العادي على الرسائل المحولة
            if message.reply_to_message and message.reply_to_message.forward_from:
                target_id = message.reply_to_message.forward_from.id
                try:
                    await bot.copy_message(chat_id=target_id, from_chat_id=message.chat.id, message_id=message.message_id)
                    await message.answer("🚀 تم إرسال ردك للمستخدم.")
                except Exception as e:
                    await message.answer(f"❌ فشل إرسال الرد: {e}")

        # 7. الإذاعة الخاصة بالبوت المصنوع (طلب الرسالة)
        @dp.callback_query(F.data == "mybot_broadcast", F.from_user.id == owner_id)
        async def start_mybot_broadcast(callback: types.CallbackQuery, state: FSMContext):
            await callback.message.answer("📣 أرسل رسالتك الآن ليتم إرسالها لجميع مستخدمي بوتك:")
            await state.set_state(BotSettings.waiting_for_mybot_msg)
            await callback.answer()

        # 8. تنفيذ الإذاعة الخاصة (تم التصحيح هنا ليكون داخل دالة التشغيل)
        @dp.message(F.from_user.id == owner_id, StateFilter(BotSettings.waiting_for_mybot_msg))
        async def perform_mybot_broadcast(message: types.Message, state: FSMContext):
            from database import get_bot_users_for_broadcast
            users = get_bot_users_for_broadcast(bot_id)
            
            success = 0
            for u_id in users:
                try:
                    await bot.copy_message(chat_id=u_id, from_chat_id=message.chat.id, message_id=message.message_id)
                    success += 1
                except: continue
            
            await message.answer(f"✅ تم الإرسال بنجاح إلى {success} مستخدم.")
            await state.clear()

        # 9. معالجات أزرار الإحصائيات والتعليمات
        @dp.callback_query(F.data == "bot_guide")
        async def show_guide(callback: types.CallbackQuery):
            guide_text = (
                "📖 **تعليمات إدارة بوتك:**\n\n"
                "• **للرد:** قم بعمل Reply على رسالة المستخدم واكتب ردك.\n"
                "• **للتحظر:** قم بعمل Reply واكتب كلمة 'حظر'.\n"
                "• **للإذاعة:** استخدم زر الإذاعة لإرسال رسالة للجميع.\n"
                "• **للإحصائيات:** لمعرفة عدد المشتركين في بوتك."
            )
            await callback.message.answer(guide_text, parse_mode="Markdown")
            await callback.answer()

        @dp.callback_query(F.data == "mybot_stats")
        async def show_mybot_stats(callback: types.CallbackQuery):
            stats = get_bot_stats(bot_id) 
            await callback.message.answer(f"📊 إحصائيات بوتك:\n\n👥 عدد المستخدمين: {stats}")
            await callback.answer()

        # تسجيل البوت في الذاكرة والبدء بالاستماع
        active_bots[bot_id] = {"bot": bot, "dp": dp}
        print(f"🚀 البوت {bot_id} انطلق بنجاح للمالك {owner_id}!")
        await dp.start_polling(bot)

    except Exception as e:
        print(f"❌ خطأ فادح في تشغيل البوت {bot_id}: {e}")
