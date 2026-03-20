from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
from aiogram.types import FSInputFile
import os
from aiogram.utils.keyboard import InlineKeyboardBuilder

# استيراد الوظائف من الملفات الفرعية المحدثة
from keyboards import main_menu, cancel_menu, bot_types_menu 
from database import (
    add_bot, init_db, get_all_active_bots, 
    get_user_bots, get_stats, count_user_bots, get_all_users,
    activate_user_subscription, is_subscription_active,
    get_subscription_details, update_user_points,
    get_bot_users_for_broadcast
)
from bot_engine import start_custom_bot

# إعداد قاعدة البيانات عند تشغيل السيرفر لأول مرة
init_db()

# حالات الإدخال للنظام المطور
class BotStates(StatesGroup):
    waiting_for_bot_type = State() 
    waiting_for_token = State()
    waiting_for_broadcast = State()

# --- الإعدادات الأساسية (البوت الأب) ---
# ⚠️ ملاحظة: ADMIN_ID هو المتحكم الكامل في المنصة
ADMIN_ID = 873158772  
bot = Bot(token="7353517186:AAGSFyYX0JgElvaKjbWvS0ZmNh9OtalOGqM")
dp = Dispatcher()

# 1. معالج أمر البداية (Start)
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    is_vip = is_subscription_active(message.from_user.id)
    status_text = "✅ مدفوع (VIP)" if is_vip else "❌ مجاني"
    
    welcome_text = (
        "🔥 **أهلاً بك في منصة صناعة البوتات المتطورة (SaaS)!**\n\n"
        "الآن يمكنك إنشاء بوت تواصل، ترجمة، متجر، أو دعم فني بضغطة زر واحدة.\n\n"
        f"💎 **حالة حسابك حالياً:** {status_text}\n\n"
        "🚀 استخدم الأزرار أدناه للبدء في بناء إمبراطوريتك البرمجية."
    )
    await message.answer(text=welcome_text, reply_markup=main_menu(), parse_mode="Markdown")

# 2. معالج البروفايل المطور
@dp.callback_query(F.data == "profile")
async def profile_handler(callback: types.CallbackQuery):
    sub_data = get_subscription_details(callback.from_user.id)
    expire_date = sub_data[0] if sub_data else None
    points = sub_data[1] if sub_data else 0
    bots_count = count_user_bots(callback.from_user.id)
    
    text = (
        "👤 **معلومات حسابك الاحترافية:**\n\n"
        f"🆔 معرف الحساب: `{callback.from_user.id}`\n"
        f"💰 رصيد النقاط: `{points} نقطة`\n"
        f"🤖 البوتات النشطة: `{bots_count}/3`\n"
        f"📅 انتهاء الاشتراك: `{expire_date if expire_date else 'غير مشترك'}`\n\n"
        "💡 *ملاحظة: يمكنك ترقية حسابك للحصول على ميزات إضافية في بوتاتك.*"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

# 3. معالج زر الإلغاء الشامل
@dp.callback_query(F.data == "cancel_action")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ تم إلغاء العملية والعودة للقائمة الرئيسية.",
        reply_markup=main_menu()
    )
    await callback.answer()

# 4. أوامر المطور (تفعيل VIP وتصفير البيانات)
@dp.message(Command("vip"), F.from_user.id == ADMIN_ID)
async def cmd_activate_vip(message: types.Message):
    try:
        args = message.text.split()
        target_id, days = int(args[1]), int(args[2])
        expire_dt = activate_user_subscription(target_id, days)
        await message.answer(f"✅ تم تفعيل VIP للمستخدم {target_id}\n📅 ينتهي في: {expire_dt}")
        await bot.send_message(target_id, f"🎉 تهانينا! تم تفعيل اشتراكك VIP لمدة {days} يوم.")
    except Exception:
        await message.answer("❌ خطأ! استخدم: `/vip id days` ")

@dp.message(Command("reset_db"), F.from_user.id == ADMIN_ID)
async def reset_database(message: types.Message):
    if os.path.exists("factory.db"):
        os.remove("factory.db")
        await message.answer("✅ تم حذف القاعدة بنجاح. يرجى إعادة تشغيل السيرفر الآن.")
    else:
        await message.answer("❌ الملف غير موجود.")

# 5. منطق إنشاء بوت جديد (تم إتاحة الميزة للجميع)
@dp.callback_query(F.data == "create")
async def create_bot_callback(callback: types.CallbackQuery, state: FSMContext):
    if count_user_bots(callback.from_user.id) >= 3:
        return await callback.answer("⚠️ وصلت للحد الأقصى المسموح به (3 بوتات).", show_alert=True)
    
    await callback.message.edit_text(
        "⚙️ **اختر نوع البوت الذي ترغب في إنشائه الآن:**", 
        reply_markup=bot_types_menu()
    )
    await state.set_state(BotStates.waiting_for_bot_type)
    await callback.answer()

@dp.callback_query(BotStates.waiting_for_bot_type, F.data.startswith("type_"))
async def select_bot_type(callback: types.CallbackQuery, state: FSMContext):
    bot_type = callback.data.split("_")[1]
    await state.update_data(selected_type=bot_type)
    
    await callback.message.edit_text(
        f"✅ تم اختيار نوع: **{bot_type}**\n\n📝 الآن، أرسل **توكن البوت** من @BotFather:",
        reply_markup=cancel_menu()
    )
    await state.set_state(BotStates.waiting_for_token)
    await callback.answer()

# 6. استقبال التوكن وتشغيله وإرسال إشعار للمطور
# ... (نفس الاستيرادات السابقة)

@dp.message(BotStates.waiting_for_token)
async def process_token(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    bot_type = user_data.get("selected_type", "communication")
    user_token = message.text.strip()
    user = message.from_user
    
    msg = await message.answer("🔄 جاري التحقق والتشغيل برمجياً...")
    try:
        temp_bot = Bot(token=user_token)
        bot_info = await temp_bot.get_me()
        await temp_bot.session.close() 
        
        # حفظ في القاعدة
        bot_id = add_bot(message.from_user.id, user_token, bot_type)
        
        # --- [تصحيح] إرسال إشعار للمطور (البوت الأب) ---
        stats = get_stats()
        admin_notify = (
            "تم صنع بوت جديد في الصانع الخاص بك 📝\n"
            "            -----------------------\n"
            "• معلومات عن الشخص الذي صنع البوت .\n\n"
            f"• الاسم : {user.full_name} ،\n"
            f"• المعرف : @{user.username if user.username else 'لا يوجد'} ،\n"
            f"• الايدي : `{user.id}` ،\n"
            "            -----------------------\n"
            f"• نوع البوت المصنوع : {bot_type} ،\n"
            f"• معرف البوت المُنشأ : @{bot_info.username} ،\n"
            "            -----------------------\n\n"
            f"• عدد البوتات المصنوعة : {stats['bots']}"
        )
        # نستخدم الكائن 'bot' الأساسي في main.py للإرسال للمطور
        try:
            await bot.send_message(chat_id=ADMIN_ID, text=admin_notify, parse_mode="Markdown")
        except Exception as e:
            print(f"Admin Notify Error: {e}")

        await msg.edit_text(
            f"✅ تم تشغيل بوت **{bot_type}** بنجاح!\n\n"
            f"🤖 الاسم: **{bot_info.first_name}**\n🔗 المعرف: @{bot_info.username}"
        )
        
        update_user_points(message.from_user.id, 10) 
        asyncio.create_task(start_custom_bot(bot_id, user_token, message.from_user.id, bot_type))
        await state.clear()
    except Exception:
        await msg.edit_text("❌ التوكن غير صحيح أو منتهي.", reply_markup=cancel_menu())


# 7. عرض قائمة "بوتاتي المصنوعة"
@dp.callback_query(F.data == "my_bots")
async def show_my_bots(callback: types.CallbackQuery):
    user_bots = get_user_bots(callback.from_user.id)
    if not user_bots:
        return await callback.answer("🚫 ليس لديك بوتات مصنوعة حالياً.", show_alert=True)
    
    text = "🤖 **قائمة بوتاتك النشطة:**\n\n"
    for b_id, b_name, b_type in user_bots:
        text += f"🔹 معرف: `{b_id}` | النوع: {b_type}\n"
    
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

# 8. الإحصائيات والنسخ الاحتياطي (للمطور فقط)
@dp.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("⚠️ خاص بالمطور فقط.", show_alert=True)
    stats = get_stats()
    await callback.message.answer(f"📊 البوتات النشطة: `{stats['bots']}`\n👥 المستخدمين: `{stats['users']}`")
    await callback.answer()

@dp.callback_query(F.data == "backup")
async def backup_db(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    if os.path.exists("factory.db"):
        await callback.message.answer_document(FSInputFile("factory.db"), caption="📂 نسخة القاعدة الاحترافية.")

# 9. نظام الإذاعة العالمية
@dp.callback_query(F.data == "broadcast")
async def broadcast_cmd(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer(
        "📣 **إذاعة عالمية:** أرسل رسالتك الآن ليتم إرسالها لجميع مستخدمي المنصة وبوتاتها:",
        reply_markup=cancel_menu()
    )
    await state.set_state(BotStates.waiting_for_broadcast)
    await callback.answer()

@dp.message(BotStates.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    main_platform_users = get_all_users()
    main_count = 0
    for u_id in main_platform_users:
        try:
            await bot.copy_message(chat_id=u_id, from_chat_id=message.chat.id, message_id=message.message_id)
            main_count += 1
        except: continue

    all_bots = get_all_active_bots()
    child_count = 0
    for b_id, b_token, b_owner, b_type in all_bots:
        try:
            temp_bot = Bot(token=b_token)
            bot_users = get_bot_users_for_broadcast(b_id)
            for u_id in bot_users:
                try:
                    await temp_bot.copy_message(chat_id=u_id, from_chat_id=message.chat.id, message_id=message.message_id)
                    child_count += 1
                except: continue
            await temp_bot.session.close()
        except: continue
            
    await message.answer(f"✅ اكتملت الإذاعة: {main_count} مستخدم منصة | {child_count} مستخدم بوتات.")
    await state.clear()

# 10. محرك التشغيل التلقائي
async def startup_all_bots():
    existing_bots = get_all_active_bots()
    if existing_bots:
        print(f"📦 جاري إعادة تشغيل {len(existing_bots)} بوت...")
        for bot_id, token, owner_id, b_type in existing_bots:
            asyncio.create_task(start_custom_bot(bot_id, token, owner_id, b_type))
            await asyncio.sleep(0.3)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(startup_all_bots())
    print("🚀 المنصة المصنعة (SaaS) تعمل الآن...")
    try:
        loop.run_until_complete(dp.start_polling(bot))
    except KeyboardInterrupt:
        print("👋 إيقاف النظام.")

