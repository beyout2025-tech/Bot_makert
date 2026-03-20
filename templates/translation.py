# templates/translation.py
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from deep_translator import GoogleTranslator
from database import update_user_points

router = Router()

def register_translation_handlers(dp: Router, bot_id, owner_id, BotSettings):
    
    @router.callback_query(F.data == "start_translate")
    async def start_translation_flow(callback: types.CallbackQuery, state: FSMContext):
        await callback.message.answer("🌐 أرسل الآن النص الذي تريد ترجمته:")
        await state.set_state(BotSettings.waiting_for_translation_text)
        await callback.answer()

    @router.message(StateFilter(BotSettings.waiting_for_translation_text))
    async def process_translation(message: types.Message, state: FSMContext):
        user_data = await state.get_data()
        target = user_data.get("target_lang", "en")
        msg = await message.answer("🔄 جاري الترجمة...")
        try:
            translated = GoogleTranslator(source='auto', target=target).translate(message.text)
            await msg.edit_text(f"✅ **الترجمة:**\n\n`{translated}`", parse_mode="Markdown")
            update_user_points(message.from_user.id, 2)
        except:
            await msg.edit_text("❌ حدث خطأ أثناء الترجمة.")
        await state.clear()

    dp.include_router(router)
