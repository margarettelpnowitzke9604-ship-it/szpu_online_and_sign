# SZPU 校园网上网与 CC 签到工具

这个项目可以帮助你节省重复的输入账号签到和上网，一键点击即可完成。

两个互相独立、按需运行的 Windows 小工具。可在 [GitHub 仓库](https://github.com/margarettelpnowitzke9604-ship-it/szpu_online_and_sign) 点击 **Code → Download ZIP** 下载，解压后按下面步骤配置。

GitHub 下载包解压后的目录可能叫 `szpu_online_and_sign-main`，以本机实际目录为准。

工具概览：

| 工具 | 用途 | 发布形式 | 本机 Python |
| --- | --- | --- | --- |
| 上网 | 登录深职大深澜 SRUN 认证门户，检测外网连通性 | Python 源码 + BAT | 需要，仅使用标准库 |
| 签到 | 登录 CC 平台，等待签到开放、提交并查询记录 | 已打包 EXE + BAT | 不需要，EXE 内含环境 |

> **签到不需要先运行上网程序，也不要求先完成校园网外网认证。** 只要当前网络能够访问 CC 平台，就可以直接运行签到。校内平台可达和外网可达是两回事；两个启动器不会相互调用。

目标平台为 `renzheng.szpu.edu.cn` 和 `cc.szpu.edu.cn`，不是适用于所有学校的通用工具。签到目前只有既有 EXE，尚未包含 Python 源码。

## 1. 首次使用：先确认自己的运行环境

**不要照搬作者电脑的盘符、Python 路径或 Anaconda 路径。** 下载后先解压到自己可写的文件夹，不要在 ZIP 内直接运行。以下示例使用 PowerShell，示例路径均需替换。

### 确认项目实际放在哪里

```powershell
# 替换成你解压后的实际目录。
$projectRoot = 'D:\你的目录\szpu_online_and_sign'
Test-Path -LiteralPath $projectRoot
Get-ChildItem -LiteralPath $projectRoot
Set-Location -LiteralPath $projectRoot
```

`Test-Path` 应返回 `True`，目录内应有 `上网` 和 `签到` 两个文件夹。路径含空格或中文时保留引号。BAT 自动进入自身目录，移动整个项目后无需修改 BAT 中的项目路径。

### 只用签到：不必安装 Python

现有 `签到.exe` 是 **Windows x64** 程序，打包信息显示内含 **CPython 3.13**。建议在 Windows 10/11 x64 上先检查状态。本仓库不承诺 Windows 7、32 位 Windows、ARM 原生环境、macOS 或 Linux 可直接运行，也未完成所有 Windows 版本的兼容测试。

在 Windows“设置 → 系统 → 系统信息/关于”确认版本和系统类型，或执行：

```powershell
Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, OSArchitecture
```

EXE 内部环境不能通过修改系统 Python 来更换。若提示“此应用无法在你的电脑上运行”或打包运行时错误，需要匹配的系统/构建版本，或取得源码后重新打包。

### 需要上网：确认实际使用哪个 Python

逐项运行以下命令。某条命令不存在，不代表所有 Python 都不可用：

```powershell
where.exe python
where.exe py
py -0p
python -c "import sys; print(sys.executable); print(sys.version)"
py -3 -c "import sys; print(sys.executable); print(sys.version)"
```

重点确认 `sys.executable` 输出的**完整解释器路径**。`python`、`py -3`、Conda 和虚拟环境可能指向不同安装；`WindowsApps` 中的命令也可能只是应用执行别名。

- 上网源码只依赖 Python 标准库，无需安装 `requests`、Selenium 或浏览器驱动。
- 使用能运行该脚本的 Python 3。新部署可选择 Python 3.11 或更高版本，再做本机验证。
- 使用 Anaconda/Miniconda 时，在已激活的目标环境执行 `python -c ...`，取得该环境的路径。
- 没有 Python 时，从 [Python 官方网站](https://www.python.org/downloads/windows/) 安装适合本机的版本，再确认路径。仅用签到可以跳过。

**修改上网的解释器位置：** 用文本编辑器打开 `上网/上网.bat`，找到：

```bat
set "PYTHON_EXE="
```

改为刚刚确认的真实路径，例如：

```bat
set "PYTHON_EXE=D:\你的Python目录\python.exe"
```

保留 `set "变量=值"` 的外层引号，不要在值内再加引号。启动器使用 UTF-8 编码，保存时保持 UTF-8。留空时会依次尝试 `py -3`、`python`；启动器会显示本次解释器路径和版本。**多 Python/Conda 环境建议明确填写路径。** 如果显示的环境不对，关闭窗口并修改配置后再运行。

也可绕过 BAT，直接指定解释器：

```powershell
$pythonExe = 'D:\你的Python目录\python.exe'  # 替换成真实路径
& $pythonExe -c "import sys; print(sys.executable); print(sys.version)"
& $pythonExe '.\上网\上网.py' --check
```

PowerShell 执行带引号的程序路径时，需要前面的 `&`。

### 分别确认网络条件

- **上网**：接入学校对应校园网络，能访问 `https://renzheng.szpu.edu.cn`。程序还会访问外部探测站点，检查是否真正可上外网。
- **签到**：能访问 `http://cc.szpu.edu.cn` 即可。可以是可访问该平台的校内网络，或学校允许且配置正确的 VPN，以本机实际可达性为准。
- CC 无法访问时，检查校园网/VPN、DNS、代理和平台状态。**不要把“先运行上网程序”当作签到的固定前置步骤。**

## 2. 配置各自的账号

仓库只提供占位模板，不含真实账号、密码或历史日志。在项目根目录按需执行，已有账号文件不会被覆盖：

```powershell
if (-not (Test-Path -LiteralPath '.\上网\账号.txt')) {
    Copy-Item -LiteralPath '.\上网\账号.example.txt' -Destination '.\上网\账号.txt'
}
if (-not (Test-Path -LiteralPath '.\签到\账号.txt')) {
    Copy-Item -LiteralPath '.\签到\账号.example.txt' -Destination '.\签到\账号.txt'
}
```

用记事本分别编辑对应目录的 `账号.txt`，替换为本人在该系统实际使用的账号密码，UTF-8 保存：

```text
你的账号
你的密码
```

两个文件互不共享，两套系统的账号也不必相同。不要将模板 `账号.example.txt` 填成真实凭据后提交。

上网源码忽略空行和以 `#` 开头的行，并去掉行首尾空格。因此以 `#` 开头或需要保留首尾空格的密码不适合当前解析方式。签到原说明也采用前两条有效行的格式；真实文件建议只保留账号和密码两行。

账号在本机明文保存；日志可能含账号、IP 和签到信息。`.gitignore` 已忽略真实账号和日志，不要强制添加这些文件。

## 3. 独立运行签到

配置后，**直接双击 `签到/签到.bat`**，无需先上网，也无需安装 Python。根据原说明，程序会登录、等待签到开放、提交，并查询当天记录。

首次可在 PowerShell 中检查状态：

```powershell
Set-Location -LiteralPath "$projectRoot\签到"
.\签到.exe --check
```

`--check` 会真实访问平台并登录，按原说明不会提交签到，**不是离线测试**。

| 命令 | 含义 |
| --- | --- |
| `.\签到.exe` | 正常签到，默认最多等待 90 分钟 |
| `.\签到.exe --check` | 登录查看状态，不提交 |
| `.\签到.exe --dry-run` | 演练，检测按钮但不点击 |
| `.\签到.exe --wait 120` | 最多等待 120 **分钟** |
| `.\签到.exe --interval 60` | 每 60 **秒**刷新；原说明默认 30 秒 |

签到参数和流程依据随附原说明整理。目前缺少签到源码，发布准备过程中未使用真实账号登录或提交，也未验证平台是否改版。请以本机检查结果和平台实际记录为准。

## 4. 需要外网时运行上网

确认解释器和账号后，双击 `上网/上网.bat`。程序读取同目录账号，通过深澜 SRUN 接口认证，并检查外网连通性。已经可上网时直接结束；门户显示本账号在线但外网探测失败时，可能注销该会话后重新认证。

```powershell
Set-Location -LiteralPath "$projectRoot\上网"
.\上网.bat --check
.\上网.bat
.\上网.bat --wait 120 --interval 5
```

| 参数 | 含义 |
| --- | --- |
| 无参数 | 正常认证，默认不持续重试 |
| `--check` | 检查状态，不提交登录或注销；仍需账号文件 |
| `--wait 120` | 设置认证失败后重试窗口为 120 **秒** |
| `--interval 5` | 重试间隔 5 **秒**，默认 5 秒 |

**两个工具的 `--wait` 单位不同：上网是秒，签到是分钟。** 上网的网络请求和登录后验证也会耗时，`--wait` 不是精确的总运行时长上限。

两个 BAT 都转发参数并保留窗口供阅读输出。需要自动化执行或读取退出码时，可以直接调用 Python 脚本/EXE，避免 BAT 的 `pause` 等待。

## 5. 换电脑或修改配置时改哪里

| 要修改什么 | 修改位置 / 方法 |
| --- | --- |
| 项目位置 | 移动整个目录，重新设置示例中的 `$projectRoot`，保留各工具内部文件相对位置 |
| 上网 Python/Conda/venv 环境 | 修改 `上网/上网.bat` 的 `PYTHON_EXE`，或以解释器完整路径运行源码 |
| 校园网账号密码 | 本机 `上网/账号.txt` |
| CC 账号密码 | 本机 `签到/账号.txt` |
| 等待时间、刷新间隔 | 运行时传递 `--wait` / `--interval`，注意单位 |
| 上网认证门户及区域 | `上网/上网.py` 顶部 `PORTAL`、`PC_PAGE`、`ACID` 等常量；页面 URL 和区域 ID 保持一致，先确认目标门户协议 |
| 上网探测地址与超时 | `PROBE_URLS`、`PROBE_HTTPS_URL`、`PROBE_TIMEOUT`、`VERIFY_SECONDS` |
| 签到 URL、页面结构或内含运行环境 | 目前仅有 EXE，无可确认的外部配置入口，需要原源码并重新构建；不能靠改系统 Python 或 BAT 修改 |

换电脑后重新确认路径、系统架构、解释器、网络和账号，再检查状态。原电脑能运行不等于新电脑已配置完成。

## 6. 目录结构

```text
szpu_online_and_sign/
├── README.md
├── 部署说明.md
├── .gitignore
├── .gitattributes
├── 上网/
│   ├── 上网.py
│   ├── 上网.bat
│   ├── 账号.example.txt
│   └── 使用说明.txt
└── 签到/
    ├── 签到.exe
    ├── 签到.bat
    ├── 账号.example.txt
    └── 使用说明.txt
```

真实 `账号.txt` 由使用者自行创建，日志运行时生成，均不上传。

## 7. 故障排查与退出码

| 现象 | 检查方式 |
| --- | --- |
| 找不到 Python / 弹出商店 | 确认 `sys.executable`，填写 BAT 的 `PYTHON_EXE` |
| 多环境行为不同 | 对照启动器显示的路径，用同一完整路径直接运行 |
| 找不到账号 / 配置不完整 | 确认与脚本或 EXE 同目录、不是 `账号.txt.txt`、UTF-8 编码、有效行数正确 |
| 上网门户不可达 | 检查校园网接入、DNS、代理和门户状态 |
| 门户在线但外网失败 | 查看日志及探测站点可达性；正常运行可能注销再认证，`--check` 可只观察 |
| 签到网站不可达 | 检查 CC 页面、校园网/VPN 路由和平台状态；不要求先运行上网 |
| 签到未开放 | 确认对应课程、开放时间与平台页面，必要时调整等待时间 |
| EXE 启动失败 | 检查系统版本/架构与临时目录写入权限；更换系统 Python 不改变 EXE 环境 |
| Windows 提示未知发布者 | 先确认来源和本机安全检查结果，不要为运行工具全局关闭安全防护 |

上网退出码（依据源码）：`0` 外网可用；`1` 缺少账号配置；`2` 正常登录流程中门户不可达；`3` 认证失败或重试结束。`--check` 外网不可用时返回 `3`，即使原因是门户不可达。

签到退出码（依据原说明，未逐项实测）：`0` 成功/已签到；`1` 登录失败；`2` 等待超时；`3` 提交失败。

## 8. 可选：把上网脚本打包成 EXE

只针对上网源码；签到 EXE 无需再打包。使用已确认的解释器，在项目根目录运行：

```powershell
$pythonExe = 'D:\你的Python目录\python.exe'  # 替换成真实路径
& $pythonExe -m pip install pyinstaller
& $pythonExe -m PyInstaller --onefile --name 上网 '.\上网\上网.py'
```

输出位于根目录 `dist/上网.exe`。将其复制到 `上网/` 与本机 `账号.txt` 放在一起，直接运行 EXE；现有 `上网.bat` 仍调用源码。源码已处理单文件打包的路径差异，配置和日志以 EXE 所在目录为准。

产物兼容性取决于构建系统和架构，仍需在目标机验证。只打包程序，不把真实账号或日志加入发布包。

## 9. 验证范围与源码说明

- 发布准备只进行离线检查，没有执行真实校园网登录、注销或签到。
- 签到 EXE 的架构和内含 Python 版本来自静态检查；缺少源码，暂时无法从仓库复现其构建。
- 未指定开源许可证。公开仓库不等同于任意复制、修改、再分发授权；维护者可后续补充许可证。
- 使用本人账号，遵守学校网络及考勤规定，签到结果以平台记录为准。
