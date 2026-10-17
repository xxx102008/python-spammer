import smtplib from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
import time
import random
import socks
import socket
from fake_useragent import UserAgent
import requests
from config import *

ua = UserAgent()

def set_proxy(proxy):
    if proxy:
        ip, port = proxy.split(':')
        socks.set_default_proxy(socks.SOCKS5, ip, int(port))
        socket.socket = socks.socksocket

def send_email(receiver, proxy=None):
    if proxy:
        set_proxy(proxy)
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = receiver
    msg['Subject'] = SUBJECT
    msg.attach(MIMEText(BODY, 'plain'))
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, receiver, msg.as_string())
        server.quit()
        print(f"נשלח אימייל ל-{receiver}")
        return True
    except Exception as e:
        print(f"שגיאה באימייל {receiver}: {e}")
        return False

def send_sms(to_number):
    url = f'https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json'
    data = {'From': TWILIO_FROM, 'To': to_number, 'Body': SMS_BODY}
    try:
        response = requests.post(url, data=data, auth=(TWILIO_SID, TWILIO_TOKEN))
        print(f"נשלח SMS ל-{to_number}: {response.status_code}")
        return True
    except Exception as e:
        print(f"שגיאה ב-SMS {to_number}: {e}")
        return False

def email_worker(email_chunk, proxies):
    for email in email_chunk:
        proxy = random.choice(proxies) if proxies else None
        send_email(email, proxy)
        time.sleep(random.uniform(0.3, 1.2))

def sms_worker(phone_chunk):
    for phone in phone_chunk:
        send_sms(phone)
        time.sleep(random.uniform(1, 3))

def load_list(filename): try:
        with open(filename, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]
    except:
        return []

def main():
    emails = load_list('emails.txt')
    phones = load_list('phones.txt')
    proxies = load_list('proxies.txt')
    
    print(f"נטענו {len(emails)} אימיילים, {len(phones)} טלפונים, {len(proxies)} פרוקסי")
    
    # threads לאימייל
    if emails:
        num_threads = min(8, len(emails))
        chunk_size = max(1, len(emails) // num_threads)
        threads = []
        for i in range(num_threads):
            chunk = emails[i*chunk_size:(i+1)*chunk_size]
            t = threading.Thread(target=email_worker, args=(chunk, proxies))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()
    
    # threads ל-SMS
    if phones:
        num_threads_sms = min(4, len(phones))
        chunk_size_sms = max(1, len(phones) // num_threads_sms)
        threads_sms = []
        for i in range(num_threads_sms):
            chunk = phones[i*chunk_size_sms:(i+1)*chunk_size_sms]
            t = threading.Thread(target=sms_worker, args=(chunk,))
            threads_sms.append(t)
            t.start()        for t in threads_sms:
            t.join()
    
    print("הסתיים השליחה")

if __name__ == "__main__":
    main()
