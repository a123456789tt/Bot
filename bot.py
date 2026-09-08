import requests
from urllib.parse import unquote, quote, urlparse
from pathlib import Path
import socket
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------- ИСТОЧНИКИ ----------
SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/zieng2/wl/refs/heads/main/vless_universal.txt",
    # Новые рабочие источники
    "https://raw.githubusercontent.com/sakha1370/OpenRay/refs/heads/main/output/kind/vless.txt",
    "https://github.com/Mr-Meshky/vify/raw/refs/heads/main/configs/vless.txt",
]

OUTPUT = "result.txt"

COUNTRIES = {
    "🇳🇱": ("Нидерланды", 5),
    "🇫🇮": ("Финляндия", 5),
    "🇩🇪": ("Германия", 5),
    "🇷🇺": ("Россия", 10),
    "🇨🇿": ("Чехия", 5),
    "🇰🇿": ("Казахстан", 5),
    "🇺🇦": ("Украина", 5),
    "🇧🇬": ("Болгария", 5),
    "🇺🇸": ("США", 5),
    "🇨🇦": ("Канада", 5),
    "🇫🇷": ("Франция", 5),
    "🇬🇧": ("Великобритания", 5),
    "🇱🇹": ("Литва", 5),
    "🇸🇪": ("Швеция", 5),
    "🇹🇷": ("Турция", 5),
    "🇵🇱": ("Польша", 5),
}

# ---------- НАСТРОЙКИ ПИНГА ----------
PING_LIMIT_MS = 1000          # увеличено до 1000 мс (1 секунда)
TCP_TIMEOUT = 10.0            # таймаут соединения 10 секунд
MAX_WORKERS = 50              # потоков для параллельного пинга
BLACKLIST_WORDS = ["analyst"]


def download(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def decode_name(line):
    if "#" not in line:
        return ""
    name = line.split("#", 1)[1]
    for _ in range(3):
        decoded = unquote(name)
        if decoded == name:
            break
        name = decoded
    return name


def is_blacklisted(line, decoded_cache):
    if line not in decoded_cache:
        decoded_cache[line] = decode_name(line)
    decoded = decoded_cache[line]
    text_to_check = (line + " " + decoded).lower()
    return any(word in text_to_check for word in BLACKLIST_WORDS)


def find_country(line, decoded_cache):
    if line not in decoded_cache:
        decoded_cache[line] = decode_name(line)
    decoded = decoded_cache[line]
    for flag, (country, _) in COUNTRIES.items():
        if flag in decoded:
            return flag, country
    return None


def get_host_port(vless_line):
    try:
        raw = vless_line.split('#')[0].strip()
        parsed = urlparse(raw)
        if parsed.hostname and parsed.port:
            return parsed.hostname, parsed.port
        if parsed.hostname:
            return parsed.hostname, 443
    except Exception:
        pass
    return None, None


def check_ping(host, port):
    try:
        start = time.time()
        with socket.create_connection((host, port), timeout=TCP_TIMEOUT):
            elapsed = (time.time() - start) * 1000
        if elapsed <= PING_LIMIT_MS:
            return elapsed
    except Exception:
        pass
    return None


def translate_comment(line, flag, country):
    uri_part = line.split('#', 1)[0] if '#' in line else line
    new_comment = quote(flag, safe='') + '%20' + quote(country, safe='')
    return uri_part + '#' + new_comment


def ping_worker(line, flag, country, host, port):
    ping = check_ping(host, port)
    if ping is not None:
        new_line = translate_comment(line, flag, country)
        return (flag, new_line, ping)
    return None


def main():
    print("=== Запуск сборщика конфигов (порог пинга 1000 мс) ===")

    raw_candidates = {flag: [] for flag in COUNTRIES}
    seen = set()
    decoded_cache = {}
    stats = {
        "total_lines": 0,
        "blacklisted": 0,
        "no_country": 0,
        "no_host": 0,
        "duplicate": 0,
        "empty": 0,
    }

    for url in SOURCES:
        print(f"\nЗагрузка: {url}")
        try:
            text = download(url)
        except Exception as e:
            print(f"  Ошибка загрузки: {e}")
            continue

        lines = text.splitlines()
        stats["total_lines"] += len(lines)
        print(f"  Получено строк: {len(lines)}")

        for line in lines:
            line = line.strip()
            if not line:
                stats["empty"] += 1
                continue

            if line in seen:
                stats["duplicate"] += 1
                continue

            if is_blacklisted(line, decoded_cache):
                stats["blacklisted"] += 1
                continue

            result = find_country(line, decoded_cache)
            if result is None:
                stats["no_country"] += 1
                continue

            flag, country = result

            host, port = get_host_port(line)
            if not host or not port:
                stats["no_host"] += 1
                continue

            raw_candidates[flag].append((line, country, host, port))
            seen.add(line)

    # Параллельный пинг
    print("\nНачинаем параллельную проверку пинга (таймаут 10 с, лимит 1000 мс)...")
    candidates = {flag: [] for flag in COUNTRIES}
    total_to_ping = sum(len(lst) for lst in raw_candidates.values())
    pinged = 0
    stats["ping_fail"] = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = []
        for flag, items in raw_candidates.items():
            for line, country, host, port in items:
                futures.append(executor.submit(ping_worker, line, flag, country, host, port))

        for future in as_completed(futures):
            pinged += 1
            if pinged % 20 == 0:
                print(f"  Проверено пингов: {pinged}/{total_to_ping}", end='\r')
            result = future.result()
            if result is not None:
                flag, new_line, ping = result
                candidates[flag].append((new_line, ping))
            else:
                stats["ping_fail"] += 1

    print(f"  Проверено пингов: {pinged}/{total_to_ping}")

    # Формируем вывод
    output_lines = []
    total = 0

    for flag, (country, limit) in COUNTRIES.items():
        items = candidates[flag]
        if not items:
            continue

        items.sort(key=lambda x: x[1])
        selected = items[:limit]

        output_lines.append(f"# {flag} {country}")
        for line, _ in selected:
            output_lines.append(line)
        output_lines.append("")

        total += len(selected)

    if total == 0:
        output_lines = [
            "# Конфиги не найдены. Возможные причины:",
            "# - все сервера имеют пинг > 1000 мс или таймаут >10 с",
            "# - все конфиги отфильтрованы как 'analyst'",
            "# - нет подходящих строк с флагами стран",
            "# Проверьте логи выше."
        ]

    content = "\n".join(output_lines).rstrip()
    Path(OUTPUT).write_text(content, encoding="utf-8")

    print("\n=== СТАТИСТИКА ===")
    print(f"Всего строк в источниках: {stats['total_lines']}")
    print(f"Пустых строк: {stats['empty']}")
    print(f"Дубликатов: {stats['duplicate']}")
    print(f"Отфильтровано как 'analyst': {stats['blacklisted']}")
    print(f"Не удалось определить страну: {stats['no_country']}")
    print(f"Нет хоста/порта: {stats['no_host']}")
    print(f"Не прошли пинг (>{PING_LIMIT_MS} мс или таймаут >{TCP_TIMEOUT} с): {stats['ping_fail']}")

    print("\n=== РЕЗУЛЬТАТ ПО СТРАНАМ ===")
    for flag, (country, limit) in COUNTRIES.items():
        count = len(candidates[flag])
        if count:
            print(f"{flag} {country}: {count} проверено, взято {min(count, limit)} (лимит {limit})")

    print(f"\nВсего строк в результате: {total}")
    print(f"Результат записан в {OUTPUT}")
    print("=== Готово ===")


if __name__ == "__main__":
    main()
