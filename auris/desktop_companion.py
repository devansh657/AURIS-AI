from __future__ import annotations

import ctypes
import os
import queue
import subprocess
import threading
import tkinter as tk
from ctypes import wintypes
from pathlib import Path
from typing import Any, Callable

from auris.audit import record_event
from auris.desktop_state import COMPANION_STATUS_PATH, write_companion_status
from auris.local_client import AurisClientError, AurisLocalClient


ROOT = Path(__file__).resolve().parents[1]
LAUNCH_SCRIPT = ROOT / "scripts" / "launch_auris.ps1"
COMPANION_PID_PATH = ROOT / "data" / "desktop-companion.pid"

BG = "#05090d"
PANEL = "#09131a"
PANEL_2 = "#0d1d25"
CYAN = "#54d9e8"
TEAL = "#48c9a8"
AMBER = "#e9b95d"
RED = "#ef6b73"
TEXT = "#e5f4f5"
MUTED = "#7e9aa3"
HOTKEY_ACTIONS = {1: "toggle_overlay", 2: "push_to_talk", 3: "emergency_stop"}


class NotifyIconData(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("hWnd", wintypes.HWND),
        ("uID", wintypes.UINT),
        ("uFlags", wintypes.UINT),
        ("uCallbackMessage", wintypes.UINT),
        ("hIcon", wintypes.HICON),
        ("szTip", wintypes.WCHAR * 128),
        ("dwState", wintypes.DWORD),
        ("dwStateMask", wintypes.DWORD),
        ("szInfo", wintypes.WCHAR * 256),
        ("uTimeoutOrVersion", wintypes.UINT),
        ("szInfoTitle", wintypes.WCHAR * 64),
        ("dwInfoFlags", wintypes.DWORD),
        ("guidItem", ctypes.c_byte * 16),
        ("hBalloonIcon", wintypes.HICON),
    ]


class Win32Tray:
    WM_TRAY = 0x0400 + 40
    WM_UPDATE = 0x0400 + 41
    WM_NOTIFY = 0x0400 + 42
    NIM_ADD = 0
    NIM_MODIFY = 1
    NIM_DELETE = 2
    NIF_MESSAGE = 0x1
    NIF_ICON = 0x2
    NIF_TIP = 0x4
    NIF_INFO = 0x10
    MF_STRING = 0x0
    MF_SEPARATOR = 0x800
    MF_CHECKED = 0x8
    TPM_RETURNCMD = 0x100
    TPM_NONOTIFY = 0x80
    WM_CLOSE = 0x0010
    WM_DESTROY = 0x0002
    WM_HOTKEY = 0x0312
    WM_LBUTTONDBLCLK = 0x0203
    WM_RBUTTONUP = 0x0205
    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_NOREPEAT = 0x4000

    ACTIONS = {
        101: "toggle_overlay",
        102: "push_to_talk",
        103: "open_dashboard",
        104: "toggle_voice",
        105: "toggle_private",
        106: "toggle_control",
        107: "emergency_stop",
        108: "exit",
    }

    def __init__(self, callback: Callable[[str], None]) -> None:
        self.callback = callback
        self.hwnd: int | None = None
        self._thread = threading.Thread(target=self._run, name="auris-tray", daemon=True)
        self._ready = threading.Event()
        self._state_lock = threading.Lock()
        self._state = {"voice": False, "private": False, "stopped": False}
        self._notification = ("", "", False)
        self.hotkeys: list[str] = []
        self._nid: NotifyIconData | None = None
        self._wndproc: Any = None
        self.error = ""
        self.registered = False

    def start(self) -> list[str]:
        self._thread.start()
        self._ready.wait(timeout=8)
        return list(self.hotkeys)

    def stop(self) -> None:
        if self.hwnd:
            ctypes.windll.user32.PostMessageW(self.hwnd, self.WM_CLOSE, 0, 0)
        self._thread.join(timeout=4)

    def update_state(self, *, voice: bool, private: bool, stopped: bool) -> None:
        with self._state_lock:
            self._state = {"voice": voice, "private": private, "stopped": stopped}
        if self.hwnd:
            ctypes.windll.user32.PostMessageW(self.hwnd, self.WM_UPDATE, 0, 0)

    def notify(self, title: str, message: str, *, warning: bool = False) -> None:
        with self._state_lock:
            self._notification = (title[:63], message[:255], warning)
        if self.hwnd:
            ctypes.windll.user32.PostMessageW(self.hwnd, self.WM_NOTIFY, 0, 0)

    def _run(self) -> None:
        try:
            self._run_win32()
        except BaseException as error:
            self.error = str(error)[:300]
            self._ready.set()

    def _run_win32(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        shell32 = ctypes.windll.shell32

        result_type = ctypes.c_ssize_t
        wndproc_type = ctypes.WINFUNCTYPE(
            result_type, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        )

        class WindowClass(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", wndproc_type),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        user32.DefWindowProcW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.DefWindowProcW.restype = result_type
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            wintypes.LPVOID,
        ]
        user32.CreateWindowExW.restype = wintypes.HWND
        user32.CreatePopupMenu.restype = wintypes.HMENU
        user32.TrackPopupMenu.restype = wintypes.UINT
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        shell32.ExtractIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT]
        shell32.ExtractIconW.restype = wintypes.HICON
        shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NotifyIconData)]

        @wndproc_type
        def window_proc(hwnd: int, message: int, wparam: int, lparam: int) -> int:
            if message == self.WM_TRAY:
                mouse_message = int(lparam)
                if mouse_message == self.WM_LBUTTONDBLCLK:
                    self.callback("toggle_overlay")
                elif mouse_message == self.WM_RBUTTONUP:
                    self._show_menu(hwnd)
                return 0
            if message == self.WM_HOTKEY:
                action = hotkey_action(int(wparam))
                if action:
                    self.callback(action)
                return 0
            if message == self.WM_UPDATE:
                self._update_tooltip()
                return 0
            if message == self.WM_NOTIFY:
                self._show_notification()
                return 0
            if message == self.WM_CLOSE:
                user32.DestroyWindow(hwnd)
                return 0
            if message == self.WM_DESTROY:
                for identifier in (1, 2, 3):
                    user32.UnregisterHotKey(hwnd, identifier)
                if self._nid is not None:
                    shell32.Shell_NotifyIconW(self.NIM_DELETE, ctypes.byref(self._nid))
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, message, wparam, lparam)

        self._wndproc = window_proc
        instance = kernel32.GetModuleHandleW(None)
        class_name = f"AURISDesktopCompanion{os.getpid()}"
        window_class = WindowClass()
        window_class.lpfnWndProc = window_proc
        window_class.hInstance = instance
        window_class.lpszClassName = class_name
        if not user32.RegisterClassW(ctypes.byref(window_class)):
            self._ready.set()
            return
        hwnd = user32.CreateWindowExW(0, class_name, "AURIS", 0, 0, 0, 0, 0, 0, 0, instance, None)
        if not hwnd:
            self._ready.set()
            return
        self.hwnd = hwnd

        icon_path = str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "shell32.dll")
        icon = shell32.ExtractIconW(instance, icon_path, 220)
        nid = NotifyIconData()
        nid.cbSize = ctypes.sizeof(NotifyIconData)
        nid.hWnd = hwnd
        nid.uID = 1
        nid.uFlags = self.NIF_MESSAGE | self.NIF_ICON | self.NIF_TIP
        nid.uCallbackMessage = self.WM_TRAY
        nid.hIcon = icon
        nid.szTip = "AURIS // Initializing"
        self._nid = nid
        self.registered = bool(shell32.Shell_NotifyIconW(self.NIM_ADD, ctypes.byref(nid)))

        definitions = (
            (1, self.MOD_CONTROL | self.MOD_NOREPEAT, 0x20, "Ctrl+Space"),
            (2, self.MOD_CONTROL | self.MOD_SHIFT | self.MOD_NOREPEAT, ord("J"), "Ctrl+Shift+J"),
            (3, self.MOD_CONTROL | self.MOD_SHIFT | self.MOD_NOREPEAT, ord("X"), "Ctrl+Shift+X"),
        )
        self.hotkeys = [
            label for identifier, modifiers, key, label in definitions
            if user32.RegisterHotKey(hwnd, identifier, modifiers, key)
        ]
        self._ready.set()
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        self.hwnd = None

    def _show_menu(self, hwnd: int) -> None:
        user32 = ctypes.windll.user32
        user32.CreatePopupMenu.restype = wintypes.HMENU
        with self._state_lock:
            state = dict(self._state)
        menu = user32.CreatePopupMenu()
        entries = (
            (101, "Quick command", False),
            (102, "Push to talk", False),
            (103, "Open command centre", False),
            (0, "", False),
            (104, "Background voice", state["voice"]),
            (105, "Private overlay mode", state["private"]),
            (106, "Resume automation" if state["stopped"] else "Pause automation", False),
            (107, "Emergency stop", False),
            (0, "", False),
            (108, "Exit desktop companion", False),
        )
        for identifier, label, checked in entries:
            if identifier == 0:
                user32.AppendMenuW(menu, self.MF_SEPARATOR, 0, None)
            else:
                flags = self.MF_STRING | (self.MF_CHECKED if checked else 0)
                user32.AppendMenuW(menu, flags, identifier, label)
        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        user32.SetForegroundWindow(hwnd)
        choice = user32.TrackPopupMenu(
            menu,
            self.TPM_RETURNCMD | self.TPM_NONOTIFY,
            point.x,
            point.y,
            0,
            hwnd,
            None,
        )
        user32.DestroyMenu(menu)
        action = self.ACTIONS.get(int(choice))
        if action:
            self.callback(action)

    def _update_tooltip(self) -> None:
        if self._nid is None:
            return
        with self._state_lock:
            state = dict(self._state)
        if state["stopped"]:
            label = "AURIS // Automation paused"
        elif state["voice"]:
            label = "AURIS // Online // Wake word armed"
        else:
            label = "AURIS // Online // Voice standby"
        self._nid.uFlags = self.NIF_MESSAGE | self.NIF_ICON | self.NIF_TIP
        self._nid.szTip = label
        ctypes.windll.shell32.Shell_NotifyIconW(self.NIM_MODIFY, ctypes.byref(self._nid))

    def _show_notification(self) -> None:
        if self._nid is None:
            return
        with self._state_lock:
            title, message, warning = self._notification
        self._nid.uFlags = self.NIF_INFO
        self._nid.szInfoTitle = title
        self._nid.szInfo = message
        self._nid.dwInfoFlags = 2 if warning else 1
        ctypes.windll.shell32.Shell_NotifyIconW(self.NIM_MODIFY, ctypes.byref(self._nid))


class DesktopCompanion:
    def __init__(self) -> None:
        self.client = AurisLocalClient()
        self.actions: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("AURIS Quick Command")
        self.root.configure(bg=BG)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.protocol("WM_DELETE_WINDOW", self.hide_overlay)
        self.private_mode = tk.BooleanVar(value=False)
        self.voice_enabled = False
        self.control_stopped = False
        self.active_approval: str | None = None
        self.hotkeys: list[str] = []
        self._busy = False
        self._status_inflight = False
        self._drag_origin = (0, 0)
        self._build_overlay()
        self.tray = Win32Tray(lambda action: self.actions.put(("action", action)))
        self.hotkeys = self.tray.start()
        self.root.after(50, self._drain_actions)
        self.root.after(100, self.refresh_status)
        record_event(
            "desktop_companion.started",
            {
                "pid": os.getpid(),
                "hotkeys": self.hotkeys,
                "tray_registered": self.tray.registered,
                "tray_error": self.tray.error,
            },
        )

    def run(self) -> None:
        self.root.mainloop()

    def _build_overlay(self) -> None:
        shell = tk.Frame(self.root, bg=BG, highlightbackground=CYAN, highlightthickness=1)
        shell.pack(fill="both", expand=True)

        header = tk.Frame(shell, bg=PANEL, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="AURIS // QUICK COMMAND",
            bg=PANEL,
            fg=TEXT,
            font=("Segoe UI Semibold", 12),
        ).pack(side="left", padx=18)
        self.state_label = tk.Label(
            header,
            text="CONNECTING",
            bg=PANEL,
            fg=AMBER,
            font=("Consolas", 9, "bold"),
        )
        self.state_label.pack(side="left", padx=12)
        tk.Button(
            header,
            text="HIDE",
            command=self.hide_overlay,
            bg=PANEL,
            fg=MUTED,
            activebackground=PANEL_2,
            activeforeground=TEXT,
            bd=0,
            padx=14,
            font=("Consolas", 9, "bold"),
            cursor="hand2",
        ).pack(side="right", padx=8)
        header.bind("<ButtonPress-1>", self._begin_drag)
        header.bind("<B1-Motion>", self._drag)

        command_band = tk.Frame(shell, bg=PANEL_2, padx=16, pady=14)
        command_band.pack(fill="x")
        self.command_input = tk.Entry(
            command_band,
            bg=BG,
            fg=TEXT,
            insertbackground=CYAN,
            relief="flat",
            highlightbackground="#1b3b47",
            highlightcolor=CYAN,
            highlightthickness=1,
            font=("Segoe UI", 13),
        )
        self.command_input.pack(side="left", fill="x", expand=True, ipady=9)
        self.command_input.bind("<Return>", lambda _event: self.execute_command())
        self.execute_button = tk.Button(
            command_band,
            text="EXECUTE",
            command=self.execute_command,
            bg="#123642",
            fg=TEXT,
            activebackground="#18505d",
            activeforeground=TEXT,
            relief="flat",
            padx=18,
            pady=9,
            font=("Consolas", 10, "bold"),
            cursor="hand2",
        )
        self.execute_button.pack(side="left", padx=(10, 0))

        transcript_shell = tk.Frame(shell, bg=BG, padx=16, pady=12)
        transcript_shell.pack(fill="both", expand=True)
        self.transcript = tk.Text(
            transcript_shell,
            bg=BG,
            fg=TEXT,
            relief="flat",
            wrap="word",
            state="disabled",
            font=("Segoe UI", 11),
            padx=2,
            pady=2,
            height=10,
            cursor="arrow",
        )
        self.transcript.tag_configure("label", foreground=CYAN, font=("Consolas", 9, "bold"), spacing1=8)
        self.transcript.tag_configure("body", foreground=TEXT, spacing3=8)
        self.transcript.tag_configure("system", foreground=MUTED, font=("Consolas", 9), spacing3=8)
        self.transcript.tag_configure("warning", foreground=RED, spacing3=8)
        self.transcript.pack(fill="both", expand=True)
        self._append_transcript("SYSTEM", "Desktop companion ready.", "system")

        self.approval_frame = tk.Frame(shell, bg="#241c10", padx=16, pady=10)
        self.approval_text = tk.Label(
            self.approval_frame,
            text="",
            bg="#241c10",
            fg=AMBER,
            justify="left",
            anchor="w",
            font=("Consolas", 9, "bold"),
        )
        self.approval_text.pack(side="left", fill="x", expand=True)
        tk.Button(
            self.approval_frame,
            text="REJECT",
            command=lambda: self.decide_approval(False),
            bg="#3b171b",
            fg=TEXT,
            relief="flat",
            padx=13,
            pady=7,
            cursor="hand2",
        ).pack(side="right", padx=(8, 0))
        tk.Button(
            self.approval_frame,
            text="APPROVE ONCE",
            command=lambda: self.decide_approval(True),
            bg="#184638",
            fg=TEXT,
            relief="flat",
            padx=13,
            pady=7,
            cursor="hand2",
        ).pack(side="right", padx=(8, 0))

        controls = tk.Frame(shell, bg=PANEL, padx=16, pady=10)
        controls.pack(fill="x")
        self.listen_button = tk.Button(
            controls,
            text="LISTEN",
            command=self.push_to_talk,
            bg=PANEL_2,
            fg=CYAN,
            relief="flat",
            padx=14,
            pady=7,
            font=("Consolas", 9, "bold"),
            cursor="hand2",
        )
        self.listen_button.pack(side="left")
        tk.Button(
            controls,
            text="COMMAND CENTRE",
            command=self.open_dashboard,
            bg=PANEL_2,
            fg=TEXT,
            relief="flat",
            padx=14,
            pady=7,
            font=("Consolas", 9, "bold"),
            cursor="hand2",
        ).pack(side="left", padx=8)
        self.private_check = tk.Checkbutton(
            controls,
            text="PRIVATE",
            variable=self.private_mode,
            command=self._private_changed,
            bg=PANEL,
            fg=MUTED,
            activebackground=PANEL,
            activeforeground=TEXT,
            selectcolor=BG,
            font=("Consolas", 9, "bold"),
        )
        self.private_check.pack(side="left", padx=8)
        self.activity_label = tk.Label(
            controls,
            text="READY",
            bg=PANEL,
            fg=MUTED,
            font=("Consolas", 9),
        )
        self.activity_label.pack(side="left", padx=10)
        tk.Button(
            controls,
            text="EMERGENCY STOP",
            command=self.emergency_stop,
            bg="#4a171c",
            fg="#ffdfe1",
            activebackground="#6a1f26",
            activeforeground="#ffffff",
            relief="flat",
            padx=14,
            pady=7,
            font=("Consolas", 9, "bold"),
            cursor="hand2",
        ).pack(side="right")

        self.root.bind("<Escape>", lambda _event: self.hide_overlay())
        self.root.bind("<Control-l>", lambda _event: self.push_to_talk())

    def show_overlay(self) -> None:
        width, height = 760, 470
        x = max(12, self.root.winfo_screenwidth() - width - 28)
        y = max(12, self.root.winfo_screenheight() - height - 72)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.deiconify()
        self.root.lift()
        self.command_input.focus_force()
        self._write_status("ready")

    def hide_overlay(self) -> None:
        self.root.withdraw()
        self._write_status("ready")

    def toggle_overlay(self) -> None:
        if self.root.state() == "withdrawn":
            self.show_overlay()
        else:
            self.hide_overlay()

    def execute_command(self, *, from_voice: bool = False, voice_turn_id: str | None = None) -> None:
        command = self.command_input.get().strip()
        if not command or self._busy:
            return
        if self.control_stopped and "resume" not in command.casefold():
            self._append_transcript("AURIS", "Automation is paused. Resume it before issuing a command.", "warning")
            return
        self.command_input.delete(0, "end")
        self._append_transcript("DEVANSH // VOICE" if from_voice else "DEVANSH", command, "body")
        self._set_busy(True, "PLANNING AND EXECUTING")
        private = self.private_mode.get()
        self._run_async(
            lambda: self.client.command(command, private=private, voice_turn_id=voice_turn_id, allow_failure=True),
            lambda result: self._command_finished(result, from_voice=from_voice, voice_turn_id=voice_turn_id),
        )

    def push_to_talk(self) -> None:
        if self._busy or self.control_stopped:
            return
        self.show_overlay()
        self._set_busy(True, "LISTENING // SPEAK NOW")
        private = self.private_mode.get()

        def listen() -> dict[str, Any]:
            status = self.client.status()
            restore_voice = bool(status.get("voice", {}).get("background_enabled"))
            if restore_voice:
                self.client.set_background_voice(False)
            try:
                return self.client.listen(timeout_seconds=10, private=private)
            finally:
                if restore_voice:
                    self.client.set_background_voice(True)

        self._run_async(listen, self._voice_finished)

    def decide_approval(self, approve: bool) -> None:
        if not self.active_approval or self._busy:
            return
        approval_id = self.active_approval
        self._set_busy(True, "EXECUTING APPROVED ACTION" if approve else "REJECTING ACTION")
        self._run_async(
            lambda: self.client.decide_approval(approval_id, approve=approve),
            self._approval_finished,
        )

    def emergency_stop(self) -> None:
        self.show_overlay()
        self.state_label.configure(text="STOPPING", fg=RED)
        self.activity_label.configure(text="EMERGENCY STOP REQUESTED", fg=RED)
        self._run_async(
            lambda: self.client.stop_automation("Emergency stop from AURIS desktop companion"),
            self._emergency_finished,
            exclusive=False,
        )

    def toggle_control(self) -> None:
        if self.control_stopped:
            operation = lambda: self.client.resume_automation("Resumed from AURIS desktop companion")
        else:
            operation = lambda: self.client.stop_automation("Paused from AURIS desktop companion")
        self._run_async(operation, lambda _result: self.refresh_status(), exclusive=False)

    def toggle_voice(self) -> None:
        target = not self.voice_enabled
        self._run_async(
            lambda: self.client.set_background_voice(target),
            lambda _result: self.refresh_status(),
            exclusive=False,
        )

    def toggle_private(self) -> None:
        self.private_mode.set(not self.private_mode.get())
        self._private_changed()

    def open_dashboard(self) -> None:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(LAUNCH_SCRIPT),
            ],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def refresh_status(self) -> None:
        if not self._status_inflight:
            self._status_inflight = True

            def worker() -> None:
                try:
                    result = self.client.status()
                    self.actions.put(("status", result, None))
                except Exception as error:
                    self.actions.put(("status", None, error))

            threading.Thread(target=worker, name="auris-overlay-status", daemon=True).start()
        self.root.after(5000, self.refresh_status)

    def shutdown(self) -> None:
        record_event("desktop_companion.stopped", {"pid": os.getpid()})
        self.tray.stop()
        try:
            current_pid = COMPANION_PID_PATH.read_text(encoding="ascii").strip()
            if current_pid == str(os.getpid()):
                COMPANION_PID_PATH.unlink(missing_ok=True)
                COMPANION_STATUS_PATH.unlink(missing_ok=True)
        except OSError:
            pass
        self.root.destroy()

    def _command_finished(self, response: dict[str, Any], *, from_voice: bool, voice_turn_id: str | None = None) -> None:
        result = response.get("result", {})
        message = str(result.get("message") or response.get("error") or "No successful outcome was reported.")
        self._append_transcript("AURIS", message, "body")
        verification = result.get("verification")
        if verification:
            self._append_transcript("VERIFICATION", str(verification), "system")
        approval = response.get("approval")
        if approval:
            self.active_approval = str(approval["approval_id"])
            risk = str(approval.get("risk_level", "sensitive")).upper()
            self.approval_text.configure(
                text=(
                    f"AUTHORISATION REQUIRED // {risk}\n"
                    f"{approval.get('proposed_action', '')}\n"
                    f"TARGET // {approval.get('target', 'not specified')} // "
                    f"{'REVERSIBLE' if approval.get('reversible') else 'NOT GUARANTEED REVERSIBLE'}\n"
                    f"DATA // {approval.get('data_summary', 'not specified')}"
                )
            )
            self.approval_frame.pack(fill="x", before=self.approval_frame.master.winfo_children()[-1])
            self.tray.notify("AURIS approval required", str(approval.get("proposed_action", "Review action")), warning=True)
        else:
            self._clear_approval()
        self._set_busy(False, "READY")
        if from_voice:
            self._run_async(lambda: self.client.speak(message, voice_turn_id=voice_turn_id), lambda _result: None, exclusive=False)
        self.refresh_status()

    def _voice_finished(self, voice: dict[str, Any]) -> None:
        transcript = str(voice.get("text", "")).strip()
        if not transcript:
            self._set_busy(False, "NO COMMAND HEARD")
            return
        self.command_input.delete(0, "end")
        self.command_input.insert(0, transcript)
        self._append_transcript("VOICE TRANSCRIPT", f"{transcript} // {voice.get('input_provider') or 'LOCAL SPEECH'}", "system")
        self._set_busy(False, "UNDERSTOOD")
        self.execute_command(from_voice=True, voice_turn_id=voice.get("turn_id"))

    def _approval_finished(self, response: dict[str, Any]) -> None:
        task = response.get("task") or {}
        result = task.get("result") or {}
        message = str(result.get("message") or "Approval decision recorded.")
        verification = str(result.get("verification") or "Decision persisted.")
        self._append_transcript("AURIS", message, "body")
        self._append_transcript("VERIFICATION", verification, "system")
        self._clear_approval()
        self._set_busy(False, "READY")
        self.refresh_status()

    def _emergency_finished(self, control: dict[str, Any]) -> None:
        self.control_stopped = bool(control.get("stopped"))
        self._append_transcript("EMERGENCY STOP", str(control.get("reason") or "Automation paused."), "warning")
        self._set_busy(False, "AUTOMATION PAUSED")
        self._render_status()

    def _run_async(
        self,
        operation: Callable[[], Any],
        callback: Callable[[Any], None],
        *,
        exclusive: bool = True,
    ) -> None:
        if exclusive and self._busy is False:
            self._set_busy(True, "WORKING")

        def worker() -> None:
            try:
                result = operation()
                self.actions.put(("work", callback, result, None, exclusive))
            except Exception as error:
                self.actions.put(("work", callback, None, error, exclusive))

        threading.Thread(target=worker, name="auris-overlay-operation", daemon=True).start()

    def _drain_actions(self) -> None:
        try:
            while True:
                item = self.actions.get_nowait()
                if item[0] == "action":
                    self._handle_action(str(item[1]))
                elif item[0] == "status":
                    self._status_inflight = False
                    if item[2] is None:
                        self._apply_status(item[1])
                    else:
                        self._status_failed(item[2])
                elif item[0] == "work":
                    _, callback, result, error, exclusive = item
                    if error is None:
                        callback(result)
                    else:
                        self._operation_failed(error)
                    if exclusive and error is not None:
                        self._set_busy(False, "READY")
        except queue.Empty:
            pass
        self.root.after(50, self._drain_actions)

    def _handle_action(self, action: str) -> None:
        handlers = {
            "toggle_overlay": self.toggle_overlay,
            "push_to_talk": self.push_to_talk,
            "open_dashboard": self.open_dashboard,
            "toggle_voice": self.toggle_voice,
            "toggle_private": self.toggle_private,
            "toggle_control": self.toggle_control,
            "emergency_stop": self.emergency_stop,
            "exit": self.shutdown,
        }
        handler = handlers.get(action)
        if handler:
            handler()

    def _apply_status(self, status: dict[str, Any]) -> None:
        self.voice_enabled = bool(status.get("voice", {}).get("background_enabled"))
        self.control_stopped = bool(status.get("control", {}).get("stopped"))
        self._render_status()
        self._write_status("ready")

    def _status_failed(self, error: Exception) -> None:
        self.state_label.configure(text="OFFLINE", fg=RED)
        self.activity_label.configure(text="LOCAL CORE UNAVAILABLE", fg=RED)
        write_companion_status("degraded", error=str(error)[:200], hotkeys=self.hotkeys)

    def _render_status(self) -> None:
        if self.control_stopped:
            self.state_label.configure(text="AUTOMATION PAUSED", fg=RED)
        elif self.voice_enabled:
            self.state_label.configure(text="ONLINE // WAKE ARMED", fg=TEAL)
        else:
            self.state_label.configure(text="ONLINE // VOICE STANDBY", fg=CYAN)
        self.tray.update_state(
            voice=self.voice_enabled,
            private=self.private_mode.get(),
            stopped=self.control_stopped,
        )

    def _operation_failed(self, error: Exception) -> None:
        message = str(error) if isinstance(error, AurisClientError) else "The desktop operation failed."
        self._append_transcript("AURIS ERROR", message, "warning")
        self.activity_label.configure(text="OPERATION FAILED", fg=RED)
        self.tray.notify("AURIS operation failed", message, warning=True)
        self.refresh_status()

    def _set_busy(self, busy: bool, activity: str) -> None:
        self._busy = busy
        state = "disabled" if busy or self.control_stopped else "normal"
        self.execute_button.configure(state=state)
        self.listen_button.configure(state=state)
        self.activity_label.configure(text=activity, fg=AMBER if busy else MUTED)
        self._write_status("busy" if busy else "ready")

    def _clear_approval(self) -> None:
        self.active_approval = None
        self.approval_frame.pack_forget()

    def _append_transcript(self, label: str, text: str, style: str) -> None:
        self.transcript.configure(state="normal")
        self.transcript.insert("end", f"{label}\n", "label")
        self.transcript.insert("end", f"{text}\n", style)
        self.transcript.see("end")
        self.transcript.configure(state="disabled")

    def _private_changed(self) -> None:
        self.tray.update_state(
            voice=self.voice_enabled,
            private=self.private_mode.get(),
            stopped=self.control_stopped,
        )
        self._append_transcript(
            "PRIVACY",
            "Private overlay mode enabled. Commands from this overlay will not persist."
            if self.private_mode.get()
            else "Standard project context restored.",
            "system",
        )
        self._write_status("ready")

    def _write_status(self, state: str) -> None:
        required_hotkeys = {"Ctrl+Space", "Ctrl+Shift+J", "Ctrl+Shift+X"}
        healthy_shell = self.tray.registered and required_hotkeys.issubset(self.hotkeys)
        write_companion_status(
            state if healthy_shell else "degraded",
            overlay_visible=self.root.state() != "withdrawn",
            voice_enabled=self.voice_enabled,
            private_mode=self.private_mode.get(),
            control_stopped=self.control_stopped,
            hotkeys=self.hotkeys,
            tray_error=self.tray.error,
            tray_registered=self.tray.registered,
        )

    def _begin_drag(self, event: tk.Event) -> None:
        self._drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _drag(self, event: tk.Event) -> None:
        x = event.x_root - self._drag_origin[0]
        y = event.y_root - self._drag_origin[1]
        self.root.geometry(f"+{x}+{y}")


def _acquire_singleton() -> int | None | bool:
    if os.name != "nt":
        return None
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel32.CreateMutexW(None, False, "Local\\AURISDesktopCompanion")
    if not handle:
        raise OSError(ctypes.get_last_error(), "Could not create the AURIS desktop companion mutex.")
    if ctypes.get_last_error() == 183:
        kernel32.CloseHandle(handle)
        return False
    return int(handle)


def hotkey_action(identifier: int) -> str | None:
    return HOTKEY_ACTIONS.get(identifier)


def _release_singleton(handle: int | None | bool) -> None:
    if os.name == "nt" and isinstance(handle, int) and not isinstance(handle, bool):
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle(handle)


def main() -> None:
    if os.name != "nt":
        raise SystemExit("The AURIS desktop companion requires Windows.")
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        ctypes.windll.user32.SetProcessDPIAware()
    singleton = _acquire_singleton()
    if singleton is False:
        return
    COMPANION_PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    COMPANION_PID_PATH.write_text(str(os.getpid()), encoding="ascii")
    try:
        DesktopCompanion().run()
    finally:
        _release_singleton(singleton)


if __name__ == "__main__":
    main()
