import os
import psycopg2
import logging
from telegram import Update
from telegram.ext import CallbackContext

# --- ১. কনস্ট্যান্ট ও লগিং ---
logger = logging.getLogger(__name__)

# Fetching the referral bonus constant
REFERRAL_BONUS_JOINING = 40.00 

# --- ২. ডেটাবেস সংযোগ ফাংশন (Circular Import এড়াতে) ---
def connect_db():
    DATABASE_URL = os.environ.get("DATABASE_URL")
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

# --- ৩. রেফারেল মেনু ফাংশন (আসল Text Style এবং ইমোজি সহ) ---
async def refer_menu(update: Update, context: CallbackContext):
    """Handles the 💸 REFER button or /refer command"""
    
    user_id = update.effective_user.id
    
    conn = connect_db()
    if not conn:
        await update.message.reply_text("দুঃখিত, বর্তমানে ডেটাবেস সংযোগে সমস্যা হচ্ছে। পরে চেষ্টা করুন।")
        return

    cursor = conn.cursor()
    refer_balance = 0.00
    referral_count = 0
    
    try:
        # ১. Fetch user's referral balance
        cursor.execute("SELECT refer_balance FROM users WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        
        if result:
            refer_balance = result[0]
        else:
            refer_balance = 0.00
        
        # ২. Count the total number of referrals
        cursor.execute("SELECT COUNT(user_id) FROM users WHERE referrer_id = %s", (user_id,))
        referral_count = cursor.fetchone()[0]
        
        # ৩. Create the dynamic referral link
        bot_username = context.bot.username
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        
        # ৪. Create the message (আপনার দেওয়া স্টাইল অনুযায়ী)
        message = (
            "✅ রেফার করে উপার্জন করুন 🎉\n"
            "✅ যত বেশি রেফার তত বেশি ইনকাম\n"
            "🔥 **REFER REWARDS** 🎁\n"
            "---------------------------\n"
            "1️⃣ ɴᴇᴡ **ᴍᴇᴍʙᴇʀ ᴊᴏɪɴɪɴɢ** 🎊\n"
            f"**ʀᴇᴡᴀʀᴅ** : **{REFERRAL_BONUS_JOINING:.2f}$**\n" # REFERRAL_B পরিবর্তন করা হলো
            "2️⃣ ᴘʀᴇᴍɪᴜᴍ sᴜʙsᴄʀɪᴘᴛɪᴏɴ 💸\n"
            "ʀᴇᴡᴀʀᴅ : **25%**\n"
            "---------------------------\n"
            f"🆕 **ғʀᴇᴇ ᴍᴇᴍʙᴇʀs**: **{referral_count}**\n" # রেফারেল সংখ্যা যোগ
            "✨ **ᴘʀᴇᴍɪᴜᴍ ᴍᴇᴍʙᴇs** : **0**\n" # এটি স্থির রাখা হয়েছে
            f"📣 **ᴛᴏᴛᴀʟ ʀᴇғᴇʀʀᴀʟs**: **{referral_count}**\n" # মোট রেফারেল সংখ্যা যোগ
            "---------------------------\n"
            "💲 **ʏᴏᴜʀ ʀᴇғᴇʀ ʙᴀʟᴀɴᴄᴇ** [৳]\n" # আপনার আসল প্রতীক ব্যবহার
            f"Balance: **{refer_balance:.2f}**\n"
            "---------------------------\n"
            "🔗 **ʏᴏᴜʀ ʀᴇғᴇʀ ʟɪɴᴋ** 💾\n"
            f"`{referral_link}`\n\n"
            "এই লিংক বন্ধুদেরকে শেয়ার করুন"
        )

    except Exception as e:
        logger.error(f"Referral data fetch error: {e}")
        message = "দুঃখিত! রেফারেলে তথ্য দেখাতে সমস্যা হচ্ছে।"
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    # মেসেজ রিপ্লাই করা
    await update.message.reply_text(
        message, 
        parse_mode='Markdown'
    )
