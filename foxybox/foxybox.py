#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FoxyBox — локальний інструмент рекрутера для теплої розсилки перших
повідомлень кандидатам у Telegram з особистого акаунта (MTProto, не бот).

Працює повністю на вашому комп'ютері. Нічого не надсилає на чужі сервери,
окрім самих повідомлень у Telegram через ваш акаунт.

Запуск: подвійний клік по FoxyBox.command (Mac) або FoxyBox.bat (Windows).
Вони самі готують середовище (.venv) і ставлять Telethon.

Тестовий режим (нічого реально не шле):
    FoxyBox.command --test      (Mac, у Терміналі)
    FoxyBox.bat --test          (Windows, у Командному рядку)
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

try:
    from telethon import TelegramClient, errors, utils
except ImportError:
    print("FoxyBox: не знайдено бібліотеку Telethon.")
    print("Запускайте FoxyBox подвійним кліком по FoxyBox.command (Mac) або FoxyBox.bat (Windows):")
    print("вони встановлять усе потрібне самі.")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
#  1. НАЛАШТУВАННЯ TELEGRAM
#     Редагувати файл НЕ потрібно: при першому запуску FoxyBox сам запитає
#     api_id і api_hash і збереже їх у foxybox_config.json поруч.
#     (Старий спосіб теж працює: якщо вписати значення нижче, вони мають пріоритет.)
# ─────────────────────────────────────────────────────────────────────────────
API_ID = 0
API_HASH = ""

# ─────────────────────────────────────────────────────────────────────────────
#  Загальні константи
# ─────────────────────────────────────────────────────────────────────────────
HOST = "127.0.0.1"
PORT = 8770
DAILY_LIMIT = 30               # максимум повідомлень на день
PAUSE_MIN = 18                 # мінімальна пауза між відправками, секунд
PAUSE_MAX = 24                 # максимальна пауза між відправками, секунд
GROUP_DAILY_LIMIT = 15         # максимум постів у групи на день
GROUP_PAUSE_MIN = 40           # пауза між постами в групи, секунд
GROUP_PAUSE_MAX = 70
try:
    TZ = ZoneInfo("Europe/Paris")  # ліміт скидається о 00:00 CET
except Exception:
    # На Windows часто нема системної бази таймзон — треба пакет tzdata.
    TZ = None

HERE = Path(__file__).resolve().parent
DB_PATH = HERE / "foxybox_db.json"
CONFIG_PATH = HERE / "foxybox_config.json"   # api_id / api_hash (приватне)
SESSION_PATH = HERE / "foxybox_session"      # файл сесії Telegram
LOG_PATH = HERE / "foxybox.log"
INDEX_PATH = HERE / "index.html"

DRY = (os.environ.get("FOXYBOX_DRY", "") in ("1", "true", "yes")
       or any(a in ("--test", "--dry") for a in sys.argv[1:]))

# Адреси, з яких дозволено звертатись до сервера (захист від сторонніх сайтів)
ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
ALLOWED_ORIGINS = {f"http://{h}" for h in ALLOWED_HOSTS}

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
#  База даних (JSON на диску)
# ─────────────────────────────────────────────────────────────────────────────
_db_lock = threading.Lock()


def _default_db() -> dict:
    return {"contacts": {}, "daily_sent": {}, "total_sent": 0,
            "groups": {}, "daily_groups": {}}


def load_db() -> dict:
    if DB_PATH.exists():
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # підстрахуємось на випадок неповного файлу
            base = _default_db()
            base.update(data)
            return base
        except Exception as e:
            log.error("Не вдалося прочитати базу, створюю нову: %s", e)
    return _default_db()


def save_db(db: dict) -> None:
    tmp = DB_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    tmp.replace(DB_PATH)


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


def find_contact(db: dict, username: str):
    """Шукає контакт у базі без урахування регістру. Повертає (ключ, запис)."""
    low = username.lower()
    for key, c in db["contacts"].items():
        if key.lower() == low:
            return key, c
    return None, None


_NAME_RE = re.compile(r"\{(?:name|ім['ʼ’]?я)\}", re.IGNORECASE)


def personalize(text: str, first_name: str) -> str:
    """Підставляє ім'я кандидата замість {name} / {ім'я}.
    Якщо імені нема — акуратно прибирає плейсхолдер разом із сусідньою комою."""
    if not _NAME_RE.search(text):
        return text
    first_name = (first_name or "").strip()
    if first_name:
        return _NAME_RE.sub(first_name, text)
    text = re.sub(r",[ \t]*" + _NAME_RE.pattern, "", text, flags=re.IGNORECASE)
    text = re.sub(_NAME_RE.pattern + r",?[ \t]*", "", text, flags=re.IGNORECASE)
    return text


def stats(db: dict) -> dict:
    sent_today = db["daily_sent"].get(today_str(), 0)
    groups_today = db["daily_groups"].get(today_str(), 0)
    return {
        "groups_today": groups_today,
        "groups_remaining_today": max(0, GROUP_DAILY_LIMIT - groups_today),
        "group_limit": GROUP_DAILY_LIMIT,
        "total_contacts": len(db["contacts"]),
        "total_sent": db.get("total_sent", 0),
        "sent_today": sent_today,
        "remaining_today": max(0, DAILY_LIMIT - sent_today),
        "limit": DAILY_LIMIT,
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
#  Ключі Telegram: з коду, з foxybox_config.json або запит у Терміналі
# ─────────────────────────────────────────────────────────────────────────────
_QUOTES = "\"'“”«»„‘’ \t"


def _clean_input(s: str) -> str:
    return (s or "").strip().strip(_QUOTES)


def load_credentials():
    """Повертає (api_id, api_hash) або (None, None)."""
    if API_ID and API_HASH:
        return int(API_ID), str(API_HASH).strip()
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            api_id = int(cfg.get("api_id", 0))
            api_hash = _clean_input(cfg.get("api_hash", ""))
            if api_id and re.fullmatch(r"[0-9a-f]{32}", api_hash):
                return api_id, api_hash
        except Exception as e:
            log.error("Bad config: %s", e)
    return None, None


def ask_credentials():
    """Інтерактивно питає api_id / api_hash, перевіряє формат і зберігає."""
    print("\n=== Ключі від Telegram (одноразово) ===")
    print("Відкрийте https://my.telegram.org → API development tools.")
    print("Скопіюйте звідти два значення і вставте нижче.\n")
    while True:
        raw = _clean_input(input("api_id (коротке число): "))
        if re.fullmatch(r"\d{4,12}", raw):
            api_id = int(raw)
            break
        print("  Це має бути лише число, наприклад 1234567. Спробуйте ще раз.")
    while True:
        api_hash = _clean_input(input("api_hash (довгий рядок з букв і цифр): ")).lower()
        if re.fullmatch(r"[0-9a-f]{32}", api_hash):
            break
        print("  api_hash має 32 символи (цифри та латинські a-f). Скопіюйте його повністю.")
    CONFIG_PATH.write_text(
        json.dumps({"api_id": api_id, "api_hash": api_hash}, indent=2),
        encoding="utf-8",
    )
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass
    print("Ключі збережено у foxybox_config.json (нікому його не пересилайте).\n")
    return api_id, api_hash


def forget_credentials():
    try:
        CONFIG_PATH.unlink()
    except FileNotFoundError:
        pass


def clean_phone(s: str) -> str:
    """+38 (067) 123-45-67 → +380671234567"""
    s = re.sub(r"[^\d+]", "", s or "")
    if s and not s.startswith("+"):
        s = "+" + s
    return s


# ─────────────────────────────────────────────────────────────────────────────
#  Telegram (Telethon) у власному asyncio-циклі на фоновому потоці
# ─────────────────────────────────────────────────────────────────────────────

_loop = asyncio.new_event_loop()
asyncio.set_event_loop(_loop)
client = None  # створюється в main() після перевірки ключів (build_client)

_me_cache = {"name": None, "username": None, "authorized": False}


def build_client(api_id: int, api_hash: str):
    global client
    client = TelegramClient(str(SESSION_PATH), api_id, api_hash, loop=_loop)
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


def record_sent(username: str, vacancy: str) -> None:
    """Записує успішну відправку в базу й денний лічильник."""
    with _db_lock:
        db = load_db()
        _, c = find_contact(db, username)
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


# ─────────────────────────────────────────────────────────────────────────────
#  Логіка розсилки — корутина, що складає події у чергу для стріму в браузер
# ─────────────────────────────────────────────────────────────────────────────
async def run_campaign(text: str, usernames: list, q: Queue, resend: bool = False):
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

        # кому вже писали раніше — не пишемо вдруге (якщо не просили resend)
        already = []
        if not resend:
            fresh = []
            for u in clean:
                _, c = find_contact(db, u)
                if c:
                    already.append(u)
                    log.info("skip %s: already contacted %s", u, c.get("last_contact"))
                else:
                    fresh.append(u)
            clean = fresh
            if not clean:
                emit(type="error", message=f"Усім зі списку ({len(already)}) ви вже писали раніше. "
                                           "Деталі на сторінці бази контактів.")
                emit(type="done"); return

        remaining = stats(db)["remaining_today"]
        if remaining <= 0:
            emit(type="error", message="На сьогодні ліміт вичерпано. Спробуйте завтра після 00:00 CET.")
            emit(type="done"); return

        to_send = clean[:remaining]
        overflow = clean[remaining:]

        emit(type="start", total=len(to_send), vacancy=vacancy,
             overflow=len(overflow), already=len(already),
             already_list=already, dry=DRY)

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
                msg = personalize(text, getattr(entity, "first_name", "") or "")
                if not DRY:
                    await client.send_message(entity, msg)
                sent += 1

                # у тестовому режимі базу не чіпаємо: інакше тест з'їдав би
                # ліміт і позначав кандидатів як «вже писали»
                if not DRY:
                    record_sent(username, vacancy)

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
             overflow=len(overflow), already=len(already), dry=DRY)
    except Exception as e:
        log.exception("campaign crashed")
        emit(type="error", message=f"Несподівана помилка: {e}")
    finally:
        emit(type="done")


# ─────────────────────────────────────────────────────────────────────────────
#  Режим «Групи»: пост вакансії в чати, де ви учасник
# ─────────────────────────────────────────────────────────────────────────────
_group_cache = {}   # peer_id -> entity з останнього завантаження списку груп


def _can_post(entity) -> bool:
    """Приблизна перевірка, чи можна писати в чат (без запиту до Telegram)."""
    if getattr(entity, "broadcast", False):          # канал: лише адміни
        return bool(getattr(entity, "creator", False) or getattr(entity, "admin_rights", None))
    if getattr(entity, "creator", False) or getattr(entity, "admin_rights", None):
        return True
    for attr in ("banned_rights", "default_banned_rights"):
        r = getattr(entity, attr, None)
        if r is not None and getattr(r, "send_messages", False):
            return False
    return True


async def list_groups() -> list:
    """Групи й канали акаунта, куди (ймовірно) можна писати."""
    out = []
    async for d in client.iter_dialogs():
        if not (d.is_group or d.is_channel):
            continue
        e = d.entity
        if getattr(e, "left", False) or getattr(e, "deactivated", False):
            continue
        pid = utils.get_peer_id(e)
        _group_cache[pid] = e
        out.append({
            "id": pid,
            "title": d.name or "—",
            "username": getattr(e, "username", None),
            "members": getattr(e, "participants_count", None),
            "kind": "канал" if getattr(e, "broadcast", False) else "група",
            "can_post": _can_post(e),
        })
    out.sort(key=lambda g: (not g["can_post"], g["title"].lower()))
    return out


def record_group_post(key: str, title: str, vacancy: str) -> None:
    with _db_lock:
        db = load_db()
        g = db["groups"].get(key)
        if g:
            g["title"] = title
            g["last_post"] = today_str()
            g["count"] = g.get("count", 0) + 1
            if vacancy:
                g["vacancy"] = vacancy
        else:
            db["groups"][key] = {"title": title, "vacancy": vacancy,
                                 "first_post": today_str(), "last_post": today_str(),
                                 "count": 1}
        d = today_str()
        db["daily_groups"][d] = db["daily_groups"].get(d, 0) + 1
        save_db(db)


async def _resolve_group(ref):
    """ref — id з поля вибору або @username / t.me-посилання з ручного поля."""
    if isinstance(ref, int) or (isinstance(ref, str) and re.fullmatch(r"-?\d+", ref)):
        pid = int(ref)
        if pid in _group_cache:
            return _group_cache[pid]
        return await client.get_entity(pid)
    name = norm_username(str(ref))
    if not name or name.startswith("+") or name.lower().startswith("joinchat"):
        raise ValueError("приватне посилання-запрошення: спершу вступіть у групу і оберіть її зі списку")
    return await client.get_entity(name)


async def run_group_campaign(text: str, refs: list, q: Queue, resend: bool = False):
    """Публікує текст у вибрані групи. Події ті самі, що й для особистих."""

    def emit(**ev):
        ev["mode"] = "group"
        q.put(ev)

    try:
        vacancy = extract_vacancy(text)
        msg = personalize(text, "")      # {name} у групі не має сенсу — прибираємо
        if not text.strip():
            emit(type="error", message="Текст повідомлення порожній. Впишіть піч і спробуйте ще раз.")
            return
        seen, clean = set(), []
        for r in refs:
            k = str(r).strip()
            if k and k.lower() not in seen:
                seen.add(k.lower()); clean.append(r)
        if not clean:
            emit(type="error", message="Не вибрано жодної групи. Позначте групи у списку або вставте посилання.")
            return

        db = load_db()
        remaining = stats(db)["groups_remaining_today"]
        if remaining <= 0:
            emit(type="error", message="На сьогодні ліміт постів у групи вичерпано. Спробуйте завтра після 00:00 CET.")
            return
        to_send, overflow = clean[:remaining], clean[remaining:]
        emit(type="start", total=len(to_send), vacancy=vacancy,
             overflow=len(overflow), already=0, dry=DRY)

        sent = 0
        posted_keys = set()   # одна група могла прийти і галочкою, і посиланням
        for i, ref in enumerate(to_send, start=1):
            label = str(ref)
            try:
                entity = await _resolve_group(ref)
                label = getattr(entity, "title", None) or label
                key = str(utils.get_peer_id(entity))
                g = db["groups"].get(key)
                if key in posted_keys:
                    emit(type="skipped", username=label, index=i, reason="ця група вже є у списку")
                    continue
                if g and g.get("last_post") == today_str() and not resend:
                    emit(type="skipped", username=label, index=i,
                         reason="сьогодні вже постили в цю групу")
                    continue
                if not DRY:
                    await client.send_message(entity, msg)
                    record_group_post(key, label, vacancy)
                posted_keys.add(key)
                sent += 1
                is_last = (i == len(to_send))
                wait = 0 if is_last else random.randint(GROUP_PAUSE_MIN, GROUP_PAUSE_MAX)
                emit(type="sent", username=label, index=i, total=len(to_send),
                     sent=sent, wait=wait, dry=DRY)
                log.info("group post %s (%d/%d)%s", label, i, len(to_send), " [DRY]" if DRY else "")
                if not is_last:
                    await asyncio.sleep(random.randint(1, 2) if DRY else wait)
            except errors.FloodWaitError as e:
                emit(type="stopped", username=label, reason="floodwait",
                     message=f"Telegram просить зачекати {e.seconds} с. Зупиняюсь. Спробуйте пізніше.")
                log.warning("FloodWait %ss on group %s", e.seconds, label)
                break
            except errors.PeerFloodError:
                emit(type="stopped", username=label, reason="peerflood",
                     message="Telegram позначив акаунт за надто активну розсилку (PeerFlood). "
                             "Зупиняюсь. Зробіть паузу на 1-2 дні.")
                log.warning("PeerFlood on group %s", label)
                break
            except errors.SlowModeWaitError as e:
                emit(type="skipped", username=label, index=i,
                     reason=f"у групі повільний режим, можна через {e.seconds} с")
            except (errors.ChatWriteForbiddenError, errors.ChatAdminRequiredError,
                    errors.ChatSendPlainForbiddenError, errors.UserBannedInChannelError) as e:
                emit(type="skipped", username=label, index=i,
                     reason="у цій групі вам не можна писати")
                log.info("skip group %s: %s", label, type(e).__name__)
            except (errors.ChannelPrivateError, errors.ChannelInvalidError):
                emit(type="skipped", username=label, index=i,
                     reason="група приватна або ви не є її учасником")
            except ValueError as e:
                emit(type="skipped", username=label, index=i,
                     reason=str(e) if "запрошення" in str(e) else "групу не знайдено")
            except Exception as e:
                emit(type="skipped", username=label, index=i,
                     reason=f"помилка ({type(e).__name__})")
                log.info("skip group %s: %s", label, e)

        emit(type="finished", sent=sent, requested=len(to_send),
             overflow=len(overflow), already=0, dry=DRY)
    except Exception as e:
        log.exception("group campaign crashed")
        emit(type="error", message=f"Несподівана помилка: {e}")
    finally:
        emit(type="done")


# ─────────────────────────────────────────────────────────────────────────────
#  HTTP-сервер
# ─────────────────────────────────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    server_version = "FoxyBox"

    def log_message(self, fmt, *args):  # тиша в консолі
        return

    def _request_ok(self) -> bool:
        """Пускаємо лише запити з самого FoxyBox. Без цього будь-який сайт,
        відкритий у браузері, міг би надіслати POST на 127.0.0.1 і розіслати
        повідомлення з вашого акаунта."""
        host = (self.headers.get("Host") or "").lower()
        origin = (self.headers.get("Origin") or "").rstrip("/").lower()
        if host not in ALLOWED_HOSTS:
            return False
        if origin and origin not in ALLOWED_ORIGINS:
            return False
        if self.command == "POST" and not origin:
            # сучасні браузери завжди додають Origin до POST
            return False
        return True

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
        if not self._request_ok():
            self._json({"error": "forbidden"}, 403); return
        path = self.path.split("?")[0]
        if path == "/":
            try:
                html = INDEX_PATH.read_bytes()
            except FileNotFoundError:
                html = ("<meta charset='utf-8'><p style='font-family:sans-serif'>"
                        "Не знайдено файл <b>index.html</b>. Він має лежати в одній папці "
                        "з foxybox.py.</p>").encode("utf-8")
            self._send(200, html, "text/html; charset=utf-8")
        elif path == "/api/stats":
            db = load_db()
            s = stats(db)
            s["authorized"] = _me_cache["authorized"]
            s["me"] = _me_cache["username"] or _me_cache["name"]
            self._json(s)
        elif path == "/api/groups":
            if not _me_cache["authorized"]:
                self._json({"error": "Telegram не підключено."}, 400); return
            try:
                self._json({"groups": run_coro(list_groups())})
            except Exception as e:
                log.exception("list_groups")
                self._json({"error": f"Не вдалося завантажити групи: {e}"}, 500)
        elif path == "/db":
            self._send(200, render_db_page().encode("utf-8"),
                       "text/html; charset=utf-8")
        elif path == "/favicon.ico":
            self._send(204, b"")
        else:
            self._json({"error": "not found"}, 404)

    # ── POST ──
    def do_POST(self):
        if not self._request_ok():
            self._json({"error": "forbidden"}, 403); return
        path = self.path.split("?")[0]
        if path == "/api/preview":
            data = self._read_json()
            vacancy = extract_vacancy(data.get("text", ""))
            self._json({"vacancy": vacancy})
        elif path == "/api/send":
            self._handle_send()
        else:
            self._json({"error": "not found"}, 404)

    def _handle_send(self):
        if not _me_cache["authorized"]:
            self._json({"error": "Telegram не підключено. Запустіть авторизацію в Терміналі."}, 400)
            return
        if not _campaign_lock.acquire(blocking=False):
            self._json({"error": "Розсилка вже виконується. Дочекайтесь її завершення."}, 409)
            return

        data = self._read_json()
        text = data.get("text", "")
        usernames = data.get("usernames", [])
        if isinstance(usernames, str):
            usernames = re.split(r"[\s,;]+", usernames)
        resend = bool(data.get("resend", False))

        q: Queue = Queue()
        if data.get("mode") == "group":
            refs = list(data.get("groups", []) or [])
            links = data.get("links", "")
            if isinstance(links, str):
                links = re.split(r"[\s,;]+", links)
            refs += [l for l in links if l and l.strip()]
            coro = run_group_campaign(text, refs, q, resend)
        else:
            coro = run_campaign(text, usernames, q, resend)
        asyncio.run_coroutine_threadsafe(coro, _loop)

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
    for key, g in sorted(db.get("groups", {}).items(),
                         key=lambda kv: kv[1].get("last_post", ""), reverse=True):
        grows.append(
            "<tr>"
            f"<td class='u'>{_esc(g.get('title') or key)}</td>"
            f"<td>{_esc(g.get('vacancy') or '—')}</td>"
            f"<td>{_esc(g.get('first_post') or '—')}</td>"
            f"<td>{_esc(g.get('last_post') or '—')}</td>"
            f"<td class='num'>{g.get('count', 0)}</td>"
            "</tr>"
        )
    gbody = "".join(grows) or "<tr><td colspan='5' class='empty'>Ще не було постів у групи.</td></tr>"
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
  <p class="muted">Усього контактів: {s['total_contacts']} · Усього надіслано: {s['total_sent']}</p>
  <table>
    <thead><tr><th>Кандидат</th><th>Вакансія</th><th>Перший контакт</th><th>Останній</th><th>Разів</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
  <h1 style="margin-top:40px">Пости в групах</h1>
  <table>
    <thead><tr><th>Група</th><th>Вакансія</th><th>Перший пост</th><th>Останній</th><th>Разів</th></tr></thead>
    <tbody>{gbody}</tbody>
  </table>
</div></body></html>"""


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
    if TZ is None:
        # Найчастіше це Windows без бази таймзон.
        print("FoxyBox: бракує бази часових поясів (потрібна для скидання ліміту о 00:00 CET).")
        print("Встановіть її однією командою і запустіть FoxyBox знову:")
        print("    pip install tzdata")
        sys.exit(0)

    # Порт перевіряємо ПЕРШИМ: якщо FoxyBox уже запущено, друга копія не повинна
    # чіпати файл сесії (інакше SQLite видає "database is locked").
    try:
        httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        log.info("Port %s busy (%s). Exit 0.", PORT, e)
        print(f"FoxyBox вже працює: http://{HOST}:{PORT}  (відкриваю браузер)")
        webbrowser.open(f"http://{HOST}:{PORT}")
        sys.exit(0)

    api_id, api_hash = load_credentials()
    if not api_id:
        if not sys.stdin.isatty():
            print("FoxyBox: ще немає ключів Telegram. Запустіть FoxyBox подвійним кліком, щоб їх ввести.")
            sys.exit(0)
        api_id, api_hash = ask_credentials()

    build_client(api_id, api_hash)

    # Підключення й авторизацію робимо ДО старту фонового циклу,
    # щоб інтерактивний ввід коду не конфліктував з asyncio.
    try:
        _loop.run_until_complete(client.connect())
        authorized = _loop.run_until_complete(client.is_user_authorized())
    except Exception as e:
        log.exception("connect failed")
        print(f"FoxyBox: не вдалося підключитися до Telegram: {e}")
        sys.exit(0)

    if not authorized:
        if not sys.stdin.isatty():
            log.error("Not authorized, no TTY. Exit 0.")
            print("FoxyBox: Telegram ще не підключено. Запустіть у Терміналі, щоб увійти.")
            sys.exit(0)
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
                phone=lambda: clean_phone(input("Номер телефону (формат +380...): ")),
                code_callback=lambda: input("Код із Telegram: ").strip(),
                password=lambda: getpass("Хмарний пароль (двоетапна перевірка): "),
            )
        except errors.ApiIdInvalidError:
            log.exception("Auth failed: bad api_id/api_hash")
            forget_credentials()
            print("\nTelegram не прийняв api_id / api_hash. Ключі скинуто:")
            print("запустіть FoxyBox ще раз і вставте їх уважно з my.telegram.org.")
            sys.exit(0)
        except (errors.PhoneNumberInvalidError, errors.PhoneNumberBannedError) as e:
            log.exception("Auth failed: phone")
            print(f"\nПроблема з номером телефону ({type(e).__name__}). "
                  "Перевірте номер у форматі +380... і запустіть ще раз.")
            sys.exit(0)
        except Exception as e:
            log.exception("Auth failed")
            print(f"\nНе вдалося увійти: {e}")
            print("Спробуйте ще раз (можливо, знадобиться новий код).")
            sys.exit(0)
        print("\nГотово! Ви увійшли. Сесію збережено.\n")

    _loop.run_until_complete(_refresh_me())

    # тепер вмикаємо фоновий цикл asyncio для обробки запитів на розсилку
    start_loop_thread()

    url = f"http://{HOST}:{PORT}"
    mode = "  [ТЕСТОВИЙ РЕЖИМ — нічого реально не надсилається]" if DRY else ""
    print(f"\nFoxyBox працює: {url}{mode}")
    print(f"Хто увійшов: {_me_cache['username'] or _me_cache['name']}")
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
    finally:
        httpd.server_close()
        try:
            asyncio.run_coroutine_threadsafe(client.disconnect(), _loop).result(timeout=5)
        except Exception:
            pass


if __name__ == "__main__":
    main()
