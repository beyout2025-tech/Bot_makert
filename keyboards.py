# ملف keyboards.py
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder

def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="➕ إنشاء بوت جديد", callback_data="create"),
        types.InlineKeyboardButton(text="🤖 بوتاتي المصنوعة", callback_data="my_bots")
    )
    builder.row(
        types.InlineKeyboardButton(text="📢 إذاعة عامة", callback_data="broadcast"),
        types.InlineKeyboardButton(text="📊 الإحصائيات", callback_data="stats")
    )
    builder.row(
        types.InlineKeyboardButton(text="📥 نسخة احتياطية", callback_data="backup"),
        types.InlineKeyboardButton(text="📤 رفع نسخة", callback_data="restore")
    )
    # تعديل بسيط: جعل الأزرار تظهر بشكل مرتب (زرين في كل صف)
    builder.adjust(2) 
    return builder.as_markup()

