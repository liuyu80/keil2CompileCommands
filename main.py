from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from keil2compilecommands.cli import main
from keil2compilecommands.k2c_utils import (
    build_compile_commands,
    create_clangd_directory,
    get_clangd_query_driver,
    write_compile_commands,
)


def parse_keil_project(keil_project_file_path: str):
    return build_compile_commands(
        keil_project_file_path,
        compiler=get_clangd_query_driver(),
    )


if __name__ == "__main__":
    raise SystemExit(main())
