"""
app.py — AI File Integrator v3
Multi-project desktop tool. No external API. 100% local.
Patch module includes Git checkpoint + validation + revert.
"""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import threading
import sys
import subprocess
import shlex

sys.path.insert(0, str(Path(__file__).parent))
import backend

BG        = "#0d1117"
BG_PANEL  = "#161b22"
BG_CARD   = "#1c2128"
BG_INPUT  = "#0d1117"
BORDER    = "#30363d"
ACCENT    = "#3fb950"
BLUE      = "#58a6ff"
AMBER     = "#d29922"
RED       = "#f85149"
TEXT      = "#e6edf3"
TEXT_DIM  = "#8b949e"
TEXT_MUTED= "#484f58"
MONO      = ("Cascadia Code", 10)
UI        = ("Cantarell", 10)
UI_B      = ("Cantarell", 10, "bold")
UI_SM     = ("Cantarell", 9)
UI_LG     = ("Cantarell", 13, "bold")
UI_XS     = ("Cantarell", 8, "bold")


class ProjectTab:
    def __init__(self, app, notebook, path=None):
        self.app      = app
        self.notebook = notebook
        self.state    = None
        self.pending_decisions   = []
        self.queued_files        = []
        self._patch_target       = None
        self._last_patch_outcome = None
        self._last_integrated_files = []
        self._detected_deps      = []

        self.frame = tk.Frame(notebook, bg=BG)
        self.tab_name = path.name if path else "New Project"
        notebook.add(self.frame, text=f"  {self.tab_name}  ")
        self._build(path)
        if path:
            self._load_project(path)

    def _build(self, initial_path):
        left = tk.Frame(self.frame, bg=BG_PANEL, width=260)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)
        self._build_left(left, initial_path)
        right = tk.Frame(self.frame, bg=BG)
        right.pack(side="left", fill="both", expand=True)
        self._build_right(right)

    def _build_left(self, parent, initial_path):
        self._slabel(parent, "PROJECT")
        self._path_var = tk.StringVar(value=str(initial_path) if initial_path else "No folder selected")
        path_box = tk.Frame(parent, bg=BG_CARD, padx=8, pady=6)
        path_box.pack(fill="x", padx=10)
        tk.Label(path_box, textvariable=self._path_var, bg=BG_CARD, fg=TEXT_DIM,
                 font=UI_SM, wraplength=210, justify="left").pack(fill="x")
        self.app._btn(parent, "📁  Choose Folder", self._choose_folder,
                      bg=BG_CARD, fg=TEXT, full=True).pack(fill="x", padx=10, pady=(4, 0))
        self._divider(parent)
        self._slabel(parent, "PROJECT INFO")
        self._info = {}
        for k in ["Type", "Files", "Dirs", "Git"]:
            row = tk.Frame(parent, bg=BG_PANEL)
            row.pack(fill="x", padx=10, pady=1)
            tk.Label(row, text=f"{k}:", bg=BG_PANEL, fg=TEXT_MUTED,
                     font=UI_SM, width=6, anchor="w").pack(side="left")
            lbl = tk.Label(row, text="—", bg=BG_PANEL, fg=TEXT_DIM, font=UI_SM, anchor="w")
            lbl.pack(side="left")
            self._info[k] = lbl
        self._divider(parent)
        self._slabel(parent, ".AICONFIG")
        self.app._btn(parent, "✨  Generate .aiconfig", self._generate_aiconfig,
                      bg=BG_CARD, fg=TEXT, full=True).pack(fill="x", padx=10, pady=(0, 4))
        editor_frame = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        editor_frame.pack(fill="both", expand=True, padx=10)
        inner = tk.Frame(editor_frame, bg=BG_INPUT)
        inner.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(inner, orient="vertical", style="Vertical.TScrollbar")
        sb.pack(side="right", fill="y")
        self._aiconfig_text = tk.Text(inner, bg=BG_INPUT, fg=TEXT, font=("Cascadia Code", 8),
            relief="flat", borderwidth=0, wrap="none", insertbackground=BLUE,
            selectbackground="#264f78", yscrollcommand=sb.set, padx=6, pady=6)
        self._aiconfig_text.pack(fill="both", expand=True)
        sb.config(command=self._aiconfig_text.yview)
        self.app._btn(parent, "💾  Save .aiconfig", self._save_aiconfig,
                      bg=ACCENT, fg="#0a0f0a", font=UI_B, full=True).pack(
                      fill="x", padx=10, pady=(4, 10))

    def _build_right(self, parent):
        nb = ttk.Notebook(parent, style="Inner.TNotebook")
        nb.pack(fill="both", expand=True)
        self._mod_nb = nb
        m1 = tk.Frame(nb, bg=BG_PANEL)
        nb.add(m1, text="  📦 Integrate  ")
        self._build_integrate(m1)
        m2 = tk.Frame(nb, bg=BG_PANEL)
        nb.add(m2, text="  ✏️ Patch  ")
        self._build_patch(m2)
        m3 = tk.Frame(nb, bg=BG_PANEL)
        nb.add(m3, text="  📦 Deps  ")
        self._build_deps(m3)
        m4 = tk.Frame(nb, bg=BG_PANEL)
        nb.add(m4, text="  📋 Log  ")
        self._build_log(m4)

    def _build_integrate(self, parent):
        top = tk.Frame(parent, bg=BG_PANEL)
        top.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(top, text="Integrate Files", bg=BG_PANEL, fg=TEXT, font=UI_B).pack(side="left")
        bf = tk.Frame(top, bg=BG_PANEL)
        bf.pack(side="right")
        self.app._btn(bf, "📂  Browse", self._browse_files, bg=BG_CARD, fg=TEXT, px=12, py=4).pack(side="left", padx=(0, 6))
        self._btn_analyze = self.app._btn(bf, "⚡  Analyze", self._analyze_files, bg=BLUE, fg="#0a0f14", font=UI_B, px=14, py=4)
        self._btn_analyze.pack(side="left")
        tk.Label(parent, text="Queued files:", bg=BG_PANEL, fg=TEXT_MUTED, font=UI_XS, anchor="w").pack(fill="x", padx=14, pady=(0, 2))
        qf = tk.Frame(parent, bg=BG_CARD)
        qf.pack(fill="x", padx=14, pady=(0, 8))
        self._queue_list = tk.Listbox(qf, bg=BG_CARD, fg=TEXT_DIM, font=UI_SM,
            relief="flat", borderwidth=0, height=4, selectbackground=BG_INPUT, activestyle="none")
        self._queue_list.pack(fill="x", padx=4, pady=4)
        tk.Label(parent, text="AI Decisions — review before confirming:",
                 bg=BG_PANEL, fg=TEXT_MUTED, font=UI_XS, anchor="w").pack(fill="x", padx=14, pady=(0, 2))
        dec_outer = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        dec_outer.pack(fill="both", expand=True, padx=14)
        canvas = tk.Canvas(dec_outer, bg=BG_PANEL, highlightthickness=0)
        sb = ttk.Scrollbar(dec_outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        self._dec_inner = tk.Frame(canvas, bg=BG_PANEL)
        self._dec_win = canvas.create_window((0, 0), window=self._dec_inner, anchor="nw")
        self._dec_inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(self._dec_win, width=e.width))
        self._btn_confirm = self.app._btn(parent, "✓  Confirm All & Write Files", self._confirm_all,
            bg=ACCENT, fg="#0a0f0a", font=UI_B, px=20, py=8, full=True)
        self._btn_confirm.pack(fill="x", padx=14, pady=(6, 12))
        self._btn_confirm.config(state="disabled")

    def _build_patch(self, parent):
        top = tk.Frame(parent, bg=BG_PANEL)
        top.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(top, text="Patch Editor", bg=BG_PANEL, fg=TEXT, font=UI_B).pack(side="left")
        tk.Label(top, text="paste a fragment — only changed lines get applied",
                 bg=BG_PANEL, fg=TEXT_MUTED, font=UI_SM).pack(side="left", padx=(8, 0))
        self._git_status_var = tk.StringVar(value="")
        self._git_label = tk.Label(top, textvariable=self._git_status_var, bg=BG_PANEL, fg=ACCENT, font=UI_SM)
        self._git_label.pack(side="right")
        sel = tk.Frame(parent, bg=BG_PANEL)
        sel.pack(fill="x", padx=14, pady=(0, 6))
        tk.Label(sel, text="Target file:", bg=BG_PANEL, fg=TEXT_DIM, font=UI_SM).pack(side="left")
        self._patch_file_var = tk.StringVar(value="— select a file —")
        tk.Label(sel, textvariable=self._patch_file_var, bg=BG_PANEL, fg=BLUE, font=UI_SM).pack(side="left", padx=(6, 0))
        self.app._btn(sel, "Browse", self._select_patch_target, bg=BG_CARD, fg=TEXT, px=10, py=3).pack(side="right")
        self._validate_var = tk.BooleanVar(value=True)
        tk.Checkbutton(sel, text="Validate after patch", variable=self._validate_var,
            bg=BG_PANEL, fg=TEXT_DIM, selectcolor=BG_CARD, activebackground=BG_PANEL,
            activeforeground=TEXT, font=UI_SM, relief="flat").pack(side="right", padx=(0, 12))
        split = tk.Frame(parent, bg=BG_PANEL)
        split.pack(fill="both", expand=True, padx=14, pady=(0, 6))
        lp = tk.Frame(split, bg=BG_PANEL)
        lp.pack(side="left", fill="both", expand=True, padx=(0, 4))
        tk.Label(lp, text="Paste new fragment:", bg=BG_PANEL, fg=TEXT_MUTED, font=UI_XS, anchor="w").pack(fill="x")
        pb = tk.Frame(lp, bg=BORDER, padx=1, pady=1)
        pb.pack(fill="both", expand=True)
        ip = tk.Frame(pb, bg=BG_INPUT)
        ip.pack(fill="both", expand=True)
        self._patch_input = tk.Text(ip, bg=BG_INPUT, fg=TEXT, font=MONO,
            relief="flat", borderwidth=0, wrap="none", insertbackground=BLUE,
            selectbackground="#264f78", padx=8, pady=6)
        self._patch_input.pack(fill="both", expand=True)
        rp = tk.Frame(split, bg=BG_PANEL)
        rp.pack(side="left", fill="both", expand=True, padx=(4, 0))
        tk.Label(rp, text="Diff preview:", bg=BG_PANEL, fg=TEXT_MUTED, font=UI_XS, anchor="w").pack(fill="x")
        db = tk.Frame(rp, bg=BORDER, padx=1, pady=1)
        db.pack(fill="both", expand=True)
        id_ = tk.Frame(db, bg=BG_INPUT)
        id_.pack(fill="both", expand=True)
        self._diff_text = tk.Text(id_, bg=BG_INPUT, fg=TEXT, font=MONO,
            relief="flat", borderwidth=0, state="disabled", wrap="none", padx=8, pady=6)
        self._diff_text.pack(fill="both", expand=True)
        self._diff_text.tag_config("add", foreground=ACCENT)
        self._diff_text.tag_config("rem", foreground=RED)
        self._diff_text.tag_config("hdr", foreground=BLUE)
        br = tk.Frame(parent, bg=BG_PANEL)
        br.pack(fill="x", padx=14, pady=(0, 6))
        self.app._btn(br, "👁  Preview Diff", self._preview_patch, bg=BG_CARD, fg=TEXT, px=14, py=6).pack(side="left", padx=(0, 8))
        self.app._btn(br, "✓  Apply Patch", self._apply_patch, bg=ACCENT, fg="#0a0f0a", font=UI_B, px=18, py=6).pack(side="left")
        self._val_frame = tk.Frame(parent, bg=BG_CARD, padx=12, pady=10)
        self._val_title = tk.Label(self._val_frame, text="", bg=BG_CARD, fg=AMBER, font=UI_B, anchor="w")
        self._val_title.pack(fill="x")
        self._val_errors = tk.Text(self._val_frame, bg=BG_CARD, fg=RED, font=MONO,
            relief="flat", borderwidth=0, height=6, state="disabled", padx=4, pady=4, wrap="word")
        self._val_errors.pack(fill="x")
        vbr = tk.Frame(self._val_frame, bg=BG_CARD)
        vbr.pack(fill="x", pady=(8, 0))
        self.app._btn(vbr, "↩  Revert Patch", self._revert_patch, bg=RED, fg="white", font=UI_B, px=14, py=6).pack(side="left", padx=(0, 8))
        self.app._btn(vbr, "✎  Keep & Fix Manually", self._ignore_validation, bg=BG_CARD, fg=TEXT_DIM, px=14, py=6).pack(side="left")

    def _build_deps(self, parent):
        top = tk.Frame(parent, bg=BG_PANEL)
        top.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(top, text="Dependencies & Environment", bg=BG_PANEL, fg=TEXT, font=UI_B).pack(side="left")
        self.app._btn(top, "🔍  Scan Last Integration", self._scan_deps, bg=BG_CARD, fg=TEXT, px=12, py=4).pack(side="right")
        tk.Label(parent, text="Detected dependencies:", bg=BG_PANEL, fg=TEXT_MUTED, font=UI_XS, anchor="w").pack(fill="x", padx=14, pady=(0, 2))
        df = tk.Frame(parent, bg=BG_CARD)
        df.pack(fill="x", padx=14, pady=(0, 10))
        self._deps_list = tk.Text(df, bg=BG_CARD, fg=TEXT, font=MONO,
            relief="flat", borderwidth=0, height=6, state="disabled", padx=8, pady=6)
        self._deps_list.pack(fill="x")
        self._deps_list.tag_config("ok", foreground=ACCENT)
        self._deps_list.tag_config("miss", foreground=AMBER)
        self._deps_list.tag_config("dim", foreground=TEXT_DIM)
        self.app._btn(parent, "⚡  Install Missing Packages", self._install_deps,
            bg=BLUE, fg="#0a0f14", font=UI_B, px=16, py=6, full=True).pack(fill="x", padx=14, pady=(0, 10))
        tk.Label(parent, text="Suggested .env variables (not written automatically):",
            bg=BG_PANEL, fg=TEXT_MUTED, font=UI_XS, anchor="w").pack(fill="x", padx=14, pady=(0, 2))
        ef = tk.Frame(parent, bg=BG_CARD)
        ef.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        self._env_text = tk.Text(ef, bg=BG_CARD, fg=ACCENT, font=MONO,
            relief="flat", borderwidth=0, state="disabled", padx=8, pady=6)
        self._env_text.pack(fill="both", expand=True)

    def _build_log(self, parent):
        top = tk.Frame(parent, bg=BG_PANEL)
        top.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(top, text="Activity Log", bg=BG_PANEL, fg=TEXT, font=UI_B).pack(side="left")
        self.app._btn(top, "✕ Clear", self._clear_log, bg=BG_CARD, fg=TEXT_DIM, px=10, py=4).pack(side="right")
        lo = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        lo.pack(fill="both", expand=True, padx=14, pady=(0, 14))
        inner = tk.Frame(lo, bg=BG_INPUT)
        inner.pack(fill="both", expand=True)
        sb = ttk.Scrollbar(inner, orient="vertical", style="Vertical.TScrollbar")
        sb.pack(side="right", fill="y")
        self._log_txt = tk.Text(inner, bg=BG_INPUT, fg=TEXT, font=MONO,
            relief="flat", borderwidth=0, state="disabled", wrap="none",
            yscrollcommand=sb.set, padx=10, pady=8)
        self._log_txt.pack(fill="both", expand=True)
        sb.config(command=self._log_txt.yview)
        self._log_txt.tag_config("ok",   foreground=ACCENT)
        self._log_txt.tag_config("err",  foreground=RED)
        self._log_txt.tag_config("warn", foreground=AMBER)
        self._log_txt.tag_config("info", foreground=BLUE)
        self._log_txt.tag_config("dim",  foreground=TEXT_DIM)

    def _choose_folder(self):
        folder = filedialog.askdirectory(title="Select Project Root")
        if folder:
            self._load_project(Path(folder))

    def _load_project(self, path):
        self._path_var.set(str(path))
        self.app._status(f"Scanning {path.name}...")
        self.frame.update_idletasks()
        try:
            self.state = backend.scan(path)
            backend.add_project(str(path))
            self._info["Type"].config(text=self.state.project_type.value)
            self._info["Files"].config(text=str(self.state.total_files))
            self._info["Dirs"].config(text=str(self.state.total_dirs))
            self._info["Git"].config(
                text="✓ Yes" if self.state.has_git else "✗ No",
                fg=ACCENT if self.state.has_git else TEXT_DIM)
            idx = self.notebook.index(self.frame)
            self.notebook.tab(idx, text=f"  {self.state.name}  ")
            self._aiconfig_text.delete("1.0", "end")
            if self.state.config.has_config:
                self._aiconfig_text.insert("1.0", self.state.config.raw_content)
                self._log("✓ .aiconfig loaded", "ok")
            else:
                self._aiconfig_text.insert("1.0",
                    f"Proyecto: {self.state.name}\nTipo: {self.state.project_type.value}\n"
                    f"Plataforma: \n\nReglas:\n# Ejemplo:\n# Componentes → src/components/\n# Hooks → src/hooks/\n")
                self._log("ℹ No .aiconfig found — template generated", "info")
            self._update_git_indicator()
            self._log(f"✓ Project: {path.name} | {self.state.project_type.value} | Git: {'Yes' if self.state.has_git else 'No'}", "ok")
            self.app._status(f"Project loaded: {self.state.name}")
        except Exception as e:
            self._log(f"✗ Scan error: {e}", "err")
            self.app._status(f"Error: {e}")

    def _save_aiconfig(self):
        if not self.state:
            messagebox.showwarning("No Project", "Select a project first.")
            return
        backend.save_aiconfig(self.state.root, self._aiconfig_text.get("1.0", "end").strip())
        self.state = backend.scan(self.state.root)
        self._log("✓ .aiconfig saved", "ok")
        self.app._status(".aiconfig saved.")

    def _generate_aiconfig(self):
        if not self.state:
            messagebox.showwarning("No Project", "Select a project first.")
            return
        template = (f"Proyecto: {self.state.name}\nTipo: {self.state.project_type.value}\n"
                    f"Plataforma: \n\nPROJECT STRUCTURE:\n{self.state.tree}\n\n"
                    f"Reglas:\n# Componentes → src/components/\n# Hooks → src/hooks/\n"
                    f"# Estilos → src/styles/\n# Config → raíz\n")
        self._aiconfig_text.delete("1.0", "end")
        self._aiconfig_text.insert("1.0", template)
        self._log("✓ .aiconfig template generated — edit and save", "info")

    def _browse_files(self):
        try:
            result = subprocess.run(["kdialog", "--getopenfilename", "--multiple", str(Path.home()), "*"],
                                    capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                for f in shlex.split(result.stdout.strip()):
                    self._add_file(Path(f))
        except Exception:
            for f in filedialog.askopenfilenames(title="Select files"):
                self._add_file(Path(f))

    def _add_file(self, path):
        if not path.exists() or path in self.queued_files:
            return
        self.queued_files.append(path)
        self._queue_list.insert("end", f"  {path.name}")
        self.app._status(f"{len(self.queued_files)} file(s) queued.")

    def _analyze_files(self):
        if not self.state:
            messagebox.showwarning("No Project", "Select a project first.")
            return
        if not self.queued_files:
            messagebox.showwarning("No Files", "Add files to the queue first.")
            return
        files = list(self.queued_files)
        self.queued_files.clear()
        self._queue_list.delete(0, "end")
        for w in self._dec_inner.winfo_children():
            w.destroy()
        self.pending_decisions.clear()
        self._btn_confirm.config(state="disabled")
        self._btn_analyze.config(state="disabled", text="⏳ Analyzing...")
        self.app._status(f"Analyzing {len(files)} file(s)...")
        def run():
            for f in files:
                decision = backend.analyze(f, self.state)
                result = {"file": f, "decision": decision}
                self.pending_decisions.append(result)
                self.frame.after(0, lambda r=result: self._add_decision_card(r))
            self.frame.after(0, self._on_analyze_done)
        threading.Thread(target=run, daemon=True).start()

    def _on_analyze_done(self):
        self._btn_analyze.config(state="normal", text="⚡  Analyze")
        self._btn_confirm.config(state="normal")
        self.app._status(f"Analysis done. {len(self.pending_decisions)} decision(s) ready.")
        self._log(f"✓ Analyzed {len(self.pending_decisions)} file(s)", "ok")

    def _add_decision_card(self, result):
        file = result["file"]
        dec  = result["decision"]
        conf_color = {
            backend.ConfidenceLevel.HIGH:   ACCENT,
            backend.ConfidenceLevel.MEDIUM: AMBER,
            backend.ConfidenceLevel.LOW:    RED,
        }.get(dec.confidence, RED)
        card = tk.Frame(self._dec_inner, bg=BG_CARD, padx=12, pady=8)
        card.pack(fill="x", pady=(0, 4), padx=2)
        hdr = tk.Frame(card, bg=BG_CARD)
        hdr.pack(fill="x")
        tk.Label(hdr, text="●", bg=BG_CARD, fg=conf_color, font=UI).pack(side="left", padx=(0, 6))
        tk.Label(hdr, text=file.name, bg=BG_CARD, fg=TEXT, font=UI_B).pack(side="left")
        tk.Label(hdr, text=f"({dec.confidence.value})", bg=BG_CARD, fg=conf_color, font=UI_SM).pack(side="left", padx=(6, 0))
        dr = tk.Frame(card, bg=BG_CARD)
        dr.pack(fill="x", pady=(4, 0))
        tk.Label(dr, text="→", bg=BG_CARD, fg=TEXT_DIM, font=UI).pack(side="left", padx=(0, 6))
        dest_var = tk.StringVar(value=dec.destination)
        tk.Entry(dr, textvariable=dest_var, bg=BG_INPUT, fg=BLUE, font=MONO,
                 relief="flat", insertbackground=BLUE, selectbackground="#1e3a5f").pack(side="left", fill="x", expand=True)
        tk.Label(card, text=dec.reason, bg=BG_CARD, fg=TEXT_DIM,
                 font=UI_SM, anchor="w", wraplength=500).pack(fill="x", pady=(4, 0))
        result["dest_var"] = dest_var

    def _confirm_all(self):
        if not self.pending_decisions or not self.state:
            return
        if not messagebox.askyesno("Confirm",
            f"Write {len(self.pending_decisions)} file(s) to {self.state.name}?\nBackups created for existing files."):
            return
        self._btn_confirm.config(state="disabled", text="⏳ Writing...")
        self._mod_nb.select(3)
        def run():
            written = []
            for result in self.pending_decisions:
                file = result["file"]
                dest_var = result.get("dest_var")
                dest = dest_var.get().strip() if dest_var else result["decision"].destination
                result["decision"].destination = dest
                wr = backend.write_file(result["decision"], self.state.root)
                written.append(file)
                if wr.status == backend.WriteStatus.SUCCESS:
                    msg = f"✓ {wr.message}"
                    if wr.backup:
                        msg += " (Git)" if wr.backup.used_git else " (.afi_backups/)"
                    if wr.created_dirs:
                        msg += f" | created: {', '.join(wr.created_dirs)}"
                    tag = "ok"
                else:
                    msg, tag = f"✗ {wr.message}", "err"
                self.frame.after(0, lambda m=msg, t=tag: self._log(m, t))
            self._last_integrated_files = written
            self.frame.after(0, self._on_confirm_done)
        threading.Thread(target=run, daemon=True).start()

    def _on_confirm_done(self):
        self._btn_confirm.config(state="normal", text="✓  Confirm All & Write Files")
        self.app._status(f"Done! Files written to {self.state.name}.")
        self.state = backend.scan(self.state.root)
        for w in self._dec_inner.winfo_children():
            w.destroy()
        self.pending_decisions.clear()
        self._btn_confirm.config(state="disabled")
        self._mod_nb.select(2)
        self._scan_deps()

    def _update_git_indicator(self):
        if self.state and self.state.has_git:
            self._git_status_var.set("● Git — checkpoint enabled")
            self._git_label.config(fg=ACCENT)
        else:
            self._git_status_var.set("○ No Git — using .afi_backups/")
            self._git_label.config(fg=AMBER)

    def _select_patch_target(self):
        if not self.state:
            messagebox.showwarning("No Project", "Select a project first.")
            return
        try:
            result = subprocess.run(["kdialog", "--getopenfilename", str(self.state.root), "*"],
                                    capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                self._patch_target = Path(result.stdout.strip())
                self._patch_file_var.set(self._patch_target.name)
        except Exception:
            f = filedialog.askopenfilename(title="Select file to patch", initialdir=str(self.state.root))
            if f:
                self._patch_target = Path(f)
                self._patch_file_var.set(self._patch_target.name)

    def _preview_patch(self):
        if not self._patch_target:
            messagebox.showwarning("No File", "Select a target file first.")
            return
        fragment = self._patch_input.get("1.0", "end").strip()
        if not fragment:
            messagebox.showwarning("Empty", "Paste a code fragment first.")
            return
        diff = backend.preview_patch(self._patch_target, fragment)
        self._diff_text.config(state="normal")
        self._diff_text.delete("1.0", "end")
        for line in diff.splitlines(keepends=True):
            if line.startswith('+') and not line.startswith('+++'):
                self._diff_text.insert("end", line, "add")
            elif line.startswith('-') and not line.startswith('---'):
                self._diff_text.insert("end", line, "rem")
            elif line.startswith('@@'):
                self._diff_text.insert("end", line, "hdr")
            else:
                self._diff_text.insert("end", line)
        self._diff_text.config(state="disabled")

    def _apply_patch(self):
        if not self._patch_target or not self.state:
            messagebox.showwarning("No File", "Select a target file first.")
            return
        fragment = self._patch_input.get("1.0", "end").strip()
        if not fragment:
            messagebox.showwarning("Empty", "Paste a code fragment first.")
            return
        git_msg = ("A Git checkpoint will be created before applying.\nYou can revert instantly if validation fails."
                   if self.state.has_git else "A backup will be saved to .afi_backups/ before applying.")
        if not messagebox.askyesno("Confirm Patch", f"Apply patch to {self._patch_target.name}?\n\n{git_msg}"):
            return
        self._val_frame.pack_forget()
        self._mod_nb.select(3)
        self._log("⚡ Applying patch...", "info")
        validate = self._validate_var.get()
        def run():
            outcome = backend.apply_patch(
                target_file=self._patch_target,
                new_fragment=fragment,
                project_root=self.state.root,
                state=self.state if validate else None,
                validate_after=validate,
            )
            self._last_patch_outcome = outcome
            self.frame.after(0, lambda: self._on_patch_done(outcome))
        threading.Thread(target=run, daemon=True).start()

    def _on_patch_done(self, outcome):
        pr = outcome.patch_result
        self._mod_nb.select(1)
        if not pr.success:
            self._log(f"✗ {pr.message}", "err")
            self.app._status(f"Patch failed: {pr.message}")
            return
        self._log(f"✓ {pr.message}", "ok")
        if outcome.git_checkpoint:
            self._log(f"  Git checkpoint: {outcome.git_checkpoint[:8]}", "dim")
        elif pr.backup:
            self._log("  Backup: .afi_backups/", "dim")
        if outcome.validation is not None:
            val = outcome.validation
            if val.success:
                self._log(f"✓ Validation passed — {val.command_used}", "ok")
                self.app._status("Patch applied and validated successfully.")
                self._val_frame.pack_forget()
            else:
                self._log(f"✗ Validation failed — {val.error_count} error(s)", "err")
                self._log(f"  Command: {val.command_used}", "dim")
                for e in val.errors[:5]:
                    line_str = f":{e.line}" if e.line else ""
                    self._log(f"  {e.file}{line_str} — {e.message}", "err")
                self._val_title.config(text=f"⚠ {val.error_count} error(s) detected after patch — what do you want to do?")
                self._val_errors.config(state="normal")
                self._val_errors.delete("1.0", "end")
                for e in val.errors:
                    line_str = f" (line {e.line})" if e.line else ""
                    self._val_errors.insert("end", f"• {e.file}{line_str}\n  {e.message}\n\n")
                self._val_errors.config(state="disabled")
                self._val_frame.pack(fill="x", padx=14, pady=(0, 12))
                self.app._status(f"⚠ {val.error_count} error(s) after patch — revert or fix manually.")
        else:
            self.app._status(f"Patch applied — {pr.lines_changed} line(s) changed.")
        self._patch_input.delete("1.0", "end")
        self._diff_text.config(state="normal")
        self._diff_text.delete("1.0", "end")
        self._diff_text.config(state="disabled")

    def _revert_patch(self):
        if not self._last_patch_outcome or not self.state:
            return
        if not messagebox.askyesno("Revert Patch",
            "Revert the project to the state before this patch?\nThis cannot be undone."):
            return
        success, msg = backend.revert_patch(self._last_patch_outcome, self.state.root)
        self._mod_nb.select(3)
        if success:
            self._log(f"✓ {msg}", "ok")
            self.app._status("Patch reverted successfully.")
            self._val_frame.pack_forget()
            self._last_patch_outcome = None
        else:
            self._log(f"✗ {msg}", "err")
            self.app._status(f"Revert failed: {msg}")

    def _ignore_validation(self):
        self._val_frame.pack_forget()
        self._log("⚠ Keeping patch despite errors — fix manually.", "warn")
        self.app._status("Patch kept — fix errors manually.")
        self._last_patch_outcome = None

    def _scan_deps(self):
        if not self.state or not self._last_integrated_files:
            self._log("ℹ No files integrated yet in this session.", "info")
            return
        all_deps, all_env = [], []
        for f in self._last_integrated_files:
            if not f.exists():
                continue
            try:
                content = f.read_text(encoding='utf-8', errors='replace')
            except Exception:
                continue
            deps, env_vars = backend.analyze_dependencies(f, content, self.state.root)
            all_deps.extend(deps)
            all_env.extend(env_vars)
        self._detected_deps = all_deps
        self._deps_list.config(state="normal")
        self._deps_list.delete("1.0", "end")
        if all_deps:
            for d in all_deps:
                status = "✓" if d.is_installed else "⚠"
                tag    = "ok" if d.is_installed else "miss"
                self._deps_list.insert("end", f"{status} [{d.package_manager}] {d.name}\n", tag)
        else:
            self._deps_list.insert("end", "No new dependencies detected.", "dim")
        self._deps_list.config(state="disabled")
        self._env_text.config(state="normal")
        self._env_text.delete("1.0", "end")
        if all_env:
            self._env_text.insert("end", "# Add these to your .env file:\n\n")
            for e in all_env:
                self._env_text.insert("end", f"{e.name}={e.example_value}\n")
        else:
            self._env_text.insert("end", "# No environment variables detected.")
        self._env_text.config(state="disabled")

    def _install_deps(self):
        if not self.state or not self._detected_deps:
            messagebox.showwarning("No Deps", "Scan dependencies first.")
            return
        missing = [d for d in self._detected_deps if not d.is_installed]
        if not missing:
            messagebox.showinfo("All Good", "All dependencies are already installed!")
            return
        names = "\n".join(f"  • {d.name} ({d.package_manager})" for d in missing)
        if not messagebox.askyesno("Install", f"Install these packages?\n\n{names}"):
            return
        self._mod_nb.select(3)
        self._log("⚡ Installing dependencies...", "info")
        def run():
            logs = backend.install_dependencies(self._detected_deps, self.state.root)
            for msg in logs:
                tag = "ok" if msg.startswith("✓") else "warn" if msg.startswith("⚠") else "err"
                self.frame.after(0, lambda m=msg, t=tag: self._log(m, t))
            self.frame.after(0, lambda: self.app._status("Done."))
        threading.Thread(target=run, daemon=True).start()

    def _log(self, msg, tag=""):
        self._log_txt.config(state="normal")
        self._log_txt.insert("end", msg + "\n", tag)
        self._log_txt.see("end")
        self._log_txt.config(state="disabled")

    def _clear_log(self):
        self._log_txt.config(state="normal")
        self._log_txt.delete("1.0", "end")
        self._log_txt.config(state="disabled")

    def _slabel(self, parent, text):
        tk.Label(parent, text=text, bg=BG_PANEL, fg=TEXT_MUTED,
                 font=UI_XS, anchor="w").pack(fill="x", padx=10, pady=(12, 4))

    def _divider(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=10, pady=4)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI File Integrator v3")
        self.geometry("1160x760")
        self.minsize(900, 600)
        self.configure(bg=BG)
        self._apply_styles()
        self._build_ui()
        self._project_tabs = []
        self._load_saved_projects()

    def _apply_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TFrame", background=BG)
        s.configure("TNotebook", background=BG, borderwidth=0, tabmargins=0)
        s.configure("TNotebook.Tab", background=BG_CARD, foreground=TEXT_DIM,
                    font=UI, padding=(12, 7), borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", BG_PANEL)], foreground=[("selected", BLUE)])
        s.configure("Inner.TNotebook", background=BG_PANEL, borderwidth=0)
        s.configure("Inner.TNotebook.Tab", background=BG_CARD, foreground=TEXT_DIM,
                    font=UI_SM, padding=(10, 5), borderwidth=0)
        s.map("Inner.TNotebook.Tab", background=[("selected", BG_PANEL)], foreground=[("selected", ACCENT)])
        s.configure("Vertical.TScrollbar", background=BG_CARD,
                    troughcolor=BG_INPUT, borderwidth=0, arrowcolor=TEXT_DIM)

    def _build_ui(self):
        self._build_header()
        self._nb = ttk.Notebook(self, style="TNotebook")
        self._nb.pack(fill="both", expand=True, padx=12, pady=(0, 4))
        tb = tk.Frame(self, bg=BG, height=28)
        tb.pack(fill="x", padx=12)
        self._btn(tb, "+ New Project", self._new_tab, bg=BG_CARD, fg=TEXT_DIM, px=12, py=3).pack(side="left")
        self._btn(tb, "✕ Close Tab", self._close_tab, bg=BG_CARD, fg=TEXT_DIM, px=12, py=3).pack(side="left", padx=(4, 0))
        self._build_statusbar()

    def _build_header(self):
        hdr = tk.Frame(self, bg=BG_PANEL, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="◈", bg=BG_PANEL, fg=ACCENT, font=("Cantarell", 18)).pack(side="left", padx=(16, 8))
        tk.Label(hdr, text="AI File Integrator", bg=BG_PANEL, fg=TEXT, font=UI_LG).pack(side="left")
        tk.Label(hdr, text="v3 — local", bg=BG_PANEL, fg=TEXT_MUTED, font=UI_SM).pack(side="left", padx=(8, 0), anchor="s", pady=(0, 4))
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

    def _build_statusbar(self):
        bar = tk.Frame(self, bg=BG_PANEL, height=26)
        bar.pack(fill="x", side="bottom")
        bar.pack_propagate(False)
        tk.Frame(bar, bg=BORDER, height=1).pack(fill="x", side="top")
        self._status_var = tk.StringVar(value="Ready — open a project to start.")
        tk.Label(bar, textvariable=self._status_var, bg=BG_PANEL, fg=TEXT_DIM,
                 font=UI_SM, anchor="w", padx=14).pack(side="left", fill="y")

    def _status(self, msg):
        self._status_var.set(msg)

    def _new_tab(self, path=None):
        tab = ProjectTab(self, self._nb, path)
        self._project_tabs.append(tab)
        self._nb.select(tab.frame)

    def _close_tab(self):
        if not self._project_tabs:
            return
        idx = self._nb.index("current")
        self._nb.forget(idx)
        if idx < len(self._project_tabs):
            self._project_tabs.pop(idx)

    def _load_saved_projects(self):
        projects = backend.get_projects()
        if projects:
            for p in projects[:3]:
                path = Path(p)
                if path.exists():
                    self._new_tab(path)
        if not self._project_tabs:
            self._new_tab()

    def _btn(self, parent, text, cmd, bg=BG_CARD, fg=TEXT, font=None, px=12, py=6, full=False):
        b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, font=font or UI,
                      relief="flat", borderwidth=0, padx=px, pady=py, cursor="hand2",
                      activebackground=self._lighten(bg), activeforeground=fg)
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


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
