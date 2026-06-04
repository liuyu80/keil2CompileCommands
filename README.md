# Keil to Compile Commands Converter

这是一个 Python/uv 工具，用于解析 Keil MDK 项目文件 (.uvprojx、.uvproj) 并生成 `compile_commands.json` 文件。这个文件可以被 Clangd 等语言服务器使用，以提供更准确的代码补全、导航和诊断功能。

## 功能

*   解析 Keil `.uvprojx` XML 文件。
*   提取项目中包含的 C/C++ 源文件 (`.c`) 和汇编文件 (`.s`)。
*   提取在 Keil 项目设置中定义的宏 (`-D` 标志)。
*   提取在 Keil 项目设置中指定的包含路径 (`-I` 标志)。
*   支持 Target 选择和 Target 列表查看。
*   合并 Target、Group、File 级别的宏、包含路径和部分编译选项。
*   支持 C、C++、汇编源文件 (`.c`, `.cc`, `.cpp`, `.cxx`, `.s`, `.S`)。
*   从 Keil CPU/FPU 配置推导常用 clang 参数，如 `-mcpu`、`-mthumb`、`-mfpu`。
*   自动处理包含路径的相对路径转换
*   统一路径分隔符为 `/` 格式
*   支持从 VSCode Clangd 设置中自动获取编译器路径
*   支持检查缺失的源文件和包含目录。
*   根据提取的信息生成 `compile_commands.json` 文件。

## 依赖

*   uv
*   Python 3.13+
*   标准库: `xml.etree.ElementTree`, `json`, `os`, `sys` (无需额外安装)
*   `json5` (由 uv 按 `pyproject.toml` 自动安装，用于读取带注释的VSCode设置文件)

## 使用方法

### 安装

通过 pip 安装 Python 包:

```bash
pip install k2c
```

安装后可以直接运行:

```bash
k2c --version
```

也可以从 GitHub Release 下载 `k2c.exe` 后直接运行。

### 本地开发运行

首次使用先同步运行环境：

```bash
uv sync
```

日常使用建议加 `--no-sync`，避免每次运行前重复检查和同步环境：

```bash
uv run --no-sync k2c <path_to_your_keil_project.uvprojx> [options]
```

**参数说明:**
- `--version`: 输出当前版本号
- `-d`: 可选参数，创建clangd缓存目录
  - 不带参数值: 默认创建`.cache`目录
  - 带参数值: 创建指定名称的目录
- `-o, --output`: 指定输出文件路径，默认 `compile_commands.json`
- `--target`: 指定要解析的 Keil Target 名称
- `--list-targets`: 列出工程中的 Target 名称后退出
- `--compiler`: 显式指定编译器路径，优先级高于 VSCode 设置
- `--dry-run`: 只解析并打印摘要，不写入文件
- `--verbose`: 打印解析摘要
- `--check-missing-files`: 检查缺失的源文件和 include 路径

**示例:**

基本用法:
```bash
uv run --no-sync k2c C:/Path/To/Your/Project/YourProject.uvprojx
```

查看 Target:
```bash
uv run --no-sync k2c ../../MyKeilProject/MyProject.uvprojx --list-targets
```

查看版本:
```bash
uv run --no-sync k2c --version
```

指定 Target 和编译器:
```bash
uv run --no-sync k2c ../../MyKeilProject/MyProject.uvprojx --target Debug --compiler C:/Keil_v5/ARM/ARMCLANG/bin/armclang.exe
```

指定输出路径:
```bash
uv run --no-sync k2c ../../MyKeilProject/MyProject.uvprojx -o build/compile_commands.json
```

检查解析结果:
```bash
uv run --no-sync k2c ../../MyKeilProject/MyProject.uvprojx --dry-run --verbose --check-missing-files
```

创建默认缓存目录:
```bash
uv run --no-sync k2c ../../MyKeilProject/MyProject.uvprojx -d
```

创建自定义缓存目录:
```bash
uv run --no-sync k2c ../../MyKeilProject/MyProject.uvprojx -d my_cache
```

当然你也可以使用打包好的exe可执行文件 [Release](https://github.com/liuyu80/keil2CompileCommands/releases/latest)

```bash
k2c ../../MyKeilProject/MyProject.uvprojx -d
```

工具默认将在当前工作目录下生成一个名为 `compile_commands.json` 的文件。

## 编译器路径设置

为了获取正确的编译器路径，脚本会按以下顺序查找：
1. 当前项目目录下的 `.vscode/settings.json`
2. 全局 VSCode 用户设置 (`AppData/Code/User/settings.json`)

如果找不到编译器路径，脚本会提醒您添加以下配置到 VSCode 设置中：
```json
"clangd.arguments": ["--query-driver=<absolute_path_to_compiler>"]
```

## `compile_commands.json`

生成的 `compile_commands.json` 文件包含一个 JSON 数组，其中每个对象代表项目中的一个源文件及其编译参数。结构如下：

```json
[
  {
    "directory": "/path/to/source/file/directory",
    "arguments": [
      "<absolute_path_to_compiler>",
      "-Iinclude/path1",
      "-Iinclude/path2",
      "-DMACRO1",
      "-DMACRO2"
    ],
    "file": "/path/to/source/file/filename.c"
  },
  ...
]
```

这个文件可以被许多开发工具（如 VS Code 配合 Clangd 插件）使用，以增强代码编辑体验。

Clangd LSP 安装包: https://github.com/clangd/clangd/releases/latest

VS Code 的 Clangd 插件: https://github.com/clangd/vscode-clangd/releases/latest

