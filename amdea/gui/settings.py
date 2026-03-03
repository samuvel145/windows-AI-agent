import tkinter as tk
from tkinter import ttk, messagebox
import os
import json
import pathlib
from amdea import config
from amdea.security import keystore
from amdea.memory import custom_commands, database

class SettingsWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AMDEA Settings")
        self.root.geometry("600x500")
        self.root.resizable(False, False)
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self._setup_api_tab()
        self._setup_safety_tab()
        self._setup_commands_tab()
        self._setup_logs_tab()
        
        # Bottom Buttons
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=10, pady=10)
        ttk.Button(btn_frame, text="Close", command=self.root.destroy).pack(side=tk.RIGHT)

    def _setup_api_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="API Keys")
        
        # API Keys Section
        ttk.Label(tab, text="AI Services Layout:", font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=(10, 0), padx=10)
        
        for service in ["DEEPGRAM", "GROQ", "CARTESIA"]:
            frame = ttk.Frame(tab, padding=5)
            frame.pack(fill=tk.X, padx=10)
            ttk.Label(frame, text=f"{service} API Key:").pack(side=tk.LEFT)
            entry = ttk.Entry(frame, show="*")
            entry.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)
            setattr(self, f"{service.lower()}_entry", entry)
            
            # Show status
            has_key = "Set" if keystore.get_api_key(service) else "Not Set"
            ttk.Label(frame, text=f"({has_key})").pack(side=tk.RIGHT)

        ttk.Button(tab, text="Save All Keys", command=self.save_all_keys).pack(anchor=tk.E, padx=20, pady=10)
        
        ttk.Separator(tab, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)
        
        # SMTP Section
        ttk.Label(tab, text="SMTP Configuration:", font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, padx=10)
        smtp_frame = ttk.Frame(tab, padding=10)
        smtp_frame.pack(fill=tk.X)
        
        self.smtp_fields = {}
        for i, field in enumerate(["host", "port", "user", "password", "sender"]):
            ttk.Label(smtp_frame, text=field.capitalize() + ":").grid(row=i, column=0, sticky=tk.W)
            entry = ttk.Entry(smtp_frame)
            if field == "password": entry.config(show="*")
            entry.grid(row=i, column=1, sticky=tk.EW, padx=5, pady=2)
            self.smtp_fields[field] = entry
            
        smtp_frame.columnconfigure(1, weight=1)
        ttk.Button(tab, text="Save SMTP Config", command=self.save_smtp).pack(anchor=tk.E, padx=20)

    def _setup_safety_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Safety")
        
        self.safe_mode_var = tk.BooleanVar(value=(os.getenv("AMDEA_SAFE_MODE") == "true"))
        ttk.Checkbutton(tab, text="Enable Safe Demo Mode (Blocks destructive actions)", 
                        variable=self.safe_mode_var, command=self.toggle_safe_mode).pack(anchor=tk.W, pady=20, padx=20)
        
        ttk.Label(tab, text="Allowed Directories (Roots):", font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, padx=10)
        list_frame = ttk.Frame(tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        self.roots_listbox = tk.Listbox(list_frame)
        self.roots_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        sb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.roots_listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.roots_listbox.config(yscrollcommand=sb.set)
        
        for root in config.ALLOWED_ROOTS:
            self.roots_listbox.insert(tk.END, str(root))

    def _setup_commands_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Shortcuts")
        
        ttk.Label(tab, text="Custom Voice Commands (Macros):", font=("TkDefaultFont", 10, "bold")).pack(anchor=tk.W, pady=10, padx=10)
        
        list_frame = ttk.Frame(tab)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)
        
        self.cmd_listbox = tk.Listbox(list_frame)
        self.cmd_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        ttk.Button(btn_frame, text="Delete Selected", command=self.delete_cmd).pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Refresh", command=self.refresh_cmds).pack(side=tk.RIGHT)
        
        self.refresh_cmds()

    def _setup_logs_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Logs")
        
        self.log_text = tk.Text(tab, state=tk.DISABLED, wrap=tk.NONE)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(btn_frame, text="Refresh Logs", command=self.refresh_logs).pack(side=tk.LEFT)
        
        self.refresh_logs()

    def save_all_keys(self):
        updated = []
        for service in ["DEEPGRAM", "GROQ", "CARTESIA"]:
            entry = getattr(self, f"{service.lower()}_entry")
            key = entry.get().strip()
            if key:
                keystore.store_api_key(service, key)
                updated.append(service)
                entry.delete(0, tk.END)
        
        if updated:
            messagebox.showinfo("Success", f"Updated keys for: {', '.join(updated)}")
        else:
            messagebox.showwarning("No Input", "Please enter at least one API key to update.")

    def save_smtp(self):
        data = {k: v.get().strip() for k, v in self.smtp_fields.items()}
        if all(data.values()):
            keystore.store_smtp_config(**data)
            messagebox.showinfo("Success", "SMTP Configuration saved.")

    def toggle_safe_mode(self):
        os.environ["AMDEA_SAFE_MODE"] = "true" if self.safe_mode_var.get() else "false"

    def refresh_cmds(self):
        self.cmd_listbox.delete(0, tk.END)
        cmds = custom_commands.list_commands()
        for c in cmds:
            self.cmd_listbox.insert(tk.END, f"{c['trigger_phrase']} ({c['use_count']} uses)")

    def delete_cmd(self):
        sel = self.cmd_listbox.curselection()
        if sel:
            phrase = self.cmd_listbox.get(sel).split(" (")[0]
            custom_commands.delete_command(phrase)
            self.refresh_cmds()

    def refresh_logs(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete('1.0', tk.END)
        
        conn = database.get_connection()
        logs = conn.execute("SELECT timestamp, action_type, outcome FROM action_log ORDER BY timestamp DESC LIMIT 50").fetchall()
        for ts, action, outcome in logs:
            self.log_text.insert(tk.END, f"[{ts}] {action:15} | {outcome}\n")
            
        self.log_text.config(state=tk.DISABLED)

    def run(self):
        self.root.mainloop()

def show_settings():
    SettingsWindow().run()
