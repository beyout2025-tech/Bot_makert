from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import asyncio
from aiogram.types import FSInputFile
import os

# استيراد الوظائف من الملفات الفرعية
from keyboards import main_menu 
from database import (
    add_bot, init_db, get_all_active_bots, 
    get_user_bots, get_stats, count_user_bots, get_all_users,
    activate_user_subscription, is_subscription_active # أضف هذه السطور
) # تم التأكد من جلب كافة الدوال المطلوبة
from bot_engine import start_custom_bot

# إعداد قاعدة البيانات عند تشغيل السيرفر
init_db()

class BotStates(StatesGroup):
    waiting_for_token = State()
    waiting_for_broadcast = State()

# --- الإعدادات الأساسية ---
# ⚠️ ملاحظة: يجب استبدال ADMIN_ID بالرقم الحقيقي الخاص بك لتفعيل صلاحيات المطور
ADMIN_ID = 873158772  
bot = Bot(token="7353517186:AAGSFyYX0JgElvaKjbWvS0ZmNh9OtalOGqM")
dp = Dispatcher()

# 1. معالج أمر البداية مع رسالة ترحيب احترافية
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    welcome_text = (
        "🔥 **أهلاً بك في منصة صناعة البوتات المتطورة!**\n\n"
        "هنا يمكنك إنشاء بوت تواصل خاص بك بضغطة زر، وإدارته بالكامل من هنا.\n\n"
        "💡 **ماذا يمكنك أن تفعل؟**\n"
        "• إنشاء بوتات تواصل احترافية.\n"
        "• إدارة رسائل المستخدمين والحظر بالرد.\n"
        "• عمل إذاعة (برودكاست) لمشتركيك."
    )
    await message.answer(text=welcome_text, reply_markup=main_menu(), parse_mode="Markdown")

# أمر التفعيل: /vip user_id days
@dp.message(Command("vip"), F.from_user.id == ADMIN_ID)
async def cmd_activate_vip(message: types.Message):
    try:
        args = message.text.split()
        target_id = int(args[1])
        days = int(args[2])
        
        expire_dt = activate_user_subscription(target_id, days)
        
        # إشعار المطور
        await message.answer(f"✅ تم تفعيل الاشتراك للمستخدم {target_id}\n📅 ينتهي في: {expire_dt}")
        
        # إشعار المستخدم
        await bot.send_message(target_id, f"🎉 تهانينا! تم تفعيل اشتراكك في المنصة لمدة {days} يوم.\n🚀 يمكنك الآن إنشاء بوتاتك.")
    except Exception as e:
        await message.answer("❌ خطأ في الصيغة. استخدم: `/vip id days`")

# 2. منطق إنشاء بوت جديد (مع نظام الحدود المتكامل)
@dp.callback_query(F.data == "create")
async def create_bot_callback(callback: types.CallbackQuery, state: FSMContext):
    # 1. التحقق أولاً: هل المشترك دفع وقمت أنت بتفعيله؟
    if not is_subscription_active(callback.from_user.id):
        return await callback.message.answer(
            "⚠️ **عذراً، خدمة إنشاء البوتات متاحة للمشتركين فقط.**\n\n"
            "للاشتراك وتفعيل حسابك، يرجى التواصل مع الإدارة.",
            show_alert=True
        )

    # 2. التحقق ثانياً: هل تخطى عدد البوتات المسموحة؟
    current_count = count_user_bots(callback.from_user.id)
    LIMIT = 3 # الحد الأقصى للبوتات لكل مستخدم
    
    if current_count >= LIMIT:
        return await callback.answer(f"⚠️ عذراً، لقد وصلت للحد الأقصى المسموح به ({LIMIT} بوتات).", show_alert=True)
    
    # إذا اجتاز الشرطين، نفتح له عملية الإنشاء
    await callback.message.edit_text("📝 من فضلك أرسل الآن **توكن البوت** (Token) من @BotFather:")
    await state.set_state(BotStates.waiting_for_token)
    await callback.answer()


# 3. معالج استقبال التوكن والتحقق منه وحفظه وتشغيله
@dp.message(BotStates.waiting_for_token)
async def process_token(message: types.Message, state: FSMContext):
    user_token = message.text.strip()
    checking_msg = await message.answer("🔄 جاري التحقق من صحة التوكن وتشغيله...")
    
    try:
        # التحقق من صحة التوكن عبر API تليجرام
        temp_bot = Bot(token=user_token)
        bot_info = await temp_bot.get_me()
        await temp_bot.session.close() 
        
        # حفظ بيانات البوت في قاعدة البيانات
        bot_id = add_bot(message.from_user.id, user_token)
        
        await checking_msg.edit_text(
            f"✅ تم تشغيل بوتك بنجاح!\n\n"
            f"🤖 الاسم: **{bot_info.first_name}**\n"
            f"🔗 المعرف: @{bot_info.username}\n\n"
            f"🚀 البوت الآن في وضع الاستعداد لاستقبال الرسائل."
        )
        
        # تشغيل محرك البوت المصنوع فوراً في الخلفية
        asyncio.create_task(start_custom_bot(bot_id, user_token, message.from_user.id))
        await state.clear()
        
    except Exception as e:
        await checking_msg.edit_text(f"❌ التوكن غير صحيح أو منتهي الصلاحية. حاول مرة أخرى.")

# 4. عرض قائمة "بوتاتي المصنوعة"
@dp.callback_query(F.data == "my_bots")
async def show_my_bots(callback: types.CallbackQuery):
    user_bots = get_user_bots(callback.from_user.id)
    if not user_bots:
        return await callback.answer("🚫 ليس لديك بوتات مصنوعة حالياً.", show_alert=True)
    
    text = "🤖 **قائمة بوتاتك النشطة:**\n\n"
    for b_id, b_name in user_bots:
        text += f"🔹 معرف: {b_id} | اسم: {b_name}\n"
    
    await callback.message.answer(text)
    await callback.answer()

# 5. ميزة الإحصائيات (للمطور فقط)
@dp.callback_query(F.data == "stats")
async def show_stats(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        return await callback.answer("⚠️ عذراً، هذا القسم خاص بمطور المنصة فقط.", show_alert=True)
    
    stats = get_stats()
    await callback.message.answer(
        f"📊 **إحصائيات المنصة الشاملة:**\n\n"
        f"✅ عدد البوتات النشطة: {stats['bots']}\n"
        f"👥 عدد مستخدمي المنصة: {stats['users']}"
    )
    await callback.answer()

# 6. نظام النسخة الاحتياطية (للمطور فقط)
@dp.callback_query(F.data == "backup")
async def backup_db(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: 
        return await callback.answer("⚠️ صلاحية النسخ الاحتياطي للمطور فقط.", show_alert=True)
    
    if os.path.exists("factory.db"):
        document = FSInputFile("factory.db")
        await callback.message.answer_document(document, caption="📂 نسخة احتياطية لقاعدة البيانات (Factory Backup).")
        await callback.answer("تم استخراج النسخة بنجاح ✅")
    else:
        await callback.answer("❌ خطأ: قاعدة البيانات غير موجودة.")

# 7. نظام الإذاعة العامة (للمطور فقط)
@dp.callback_query(F.data == "broadcast")
async def broadcast_cmd(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: 
        return await callback.answer("⚠️ صلاحية الإذاعة للمطور فقط.", show_alert=True)
        
    await callback.message.answer("📣 من فضلك أرسل الرسالة التي تود إذاعتها لجميع مستخدمي المنصة:")
    await state.set_state(BotStates.waiting_for_broadcast)
    await callback.answer()

@dp.message(BotStates.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    from database import get_all_users, is_subscription_active
    
    users = get_all_users() # جلب كافة مستخدمي المنصة
    count = 0
    skipped = 0
    
    for u_id in users:
        # الفلتر الذكي: إذا كان اشتراكه سارياً، نتخطاه ولا نرسل له الإذاعة
        if is_subscription_active(u_id):
            skipped += 1
            continue 
            
        try: 
            # الإرسال للمستخدمين المجانيين فقط
            await bot.copy_message(chat_id=u_id, from_chat_id=message.chat.id, message_id=message.message_id)
            count += 1
        except: 
            continue
            
    await message.answer(
        f"✅ **اكتملت الإذاعة بنجاح!**\n\n"
        f"👥 تم الإرسال إلى: {count} مستخدم (مجاني).\n"
        f"💎 تم استثناء: {skipped} مستخدم (VIP/مدفوع)."
    )
    await state.clear()

# --- محرك التشغيل التلقائي لجميع البوتات عند الإقلاع ---
async def startup_all_bots():
    existing_bots = get_all_active_bots()
    if existing_bots:
        print(f"📦 جاري إعادة تشغيل {len(existing_bots)} بوت من قاعدة البيانات...")
        for bot_id, token, owner_id in existing_bots:
            asyncio.create_task(start_custom_bot(bot_id, token, owner_id))
            await asyncio.sleep(0.3) # تأخير بسيط لتفادي حظر الـ Flood من تليجرام

# تشغيل البوت الرئيسي والبدء بالاستماع
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    # تشغيل مهمة إعادة تشغيل البوتات السابقة في الخلفية
    loop.create_task(startup_all_bots())
    print("🚀 المنصة المصنعة تعمل الآن بكامل طاقتها...")
    
    try:
        loop.run_until_complete(dp.start_polling(bot))
    except KeyboardInterrupt:
        print("👋 تم إيقاف النظام يدوياً.")
