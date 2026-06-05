from __future__ import annotations

import json
import os
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from keil2compilecommands.k2c_utils import (
    build_compile_commands,
    check_missing_paths,
    find_system_compilers,
    get_clangd_query_driver,
    keil_cpu_arguments,
    list_target_names,
)
from keil2compilecommands.cli import main


class K2CUtilsTests(unittest.TestCase):
    def test_lists_targets(self) -> None:
        with temp_project(self.sample_project()) as project:
            self.assertEqual(list_target_names(project), ["Debug", "Release"])

    def test_builds_commands_with_cleaned_macros_paths_and_cpu_args(self) -> None:
        with temp_project(self.sample_project()) as project:
            commands = build_compile_commands(
                project,
                compiler="armclang",
                target_name="Debug",
                output_dir=project.parent,
            )

        self.assertEqual(len(commands), 4)
        first_args = commands[0]["arguments"]
        self.assertIn("-mcpu=cortex-m7", first_args)
        self.assertIn("-mthumb", first_args)
        self.assertIn("-mfpu=fpv5-d16", first_args)
        self.assertIn("-mfloat-abi=hard", first_args)
        self.assertIn("-mlittle-endian", first_args)
        self.assertIn("-Iinc", first_args)
        self.assertIn("-IDrivers/CMSIS", first_args)
        self.assertIn("-DDEBUG", first_args)
        self.assertIn("-DUSE_HAL", first_args)
        self.assertIn("-std=gnu99", first_args)
        self.assertIn("-O1", first_args)
        self.assertIn("-Wall", first_args)
        self.assertIn("-Wextra", first_args)
        self.assertIn("-fshort-enums", first_args)
        self.assertIn("-fshort-wchar", first_args)
        self.assertIn("-Wno-invalid-source-encoding", first_args)
        self.assertTrue(first_args[-1].endswith("src/main.c"))

    def test_supports_cpp_and_uppercase_assembly_sources(self) -> None:
        with temp_project(self.sample_project()) as project:
            commands = build_compile_commands(
                project,
                compiler="armclang",
                target_name="Debug",
                output_dir=project.parent,
            )

        files = {command["file"] for command in commands}
        self.assertTrue(any(file.endswith("src/main.c") for file in files))
        self.assertTrue(any(file.endswith("src/startup.S") for file in files))
        self.assertTrue(any(file.endswith("src/app.cpp") for file in files))
        self.assertTrue(any(file.endswith("src/legacy.S") for file in files))

    def test_merges_group_and_file_controls(self) -> None:
        with temp_project(self.sample_project()) as project:
            commands = build_compile_commands(
                project,
                compiler="armclang",
                target_name="Debug",
                output_dir=project.parent,
            )

        app_args = next(command["arguments"] for command in commands if command["file"].endswith("src/app.cpp"))
        self.assertIn("-Igroup_inc", app_args)
        self.assertIn("-Ifile_inc", app_args)
        self.assertIn("-DGROUP_ONLY", app_args)
        self.assertIn("-DFILE_ONLY", app_args)
        self.assertIn("-std=gnu++14", app_args)
        self.assertIn("-O0", app_args)
        self.assertIn("-fno-rtti", app_args)

    def test_selects_requested_target(self) -> None:
        with temp_project(self.sample_project()) as project:
            commands = build_compile_commands(
                project,
                compiler="armclang",
                target_name="Release",
                output_dir=project.parent,
            )

        self.assertEqual(len(commands), 1)
        self.assertTrue(commands[0]["file"].endswith("src/release.c"))
        self.assertIn("-DRELEASE", commands[0]["arguments"])

    def test_cpu_argument_mapping(self) -> None:
        args = keil_cpu_arguments('CPUTYPE("Cortex-M4") FPU2(SFPU) ELITTLE')
        self.assertEqual(args, ["-mcpu=cortex-m4", "-mthumb", "-mfpu=fpv4-sp-d16", "-mfloat-abi=hard", "-mlittle-endian"])

    def test_check_missing_paths_reports_missing_inputs(self) -> None:
        with temp_project(self.sample_project(), existing=["src/main.c", "inc"]) as project:
            report = check_missing_paths(project, target_name="Debug")

        self.assertIn("src/startup.S", report.missing_sources)
        self.assertIn("Drivers/CMSIS", report.missing_includes)

    def test_finds_system_compilers_from_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            compiler = bin_dir / "armclang.exe"
            compiler.write_text("", encoding="utf-8")
            compiler.chmod(0o755)

            candidates = find_system_compilers(
                path_value=str(bin_dir),
                pathext_value=".EXE",
            )

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].name, "armclang")
        self.assertTrue(candidates[0].path.endswith("armclang.exe"))

    def test_get_clangd_query_driver_lets_user_select_system_compiler(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bin_dir = root / "bin"
            bin_dir.mkdir()
            compiler = bin_dir / "arm-none-eabi-gcc.exe"
            compiler.write_text("", encoding="utf-8")
            compiler.chmod(0o755)

            with patch.dict(os.environ, {"PATH": str(bin_dir), "PATHEXT": ".EXE", "AppData": ""}):
                with patch("sys.stdin.isatty", return_value=True):
                    with patch("builtins.input", return_value="1"):
                        selected = get_clangd_query_driver(root)

        self.assertTrue(selected.endswith("arm-none-eabi-gcc.exe"))

    def test_cli_dry_run_and_output(self) -> None:
        with temp_project(self.sample_project()) as project:
            out = project.parent / "out" / "compile_commands.json"
            exit_code = main([
                str(project),
                "--target",
                "Debug",
                "--compiler",
                "armclang",
                "-o",
                str(out),
            ])

            self.assertEqual(exit_code, 0)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(data), 4)

    def test_cli_version(self) -> None:
        with self.assertRaises(SystemExit) as context:
            main(["--version"])

        self.assertEqual(context.exception.code, 0)

    @staticmethod
    def sample_project() -> str:
        return textwrap.dedent(
            """
            <?xml version="1.0" encoding="UTF-8" standalone="no" ?>
            <Project>
              <Targets>
                <Target>
                  <TargetName>Debug</TargetName>
                  <TargetOption>
                    <TargetCommonOption>
                      <Cpu>CPUTYPE("Cortex-M7") FPU3(DFPU) ELITTLE</Cpu>
                    </TargetCommonOption>
                    <TargetArmAds>
                      <Cads>
                        <Optim>1</Optim>
                        <v6Lang>4</v6Lang>
                        <v6LangP>5</v6LangP>
                        <vShortEn>1</vShortEn>
                        <vShortWch>1</vShortWch>
                        <v6Rtti>0</v6Rtti>
                        <wLevel>4</wLevel>
                        <VariousControls>
                          <Define> DEBUG, USE_HAL </Define>
                          <IncludePath> inc ; Drivers\\CMSIS ; </IncludePath>
                          <MiscControls>-Wno-invalid-source-encoding</MiscControls>
                        </VariousControls>
                      </Cads>
                    </TargetArmAds>
                  </TargetOption>
                  <Groups>
                    <Group>
                      <GroupName>Core</GroupName>
                      <GroupOption>
                        <Cads>
                          <VariousControls>
                            <Define>GROUP_ONLY</Define>
                            <IncludePath>group_inc</IncludePath>
                          </VariousControls>
                        </Cads>
                      </GroupOption>
                      <Files>
                        <File>
                          <FileType>1</FileType>
                          <FilePath>src\\main.c</FilePath>
                        </File>
                        <File>
                          <FileType>2</FileType>
                          <FilePath>src\\startup.S</FilePath>
                        </File>
                        <File>
                          <FileType>1</FileType>
                          <FilePath>src\\app.cpp</FilePath>
                          <FileOption>
                            <Cads>
                              <Optim>0</Optim>
                              <VariousControls>
                                <Define>FILE_ONLY</Define>
                                <IncludePath>file_inc</IncludePath>
                              </VariousControls>
                            </Cads>
                          </FileOption>
                        </File>
                        <File>
                          <FileType>2</FileType>
                          <FilePath>src\\legacy.S</FilePath>
                        </File>
                        <File>
                          <FileType>5</FileType>
                          <FilePath>readme.txt</FilePath>
                        </File>
                      </Files>
                    </Group>
                  </Groups>
                </Target>
                <Target>
                  <TargetName>Release</TargetName>
                  <TargetOption>
                    <TargetCommonOption>
                      <Cpu>CPUTYPE("Cortex-M4") ELITTLE</Cpu>
                    </TargetCommonOption>
                    <TargetArmAds>
                      <Cads>
                        <Optim>2</Optim>
                        <VariousControls>
                          <Define>RELEASE</Define>
                          <IncludePath>inc</IncludePath>
                        </VariousControls>
                      </Cads>
                    </TargetArmAds>
                  </TargetOption>
                  <Groups>
                    <Group>
                      <Files>
                        <File>
                          <FileType>1</FileType>
                          <FilePath>src\\release.c</FilePath>
                        </File>
                      </Files>
                    </Group>
                  </Groups>
                </Target>
              </Targets>
            </Project>
            """
        ).lstrip()


def temp_project(xml: str, existing: list[str] | None = None):
    class ProjectContext:
        def __enter__(self) -> Path:
            self.tmp = tempfile.TemporaryDirectory()
            root = Path(self.tmp.name)
            project = root / "Project.uvprojx"
            project.write_text(xml, encoding="utf-8")
            for item in existing or []:
                path = root / item
                if "." in path.name:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("", encoding="utf-8")
                else:
                    path.mkdir(parents=True, exist_ok=True)
            self.project = project
            return project

        def __exit__(self, exc_type, exc, tb) -> None:
            self.tmp.cleanup()

    return ProjectContext()


if __name__ == "__main__":
    unittest.main()
