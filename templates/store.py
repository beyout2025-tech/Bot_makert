# templates/store.py
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import bot_db_update_user, update_user_points, get_products, add_order, get_user_orders

router = Router()

def register_store_handlers(dp: Router, bot_id, owner_id):
    
    # 1. عرض المنتجات من قاعدة البيانات
    @router.callback_query(F.data == "view_products")
    async def view_products(callback: types.CallbackQuery):
        products = get_products(bot_id)
        if not products:
            return await callback.message.answer("📦 المتجر فارغ حالياً، يرجى الانتظار لحين إضافة منتجات.")
        
        for p_id, name, price, desc in products:
            kb = InlineKeyboardBuilder()
            kb.row(types.InlineKeyboardButton(text=f"🛒 طلب: {name}", callback_data=f"buy_{p_id}"))
            
            text = f"🛍 **{name}**\n💰 السعر: {price}\n📝 الوصف: {desc}"
            await callback.message.answer(text, reply_markup=kb.as_markup())
        await callback.answer()

    # 2. معالجة عملية الشراء والطلب
    @router.callback_query(F.data.startswith("buy_"))
    async def process_buy(callback: types.CallbackQuery):
        product_id = int(callback.data.split("_")[1])
        # جلب اسم المنتج (تبسيطاً نعتمد على النص في هذه الخطوة)
        product_name = callback.message.text.split("\n")[0]
        
        # [span_11](start_span)حفظ الطلب في القاعدة[span_11](end_span)
        add_order(bot_id, callback.from_user.id, product_name)
        
        # إشعار المستخدم
        await callback.message.answer(f"✅ تم تسجيل طلبك لـ **{product_name}** بنجاح! سيقوم المالك بالتواصل معك.")
        
        # [span_12](start_span)إشعار المالك فوراً[span_12](end_span)
        try:
            order_info = (f"🔔 **طلب جديد في متجرك!**\n"
                          f"👤 العميل: `{callback.from_user.id}`\n"
                          f"📦 المنتج: {product_name}\n"
                          f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            await callback.bot.send_message(owner_id, order_info, parse_mode="Markdown")
        except: pass
        
        update_user_points(callback.from_user.id, 5) # مكافأة الشراء
        await callback.answer()

    # 3. عرض حالة طلبات المستخدم
    @router.callback_query(F.data == "order_status")
    async def order_status(callback: types.CallbackQuery):
        orders = get_user_orders(bot_id, callback.from_user.id)
        if not orders:
            return await callback.message.answer("📦 ليس لديك طلبات سابقة.")
        
        text = "📋 **سجل طلباتك:**\n\n"
        for _, name, status, date in orders:
            text += f"🔹 {name} | الحالة: {status}\n⏰ {date}\n---\n"
        await callback.message.answer(text)
        await callback.answer()

    dp.include_router(router)
