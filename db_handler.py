import os
import psycopg2
import logging

logger = logging.getLogger(__name__)

# ডেটাবেস সংযোগের URL এনভায়রনমেন্ট ভেরিয়েবল থেকে নেওয়া
DATABASE_URL = os.environ.get("DATABASE_URL")

def connect_db():
    """ডেটাবেসের সাথে সংযোগ স্থাপন করে।"""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        return None

def create_table_if_not_exists():
    """ইউজার এবং উইথড্র রিকোয়েস্ট টেবিল তৈরি করে।"""
    conn = connect_db()
    if conn:
        try:
            cur = conn.cursor()
            # 1. ইউজার টেবিল
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(50),
                    first_name VARCHAR(50),
                    balance NUMERIC(10, 2) DEFAULT 0.00,
                    wallet_address VARCHAR(100),
                    referred_by BIGINT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # 2. উইথড্র রিকোয়েস্ট টেবিল (যা আপনার প্রয়োজন)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS withdraw_requests (
                    request_id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    amount NUMERIC(10, 2) NOT NULL,
                    wallet_address VARCHAR(100) NOT NULL,
                    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'completed', 'rejected'
                    requested_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            logger.info("Database tables checked/completed successfully.")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
        finally:
            conn.close()

# --- হ্যান্ডলারের জন্য প্রয়োজনীয় অন্যান্য DB ফাংশন ---

def get_user_balance(user_id):
    conn = connect_db()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT balance FROM users WHERE user_id = %s", (user_id,))
            result = cur.fetchone()
            return result[0] if result else 0.00
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 0.00
        finally:
            conn.close()

def update_balance(user_id, amount_change):
    # নেগেটিভ বা পজিটিভ পরিবর্তন
    conn = connect_db()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE users SET balance = balance + %s WHERE user_id = %s",
                (amount_change, user_id)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Error updating balance: {e}")
        finally:
            conn.close()

def record_withdraw_request(user_id, amount, wallet_address):
    conn = connect_db()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO withdraw_requests (user_id, amount, wallet_address) VALUES (%s, %s, %s) RETURNING request_id",
                (user_id, amount, wallet_address)
            )
            request_id = cur.fetchone()[0]
            conn.commit()
            return request_id
        except Exception as e:
            logger.error(f"Error recording withdrawal request: {e}")
            return None
        finally:
            conn.close()
            
def update_withdraw_status(request_id, status):
    conn = connect_db()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                "UPDATE withdraw_requests SET status = %s WHERE request_id = %s AND status = 'pending' RETURNING user_id",
                (status, request_id)
            )
            user_id = cur.fetchone()[0] if cur.rowcount > 0 else None
            conn.commit()
            return (True, user_id) if user_id else (False, None)
        except Exception as e:
            logger.error(f"Error updating withdrawal status: {e}")
            return (False, None)
        finally:
            conn.close()

# get_user_data ফাংশনটি profile_handler এর জন্য (আপনার প্রোফাইল ফাংশন এটিকে db_handler এ আশা করে)
def get_user_data(user_id):
    conn = connect_db()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT username, first_name, wallet_address FROM users WHERE user_id = %s",
                (user_id,)
            )
            result = cur.fetchone()
            if result:
                return {
                    'username': result[0], 
                    'first_name': result[1],
                    'wallet_address': result[2] 
                }
            return {}
        except Exception as e:
            logger.error(f"Error getting user data: {e}")
            return {}
        finally:
            conn.close()
