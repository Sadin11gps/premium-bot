from telegram import Update
from telegram.ext import ContextTypes
import bot as main_bot 

# -----------------
# ১. প্রোফাইল মেসেজ তৈরির ফাংশন
# -----------------

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'👤 PROFILE 👤' বাটনে ক্লিক করলে ইউজারের তথ্য দেখায়।"""
    user = update.effective_user
    user_id = user.id
    
    # status: (is_premium, expiry_date, premium_balance, free_income, refer_balance, salary_balance, total_withdraw)
    # **NOTE:** এই মুহূর্তে bot.py ফাইলে এই কলামগুলো (free_income, refer_balance, etc.) নাও থাকতে পারে,
    # কিন্তু আমরা ধরে নিচ্ছি আপনার পরবর্তী ধাপে সেগুলি ঠিক করা হবে। 
    status = main_bot.get_user_status(user_id)
    
    # ডেটা ফরমেটিং
    if status and len(status) >= 7:
        # ডেটাবেস থেকে নতুন ব্যালেন্স কলামের মান পাওয়া যাচ্ছে
        premium_balance = f"{status[2]:.2f} BDT" if status[2] is not None else "0.00 BDT"
        free_income = f"{status[3]:.2f} BDT" if status[3] is not None else "0.00 BDT"
        refer_balance = f"{status[4]:.2f} BDT" if status[4] is not None else "0.00 BDT"
        salary_balance = f"{status[5]:.2f} BDT" if status[5] is not None else "0.00 BDT"
        total_withdraw = f"{status[6]:.2f} BDT" if status[6] is not None else "0.00 BDT"
        
        # প্রিমিয়াম স্ট্যাটাস
        expiry_date = status[1].strftime('%d-%m-%Y') if status[1] else 'নেই'
        is_premium_text = "✅ প্রিমিয়াম সদস্য" if status[0] else "❌ ফ্রি সদস্য"

    else:
        # ডেটাবেস এরর বা কলাম অনুপস্থিত হলে ডিফল্ট মান
        premium_balance = free_income = refer_balance = salary_balance = total_withdraw = "0.00 BDT"
        expiry_date = 'নেই'
        is_premium_text = "❌ ডেটাবেস ত্রুটি / ফ্রি সদস্য"

    # প্রোফাইল মেসেজ তৈরি (আপনার চাওয়া ফরম্যাট অনুযায়ী)
    message = (
        f"**👤 আপনার প্রোফাইল 👤**\n"
        f"📝 ইউজার নেম: **{user.first_name or 'নেই'}**\n\n"
        
        f"✨ Balance: **{premium_balance}**\n"
        f"💸 Free income: **{free_income}**\n"
        f"🎁 Refer balance: **{refer_balance}**\n"
        f"💵 Salary: **{salary_balance}**\n"
        f"🏦 Withdraw: **{total_withdraw}**\n\n"
        
        f"⭐️ সদস্যপদ স্ট্যাটাস: **{is_premium_text}**\n"
        f"📅 প্রিমিয়াম মেয়াদ: **{expiry_date}**\n\n"
        
        f"🔗 আপনার রেফারেল লিঙ্ক: `t.me/{context.bot.username}?start={user_id}`"
    )

    await update.message.reply_text(
        message, 
        parse_mode='Markdown'
    )
