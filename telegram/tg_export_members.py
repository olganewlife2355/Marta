#!/usr/bin/env python3
"""
Вивантаження учасників Telegram-групи / підписників каналу у CSV.

Запускати ЛОКАЛЬНО на своєму компʼютері (потрібен вхід у свій Telegram-акаунт).

Підготовка:
    1. Відкрий https://my.telegram.org -> API development tools -> створи app.
       Звідти візьми api_id і api_hash.
    2. pip install telethon
    3. export TG_API_ID=1234567
       export TG_API_HASH=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    4. python tg_export_members.py huntlify

Перший запуск попросить номер телефону + код з Telegram (і 2FA-пароль, якщо є).
Сесія збережеться у файл tg_export.session — далі логін не потрібен.

Опції:
    python tg_export_members.py huntlify --out members.csv
    python tg_export_members.py huntlify --from-messages 5000
        ^ якщо список учасників закритий (канал без прав адміна) — збирає
          користувачів з авторів повідомлень/коментарів за останні N повідомлень.
"""

import argparse
import asyncio
import csv
import os
import sys

try:
    from telethon import TelegramClient
    from telethon.errors import ChatAdminRequiredError
    from telethon.tl.types import Channel, Chat, User
except ImportError:
    sys.exit("Спочатку встанови залежність:  pip install telethon")


FIELDS = [
    "user_id",
    "username",
    "first_name",
    "last_name",
    "phone",
    "is_bot",
    "is_premium",
    "source",
]


def row(user: "User", source: str) -> dict:
    return {
        "user_id": user.id,
        "username": user.username or "",
        "first_name": user.first_name or "",
        "last_name": user.last_name or "",
        # Телефон видно лише якщо контакт або відкриті налаштування приватності.
        "phone": user.phone or "",
        "is_bot": bool(user.bot),
        "is_premium": bool(getattr(user, "premium", False)),
        "source": source,
    }


async def collect_participants(client, entity) -> dict:
    """Штатний спосіб: список учасників. aggressive=True обходить ліміт у 10k
    через пошук по буквах (працює для супергруп)."""
    found = {}
    async for user in client.iter_participants(entity, aggressive=True):
        if isinstance(user, User):
            found[user.id] = row(user, "participants")
            if len(found) % 200 == 0:
                print(f"  ...{len(found)}", flush=True)
    return found


async def collect_from_messages(client, entity, limit: int) -> dict:
    """Запасний спосіб: автори повідомлень і коментарів."""
    found = {}
    seen_ids = set()
    async for msg in client.iter_messages(entity, limit=limit):
        sender_id = msg.sender_id
        if sender_id is None or sender_id in seen_ids:
            continue
        seen_ids.add(sender_id)
        sender = await msg.get_sender()
        if isinstance(sender, User):
            found[sender.id] = row(sender, "messages")
    return found


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="юзернейм або посилання, напр. huntlify або https://t.me/huntlify")
    parser.add_argument("--out", default="telegram_members.csv")
    parser.add_argument(
        "--from-messages",
        type=int,
        default=0,
        metavar="N",
        help="додатково зібрати авторів останніх N повідомлень",
    )
    args = parser.parse_args()

    api_id = os.environ.get("TG_API_ID")
    api_hash = os.environ.get("TG_API_HASH")
    if not api_id or not api_hash:
        return print("Задай TG_API_ID і TG_API_HASH (з https://my.telegram.org)") or 1

    target = args.target.rstrip("/").split("/")[-1].lstrip("@")

    async with TelegramClient("tg_export", int(api_id), api_hash) as client:
        entity = await client.get_entity(target)

        if isinstance(entity, Channel):
            kind = "супергрупа" if entity.megagroup else "канал (broadcast)"
        elif isinstance(entity, Chat):
            kind = "звичайна група"
        else:
            return print(f"{target} — це не група і не канал.") or 1
        print(f"{getattr(entity, 'title', target)} — {kind}\n")

        people = {}
        try:
            print("Читаю список учасників...")
            people = await collect_participants(client, entity)
            print(f"Отримано {len(people)} учасників.")
        except ChatAdminRequiredError:
            print(
                "Telegram не віддає список: для каналу підписників бачить лише адмін.\n"
                "Спробуй --from-messages 5000, щоб зібрати активних учасників."
            )
        except ValueError as exc:
            print(f"Не вдалося прочитати учасників: {exc}")

        if args.from_messages:
            print(f"Збираю авторів останніх {args.from_messages} повідомлень...")
            extra = await collect_from_messages(client, entity, args.from_messages)
            new = {uid: r for uid, r in extra.items() if uid not in people}
            people.update(new)
            print(f"Додано ще {len(new)} унікальних людей.")

        if not people:
            print("Нічого не зібрано.")
            return 1

        with open(args.out, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(people.values())

        print(f"\nГотово: {len(people)} рядків -> {args.out}")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
