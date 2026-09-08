import requests
from urllib.parse import unquote, urlparse
from pathlib import Path
import socket
import time

SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/zieng2/wl/refs/heads/main/vless_universal.txt",
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
TCP_TIMEOUT = 2.0  # секунды, чтобы не ждать слишком долго


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
        # Обрезаем возможный фрагмент после '#'
        raw = vless_line.split('#')[0].strip()
        parsed = urlparse(raw)
        if parsed.hostname and parsed.port:
            return parsed.hostname, parsed.port
        # Если порт не указан, стандартный для VLESS – 443
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
            elapsed = (time.time() - start) * 1000  # в мс
        if elapsed <= PING_LIMIT_MS:
            return elapsed
    except Exception:
        pass
    return None


def main():
    # Словарь для хранения кандидатов: flag -> list of (line, ping_ms)
    candidates = {flag: [] for flag in COUNTRIES}
    seen = set()  # для уникальности строк

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

            result = find_country(line)
            if result is None:
                continue

            flag, _ = result

            # Извлекаем хост и порт
            host, port = get_host_port(line)
            if not host or not port:
                continue

            # Проверяем пинг
            ping = check_ping(host, port)
            if ping is None:
                continue  # не прошёл по времени или недоступен

            # Сохраняем
            candidates[flag].append((line, ping))
            seen.add(line)

    # Формируем итоговый список для вывода
    output_lines = []
    total = 0

    for flag, (country, limit) in COUNTRIES.items():
        items = candidates[flag]
        if not items:
            continue

        # Сортируем по пингу (от лучшего к худшему)
        items.sort(key=lambda x: x[1])

        # Берём не больше лимита (если меньше – все)
        selected = items[:limit] if len(items) >= limit else items

        output_lines.append(f"# {flag} {country}")
        for line, _ in selected:
            output_lines.append(line)
        output_lines.append("")  # пустая строка после блока

        total += len(selected)

    # Записываем результат
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
