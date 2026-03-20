# templates/store.py
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from database import bot_db_update_user, update_user_points

router = Router()

def register_store_handlers(dp: Router, bot_id, owner_id):
    
    # معالج عرض المنتجات
    @router.callback_query(F.data == "view_products")
    async def view_products(callback: types.CallbackQuery):
        # في هذه المرحلة نعرض رسالة ثابتة، وفي الخطوات القادمة سنربطها بقاعدة البيانات
        text = (
            "🛒 **مرحباً بك في المتجر!**\n\n"
            "المنتجات المتاحة حالياً:\n"
            "1️⃣ منتج تجريبي 1 - السعر: 50$\n"
            "2️⃣ منتج تجريبي 2 - السعر: 100$\n\n"
            "💡 للطلب، يرجى التواصل مع الإدارة مباشرة."
        )
        await callback.message.answer(text, parse_mode="Markdown")
        await callback.answer()

    # معالج حالة الطلب
    @router.callback_query(F.data == "order_status")
    async def order_status(callback: types.CallbackQuery):
        await callback.message.answer("📦 ليس لديك طلبات نشطة حالياً.")
        await callback.answer()

    dp.include_router(router)
