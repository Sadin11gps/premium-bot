import os
import logging
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ConversationHandler
)
from datetime import datetime, timedelta

# আপনার ফাংশনের নামগুলো অনুযায়ী ইম্পোর্ট করুন
from profile_handler import profile_menu, handle_wallet_input, PROFILE_STATE
from refer_handler import refer_command 
from verify_handler import verify_command, SELECT_METHOD, SUBMIT_TNX, handle_tnx_submission 

# --- কনস্ট্যান্ট সেটআপ ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL")
# !!! এটি আপনার ইউজার আইডি দিয়ে পরিবর্তন করুন !!!
ADMIN_ID = 123456789  # <--- এখানে আপনার ব্যক্তিগত Telegram User ID দিন

# লগিং সেটআপ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- ডেটাবেস সংযোগ ফাংশন ---
def connect_db():
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

# --- টেবিল তৈরি ও মাইগ্রেশন ফাংশন (সমস্ত ত্রুটিমুক্ত) ---
def create_table_if_not_exists():
    conn = connect_db()
    if conn is None:
        return
    
    cursor = conn.cursor()
    
    try:
        # ১. 'users' টেবিল তৈরি ও মাইগ্রেট করা (VERIFY কলাম সহ)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                status TEXT DEFAULT 'active',
                is_premium BOOLEAN DEFAULT FALSE,
                expiry_date TIMESTAMP NULL,
                premium_balance DECIMAL(10, 2) DEFAULT 0.00,
                free_income DECIMAL(10, 2) DEFAULT 0.00,
                refer_balance DECIMAL(10, 2) DEFAULT 0.00,
                salary_balance DECIMAL(10, 2) DEFAULT 0.00,
                total_withdraw DECIMAL(10, 2) DEFAULT 0.00,
                wallet_address TEXT,
                referrer_id BIGINT DEFAULT NULL,
                verify_expiry_date TIMESTAMP NULL 
            );
        """)
        
        # ২. 'referrals' টেবিল তৈরি করা
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                referral_id SERIAL PRIMARY KEY,
                referrer_id BIGINT NOT NULL,
                referred_id BIGINT NOT NULL UNIQUE,
                referred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # ৩. নতুন 'verify_requests' টেবিল তৈরি করা (VERIFY সিস্টেমের জন্য)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verify_requests (
                request_id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                username VARCHAR(255),
                method VARCHAR(50) NOT NULL,
                tnx_id VARCHAR(255) NOT NULL,
                amount FLOAT NOT NULL,
                status VARCHAR(50) DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # --- অন্যান্য ALTER TABLE লজিক (যদি থাকে) এখানে যোগ করা যেতে পারে ---
        
        conn.commit()
        logger.info("Database tables and migrations checked/completed successfully.")
        
    except Exception as e:
        logger.error(f"Error during table creation/migration: {e}")
        
    finally:
        cursor.close()
        conn.close()

# --- প্রধান মেনু ফাংশন ---
async def start(update: Update, context):
    user_id = update.effective_user.id
    username = update.effective_user.username or user_id
    referrer_id = None
    
    if context.args and context.args[0].isdigit():
        referrer_id = int(context.args[0])
    
    conn = connect_db()
    if conn:
        cursor = conn.cursor()
        
        # ইউজার ডাটাবেসে আছে কিনা চেক
        cursor.execute("SELECT user_id, status FROM users WHERE user_id = %s", (user_id,))
        user_data = cursor.fetchone()

        if not user_data:
            # নতুন ইউজার, ডাটাবেসে যোগ
            cursor.execute("""
                INSERT INTO users (user_id, status) VALUES (%s, %s);
            """, (user_id, 'active'))
            
            if referrer_id and referrer_id != user_id:
                # রেফেলার বৈধ কিনা চেক
                cursor.execute("SELECT user_id FROM users WHERE user_id = %s", (referrer_id,))
                if cursor.fetchone():
                    # রেফারেল যোগ
                    cursor.execute("""
                        INSERT INTO referrals (referrer_id, referred_id) VALUES (%s, %s);
                    """, (referrer_id, user_id))
                    logger.info(f"User {user_id} referred by {referrer_id}")

            conn.commit()
            await update.message.reply_text(
                f"স্বাগতম, {username}! আপনি সফলভাবে আমাদের সিস্টেমে নিবন্ধিত হয়েছেন।"
            )
        
        # প্রধান মেনু প্রদর্শন
        await main_menu(update, context)
        
        cursor.close()
        conn.close()
    else:
        await update.message.reply_text("দুঃখিত, ডেটাবেস সংযোগে সমস্যা হচ্ছে।")


async def main_menu(update: Update, context):
    keyboard = [
        [
            InlineKeyboardButton("🏠 প্রধান মেনু (Home)", callback_data='menu_home'),
            InlineKeyboardButton("👤 PROFILE", callback_data='menu_profile'),
            InlineKeyboardButton("💰 WITHDRAW", callback_data='menu_withdraw') # <-- উইথড্র পরে যোগ করব
        ],
        [
            InlineKeyboardButton("⭐ প্রিমিয়াম সার্ভিস", callback_data='menu_premium'),
            InlineKeyboardButton("🥇 TASK", callback_data='menu_task'),
            InlineKeyboardButton("🎁 REFER 🎉", callback_data='menu_refer')
        ],
        [
            InlineKeyboardButton("✅ VERIFY ✅", callback_data='menu_verify'),
            InlineKeyboardButton("📦 HISTORY", callback_data='menu_history')
        ],
        [
            InlineKeyboardButton("💡 কিভাবে কাজ করে", callback_data='menu_how_it_works'),
            InlineKeyboardButton("💬 সাপোর্ট", callback_data='menu_support')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "আপনার জন্য সেরা সার্ভিসটি বেছে নিন:"
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

# --- উইথড্র প্লেসহোল্ডার ---
async def withdraw_placeholder(update: Update, context):
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            "💰 উইথড্র সিস্টেম এখন ডেভেলপ করা হচ্ছে। শীঘ্রই আসছে!"
        )

# --- অন্যান্য মেনু প্লেসহোল্ডার ---
async def simple_placeholder(update: Update, context):
    query = update.callback_query
    await query.answer()
    text_map = {
        'menu_premium': "⭐ প্রিমিয়াম সার্ভিসের তথ্য: ...",
        'menu_task': "🥇 টাস্ক তালিকা: ...",
        'menu_history': "📦 লেনদেনের ইতিহাস: ...",
        'menu_how_it_works': "💡 কিভাবে কাজ করে: বিস্তারিত...",
        'menu_support': "💬 সাপোর্ট যোগাযোগ তথ্য: ..."
    }
    
    callback_data = query.data
    text = text_map.get(callback_data, "এই ফিচারটি এখন উপলব্ধ নয়।")
    
    keyboard = [[InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='menu_home')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# --- Error Handler ---
async def error_handler(update: Update, context):
    logger.error(f"Update {update} caused error {context.error}")

# --- প্রধান ফাংশন ---
def main():
    # ডেটাবেস মাইগ্রেশন নিশ্চিত করা
    create_table_if_not_exists()
    
    application = Application.builder().token(BOT_TOKEN).build()

    # Conversation Handlers
    # ১. PROFILE Conversation Handler (ওয়ালেট সেভ করার জন্য)
    profile_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(profile_menu, pattern='^menu_profile$')],
        states={
            PROFILE_STATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_wallet_input)],
        },
        fallbacks=[CallbackQueryHandler(main_menu, pattern='^menu_home$')],
        map_to_parent={
            PROFILE_STATE: PROFILE_STATE # প্রয়োজন হলে অন্য কনভার্সেশন হ্যান্ডলারে ফিরে যাওয়ার জন্য
        }
    )
    application.add_handler(profile_conv_handler)


    # ২. VERIFY Conversation Handler
verify_conv_handler = ConversationHandler(
    #...
    states={
        SELECT_METHOD: [CallbackQueryHandler(start_verify_flow, pattern='^VERIFY_REQUEST$|^(method_bkash|method_nagad)$')], 
        SUBMIT_TNX: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tnx_submission)] # ✅ এখানে ফাংশনটি যুক্ত করা হলো
        }
    )
    application.add_handler(verify_conv_handler)


    # Command Handlers
    application.add_handler(CommandHandler("start", start))

    # CallbackQuery Handlers
    application.add_handler(CallbackQueryHandler(main_menu, pattern='^menu_home$'))
    application.add_handler(CallbackQueryHandler(refer_menu, pattern='^menu_refer$'))
    application.add_handler(CallbackQueryHandler(withdraw_placeholder, pattern='^menu_withdraw$'))

    # VERIFY Admin Action Handler
    application.add_handler(CallbackQueryHandler(handle_admin_callback, pattern='^(verify_accept|verify_reject)_(\d+)$'))

    # Simple Placeholder Handlers
    application.add_handler(CallbackQueryHandler(simple_placeholder, pattern='^menu_(premium|task|history|how_it_works|support)$'))
    
    # Error Handler
    application.add_handler(application.error_handler)

    # রান করা
    application.run_polling(poll_interval=1.0)

if __name__ == '__main__':
    main()
