from cli import main
from k2c_utils import (
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
