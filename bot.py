import requests
from urllib.parse import unquote, urlparse
from pathlib import Path
import socket
import time

# Добавлены новые источники
SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/zieng2/wl/refs/heads/main/vless_universal.txt",
    "https://github.com/Mr-Meshky/vify/raw/refs/heads/main/configs/vless.txt",          # новый
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",  # новый
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

PING_LIMIT_MS = 800
TCP_TIMEOUT = 2.0


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


def find_country(line):
    decoded_name = decode_name(line)
    for flag, (country, _) in COUNTRIES.items():
        if flag in decoded_name:
            return flag, country
    return None


def get_host_port(vless_line):
    """Извлекает хост и порт из строки вида vless://uuid@host:port?params"""
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
    """Возвращает задержку в мс или None при ошибке/превышении лимита"""
    try:
        start = time.time()
        with socket.create_connection((host, port), timeout=TCP_TIMEOUT):
            elapsed = (time.time() - start) * 1000
        if elapsed <= PING_LIMIT_MS:
            return elapsed
    except Exception:
        pass
    return None


def translate_config_line(line, country):
    """
    Заменяет оригинальный комментарий (часть после #) на русское название страны.
    Если комментария нет – добавляет его в конец.
    """
    if '#' in line:
        base, _ = line.split('#', 1)
        return f"{base}#{country}"
    else:
        return f"{line}#{country}"


def main():
    candidates = {flag: [] for flag in COUNTRIES}
    seen = set()

    for url in SOURCES:
        print(f"Загрузка: {url}")
        try:
            text = download(url)
        except Exception as e:
            print(f"Ошибка загрузки: {e}")
            continue

        for line in text.splitlines():
            line = line.strip()
            if not line or line in seen:
                continue

            # --- Фильтр: пропускаем конфиги, содержащие "analyst" (регистронезависимо) ---
            if "analyst" in line.lower():
                continue

            result = find_country(line)
            if result is None:
                continue

            flag, country = result

            host, port = get_host_port(line)
            if not host or not port:
                continue

            ping = check_ping(host, port)
            if ping is None:
                continue

            # --- Перевод комментария на русский ---
            new_line = translate_config_line(line, country)

            candidates[flag].append((new_line, ping))
            seen.add(line)

    output_lines = []
    total = 0

    for flag, (country, limit) in COUNTRIES.items():
        items = candidates[flag]
        if not items:
            continue

        items.sort(key=lambda x: x[1])
        selected = items[:limit] if len(items) >= limit else items

        output_lines.append(f"# {flag} {country}")
        for line, _ in selected:
            output_lines.append(line)
        output_lines.append("")

        total += len(selected)

    Path(OUTPUT).write_text("\n".join(output_lines), encoding="utf-8")

    print()
    print("Результат:")
    for flag, (country, limit) in COUNTRIES.items():
        count = len(candidates[flag])
        if count:
            print(f"{flag} {country}: {count} проверено, выбрано {min(count, limit)} (лимит {limit})")
    print(f"Всего строк в результате: {total}")
    print(f"Готово: {OUTPUT}")


if __name__ == "__main__":
    main()
