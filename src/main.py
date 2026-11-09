import argparse
import io
import os
import subprocess
import sys
import tarfile
import urllib.request


def parse_args():
    parser = argparse.ArgumentParser(
        description="Визуализатор графа зависимостей пакетов apk"
    )
    parser.add_argument(
        "--package", required=True,
        help="Имя анализируемого пакета",
    )
    parser.add_argument(
        "--repo", required=True,
        help="URL репозитория или путь к тестовому файлу",
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Режим тестирования: --repo это путь к файлу",
    )
    parser.add_argument(
        "--ascii", action="store_true",
        help="Вывод зависимостей в виде ASCII-дерева",
    )
    parser.add_argument(
        "--filter", default="",
        help="Подстрока: пакеты с ней в имени пропускаются",
    )
    parser.add_argument(
        "--reverse", action="store_true",
        help="Показать обратные зависимости",
    )
    parser.add_argument(
        "--output", default="graph",
        help="Имя файлов для графа (без расширения)",
    )
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


def download_index(url):
    with urllib.request.urlopen(url) as response:
        data = response.read()
    archive = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
    member = archive.extractfile("APKINDEX")
    return member.read().decode("utf-8")


def parse_index(text):
    packages = {}
    for block in text.strip().split("\n\n"):
        name = None
        deps = []
        for line in block.splitlines():
            if line.startswith("P:"):
                name = line[2:]
            elif line.startswith("D:"):
                deps = line[2:].split()
        if name and name not in packages:
            packages[name] = deps
    return packages


def load_test_graph(path):
    graph = {}
    with open(path, encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or ":" not in line:
                continue
            name, rest = line.split(":", 1)
            graph[name.strip()] = rest.split()
    return graph


def clean_dep(item):
    if item.startswith("!") or ":" in item:
        return None
    for sign in ("<", ">", "=", "~"):
        item = item.split(sign)[0]
    return item


def get_direct_deps(graph, name, substring):
    result = []
    for item in graph.get(name, []):
        dep = clean_dep(item)
        if dep and (not substring or substring not in dep):
            result.append(dep)
    return result


def build_full_graph(graph, start, substring):
    """DFS без рекурсии: собирает все транзитивные связи."""
    full = {}
    stack = [start]
    while stack:
        name = stack.pop()
        if name in full:
            continue
        deps = get_direct_deps(graph, name, substring)
        full[name] = deps
        for dep in deps:
            if dep not in full:
                stack.append(dep)
    return full


def build_reverse(graph, substring):
    """Обратный граф: от пакета к тем, кто от него зависит."""
    reverse = {}
    for name in graph:
        if substring and substring in name:
            continue
        reverse.setdefault(name, [])
        for dep in get_direct_deps(graph, name, substring):
            reverse.setdefault(dep, []).append(name)
    return reverse


def print_list(full, start, reverse):
    if reverse:
        print(f"Обратные зависимости пакета {start}:")
    else:
        print(f"Все зависимости пакета {start}:")
    for name in sorted(full):
        print(name)
        for dep in full[name]:
            print(f"  -> {dep}")


def print_ascii(full, start):
    """Дерево без рекурсии. Уже раскрытые пакеты не повторяются."""
    print(start)
    expanded = set()
    stack = [(start, "", True, True)]
    while stack:
        name, prefix, is_last, is_root = stack.pop()
        if not is_root:
            connector = "└── " if is_last else "├── "
            if name in expanded:
                print(prefix + connector + name + " (уже выведен)")
                continue
            print(prefix + connector + name)
        expanded.add(name)
        if is_root:
            child_prefix = prefix
        else:
            child_prefix = prefix + ("    " if is_last else "│   ")
        children = full.get(name, [])
        for index in reversed(range(len(children))):
            is_child_last = index == len(children) - 1
            stack.append(
                (children[index], child_prefix, is_child_last, False)
            )


def to_d2(full):
    lines = [f'"{name}"' for name in sorted(full)]
    for name in sorted(full):
        for dep in full[name]:
            lines.append(f'"{name}" -> "{dep}"')
    return "\n".join(lines) + "\n"


def render_svg(d2_path, svg_path):
    try:
        subprocess.run(["d2", d2_path, svg_path], check=True)
    except FileNotFoundError:
        print("Ошибка: программа d2 не найдена", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError:
        print("Ошибка: d2 не построила изображение", file=sys.stderr)
        sys.exit(1)
    print(f"Изображение сохранено: {svg_path}")
    if os.name == "nt":
        os.startfile(svg_path)


def main():
    args = parse_args()
    error = check_args(args)
    if error:
        print(f"Ошибка: {error}", file=sys.stderr)
        sys.exit(1)

    if args.test:
        graph = load_test_graph(args.repo)
    else:
        graph = parse_index(download_index(args.repo))

    if args.package not in graph:
        print(f"Ошибка: пакет не найден: {args.package}", file=sys.stderr)
        sys.exit(1)

    source = build_reverse(graph, args.filter) if args.reverse else graph
    full = build_full_graph(source, args.package, args.filter)
    print_list(full, args.package, args.reverse)

    if args.ascii:
        print()
        print_ascii(full, args.package)

    d2_path = args.output + ".d2"
    svg_path = args.output + ".svg"
    with open(d2_path, "w", encoding="utf-8") as file:
        file.write(to_d2(full))
    render_svg(d2_path, svg_path)


if __name__ == "__main__":
    main()