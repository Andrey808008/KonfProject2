import argparse
import io
import os
import subprocess
import sys
import tarfile
import urllib.request

OPERATORS = ("<=", ">=", "<", ">", "=", "~")


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


def parse_versions(text):
    versions = {}
    for block in text.strip().split("\n\n"):
        name = None
        version = None
        for line in block.splitlines():
            if line.startswith("P:"):
                name = line[2:]
            elif line.startswith("V:"):
                version = line[2:]
        if name and version and name not in versions:
            versions[name] = version
    return versions


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


def split_dep(item):
    """Делит 'libcurl>=8.0' на имя и условие (('>=', '8.0'))."""
    if item.startswith("!") or ":" in item:
        return "", ("", "")
    for op in OPERATORS:
        if op in item:
            name, ver = item.split(op, 1)
            return name, (op, ver)
    return item, ("", "")


def get_direct_deps(graph, name, substring):
    result = []
    for item in graph.get(name, []):
        dep, cond = split_dep(item)
        if not dep or (substring and substring in dep):
            continue
        result.append((dep, cond))
    return result


def collect_conds(graph, substring):
    conds = {}
    for name in graph:
        for dep, cond in get_direct_deps(graph, name, substring):
            conds[(name, dep)] = cond
    return conds


def build_full_graph(graph, start, substring):
    """DFS без рекурсии: собирает все транзитивные связи."""
    full = {}
    stack = [start]
    while stack:
        name = stack.pop()
        if name in full:
            continue
        deps = [dep for dep, _ in get_direct_deps(graph, name, substring)]
        full[name] = deps
        for dep in deps:
            if dep not in full:
                stack.append(dep)
    return full


def build_reverse(graph, substring):
    """Обратный граф: от пакета к тем, кто от него зависит."""
    reverse = {}
    for name in graph:
        reverse.setdefault(name, [])
        for dep, _ in get_direct_deps(graph, name, substring):
            reverse.setdefault(dep, []).append(name)
    return reverse


OPERATOR_SIGNS = {
    "=": "=",
    ">": ">",
    "<": "<",
    ">=": ">=",
    "<=": "<=",
    "~": "~",
}


def edge_text(info, parent, child):
    if info["reverse"]:
        key = (child, parent)
    else:
        key = (parent, child)
    op, ver = info["conds"].get(key, ("", ""))
    if not op:
        return " (нет условия)"
    return f" {OPERATOR_SIGNS.get(op, op)} {ver}"


def node_text(name, parent, info):
    text = name
    if parent is not None:
        text += edge_text(info, parent, name)
    version = info["versions"].get(name)
    if version:
        text += f" ({version})"
    return text


def print_list(full, start, info):
    if info["reverse"]:
        print(f"Обратные зависимости пакета {start}:")
    else:
        print(f"Все зависимости пакета {start}:")
    for name in sorted(full):
        print(name)
        for dep in full[name]:
            print(f"  -> {dep}{edge_text(info, name, dep)}")


def print_ascii(full, start, info):
    """Дерево без рекурсии. Уже раскрытые пакеты не повторяются."""
    print(node_text(start, None, info))
    expanded = set()
    stack = [(start, "", True, True, None)]
    while stack:
        name, prefix, is_last, is_root, parent = stack.pop()
        if not is_root:
            connector = "└── " if is_last else "├── "
            text = node_text(name, parent, info)
            if name in expanded:
                print(prefix + connector + text + " (уже выведен)")
                continue
            print(prefix + connector + text)
        expanded.add(name)
        if is_root:
            child_prefix = prefix
        else:
            child_prefix = prefix + ("    " if is_last else "│   ")
        children = full.get(name, [])
        for index in reversed(range(len(children))):
            child = children[index]
            is_child_last = index == len(children) - 1
            stack.append((child, child_prefix, is_child_last, False, name))


def to_d2(full, info):
    lines = []
    for name in sorted(full):
        lines.append(f'"{name}": "{node_text(name, None, info)}"')
    for name in sorted(full):
        for dep in full[name]:
            label = edge_text(info, name, dep).strip()
            line = f'"{name}" -> "{dep}"'
            if label:
                line += f': "{label}"'
            lines.append(line)
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

    versions = {}
    if args.test:
        graph = load_test_graph(args.repo)
    else:
        text = download_index(args.repo)
        graph = parse_index(text)
        versions = parse_versions(text)

    if args.package not in graph:
        print(f"Ошибка: пакет не найден: {args.package}", file=sys.stderr)
        sys.exit(1)

    if not args.test:
        version = versions.get(args.package, "неизвестна")
        print(f"Версия пакета {args.package}: {version}")

    conds = collect_conds(graph, args.filter)
    info = {"versions": versions, "conds": conds, "reverse": args.reverse}
    source = build_reverse(graph, args.filter) if args.reverse else graph
    full = build_full_graph(source, args.package, args.filter)
    print_list(full, args.package, info)

    if args.ascii:
        print()
        print_ascii(full, args.package, info)

    d2_path = args.output + ".d2"
    svg_path = args.output + ".svg"
    with open(d2_path, "w", encoding="utf-8") as file:
        file.write(to_d2(full, info))
    render_svg(d2_path, svg_path)


if __name__ == "__main__":
    main()