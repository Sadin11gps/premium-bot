import os
import logging
import psycopg2
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler # ConversationHandler ইম্পোর্ট করা হলো

# --- Conversation States ---
# আপনার দেওয়া স্ক্রিনশট অনুযায়ী, এখানে শুধু একটি স্টেট দরকার
PROFILE_STATE = 0 
# PROFILE_EDIT_STATE = range(2) # যদি প্রয়োজন না হয়, ডিলিট করে দিন
# PROFILE_EDIT_STATE = 1 


# লগিং সেটআপ
logger = logging.getLogger(__name__)

# --- ২. ডেটাবেস সংযোগ ফাংশন ---
# এটি db_handler.py থেকে ইম্পোর্ট করা উচিত ছিল, কিন্তু circular import এড়ানোর জন্য সাময়িকভাবে এখানে রাখা হলো
def connect_db():
    """Render ডেটাবেসের সাথে যুক্ত হয়"""
    DATABASE_URL = os.environ.get("DATABASE_URL") 
    try:
        if not DATABASE_URL:
            logger.error("DATABASE_URL environment variable is not set.")
            return None
            
        conn = psycopg2.connect(DATABASE_URL, sslmode='require') 
        return conn
    except Exception as e:
        logger.error(f"ডেটাবেস সংযোগে সমস্যা: {e}")
        return None

# --- ৩. প্রোফাইল মেনু (এন্ট্রি পয়েন্ট ফাংশন) ---
# আপনার bot.py এখন এটি ইম্পোর্ট করবে: profile_menu
async def handle_wallet_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ইউজারের প্রোফাইল তথ্য দেখায় এবং ওয়ালেট সেট করার অপশন দেয়।"""
    user_id = update.effective_user.id
    status = None
    conn = connect_db()
    
    # ডেটাবেস থেকে ইউজারের স্ট্যাটাস/তথ্য আনা
    if conn:
        cursor = conn.cursor()
        try:
            # আপনার দেওয়া SELECT স্টেটমেন্টটি ব্যবহার করা হলো
            cursor.execute("""
                SELECT 
                    is_premium, expiry_date, premium_balance, free_income, 
                    refer_balance, salary_balance, total_withdraw, wallet_address, 
                    expiry_date, referrer_id 
                FROM users 
                WHERE user_id = %s
                """, (user_id,))
            status = cursor.fetchone()
        except Exception as e:
            logger.error(f"Error fetching profile: {e}")
            status = None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # তথ্য প্রক্রিয়াকরণ ও মেসেজ তৈরি
    if status and len(status) >= 10:
        is_premium = status[0]
        expiry_date = status[1]
        premium_balance = status[2]
        free_income = status[3]
        refer_balance = status[4]
        salary_balance = status[5]
        total_withdraw = status[6]
        wallet_address = status[7]
        verify_expiry_date = status[8] # একই কলাম দুইবার নেওয়া হয়েছে, ধরে নিলাম এটি verify_expiry_date
        referrer_id = status[9]

        # প্রিমিয়াম স্ট্যাটাস
        premium_status = "✅ Active" if is_premium and expiry_date and expiry_date >= datetime.now().date() else "❌ Inactive"
        expiry_date_text = expiry_date.strftime("%Y-%m-%d") if expiry_date else "N/A"

        # ভেরিফাই স্ট্যাটাস
        verify_status = "❌ Not Verified"
        if verify_expiry_date and verify_expiry_date >= datetime.now().date():
            verify_status = "✅ Verified (Expires: " + verify_expiry_date.strftime("%Y-%m-%d") + ")"

        # প্রোফাইল মেসেজ তৈরি (ইমোজি সহ)
        message = (
            f"👤 **আপনার ব্যক্তিগত তথ্য** 🏆\n"
            f"**ইউজার আইডি:** `{user_id}`\n\n"
            f"**💎 প্রিমিয়াম স্ট্যাটাস:** {premium_status}\n"
            f"**📅 মেয়াদ শেষ:** {expiry_date_text}\n"
            f"**✅ ভেরিফিকেশন স্ট্যাটাস:** {verify_status}\n\n"
            f"**💰 আপনার ব্যালেন্স:**\n"
            f"✨ Premium Balance: **৳ {premium_balance:.2f}**\n"
            f"🆓 Free Income: **৳ {free_income:.2f}**\n"
            f"🎁 Refer Balance: **৳ {refer_balance:.2f}**\n"
            f"💵 Salary Balance: **৳ {salary_balance:.2f}**\n\n"
            f"***"
            f"💸 **মোট উত্তোলন:** **৳ {total_withdraw:.2f}**\n"
            f"💳 **ওয়ালেট অ্যাড্রেস:** `{wallet_address or 'সেট করা নেই'}`\n"
        )
        
        # বাটন তৈরি
        keyboard = [
            [InlineKeyboardButton("💳 ওয়ালেট সেট করুন", callback_data='set_wallet')], 
            [InlineKeyboardButton("🔙 মেনু", callback_data='menu_home')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
    else:
        # যদি ডেটাবেসে না থাকে
        message = "দুঃখিত, আপনার প্রোফাইল তথ্য পাওয়া যায়নি বা আপনি এখনো রেজিস্টার করেননি। /start চাপুন।"
        reply_markup = None
        # ConversationHandler-এ থাকাকালীন যদি এই error হয়, তাহলে মেনু বাটনও থাকবে না।

    
    # মেসেজ পাঠানো (Callback Query হ্যান্ডলিং)
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        # 'set_wallet' বাটনে ক্লিক করলে
        if query.data == 'set_wallet':
            await query.edit_message_text(
                "📝 **আপনার ওয়ালেট অ্যাড্রেস ইনপুট করুন।** (যেমন: আপনার বিকাশ/নগদ/রকেট নম্বর)\n\n"
                "ক্যানসেল করতে /cancel লিখুন।"
            )
            return PROFILE_STATE # পরবর্তী স্টেট
            
        else:
            # অন্য কোনো ক্যোয়ারি (যেমন 'menu_home')
            await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
            return ConversationHandler.END # কথোপকথন শেষ

        elif update.message:
    # মেসেজ থেকে আসলে (প্রথমবার '👤 PROFILE 👤' চাপলে)
            await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return ConversationHandler.END 


# --2- ৪. প্রোফাইল ইনপুট হ্যান্ডলার ফাংশন ---
# আপনার bot.py এই ফাংশনটি ইম্পোর্ট করে ব্যবহার করবে: handle_profile_input
async def handle_profile_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ওয়ালেট ইনপুট হ্যান্ডলার হিসেবে কাজ করবে।"""
    user_id = update.effective_user.id
    wallet_address = update.message.text.strip()
    
    # ইনপুট যাচাই
    if not wallet_address or len(wallet_address) < 5:
        await update.message.reply_text("❌ অকার্যকর ইনপুট। দয়া করে সঠিক ওয়ালেট অ্যাড্রেস দিন।")
        return PROFILE_STATE # একই স্টেটে থাকুন
        
    conn = connect_db()
    if conn:
        cursor = conn.cursor()
        try:
            # ডেটাবেসে ওয়ালেট অ্যাড্রেস আপডেট করা
            cursor.execute(
                """UPDATE users SET wallet_address = %s WHERE user_id = %s""",
                (wallet_address, user_id)
            )
            conn.commit()
            
            await update.message.reply_text(
                f"✅ **সফল!**\n\n"
                f"আপনার নতুন ওয়ালেট অ্যাড্রেসটি সেভ করা হয়েছে: `{wallet_address}`",
                parse_mode='Markdown'
            )
            
            return ConversationHandler.END # কথোপকথন শেষ
            
        except Exception as e:
            logger.error(f"Error saving wallet address for {user_id}: {e}")
            await update.message.reply_text("❌ ওয়ালেট অ্যাড্রেস সেভ করতে সমস্যা হয়েছে।")
            return ConversationHandler.END # কথোপকথন শেষ
            
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
                
    else:
        await update.message.reply_text("❌ ডেটাবেস সংযোগে সমস্যা।")
        return ConversationHandler.END # কথোপকথন শেষ
