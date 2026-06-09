from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .k2c_utils import (
    build_compile_commands,
    find_keil_project_files,
    check_missing_paths,
    create_clangd_directory,
    get_clangd_query_driver,
    list_target_names,
    write_compile_commands,
)
from .version import get_version

def _search_and_select_project() -> str:
    """Search current directory for Keil project files and let user select one."""
    cwd = Path.cwd()
    project_files = find_keil_project_files(cwd)
    if not project_files:
        sys.exit("Error: No Keil project files (.uvprojx, .uvproj) found in current directory.")
    print(f"Found {len(project_files)} Keil project file(s):")
    for i, f in enumerate(project_files, start=1):
        print(f"  {i}. {f.name}  ({f.relative_to(cwd)})")
    while True:
        try:
            answer = input("Select project number: ").strip()
        except (EOFError, KeyboardInterrupt):
            raise SystemExit(0)
        if answer.isdecimal():
            selected = int(answer)
            if 1 <= selected <= len(project_files):
                return str(project_files[selected - 1])
        print(f"Invalid selection: {answer}. Please enter a number between 1 and {len(project_files)}.")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse Keil project file and generate compile_commands.json"
    )
    parser.add_argument("--version", action="version", version=f"k2c {get_version()}")
    parser.add_argument("project_file", nargs="?", type=str, help="Path to Keil project file (.uvprojx .uvproj)")
    parser.add_argument("-d", nargs="?", const=".cache", metavar="CACHE_DIR",
                        help="Create clangd cache directory (default: .cache)")
    parser.add_argument("-o", "--output", default="compile_commands.json",
                        help="Output compile_commands.json path")
    parser.add_argument("--target", help="Keil target name to parse")
    parser.add_argument("--list-targets", action="store_true",
                        help="List target names and exit")
    parser.add_argument("--compiler", help="Compiler path used as argv[0] in compile commands")
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse and print a summary without writing output")
    parser.add_argument("--verbose", action="store_true",
                        help="Print parsing summary")
    parser.add_argument("--check-missing-files", action="store_true",
                        help="Warn about missing source and include paths")
    return parser

def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.project_file:
        args.project_file = _search_and_select_project()

    project_path = Path(args.project_file)
    if not project_path.exists():
        parser.error(f"The specified Keil project file does not exist: {args.project_file}")

    try:
        if args.list_targets:
            for target_name in list_target_names(project_path):
                print(target_name)
            return 0

        compiler = args.compiler or get_clangd_query_driver(project_path.resolve().parent)
        compile_info = build_compile_commands(
            project_path,
            compiler=compiler,
            target_name=args.target,
            output_dir=Path(args.output).resolve().parent,
            verbose=args.verbose,
        )

        if args.check_missing_files:
            report = check_missing_paths(project_path, target_name=args.target)
            if report.missing_sources:
                print(f"Missing source files: {len(report.missing_sources)}")
                for missing in report.missing_sources:
                    print(f"  {missing}")
            if report.missing_includes:
                print(f"Missing include paths: {len(report.missing_includes)}")
                for missing in report.missing_includes:
                    print(f"  {missing}")

        if args.dry_run:
            print(f"Would write {len(compile_info)} compile command entries to {args.output}")
        else:
            write_compile_commands(compile_info, args.output)

        if args.d is not None:
            create_clangd_directory(args.d)
    except Exception as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
