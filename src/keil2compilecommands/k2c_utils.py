from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional
import xml.etree.ElementTree as ET


SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".s"}
COMMON_COMPILER_NAMES = (
    "armclang",
    "armcc",
    "arm-none-eabi-gcc",
    "arm-none-eabi-g++",
    "clang",
    "clang++",
    "gcc",
    "g++",
    "cl",
)


@dataclass(frozen=True)
class KeilControls:
    defines: list[str] = field(default_factory=list)
    include_paths: list[str] = field(default_factory=list)
    misc_controls: list[str] = field(default_factory=list)
    optimization: Optional[str] = None
    language: Optional[str] = None
    language_cpp: Optional[str] = None
    warning_level: Optional[str] = None
    warnings_as_errors: Optional[str] = None
    rtti: Optional[str] = None
    short_enums: Optional[str] = None
    short_wchar: Optional[str] = None


@dataclass(frozen=True)
class KeilSource:
    path: str
    controls: KeilControls = field(default_factory=KeilControls)


@dataclass(frozen=True)
class KeilTarget:
    name: str
    element: ET.Element
    controls: KeilControls
    cpu_text: str
    sources: list[KeilSource]


@dataclass(frozen=True)
class MissingPathReport:
    missing_sources: list[str]
    missing_includes: list[str]


@dataclass(frozen=True)
class CompilerCandidate:
    name: str
    path: str


def normalize_path(path: Path | str) -> str:
    return str(path).replace("\\", "/")


def relative_or_absolute(path: Path, start: Path) -> str:
    try:
        return normalize_path(os.path.relpath(path, start))
    except ValueError:
        return normalize_path(path)


def split_list(value: Optional[str], separator: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(separator) if item.strip()]


def split_shell_words(value: Optional[str]) -> list[str]:
    if not value:
        return []
    import shlex

    return shlex.split(value, posix=False)


def unique_preserving_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def parse_controls(container: Optional[ET.Element]) -> KeilControls:
    if container is None:
        return KeilControls()

    various = container.find(".//VariousControls")
    define_text = text_or_empty(various.find("Define") if various is not None else None)
    include_text = text_or_empty(various.find("IncludePath") if various is not None else None)
    misc_text = text_or_empty(various.find("MiscControls") if various is not None else None)
    optimization = text_or_empty(container.find("Optim")) or None

    return KeilControls(
        defines=split_list(define_text, ","),
        include_paths=split_list(include_text, ";"),
        misc_controls=split_shell_words(misc_text),
        optimization=optimization,
        language=_language_standard(container),
        language_cpp=_cpp_language_standard(container),
        warning_level=_field_text(container, "wLevel"),
        warnings_as_errors=_field_text(container, "v6WtE"),
        rtti=_field_text(container, "v6Rtti"),
        short_enums=_field_text(container, "vShortEn"),
        short_wchar=_field_text(container, "vShortWch"),
    )


def merge_controls(*controls: KeilControls) -> KeilControls:
    return KeilControls(
        defines=unique_preserving_order(
            item for control in controls for item in control.defines
        ),
        include_paths=unique_preserving_order(
            item for control in controls for item in control.include_paths
        ),
        misc_controls=[
            item for control in controls for item in control.misc_controls
        ],
        optimization=next(
            (control.optimization for control in reversed(controls) if control.optimization),
            None,
        ),
        language=next(
            (control.language for control in reversed(controls) if control.language),
            None,
        ),
        language_cpp=next(
            (control.language_cpp for control in reversed(controls) if control.language_cpp),
            None,
        ),
        warning_level=next(
            (control.warning_level for control in reversed(controls) if control.warning_level),
            None,
        ),
        warnings_as_errors=next(
            (control.warnings_as_errors for control in reversed(controls) if control.warnings_as_errors),
            None,
        ),
        rtti=next(
            (control.rtti for control in reversed(controls) if control.rtti),
            None,
        ),
        short_enums=next(
            (control.short_enums for control in reversed(controls) if control.short_enums),
            None,
        ),
        short_wchar=next(
            (control.short_wchar for control in reversed(controls) if control.short_wchar),
            None,
        ),
    )


def text_or_empty(element: Optional[ET.Element]) -> str:
    if element is None or element.text is None:
        return ""
    return element.text.strip()


def _field_text(container: ET.Element, name: str) -> Optional[str]:
    value = text_or_empty(container.find(name))
    if not value or value == "2":
        return None
    return value


def _language_standard(container: ET.Element) -> Optional[str]:
    v6_lang = _field_text(container, "v6Lang")
    if v6_lang:
        mapping = {
            "0": "c90",
            "1": "c99",
            "2": "c11",
            "3": "gnu90",
            "4": "gnu99",
            "5": "gnu11",
        }
        return mapping.get(v6_lang)

    if _field_text(container, "uGnu") == "1":
        return "gnu99" if _field_text(container, "uC99") == "1" else "gnu90"
    if _field_text(container, "uC99") == "1":
        return "c99"
    return None


def _cpp_language_standard(container: ET.Element) -> Optional[str]:
    v6_lang_cpp = _field_text(container, "v6LangP")
    if not v6_lang_cpp:
        return None
    mapping = {
        "0": "c++03",
        "1": "gnu++03",
        "2": "c++11",
        "3": "gnu++11",
        "4": "c++14",
        "5": "gnu++14",
        "6": "c++17",
        "7": "gnu++17",
    }
    return mapping.get(v6_lang_cpp)


def find_targets(project_file: str | Path) -> list[KeilTarget]:
    tree = ET.parse(project_file)
    root = tree.getroot()
    targets = root.findall(".//Target")
    return [_parse_target(target) for target in targets]


def list_target_names(project_file: str | Path) -> list[str]:
    return [target.name for target in find_targets(project_file)]


def _parse_target(target: ET.Element) -> KeilTarget:
    name = text_or_empty(target.find("TargetName")) or "<unnamed>"
    target_option = target.find(".//TargetOption")
    controls = parse_controls(target_option.find(".//Cads") if target_option is not None else None)
    cpu_text = text_or_empty(target_option.find(".//Cpu") if target_option is not None else None)
    sources = _parse_sources(target, controls)
    return KeilTarget(name=name, element=target, controls=controls, cpu_text=cpu_text, sources=sources)


def _parse_sources(target: ET.Element, target_controls: KeilControls) -> list[KeilSource]:
    sources: list[KeilSource] = []
    for group in target.findall(".//Group"):
        group_controls = parse_controls(group.find(".//GroupOption/Cads"))
        for file_element in group.findall("./Files/File"):
            file_type = _parse_int(text_or_empty(file_element.find("FileType")))
            file_path = text_or_empty(file_element.find("FilePath"))
            if file_type not in {1, 2} or not file_path:
                continue
            if not _is_supported_source(file_path):
                continue

            file_controls = parse_controls(file_element.find(".//FileOption/Cads"))
            controls = merge_controls(target_controls, group_controls, file_controls)
            sources.append(KeilSource(path=file_path, controls=controls))
    return sources


def _parse_int(value: str) -> Optional[int]:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _is_supported_source(path: str) -> bool:
    suffix = Path(path).suffix
    return suffix.lower() in SOURCE_SUFFIXES or suffix == ".S"


def select_target(targets: list[KeilTarget], target_name: Optional[str]) -> KeilTarget:
    if not targets:
        raise ValueError("Target element not found in Keil project file.")
    if target_name is None:
        return targets[0]

    matches = [target for target in targets if target.name == target_name]
    if not matches:
        available = ", ".join(target.name for target in targets)
        raise ValueError(f"Target '{target_name}' not found. Available targets: {available}")
    return matches[0]


def keil_cpu_arguments(cpu_text: str) -> list[str]:
    args: list[str] = []
    lowered = cpu_text.lower()

    cpu = _extract_between(cpu_text, 'CPUTYPE("', '")')
    if cpu:
        cpu_map = {
            "cortex-m0": "cortex-m0",
            "cortex-m0+": "cortex-m0plus",
            "cortex-m3": "cortex-m3",
            "cortex-m4": "cortex-m4",
            "cortex-m7": "cortex-m7",
            "cortex-m23": "cortex-m23",
            "cortex-m33": "cortex-m33",
            "cortex-m55": "cortex-m55",
        }
        mapped = cpu_map.get(cpu.lower(), cpu.lower())
        args.extend(["-mcpu=" + mapped, "-mthumb"])
    elif "cortex-m" in lowered:
        args.append("-mthumb")

    if "fpu" in lowered or "dfpu" in lowered or "spfu" in lowered:
        if "cortex-m7" in lowered:
            args.extend(["-mfpu=fpv5-d16", "-mfloat-abi=hard"])
        elif "cortex-m4" in lowered:
            args.extend(["-mfpu=fpv4-sp-d16", "-mfloat-abi=hard"])

    if "elittle" in lowered:
        args.append("-mlittle-endian")
    elif "ebig" in lowered:
        args.append("-mbig-endian")

    return unique_preserving_order(args)


def optimization_argument(optimization: Optional[str]) -> list[str]:
    if optimization is None:
        return []
    mapping = {
        "0": "-O0",
        "1": "-O1",
        "2": "-O2",
        "3": "-O3",
        "4": "-Os",
    }
    return [mapping.get(optimization, f"-O{optimization}")]


def control_arguments(controls: KeilControls, source_path: str) -> list[str]:
    args: list[str] = []
    standard = controls.language_cpp if _is_cpp_source(source_path) else controls.language
    if standard:
        args.append(f"-std={standard}")

    args.extend(optimization_argument(controls.optimization))
    args.extend(warning_arguments(controls.warning_level))

    if controls.warnings_as_errors == "1":
        args.append("-Werror")
    if controls.short_enums == "1":
        args.append("-fshort-enums")
    if controls.short_wchar == "1":
        args.append("-fshort-wchar")
    if controls.rtti == "0" and _is_cpp_source(source_path):
        args.append("-fno-rtti")
    elif controls.rtti == "1" and _is_cpp_source(source_path):
        args.append("-frtti")

    args.extend(controls.misc_controls)
    return args


def warning_arguments(warning_level: Optional[str]) -> list[str]:
    if warning_level is None:
        return []
    mapping = {
        "0": ["-w"],
        "1": ["-Wall"],
        "2": ["-Wall"],
        "3": ["-Wall", "-Wextra"],
        "4": ["-Wall", "-Wextra"],
    }
    return mapping.get(warning_level, [])


def _is_cpp_source(path: str) -> bool:
    return Path(path).suffix.lower() in {".cc", ".cpp", ".cxx"}


def _extract_between(value: str, prefix: str, suffix: str) -> Optional[str]:
    start = value.find(prefix)
    if start < 0:
        return None
    start += len(prefix)
    end = value.find(suffix, start)
    if end < 0:
        return None
    return value[start:end]


def build_compile_commands(
    project_file: str | Path,
    *,
    compiler: str,
    target_name: Optional[str] = None,
    output_dir: str | Path | None = None,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    project_path = Path(os.path.abspath(project_file))
    project_dir = project_path.parent
    output_path = Path(os.path.abspath(Path.cwd() if output_dir is None else output_dir))

    targets = find_targets(project_path)
    target = select_target(targets, target_name)
    if verbose and target_name is None and len(targets) > 1:
        print(f"Using first target '{target.name}'. Use --target to select another target.")

    base_args = keil_cpu_arguments(target.cpu_text)
    compile_commands: list[dict[str, Any]] = []
    include_cache: dict[str, str] = {}

    def include_argument(include: str) -> str:
        cached = include_cache.get(include)
        if cached is not None:
            return cached
        abs_include = Path(os.path.abspath(project_dir / include))
        cached = "-I" + relative_or_absolute(abs_include, output_path)
        include_cache[include] = cached
        return cached

    for source in target.sources:
        abs_source = Path(os.path.abspath(project_dir / source.path))
        rel_source = relative_or_absolute(abs_source, output_path)
        includes = [include_argument(include) for include in source.controls.include_paths]
        macros = [f"-D{define}" for define in source.controls.defines]
        arguments = (
            [compiler]
            + base_args
            + includes
            + macros
            + control_arguments(source.controls, source.path)
            + [rel_source]
        )
        compile_commands.append(
            {
                "arguments": arguments,
                "directory": str(output_path),
                "file": rel_source,
            }
        )

    if verbose:
        print(
            f"Parsed target '{target.name}': "
            f"{len(target.controls.include_paths)} target includes, "
            f"{len(target.controls.defines)} target macros, "
            f"{len(target.sources)} source files."
        )
    return compile_commands


def write_compile_commands(
    compile_commands: list[dict[str, Any]],
    output_file: str | Path = "compile_commands.json",
) -> None:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(compile_commands, file, indent=4, ensure_ascii=False)
    print(f"Successfully wrote compile commands to {output_path}")


def create_clangd_directory(cache_dir: Optional[str] = None) -> None:
    cache_path = Path(".cache" if cache_dir is None else cache_dir)
    cache_path.mkdir(parents=True, exist_ok=True)
    (cache_path / ".gitignore").write_text("*", encoding="utf-8")
    print(f"Successfully created {cache_path} directory and .gitignore file")


def check_missing_paths(
    project_file: str | Path,
    *,
    target_name: Optional[str] = None,
) -> MissingPathReport:
    project_path = Path(os.path.abspath(project_file))
    project_dir = project_path.parent
    target = select_target(find_targets(project_path), target_name)
    missing_sources: list[str] = []
    missing_includes: list[str] = []

    for source in target.sources:
        source_path = Path(os.path.abspath(project_dir / source.path))
        if not source_path.exists():
            missing_sources.append(normalize_path(source.path))
        for include in source.controls.include_paths:
            include_path = Path(os.path.abspath(project_dir / include))
            normalized = normalize_path(include)
            if not include_path.exists() and normalized not in missing_includes:
                missing_includes.append(normalized)

    return MissingPathReport(missing_sources=missing_sources, missing_includes=missing_includes)


def find_system_compilers(
    *,
    path_value: Optional[str] = None,
    pathext_value: Optional[str] = None,
) -> list[CompilerCandidate]:
    if path_value is None:
        path_value = os.getenv("PATH", "")
    if pathext_value is None:
        pathext_value = os.getenv("PATHEXT", ".COM;.EXE;.BAT;.CMD")

    path_extensions = [""] + [
        extension.lower()
        for extension in split_list(pathext_value, ";")
        if extension
    ]
    candidates: list[CompilerCandidate] = []
    seen_paths: set[str] = set()

    for raw_directory in split_list(path_value, os.pathsep):
        directory = Path(raw_directory.strip('"'))
        if not directory.is_dir():
            continue
        for compiler_name in COMMON_COMPILER_NAMES:
            for extension in path_extensions:
                executable = directory / f"{compiler_name}{extension}"
                if not _is_executable_file(executable):
                    continue
                normalized_path = os.path.normcase(str(executable.resolve()))
                if normalized_path in seen_paths:
                    continue
                seen_paths.add(normalized_path)
                candidates.append(
                    CompilerCandidate(
                        name=compiler_name,
                        path=normalize_path(executable),
                    )
                )

    return candidates


def choose_compiler(candidates: list[CompilerCandidate]) -> Optional[str]:
    if not candidates:
        return None

    print("Found compilers in PATH:")
    for index, candidate in enumerate(candidates, start=1):
        print(f"  {index}. {candidate.name}: {candidate.path}")

    while True:
        try:
            answer = input(
                "Select compiler number, enter compiler path manually, "
                "or press Enter to skip: "
            ).strip()
        except EOFError:
            return None

        if not answer:
            return None
        if answer.isdecimal():
            selected = int(answer)
            if 1 <= selected <= len(candidates):
                return candidates[selected - 1].path
            print(f"Invalid compiler number: {answer}")
            continue
        return answer


def _is_executable_file(path: Path) -> bool:
    if not path.is_file():
        return False
    if os.name == "nt":
        return True
    return os.access(path, os.X_OK)


def get_clangd_query_driver(project_dir: str | Path | None = None) -> str:
    def read_json_file(file_path: Path) -> dict[str, Any]:
        try:
            import json5
        except ModuleNotFoundError:
            with open(file_path, "r", encoding="utf-8") as file:
                return json.load(file)
        with open(file_path, "r", encoding="utf-8") as file:
            return json5.load(file)

    def find_compiler_in_settings(settings_path: Path) -> Optional[str]:
        if not settings_path.exists():
            return None
        data = read_json_file(settings_path)
        arguments = data.get("clangd.arguments", [])
        if not isinstance(arguments, list):
            return None
        for arg in arguments:
            if isinstance(arg, str) and arg.startswith("--query-driver="):
                compilers = split_list(arg.split("=", 1)[1], ",")
                if compilers:
                    print(f"Found compiler: {compilers}")
                    return compilers[0]
        return None

    search_dir = Path.cwd() if project_dir is None else Path(project_dir)
    compiler = find_compiler_in_settings(search_dir / ".vscode" / "settings.json")
    if compiler:
        return compiler

    app_data = os.getenv("AppData")
    if app_data:
        compiler = find_compiler_in_settings(Path(app_data) / "Code" / "User" / "settings.json")
        if compiler:
            return compiler

    if sys.stdin.isatty():
        compiler = choose_compiler(find_system_compilers())
        if compiler:
            return compiler

    print("Please add the following to your VSCode settings.json (use absolute path):")
    print('"clangd.arguments": ["--query-driver=<absolute_path_to_compiler>"]')
    return "<compilerPath>"
