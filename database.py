import sqlite3
import json
from datetime import datetime, timedelta

# 1. تهيئة قاعدة البيانات (تحديث الجداول لدعم SaaS)
def init_db():
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    # جدول البوتات: أضفنا bot_type و config
    c.execute('''CREATE TABLE IF NOT EXISTS bots 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  user_id INTEGER, 
                  token TEXT, 
                  welcome_msg TEXT, 
                  bot_type TEXT DEFAULT 'communication', 
                  config TEXT,
                  status INTEGER DEFAULT 1)''')
    
    # جدول مستخدمي المنصة: أضفنا points
    c.execute('''CREATE TABLE IF NOT EXISTS platform_users 
             (user_id INTEGER PRIMARY KEY, expiry_date TEXT, points INTEGER DEFAULT 0)''')

    # جدول مستخدمين كل بوت مصنوع
    c.execute('''CREATE TABLE IF NOT EXISTS bot_users 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  bot_id INTEGER, 
                  user_id INTEGER, 
                  is_banned INTEGER DEFAULT 0)''')
    
    conn.commit()
    conn.close()

# 2. إضافة بوت جديد (يدعم اختيار النوع)
def add_bot(user_id, token, bot_type="communication"):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    # الإعدادات الافتراضية تكون عبارة عن JSON فارغ
    default_config = json.dumps({}) 
    c.execute("INSERT INTO bots (user_id, token, welcome_msg, bot_type, config) VALUES (?, ?, ?, ?, ?)", 
              (user_id, token, "مرحباً بك في بوتنا الجديد!", bot_type, default_config))
    c.execute("INSERT OR IGNORE INTO platform_users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    bot_id = c.lastrowid
    conn.close()
    return bot_id

# 3. جلب جميع البوتات النشطة مع أنواعها
def get_all_active_bots():
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT id, token, user_id, bot_type FROM bots WHERE status = 1")
    bots = c.fetchall()
    conn.close()
    return bots

# 4. جلب بوتات مستخدم معين مع النوع
def get_user_bots(user_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT id, token, bot_type FROM bots WHERE user_id = ?", (user_id,))
    bots = c.fetchall()
    conn.close()
    return [(b[0], f"{b[2].capitalize()}_{str(b[1])[:5]}...") for b in bots]

# 5. جلب إحصائيات المنصة
def get_stats():
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM bots WHERE status = 1")
    bots_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM platform_users")
    users_count = c.fetchone()[0]
    conn.close()
    return {"bots": bots_count, "users": users_count}

# 6. جلب جميع مستخدمي المنصة
def get_all_users():
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM platform_users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

# 7. تحديث مستخدم البوت المصنوع
def bot_db_update_user(bot_id, user_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO bot_users (bot_id, user_id) VALUES (?, ?)", (bot_id, user_id))
    conn.commit()
    conn.close()

# 8. حظر مستخدم
def ban_user_db(bot_id, user_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("UPDATE bot_users SET is_banned = 1 WHERE bot_id = ? AND user_id = ?", (bot_id, user_id))
    conn.commit()
    conn.close()

# 9. التحقق من الحظر
def is_user_banned(bot_id, user_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT is_banned FROM bot_users WHERE bot_id = ? AND user_id = ?", (bot_id, user_id))
    result = c.fetchone()
    conn.close()
    return result is not None and result[0] == 1

# 10. إحصائيات البوت المصنوع
def get_bot_stats(bot_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM bot_users WHERE bot_id = ?", (bot_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

# 11. مستخدمي الإذاعة
def get_bot_users_for_broadcast(bot_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM bot_users WHERE bot_id = ? AND is_banned = 0", (bot_id,))
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

# 12. تحديث الترحيب
def update_welcome_msg(bot_id, new_msg):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("UPDATE bots SET welcome_msg = ? WHERE id = ?", (new_msg, bot_id))
    conn.commit()
    conn.close()

# 13. جلب الترحيب
def get_welcome_msg(bot_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT welcome_msg FROM bots WHERE id = ?", (bot_id, ))
    result = c.fetchone()
    conn.close()
    return result[0] if result else "مرحباً بك!"

# 14. حساب البوتات لكل مستخدم
def count_user_bots(user_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM bots WHERE user_id = ?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

# 15. تفعيل VIP
def activate_user_subscription(user_id, days):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    expire_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute("INSERT OR REPLACE INTO platform_users (user_id, expiry_date) VALUES (?, ?)", 
              (user_id, expire_date))
    conn.commit()
    conn.close()
    return expire_date

# 16. التحقق من الاشتراك
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
        except ValueError: return False
    return False

# 17. قائمة المحظورين
def get_banned_users(bot_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM bot_users WHERE bot_id = ? AND is_banned = 1", (bot_id,))
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

# 18. فك الحظر
def unban_user_db(bot_id, user_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("UPDATE bot_users SET is_banned = 0 WHERE bot_id = ? AND user_id = ?", (bot_id, user_id))
    conn.commit()
    conn.close()

# 19. تفاصيل البروفايل
def get_subscription_details(user_id):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("SELECT expiry_date, points FROM platform_users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row if row else (None, 0)

# 20. تحديث النقاط (جديد)
def update_user_points(user_id, amount):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    c.execute("UPDATE platform_users SET points = points + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# 21. تحديث إعدادات البوت (JSON Config) (جديد)
def update_bot_settings(bot_id, config_dict):
    conn = sqlite3.connect('factory.db')
    c = conn.cursor()
    config_json = json.dumps(config_dict)
    c.execute("UPDATE bots SET config = ? WHERE id = ?", (config_json, bot_id))
    conn.commit()
    conn.close()
