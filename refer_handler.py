from telegram import Update
from telegram.ext import ContextTypes
import bot as main_bot 
import logging

# লগিং সেটআপ
logger = logging.getLogger(__name__)

# -----------------
# ডেটাবেস ফাংশন (আপডেট করা হয়েছে)
# -----------------
def get_referral_data(user_id: int):
    """ইউজারের রেফার সংখ্যা, রেফার ব্যালেন্স এবং প্রিমিয়াম রেফার সংখ্যা ফেচ করে"""
    conn = main_bot.connect_db()
    
    # রিটার্ন ভেরিয়েবল
    referral_count_total = 0
    referral_count_premium = 0
    refer_balance = 0.0
    
    if conn:
        cursor = conn.cursor()
        try:
            # ১. মোট রেফার সংখ্যা গণনা করা (যারা জয়েন করেছে)
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE referrer_id = %s", 
                (user_id,)
            )
            referral_count_total = cursor.fetchone()[0]
            
            # ২. প্রিমিয়াম রেফার সংখ্যা গণনা করা (যারা প্রিমিয়াম নিয়েছে)
            cursor.execute(
                "SELECT COUNT(*) FROM users WHERE referrer_id = %s AND is_premium = TRUE", 
                (user_id,)
            )
            referral_count_premium = cursor.fetchone()[0]
            
            # ৩. রেফার ব্যালেন্স ফেচ করা 
            cursor.execute(
                "SELECT refer_balance FROM users WHERE user_id = %s", 
                (user_id,)
            )
            balance_result = cursor.fetchone()
            if balance_result and balance_result[0] is not None:
                refer_balance = balance_result[0]
            
        except Exception as e:
            logger.error(f"রেফারেল ডেটা পেতে সমস্যা: {e}")
        finally:
            cursor.close()
            conn.close()
    
    # প্রিমিয়াম নয় এমন সদস্যের সংখ্যা
    referral_count_new = referral_count_total - referral_count_premium
    
    return referral_count_total, referral_count_new, referral_count_premium, refer_balance

# -----------------
# রেফারেল মেসেজ তৈরির ফাংশন (আপডেট করা হয়েছে)
# -----------------

async def refer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'📢 REFER 🎁' বাটনে ক্লিক করলে ইউজারের রেফারেল তথ্য দেখায়।"""
    user = update.effective_user
    user_id = user.id

    # ডেটাবেস থেকে ডেটা আনা
    total, new_members, premium_members, refer_balance = get_referral_data(user_id)
    
    refer_balance_formatted = f"{refer_balance:.2f} BDT"

    # রেফারেল লিঙ্ক
    referral_link = f"t.me/{context.bot.username}?start={user_id}"
    
    # মেসেজ ডিজাইন (আপনার দেওয়া ফরম্যাট অনুযায়ী)
    message = (
        f"✅ **রেফার করে উপার্জন করুন** 🎉\n"
        f"✅ **যত বেশি রেফার তত বেশি ইনকাম** 🎉\n\n"
        f"🍩 🎀 `𝑅𝐸𝐹𝐹𝐸𝑅 𝑅𝐸𝒲𝒜𝑅𝒟𝒮` 🎀 🍩\n\n"
        f"🔥 **REFER SANCTION** 🔥\n\n"
        
        f"1️⃣_🆕 `N͢E͢W͢ M͢E͢M͢B͢E͢R͢ J͢O͢I͢N͢I͢N͢G͢`🤝\n"
        f"🎁 **ʀᴇᴡᴀʀᴅ** : **40 TK** 🎉 (প্রতি জয়েনিংয়ে)\n\n"
        
        f"2️⃣_✨ `P͢R͢E͢M͢I͢U͢M͢ S͢U͢B͢S͢C͢R͢I͢P͢T͢I͢O͢N͢`🎨\n"
        f"🎁 **ʀᴇᴡᴀʀᴅ** : **25%** (প্রিমিয়াম কেনার মূল্যের উপর)\n\n"
        
        f"🆕 **MENBERS** : (যারা জয়েন করেছে এবং ফ্রি প্ল্যানে কাজ করছে): **{new_members} জন**\n"
        f"✨ **MEMBES** : (যারা রেফারারের মাধ্যমে প্রিমিয়াম নিয়েছে): **{premium_members} জন**\n"
        f"📢 **MEMBERS** : (সমস্ত রেফারার - প্রিমিয়াম এবং ফ্রী প্ল্যান ইউজার): **{total} জন**\n\n"
        
        f"💰 **YOUR REFER BALANCE** 💰\n"
        f"💵 **Balance** : **{refer_balance_formatted}**\n\n"
        
        f"🎉 **YOUR REFER LINK** 💾\n"
        f"🔗 : `{referral_link}`\n\n"
        
        f"✍️ এই লিংক বন্ধুদেরকে শেয়ার করুন এবং বেশি বেশি উপার্জন করুন 🤑"
    )

    await update.message.reply_text(
        message, 
        parse_mode='Markdown'
    )
