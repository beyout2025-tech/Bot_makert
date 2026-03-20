from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
from aiogram.types import FSInputFile
import os
from aiogram.utils.keyboard import InlineKeyboardBuilder

# استيراد الوظائف من الملفات الفرعية المحدثة
# تم التأكد من جلب كافة الدوال المطلوبة للنظام المطور
from keyboards import main_menu, cancel_menu, bot_types_menu 
from database import (
    add_bot, init_db, get_all_active_bots, 
    get_user_bots, get_stats, count_user_bots, get_all_users,
    activate_user_subscription, is_subscription_active,
    get_subscription_details, update_user_points # الدوال الجديدة لدعم نظام SaaS
)
from bot_engine import start_custom_bot

# إعداد قاعدة البيانات عند تشغيل السيرفر لأول مرة
init_db()

# تطوير حالات الإدخال لتشمل تدفق اختيار "نوع البوت"
class BotStates(StatesGroup):
    waiting_for_bot_type = State() # حالة اختيار النوع (تواصل، ترجمة، إلخ)
    waiting_for_token = State()
    waiting_for_broadcast = State()

# --- الإعدادات الأساسية ---
# ⚠️ ملاحظة: ADMIN_ID هو المتحكم الكامل في صلاحيات المطور
ADMIN_ID = 873158772  
bot = Bot(token="7353517186:AAGSFyYX0JgElvaKjbWvS0ZmNh9OtalOGqM")
dp = Dispatcher()

# 1. معالج أمر البداية (Start) مع عرض حالة الاشتراك الاحترافية
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    # التحقق من حالة الاشتراك لإظهارها في الرسالة الترحيبية
    is_vip = is_subscription_active(message.from_user.id)
    status_text = "✅ مدفوع (VIP)" if is_vip else "❌ مجاني"
    
    welcome_text = (
        "🔥 **أهلاً بك في منصة صناعة البوتات المتطورة (SaaS)!**\n\n"
        "هنا يمكنك إنشاء وإدارة أنواع متعددة من البوتات من مكان واحد، وباحترافية كاملة.\n\n"
        f"💎 **حالة حسابك حالياً:** {status_text}\n\n"
        "💡 **ماذا يمكنك أن تفعل؟**\n"
        "• إنشاء بوتات (تواصل، ترجمة، متجر، دعم).\n"
        "• إدارة رسائل المستخدمين والحظر بالرد.\n"
        "• عمل إذاعة (برودكاست) لمشتركيك."
    )
    await message.answer(text=welcome_text, reply_markup=main_menu(), parse_mode="Markdown")

# 2. معالج البروفايل المطور (يشمل عرض النقاط وتاريخ الاشتراك)
@dp.callback_query(F.data == "profile")
async def profile_handler(callback: types.CallbackQuery):
    # جلب التاريخ والنقاط من الدالة المحدثة في قاعدة البيانات
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
        "💡 *ملاحظة: النقاط تمنحك ميزات إضافية وخصومات عند التجديد.*"
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

# 4. أوامر المطور (تفعيل VIP وتصفير قاعدة البيانات)
@dp.message(Command("vip"), F.from_user.id == ADMIN_ID)
async def cmd_activate_vip(message: types.Message):
    try:
        args = message.text.split()
        target_id, days = int(args[1]), int(args[2])
        expire_dt = activate_user_subscription(target_id, days)
        await message.answer(f"✅ تم تفعيل VIP للمستخدم {target_id}\n📅 ينتهي في: {expire_dt}")
        await bot.send_message(target_id, f"🎉 تهانينا! تم تفعيل اشتراكك VIP لمدة {days} يوم.")
    except Exception:
        await message.answer("❌ خطأ! استخدم: `/vip id days`")

@dp.message(Command("reset_db"), F.from_user.id == ADMIN_ID)
async def reset_database(message: types.Message):
    if os.path.exists("factory.db"):
        os.remove("factory.db")
        await message.answer("✅ تم حذف القاعدة بنجاح. يرجى إعادة تشغيل السيرفر الآن.")
    else:
        await message.answer("❌ الملف غير موجود.")

# 5. منطق إنشاء بوت جديد (تدفق SaaS: فحص -> اختيار نوع -> توكن)
@dp.callback_query(F.data == "create")
async def create_bot_callback(callback: types.CallbackQuery, state: FSMContext):
    # 1. فحص الاشتراك
    if not is_subscription_active(callback.from_user.id):
        return await callback.message.answer("⚠️ هذه الميزة للمشتركين VIP فقط.", show_alert=True)
    
    # 2. فحص الحد الأقصى
    if count_user_bots(callback.from_user.id) >= 3:
        return await callback.answer("⚠️ وصلت للحد الأقصى المسموح به (3 بوتات).", show_alert=True)
    
    # 3. عرض قائمة أنواع البوتات
    await callback.message.edit_text(
        "⚙️ **اختر نوع البوت الذي ترغب في إنشائه الآن:**", 
        reply_markup=bot_types_menu()
    )
    await state.set_state(BotStates.waiting_for_bot_type)
    await callback.answer()

# معالج اختيار النوع
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

# 6. استقبال التوكن وتشغيله بالنوع المحدد
@dp.message(BotStates.waiting_for_token)
async def process_token(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    bot_type = user_data.get("selected_type", "communication")
    user_token = message.text.strip()
    
    msg = await message.answer("🔄 جاري التحقق والتشغيل برمجياً...")
    try:
        temp_bot = Bot(token=user_token)
        bot_info = await temp_bot.get_me()
        await temp_bot.session.close() 
        
        # حفظ في القاعدة مع النوع المختار
        bot_id = add_bot(message.from_user.id, user_token, bot_type)
        
        await msg.edit_text(
            f"✅ تم تشغيل بوت **{bot_type}** بنجاح!\n\n"
            f"🤖 الاسم: **{bot_info.first_name}**\n🔗 المعرف: @{bot_info.username}"
        )
        
        # مكافأة المستخدم بنقاط عند الإنشاء الناجح
        update_user_points(message.from_user.id, 10)
        
        # تصحيح: تمرير النوع للمحرك لضمان الرد المناسب
        asyncio.create_task(start_custom_bot(bot_id, user_token, message.from_user.id, bot_type))
        await state.clear()
    except Exception:
        await msg.edit_text("❌ التوكن غير صحيح أو منتهي. حاول مجدداً.", reply_markup=cancel_menu())

# 7. عرض قائمة "بوتاتي المصنوعة"
@dp.callback_query(F.data == "my_bots")
async def show_my_bots(callback: types.CallbackQuery):
    user_bots = get_user_bots(callback.from_user.id)
    if not user_bots:
        return await callback.answer("🚫 ليس لديك بوتات مصنوعة حالياً.", show_alert=True)
    
    text = "🤖 **قائمة بوتاتك النشطة:**\n\n"
    for b_id, b_name in user_bots:
        # b[2] يمثل نوع البوت في قاعدة البيانات المحدثة
        text += f"🔹 معرف السجل: `{b_id}` | النوع: {b_name}\n"
    
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

# 9. نظام الإذاعة العامة
@dp.callback_query(F.data == "broadcast")
async def broadcast_cmd(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.answer("📣 أرسل رسالة الإذاعة:", reply_markup=cancel_menu())
    await state.set_state(BotStates.waiting_for_broadcast)

@dp.message(BotStates.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    users = get_all_users(); count, skipped = 0, 0
    for u_id in users:
        if is_subscription_active(u_id):
            skipped += 1; continue 
        try:
            await bot.copy_message(chat_id=u_id, from_chat_id=message.chat.id, message_id=message.message_id)
            count += 1
        except: continue
    await message.answer(f"✅ تم الإرسال لـ {count} مستخدم | استثناء {skipped} VIP")
    await state.clear()

# 10. محرك التشغيل التلقائي المطور (تمرير 4 قيم)
async def startup_all_bots():
    existing_bots = get_all_active_bots()
    if existing_bots:
        print(f"📦 جاري إعادة تشغيل {len(existing_bots)} بوت بأنواعها المختلفة...")
        for bot_id, token, owner_id, b_type in existing_bots: # تصحيح عدد القيم المستلمة
            asyncio.create_task(start_custom_bot(bot_id, token, owner_id, b_type))
            await asyncio.sleep(0.3)

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(startup_all_bots())
    print("🚀 المنصة المصنعة (SaaS) تعمل الآن بكامل طاقتها...")
    try:
        loop.run_until_complete(dp.start_polling(bot))
    except KeyboardInterrupt:
        print("👋 إيقاف.")
