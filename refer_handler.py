from telegram import Update
from telegram.ext import ContextTypes
import bot as main_bot 
import logging

logger = logging.getLogger(__name__)

# Fetching the referral bonus constant from bot.py
REFERRAL_BONUS_JOINING = main_bot.REFERRAL_BONUS_JOINING 

# -----------------
# 1. Referral Command Handler
# -----------------

async def refer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the '📢 REFER 🎁' button click and displays referral info."""
    user = update.effective_user
    user_id = user.id

    conn = main_bot.connect_db()
    
    if not conn:
        await update.message.reply_text("দুঃখিত! ডেটাবেস সংযোগে সমস্যা হচ্ছে।")
        return

    cursor = conn.cursor()
    
    try:
        # 1. Fetch user's referral balance
        cursor.execute(
            "SELECT refer_balance FROM users WHERE user_id = %s",
            (user_id,)
        )
        result = cursor.fetchone()
        
        if result:
            refer_balance = result[0]
        else:
            refer_balance = 0.00
            
        # 2. Count the total number of users referred by this user
        cursor.execute(
            "SELECT COUNT(user_id) FROM users WHERE referrer_id = %s",
            (user_id,)
        )
        referral_count = cursor.fetchone()[0]
        
        # Create the dynamic referral link
        referral_link = f"https://t.me/{context.bot.username}?start={user_id}"
        
        # 3. Create the message (Fully Cleaned & Dynamic)
        message = (
            "✅ রেফাফর করে উপার্জন করুন 🎉🎊\n"
            "✅ যত বেশি রেফার তত বেশি ইনকাম💰\n"
            "🔥 **REFER REWARDS** 🎁\n"
            "----------------------------------------\n"
            "1️⃣ ɴᴇᴡ **ᴍᴇᴍʙᴇʀ ᴊᴏɪɴɪɴɢ** 🎊\n"
            f"**ʀᴇᴡᴀʀᴅ** : **{REFERRAL_BONUS_JOINING:.2f} ᴛᴋ**\n"
            "2️⃣ ᴘʀᴇᴍɪᴜᴍ sᴜʙsᴄʀɪᴘᴛɪᴏɴ 💸\n"
            "ʀᴇᴡᴀʀᴅ : **25%**\n"
            "----------------------------------------\n"
            "🆕 **ғʀᴇᴇ ᴍᴇᴍʙᴇʀs** : **{referral_count}** জন\n" 
            "✨ **ᴘʀᴇᴍɪᴜᴍ ᴍᴇᴍʙᴇs** : **0** জন\n" 
            "📣 **ᴛᴏᴛᴀʟ ʀᴇғᴇʀʀᴀʟs** : **{referral_count}** জন\n"
            "----------------------------------------\n"
            "💲 **ʏᴏᴜʀ ʀᴇғᴇʀ ʙᴀʟᴀɴᴄᴇ** 💵\n"
            f"Balance: **{refer_balance:.2f} BDT**\n"
            "----------------------------------------\n"
            "🔗 **ʏᴏᴜʀ ʀᴇғᴇʀ ʟɪɴᴋ** 💾\n"
            f"`{referral_link}`\n\n"
            "এই লিংক বন্ধুদেরকে শেয়ার করুন এবং উপার্জন শুরু করুন!"
        )
        
    except Exception as e:
        logger.error(f"Referral data fetch error: {e}")
        message = "রেফারেল তথ্য দেখাতে সাময়িক সমস্যা হচ্ছে।"
    finally:
        cursor.close()
        conn.close()

    await update.message.reply_text(message, parse_mode='Markdown')
