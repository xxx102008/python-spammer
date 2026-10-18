# ===== 1. מי שולח (חובה) =====
EMAIL_SENDER   = "sp0mm0r999@gmail.com"
EMAIL_PASSWORD = "sqhmizrgbnuimbhy"

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT   = 587

# ===== 2. תוכן ההודעה =====
SENDER_NAME = "השם שלך"
SUBJECT     = "הודעה קצרה"
BODY        = """שלום,

רציתי לעדכן אותך לגבי משהו.
https://example.com

בברכה"""

# ===== 3. SMS - אופציונלי, ריק אם אין Twilio =====
TWILIO_SID   = ""
TWILIO_TOKEN = ""
TWILIO_FROM  = ""
SMS_BODY     = "הודעה קצרה"

# ===== 4. הגדרות שליחה =====
THREADS     = 4
DELAY_MIN   = 0.3
DELAY_MAX   = 1.2
USE_PROXY   = False
DAILY_CAP   = 450
LOG_FILE    = "sent.log"
FAILED_FILE = "failed.txt"
