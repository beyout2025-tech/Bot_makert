from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
from aiogram.types import FSInputFile
import os
from aiogram.utils.keyboard import InlineKeyboardBuilder

# استيراد الوظائف من الملفات الفرعية المحدثة
from keyboards import main_menu, cancel_menu 
from database import (
    add_bot, init_db, get_all_active_bots, 
    get_user_bots, get_stats, count_user_bots, get_all_users,
    activate_user_subscription, is_subscription_active,
    get_subscription_details, update_user_points # الدوال الجديدة
)
from bot_engine import start_custom_bot

# إعداد قاعدة البيانات عند تشغيل السيرفر
init_db()

# تطوير حالات الإدخال لتشمل "نوع البوت"
class BotStates(StatesGroup):
    waiting_for_bot_type = State() # حالة اختيار النوع
    waiting_for_token = State()
    waiting_for_broadcast = State()

# --- الإعدادات الأساسية ---
ADMIN_ID = 873158772  
bot = Bot(token="7353517186:AAGSFyYX0JgElvaKjbWvS0ZmNh9OtalOGqM")
dp = Dispatcher()

# دالة مساعدة لإنشاء أزرار أنواع البوتات
def bot_types_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💬 بوت تواصل", callback_data="type_communication"))
    builder.row(types.InlineKeyboardButton(text="🌐 بوت ترجمة", callback_data="type_translation"))
    builder.row(types.InlineKeyboardButton(text="🛒 بوت متجر", callback_data="type_store"))
    builder.row(types.InlineKeyboardButton(text="🎧 بوت دعم (تذاكر)", callback_data="type_support"))
    builder.row(types.InlineKeyboardButton(text="❌ إلغاء", callback_data="cancel_action"))
    builder.adjust(2)
    return builder.as_markup()

# 1. معالج أمر البداية المطور
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    is_vip = is_subscription_active(message.from_user.id)
    status_text = "✅ مدفوع (VIP)" if is_vip else "❌ مجاني"
    
    welcome_text = (
        "🔥 **أهلاً بك في منصة صناعة البوتات المتطورة (SaaS)!**\n\n"
        "يمكنك الآن إنشاء وإدارة أنواع متعددة من البوتات من مكان واحد.\n\n"
        f"💎 **حالة حسابك:** {status_text}\n"
        "🚀 اختر من القائمة أدناه لبدء رحلتك."
    )
    await message.answer(text=welcome_text, reply_markup=main_menu(), parse_mode="Markdown")

# 2. معالج البروفايل المطور (يشمل النقاط)
@dp.callback_query(F.data == "profile")
async def profile_handler(callback: types.CallbackQuery):
    # جلب التاريخ والنقاط من الدالة المحدثة
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
        "💡 *ملاحظة: النقاط تمكنك من الحصول على ميزات إضافية قريباً.*"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

# 3. معالج زر الإلغاء
@dp.callback_query(F.data == "cancel_action")
async def cancel_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ تم إلغاء العملية والعودة للقائمة.", reply_markup=main_menu())
    await callback.answer()

# 4. أوامر المطور (VIP & Reset)
@dp.message(Command("vip"), F.from_user.id == ADMIN_ID)
async def cmd_activate_vip(message: types.Message):
    try:
        args = message.text.split()
        target_id, days = int(args[1]), int(args[2])
        expire_dt = activate_user_subscription(target_id, days)
        await message.answer(f"✅ تم التفعيل لـ {target_id}\n📅 ينتهي في: {expire_dt}")
        await bot.send_message(target_id, f"🎉 تم تفعيل اشتراكك VIP لمدة {days} يوم!")
    except: await message.answer("❌ استخدم: `/vip id days`")

@dp.message(Command("reset_db"), F.from_user.id == ADMIN_ID)
async def reset_database(message: types.Message):
    if os.path.exists("factory.db"):
        os.remove("factory.db")
        await message.answer("✅ تم حذف القاعدة. يرجى إعادة تشغيل السيرفر.")
    else: await message.answer("❌ الملف غير موجود.")

# 5. منطق الإنشاء المطور (اختيار النوع)
@dp.callback_query(F.data == "create")
async def create_bot_callback(callback: types.CallbackQuery, state: FSMContext):
    if not is_subscription_active(callback.from_user.id):
        return await callback.message.answer("⚠️ هذه الميزة للمشتركين VIP فقط.", show_alert=True)
    
    if count_user_bots(callback.from_user.id) >= 3:
        return await callback.answer("⚠️ وصلت للحد الأقصى (3 بوتات).", show_alert=True)
    
    await callback.message.edit_text("⚙️ **اختر نوع البوت الذي ترغب في إنشائه:**", reply_markup=bot_types_keyboard())
    await state.set_state(BotStates.waiting_for_bot_type)
    await callback.answer()

# معالج اختيار النوع
@dp.callback_query(BotStates.waiting_for_bot_type, F.data.startswith("type_"))
async def select_bot_type(callback: types.CallbackQuery, state: FSMContext):
    bot_type = callback.data.split("_")[1]
    await state.update_data(selected_type=bot_type)
    
    await callback.message.edit_text(
        f"✅ اخترت نوع: **{bot_type}**\n\n📝 الآن، من فضلك أرسل **التوكن** من @BotFather:",
        reply_markup=cancel_menu()
    )
    await state.set_state(BotStates.waiting_for_token)
    await callback.answer()

# 6. استقبال التوكن والتشغيل بالنوع المحدد
@dp.message(BotStates.waiting_for_token)
async def process_token(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    bot_type = user_data.get("selected_type", "communication")
    user_token = message.text.strip()
    
    msg = await message.answer("🔄 جاري التحقق والتشغيل...")
    try:
        temp_bot = Bot(token=user_token)
        bot_info = await temp_bot.get_me()
        await temp_bot.session.close() 
        
        # حفظ في القاعدة مع النوع
        bot_id = add_bot(message.from_user.id, user_token, bot_type)
        
        await msg.edit_text(
            f"✅ تم تشغيل بوت **{bot_type}** بنجاح!\n\n"
            f"🤖 الاسم: {bot_info.first_name}\n🔗 المعرف: @{bot_info.username}"
        )
        
        # منح المستخدم نقاط كهدية عند الإنشاء
        update_user_points(message.from_user.id, 10)
        
        asyncio.create_task(start_custom_bot(bot_id, user_token, message.from_user.id))
        await state.clear()
    except: await msg.edit_text("❌ التوكن غير صحيح.")

# 7. بوتاتي المصنوعة
@dp.callback_query(F.data == "my_bots")
async def show_my_bots(callback: types.CallbackQuery):
    user_bots = get_user_bots(callback.from_user.id)
    if not user_bots: return await callback.answer("🚫 لا يوجد بوتات.", show_alert=True)
    text = "🤖 **قائمة بوتاتك:**\n\n" + "\n".join([f"🔹 {b[0]} | النوع: {b[1]}" for b in user_bots])
    await callback.message.answer(text); await callback.answer()

# 8. الإحصائيات والنسخ الاحتياطي والإذاعة (للمطور)
@dp.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return await callback.answer("⚠️ للمطور فقط.", show_alert=True)
    s = get_stats()
    await callback.message.answer(f"📊 البوتات: {s['bots']}\n👥 المستخدمين: {s['users']}")

@dp.callback_query(F.data == "backup")
async def backup_db(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    if os.path.exists("factory.db"):
        await callback.message.answer_document(FSInputFile("factory.db"), caption="📂 نسخة القاعدة.")

@dp.callback_query(F.data == "broadcast")
async def broadcast_cmd(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("📣 أرسل رسالة الإذاعة:", reply_markup=cancel_menu())
    await state.set_state(BotStates.waiting_for_broadcast)

@dp.message(BotStates.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    users = get_all_users(); count, skipped = 0, 0
    for u_id in users:
        if is_subscription_active(u_id): skipped += 1; continue 
        try: await bot.copy_message(chat_id=u_id, from_chat_id=message.chat.id, message_id=message.message_id); count += 1
        except: continue
    await message.answer(f"✅ تم الإرسال لـ {count} مستخدم | استثناء {skipped} VIP"); await state.clear()

# --- التشغيل التلقائي ---
async def startup_all_bots():
    existing_bots = get_all_active_bots()
    if existing_bots:
        for bot_id, token, owner_id, b_type in existing_bots:
            asyncio.create_task(start_custom_bot(bot_id, token, owner_id))
            await asyncio.sleep(0.3)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(startup_all_bots())
    print("🚀 المنصة المصنعة (SaaS) تعمل الآن...")
    try: loop.run_until_complete(dp.start_polling(bot))
    except KeyboardInterrupt: print("👋 إيقاف.")
