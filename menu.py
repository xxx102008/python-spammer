#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# menu.py - שולח מיילים עם תפריט. קורא הגדרות מ-config.py ומ-settings.json

import importlib.util, json, os, queue, random, re, smtplib, threading, time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr, formatdate, make_msgid

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(HERE, "settings.json")
CONFIG_FILE = os.path.join(HERE, "config.py")
RECIPIENTS_FILE = os.path.join(HERE, "emails.txt")
FAILED_FILE = os.path.join(HERE, "failed.txt")

EMAIL_RE = re.compile(r"^[\w\.\-\+]+@[\w\-]+\.[\w\.\-]+$")

DEFAULTS = {
    "sender": "",
    "password": "",
    "sender_name": "",
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "subject": "הודעה קצרה",
    "body": "שלום,\n\nרציתי לספר לך משהו קצר.\n\nבברכה",
    "threads": 4,
    "delay_min": 0.3,
    "delay_max": 1.2,
}


# ---------------- טעינה ושמירה ----------------
def from_config_file():
    """לוקח את הפרטים שכבר מילאת ב-config.py"""
    out = {}
    try:
        spec = importlib.util.spec_from_file_location("userconfig", CONFIG_FILE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for key, attr in (
            ("sender", "EMAIL_SENDER"),
            ("password", "EMAIL_PASSWORD"),
            ("sender_name", "SENDER_NAME"),
            ("subject", "SUBJECT"),
            ("body", "BODY"),
            ("smtp_server", "SMTP_SERVER"),
            ("smtp_port", "SMTP_PORT"),
        ):
            val = getattr(mod, attr, None)
            if val:
                out[key] = str(val)
        if out.get("password"):
            out["password"] = out["password"].replace(" ", "")
    except Exception:
        pass
    return out


def load_cfg():
    cfg = {**DEFAULTS, **from_config_file()}
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        for k, v in saved.items():
            if k in DEFAULTS and v not in (None, ""):
                cfg[k] = v
    except Exception:
        pass
    return cfg


def save_cfg(cfg):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump({k: cfg.get(k, DEFAULTS[k]) for k in DEFAULTS}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def load_recipients():
    try:
        with open(RECIPIENTS_FILE, encoding="utf-8") as f:
            return [l.strip().lower() for l in f if l.strip() and not l.startswith("#")]
    except FileNotFoundError:
        return []


def save_recipients(addrs):
    with open(RECIPIENTS_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(addrs))


# ---------------- עזרים ----------------
def clear():
    os.system("cls" if os.name == "nt" else "clear")


def ask(prompt, default=None):
    hint = f" [{default}]" if default not in (None, "") else ""
    val = input(f"{prompt}{hint}: ").strip()
    return val if val else (default if default is not None else "")


def pause(msg="\nEnter להמשך..."):
    input(msg)


def line(n=42):
    print("-" * n)


# ---------------- שליחה ----------------
def build_message(cfg, to_addr):
    msg = MIMEMultipart()
    if cfg.get("sender_name"):
        msg["From"] = formataddr((str(Header(cfg["sender_name"], "utf-8")), cfg["sender"]))
    else:
        msg["From"] = cfg["sender"]
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


def send_job(cfg, addrs):
    total = len(addrs)
    q = queue.Queue()
    for a in addrs:
        q.put(a)

    lock = threading.Lock()
    counter = {"i": 0, "ok": 0, "bad": 0}
    failed = []

    def worker():
        try:
            server = connect(cfg)
        except Exception as e:
            print(f"\n  ! כשל בחיבור: {e}")
            return
        while True:
            try:
                addr = q.get_nowait()
            except queue.Empty:
                break
            status = ""
            try:
                server.sendmail(cfg["sender"], addr, build_message(cfg, addr).as_string())
                status = "נשלח"
            except Exception:
                try:
                    server.quit()
                except Exception:
                    pass
                try:
                    server = connect(cfg)
                    server.sendmail(cfg["sender"], addr, build_message(cfg, addr).as_string())
                    status = "נשלח (ניסיון שני)"
                except Exception as e2:
                    status = f"נכשל: {e2}"
            with lock:
                counter["i"] += 1
                if status.startswith("נשלח"):
                    counter["ok"] += 1
                else:
                    counter["bad"] += 1
                    failed.append(addr)
                print(f"  [{counter['i']}/{total}] {status} -> {addr}")
            time.sleep(random.uniform(float(cfg["delay_min"]), float(cfg["delay_max"])))
        try:
            server.quit()
        except Exception:
            pass

    n = max(1, min(int(cfg["threads"]), total))
    print(f"\nשולח ל-{total} נמענים עם {n} חוטים...\n")
    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    print()
    line()
    print(f"  נשלחו: {counter['ok']}   |   נכשלו: {counter['bad']}")
    if failed:
        with open(FAILED_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(failed) + "\n")
        print(f"  הכתובות שנכשלו נשמרו ב-{FAILED_FILE}")
    line()


# ---------------- מסכים ----------------
def screen_test(cfg):
    clear()
    print("=== בדיקת חיבור ===\n")
    print(f"  שרת:   {cfg['smtp_server']}:{cfg['smtp_port']}")
    print(f"  משתמש: {cfg['sender'] or '(חסר!)'}")
    print(f"  סיסמה: {'יש' if cfg['password'] else '(חסרה!)'}")
    print()
    if not cfg["sender"] or not cfg["password"]:
        print("! קודם תמלא את החשבון (אפשרות 6).")
        pause()
        return
    try:
        print("מתחבר לשרת...")
        s = smtplib.SMTP(cfg["smtp_server"], int(cfg["smtp_port"]), timeout=30)
        s.ehlo()
        s.starttls()
        s.ehlo()
        print("מתחבר לחשבון...")
        s.login(cfg["sender"], cfg["password"])
        s.quit()
        print("\nהצלחה! החשבון תקין והסיסמה נכונה.")
    except smtplib.SMTPAuthenticationError as e:
        print(f"\n! שגיאת התחברות: {e}")
        print("  בדוק: סיסמת אפליקציה של 16 תווים, ואימות דו-שלבי דלוק בגוגל.")
    except Exception as e:
        print(f"\n! שגיאה: {type(e).__name__}: {e}")
    pause()


def screen_account(cfg):
    clear()
    print("=== הגדרות החשבון ===\n")
    print("חייב להיות חשבון ג'ימייל אמיתי + סיסמת אפליקציה של 16 תווים.\n")
    cfg["sender"] = ask("כתובת המייל", cfg["sender"])
    pwd = ask("סיסמת אפליקציה (אפשר עם רווחים)", cfg["password"])
    cfg["password"] = pwd.replace(" ", "")
    cfg["sender_name"] = ask("השם שיופיע לנמען (לא חובה)", cfg["sender_name"])
    save_cfg(cfg)
    print("\nנשמר.")
    pause()


def screen_message(cfg):
    clear()
    print("=== תוכן ההודעה ===\n")
    print("הנושא הנוכחי:")
    print(f"  {cfg['subject']}\n")
    print("התוכן הנוכחי:")
    print("  " + cfg["body"].replace("\n", "\n  "))
    print()
    if ask("לערוך? (y/n)", "y").lower().startswith("y"):
        cfg["subject"] = ask("נושא חדש", cfg["subject"])
        print("\nתוכן חדש. לכתוב \\n בשביל ירידת שורה. לסיום שורה ריקה:")
        print("(אם לא תכתוב כלום - יישאר הנוכחי)")
        rows = []
        while True:
            r = input()
            if r == "" and rows:
                break
            rows.append(r.replace("\\n", "\n"))
        if rows:
            cfg["body"] = "\n".join(rows)
        save_cfg(cfg)
        print("\nנשמר.")
    pause()


def screen_recipients(addrs):
    while True:
        clear()
        print("=== רשימת הנמענים ===\n")
        print(f"כרגע ברשימה: {len(addrs)} כתובות\n")
        print("  1. הוסף כתובות")
        print("  2. הצג את הרשימה")
        print("  3. מחק כתובת מסוימת")
        print("  4. מחק הכל")
        print("  0. חזור")
        print()
        c = ask("בחר")

        if c == "1":
            print("\nהדבק כתובות - אחת בכל שורה. לסיום: שורה ריקה ואז Enter")
            print("(אפשר גם עם פסיקים או רווחים באמצע)\n")
            added, bad = 0, 0
            while True:
                row = input().strip()
                if row == "":
                    break
                for part in re.split(r"[,;\s]+", row):
                    part = part.lower()
                    if not part:
                        continue
                    if EMAIL_RE.match(part):
                        if part not in addrs:
                            addrs.append(part)
                            added += 1
                    else:
                        bad += 1
            save_recipients(addrs)
            print(f"\nנוספו {added} כתובות" + (f" | נפסלו {bad}" if bad else ""))
            pause()

        elif c == "2":
            clear()
            print(f"=== {len(addrs)} כתובות ===\n")
            for i, a in enumerate(addrs, 1):
                print(f"  {i}. {a}")
            pause()

        elif c == "3":
            a = ask("הדבק את הכתובת למחיקה").lower()
            if a in addrs:
                addrs.remove(a)
                save_recipients(addrs)
                print("נמחק.")
            else:
                print("לא נמצא.")
            pause()

        elif c == "4":
            if ask("למחוק את כל הרשימה? (y/n)", "n").lower().startswith("y"):
                addrs.clear()
                save_recipients(addrs)
                print("הרשימה רוקנה.")
            pause()

        elif c == "0":
            return addrs


def screen_speed(cfg):
    clear()
    print("=== מהירות שליחה ===\n")
    print("חוטים = כמה מיילים נשלחים במקביל. עם ג'ימייל: 3 עד 5.")
    print("השהיה = הפסקה בין מייל למייל, בשניות.\n")
    cfg["threads"] = int(ask("חוטים", cfg["threads"]) or cfg["threads"])
    cfg["delay_min"] = float(ask("השהיה מינימלית", cfg["delay_min"]) or cfg["delay_min"])
    cfg["delay_max"] = float(ask("השהיה מקסימלית", cfg["delay_max"]) or cfg["delay_max"])
    save_cfg(cfg)
    print("\nנשמר.")
    pause()


def screen_summary(cfg, addrs):
    clear()
    print("=== סיכום ===\n")
    print(f"  שולח:      {cfg['sender'] or '(לא מוגדר!)'}")
    print(f"  סיסמה:     {'מוגדרת' if cfg['password'] else '(חסרה!)'}")
    print(f"  נמענים:    {len(addrs)}")
    print(f"  נושא:      {cfg['subject']}")
    print(f"  חוטים:     {cfg['threads']}")
    print(f"  השהיה:     {cfg['delay_min']}-{cfg['delay_max']} שניות")
    if addrs:
        est = len(addrs) * (float(cfg["delay_min"]) + float(cfg["delay_max"])) / 2 / max(1, int(cfg["threads"]))
        print(f"  זמן משוער: כ-{int(est // 60)} דקות {int(est % 60)} שניות")
    print("\n  תוכן:")
    print("  " + cfg["body"].replace("\n", "\n  "))
    print()
    if len(addrs) > 450:
        print(f"  ! שים לב: יש לך {len(addrs)} נמענים, ומכסת ג'ימייל היא ~500 ביום.")
    pause()


def do_send(cfg, addrs, limit=None):
    if not cfg["sender"] or not cfg["password"]:
        print("\n! אין חשבון מוגדר. תלחץ 6 ותמלא מייל + סיסמה.")
        pause()
        return
    if not addrs:
        print("\n! הרשימה ריקה. תלחץ 4 ותוסיף כתובות.")
        pause()
        return
    target = addrs[:limit] if limit else addrs
    clear()
    print(f"עומד לשלוח ל-{len(target)} נמענים.")
    if not ask("להתחיל? (y/n)", "y").lower().startswith("y"):
        return
    send_job(cfg, target)
    pause()


def main():
    cfg = load_cfg()
    addrs = load_recipients()

    while True:
        clear()
        print("=" * 42)
        print("            ש ו ל ח   ה מ י י ל י ם")
        print("=" * 42)
        if cfg["sender"]:
            print(f"  חשבון:  {cfg['sender']}")
        else:
            print("  חשבון:  ! לא מוגדר - תלחץ 6")
        print(f"  נמענים: {len(addrs)}")
        print(f"  נושא:   {cfg['subject']}")
        line()
        print("  1. שלח לכולם")
        print("  2. שלח לכמה ראשונים")
        print("  3. שלח לכתובת אחת (בדיקה)")
        print("  4. רשימת הנמענים")
        print("  5. תוכן ההודעה")
        print("  6. הגדרות החשבון")
        print("  7. מהירות שליחה")
        print("  8. הצג סיכום")
        print("  9. בדיקת חיבור")
        print("  0. יציאה")
        line()
        c = ask("בחר")

        if c == "1":
            do_send(cfg, addrs)
        elif c == "2":
            try:
                n = int(ask("כמה לשלוח", "10"))
            except ValueError:
                n = 10
            do_send(cfg, addrs, n)
        elif c == "3":
            a = ask("כתובת לבדיקה").lower()
            if EMAIL_RE.match(a):
                do_send(cfg, [a])
            else:
                print("\n! כתובת לא תקינה.")
                pause()
        elif c == "4":
            addrs = screen_recipients(addrs)
        elif c == "5":
            screen_message(cfg)
        elif c == "6":
            screen_account(cfg)
        elif c == "7":
            screen_speed(cfg)
        elif c == "8":
            screen_summary(cfg, addrs)
        elif c == "9":
            screen_test(cfg)
        elif c == "0":
            save_cfg(cfg)
            save_recipients(addrs)
            print("\nנשמר. להתראות.")
            break
        else:
            print("\n! אין אפשרות כזו.")
            pause()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nיצאת.")
