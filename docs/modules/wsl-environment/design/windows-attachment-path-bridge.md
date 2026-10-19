# Windows 原生附件与 Linux 命令路径边界

## 目标

Windows 原生 Agent 直接用文件工具读取用户提供的、已核实存在的 Windows 路径。附件、图片和截图不因宿主迁移而统一转成 WSL 路径。

## Linux 命令需要文件时

只有具体 Linux 项目命令需要访问该文件时，才使用 `scripts/resolve-wsl-path.py` 将单个已识别 Windows 路径转换为 WSL 等价路径，并检查存在性。反向交给 Windows 程序时只转换该路径值。resolver 是 Linux 开发辅助工具，不是 GUI 桥或原生文件工具的前置步骤。

## 边界

- Windows 文件工具使用已核实的 C:/、D:/ 等盘符路径；Linux-only 路径不得猜映射。
- 不扫描磁盘猜附件，不根据最近目录或错误文本推断路径，不改写整段命令、JSON、正则或环境变量。
- 缺文件或权限时报告实际缺口，不伪造内容，不通过换平台掩盖失败。
- Windows 原生文件操作可以使用 PowerShell；Git/Python/Node/测试构建仍在 WSL。
- 附件 initial banner、UI 上传及官方工具是否暴露属于上游产品状态；路径转换不能证明上传成功或消除 banner，必须另留真实操作证据。
