"""A responsive Tk desktop; worker results cross a queue before touching any widget."""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .protocol import ACTIONS, Action
from .speech import Speech, flash_image


class Desktop:
    def __init__(self, companion, robot, demo: bool = False, config_path: Path | None = None):
        self.companion, self.robot, self.demo = companion, robot, demo
        self.config_path = config_path
        self.window = tk.Tk()
        self.window.title("Emobot Companion · DEMO" if demo else "Emobot Companion")
        self.window.geometry("1060x760")
        self.window.minsize(820, 620)
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="emobot-desktop")
        self.results = queue.Queue()
        self.busy = False
        self.closing = False
        self.status = tk.StringVar(value="Demo / 演示模式" if demo else "Ready / 就绪")
        self.book = ttk.Notebook(self.window)
        self.book.pack(fill="both", expand=True, padx=12, pady=12)
        self.pages = {}
        for name in (
            "Chat / 对话",
            "Actions / 表情动作",
            "Device / 连接校准",
            "Settings / API 设置",
            "Persona & memory / 人格记忆",
            "Firmware / 固件",
            "Help / 帮助",
        ):
            page = ttk.Frame(self.book, padding=12)
            self.book.add(page, text=name)
            self.pages[name] = page
        ttk.Label(self.window, textvariable=self.status).pack(anchor="w", padx=16, pady=5)
        self._chat_page()
        self._actions_page()
        self._device_page()
        self._settings_page()
        self._memory_page()
        self._firmware_page()
        ttk.Label(
            self.pages["Help / 帮助"],
            wraplength=880,
            justify="left",
            text="Emobot Companion\n\n1. Configure your API endpoint and models. Demo mode works without keys.\n2. Connect USB at 115200 baud or scan BLE. All robot actions also appear in the chat simulation.\n3. Long-term memory and chat history are separate switches. Forget deletes persisted personal data.\n4. Import Markdown for searchable documentation. Embeddings are optional.\n5. Flash only a matching image; disconnect the robot before flashing.\n\n请阅读仓库 docs/ 下的安装、硬件、隐私和作品集说明。语音需要安装 voice 扩展及可用音频设备。\nThis is a jointly originated, GPLv3 project. See NOTICE.md.",
        ).pack(anchor="nw")
        self.apply_theme(self.companion.settings.theme)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self._poll_handle = self.window.after(50, self._drain)

    def run(self) -> None:
        self.window.mainloop()

    def submit(self, job, callback=None) -> None:
        if self.busy or self.closing:
            self.status.set("An operation is running / 请等待当前操作")
            return
        self.busy = True
        self.status.set("Working / 处理中…")

        def work():
            try:
                self.results.put((True, job(), callback, True))
            except Exception as error:
                self.results.put((False, f"{type(error).__name__}: {error}", None, True))

        self.pool.submit(work)

    def _drain(self) -> None:
        if self.closing:
            return
        try:
            while True:
                success, result, callback, completed = self.results.get_nowait()
                if completed:
                    self.busy = False
                    self.status.set("Ready / 就绪" if success else str(result))
                if success and callback:
                    callback(result)
        except queue.Empty:
            pass
        try:
            while True:
                event = self.robot.events.get_nowait()
                self.status.set(str(event))
        except queue.Empty:
            pass
        self._poll_handle = self.window.after(50, self._drain)

    def _chat_page(self) -> None:
        page = self.pages["Chat / 对话"]
        self.transcript = tk.Text(page, wrap="word", state="disabled", height=23)
        self.transcript.pack(fill="both", expand=True)
        self.question = tk.Text(page, height=3, wrap="word")
        self.question.pack(fill="x", pady=8)
        buttons = ttk.Frame(page)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Send / 发送", command=self.send).pack(side="left")
        ttk.Button(buttons, text="Microphone / 录音", command=self.listen).pack(side="left", padx=8)
        ttk.Button(
            buttons, text="New session / 新会话", command=lambda: self.submit(self.companion.new_session)
        ).pack(side="left")
        self.question.bind("<Control-Return>", lambda _event: self.send())

    def append(self, who: str, content: str) -> None:
        self.transcript.configure(state="normal")
        self.transcript.insert("end", f"{who}: {content}\n\n")
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    def send(self) -> None:
        content = self.question.get("1.0", "end").strip()
        if not content or self.busy:
            return
        self.question.delete("1.0", "end")
        self.append("You / 你", content)

        def chat():
            reply = self.companion.ask(content)
            self.results.put((True, reply, self.show_reply, False))
            if self.companion.settings.voice_enabled and not self.demo:
                try:
                    Speech(self.companion.cloud).speak(reply.text)
                except Exception as error:
                    reply = replace(reply, warnings=reply.warnings + (f"Voice: {type(error).__name__}",))
            return reply

        self.submit(chat, lambda reply: self.status.set(f"{reply.route}; {'; '.join(reply.warnings)}"))

    def show_reply(self, reply) -> None:
        self.append("Emobot", reply.text)
        self.append("Actions / 动作", ", ".join(f"{a.name} {a.duration}ms" for a in reply.actions) or "—")
        self.status.set(f"{reply.route}; references={len(reply.references)}; {'; '.join(reply.warnings)}")
        self.refresh_memory()

    def listen(self) -> None:
        if self.demo:
            self.status.set("Microphone requires cloud configuration / 演示模式不调用语音服务")
            return
        self.submit(
            lambda: Speech(self.companion.cloud).listen(), lambda text: self.question.insert("end", text)
        )

    def _actions_page(self) -> None:
        page = self.pages["Actions / 表情动作"]
        ttk.Label(page, text="59 actions · Duration / 时长 (50–5000 ms)").pack(anchor="w")
        self.duration = tk.IntVar(value=700)
        ttk.Spinbox(page, from_=50, to=5000, increment=50, textvariable=self.duration, width=12).pack(
            anchor="w", pady=8
        )
        grid = ttk.Frame(page)
        grid.pack(fill="both", expand=True)
        for index, action in enumerate(ACTIONS):
            ttk.Button(grid, text=action, command=lambda value=action: self.perform(value)).grid(
                row=index // 6, column=index % 6, sticky="ew", padx=3, pady=4
            )
        for index in range(6):
            grid.columnconfigure(index, weight=1)

    def perform(self, name: str) -> None:
        try:
            action = Action(name, self.duration.get())
        except (ValueError, tk.TclError) as error:
            self.status.set(str(error))
            return
        if self.robot.connected:
            self.submit(lambda: self.robot.send_actions((action,)))
        else:
            self.status.set(f"Simulated / 模拟: {name} {action.duration}ms")

    def _device_page(self) -> None:
        page = self.pages["Device / 连接校准"]
        self.port = tk.StringVar()
        self.ports = ttk.Combobox(page, textvariable=self.port, width=50)
        self.ports.pack(anchor="w", pady=5)
        ttk.Button(
            page,
            text="Scan USB / 扫描串口",
            command=lambda: self.submit(
                self.robot.serial_ports, lambda values: self.ports.configure(values=values)
            ),
        ).pack(anchor="w")
        ttk.Button(
            page,
            text="Connect USB / 连接串口",
            command=self.connect_usb,
        ).pack(anchor="w", pady=5)
        self.ble_address = tk.StringVar()
        self.ble_choices = ttk.Combobox(page, textvariable=self.ble_address, width=70)
        self.ble_choices.pack(anchor="w", pady=5)
        ttk.Button(
            page,
            text="Scan BLE / 扫描蓝牙",
            command=lambda: self.submit(
                self.robot.ble_devices,
                lambda values: self.ble_choices.configure(values=[address for _, address in values]),
            ),
        ).pack(anchor="w")
        ttk.Button(
            page,
            text="Connect BLE / 连接蓝牙",
            command=self.connect_ble,
        ).pack(anchor="w", pady=5)
        ttk.Button(page, text="Disconnect / 断开", command=lambda: self.submit(self.robot.disconnect)).pack(
            anchor="w", pady=5
        )
        factory = ttk.LabelFrame(page, text="Calibration & device commands / 校准和设备指令", padding=10)
        factory.pack(fill="x", pady=16)
        self.factory_text = tk.StringVar(value="head_move 90 90 600")
        ttk.Entry(factory, textvariable=self.factory_text, width=65).pack(side="left")
        ttk.Button(factory, text="Execute / 执行", command=self.factory).pack(side="left", padx=8)
        ttk.Label(
            page,
            text="Commands: on, off, mac_address, reboot, reset_wifi, adjust_x ±N, adjust_y ±N, head_move X Y MS\nX/Y: 0–180; firmware clamps movement to safe calibrated ranges.",
            wraplength=850,
        ).pack(anchor="w")

    def factory(self) -> None:
        command = self.factory_text.get()
        self.submit(lambda: self.robot.factory(command))

    def connect_usb(self) -> None:
        port = self.port.get()
        self.submit(lambda: self.robot.connect_usb(port))

    def connect_ble(self) -> None:
        address = self.ble_address.get()
        self.submit(lambda: self.robot.connect_ble(address))

    def _settings_page(self) -> None:
        page = self.pages["Settings / API 设置"]
        canvas = tk.Canvas(page, highlightthickness=0)
        scrollbar = ttk.Scrollbar(page, orient="vertical", command=canvas.yview)
        form = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.config_vars = {}
        for index, (name, value) in enumerate(asdict(self.companion.settings).items()):
            if name == "persona":
                continue
            ttk.Label(form, text=name).grid(row=index, column=0, sticky="w", padx=5, pady=4)
            variable = (
                tk.BooleanVar(value=value) if isinstance(value, bool) else tk.StringVar(value=str(value))
            )
            self.config_vars[name] = variable
            if isinstance(value, bool):
                widget = ttk.Checkbutton(form, variable=variable)
            elif name in {"language", "theme", "voice", "speech_provider"}:
                choices = {
                    "language": ["zh", "en"],
                    "theme": ["system", "light", "dark"],
                    "voice": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                    "speech_provider": ["openai", "volcano"],
                }[name]
                widget = ttk.Combobox(form, textvariable=variable, values=choices, state="readonly", width=48)
            else:
                widget = ttk.Entry(
                    form,
                    textvariable=variable,
                    width=55,
                    show="•" if "key" in name or "token" in name else "",
                )
            widget.grid(row=index, column=1, sticky="w", pady=4)
        ttk.Button(form, text="Save & apply / 保存应用", command=self.save_settings).grid(
            row=40, column=1, sticky="w", pady=12
        )

    def save_settings(self) -> None:
        if self.busy:
            self.status.set("Wait for the current operation before changing settings")
            return
        try:
            values = {name: variable.get() for name, variable in self.config_vars.items()}
            values["embedding_dimensions"] = int(values["embedding_dimensions"])
            updated = replace(self.companion.settings, **values).validate()
            if any(
                getattr(updated, name) != getattr(self.companion.settings, name)
                for name in ("user", "database_url", "embedding_dimensions")
            ):
                updated.save(self.config_path)
                self.status.set("Settings saved. Restart to apply database/user/dimensions / 重启后应用")
                return
            self.companion.update_settings(updated)
            updated.save(self.config_path)
            self.apply_theme(updated.theme)
            self.status.set("Settings saved / 设置已保存")
        except (ValueError, tk.TclError) as error:
            self.status.set(str(error))

    def apply_theme(self, name: str) -> None:
        style = ttk.Style(self.window)
        if not hasattr(self, "_native_theme"):
            self._native_theme = style.theme_use()
            self._native_colors = (
                style.lookup(".", "background") or "#f5f7fb",
                style.lookup(".", "foreground") or "#182338",
            )
        dark = name == "dark"
        background, foreground = ("#20242c", "#f4f6fa") if dark else ("#f5f7fb", "#182338")
        if name == "system":
            background, foreground = self._native_colors
        style.theme_use(self._native_theme if name == "system" else "clam")
        style.configure(".", background=background, foreground=foreground)
        style.configure("TNotebook.Tab", padding=[8, 8])
        self.window.configure(background=background)
        self.transcript.configure(background=background, foreground=foreground, insertbackground=foreground)
        self.question.configure(background=background, foreground=foreground, insertbackground=foreground)

    def _memory_page(self) -> None:
        page = self.pages["Persona & memory / 人格记忆"]
        ttk.Label(page, text="Editable persona / 可编辑人格").pack(anchor="w")
        self.persona = tk.Text(page, height=4, wrap="word")
        self.persona.insert("1.0", self.companion.settings.persona)
        self.persona.pack(fill="x", pady=6)
        ttk.Button(page, text="Save persona / 保存人格", command=self.save_persona).pack(anchor="w")
        self.memory_table = ttk.Treeview(page, columns=("content", "category"), show="headings", height=9)
        self.memory_table.heading("content", text="Memory / 记忆")
        self.memory_table.heading("category", text="Category / 类别")
        self.memory_table.column("content", width=680)
        self.memory_table.column("category", width=120)
        self.memory_table.pack(fill="both", expand=True, pady=10)
        self.memory_text = tk.StringVar()
        ttk.Entry(page, textvariable=self.memory_text).pack(fill="x")
        row = ttk.Frame(page)
        row.pack(fill="x", pady=8)
        for label, command in (
            ("Add / 新增", self.add_memory),
            ("Update / 修改", self.edit_memory),
            ("Forget selected / 删除", self.forget_memory),
            ("Forget all / 清除全部", self.forget_all),
            ("Import docs / 导入文档", self.import_docs),
            ("Index vectors / 向量索引", self.index_vectors),
        ):
            ttk.Button(row, text=label, command=command).pack(side="left", padx=3)
        self.memory_table.bind("<<TreeviewSelect>>", self.select_memory)
        self.refresh_memory()

    def save_persona(self) -> None:
        if self.busy:
            self.status.set("Wait for the current operation before editing persona")
            return
        value = self.persona.get("1.0", "end").strip()
        if len(value) > 6000:
            self.status.set("Persona exceeds 6000 characters")
            return
        updated = replace(self.companion.settings, persona=value)
        self.companion.update_settings(updated)
        updated.save(self.config_path)
        self.status.set("Persona saved / 人格已保存")

    def refresh_memory(self) -> None:
        for item in self.memory_table.get_children():
            self.memory_table.delete(item)
        for row in self.companion.archive.list_memories():
            self.memory_table.insert("", "end", iid=row["id"], values=(row["content"], row["category"]))

    def select_memory(self, _event=None) -> None:
        selected = self.memory_table.selection()
        if selected:
            self.memory_text.set(self.memory_table.item(selected[0], "values")[0])

    def add_memory(self) -> None:
        value = self.memory_text.get()
        self.submit(
            lambda: self.companion.archive.remember(value, "manual"), lambda _result: self.refresh_memory()
        )

    def edit_memory(self) -> None:
        selected, value = self.memory_table.selection(), self.memory_text.get()
        if selected:
            self.submit(
                lambda: self.companion.archive.edit_memory(selected[0], value),
                lambda _result: self.refresh_memory(),
            )

    def forget_memory(self) -> None:
        selected = self.memory_table.selection()
        if selected:
            self.submit(lambda: self.companion.forget(selected[0]), lambda _result: self.refresh_memory())

    def forget_all(self) -> None:
        if messagebox.askyesno(
            "Forget / 清除", "Delete all memories and saved chat history?\n删除全部记忆和已保存聊天？"
        ):
            self.submit(self.companion.forget, lambda _result: self.refresh_memory())

    def import_docs(self) -> None:
        paths = filedialog.askopenfilenames(filetypes=[("Markdown", "*.md")])
        if paths:
            self.submit(
                lambda: self.companion.archive.import_markdown([Path(p) for p in paths]),
                lambda count: self.status.set(f"Imported {count} documents"),
            )

    def index_vectors(self) -> None:
        self.submit(
            lambda: self.companion.archive.index(self.companion.cloud),
            lambda count: self.status.set(f"Indexed {count} chunks/memories"),
        )

    def _firmware_page(self) -> None:
        page = self.pages["Firmware / 固件"]
        self.image = tk.StringVar()
        self.flash_chip = tk.StringVar(value="esp32s3")
        self.flash_offset = tk.StringVar(value="0x0")
        ttk.Label(
            page,
            text="Select the serial port on the Device tab; disconnect before flashing.\nMerged image: 0x0. Application image: 0x10000. / 选择匹配的芯片与镜像偏移。",
        ).pack(anchor="w", pady=8)
        ttk.Entry(page, textvariable=self.image, width=85).pack(anchor="w", pady=6)
        ttk.Button(
            page,
            text="Choose .bin / 选择固件",
            command=lambda: self.image.set(filedialog.askopenfilename(filetypes=[("Firmware", "*.bin")])),
        ).pack(anchor="w")
        ttk.Combobox(page, textvariable=self.flash_chip, values=["esp32s3", "esp32"], state="readonly").pack(
            anchor="w", pady=8
        )
        ttk.Combobox(page, textvariable=self.flash_offset, values=["0x0", "0x10000"], state="readonly").pack(
            anchor="w", pady=8
        )
        ttk.Button(page, text="Flash / 烧录", command=self.flash).pack(anchor="w")
        self.flash_log = tk.Text(page, height=20, wrap="word")
        self.flash_log.pack(fill="both", expand=True, pady=12)

    def flash(self) -> None:
        port, image, chip, offset = (
            self.port.get(),
            Path(self.image.get()),
            self.flash_chip.get(),
            self.flash_offset.get(),
        )
        if not port:
            self.status.set("Select a serial port first")
            return

        def execute():
            self.robot.disconnect()
            return flash_image(port, image, chip, offset)

        self.submit(execute, lambda result: self.flash_log.insert("end", result + "\n"))

    def close(self) -> None:
        if self.closing:
            return
        if self.busy:
            self.status.set("Waiting for operation to finish before closing / 等待操作完成后关闭")
            self.window.after(200, self.close)
            return
        self.closing = True
        self.window.after_cancel(self._poll_handle)
        self.pool.shutdown(wait=True, cancel_futures=True)
        errors = []
        for component in (self.robot, self.companion.cloud, self.companion.archive):
            try:
                component.close()
            except Exception as error:
                errors.append(type(error).__name__)
        self.window.destroy()
        if errors:
            logging.getLogger(__name__).warning("Shutdown cleanup incomplete: %s", ", ".join(errors))
