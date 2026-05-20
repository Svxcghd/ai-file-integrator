"""
app.py — AI File Integrator v2
Main desktop application. Drag files → AI decides where they go → you confirm.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
import sys
import os

import config
import scanner
from agent import ask_gemini
from mover import safe_move, get_relative, MoveError

# ── Try importing tkinterdnd2 for drag & drop ─────────────────────────────────
try:
    pass  # tkinterdnd2 removed
    DND_AVAILABLE = False
except ImportError:
    DND_AVAILABLE = False

# ── Color palette ─────────────────────────────────────────────────────────────
BG           = "#0e1116"
BG_PANEL     = "#13171f"
BG_CARD      = "#1a1f2b"
BG_INPUT     = "#0b0e14"
BORDER       = "#252c3b"
ACCENT       = "#4ade80"       # green — "go / confirm"
ACCENT_BLUE  = "#60a5fa"
ACCENT_RED   = "#f87171"
ACCENT_AMBER = "#fbbf24"
TEXT         = "#e2e8f0"
TEXT_DIM     = "#64748b"
TEXT_MUTED   = "#334155"
MONO         = ("Cascadia Code", 10) if sys.platform != "win32" else ("Consolas", 10)
UI           = ("Cantarell", 10)
UI_BOLD      = ("Cantarell", 10, "bold")
UI_SM        = ("Cantarell", 9)
UI_LG        = ("Cantarell", 13, "bold")


# ── Main App ──────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI File Integrator")
        self.geometry("1080x700")
        self.minsize(860, 560)
        self.configure(bg=BG)

        # State
        self.project_root: Path | None = None
        self.project_tree: str = ""
        self.project_type: str = ""
        self.project_aiconfig: str = ""
        self.pending_decisions: list[dict] = []  # [{file, decision}, ...]

        self._apply_styles()
        self._build_ui()
        self._load_saved_config()

    # ── Styles ────────────────────────────────────────────────────────────────
    def _apply_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TFrame", background=BG)
        s.configure("Panel.TFrame", background=BG_PANEL)
        s.configure("Card.TFrame", background=BG_CARD)
        s.configure("TLabel", background=BG, foreground=TEXT, font=UI)
        s.configure("Dim.TLabel", background=BG_PANEL, foreground=TEXT_DIM, font=UI_SM)
        s.configure("Card.TLabel", background=BG_CARD, foreground=TEXT, font=UI)
        s.configure("TNotebook", background=BG_PANEL, borderwidth=0)
        s.configure("TNotebook.Tab", background=BG_CARD, foreground=TEXT_DIM,
                    font=UI, padding=(14, 7), borderwidth=0)
        s.map("TNotebook.Tab",
              background=[("selected", BG_PANEL)],
              foreground=[("selected", ACCENT_BLUE)])
        s.configure("Vertical.TScrollbar", background=BG_CARD,
                    troughcolor=BG_INPUT, borderwidth=0, arrowcolor=TEXT_DIM)
        s.configure("Accent.Horizontal.TProgressbar",
                    troughcolor=BG_CARD, background=ACCENT, borderwidth=0, thickness=3)

    # ── UI Build ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=14, pady=(0, 10))

        left = tk.Frame(body, bg=BG_PANEL, width=270)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)
        self._build_left(left)

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True)
        self._build_right(right)

        self._build_statusbar()

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_PANEL, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        tk.Label(hdr, text="◈", bg=BG_PANEL, fg=ACCENT,
                 font=("Cantarell", 18)).pack(side="left", padx=(18, 8))
        tk.Label(hdr, text="AI File Integrator", bg=BG_PANEL, fg=TEXT,
                 font=("Cantarell", 13, "bold")).pack(side="left")
        tk.Label(hdr, text="v2", bg=BG_PANEL, fg=TEXT_MUTED,
                 font=UI_SM).pack(side="left", padx=(6, 0), anchor="s", pady=(0, 4))

        # Right side buttons
        rf = tk.Frame(hdr, bg=BG_PANEL)
        rf.pack(side="right", padx=16, fill="y")

        self._btn_confirm = self._btn(rf, "✓  Confirm All", self._confirm_all,
                                      bg=ACCENT, fg="#0a0f0a", font=UI_BOLD, px=18, py=6)
        self._btn_confirm.pack(side="right", pady=10)
        self._btn_confirm.config(state="disabled")

        self._btn_analyze = self._btn(rf, "⚡  Analyze Files", self._analyze_files,
                                      bg=ACCENT_BLUE, fg="#0a0f14", font=UI_BOLD, px=18, py=6)
        self._btn_analyze.pack(side="right", pady=10, padx=(0, 8))
        self._btn_analyze.config(state="disabled")

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

    def _build_left(self, parent):
        # Section: Project
        self._section_label(parent, "PROJECT")

        path_box = tk.Frame(parent, bg=BG_CARD, padx=10, pady=8)
        path_box.pack(fill="x", padx=12)
        self._path_var = tk.StringVar(value="No folder selected")
        tk.Label(path_box, textvariable=self._path_var, bg=BG_CARD,
                 fg=TEXT_DIM, font=UI_SM, wraplength=210, justify="left").pack(fill="x")

        self._btn(parent, "📁  Choose Project Folder", self._choose_folder,
                  bg=BG_CARD, fg=TEXT, px=10, py=6, full=True).pack(
                  fill="x", padx=12, pady=(6, 0))

        self._divider(parent)
        self._section_label(parent, "PROJECT INFO")

        self._info = {}
        for k in ["Type", "Files", "Dirs"]:
            row = tk.Frame(parent, bg=BG_PANEL)
            row.pack(fill="x", padx=12, pady=2)
            tk.Label(row, text=f"{k}:", bg=BG_PANEL, fg=TEXT_MUTED,
                     font=UI_SM, width=6, anchor="w").pack(side="left")
            lbl = tk.Label(row, text="—", bg=BG_PANEL, fg=TEXT_DIM,
                           font=UI_SM, anchor="w")
            lbl.pack(side="left")
            self._info[k] = lbl

        self._divider(parent)
        self._section_label(parent, "API KEY")

        key_frame = tk.Frame(parent, bg=BG_CARD, padx=8, pady=6)
        key_frame.pack(fill="x", padx=12)
        self._api_var = tk.StringVar()
        self._api_entry = tk.Entry(key_frame, textvariable=self._api_var,
                                   show="•", bg=BG_INPUT, fg=TEXT,
                                   font=UI_SM, relief="flat",
                                   insertbackground=ACCENT_BLUE,
                                   selectbackground="#1e3a5f")
        self._api_entry.pack(fill="x")

        self._btn(parent, "💾  Save API Key", self._save_api_key,
                  bg=BG_CARD, fg=TEXT, px=10, py=5, full=True).pack(
                  fill="x", padx=12, pady=(6, 0))

        self._divider(parent)
        self._section_label(parent, "PROJECT TREE")

        tree_box = tk.Frame(parent, bg=BG_INPUT)
        tree_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self._tree_txt = tk.Text(tree_box, bg=BG_INPUT, fg=TEXT_DIM,
                                  font=("Cascadia Code", 8), relief="flat",
                                  borderwidth=0, state="disabled", wrap="none",
                                  selectbackground=BG_CARD)
        self._tree_txt.pack(fill="both", expand=True, padx=4, pady=4)

    def _build_right(self, parent):
        nb = ttk.Notebook(parent)
        nb.pack(fill="both", expand=True)
        self._nb = nb

        # Tab 1 — Drop Zone
        drop_tab = tk.Frame(nb, bg=BG_PANEL)
        nb.add(drop_tab, text="  Drop Files  ")
        self._build_drop_tab(drop_tab)

        # Tab 2 — Decisions (preview)
        dec_tab = tk.Frame(nb, bg=BG_PANEL)
        nb.add(dec_tab, text="  AI Decisions  ")
        self._build_decisions_tab(dec_tab)

        # Tab 3 — Log
        log_tab = tk.Frame(nb, bg=BG_PANEL)
        nb.add(log_tab, text="  Log  ")
        self._build_log_tab(log_tab)

    def _build_drop_tab(self, parent):
        tk.Label(parent, text="Drop files here or click to browse",
                 bg=BG_PANEL, fg=TEXT, font=("Cantarell", 12, "bold")).pack(pady=(20, 4))
        tk.Label(parent,
                 text="The AI will analyze each file's content and decide where it goes in your project.",
                 bg=BG_PANEL, fg=TEXT_DIM, font=UI_SM).pack()

        # Drop zone
        dz_outer = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        dz_outer.pack(fill="both", expand=True, padx=20, pady=16)

        self._drop_zone = tk.Frame(dz_outer, bg=BG_INPUT)
        self._drop_zone.pack(fill="both", expand=True)

        self._drop_label = tk.Label(
            self._drop_zone,
            text="⬇\n\nDrag & Drop files here\n\nor",
            bg=BG_INPUT, fg=TEXT_DIM,
            font=("Cantarell", 14), justify="center",
        )
        self._drop_label.pack(expand=True)

        self._btn(self._drop_zone, "📂  Browse Files", self._browse_files,
                  bg=BG_CARD, fg=TEXT, px=20, py=8).pack(pady=(0, 60))

        # Queued files list
        self._queued_frame = tk.Frame(parent, bg=BG_PANEL)
        self._queued_frame.pack(fill="x", padx=20, pady=(0, 12))

        self._queued_list = tk.Listbox(
            self._queued_frame,
            bg=BG_CARD, fg=TEXT, font=UI_SM,
            relief="flat", borderwidth=0,
            selectbackground=BG_INPUT,
            height=5,
        )

        self._queued_files: list[Path] = []

    def _build_decisions_tab(self, parent):
        top = tk.Frame(parent, bg=BG_PANEL)
        top.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(top, text="AI Placement Decisions",
                 bg=BG_PANEL, fg=TEXT, font=UI_BOLD).pack(side="left")
        tk.Label(top, text="Review before confirming",
                 bg=BG_PANEL, fg=TEXT_DIM, font=UI_SM).pack(side="left", padx=(10, 0))

        self._btn(top, "✕ Clear", self._clear_decisions,
                  bg=BG_CARD, fg=TEXT_DIM, px=10, py=4).pack(side="right")

        # Decision cards container with scrollbar
        outer = tk.Frame(parent, bg=BG_PANEL)
        outer.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        canvas = tk.Canvas(outer, bg=BG_PANEL, highlightthickness=0)
        sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)

        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        self._dec_inner = tk.Frame(canvas, bg=BG_PANEL)
        self._dec_window = canvas.create_window((0, 0), window=self._dec_inner, anchor="nw")

        self._dec_inner.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig(self._dec_window, width=e.width))

        self._dec_canvas = canvas
        self._decision_widgets: list[dict] = []

    def _build_log_tab(self, parent):
        top = tk.Frame(parent, bg=BG_PANEL)
        top.pack(fill="x", padx=16, pady=(14, 6))
        tk.Label(top, text="Activity Log", bg=BG_PANEL, fg=TEXT, font=UI_BOLD).pack(side="left")
        self._btn(top, "✕ Clear", self._clear_log,
                  bg=BG_CARD, fg=TEXT_DIM, px=10, py=4).pack(side="right")

        log_outer = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        log_outer.pack(fill="both", expand=True, padx=16, pady=(0, 14))

        inner = tk.Frame(log_outer, bg=BG_INPUT)
        inner.pack(fill="both", expand=True)

        sb = ttk.Scrollbar(inner, orient="vertical", style="Vertical.TScrollbar")
        sb.pack(side="right", fill="y")

        self._log_txt = tk.Text(
            inner, bg=BG_INPUT, fg=TEXT, font=MONO,
            relief="flat", borderwidth=0, state="disabled",
            wrap="none", yscrollcommand=sb.set,
            padx=10, pady=8, selectbackground="#1e3a5f",
        )
        self._log_txt.pack(fill="both", expand=True)
        sb.config(command=self._log_txt.yview)

        self._log_txt.tag_config("ok", foreground=ACCENT)
        self._log_txt.tag_config("err", foreground=ACCENT_RED)
        self._log_txt.tag_config("warn", foreground=ACCENT_AMBER)
        self._log_txt.tag_config("info", foreground=ACCENT_BLUE)
        self._log_txt.tag_config("dim", foreground=TEXT_DIM)

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=BG_PANEL, height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=BORDER, height=1).pack(fill="x", side="top")
        self._status_var = tk.StringVar(value="Ready — select a project folder to start.")
        tk.Label(bar, textvariable=self._status_var, bg=BG_PANEL,
                 fg=TEXT_DIM, font=UI_SM, anchor="w", padx=14).pack(side="left", fill="y")
        self._prog = ttk.Progressbar(bar, style="Accent.Horizontal.TProgressbar",
                                     mode="indeterminate", length=100)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _btn(self, parent, text, cmd, bg=BG_CARD, fg=TEXT,
             font=None, px=12, py=6, full=False):
        b = tk.Button(parent, text=text, command=cmd,
                      bg=bg, fg=fg, font=font or UI,
                      relief="flat", borderwidth=0,
                      padx=px, pady=py, cursor="hand2",
                      activebackground=self._lighten(bg),
                      activeforeground=fg)
        if full:
            b.config(anchor="w")
        b.bind("<Enter>", lambda e: b.config(bg=self._lighten(bg)))
        b.bind("<Leave>", lambda e: b.config(bg=bg))
        return b

    def _lighten(self, hex_color):
        try:
            r = min(255, int(int(hex_color[1:3], 16) * 1.25))
            g = min(255, int(int(hex_color[3:5], 16) * 1.25))
            b = min(255, int(int(hex_color[5:7], 16) * 1.25))
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return hex_color

    def _section_label(self, parent, text):
        tk.Label(parent, text=text, bg=BG_PANEL, fg=TEXT_MUTED,
                 font=("Cantarell", 8, "bold"), anchor="w").pack(
                 fill="x", padx=12, pady=(14, 6))

    def _divider(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=12, pady=6)

    def _status(self, msg, color=TEXT_DIM):
        self._status_var.set(msg)
        # Find label and recolor
        for w in self.winfo_children():
            pass  # status label color updated via var

    def _log(self, msg, tag=""):
        self._log_txt.config(state="normal")
        self._log_txt.insert("end", msg + "\n", tag)
        self._log_txt.see("end")
        self._log_txt.config(state="disabled")

    def _clear_log(self):
        self._log_txt.config(state="normal")
        self._log_txt.delete("1.0", "end")
        self._log_txt.config(state="disabled")

    def _clear_decisions(self):
        for w in self._dec_inner.winfo_children():
            w.destroy()
        self.pending_decisions.clear()
        self._decision_widgets.clear()
        self._btn_confirm.config(state="disabled")

    # ── Config ────────────────────────────────────────────────────────────────
    def _load_saved_config(self):
        key = config.get_api_key()
        if key:
            self._api_var.set(key)
        last = config.get_last_project()
        if last and Path(last).exists():
            self.project_root = Path(last)
            self._path_var.set(last)
            self._scan_project()

    def _save_api_key(self):
        key = self._api_var.get().strip()
        if not key:
            messagebox.showwarning("Empty Key", "Please enter your Gemini API key.")
            return
        config.set_api_key(key)
        self._log("✓ API key saved.", "ok")
        self._status_var.set("API key saved.")

    # ── Project ───────────────────────────────────────────────────────────────
    def _choose_folder(self):
        folder = filedialog.askdirectory(title="Select Project Root")
        if folder:
            self.project_root = Path(folder)
            self._path_var.set(folder)
            config.set_last_project(folder)
            self._scan_project()

    def _scan_project(self):
        if not self.project_root:
            return
        self._status_var.set("Scanning project...")
        self.update_idletasks()
        try:
            self.project_tree = scanner.scan(self.project_root)
            self.project_type = scanner.detect_project_type(self.project_root)
            self.project_aiconfig = scanner.read_aiconfig(self.project_root)

            all_files = list(self.project_root.rglob('*'))
            n_files = sum(1 for f in all_files if f.is_file())
            n_dirs = sum(1 for f in all_files if f.is_dir())

            self._info["Type"].config(text=self.project_type or "Unknown")
            self._info["Files"].config(text=str(n_files))
            self._info["Dirs"].config(text=str(n_dirs))

            self._tree_txt.config(state="normal")
            self._tree_txt.delete("1.0", "end")
            self._tree_txt.insert("1.0", self.project_tree)
            self._tree_txt.config(state="disabled")

            self._btn_analyze.config(state="normal")
            self._status_var.set(f"Project loaded: {self.project_root.name}")
            self._log(f"✓ Project scanned: {self.project_root}", "ok")
            self._log(f"  Type: {self.project_type} | Files: {n_files} | Dirs: {n_dirs}", "dim")
            if self.project_aiconfig:
                self._log("  ✓ .aiconfig found — project context loaded", "ok")
            else:
                self._log("  ℹ No .aiconfig found — using auto-detection only", "dim")
        except Exception as e:
            self._status_var.set(f"Scan error: {e}")
            self._log(f"✗ Scan error: {e}", "err")

    # ── File Handling ─────────────────────────────────────────────────────────
    def _on_drop(self, event):
        """Handle drag & drop."""
        raw = event.data
        # tkinterdnd2 returns paths wrapped in {} if they have spaces
        paths = self.tk.splitlist(raw)
        for p in paths:
            self._add_file(Path(p))

    def _browse_files(self):
        try:
            import subprocess, shlex
            result = subprocess.run(
                ["kdialog", "--getopenfilename", "--multiple",
                 str(Path.home()), "*"],
                capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                paths = shlex.split(result.stdout.strip())
                for f in paths:
                    self._add_file(Path(f))
        except Exception:
            files = filedialog.askopenfilenames(title="Select files to integrate")
            for f in files:
                self._add_file(Path(f))

    def _add_file(self, path: Path):
        if not path.exists():
            return
        if path in self._queued_files:
            return
        self._queued_files.append(path)

        # Show in queued list
        if not self._queued_list.winfo_ismapped():
            self._queued_list.pack(fill="x", pady=(4, 0))

        self._queued_list.insert("end", f"  {path.name}")
        self._log(f"+ Queued: {path.name}", "info")
        self._status_var.set(f"{len(self._queued_files)} file(s) queued. Click 'Analyze Files'.")

    # ── Analysis ──────────────────────────────────────────────────────────────
    def _analyze_files(self):
        if not self._queued_files:
            messagebox.showwarning("No Files", "Add files to the drop zone first.")
            return
        if not self.project_root:
            messagebox.showwarning("No Project", "Select a project folder first.")
            return
        api_key = self._api_var.get().strip()
        if not api_key:
            messagebox.showwarning("No API Key", "Enter your Gemini API key first.")
            return

        files = list(self._queued_files)
        self._queued_files.clear()
        self._queued_list.delete(0, "end")

        self._btn_analyze.config(state="disabled", text="⏳  Analyzing...")
        self._btn_confirm.config(state="disabled")
        self._prog.pack(side="right", padx=12)
        self._prog.start(10)
        self._status_var.set(f"Analyzing {len(files)} file(s) with Gemini...")
        self._nb.select(1)  # Switch to decisions tab

        def run():
            results = []
            for f in files:
                self.after(0, lambda name=f.name: self._status_var.set(f"Analyzing: {name}..."))
                self.after(0, lambda name=f.name: self._log(f"⚡ Analyzing: {name}...", "info"))
                try:
                    decision = ask_gemini(api_key, f, self.project_tree, self.project_type, self.project_aiconfig)
                except Exception as e:
                    decision = {
                        "destination": f"_uncategorized/{f.name}",
                        "create_folder": True,
                        "confidence": "low",
                        "reason": f"Gemini error: {e}",
                        "error": True,
                    }
                    self.after(0, lambda err=str(e): self._log(f"✗ Gemini error: {err}", "err"))
                results.append({"file": f, "decision": decision})
                self.after(0, lambda r={"file": f, "decision": decision}: self._add_decision_card(r))
            self.after(0, lambda: self._on_analysis_done(results))

        threading.Thread(target=run, daemon=True).start()

    def _on_analysis_done(self, results):
        self._prog.stop()
        self._prog.pack_forget()
        self._btn_analyze.config(state="normal", text="⚡  Analyze Files")
        self._btn_confirm.config(state="normal")
        self._status_var.set(f"Analysis complete. {len(results)} decision(s) ready — review and confirm.")
        self._log(f"✓ Analysis complete: {len(results)} file(s) processed.", "ok")

    def _add_decision_card(self, result: dict):
        """Add a decision card to the decisions tab."""
        file: Path = result["file"]
        dec: dict = result["decision"]
        self.pending_decisions.append(result)

        card = tk.Frame(self._dec_inner, bg=BG_CARD, padx=14, pady=12)
        card.pack(fill="x", pady=(0, 8), padx=2)

        # Header row
        hdr = tk.Frame(card, bg=BG_CARD)
        hdr.pack(fill="x")

        # Confidence indicator
        conf = dec.get("confidence", "low")
        conf_color = {
            "high": ACCENT,
            "medium": ACCENT_AMBER,
            "low": ACCENT_RED,
        }.get(conf, ACCENT_RED)

        tk.Label(hdr, text="●", bg=BG_CARD, fg=conf_color,
                 font=("Cantarell", 12)).pack(side="left", padx=(0, 6))
        tk.Label(hdr, text=file.name, bg=BG_CARD, fg=TEXT,
                 font=UI_BOLD).pack(side="left")
        tk.Label(hdr, text=f"({conf} confidence)", bg=BG_CARD,
                 fg=conf_color, font=UI_SM).pack(side="left", padx=(8, 0))

        # Arrow + destination
        dest_frame = tk.Frame(card, bg=BG_CARD)
        dest_frame.pack(fill="x", pady=(8, 0))

        tk.Label(dest_frame, text="→", bg=BG_CARD, fg=TEXT_DIM,
                 font=UI).pack(side="left", padx=(0, 8))

        # Editable destination path
        dest_var = tk.StringVar(value=dec.get("destination", ""))
        dest_entry = tk.Entry(dest_frame, textvariable=dest_var,
                              bg=BG_INPUT, fg=ACCENT_BLUE,
                              font=MONO, relief="flat",
                              insertbackground=ACCENT_BLUE,
                              selectbackground="#1e3a5f")
        dest_entry.pack(side="left", fill="x", expand=True)

        # Reason
        reason = dec.get("reason", "")
        tk.Label(card, text=reason, bg=BG_CARD, fg=TEXT_DIM,
                 font=UI_SM, anchor="w", wraplength=600, justify="left").pack(
                 fill="x", pady=(6, 0))

        # Error badge if AI had trouble
        if dec.get("error"):
            tk.Label(card, text="⚠ AI had trouble — please verify the path",
                     bg=BG_CARD, fg=ACCENT_AMBER, font=UI_SM).pack(anchor="w", pady=(4, 0))

        # Store reference to editable var
        result["dest_var"] = dest_var
        result["card"] = card

    # ── Confirm ───────────────────────────────────────────────────────────────
    def _confirm_all(self):
        if not self.pending_decisions:
            return

        ok = messagebox.askyesno(
            "Confirm Integration",
            f"Move {len(self.pending_decisions)} file(s) into the project?\n\n"
            "Files will be COPIED (originals kept in Downloads).",
        )
        if not ok:
            return

        self._btn_confirm.config(state="disabled", text="⏳  Copying...")
        self._prog.pack(side="right", padx=12)
        self._prog.start(10)
        self._nb.select(2)  # Switch to log tab

        def run():
            success = 0
            errors = 0
            for result in self.pending_decisions:
                file: Path = result["file"]
                dest_var = result.get("dest_var")
                destination = dest_var.get().strip() if dest_var else result["decision"].get("destination", "")
                create_folder = result["decision"].get("create_folder", True)

                try:
                    final = safe_move(
                        source=file,
                        project_root=self.project_root,
                        relative_destination=destination,
                        create_folder=create_folder,
                        copy_instead=True,
                    )
                    rel = get_relative(final, self.project_root)
                    self.after(0, lambda r=rel: self._log(f"✓ {r}", "ok"))
                    success += 1
                except MoveError as e:
                    self.after(0, lambda err=str(e): self._log(f"✗ {err}", "err"))
                    errors += 1
                except Exception as e:
                    self.after(0, lambda err=str(e): self._log(f"✗ Unexpected: {err}", "err"))
                    errors += 1

            self.after(0, lambda: self._on_confirm_done(success, errors))

        threading.Thread(target=run, daemon=True).start()

    def _on_confirm_done(self, success, errors):
        self._prog.stop()
        self._prog.pack_forget()
        self._btn_confirm.config(state="normal", text="✓  Confirm All")

        self._log("", "")
        self._log(f"─── Done: {success} copied, {errors} errors ───", "dim")

        self._status_var.set(f"Done! {success} file(s) copied to project. {errors} error(s).")

        # Refresh project tree
        self._scan_project()

        # Clear decisions
        self._clear_decisions()


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
