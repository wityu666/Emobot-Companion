# 使用与配置 / Usage

## 安装

Python 3.13.x。用 `python3.13 -m venv .venv` 创建环境；Windows 可使用 `py -3.13 -m venv .venv`。项目安装元数据和 CI 均限定到 3.13 系列。电脑窗口还需要可用的 Tk：python.org 的桌面 Python 通常提供；Linux 安装系统 `python3-tk`。在虚拟环境中运行 `python -m pip install -e .`。查看 `emobot doctor` 的依赖状态。macOS 录音可能需要系统麦克风授权；BLE 需要蓝牙授权。录音扩展涉及本机 PortAudio，安装方法以 PyAudio 官方说明及你的平台为准。

Windows 使用 `python -m emobot --demo gui` 或安装后的 `emobot --demo gui`；macOS/Linux 同样支持。演示模式不调用云端，也不会假称真实模型连接成功。聊天动作在无机器人连接时显示为模拟。

## API 和模型

API 输入 **base URL**，例如 `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`，应用自行追加 `/chat/completions`。选择自己的服务账号实际支持的模型名；默认模型来自旧项目兼容配置，不保证每个地区都开放。快速模型调用失败或 JSON 无效时尝试一次备用模型。文档/记忆检索命中时直接使用备用/检索模型；该模型失败时明确报错。

语音转文字使用兼容 `/audio/transcriptions` 的 multipart 接口。说话使用兼容 `/audio/speech` 的 MP3 输出。不是所有文字模型服务都实现这两个接口，需要按服务能力配置。火山配置用于 ByteDance 旧版 TTS REST 接口，支持 app ID、token、cluster、voice type；电脑录音转文字仍使用兼容 ASR 接口。机器人独立录音使用 Qwen ASR，多模态地址配置位于固件 `secrets.h`。

可配置环境变量均为 `EMOBOT_` 加 Settings 字段大写，例如：

```bash
export EMOBOT_API_KEY='your-own-key'
export EMOBOT_LANGUAGE=en
export EMOBOT_SAVE_HISTORY=false
export EMOBOT_MEMORY_ENABLED=false
emobot gui
```

不要把真实密钥写进仓库、录屏或 README。设置文件在 `EMOBOT_HOME` 指定的目录，默认 `~/.local/share/emobot-companion/settings.json`；POSIX 权限为 600，目录 700。文件不是加密保险库。Windows 的保护取决于用户目录 ACL。`.env.example` 是变量说明，程序读取进程环境变量，**不自动读取 .env 文件**。

布尔环境变量接受 `1/true/yes/on` 或 `0/false/no/off`，忽略大小写及两端空格；拼写错误会明确报错，避免无意更改记忆、历史或语音开关。配置始终按 UTF-8 保存和读取。

## 会话、记忆与文档

新会话清空本次模型上下文，既有长期记忆保持。历史默认落盘，开关 `save_history` 可以关闭落盘；当前会话仍保留最近 10 轮用于上下文。`memory_enabled` 独立控制自动写入和检索个人记忆，不妨碍文档问答。

自动记忆仅保守地接受用户明确表达的、能在当前语句中找到事实依据的长期偏好。不接受临时情绪、健康诊断或明显秘密。接受后保存用户原话，保留“不喜欢”等否定和混合偏好，不直接存储模型改写。超过 500 字的原话不自动存为记忆；可手动新增精简内容。中英文转换/复杂改写可能被过滤。旧记忆保留供你检查和编辑；手动编辑会清除旧向量，下一次索引重新生成。

删除选中的记忆会同时清除**这个用户的全部已保存聊天和动作/技能历史**，避免后续对话再次找回被删除的信息；其他记忆和导入文档保持。清除全部还会删除全部个人记忆。已导入的 Markdown 可能本身含有个人信息，需要由你管理；删除记忆不等于删除文档或数据库备份。电脑删除不控制独立机器人的 FFat 历史。

```bash
emobot import-docs README.md docs/HARDWARE.md docs/USAGE.md
emobot index
```

导入按绝对来源路径和 SHA-256 检测变化，按标题切分为最多 900 字符的片段。重新导入已变化文件会在同一事务中替换旧片段/向量。向量是可选项；配置 embedding URL/key/model/dimensions 后才能建立索引。索引每次最多 100 条，可重复执行直到 Indexed: 0。查询按余弦和关键词组合排序，无向量时使用关键词。小型作品集数据在应用进程内精确计算余弦，尚未提供大规模 ANN 索引。

## PostgreSQL

```bash
python -m pip install -e '.[postgres]'
export EMOBOT_DATABASE_URL='postgresql+psycopg://emobot:password@localhost/emobot'
emobot --demo chat hello
```

使用独立的新数据库；账号需要首次安装 vector 扩展及建表权限，或让管理员提前创建扩展。创建后的 vector 维度必须与配置一致；修改维度需要重建/迁移向量列，不能直接复用不同维度的现有表。生产远程连接请按服务商说明开启 TLS。新实现的表结构不与旧项目 Alembic 数据库直接混用，也不自动迁移旧个人数据。首次启动自动建表，SQLite 不需要 PostgreSQL。

## 设备和固件

USB 使用 **USB-UART** 接口，115200 波特率。默认音频使用 GPIO19/20，与原生 USB D-/D+ 复用，因此本版本关闭 native USB CDC。请使用开发板的 USB-UART 插口，或外置 3.3V USB-UART 转接器连接 GPIO43/44/GND。BLE 扫描显示地址，选择并连接。

全部 59 个动作在表情动作页提供，时长 50–5000ms，单序列最多 12 个且总计最多 20s。固件正播放时新序列会返回 busy；串口传输完成只代表已发送，设备 JSON `ok` 才代表接受执行，不能当成物理动作完成证明。

校准使用 `adjust_x 5` / `adjust_y -5`（累加并持久化，同时停止当前动作）；`head_move 90 90 600` 以绝对角度控制并受到中心 ±25°/±45°限制。手动移动期间新的动作序列会被拒绝。off 停止并清除移动状态，随后 on 不会恢复旧移动；关闭期间拒绝移动命令。另有 mac_address/reboot/reset_wifi。固件烧录页面必须选择匹配芯片和偏移：合并镜像为 0x0，单应用镜像为 0x10000；烧录前关闭机器人连接。建议优先 `pio run -t upload`，由平台处理分区/bootloader。
