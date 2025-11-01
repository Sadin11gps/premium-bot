from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, MessageHandler, CallbackQueryHandler
from datetime import datetime, timedelta
import bot as main_bot 
import logging
from telegram.ext.filters import TEXT # MessageHandler এর জন্য Filters আমদানি করা হলো

logger = logging.getLogger(__name__)

# Conversation States
SELECT_METHOD, SUBMIT_TNX = range(2)

# --- কনস্ট্যান্ট ও সেটিংস ---
VERIFY_AMOUNT = 50.00 # ১ মাসের ভেরিফিকেশন ফি (উদাহরণ)
VERIFY_DAYS = 30 
PAYMENT_NUMBER = "01338553254" # বিকাশ/নগদ উভয় নম্বরের জন্য (আপনার দেওয়া নম্বর)

# --- উপযোগিতা ফাংশন ---

def format_verify_status(is_premium, expiry_date, verify_expiry_date):
    """VERIFY বাটনে দেখানোর জন্য মেসেজ ফরম্যাট করা"""
    message = ""
    
    # ১. প্রিমিয়াম চেক
    if is_premium and expiry_date and expiry_date > datetime.now():
        remaining_time = expiry_date - datetime.now()
        days = remaining_time.days
        message += (
            f"✨ **PREMIUM USER** ✨\n"
            f"🗓️ PREMIUM TIME : {days} দিন বাকি\n\n"
        )
        # প্রিমিয়াম ইউজারের জন্য কোনো ভেরিফাই বাটন নেই
        return message, None

    # ২. ভেরিফাই চেক (যদি প্রিমিয়াম না হয়)
    if verify_expiry_date and verify_expiry_date > datetime.now():
        remaining_time = verify_expiry_date - datetime.now()
        days = remaining_time.days
        message += (
            f"✅ **আপনার অ্যাকাউন্টটি ভেরিফাইড** ✔️\n"
            f"🗓️ Verify time : {days} দিন বাকি\n\n"
        )
        return message, None
        
    # ৩. ভেরিফাইড বা প্রিমিয়াম কোনোটাই না হলে
    message += (
        "⚠️ **আপনার অ্যাকাউন্টটি ভেরিফাইড নয়** ⛔\n\n"
        "💬 আপনার Withdraw আনলক করতে দয়া করে ভেরিফাই করুন।"
    )
    # VERIFY বাটন
    keyboard = [[InlineKeyboardButton(">>✅ VERIFY ✅<<", callback_data='start_verify')]]
    return message, InlineKeyboardMarkup(keyboard)


# --- মূল হ্যান্ডলার: VERIFY বাটন ক্লিক (স্টেটাস চেক) ---

async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """VERIFY বাটন চাপলে ইউজারের স্ট্যাটাস দেখায় এবং পরবর্তী স্টেটে নিয়ে যায়"""
    # মেসেজ থেকে আসলে:
    if update.message:
        user_id = update.effective_user.id
        # ডেটাবেস থেকে স্ট্যাটাস আনা
        status = main_bot.get_user_status(user_id) 
        is_premium, expiry_date, verify_expiry_date = status if status else (False, None, None)
        
        # মেসেজ ও বাটন তৈরি
        message, reply_markup = format_verify_status(is_premium, expiry_date, verify_expiry_date)
        
        await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
        # যদি ভেরিফাই না করা থাকে, তবে কনভার্সেশন শুরু
        if reply_markup:
            # যদি সরাসরি মেসেজ আসে, তবে সেটিকে স্টেট হ্যান্ডল করার জন্য ConversationHandler.END এ পাঠানো হচ্ছে
            # কারণ মূল লজিকটি CallbackQueryHandler দিয়ে শুরু হয়
            return ConversationHandler.END
        else:
            return ConversationHandler.END # কনভার্সেশন শেষ করা
    
    # Callback থেকে আসলে (সাধারণত VERIFY লজিক শুরু করতে)
    return ConversationHandler.END


# --- ধাপ ১: Method সিলেক্ট (Callback) ---

async def start_verify_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """VERIFY বাটন চাপলে পেমেন্ট মেথড দেখায়"""
    query = update.callback_query
    await query.answer()

    # স্ট্যাটাস চেক করে যদি ভেরিফাইড থাকে, তবে কনভার্সেশন শুরু করবে না
    user_id = query.effective_user.id
    status = main_bot.get_user_status(user_id) 
    is_premium, expiry_date, verify_expiry_date = status if status else (False, None, None)
    
    if (is_premium and expiry_date and expiry_date > datetime.now()) or \
       (verify_expiry_date and verify_expiry_date > datetime.now()):
        # ভেরিফাইড হলে শুধু একটি বার্তা দিয়ে কনভার্সেশন শেষ
        await context.bot.send_message(query.message.chat_id, "আপনার অ্যাকাউন্ট ইতিমধ্যেই ভেরিফাইড।")
        return ConversationHandler.END

    # পেমেন্ট বাটন
    keyboard = [
        [InlineKeyboardButton("💳 Bkash", callback_data='method_Bkash'),
         InlineKeyboardButton("💳 Nagad", callback_data='method_Nagad')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # নতুন মেসেজ পাঠানো
    await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="🏦 **Method সিলেক্ট করুন** 🏦",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

    return SELECT_METHOD # পরবর্তী স্টেটে যাওয়া


# --- ধাপ ২: Tnx ID গ্রহণ এবং সাবমিট ---

async def submit_tnx_form(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """পেমেন্ট ইনস্ট্রাকশন দেখানো এবং Tnx ID সংগ্রহের জন্য প্রস্তুত করা"""
    query = update.callback_query
    
    # ইউজারকে জানানো
    await query.answer("পেমেন্ট ইনস্ট্রাকশন দেখানো হচ্ছে...")
    
    # পেমেন্ট মেথড সেভ করা
    method = query.data.split('_')[1] # 'method_Bkash' থেকে 'Bkash' নেওয়া
    context.user_data['payment_method'] = method
    
    message = (
        f" 👉 এই **{method}** Personal অ্যাকাউন্টে **{VERIFY_AMOUNT:.2f} BDT** অর্থ প্রদান করতে **Send Money** ব্যবহার করুন!🏦\n"
        f"⛔ ব্যর্থ এড়াতে **সঠিক trxID পূরণ করুন**📝\n\n"
        f"💳{method} 💳   **PERSONAL**: `{PAYMENT_NUMBER}`\n\n"
        f"👉 এই নাম্বারে টাকা পাঠানোর পর আপনার **Tnx id** লিখুন 📝👇"
    )
    
    # ইনলাইন কীবোর্ড মুছে মেসেজ আপডেট করা
    await context.bot.edit_message_text(
        chat_id=query.message.chat_id,
        message_id=query.message.message_id,
        text=message,
        parse_mode='Markdown'
    )

    return SUBMIT_TNX # পরবর্তী স্টেটে যাওয়া

# --- ধাপ ৩: Tnx ID গ্রহণ এবং এডমিন নোটিফিকেশন ---

async def handle_tnx_submission(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """ইউজারের পাঠানো Tnx ID গ্রহণ করে ডেটাবেসে সেভ করা এবং এডমিনকে জানানো"""
    user = update.effective_user
    tnx_id = update.message.text.strip()
    method = context.user_data.get('payment_method')
    
    if not method:
        await update.message.reply_text("⛔ ত্রুটি: পেমেন্ট মেথড খুঁজে পাওয়া যায়নি। আবার মেনু বাটন ব্যবহার করুন।")
        return ConversationHandler.END

    # ১. ডেটাবেসে রিকোয়েস্ট সেভ করা
    conn = main_bot.connect_db()
    request_id = None
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO verify_requests (user_id, username, method, tnx_id, amount, status)
                VALUES (%s, %s, %s, %s, %s, 'pending')
                RETURNING request_id;
            """, (user.id, user.username, method, tnx_id, VERIFY_AMOUNT))
            request_id = cursor.fetchone()[0] # নতুন রিকোয়েস্ট ID নেওয়া হলো
            conn.commit()
            
            # ২. এডমিনকে নোটিফিকেশন মেসেজ তৈরি করা
            admin_message = (
                "🚨 **নতুন ভেরিফাই রিকোয়েস্ট এসেছে** 🚨\n\n"
                f"1️⃣ **{user.first_name}**\n"
                f"🗓️ Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"👤 username: @{user.username if user.username else 'নেই'}\n"
                f"🆔 user id: `{user.id}`\n"
                f"🏦 Method: {method}\n"
                f"📝 Tnx id: `{tnx_id}`\n\n"
            )
            
            # ৩. এডমিন বাটন তৈরি 
            keyboard = [
                [InlineKeyboardButton("✅ SUBMIT (Accept)", callback_data=f'v_accept_{request_id}_{user.id}'),
                 InlineKeyboardButton("❌ REJECT", callback_data=f'v_reject_{request_id}_{user.id}')]
            ]
            admin_markup = InlineKeyboardMarkup(keyboard)

            # ৪. এডমিনকে মেসেজ পাঠানো
            if main_bot.ADMIN_ID:
                await context.bot.send_message(chat_id=main_bot.ADMIN_ID, text=admin_message, reply_markup=admin_markup, parse_mode='Markdown')

            # ৫. ইউজারকে ধন্যবাদ মেসেজ পাঠানো
            user_thanks_message = (
                "🎉 **ধন্যবাদ। আপনার VERIFY রিকোয়েস্টটি সম্পূর্ণভাবে করা হয়েছে** 🎉\n"
                "📋 **Status: pending** 🔂\n\n"
                "🙏 দয়া করে অপেক্ষা করুন। আপনার ভেরিফাইটি 30 মিনিটের বেশি **'🔂 pending'** অবস্থায় থাকলে সরাসরি সাপোর্টে যোগাযোগ করুন।"
            )
            await update.message.reply_text(user_thanks_message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error saving verify request: {e}")
            await update.message.reply_text("⛔ ডেটাবেস ত্রুটি: আপনার রিকোয়েস্ট সেভ করা সম্ভব হয়নি।")
        finally:
            conn.close()

    # কনভার্সেশন শেষ করা
    return ConversationHandler.END


# --- ফলব্যাক হ্যান্ডলার ---
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("VERIFY প্রক্রিয়া বাতিল করা হলো।")
    return ConversationHandler.END


# --- এডমিন কন্ট্রোল হ্যান্ডলার ---

async def admin_verify_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('_')
    action = data[1] # accept বা reject
    request_id = int(data[2])
    target_user_id = int(data[3])
    
    requester_name = query.effective_user.first_name # এডমিন যিনি ক্লিক করলেন
    
    conn = main_bot.connect_db()
    if conn:
        try:
            cursor = conn.cursor()
            
            # ১. রিকোয়েস্ট স্ট্যাটাস চেক
            cursor.execute("SELECT status FROM verify_requests WHERE request_id = %s", (request_id,))
            current_status = cursor.fetchone()
            
            if current_status and current_status[0] != 'pending':
                await context.bot.edit_message_text(
                    chat_id=query.message.chat_id,
                    message_id=query.message.message_id,
                    text=f"🚫 রিকোয়েস্ট #{request_id} ইতিমধ্যেই **{current_status[0].upper()}** করা হয়েছে।\nBy: {requester_name}",
                )
                return
            
            # ২. স্ট্যাটাস আপডেট
            cursor.execute("UPDATE verify_requests SET status = %s WHERE request_id = %s", 
                           (action, request_id))
            conn.commit()
            
            # ৩. যদি ACCEPT হয়, তবে ইউজারদের স্ট্যাটাস আপডেট (১ মাস মেয়াদ বাড়ানো)
            if action == 'accept':
                new_expiry_date = datetime.now() + timedelta(days=VERIFY_DAYS)
                
                # is_premium, expiry_date, total_withdraw, verify_expiry_date
                # যদি ইতিমধ্যেই ভেরিফাইড থাকে, তবে মেয়াদ বাড়িয়ে দেওয়া
                cursor.execute("""
                    UPDATE users SET verify_expiry_date = %s
                    WHERE user_id = %s
                """, (new_expiry_date, target_user_id))
                conn.commit()
                
                # ইউজারকে জানানো
                user_message = (
                    "✅ **আপনার ভেরিফাইটি সফল হয়েছে।**\n"
                    f"🗓️ মেয়াদ: {VERIFY_DAYS} দিনের জন্য যুক্ত করা হলো।\n"
                    "💰 এখন আপনি সফলভাবে উইথড্র দিতে পারবেন।"
                )
                
            # ৪. যদি REJECT হয়
            elif action == 'reject':
                user_message = (
                    "❌ **আপনার ভেরিফাই রিকোয়েস্টটি বাতিল করা হয়েছে।**\n"
                    "⚠️ আপনার Tnx ID সঠিক ছিল না অথবা পেমেন্ট রিসিভ হয়নি।\n"
                    "অনুগ্রহ করে সঠিক Tnx ID দিয়ে আবার চেষ্টা করুন অথবা সাপোর্টে যোগাযোগ করুন।"
                )
                
            # ৫. এডমিন মেসেজ আপডেট
            await context.bot.edit_message_text(
                chat_id=query.message.chat_id,
                message_id=query.message.message_id,
                text=f"✅ রিকোয়েস্ট #{request_id} ({action.upper()}) সম্পন্ন হয়েছে।\n"
                     f"ইউজার ID: `{target_user_id}`\n"
                     f"By: {requester_name}",
            )
            
            # ৬. টার্গেট ইউজারকে মেসেজ পাঠানো
            await context.bot.send_message(chat_id=target_user_id, text=user_message, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error processing admin verify callback: {e}")
            await query.message.reply_text("⛔ প্রসেসিং ত্রুটি: এডমিন কন্ট্রোলে সমস্যা হয়েছে।")
        finally:
            conn.close()


# --- কনভার্সেশন হ্যান্ডলার ---

verify_conversation_handler = ConversationHandler(
    entry_points=[MessageHandler(main_bot.filters.Regex("^💾 VERIFY ✅$"), verify_command)],
    states={
        SELECT_METHOD: [
            CallbackQueryHandler(start_verify_flow, pattern='^start_verify$'),
            CallbackQueryHandler(submit_tnx_form, pattern='^method_(Bkash|Nagad)$'),
        ],
        SUBMIT_TNX: [
            # COMMAND ছাড়া যেকোনো মেসেজ (Tnx ID) গ্রহণ করা
            MessageHandler(TEXT & ~main_bot.filters.COMMAND, handle_tnx_submission),
        ],
    },
    fallbacks=[MessageHandler(main_bot.filters.COMMAND, cancel_conversation)],
    allow_reentry=True 
)
