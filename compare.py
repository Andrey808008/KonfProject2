import json
import urllib.request

import main

PACKAGES = ["curl", "libcurl", "ca-certificates"]
INDEX = (
    "https://dl-cdn.alpinelinux.org/alpine/v3.19/main/x86_64/"
    "APKINDEX.tar.gz"
)
SITE = "https://pkgs.alpinelinux.org/package/v3.19/main/x86_64/{}"


def site_version(name):
    """Берёт версию со страницы пакета на pkgs.alpinelinux.org."""
    url = SITE.format(name)
    with urllib.request.urlopen(url) as response:
        html = response.read().decode("utf-8")
    marker = "<h1>"
    start = html.find(marker)
    if start == -1:
        return None
    end = html.find("</h1>", start)
    title = html[start + len(marker):end]
    parts = title.split()
    return parts[-1] if parts else None


def main_check():
    text = main.download_index(INDEX)
    versions = main.parse_versions(text)
    rows = ["| Пакет | Программа | Сайт | Совпадает |", "|---|---|---|---|"]
    for name in PACKAGES:
        mine = versions.get(name, "не найден")
        theirs = site_version(name) or "не найден"
        same = "да" if mine == theirs else "нет"
        rows.append(f"| {name} | {mine} | {theirs} | {same} |")
    with open("results.md", "w", encoding="utf-8") as file:
        file.write("\n".join(rows) + "\n")
    print("\n".join(rows))


if __name__ == "__main__":
    main_check()