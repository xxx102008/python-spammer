import smtplib, socket, time, random, logging, threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr, formatdate, make_msgid

import socks
import requests
from config import *

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s",
                    encoding="utf-8")


class SocksSMTP(smtplib.SMTP):
    proxy = None

    def _get_socket(self, host, port, timeout):
        if self.proxy:
            ip, p = self.proxy.split(":")
            return socks.create_connection(
                (host, port), timeout,
                proxy_type=socks.SOCKS5, proxy_addr=ip, proxy_port=int(p))
        return super()._get_socket(host, port, timeout)


def build_message(cfg, to_addr):
    msg = MIMEMultipart()
    if cfg.get("sender_name"):
        msg["From"] = formataddr((str(Header(cfg["sender_name"], "utf-8")), cfg["sender"]))
    else:
        msg["From"] = cfg["sender"]
    msg["To"] = to_addr
    msg["Subject"] = Header(cfg["subject"], "utf-8")
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="gmail.com")
    msg["Reply-To"] = cfg["sender"]
    msg["List-Unsubscribe"] = f"<mailto:{cfg['sender']}?subject=unsubscribe>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.attach(MIMEText(cfg["body"], "plain", "utf-8"))
    return msg


def connect(proxy=None):
    cls = SocksSMTP if proxy else smtplib.SMTP
    s = cls(SMTP_SERVER, SMTP_PORT, timeout=30)
    if proxy:
        s.proxy = proxy
    s.ehlo()
    s.starttls()
    s.ehlo()
    s.login(EMAIL_SENDER, EMAIL_PASSWORD)
    return s


def load_list(path):
    try:
        with open(path, encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip() and not l.startswith("#")]
    except FileNotFoundError:
        return []


def save_failed(x):
    with open(FAILED_FILE, "a", encoding="utf-8") as f:
        f.write(x + "\n")


def email_worker(chunk, proxies):
    proxy = random.choice(proxies) if (USE_PROXY and proxies) else None
    attempts = [proxy, None] if proxy else [None]

    server = None
    for attempt in attempts:
        try:
            server = connect(attempt)
            print("  [חיבור]", attempt or "ישיר")
            break
        except Exception as e:
            logging.warning(f"כשל בחיבור ({attempt}): {e}")

    if server is None:
        print("  אין חיבור בכלל - בדוק את config.py")
        return

    for addr in chunk:
        try:
            server.sendmail(EMAIL_SENDER, addr, build_message(addr).as_string())
            logging.info(f"OK {addr}")
            print("  נשלח ->", addr)
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPException, socket.error) as e:
            logging.warning(f"ניתוק על {addr}: {e}")
            try:
                server.quit()
            except Exception:
                pass
            try:
                server = connect(proxy)
                server.sendmail(EMAIL_SENDER, addr, build_message(addr).as_string())
                logging.info(f"OK-retry {addr}")
                print("  נשלח (ניסיון שני) ->", addr)
            except Exception as e2:
                logging.error(f"FAIL {addr}: {e2}")
                save_failed(addr)
        time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

    try:
        server.quit()
    except Exception:
        pass


def send_sms(num):
    url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json"
    try:
        r = requests.post(url, data={"From": TWILIO_FROM, "To": num, "Body": SMS_BODY},
                          auth=(TWILIO_SID, TWILIO_TOKEN), timeout=30)
        logging.info(f"SMS {num} -> {r.status_code}")
        print("  נשלח SMS ->", num)
    except Exception as e:
        logging.error(f"SMS FAIL {num}: {e}")
        save_failed(num)


def sms_worker(chunk):
    for p in chunk:
        send_sms(p)
        time.sleep(random.uniform(1, 3))


def run_threads(items, worker, n, extra=None):
    n = max(1, min(n, len(items)))
    size = -(-len(items) // n)
    ts = []
    for i in range(n):
        chunk = items[i * size:(i + 1) * size]
        if not chunk:
            continue
        args = (chunk, extra) if extra is not None else (chunk,)
        t = threading.Thread(target=worker, args=args)
        t.start()
        ts.append(t)
    for t in ts:
        t.join()


def main():
    emails = load_list("emails.txt")
    phones = load_list("phones.txt")
    proxies = load_list("proxies.txt")
    print(f"נטענו: {len(emails)} מיילים | {len(phones)} טלפונים | {len(proxies)} פרוקסי")

    if emails:
        todo = emails[:DAILY_CAP]
        if len(emails) > DAILY_CAP:
            print(f"שים לב: {len(emails)} נמענים, מכסה יומית ~{DAILY_CAP}. שולח {len(todo)}.")
        run_threads(todo, email_worker, THREADS, proxies)

    if phones and TWILIO_SID:
        run_threads(phones, sms_worker, 2)

    print("הסתיים. לוג: sent.log | כשלים: failed.txt")


if __name__ == "__main__":
    main()
