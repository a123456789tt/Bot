import requests
from urllib.parse import unquote, quote, urlparse
from pathlib import Path
import socket
import time
import sys

# ---------- НАСТРОЙКИ ----------
SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/zieng2/wl/refs/heads/main/vless_universal.txt",
]

OUTPUT = "result.txt"

COUNTRIES = {
    "🇳🇱": ("Нидерланды", 10),
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
    "🇧🇷": ("Бразилия", 3),
    "🇦🇹": ("Австрия", 3),
    "🇪🇪": ("Эстония", 3),
    "🇩🇰": ("Дания", 3),
    "🇪🇸": ("Испания", 3),
    "🇮🇹": ("Италия", 3),
    "🇨🇭": ("Швейцария", 3),
    "🇲🇳": ("Монголия", 3),
    "🇨🇳": ("Китай", 1),
    "🇮🇳": ("Индия", 3),
}

PING_LIMIT_MS = 800
TCP_TIMEOUT = 1.5
UPDATE_INTERVAL = 3600  # 1 час

BLACKLIST_WORDS = ["analyst"]

# ---------- ФУНКЦИИ ----------
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

def find_country(line, decoded_cache):
    if line not in decoded_cache:
        decoded_cache[line] = decode_name(line)
    decoded = decoded_cache[line]
    for flag, (country, _) in COUNTRIES.items():
        if flag in decoded:
            return flag, country
    return None

def is_blacklisted(line, decoded_cache):
    if line not in decoded_cache:
        decoded_cache[line] = decode_name(line)
    decoded = decoded_cache[line]
    check_text = (line + " " + decoded).lower()
    return any(word in check_text for word in BLACKLIST_WORDS)

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

# ---------- ОБНОВЛЕНИЕ ----------
def run_update():
    print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Начинаем обновление...")

    candidates = {flag: [] for flag in COUNTRIES}
    seen = set()
    decoded_cache = {}

    for url in SOURCES:
        print(f"  Загрузка: {url}")
        try:
            text = download(url)
        except Exception as e:
            print(f"    Ошибка: {e}")
            continue

        lines = text.splitlines()
        total_lines = len(lines)
        print(f"    Всего строк в источнике: {total_lines}")

        processed = 0
        for line in lines:
            line = line.strip()
            processed += 1
            if processed % 10 == 0:
                print(f"    Обработано {processed}/{total_lines} строк...", end='\r')

            if not line or line in seen:
                continue

            if is_blacklisted(line, decoded_cache):
                continue

            result = find_country(line, decoded_cache)
            if result is None:
                continue

            flag, country = result

            host, port = get_host_port(line)
            if not host or not port:
                continue

            ping = check_ping(host, port)
            if ping is None:
                continue

            new_line = translate_comment(line, flag, country)
            candidates[flag].append((new_line, ping))
            seen.add(line)

        print(f"    Обработано {processed}/{total_lines} строк полностью.")

    # Формируем вывод – ТОЛЬКО БЛОКИ СТРАН, БЕЗ ЗАГОЛОВКОВ
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
        output_lines.append("")  # пустая строка между блоками

        total += len(selected)

    # Записываем, убирая последний лишний перевод строки, если он есть
    content = "\n".join(output_lines).rstrip()
    Path(OUTPUT).write_text(content, encoding="utf-8")

    print(f"  Готово! Сохранено {total} конфигов.")
    print("  Статистика по странам:")
    for flag, (country, limit) in COUNTRIES.items():
        count = len(candidates[flag])
        if count:
            print(f"    {flag} {country}: {count} проверено, взято {min(count, limit)} (лимит {limit})")
    print(f"  Результат записан в {OUTPUT}")

# ---------- ТОЧКА ВХОДА ----------
def main():
    print("Запущен автообновляемый сборщик конфигов")
    print(f"Интервал обновления: {UPDATE_INTERVAL // 60} минут")
    print("Нажмите Ctrl+C для остановки.\n")

    try:
        while True:
            run_update()
            print(f"Следующее обновление через {UPDATE_INTERVAL // 60} минут...")
            time.sleep(UPDATE_INTERVAL)
    except KeyboardInterrupt:
        print("\nОстановлено пользователем.")
        sys.exit(0)

if __name__ == "__main__":
    main()
