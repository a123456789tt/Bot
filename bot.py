import requests
from pathlib import Path

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


def download(url):
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.text


def main():
    countries = {flag: [] for flag in COUNTRIES}
    seen = set()

    for url in SOURCES:
        try:
            text = download(url)
        except Exception as e:
            print(f"Ошибка загрузки {url}: {e}")
            continue

        for line in text.splitlines():
            line = line.strip()

            if not line or line in seen:
                continue

            for flag in COUNTRIES:
                if flag in line:
                    countries[flag].append(line)
                    seen.add(line)
                    break

    output = []

    for flag, (name, limit) in COUNTRIES.items():
        items = countries[flag][:limit]

        if not items:
            continue

        output.append(f"# {flag} {name}")
        output.extend(items)
        output.append("")

    Path(OUTPUT).write_text(
        "\n".join(output),
        encoding="utf-8"
    )

    print(f"Готово: {OUTPUT}")


if __name__ == "__main__":
    main()
