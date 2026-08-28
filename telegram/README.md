# Вивантаження учасників Telegram

`tg_export_members.py` — скрипт, що зберігає учасників групи (або підписників
каналу, якщо ти адмін) у CSV. Працює через Telethon від імені твого власного
Telegram-акаунта, тому запускати його треба локально.

## Як запустити

```bash
pip install telethon

# api_id / api_hash створюються на https://my.telegram.org -> API development tools
export TG_API_ID=1234567
export TG_API_HASH=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

python telegram/tg_export_members.py huntlify
```

Перший запуск попросить номер телефону, код із Telegram і 2FA-пароль (якщо
увімкнений). Сесія збережеться у файл `tg_export.session` — далі логін не
потрібен. Цей файл дає повний доступ до акаунта, тому його не можна комітити
(див. `.gitignore`).

## Опції

| Прапорець | Що робить |
| --- | --- |
| `--out FILE` | шлях до CSV (за замовчуванням `telegram_members.csv`) |
| `--from-messages N` | додатково зібрати авторів останніх N повідомлень і коментарів |

## Що реально можна вивантажити

- **Публічна супергрупа** — список учасників доступний будь-якому учаснику
  (приблизно до 10 тис. осіб; скрипт використовує `aggressive=True`, щоб обійти
  ліміт у 200).
- **Канал (broadcast)** — підписників Telegram віддає лише адміністраторам.
  Без прав адміна скрипт отримає `ChatAdminRequiredError`; тоді залишається
  `--from-messages`, який збирає тих, хто писав у коментарях.

Колонка `phone` майже завжди буде порожня — номер видно лише якщо людина є в
твоїх контактах або має відкриті налаштування приватності.

## Колонки CSV

`user_id`, `username`, `first_name`, `last_name`, `phone`, `is_bot`,
`is_premium`, `source` (`participants` або `messages`).
