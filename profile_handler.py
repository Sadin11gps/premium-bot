import os
import psycopg2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from datetime import datetime

# --- ১. কনভার্সেশন স্টেট ---
PROFILE_STATE = 1 # Wallet address input state


# --- ২. ডেটাবেস সংযোগ ফাংশন ---
def connect_db():
    DATABASE_URL = os.environ.get("DATABASE_URL")
    try:
        conn = psycopg2.connect(DATABASE_URL, sslmode="require")
        return conn
    except Exception as e:
        return None


# --- ৩. প্রোফাইল মেনু ফাংশন (আসল ইমোজি এবং লজিক সহ) ---
async def profile_menu(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    status = None
    
    conn = connect_db()
    if conn:
        cursor = None
        try:
            cursor = conn.cursor()
            
            # আপনার আগের SELECT স্টেটমেন্ট
            cursor.execute("""
                SELECT 
                    is_premium, expiry_date, premium_balance, free_income, 
                    refer_balance, salary_balance, total_withdraw, wallet_address, 
                    verify_expiry_date, referrer_id 
                FROM users 
                WHERE user_id = %s
            """, (user_id,))
            status = cursor.fetchone()
            
        except Exception as e:
            print(f"Error fetching profile data: {e}") 
            status = None
            
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    if status and len(status) >= 10: 
        # ইনডেক্স ব্যবহার করে ভ্যালু অ্যাসাইন করা 
        is_premium = status[0]
        expiry_date = status[1]
        premium_balance = status[2]
        free_income = status[3]
        refer_balance = status[4]
        salary_balance = status[5]
        total_withdraw = status[6]
        wallet_address = status[7]
        verify_expiry_date = status[8]
        # referrer_id = status[9]

        # প্রিমিয়াম স্ট্যাটাস
        premium_status = "✅ Active" if is_premium else "❌ Inactive"
        expiry_date_text = expiry_date.strftime("%d-%m-%Y") if expiry_date else "N/A"
        
        # ভেরিফাই স্ট্যাটাস 
        verify_status = "❌ Not Verified"
        if verify_expiry_date and verify_expiry_date > datetime.now():
            remaining_verify_time = verify_expiry_date - datetime.now()
            verify_status = f"✅ Verified (Ends in {remaining_verify_time.days} days)"

        # প্রোফাইল মেসেজ তৈরি (ইমোজি সহ)
        message = f"""
**👤 আপনার প্রোফাইল তথ্য 🏆**

**💎 প্রিমিয়াম স্ট্যাটাস:** {premium_status}
**📅 প্রিমিয়াম মেয়াদ:** {expiry_date_text}

**✅ ভেরিফিকেশন:** {verify_status}

**💰 আপনার ব্যালেন্স:**
  - ✨ Premium Balance: $ {premium_balance:.2f}
  - 🕊️ Free Income: $ {free_income:.2f}
  - 👥 Refer Balance: $ {refer_balance:.2f}
  - 💼 Salary Balance: $ {salary_balance:.2f}

**💸 মোট উত্তোলন:** $ {total_withdraw:.2f}
**🔗 ওয়ালেট অ্যাড্রেস:** `{wallet_address or 'Not Set'}`
"""
        # বাটন তৈরি
        keyboard = [
            [InlineKeyboardButton("🔗 ওয়ালেট অ্যাড্রেস পরিবর্তন", callback_data='set_wallet')],
            [InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='menu_home')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

    else:
        message = "দুঃখিত! আপনার প্রোফাইল তথ্য লোড করা যায়নি। দয়া করে /start দিয়ে পুনরায় চেষ্টা করুন।"
        keyboard = [[InlineKeyboardButton("🔙 মেনুতে ফিরুন", callback_data='menu_home')]]
        reply_markup = InlineKeyboardMarkup(keyboard)

    # মেসেজ আপডেট করা বা রিপ্লাই দেওয়া
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        # ওয়ালেট সেট করার জন্য কনভার্সেশন শুরু
        if query.data == 'set_wallet':
            await query.edit_message_text("দয়া করে আপনার নতুন ওয়ালেট অ্যাড্রেসটি টাইপ করে পাঠান:")
            return PROFILE_STATE # handle_wallet_input চালু হবে
        
        await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
    return ConversationHandler.END


# --- ৪. ওয়ালেট ইনপুট হ্যান্ডলার ফাংশন ---
async def handle_wallet_input(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    wallet_address = update.message.text
    
    if not wallet_address or len(wallet_address) < 10:
        await update.message.reply_text("❌ দুঃখিত! ওয়ালেট অ্যাড্রেসটি বৈধ মনে হচ্ছে না। দয়া করে সঠিক অ্যাড্রেস দিন:")
        return PROFILE_STATE 

    conn = connect_db()
    if conn:
        cursor = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE users SET wallet_address = %s WHERE user_id = %s
            """, (wallet_address, user_id))
            conn.commit()
            
            await update.message.reply_text(
                f"✅ আপনার নতুন ওয়ালেট অ্যাড্রেস **{wallet_address}** সফলভাবে সেভ করা হয়েছে।",
                parse_mode='Markdown'
            )
            return ConversationHandler.END 
        
        except Exception as e:
            print(f"Error saving wallet address: {e}")
            await update.message.reply_text("দুঃখিত, ওয়ালেট সেভ করার সময় একটি ডেটাবেস ত্রুটি হয়েছে।")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    return ConversationHandler.END
