# Визуализатор графа зависимостей (apk)

## Описание
Инструмент показывает зависимости пакетов Alpine Linux, включая транзитивные (зависимости зависимостей). Обход графа выполняется алгоритмом DFS без рекурсии. Циклические зависимости обрабатываются корректно.

Возможности:
- прямые и транзитивные зависимости пакета;
- обратные зависимости (кто зависит от пакета);
- фильтрация пакетов по подстроке;
- вывод в виде ASCII-дерева;
- построение изображения графа через D2 (файл SVG).

## Требования
- Python 3.10 или новее
- Программа `d2` для изображения (https://d2lang.com), без неё текст и дерево работают, но SVG не строится

## Запуск
    python src/main.py --package <имя> --repo <URL или путь> [--test] [--ascii] [--reverse] [--filter <подстрока>] [--output <имя>]

Или через скрипт:

    ./run.sh --package <имя> --repo <URL или путь> [--test] [--ascii] [--reverse] [--filter <подстрока>]

## Опции
- `--package` — имя анализируемого пакета
- `--repo` — URL индекса APKINDEX.tar.gz или путь к тестовому файлу
- `--test` — режим тестирования: `--repo` читается как файл графа
- `--ascii` — вывод зависимостей в виде ASCII-дерева
- `--reverse` — показать обратные зависимости (кто зависит от пакета)
- `--filter` — подстрока: пакеты, в имени которых она есть, не учитываются
- `--output` — имя файлов `.d2` и `.svg` (по умолчанию `graph`)

## Формат тестового файла
Каждая строка описывает пакет и его прямые зависимости:

    A: B C
    B: D
    C: D
    D:

## Примеры
    python src/main.py --package A --repo tests/simple.txt --test
    python src/main.py --package A --repo tests/cycle.txt --test --ascii
    python src/main.py --package A --repo tests/simple.txt --test --filter C
    python src/main.py --package D --repo tests/simple.txt --test --reverse
    python src/main.py --package curl --repo https://dl-cdn.alpinelinux.org/alpine/v3.19/main/x86_64/APKINDEX.tar.gz --ascii

## Тесты
Тестовые файлы лежат в папке `tests/`:
- `simple.txt` — граф без циклов
- `cycle.txt` — граф с циклом A → B → C → A

## Ограничения
Учитываются только прямые имена зависимостей. Записи вида `so:` и `cmd:`, а также `provides` и версии пока не обрабатываются, поэтому результат может отличаться от сайта pkgs.alpinelinux.org.