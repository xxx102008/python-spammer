python
#!/usr/bin/env python3
# gui.py - ממשק בדפדפן לשליחת מיילים. בלי תלויות חיצוניות.
import json, os, queue, random, re, smtplib, threading, time, webbrowser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr, formatdate, make_msgid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.join(HERE, "settings.json")
PORT = int(os.environ.get("PORT", "8000"))

DEFAULTS = {
    "sender": "", "password": "",
    "smtp_server": "smtp.gmail.com", "smtp_port": "587",
    "sender_name": "", "subject": "הודעה קצרה",
    "body": "שלום,\n\nרציתי לספר לך משהו קצר.\nhttps://example.com\n\nבברכה",
    "emails": "", "limit": "0", "threads": "4",
    "delay_min": "0.3", "delay_max": "1.2",
}

LOCK = threading.Lock()
STATE = {"running": False, "sent": 0, "failed": 0, "total": 0, "stop": False, "log": []}
EMAIL_RE = re.compile(r"^[\w\.\-\+]+@[\w\-]+\.[\w\.\-]+$")

def load_settings():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return {**DEFAULTS, **json.load(f)}
    except Exception:
        return dict(DEFAULTS)

def save_settings(cfg):
    try:
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump({k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def add_log(line):
    with LOCK:
        STATE["log"].append(line)
        if len(STATE["log"]) > 500:
            STATE["log"] = STATE["log"][-500:]

def build_message(cfg, to_addr):
    msg = MIMEMultipart()
    name = cfg.get("sender_name") or ""
    msg["From"] = formataddr((str(Header(name, "utf-8")), cfg["sender"])) if name else cfg["sender"]
    msg["To"] = to_addr
    msg["Subject"] = Header(cfg["subject"], "utf-8")
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg["Reply-To"] = cfg["sender"]
    msg.attach(MIMEText(cfg["body"], "plain", "utf-8"))
    return msg

def connect(cfg):
    s = smtplib.SMTP(cfg["smtp_server"], int(cfg["smtp_port"]), timeout=30)
    s.ehlo()
    s.starttls()
    s.ehlo()
    s.login(cfg["sender"], cfg["password"])
    return s

def worker(cfg, q):
    try:
        server = connect(cfg)
    except Exception as e:
        add_log(f"כשל בחיבור: {e}")
        return
    while True:
        with LOCK:
            if STATE["stop"]:
                break
        try:
            addr = q.get_nowait()
        except queue.Empty:
            break
        try:
            server.sendmail(cfg["sender"], addr, build_message(cfg, addr).as_string())
            with LOCK:
                STATE["sent"] += 1
            add_log(f"נשלח -> {addr}")
        except Exception:
            try:
                server.quit()
            except Exception:
                pass
            try:
                server = connect(cfg)
                server.sendmail(cfg["sender"], addr, build_message(cfg, addr).as_string())
                with LOCK:
                    STATE["sent"] += 1
                add_log(f"נשלח (ניסיון שני) -> {addr}")
            except Exception as e2:
                with LOCK:
                    STATE["failed"] += 1
                add_log(f"נכשל -> {addr} | {e2}")
        time.sleep(random.uniform(float(cfg["delay_min"]), float(cfg["delay_max"])))
    try:
        server.quit()
    except Exception:
        pass

def run_job(cfg, addrs):
    with LOCK:
        STATE.update(running=True, sent=0, failed=0, total=len(addrs), stop=False, log=[])
    add_log(f"מתחיל לשלוח ל-{len(addrs)} נמענים")
    q = queue.Queue()
    for a in addrs:
        q.put(a)
    n = max(1, min(int(float(cfg["threads"])), len(addrs)))
    ts = [threading.Thread(target=worker, args=(cfg, q), daemon=True) for _ in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    with LOCK:
        STATE["running"] = False
        s, f = STATE["sent"], STATE["failed"]
    add_log(f"הסתיים. נשלחו {s}, נכשלו {f}")

def start_job(data):
    with LOCK:
        if STATE["running"]:
            return False, "כבר יש שליחה פעילה"
    cfg = {**DEFAULTS, **{k: str(v) for k, v in data.items() if k in DEFAULTS}}
    cfg["password"] = cfg["password"].replace(" ", "")
    if "@" not in cfg["sender"]:
        return False, "כתובת השולח חסרה או לא תקינה"
    if not cfg["password"]:
        return False, "סיסמת האפליקציה חסרה"
    if not cfg["subject"].strip():
        return False, "חסר נושא להודעה"
    if not cfg["body"].strip():
        return False, "חסר תוכן להודעה"

    raw = [l.strip() for l in cfg["emails"].replace(",", "\n").replace(";", "\n").splitlines()]
    seen, addrs, bad = set(), [], 0
    for a in raw:
        if not a or a.startswith("#"):
            continue
        a = a.lower()
        if not EMAIL_RE.match(a):
            bad += 1
            continue
        if a in seen:
        
