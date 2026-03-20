import sqlite3
from datetime import datetime, timedelta

# 1. تهيئة قاعدة البيانات عند تشغيل السيرفر لأول مرة
def init_db():
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    # جدول البوتات المصنوعة
    c.execute('''CREATE TABLE IF NOT EXISTS bots 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER, 
                  token TEXT, 
                  welcome_msg TEXT, 
                  status INTEGER DEFAULT 1)''')
    
    # جدول مستخدمي المنصة (البوت الصانع) - تم إضافة عمود expiry_date لتفعيل النظام المدفوع
    c.execute('''CREATE TABLE IF NOT EXISTS platform_users 
             (user_id INTEGER PRIMARY KEY, expiry_date TEXT)''')

    # جدول مستخدمين كل بوت مصنوع (لعمل الإذاعة والحظر داخل كل بوت)
    c.execute('''CREATE TABLE IF NOT EXISTS bot_users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  bot_id INTEGER, 
                  user_id INTEGER, 
                  is_banned INTEGER DEFAULT 0)''')
    
    conn.commit()
    conn.close()

# 2. إضافة بوت جديد لقاعدة البيانات
def add_bot(user_id, token):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("INSERT INTO bots (user_id, token, welcome_msg) VALUES (?, ?, ?)", 
              (user_id, token, "مرحباً بك في بوت التواصل الخاص بنا!"))
    # تسجيل المستخدم في المنصة إذا لم يكن موجوداً
    c.execute("INSERT OR IGNORE INTO platform_users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    bot_id = c.lastrowid
    conn.close()
    return bot_id

# 3. جلب جميع البوتات النشطة لتشغيلها عند إقلاع السيرفر
def get_all_active_bots():
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT id, token, user_id FROM bots WHERE status = 1")
    bots = c.fetchall()
    conn.close()
    return bots

# 4. جلب بوتات مستخدم معين (لميزة "بوتاتي المصنوعة")
def get_user_bots(user_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT id, token FROM bots WHERE user_id = ?", (user_id,))
    bots = c.fetchall()
    conn.close()
    return [(b[0], f"Bot_{str(b[1])[:5]}...") for b in bots]

# 5. جلب إحصائيات المنصة (للمطور)
def get_stats():
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM bots WHERE status = 1")
    bots_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM platform_users")
    users_count = c.fetchone()[0]
    conn.close()
    return {"bots": bots_count, "users": users_count}

# 6. جلب جميع مستخدمي المنصة (لميزة الإذاعة العامة)
def get_all_users():
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM platform_users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

# 7. تحديث/إضافة مستخدم للبوت المصنوع (لغرض الإذاعة)
def bot_db_update_user(bot_id, user_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO bot_users (bot_id, user_id) VALUES (?, ?)", (bot_id, user_id))
    conn.commit()
    conn.close()

# 8. حظر مستخدم من بوت معين
def ban_user_db(bot_id, user_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("UPDATE bot_users SET is_banned = 1 WHERE bot_id = ? AND user_id = ?", (bot_id, user_id))
    conn.commit()
    conn.close()

# 9. التحقق هل المستخدم محظور في هذا البوت؟
def is_user_banned(bot_id, user_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT is_banned FROM bot_users WHERE bot_id = ? AND user_id = ?", (bot_id, user_id))
    result = c.fetchone()
    conn.close()
    return result is not None and result[0] == 1

# 10. جلب إحصائيات البوت المصنوع (عدد مستخدميه)
def get_bot_stats(bot_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM bot_users WHERE bot_id = ?", (bot_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

# 11. جلب قائمة المستخدمين لبوت معين (لعمل إذاعة خاصة بصاحب البوت)
def get_bot_users_for_broadcast(bot_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM bot_users WHERE bot_id = ? AND is_banned = 0", (bot_id,))
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

# 12. تحديث رسالة الترحيب
def update_welcome_msg(bot_id, new_msg):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("UPDATE bots SET welcome_msg = ? WHERE id = ?", (new_msg, bot_id))
    conn.commit()
    conn.close()

# 13. جلب رسالة الترحيب
def get_welcome_msg(bot_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT welcome_msg FROM bots WHERE id = ?", (bot_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else "مرحباً بك!"

# 14. حساب عدد البوتات لكل مستخدم
def count_user_bots(user_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM bots WHERE user_id = ?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

# 15. تفعيل اشتراك مستخدم (تم التعديل لضمان الإضافة الفورية)
def activate_user_subscription(user_id, days):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    expire_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    # استخدام INSERT OR REPLACE لضمان تحديث البيانات حتى لو كان المستخدم جديداً
    c.execute("INSERT OR REPLACE INTO platform_users (user_id, expiry_date) VALUES (?, ?)", 
              (user_id, expire_date))
    conn.commit()
    conn.close()
    return expire_date

# 16. التحقق من صلاحية الاشتراك
def is_subscription_active(user_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT expiry_date FROM platform_users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    
    if row and row[0] is not None:
        try:
            expire_date = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
            return datetime.now() < expire_date
        except ValueError:
            return False
    return False
