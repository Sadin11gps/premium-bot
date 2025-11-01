import os
import logging
import psycopg2
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# **নতুন: প্রোফাইল হ্যান্ডলার ফাইলটি আমদানি করা**
# এই লাইনটি profile_handler.py ফাইলটিকে ব্যবহার করার জন্য প্রয়োজন
import profile_handler 

# লগিং সেটআপ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# -----------------
# ১. ডেটাবেস ও টোকেন ভেরিয়েবল
# -----------------
# টেলিগ্রাম বট টোকেন:
BOT_TOKEN = "8360641058:AAF75LwX0nqb_LwdAGWc-wr0m9HsmZ3CiTo" 

# Render PostgreSQL ডেটাবেস কানেকশন স্ট্রিং:
DATABASE_URL = "postgresql://rds_bot_user:X6j2MJD8Uim0mMm0AXFT6435fq9XIOI1@dpg-d42gp4v5r7bs73b0dgl0-a.oregon-postgres.render.com/rds_bot_db" 

# -----------------
# ২. ডেটাবেস কানেকশন ও ইউজার টেবিল তৈরি/পড়া
# -----------------

def connect_db():
    """Render ডেটাবেসের সাথে যুক্ত হয়"""
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode='require') 
        return conn
    except Exception as e:
        logger.error(f"ডেটাবেস সংযোগে সমস্যা: {e}")
        return None

def create_table_if_not_exists():
    """ইউজারদের ডেটা সংরক্ষণের জন্য টেবিল তৈরি করে"""
    conn = connect_db()
    if conn:
        cursor = conn.cursor()
        try:
            # **আপডেট করা হয়েছে: নতুন ব্যালেন্স কলাম এবং রেফারার আইডি যুক্ত করা হয়েছে**
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    status TEXT DEFAULT 'start',
                    is_premium BOOLEAN DEFAULT FALSE,
                    expiry_date DATE,
                    
                    premium_balance DECIMAL(10, 2) DEFAULT 0.00,
                    free_income DECIMAL(10, 2) DEFAULT 0.00,
                    refer_balance DECIMAL(10, 2) DEFAULT 0.00,
                    salary_balance DECIMAL(10, 2) DEFAULT 0.00,
                    total_withdraw DECIMAL(10, 2) DEFAULT 0.00,
                    
                    wallet_address TEXT,
                    referrer_id BIGINT DEFAULT NULL
                );
            """)
            conn.commit()
            logger.info("ইউজার টেবিল তৈরি/যাচাই সম্পন্ন হয়েছে।")
        except Exception as e:
            logger.error(f"টেবিল তৈরিতে সমস্যা: {e}")
        finally:
            cursor.close()
            conn.close()

def save_user_if_not_exists(user_id: int, referrer_id: int = None):
    """নতুন ইউজারকে ডেটাবেসে যোগ করে"""
    conn = connect_db()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
            if cursor.fetchone() is None:
                cursor.execute(
                    "INSERT INTO users (user_id, referrer_id) VALUES (%s, %s)", (user_id, referrer_id)
                )
                conn.commit()
                logger.info(f"নতুন ইউজার যোগ হলো: {user_id}, রেফারার: {referrer_id}")
            else:
                logger.info(f"ইউজার বিদ্যমান: {user_id}")
        except Exception as e:
            logger.error(f"ইউজার সেভ করতে সমস্যা: {e}")
        finally:
            cursor.close()
            conn.close()

def get_user_status(user_id: int):
    """**আপডেট করা হয়েছে:** সমস্ত ব্যালেন্স কলাম সহ ইউজারের ডেটা নিয়ে আসে"""
    conn = connect_db()
    if conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT 
                    is_premium, expiry_date, 
                    premium_balance, free_income, refer_balance, 
                    salary_balance, total_withdraw 
                FROM users WHERE user_id = %s
            """, (user_id,))
            result = cursor.fetchone()
            # result এখন ৭টি কলামের মান দেবে
            return result
        except Exception as e:
            logger.error(f"ইউজার স্ট্যাটাস পেতে সমস্যা: {e}")
            return None
        finally:
            cursor.close()
            conn.close()
            
# -----------------
# ৩. বাটন ডিজাইন
# -----------------

# ক) মূল মেনুর বাটন (Reply Keyboard) - সমস্ত বাটন যুক্ত করা হয়েছে
main_menu_keyboard = [
    ["🏠 প্রধান মেনু (Home)", "👤 PROFILE 👤", "🏦 WITHDRAW 🏦"],
    ["⭐️ প্রিমিয়াম সার্ভিস", "🏅 TASK 🏅", "📢 REFER 🎁"], 
    ["💾 VERIFY ✅", "📜 HISTORY 📜"],
    ["💡 কিভাবে কাজ করে?", "📞 সাপোর্ট"]
]
main_menu_markup = ReplyKeyboardMarkup(main_menu_keyboard, resize_keyboard=True, one_time_keyboard=False)

# খ) প্রিমিয়াম বাটন (Inline Keyboard) - একক বাটন
premium_inline_keyboard = [
    [InlineKeyboardButton("✨ PREMIUM SERVICE ⭐️", callback_data='premium_service_main')], 
]
premium_inline_markup = InlineKeyboardMarkup(premium_inline_keyboard)

# -----------------
# ৪. হ্যান্ডলার ফাংশন
# -----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """বট চালু করার সময় বাটন দেখায় এবং ডেটাবেসে ইউজারকে যুক্ত করে"""
    user_id = update.effective_user.id
    
    # রেফারেল লজিক: যদি কমান্ডে কোনো আর্গুমেন্ট (রেফারার আইডি) থাকে
    referrer_id = None
    if context.args and len(context.args) > 0:
        try:
            referrer_id = int(context.args[0])
            if referrer_id == user_id: 
                referrer_id = None
        except ValueError:
            referrer_id = None
            
    save_user_if_not_exists(user_id, referrer_id)
    
    await update.message.reply_text(
        "স্বাগতম! আপনি বাটন ব্যবহার করে আপনার পছন্দের অপশন বেছে নিতে পারেন।",
        reply_markup=main_menu_markup
    )

async def premium_service_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """⭐️ প্রিমিয়াম সার্ভিস বাটনে ক্লিক করলে ইনলাইন বাটন দেখায়"""
    await update.message.reply_text(
        "আমাদের প্রিমিয়াম সেকশনে আপনাকে স্বাগতম। নিচে প্রদত্ত বাটনটি ব্যবহার করুন:",
        reply_markup=premium_inline_markup
    )


async def handle_button_clicks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    মেনু বাটনে ক্লিক করলে কী হবে তা পরিচালনা করে।
    এখন থেকে, এটি শুধু সেই বাটনগুলি হ্যান্ডেল করবে যার জন্য আলাদা হ্যান্ডলার যোগ করা হয়নি।
    বাকি মেনু বাটনগুলির জন্য মেইন ফাংশনে filters.Regex দিয়ে হ্যান্ডলার যোগ করা হবে।
    """
    text = update.message.text
    
    # এই বাটনগুলো handle_button_clicks এ রাখা হয়েছে, কারণ এগুলো মডুলার না হলেও চলে
    if text == "🏠 প্রধান মেনু (Home)":
        await update.message.reply_text("আপনি প্রধান মেনুতে আছেন।", reply_markup=main_menu_markup)
    elif text == "💡 কিভাবে কাজ করে?":
        await update.message.reply_text("এই বটটি একটি প্রিমিয়াম কন্টেন্ট অ্যাক্সেস প্রদানকারী বট। আপনি প্রিমিয়াম প্ল্যান কিনে আমাদের এক্সক্লুসিভ চ্যানেলে যুক্ত হতে পারেন।")
    elif text == "📞 সাপোর্ট":
        await update.message.reply_text("সাপোর্টের জন্য এই ইউজারনেমে যোগাযোগ করুন: @Your_Support_Username")
    else:
        # যদি অন্য কোনো টেক্সট বাটন হয় যা এখনো মডুলার করা হয়নি, তবে এখানে ডিফল্ট মেসেজ আসবে
        await update.message.reply_text("দুঃখিত, আমি এই কমান্ডটি বুঝিনি। দয়া করে মেনু বাটন ব্যবহার করুন।")
    
async def handle_inline_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ইনলাইন বাটনে ক্লিক করলে কী হবে তা পরিচালনা করে"""
    query = update.callback_query
    await query.answer() 
    
    data = query.data
    
    if data == 'premium_service_main':
        # এই লজিক পরে একটি আলাদা ফাইলে যেতে পারে
        await query.edit_message_text(
            "✨ প্রিমিয়াম মেনু:\n\n"
            "এখনো কোনো কাজ শুরু হয়নি। পরবর্তী ধাপে এর লজিক যোগ হবে।"
        )


# -----------------
# ৫. মূল ফাংশন
# -----------------

def main():
    """বট অ্যাপ্লিকেশন শুরু করে"""
    create_table_if_not_exists()
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # হ্যান্ডলার যুক্ত করা:
    application.add_handler(CommandHandler("start", start))
    
    # 💡 মডুলার লজিকের জন্য, filters.Regex ব্যবহার করে প্রতিটি বাটনের জন্য হ্যান্ডলার যোগ করা হলো:
    
    # ১. প্রোফাইল হ্যান্ডলার (profile_handler.py ফাইলটি কাজ করবে)
    application.add_handler(MessageHandler(filters.Regex("^👤 PROFILE 👤$"), profile_handler.profile_command))

    # ২. প্রিমিয়াম সার্ভিস হ্যান্ডলার (এই ফাইলের ভেতরের ফাংশন কাজ করবে)
    application.add_handler(MessageHandler(filters.Regex("^⭐️ প্রিমিয়াম সার্ভিস$"), premium_service_button))

    # ৩. অন্যান্য WIP হ্যান্ডলার (এগুলো পরে আলাদা ফাইল থেকে import করা হবে)
    # application.add_handler(MessageHandler(filters.Regex("^🏦 WITHDRAW 🏦$"), withdraw_handler.withdraw_command))
    # application.add_handler(MessageHandler(filters.Regex("^🏅 TASK 🏅$"), task_handler.task_command))
    # application.add_handler(MessageHandler(filters.Regex("^📢 REFER 🎁$"), refer_handler.refer_command))
    # application.add_handler(MessageHandler(filters.Regex("^💾 VERIFY ✅$"), verify_handler.verify_command))
    # application.add_handler(MessageHandler(filters.Regex("^📜 HISTORY 📜$"), history_handler.history_command))
    
    # ৪. অবশিষ্ট টেক্সট মেসেজ এবং অন্যান্য হ্যান্ডলার
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_button_clicks))
    application.add_handler(CallbackQueryHandler(handle_inline_callbacks))
    
    logger.info("বট চলছে... (Polling Mode)")
    application.run_polling(poll_interval=3)

if __name__ == '__main__':
    main()
