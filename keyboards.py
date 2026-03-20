# ملف keyboards.py المطور للمنصة الاحترافية
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder

# 1. القائمة الرئيسية (كما أرسلتها مع الحفاظ على كافة الأزرار)
def main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="➕ إنشاء بوت جديد", callback_data="create"),
        types.InlineKeyboardButton(text="🤖 بوتاتي المصنوعة", callback_data="my_bots")
    )
    builder.row(
        types.InlineKeyboardButton(text="👤 بروفايلي", callback_data="profile"),
        types.InlineKeyboardButton(text="📊 الإحصائيات", callback_data="stats")
    )
    builder.row(
        types.InlineKeyboardButton(text="📢 إذاعة عامة", callback_data="broadcast"),
        types.InlineKeyboardButton(text="📥 نسخة احتياطية", callback_data="backup")
    )
    builder.adjust(2) 
    return builder.as_markup()

# 2. قائمة الإلغاء (لضمان تجربة مستخدم سلسة)
def cancel_menu():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="❌ إلغاء العملية", callback_data="cancel_action"))
    return builder.as_markup()

# 3. قائمة أنواع البوتات (إضافة جديدة لدعم نظام SaaS)
def bot_types_menu():
    builder = InlineKeyboardBuilder()
    # إضافة الأنواع الخمسة المذكورة في خطة التطوير
    builder.row(
        types.InlineKeyboardButton(text="💬 بوت تواصل", callback_data="type_communication"),
        types.InlineKeyboardButton(text="🌐 بوت ترجمة", callback_data="type_translation")
    )
    builder.row(
        types.InlineKeyboardButton(text="🛒 بوت متجر", callback_data="type_store"),
        types.InlineKeyboardButton(text="🎧 بوت دعم (تذاكر)", callback_data="type_support")
    )
    builder.row(
        types.InlineKeyboardButton(text="📚 بوت تعليم", callback_data="type_education")
    )
    # زر للرجوع في حال غير المستخدم رأيه
    builder.row(types.InlineKeyboardButton(text="🔙 العودة للقائمة", callback_data="cancel_action"))
    builder.adjust(2)
    return builder.as_markup()

# 4. قائمة "الرجوع" السريعة (تستخدم في البروفايل أو الإحصائيات)
def back_menu():
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="🔙 عودة", callback_data="cancel_action"))
    return builder.as_markup()
