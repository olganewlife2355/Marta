#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FoxyBox — локальний інструмент рекрутера для теплої розсилки перших
повідомлень кандидатам у Telegram з особистого акаунта (MTProto, не бот).

Працює повністю на вашому комп'ютері. Нічого не надсилає на чужі сервери,
окрім самих повідомлень у Telegram через ваш акаунт.

Запуск:
    python3 foxybox.py

Тестовий режим (нічого реально не шле):
    FOXYBOX_DRY=1 python3 foxybox.py
"""

import os
import re
import sys
import json
import time
import random
import asyncio
import logging
import threading
import webbrowser
from queue import Queue
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ─────────────────────────────────────────────────────────────────────────────
#  1. НАЛАШТУВАННЯ TELEGRAM
#     Ці два значення ви отримаєте на https://my.telegram.org (крок 2).
#     Вставте їх сюди між лапками. Тримайте цей файл приватним.
# ─────────────────────────────────────────────────────────────────────────────
API_ID = 0                     # <-- сюди число (наприклад 1234567)
API_HASH = ""                  # <-- сюди рядок (наприклад "a1b2c3...")

# ─────────────────────────────────────────────────────────────────────────────
#  Загальні константи
# ─────────────────────────────────────────────────────────────────────────────
HOST = "127.0.0.1"
PORT = 8770
DAILY_LIMIT = 30               # максимум повідомлень на день
PAUSE_MIN = 18                 # мінімальна пауза між відправками, секунд
PAUSE_MAX = 24                 # максимальна пауза між відправками, секунд

# Пости в групи — окремі, суворіші ліміти. Групи чутливіші до спаму, ніж
# особисті повідомлення: за часті пости в чати легко впіймати обмеження.
GROUP_DAILY_LIMIT = 10         # максимум постів у групи на день
GROUP_PAUSE_MIN = 45           # мінімальна пауза між постами, секунд
GROUP_PAUSE_MAX = 90           # максимальна пауза між постами, секунд
try:
    TZ = ZoneInfo("Europe/Paris")  # ліміт скидається о 00:00 CET
except Exception:
    # На Windows часто нема системної бази таймзон — треба пакет tzdata.
    TZ = None

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "foxybox_db.json"           # база першого («головного») акаунта
SESSION_PATH = HERE / "foxybox_session"      # файл сесії Telegram
ACCOUNTS_PATH = HERE / "foxybox_accounts.json"   # список доданих акаунтів
MAIN_ACC = "main"                            # id першого акаунта
LOG_PATH = HERE / "foxybox.log"
INDEX_PATH = HERE / "index.html"

DRY = os.environ.get("FOXYBOX_DRY", "") in ("1", "true", "yes")

# ─────────────────────────────────────────────────────────────────────────────
#  Логування у файл
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    filename=str(LOG_PATH),
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
)
log = logging.getLogger("foxybox")
# щоб не засмічувати консоль зайвим від telethon
logging.getLogger("telethon").setLevel(logging.WARNING)


def today_str() -> str:
    """Сьогоднішня дата у поясі CET (Europe/Paris)."""
    return datetime.now(TZ).strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


# ─────────────────────────────────────────────────────────────────────────────
#  Акаунти
#  Кожен акаунт має власний файл сесії та власну базу контактів: ліміти
#  Telegram рахуються на акаунт, тож змішувати їх не можна.
# ─────────────────────────────────────────────────────────────────────────────
_acc_lock = threading.Lock()


def _default_accounts() -> dict:
    return {"current": MAIN_ACC, "accounts": []}


def load_accounts() -> dict:
    """Читає список акаунтів; за потреби підхоплює старий одиночний вхід."""
    data = _default_accounts()
    if ACCOUNTS_PATH.exists():
        try:
            with open(ACCOUNTS_PATH, "r", encoding="utf-8") as f:
                data.update(json.load(f))
        except Exception as e:
            log.error("Не вдалося прочитати список акаунтів: %s", e)

    # міграція: був один вхід ще до появи мультиакаунтів — робимо його головним
    if not data["accounts"] and SESSION_PATH.with_suffix(".session").exists():
        data["accounts"] = [{"id": MAIN_ACC, "title": "Основний акаунт",
                             "username": None, "phone": None}]
        data["current"] = MAIN_ACC

    ids = [a["id"] for a in data["accounts"]]
    if data["current"] not in ids:
        data["current"] = ids[0] if ids else MAIN_ACC
    return data


def save_accounts(data: dict) -> None:
    tmp = ACCOUNTS_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.replace(ACCOUNTS_PATH)


def session_path_for(acc_id: str) -> Path:
    """Файл сесії акаунта. Головний лишається зі старою назвою."""
    if acc_id == MAIN_ACC:
        return SESSION_PATH
    return HERE / f"foxybox_session_{acc_id}"


def db_path_for(acc_id: str) -> Path:
    """База контактів акаунта. Головний лишається зі старою назвою."""
    if acc_id == MAIN_ACC:
        return DB_PATH
    return HERE / f"foxybox_db_{acc_id}.json"


def current_acc_id() -> str:
    return load_accounts()["current"]


def next_acc_id(existing: list) -> str:
    """Вигадує вільний id для нового акаунта: acc2, acc3…"""
    n = 2
    while f"acc{n}" in existing:
        n += 1
    return f"acc{n}"


# ─────────────────────────────────────────────────────────────────────────────
#  База даних (JSON на диску) — своя на кожен акаунт
# ─────────────────────────────────────────────────────────────────────────────
_db_lock = threading.Lock()


def _default_db() -> dict:
    return {
        "contacts": {}, "daily_sent": {}, "total_sent": 0,
        # історія постів у групи
        "groups": {}, "group_daily_sent": {}, "total_group_sent": 0,
        # журнал опублікованих постів — для дашборда статистики
        "posts": [],
    }


def load_db(acc_id: str = None) -> dict:
    path = db_path_for(acc_id or current_acc_id())
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # підстрахуємось на випадок неповного файлу
            base = _default_db()
            base.update(data)
            return base
        except Exception as e:
            log.error("Не вдалося прочитати базу, створюю нову: %s", e)
    return _default_db()


def save_db(db: dict, acc_id: str = None) -> None:
    path = db_path_for(acc_id or current_acc_id())
    tmp = path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def norm_username(u: str) -> str:
    """Нормалізує юзернейм: прибирає пробіли, @ і посилання t.me/."""
    u = u.strip()
    if not u:
        return ""
    u = u.split("?")[0]
    u = u.replace("https://", "").replace("http://", "")
    for p in ("t.me/", "telegram.me/", "telegram.dog/"):
        if u.lower().startswith(p):
            u = u[len(p):]
    u = u.lstrip("@").strip()
    return u


def stats(db: dict) -> dict:
    sent_today = db["daily_sent"].get(today_str(), 0)
    g_today = db.get("group_daily_sent", {}).get(today_str(), 0)
    return {
        "total_contacts": len(db["contacts"]),
        "total_sent": db.get("total_sent", 0),
        "sent_today": sent_today,
        "remaining_today": max(0, DAILY_LIMIT - sent_today),
        "limit": DAILY_LIMIT,
        # пости в групи
        "total_groups": len(db.get("groups", {})),
        "total_group_sent": db.get("total_group_sent", 0),
        "group_sent_today": g_today,
        "group_remaining_today": max(0, GROUP_DAILY_LIMIT - g_today),
        "group_limit": GROUP_DAILY_LIMIT,
        "dry": DRY,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Витяг назви вакансії з тексту пічу
# ─────────────────────────────────────────────────────────────────────────────
# ключові слова, після яких очікуємо назву вакансії
_VAC_RE = re.compile(
    r"(?:вакансі\w*|позиці\w*|посад\w*|рол[іьяе]\w*|шука\w+|потріб\w+|"
    r"hiring|looking\s+for|position|role|vacancy|opening)"
    r"\s*(?:[:\-–—]\s*)?",
    re.IGNORECASE,
)

# слова-межі: на них назва вакансії закінчується
_STOP = {
    "в", "у", "на", "до", "з", "із", "зі", "для", "і", "та", "й", "а", "але",
    "який", "яка", "яке", "які", "що", "щоб", "як", "бо", "це", "наш", "нашу",
    "нашій", "нашої", "нашого", "команду", "команді", "команда", "проєкт",
    "проект", "компанію", "компанії",
    "in", "on", "for", "to", "with", "our", "the", "and", "at", "of", "a", "an",
}
# артиклі, які пропускаємо на початку
_LEAD_SKIP = {"a", "an", "the", "досвідчений", "досвідчену", "сильного", "класного"}
_WORD_OK = re.compile(r"^[A-Za-zА-Яа-яЇїІіЄєҐґ0-9][A-Za-zА-Яа-яЇїІіЄєҐґ0-9\+\#/\.\-&]*$")


def extract_vacancy(text: str) -> str:
    """Повертає назву вакансії (1-4 слова), витягнуту з тексту, або ''."""
    if not text:
        return ""
    m = _VAC_RE.search(text)
    if not m:
        return ""
    tail = text[m.end():].strip().strip("«»\"'“”").strip()
    if not tail:
        return ""

    words = []
    for tok in tail.split():
        clean = tok.strip("«»\"'“”.,;:!?()").strip()
        low = clean.lower()
        # пропускаємо провідні артиклі/прикметники, поки не набрали слів
        if not words and low in _LEAD_SKIP:
            continue
        if not clean or not _WORD_OK.match(clean):
            break
        if low in _STOP:
            break
        words.append(clean)
        if len(words) >= 4:
            break
        # якщо в токені була кома/крапка в кінці — це кінець фрази
        if tok[-1:] in ".,;:!?":
            break
    return " ".join(words)


# ─────────────────────────────────────────────────────────────────────────────
#  Telegram (Telethon) у власному asyncio-циклі на фоновому потоці
# ─────────────────────────────────────────────────────────────────────────────
from telethon import TelegramClient, errors  # noqa: E402

_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)
client = None  # створюється в main() після перевірки ключів (build_client)

_me_cache = {"name": None, "username": None, "authorized": False}


def build_client(acc_id: str = None):
    """Створює клієнт для потрібного акаунта (не підключаючи його)."""
    global client
    acc_id = acc_id or current_acc_id()
    client = TelegramClient(str(session_path_for(acc_id)), API_ID, API_HASH, loop=_loop)
    return client
_campaign_lock = threading.Lock()  # лише одна розсилка одночасно


def run_coro(coro):
    """Виконати корутину в циклі Telethon з фонового HTTP-потоку."""
    return asyncio.run_coroutine_threadsafe(coro, _loop).result()


async def _refresh_me():
    try:
        if await client.is_user_authorized():
            me = await client.get_me()
            _me_cache["authorized"] = True
            _me_cache["name"] = " ".join(
                x for x in [me.first_name, me.last_name] if x
            ).strip() or "—"
            _me_cache["username"] = ("@" + me.username) if me.username else None
        else:
            _me_cache["authorized"] = False
    except Exception as e:
        log.error("refresh_me: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
#  Перемикання акаунтів і вхід через браузер
# ─────────────────────────────────────────────────────────────────────────────
# проміжний стан входу: клієнт, якому вже надіслано код
_login = {"client": None, "phone": None, "hash": None, "acc_id": None}


async def switch_to(acc_id: str) -> dict:
    """Відключає поточний акаунт і підключає вибраний."""
    global client
    old = client
    try:
        if old is not None:
            await old.disconnect()
    except Exception as e:
        log.warning("disconnect old client: %s", e)

    _group_entities.clear()          # групи в кожного акаунта свої
    _me_cache.update({"name": None, "username": None, "authorized": False})

    build_client(acc_id)
    await client.connect()
    await _refresh_me()

    with _acc_lock:
        data = load_accounts()
        data["current"] = acc_id
        for a in data["accounts"]:
            if a["id"] == acc_id and _me_cache["username"]:
                a["username"] = _me_cache["username"]
                if a.get("title") in (None, "", "Основний акаунт") and a["id"] != MAIN_ACC:
                    a["title"] = _me_cache["username"]
        save_accounts(data)

    log.info("switched to account %s (%s)", acc_id, _me_cache["username"])
    return {"id": acc_id, "authorized": _me_cache["authorized"],
            "me": _me_cache["username"] or _me_cache["name"]}


async def login_send_code(phone: str) -> dict:
    """Крок 1 входу: просимо Telegram надіслати код на номер."""
    await login_cancel()
    existing = [a["id"] for a in load_accounts()["accounts"]]
    # найперший акаунт отримує звичну назву сесії, наступні — acc2, acc3…
    tmp_id = MAIN_ACC if not existing else next_acc_id(existing)
    c = TelegramClient(str(session_path_for(tmp_id)), API_ID, API_HASH, loop=_loop)
    await c.connect()
    sent = await c.send_code_request(phone)
    _login.update({"client": c, "phone": phone, "hash": sent.phone_code_hash,
                   "acc_id": tmp_id})
    log.info("login: code sent to %s (acc %s)", phone, tmp_id)
    return {"ok": True}


async def login_sign_in(code: str) -> dict:
    """Крок 2: код із Telegram. Може попросити хмарний пароль."""
    c = _login["client"]
    if c is None:
        return {"error": "Спершу введіть номер телефону."}
    try:
        await c.sign_in(phone=_login["phone"], code=code,
                        phone_code_hash=_login["hash"])
    except errors.SessionPasswordNeededError:
        return {"need_password": True}
    return await _finish_login()


async def login_password(password: str) -> dict:
    """Крок 3: хмарний пароль (двоетапна перевірка)."""
    c = _login["client"]
    if c is None:
        return {"error": "Спершу введіть номер телефону."}
    await c.sign_in(password=password)
    return await _finish_login()


async def _finish_login() -> dict:
    """Записує новий акаунт у список і перемикається на нього."""
    c = _login["client"]
    me = await c.get_me()
    username = ("@" + me.username) if me.username else None
    title = username or " ".join(x for x in [me.first_name, me.last_name] if x).strip() \
        or _login["phone"]
    acc_id = _login["acc_id"]

    await c.disconnect()          # далі працюємо через основний client
    _login.update({"client": None, "phone": None, "hash": None})

    with _acc_lock:
        data = load_accounts()
        if not any(a["id"] == acc_id for a in data["accounts"]):
            data["accounts"].append({"id": acc_id, "title": title,
                                     "username": username, "phone": None})
        save_accounts(data)

    log.info("login: added account %s (%s)", acc_id, title)
    res = await switch_to(acc_id)
    res["added"] = title
    return res


async def login_cancel():
    """Прибирає недороблений вхід (наприклад, якщо передумали на коді)."""
    c = _login.get("client")
    if c is not None:
        try:
            await c.disconnect()
        except Exception:
            pass
        # недороблена сесія нам не потрібна
        try:
            f = Path(str(session_path_for(_login["acc_id"])) + ".session")
            if f.exists() and not any(a["id"] == _login["acc_id"]
                                      for a in load_accounts()["accounts"]):
                f.unlink()
        except Exception as e:
            log.warning("login_cancel cleanup: %s", e)
    _login.update({"client": None, "phone": None, "hash": None})


async def account_logout(acc_id: str) -> dict:
    """Виходить з акаунта і прибирає його зі списку (база лишається)."""
    data = load_accounts()
    if not any(a["id"] == acc_id for a in data["accounts"]):
        return {"error": "Такого акаунта немає."}
    if len(data["accounts"]) <= 1:
        return {"error": "Це єдиний акаунт — видаляти нема сенсу."}

    global client
    was_current = (data["current"] == acc_id)
    try:
        if was_current:
            await client.log_out()          # log_out сам відключає клієнта
        else:
            c = TelegramClient(str(session_path_for(acc_id)), API_ID, API_HASH, loop=_loop)
            await c.connect()
            await c.log_out()
    except Exception as e:
        log.warning("logout %s: %s", acc_id, e)

    f = Path(str(session_path_for(acc_id)) + ".session")
    try:
        if f.exists():
            f.unlink()
    except Exception as e:
        log.warning("remove session %s: %s", acc_id, e)

    with _acc_lock:
        data = load_accounts()
        data["accounts"] = [a for a in data["accounts"] if a["id"] != acc_id]
        if data["current"] == acc_id and data["accounts"]:
            data["current"] = data["accounts"][0]["id"]
        save_accounts(data)

    log.info("account %s removed", acc_id)
    rest = load_accounts()
    if was_current and rest["accounts"]:
        await switch_to(rest["current"])
    return {"ok": True}


# ─────────────────────────────────────────────────────────────────────────────
#  Групи та канали, у яких ви є
# ─────────────────────────────────────────────────────────────────────────────
# Сутності Telegram кешуємо, щоб слати за id без повторного пошуку.
_group_entities = {}   # str(id) -> entity


def _can_post(entity) -> bool:
    """Чи можемо ми писати в цю групу/канал."""
    # нас звідти вигнали або ми вийшли
    if getattr(entity, "left", False) or getattr(entity, "kicked", False):
        return False
    # канал-стрічка (broadcast): писати можуть лише адміни
    if getattr(entity, "broadcast", False):
        if getattr(entity, "creator", False):
            return True
        rights = getattr(entity, "admin_rights", None)
        return bool(rights and getattr(rights, "post_messages", False))
    # звичайна група: дивимось, чи не заборонено писати всім
    banned = getattr(entity, "default_banned_rights", None)
    if banned and getattr(banned, "send_messages", False):
        # адміну заборона не заважає
        if getattr(entity, "creator", False) or getattr(entity, "admin_rights", None):
            return True
        return False
    return True


async def fetch_groups() -> list:
    """Список груп і каналів користувача — для вибору в інтерфейсі."""
    out = []
    try:
        async for d in client.iter_dialogs():
            if not (d.is_group or d.is_channel):
                continue
            e = d.entity
            gid = str(d.id)
            _group_entities[gid] = e
            out.append({
                "id": gid,
                "title": d.name or "—",
                "username": ("@" + e.username) if getattr(e, "username", None) else None,
                "kind": "channel" if getattr(e, "broadcast", False) else "group",
                "can_post": _can_post(e),
            })
    except errors.FloodWaitError as e:
        log.warning("FloodWait %ss while listing dialogs", e.seconds)
        raise
    except Exception as e:
        log.exception("fetch_groups failed")
        raise
    # спершу ті, куди можна писати; далі за назвою
    out.sort(key=lambda g: (not g["can_post"], g["title"].lower()))
    log.info("fetch_groups: %d знайдено", len(out))
    return out


async def _resolve_group(gid: str):
    """Дістати сутність групи з кешу, за потреби перечитавши діалоги."""
    if gid in _group_entities:
        return _group_entities[gid]
    await fetch_groups()
    return _group_entities.get(gid)


# ─────────────────────────────────────────────────────────────────────────────
#  Логіка розсилки — корутина, що складає події у чергу для стріму в браузер
# ─────────────────────────────────────────────────────────────────────────────
async def run_campaign(text: str, usernames: list, q: Queue):
    """Шле повідомлення, кладучи події прогресу в чергу q (NDJSON)."""

    def emit(**ev):
        q.put(ev)

    try:
        vacancy = extract_vacancy(text)

        # прибираємо порожні й дублікати, зберігаючи порядок
        seen = set()
        clean = []
        for raw in usernames:
            u = norm_username(raw)
            if u and u.lower() not in seen:
                seen.add(u.lower())
                clean.append(u)

        if not text.strip():
            emit(type="error", message="Текст повідомлення порожній. Впишіть піч і спробуйте ще раз.")
            emit(type="done"); return
        if not clean:
            emit(type="error", message="Список юзернеймів порожній. Додайте хоча б один @username.")
            emit(type="done"); return

        db = load_db()
        remaining = stats(db)["remaining_today"]
        if remaining <= 0:
            emit(type="error", message="На сьогодні ліміт вичерпано. Спробуйте завтра після 00:00 CET.")
            emit(type="done"); return

        to_send = clean[:remaining]
        overflow = clean[remaining:]

        emit(type="start", total=len(to_send), vacancy=vacancy,
             overflow=len(overflow), dry=DRY)

        sent = 0
        for i, username in enumerate(to_send, start=1):
            # 1) знайти співрозмовника
            try:
                entity = await client.get_entity(username)
            except (ValueError, errors.UsernameInvalidError,
                    errors.UsernameNotOccupiedError):
                emit(type="skipped", username=username, index=i,
                     reason="не знайдено такого юзернейма")
                log.info("skip %s: not found", username)
                continue
            except errors.FloodWaitError as e:
                emit(type="stopped", username=username,
                     reason="floodwait",
                     message=f"Telegram просить зачекати {e.seconds} с перед наступними діями. "
                             f"Зупиняюсь. Спробуйте пізніше (краще через кілька годин).")
                log.warning("FloodWait %ss while resolving %s", e.seconds, username)
                break
            except Exception as e:
                emit(type="skipped", username=username, index=i,
                     reason=f"не вдалося відкрити діалог ({type(e).__name__})")
                log.info("skip %s: resolve error %s", username, e)
                continue

            # 2) надіслати
            try:
                if not DRY:
                    await client.send_message(entity, text)
                sent += 1

                # оновити базу
                with _db_lock:
                    db = load_db()
                    c = db["contacts"].get(username)
                    if c:
                        c["last_contact"] = today_str()
                        c["count"] = c.get("count", 0) + 1
                        if vacancy and not c.get("vacancy"):
                            c["vacancy"] = vacancy
                    else:
                        db["contacts"][username] = {
                            "vacancy": vacancy,
                            "first_contact": today_str(),
                            "last_contact": today_str(),
                            "count": 1,
                        }
                    d = today_str()
                    db["daily_sent"][d] = db["daily_sent"].get(d, 0) + 1
                    db["total_sent"] = db.get("total_sent", 0) + 1
                    save_db(db)

                is_last = (i == len(to_send))
                wait = 0 if is_last else random.randint(PAUSE_MIN, PAUSE_MAX)
                emit(type="sent", username=username, index=i,
                     total=len(to_send), sent=sent, wait=wait, dry=DRY)
                log.info("sent %s (%d/%d)%s", username, i, len(to_send),
                         " [DRY]" if DRY else "")

                if not is_last:
                    # у тестовому режимі коротша пауза, щоб швидше перевірити
                    real_wait = random.randint(1, 2) if DRY else wait
                    await asyncio.sleep(real_wait)

            except errors.PeerFloodError:
                emit(type="stopped", username=username, reason="peerflood",
                     message="Telegram позначив акаунт за надто активну розсилку (PeerFlood). "
                             "Негайно зупиняюсь. Зробіть паузу на 1-2 дні й не надсилайте більше. "
                             "Коли повернетесь — зменшіть обсяг і не поспішайте.")
                log.warning("PeerFloodError on %s — stopping", username)
                break
            except errors.FloodWaitError as e:
                emit(type="stopped", username=username, reason="floodwait",
                     message=f"Telegram просить зачекати {e.seconds} секунд. Зупиняюсь. "
                             f"Спробуйте пізніше, найкраще через кілька годин.")
                log.warning("FloodWaitError %ss on %s — stopping", e.seconds, username)
                break
            except (errors.UserPrivacyRestrictedError, errors.UserIsBlockedError,
                    errors.UserBlockedError) as e:
                emit(type="skipped", username=username, index=i,
                     reason="налаштування приватності не дозволяють написати")
                log.info("skip %s: privacy (%s)", username, type(e).__name__)
                continue
            except Exception as e:
                emit(type="skipped", username=username, index=i,
                     reason=f"помилка відправки ({type(e).__name__})")
                log.info("skip %s: send error %s", username, e)
                continue

        emit(type="finished", sent=sent, requested=len(to_send),
             overflow=len(overflow), dry=DRY)
    except Exception as e:
        log.exception("campaign crashed")
        emit(type="error", message=f"Несподівана помилка: {e}")
    finally:
        emit(type="done")


# ─────────────────────────────────────────────────────────────────────────────
#  Пост у групи — та сама механіка, але з окремим лімітом і довшими паузами
# ─────────────────────────────────────────────────────────────────────────────
async def run_group_campaign(text: str, group_ids: list, q: Queue):
    """Публікує текст у вибрані групи, кладучи події прогресу в чергу q."""

    def emit(**ev):
        q.put(ev)

    try:
        vacancy = extract_vacancy(text)

        # прибираємо дублікати, зберігаючи порядок
        seen = set()
        clean = []
        for gid in group_ids:
            gid = str(gid).strip()
            if gid and gid not in seen:
                seen.add(gid)
                clean.append(gid)

        if not text.strip():
            emit(type="error", message="Текст поста порожній. Впишіть оголошення і спробуйте ще раз.")
            emit(type="done"); return
        if not clean:
            emit(type="error", message="Не вибрано жодної групи. Позначте галочками, куди публікувати.")
            emit(type="done"); return

        db = load_db()
        remaining = stats(db)["group_remaining_today"]
        if remaining <= 0:
            emit(type="error", message="На сьогодні ліміт постів у групи вичерпано. "
                                       "Спробуйте завтра після 00:00 CET.")
            emit(type="done"); return

        to_post = clean[:remaining]
        overflow = clean[remaining:]

        emit(type="start", total=len(to_post), vacancy=vacancy,
             overflow=len(overflow), dry=DRY)

        posted = 0
        posted_targets = []          # для журналу постів (дашборд)
        for i, gid in enumerate(to_post, start=1):
            entity = await _resolve_group(gid)
            if entity is None:
                emit(type="skipped", name=gid, index=i,
                     reason="групу не знайдено — можливо, ви з неї вийшли")
                log.info("skip group %s: not found", gid)
                continue
            title = getattr(entity, "title", None) or gid

            # не публікуємо двічі на день в ту саму групу
            already = load_db().get("groups", {}).get(gid, {})
            if already.get("last_post") == today_str():
                emit(type="skipped", name=title, index=i,
                     reason="сюди вже публікували сьогодні")
                log.info("skip group %s: already posted today", title)
                continue

            if not _can_post(entity):
                emit(type="skipped", name=title, index=i,
                     reason="у цій групі вам не дозволено писати")
                log.info("skip group %s: no write rights", title)
                continue

            try:
                msg_id = None
                if not DRY:
                    sent_msg = await client.send_message(entity, text)
                    msg_id = getattr(sent_msg, "id", None)
                posted += 1
                posted_targets.append({
                    "gid": gid, "title": title, "msg_id": msg_id,
                    "username": getattr(entity, "username", None),
                })

                with _db_lock:
                    db = load_db()
                    g = db["groups"].get(gid)
                    if g:
                        g["title"] = title
                        g["last_post"] = today_str()
                        g["count"] = g.get("count", 0) + 1
                        if vacancy:
                            g["vacancy"] = vacancy
                    else:
                        db["groups"][gid] = {
                            "title": title,
                            "vacancy": vacancy,
                            "first_post": today_str(),
                            "last_post": today_str(),
                            "count": 1,
                        }
                    d = today_str()
                    db["group_daily_sent"][d] = db["group_daily_sent"].get(d, 0) + 1
                    db["total_group_sent"] = db.get("total_group_sent", 0) + 1
                    save_db(db)

                is_last = (i == len(to_post))
                wait = 0 if is_last else random.randint(GROUP_PAUSE_MIN, GROUP_PAUSE_MAX)
                emit(type="sent", name=title, index=i, total=len(to_post),
                     sent=posted, wait=wait, dry=DRY)
                log.info("posted to %s (%d/%d)%s", title, i, len(to_post),
                         " [DRY]" if DRY else "")

                if not is_last:
                    real_wait = random.randint(1, 2) if DRY else wait
                    await asyncio.sleep(real_wait)

            except errors.SlowModeWaitError as e:
                emit(type="skipped", name=title, index=i,
                     reason=f"у групі повільний режим, треба чекати {e.seconds} с — пропускаю")
                log.info("skip group %s: slowmode %ss", title, e.seconds)
                continue
            except (errors.ChatWriteForbiddenError, errors.ChatAdminRequiredError,
                    errors.ChatSendPlainForbiddenError, errors.UserBannedInChannelError,
                    errors.ChatRestrictedError) as e:
                emit(type="skipped", name=title, index=i,
                     reason="писати в цю групу заборонено")
                log.info("skip group %s: forbidden (%s)", title, type(e).__name__)
                continue
            except errors.ChannelPrivateError:
                emit(type="skipped", name=title, index=i,
                     reason="група закрита або вас із неї видалили")
                log.info("skip group %s: private", title)
                continue
            except errors.PeerFloodError:
                emit(type="stopped", name=title, reason="peerflood",
                     message="Telegram позначив акаунт за надто активну публікацію (PeerFlood). "
                             "Негайно зупиняюсь. Зробіть паузу на 1-2 дні. "
                             "Коли повернетесь — публікуйте рідше й у менше груп.")
                log.warning("PeerFloodError on group %s — stopping", title)
                break
            except errors.FloodWaitError as e:
                emit(type="stopped", name=title, reason="floodwait",
                     message=f"Telegram просить зачекати {e.seconds} секунд. Зупиняюсь. "
                             f"Спробуйте пізніше, найкраще через кілька годин.")
                log.warning("FloodWaitError %ss on group %s — stopping", e.seconds, title)
                break
            except Exception as e:
                emit(type="skipped", name=title, index=i,
                     reason=f"помилка публікації ({type(e).__name__})")
                log.info("skip group %s: %s", title, e)
                continue

        # записуємо пост у журнал — з нього живе дашборд
        if posted_targets and not DRY:
            with _db_lock:
                db = load_db()
                db.setdefault("posts", []).append({
                    "date": today_str(),
                    "time": now_iso(),
                    "text": text.strip()[:400],
                    "vacancy": vacancy,
                    "platform": "telegram",
                    "targets": posted_targets,
                })
                save_db(db)

        emit(type="finished", sent=posted, requested=len(to_post),
             overflow=len(overflow), dry=DRY)
    except Exception as e:
        log.exception("group campaign crashed")
        emit(type="error", message=f"Несподівана помилка: {e}")
    finally:
        emit(type="done")


# ─────────────────────────────────────────────────────────────────────────────
#  Дашборд — жива статистика опублікованих постів
# ─────────────────────────────────────────────────────────────────────────────
async def collect_stats() -> dict:
    """Читає з Telegram актуальні перегляди/реакції для кожного поста журналу."""
    db = load_db()
    posts = db.get("posts", [])
    out = []
    tot_views = tot_reactions = tot_forwards = tot_replies = 0

    for p in reversed(posts):                      # свіжі згори
        targets_out = []
        for t in p.get("targets", []):
            row = {"title": t.get("title") or "—", "views": None,
                   "forwards": None, "reactions": None, "replies": None,
                   "link": None, "gone": False}
            if t.get("username") and t.get("msg_id"):
                row["link"] = f"https://t.me/{t['username']}/{t['msg_id']}"

            ent = await _resolve_group(t["gid"]) if t.get("gid") else None
            if ent is None or not t.get("msg_id"):
                row["gone"] = ent is None
                targets_out.append(row)
                continue
            try:
                msg = await client.get_messages(ent, ids=t["msg_id"])
            except errors.FloodWaitError:
                raise
            except Exception as e:
                log.info("stats %s/%s: %s", t.get("title"), t.get("msg_id"), e)
                targets_out.append(row)
                continue

            if msg is None:
                row["gone"] = True                 # пост видалили в групі
            else:
                row["views"] = getattr(msg, "views", None)
                row["forwards"] = getattr(msg, "forwards", None)
                r = getattr(msg, "reactions", None)
                row["reactions"] = (sum(rc.count for rc in r.results)
                                    if r and getattr(r, "results", None) else 0)
                rep = getattr(msg, "replies", None)
                row["replies"] = getattr(rep, "replies", None) if rep else None
                tot_views += row["views"] or 0
                tot_reactions += row["reactions"] or 0
                tot_forwards += row["forwards"] or 0
                tot_replies += row["replies"] or 0
            targets_out.append(row)

        out.append({"date": p.get("date"), "time": p.get("time"),
                    "text": p.get("text"), "vacancy": p.get("vacancy"),
                    "platform": p.get("platform", "telegram"),
                    "targets": targets_out})

    return {"posts": out,
            "totals": {"posts": len(out), "views": tot_views,
                       "reactions": tot_reactions, "forwards": tot_forwards,
                       "replies": tot_replies}}


# ─────────────────────────────────────────────────────────────────────────────
#  Платформи (конектори) — Telegram працює, решта чекають на ключі
# ─────────────────────────────────────────────────────────────────────────────
CONNECTORS_PATH = HERE / "foxybox_connectors.json"

# майбутні платформи центру постингу; wired=False поки немає токенів
PLATFORMS = [
    {"id": "telegram",   "name": "Telegram",                    "wired": True},
    {"id": "threads",    "name": "Threads",                     "wired": False},
    {"id": "facebook",   "name": "Facebook (сторінка)",         "wired": False},
    {"id": "instagram",  "name": "Instagram (Business)",        "wired": False},
    {"id": "linkedin",   "name": "LinkedIn (особистий)",        "wired": False},
    {"id": "linkedin_co","name": "LinkedIn (сторінка компанії)","wired": False},
]


def load_connectors() -> dict:
    if CONNECTORS_PATH.exists():
        try:
            with open(CONNECTORS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error("connectors read: %s", e)
    return {}


def connectors_status() -> list:
    """Статус кожної платформи для дашборда."""
    conf = load_connectors()
    out = []
    for p in PLATFORMS:
        if p["id"] == "telegram":
            status = "connected" if _me_cache["authorized"] else "waiting"
            detail = _me_cache["username"] or ""
        else:
            status = "keys_saved" if conf.get(p["id"]) else "planned"
            detail = ""
        out.append({"id": p["id"], "name": p["name"],
                    "status": status, "detail": detail})
    return out


# ─────────────────────────────────────────────────────────────────────────────
#  HTTP-сервер
# ─────────────────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    server_version = "FoxyBox"

    def log_message(self, fmt, *args):  # тиша в консолі
        return

    # ── helpers ──
    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8",
              extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    # ── GET ──
    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            try:
                html = INDEX_PATH.read_bytes()
            except FileNotFoundError:
                html = b"index.html not found"
            self._send(200, html, "text/html; charset=utf-8")
        elif path == "/api/stats":
            db = load_db()
            s = stats(db)
            s["authorized"] = _me_cache["authorized"]
            s["me"] = _me_cache["username"] or _me_cache["name"]
            self._json(s)
        elif path == "/api/dashboard":
            if not _me_cache["authorized"]:
                self._json({"error": "Telegram не підключено."}, 400)
                return
            try:
                data = run_coro(collect_stats())
                data["connectors"] = connectors_status()
                self._json(data)
            except errors.FloodWaitError as e:
                self._json({"error": f"Telegram просить зачекати {e.seconds} с. "
                                     f"Оновіть статистику трохи пізніше."}, 429)
            except Exception as e:
                log.exception("dashboard failed")
                self._json({"error": f"Не вдалося зібрати статистику ({type(e).__name__})."}, 500)
        elif path == "/api/accounts":
            data = load_accounts()
            cur = data["current"]
            self._json({
                "current": cur,
                "accounts": [{
                    "id": a["id"],
                    "title": a.get("title") or a["id"],
                    "username": a.get("username"),
                    "active": a["id"] == cur,
                } for a in data["accounts"]],
            })
        elif path == "/api/groups":
            if not _me_cache["authorized"]:
                self._json({"error": "Telegram не підключено."}, 400)
                return
            try:
                self._json({"groups": run_coro(fetch_groups())})
            except errors.FloodWaitError as e:
                self._json({"error": f"Telegram просить зачекати {e.seconds} с. "
                                     f"Спробуйте оновити список пізніше."}, 429)
            except Exception as e:
                self._json({"error": f"Не вдалося прочитати список груп ({type(e).__name__})."}, 500)
        elif path == "/db":
            self._send(200, render_db_page().encode("utf-8"),
                       "text/html; charset=utf-8")
        elif path == "/favicon.ico":
            self._send(204, b"")
        else:
            self._json({"error": "not found"}, 404)

    # ── POST ──
    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/preview":
            data = self._read_json()
            vacancy = extract_vacancy(data.get("text", ""))
            self._json({"vacancy": vacancy})
        elif path == "/api/send":
            self._handle_send()
        elif path == "/api/send_groups":
            self._handle_send_groups()
        elif path.startswith("/api/accounts/"):
            self._handle_accounts(path[len("/api/accounts/"):])
        else:
            self._json({"error": "not found"}, 404)

    # ── акаунти ──
    def _handle_accounts(self, action):
        # не даємо чіпати акаунти посеред розсилки
        if not _campaign_lock.acquire(blocking=False):
            self._json({"error": "Спершу дочекайтесь завершення розсилки."}, 409)
            return
        try:
            data = self._read_json()
            if action == "switch":
                acc_id = str(data.get("id", ""))
                if not any(a["id"] == acc_id for a in load_accounts()["accounts"]):
                    self._json({"error": "Такого акаунта немає."}, 400); return
                self._json(run_coro(switch_to(acc_id)))

            elif action == "add/start":
                phone = str(data.get("phone", "")).strip()
                if not re.match(r"^\+?\d[\d\s\-()]{6,}$", phone):
                    self._json({"error": "Схоже, номер написаний неправильно. "
                                         "Приклад: +380671234567"}, 400); return
                self._json(run_coro(login_send_code(phone)))

            elif action == "add/code":
                code = str(data.get("code", "")).strip()
                if not code:
                    self._json({"error": "Введіть код із Telegram."}, 400); return
                self._json(run_coro(login_sign_in(code)))

            elif action == "add/password":
                pwd = str(data.get("password", ""))
                if not pwd:
                    self._json({"error": "Введіть хмарний пароль."}, 400); return
                self._json(run_coro(login_password(pwd)))

            elif action == "add/cancel":
                run_coro(login_cancel())
                self._json({"ok": True})

            elif action == "remove":
                res = run_coro(account_logout(str(data.get("id", ""))))
                self._json(res, 400 if res.get("error") else 200)

            else:
                self._json({"error": "not found"}, 404)

        except errors.PhoneNumberInvalidError:
            self._json({"error": "Telegram не приймає цей номер. Перевірте формат: +380671234567"}, 400)
        except errors.PhoneCodeInvalidError:
            self._json({"error": "Код неправильний. Перевірте й спробуйте ще раз."}, 400)
        except errors.PhoneCodeExpiredError:
            self._json({"error": "Код застарів. Почніть додавання акаунта заново."}, 400)
        except errors.PasswordHashInvalidError:
            self._json({"error": "Хмарний пароль неправильний. Спробуйте ще раз."}, 400)
        except errors.FloodWaitError as e:
            self._json({"error": f"Telegram просить зачекати {e.seconds} с перед наступною спробою."}, 429)
        except Exception as e:
            log.exception("accounts/%s failed", action)
            self._json({"error": f"Не вдалося: {type(e).__name__}"}, 500)
        finally:
            _campaign_lock.release()

    def _handle_send(self):
        data = self._read_json()
        text = data.get("text", "")
        usernames = data.get("usernames", [])
        if isinstance(usernames, str):
            usernames = usernames.splitlines()
        self._stream(lambda q: run_campaign(text, usernames, q))

    def _handle_send_groups(self):
        data = self._read_json()
        text = data.get("text", "")
        ids = data.get("group_ids", [])
        if isinstance(ids, str):
            ids = ids.splitlines()
        self._stream(lambda q: run_group_campaign(text, ids, q))

    def _stream(self, make_coro):
        """Запускає кампанію і стрімить її події в браузер як NDJSON."""
        if not _me_cache["authorized"]:
            self._json({"error": "Telegram не підключено. Запустіть авторизацію в Терміналі."}, 400)
            return
        # одночасно виконується лише одна кампанія — хоч особисті, хоч групи
        if not _campaign_lock.acquire(blocking=False):
            self._json({"error": "Розсилка вже виконується. Дочекайтесь її завершення."}, 409)
            return

        q: Queue = Queue()
        asyncio.run_coroutine_threadsafe(make_coro(q), _loop)

        # стрімимо NDJSON у браузер, рядок за рядком
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            while True:
                ev = q.get()
                line = (json.dumps(ev, ensure_ascii=False) + "\n").encode("utf-8")
                try:
                    self.wfile.write(line)
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError):
                    break
                if ev.get("type") == "done":
                    break
        finally:
            _campaign_lock.release()


# ─────────────────────────────────────────────────────────────────────────────
#  Сторінка /db — таблиця бази контактів
# ─────────────────────────────────────────────────────────────────────────────
def render_db_page() -> str:
    db = load_db()
    rows = []
    contacts = sorted(
        db["contacts"].items(),
        key=lambda kv: kv[1].get("last_contact", ""),
        reverse=True,
    )
    for username, c in contacts:
        rows.append(
            "<tr>"
            f"<td class='u'>@{_esc(username)}</td>"
            f"<td>{_esc(c.get('vacancy') or '—')}</td>"
            f"<td>{_esc(c.get('first_contact') or '—')}</td>"
            f"<td>{_esc(c.get('last_contact') or '—')}</td>"
            f"<td class='num'>{c.get('count', 0)}</td>"
            "</tr>"
        )
    body = "".join(rows) or "<tr><td colspan='5' class='empty'>Поки що порожньо. Після першої розсилки тут з'являться контакти.</td></tr>"

    grows = []
    groups = sorted(
        db.get("groups", {}).items(),
        key=lambda kv: kv[1].get("last_post", ""),
        reverse=True,
    )
    for gid, g in groups:
        grows.append(
            "<tr>"
            f"<td class='u'>{_esc(g.get('title') or gid)}</td>"
            f"<td>{_esc(g.get('vacancy') or '—')}</td>"
            f"<td>{_esc(g.get('first_post') or '—')}</td>"
            f"<td>{_esc(g.get('last_post') or '—')}</td>"
            f"<td class='num'>{g.get('count', 0)}</td>"
            "</tr>"
        )
    gbody = "".join(grows) or "<tr><td colspan='5' class='empty'>Поки що порожньо. Після першого поста тут з'являться групи.</td></tr>"

    s = stats(db)
    return f"""<!doctype html><html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>FoxyBox · База контактів</title>
<style>
  body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Nunito',sans-serif;
       background:#0a0d0c;color:#eef3f1;
       background-image:radial-gradient(1200px 600px at 50% -200px,#12211d,transparent);}}
  .wrap{{max-width:900px;margin:40px auto;padding:0 20px;}}
  a.back{{color:#3ee0c0;text-decoration:none;font-weight:700;}}
  h1{{font-weight:800;margin:18px 0 6px;}}
  .muted{{color:#9aa6a2;margin-bottom:24px;}}
  table{{width:100%;border-collapse:collapse;background:#14181a;
         border:1px solid rgba(255,255,255,.07);border-radius:18px;overflow:hidden;}}
  th,td{{text-align:left;padding:13px 16px;border-bottom:1px solid rgba(255,255,255,.06);}}
  th{{color:#9aa6a2;font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:.04em;}}
  tr:last-child td{{border-bottom:none;}}
  td.u{{color:#3ee0c0;font-weight:700;}}
  td.num{{text-align:center;font-weight:700;}}
  td.empty{{text-align:center;color:#9aa6a2;padding:40px;}}
</style></head><body><div class="wrap">
  <a class="back" href="/">&larr; На головну</a>
  <h1>База контактів</h1>
  <p class="muted">Акаунт: <b style="color:#3ee0c0">{_esc(_acc_label())}</b> · У кожного акаунта своя база<br>
     Усього контактів: {s['total_contacts']} · Усього надіслано: {s['total_sent']}</p>
  <table>
    <thead><tr><th>Кандидат</th><th>Вакансія</th><th>Перший контакт</th><th>Останній</th><th>Разів</th></tr></thead>
    <tbody>{body}</tbody>
  </table>

  <h1 style="margin-top:38px">Пости в групи</h1>
  <p class="muted">Груп у базі: {s['total_groups']} · Усього постів: {s['total_group_sent']}</p>
  <table>
    <thead><tr><th>Група</th><th>Вакансія</th><th>Перший пост</th><th>Останній</th><th>Разів</th></tr></thead>
    <tbody>{gbody}</tbody>
  </table>
</div></body></html>"""


def _acc_label() -> str:
    """Людська назва поточного акаунта — для сторінки бази."""
    data = load_accounts()
    for a in data["accounts"]:
        if a["id"] == data["current"]:
            return a.get("username") or a.get("title") or a["id"]
    return _me_cache["username"] or "—"


def _esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ─────────────────────────────────────────────────────────────────────────────
#  Запуск
# ─────────────────────────────────────────────────────────────────────────────
def start_loop_thread():
    t = threading.Thread(target=_loop.run_forever, daemon=True)
    t.start()
    return t


def main():
    if API_ID == 0 or not API_HASH:
        print("FoxyBox: спершу впишіть API_ID і API_HASH угорі файлу foxybox.py "
              "(шукайте рядки 'API_ID =' та 'API_HASH ='). "
              "Їх видають на https://my.telegram.org")
        sys.exit(0)

    if TZ is None:
        # Найчастіше це Windows без бази таймзон.
        print("FoxyBox: бракує бази часових поясів (потрібна для скидання ліміту о 00:00 CET).")
        print("Встановіть її однією командою і запустіть FoxyBox знову:")
        print("    pip install tzdata")
        sys.exit(0)

    build_client()

    # Підключення й авторизацію робимо ДО старту фонового циклу,
    # щоб інтерактивний ввід коду не конфліктував з asyncio.
    try:
        _loop.run_until_complete(client.connect())
        authorized = _loop.run_until_complete(client.is_user_authorized())
    except Exception as e:
        log.exception("connect failed")
        print(f"FoxyBox: не вдалося підключитися до Telegram: {e}")
        sys.exit(0)

    if not authorized and sys.stdin.isatty():
        print("\n=== Перший вхід у Telegram ===")
        print("Введіть номер телефону того акаунта, який використовуєте (краще запасного).")
        print("Далі прийде код у Telegram — введіть його.")
        print("Якщо на акаунті увімкнена двоетапна перевірка (хмарний пароль) —")
        print("введіть цей пароль. Якщо її нема — просто натисніть Enter. Усе одноразово.\n")
        try:
            from getpass import getpass
            # УВАГА: коли цикл asyncio ще не запущено, telethon start() виконує
            # вхід синхронно сам і повертає клієнт, тож НЕ обгортаємо в run_until_complete.
            client.start(
                phone=lambda: input("Номер телефону (формат +380...): ").strip(),
                code_callback=lambda: input("Код із Telegram: ").strip(),
                password=lambda: getpass("Хмарний пароль (двоетапна перевірка): "),
            )
        except Exception as e:
            log.exception("Auth failed")
            print(f"\nНе вдалося увійти: {e}")
            print("Спробуйте ще раз (можливо, знадобиться новий код).")
            sys.exit(0)
        print("\nГотово! Ви увійшли. Сесію збережено.\n")

        # записуємо цей вхід як головний акаунт, якщо його ще нема в списку
        data = load_accounts()
        if not any(a["id"] == MAIN_ACC for a in data["accounts"]):
            data["accounts"].insert(0, {"id": MAIN_ACC, "title": "Основний акаунт",
                                        "username": None, "phone": None})
            data["current"] = MAIN_ACC
            save_accounts(data)

    _loop.run_until_complete(_refresh_me())

    # підтягуємо юзернейм у список акаунтів, щоб у меню було видно, хто це
    if _me_cache["authorized"]:
        data = load_accounts()
        changed = False
        for a in data["accounts"]:
            if a["id"] == data["current"] and a.get("username") != _me_cache["username"]:
                a["username"] = _me_cache["username"]
                changed = True
        if changed:
            save_accounts(data)

    # тепер вмикаємо фоновий цикл asyncio для обробки запитів на розсилку
    start_loop_thread()

    # піднімаємо HTTP-сервер
    try:
        httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        # порт зайнятий — напевно FoxyBox уже працює. Чистий вихід 0.
        log.info("Port %s busy (%s). Exit 0.", PORT, e)
        print(f"FoxyBox вже працює на http://{HOST}:{PORT}")
        if sys.stdout.isatty():
            webbrowser.open(f"http://{HOST}:{PORT}")
        sys.exit(0)

    url = f"http://{HOST}:{PORT}"
    mode = "  [ТЕСТОВИЙ РЕЖИМ — нічого реально не надсилається]" if DRY else ""
    print(f"\nFoxyBox працює: {url}{mode}")
    if _me_cache["authorized"]:
        print(f"Хто увійшов: {_me_cache['username'] or _me_cache['name']}")
    else:
        print("Telegram ще не підключено — додайте акаунт кнопкою на сторінці, "
              "що зараз відкриється.")
    print("Щоб зупинити — закрийте це вікно або натисніть Ctrl+C.\n")
    log.info("Server started on %s DRY=%s me=%s", url, DRY, _me_cache["username"])

    # браузер відкриваємо лише при ручному запуску (в терміналі)
    if sys.stdout.isatty():
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nЗупинено. До зустрічі!")
        log.info("Stopped by user")


if __name__ == "__main__":
    main()
