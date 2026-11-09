import argparse
import os
import sys


def parse_args():
    parser = argparse.ArgumentParser(
        description="Визуализатор графа зависимостей пакетов apk"
    )
    parser.add_argument("--package", required=True,
                        help="Имя анализируемого пакета")
    parser.add_argument("--repo", required=True,
                        help="URL репозитория или путь к тестовому файлу")
    parser.add_argument("--test", action="store_true",
                        help="Режим тестирования: --repo это путь к файлу")
    parser.add_argument("--ascii", action="store_true",
                        help="Вывод зависимостей в виде ASCII-дерева")
    parser.add_argument("--filter", default="",
                        help="Подстрока: пакеты с ней в имени пропускаются")
    return parser.parse_args()


def check_args(args):
    if not args.package.strip():
        return "имя пакета не может быть пустым"
    if args.test:
        if not os.path.isfile(args.repo):
            return f"тестовый файл не найден: {args.repo}"
    elif not args.repo.startswith(("http://", "https://")):
        return "URL должен начинаться с http:// или https://"
    return None


def print_params(args):
    print("Параметры запуска:")
    print(f"package: {args.package}")
    print(f"repo: {args.repo}")
    print(f"test: {args.test}")
    print(f"ascii: {args.ascii}")
    print(f"filter: {args.filter}")


def main():
    args = parse_args()
    error = check_args(args)
    if error:
        print(f"Ошибка: {error}", file=sys.stderr)
        sys.exit(1)
    print_params(args)


if __name__ == "__main__":
    main()