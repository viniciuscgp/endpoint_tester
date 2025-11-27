"""
EndpointTester: pequena ferramenta Tkinter para testar endpoints HTTP.
- Permite definir nome, URL, metodo, headers e corpo.
- Chama curl internamente e persiste configuracoes em endpoints.json.
"""

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import tkinter.font as tkfont


def _resolve_base_dir() -> Path:
    """
    Usa a pasta do executavel/script como base para ler/gravar configuracoes.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    if "__file__" in globals():
        return Path(__file__).resolve().parent
    return Path.cwd()


BASE_DIR = _resolve_base_dir()
DATA_FILE = BASE_DIR / "endpoints.json"
UI_STATE_FILE = BASE_DIR / "ui_state.json"
DEFAULT_METHOD = "GET"
METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class EndpointTester(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("EndpointTester")
        self.geometry("1100x750")
        self._configure_style()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.name_var = tk.StringVar()
        self.url_var = tk.StringVar()
        self.method_var = tk.StringVar(value=DEFAULT_METHOD)
        self.status_var = tk.StringVar(value="Pronto.")

        self.endpoints: list[dict] = []
        self.ui_state: dict = {}
        self._load_ui_state()
        self._build_ui()
        self.load_endpoints()
        self.apply_ui_state()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TLabel", padding=(2, 2))
        style.configure("TButton", padding=(10, 6))
        style.configure("Section.TLabelframe", padding=10)
        style.configure("Section.TLabelframe.Label", padding=(6, 0))
        style.configure("Card.TFrame", relief="groove", borderwidth=1, padding=10)
        style.configure("Toolbar.TButton", padding=(4, 2))
        style.configure("LabelBtn.TButton", padding=(2, 1))

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)

        # Paned horizontal: lista (esquerda) e formulario (direita)
        self.main_panes = ttk.Panedwindow(root, orient="horizontal")
        self.main_panes.pack(fill="both", expand=True)

        # Lista de endpoints salvos (coluna esquerda)
        list_label = ttk.Frame(self.main_panes)
        ttk.Label(list_label, text="Endpoints salvos").pack(side="left")
        ttk.Button(
            list_label,
            text="+",
            width=2,
            style="LabelBtn.TButton",
            command=self.clear_form,
        ).pack(side="left", padx=(8, 2))
        ttk.Button(
            list_label,
            text="x",
            width=2,
            style="LabelBtn.TButton",
            command=self.delete_selected,
        ).pack(side="left")

        list_col = ttk.LabelFrame(
            self.main_panes,
            labelwidget=list_label,
            padding=10,
            style="Section.TLabelframe",
        )
        list_col.pack_propagate(False)
        list_col.config(width=260)

        list_container = ttk.Frame(list_col)
        list_container.pack(fill="both", expand=True)
        self.listbox = tk.Listbox(list_container, height=26, exportselection=False, width=28)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side="right", fill="y")
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.bind("<<ListboxSelect>>", self.on_select_endpoint)

        self.main_panes.add(list_col, weight=1)

        # Formulario principal (coluna direita)
        form = ttk.Frame(self.main_panes)
        self.main_panes.add(form, weight=3)

        self.header_font = self._make_font("headers")
        self.body_font = self._make_font("body")
        self.response_font = self._make_font("response")

        info_frame = ttk.LabelFrame(form, text="Identificacao e destino", padding=12, style="Section.TLabelframe")
        info_frame.pack(fill="x", pady=(0, 10))
        info_frame.columnconfigure(1, weight=1)
        info_frame.columnconfigure(3, weight=1)

        ttk.Label(info_frame, text="Nome").grid(row=0, column=0, sticky="w")
        ttk.Entry(info_frame, textvariable=self.name_var).grid(row=0, column=1, sticky="ew", padx=(6, 12))
        ttk.Label(info_frame, text="Metodo").grid(row=0, column=2, sticky="e")
        method_box = ttk.Combobox(
            info_frame,
            width=10,
            textvariable=self.method_var,
            values=METHODS,
            state="readonly",
        )
        method_box.grid(row=0, column=3, sticky="w")

        ttk.Label(info_frame, text="URL").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(info_frame, textvariable=self.url_var).grid(
            row=1,
            column=1,
            columnspan=3,
            sticky="ew",
            padx=(6, 0),
            pady=(8, 0),
        )

        button_row = ttk.Frame(form, padding=(0, 4))
        button_row.pack(fill="x", pady=(0, 8))
        ttk.Button(button_row, text="Salvar", command=self.save_endpoint).pack(side="left", padx=(0, 8))
        ttk.Button(button_row, text="Enviar", command=self.send_request).pack(side="left", padx=(0, 8))

        # Paned window vertical para permitir redimensionar altura das secoes
        self.right_panes = ttk.Panedwindow(form, orient="vertical")
        self.right_panes.pack(fill="both", expand=True)

        headers_label = ttk.Frame(self.right_panes)
        ttk.Label(headers_label, text="Headers (JSON ou linhas Chave: Valor)").pack(side="left")
        ttk.Button(
            headers_label,
            text="A+",
            width=2,
            style="LabelBtn.TButton",
            command=lambda: self._adjust_font(self.header_font, 1, "headers"),
        ).pack(side="left", padx=(6, 2))
        ttk.Button(
            headers_label,
            text="A-",
            width=2,
            style="LabelBtn.TButton",
            command=lambda: self._adjust_font(self.header_font, -1, "headers"),
        ).pack(side="left")
        ttk.Button(
            headers_label,
            text="Limpar",
            width=6,
            style="LabelBtn.TButton",
            command=self.clear_headers,
        ).pack(side="left", padx=(6, 0))
        headers_frame = ttk.LabelFrame(
            self.right_panes,
            labelwidget=headers_label,
            padding=12,
            style="Section.TLabelframe",
        )
        self.headers_text = ScrolledText(headers_frame, height=6, font=self.header_font)
        self.headers_text.pack(fill="both", expand=True)
        self.right_panes.add(headers_frame, weight=1)

        body_label = ttk.Frame(self.right_panes)
        ttk.Label(body_label, text="Body (enviado como --data-raw)").pack(side="left")
        ttk.Button(
            body_label,
            text="A+",
            width=2,
            style="LabelBtn.TButton",
            command=lambda: self._adjust_font(self.body_font, 1, "body"),
        ).pack(side="left", padx=(6, 2))
        ttk.Button(
            body_label,
            text="A-",
            width=2,
            style="LabelBtn.TButton",
            command=lambda: self._adjust_font(self.body_font, -1, "body"),
        ).pack(side="left")
        ttk.Button(
            body_label,
            text="Limpar",
            width=6,
            style="LabelBtn.TButton",
            command=self.clear_body,
        ).pack(side="left", padx=(6, 0))
        body_frame = ttk.LabelFrame(
            self.right_panes,
            labelwidget=body_label,
            padding=12,
            style="Section.TLabelframe",
        )
        self.body_text = ScrolledText(body_frame, height=8, font=self.body_font)
        self.body_text.pack(fill="both", expand=True)
        self.right_panes.add(body_frame, weight=2)

        response_label = ttk.Frame(self.right_panes)
        ttk.Label(response_label, text="Resposta / log").pack(side="left")
        ttk.Button(
            response_label,
            text="A+",
            width=2,
            style="LabelBtn.TButton",
            command=lambda: self._adjust_font(self.response_font, 1, "response"),
        ).pack(side="left", padx=(6, 2))
        ttk.Button(
            response_label,
            text="A-",
            width=2,
            style="LabelBtn.TButton",
            command=lambda: self._adjust_font(self.response_font, -1, "response"),
        ).pack(side="left")
        ttk.Button(
            response_label,
            text="Limpar",
            width=6,
            style="LabelBtn.TButton",
            command=self.clear_response,
        ).pack(side="left", padx=(6, 0))
        response_frame = ttk.LabelFrame(
            self.right_panes,
            labelwidget=response_label,
            padding=12,
            style="Section.TLabelframe",
        )
        self.response_box = ScrolledText(response_frame, height=10, font=self.response_font)
        self.response_box.pack(fill="both", expand=True)
        self.right_panes.add(response_frame, weight=3)

        self.right_panes.bind("<ButtonRelease-1>", self.on_pane_release)
        self.main_panes.bind("<ButtonRelease-1>", self.on_main_pane_release)

        status_bar = ttk.Label(form, textvariable=self.status_var, relief="sunken", anchor="w")
        status_bar.pack(fill="x", pady=(10, 0))

    def load_endpoints(self) -> None:
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                self.endpoints = data
        except FileNotFoundError:
            self.endpoints = []
        except json.JSONDecodeError:
            messagebox.showwarning("Aviso", "endpoints.json corrompido. Iniciando vazio.")
            self.endpoints = []

        self.refresh_listbox()

    def _load_ui_state(self) -> None:
        try:
            with open(UI_STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self.ui_state = data
        except FileNotFoundError:
            self.ui_state = {}
        except json.JSONDecodeError:
            self.ui_state = {}

    def persist_endpoints(self) -> None:
        tmp_path = DATA_FILE.with_suffix(DATA_FILE.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.endpoints, f, indent=2)
        os.replace(tmp_path, DATA_FILE)

    def persist_ui_state(self) -> None:
        tmp_path = UI_STATE_FILE.with_suffix(UI_STATE_FILE.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(self.ui_state, f, indent=2)
        os.replace(tmp_path, UI_STATE_FILE)

    def refresh_listbox(self, select_index: int | None = None) -> None:
        self.listbox.delete(0, tk.END)
        for ep in self.endpoints:
            self.listbox.insert(tk.END, ep.get("name", "<sem nome>"))

        if select_index is not None and 0 <= select_index < len(self.endpoints):
            self.listbox.selection_clear(0, tk.END)
            self.listbox.selection_set(select_index)
            self.listbox.activate(select_index)

    def on_select_endpoint(self, event: tk.Event) -> None:
        if not self.listbox.curselection():
            return
        idx = self.listbox.curselection()[0]
        try:
            ep = self.endpoints[idx]
        except IndexError:
            return

        self.name_var.set(ep.get("name", ""))
        self.url_var.set(ep.get("url", ""))
        self.method_var.set(ep.get("method", DEFAULT_METHOD))
        self.headers_text.delete("1.0", tk.END)
        self.headers_text.insert(tk.END, self._headers_to_text(ep.get("headers", {})))
        self.body_text.delete("1.0", tk.END)
        self.body_text.insert(tk.END, ep.get("body", ""))
        self._set_status(f"Carregado: {ep.get('name', '')}")

    def clear_form(self) -> None:
        self.listbox.selection_clear(0, tk.END)
        self.name_var.set("")
        self.url_var.set("")
        self.method_var.set(DEFAULT_METHOD)
        self.headers_text.delete("1.0", tk.END)
        self.body_text.delete("1.0", tk.END)
        self._set_status("Formulario limpo.")

    def clear_headers(self) -> None:
        self.headers_text.delete("1.0", tk.END)

    def clear_body(self) -> None:
        self.body_text.delete("1.0", tk.END)

    def delete_selected(self) -> None:
        if not self.listbox.curselection():
            self._set_status("Selecione um endpoint para remover.")
            return
        idx = self.listbox.curselection()[0]
        try:
            removed = self.endpoints.pop(idx)
        except IndexError:
            return
        self.persist_endpoints()
        self.refresh_listbox()
        self.clear_form()
        self._set_status(f"Removido: {removed.get('name', '')}")

    def clear_response(self) -> None:
        self.response_box.delete("1.0", tk.END)
        self._set_status("Resposta limpa.")

    def save_endpoint(self) -> None:
        try:
            payload = self._collect_form()
        except ValueError as exc:
            messagebox.showerror("Erro", str(exc))
            self._set_status(str(exc))
            return

        idx = self._upsert_endpoint(payload)
        self.persist_endpoints()
        self.refresh_listbox(select_index=idx)
        self._set_status("Endpoint salvo.")

    def send_request(self) -> None:
        try:
            payload = self._collect_form()
        except ValueError as exc:
            messagebox.showerror("Erro", str(exc))
            self._set_status(str(exc))
            return

        idx = self._upsert_endpoint(payload)
        self.persist_endpoints()
        self.refresh_listbox(select_index=idx)

        self._set_status("Enviando requisicao...")
        cmd, output, exit_code = self._run_curl(payload)

        formatted_output = self._format_response_text(output)

        self.response_box.delete("1.0", tk.END)
        self.response_box.insert(tk.END, f"$ {cmd}\n\n")
        self.response_box.insert(tk.END, formatted_output)

        if exit_code == 0:
            self._set_status("Requisicao concluida.")
        else:
            self._set_status(f"curl retornou codigo {exit_code}.")

    def _run_curl(self, payload: dict) -> tuple[str, str, int]:
        cmd_parts = ["curl", "-i", "-X", payload["method"]]
        for key, value in payload["headers"].items():
            cmd_parts.extend(["-H", f"{key}: {value}"])
        if payload["body"]:
            cmd_parts.extend(["--data-raw", payload["body"]])
        cmd_parts.append(payload["url"])

        display_cmd = " ".join(shlex.quote(part) for part in cmd_parts)

        try:
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                check=False,
            )
            output = result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            return display_cmd, output, result.returncode
        except FileNotFoundError:
            msg = "curl nao encontrado no sistema."
            messagebox.showerror("Erro", msg)
            return display_cmd, msg, 1

    def _collect_form(self) -> dict:
        name = self.name_var.get().strip()
        url = self.url_var.get().strip()
        method = self.method_var.get().strip().upper() or DEFAULT_METHOD
        headers_text = self.headers_text.get("1.0", tk.END).strip()
        body = self.body_text.get("1.0", tk.END).rstrip("\n")

        if not name:
            raise ValueError("Informe um nome para salvar o endpoint.")
        if not url:
            raise ValueError("Informe a URL.")

        headers = self._parse_headers(headers_text)
        return {
            "name": name,
            "url": url,
            "method": method if method in METHODS else DEFAULT_METHOD,
            "headers": headers,
            "body": body,
        }

    def _parse_headers(self, text: str) -> dict:
        if not text:
            return {}
        stripped = text.strip()
        if not stripped:
            return {}

        # Tenta JSON primeiro.
        try:
            data = json.loads(stripped)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except json.JSONDecodeError:
            pass

        headers = {}
        for line in stripped.splitlines():
            if not line.strip():
                continue
            if ":" not in line:
                raise ValueError(f"Linha de header invalida: {line}")
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()
        return headers

    def _headers_to_text(self, headers: dict) -> str:
        return "\n".join(f"{k}: {v}" for k, v in headers.items())

    def _upsert_endpoint(self, payload: dict) -> int:
        for idx, ep in enumerate(self.endpoints):
            if ep.get("name") == payload["name"]:
                self.endpoints[idx] = payload
                return idx
        self.endpoints.append(payload)
        return len(self.endpoints) - 1

    def _set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _format_response_text(self, raw: str) -> str:
        """
        Tenta separar headers e body; se body for JSON valido, retorna identado.
        """
        header, body = self._split_headers_body(raw)
        if body is None:
            pretty_full = self._try_pretty_json(raw)
            return pretty_full if pretty_full is not None else raw

        # Separa eventual stderr apendado no corpo
        body_main, suffix = self._split_stderr(body)
        pretty_body = self._try_pretty_json(body_main)
        if pretty_body is None:
            return raw

        formatted_body = pretty_body + suffix
        if header:
            return f"{header}\n\n{formatted_body}"
        return formatted_body

    def _split_headers_body(self, text: str) -> tuple[str | None, str | None]:
        """
        Retorna (headers, body) quando detectar formato HTTP; caso contrario (None, None).
        """
        if not text:
            return None, None
        sep = None
        if "\r\n\r\n" in text:
            sep = text.find("\r\n\r\n")
            header = text[:sep]
            body = text[sep + 4 :]
        elif "\n\n" in text:
            sep = text.find("\n\n")
            header = text[:sep]
            body = text[sep + 2 :]
        else:
            return None, None

        if not header.strip().startswith("HTTP/"):
            return None, None
        return header, body

    def _split_stderr(self, text: str) -> tuple[str, str]:
        """
        Se texto contem bloco [stderr], separa para nao quebrar parse de JSON.
        """
        marker = "\n[stderr]"
        idx = text.find(marker)
        if idx == -1:
            return text, ""
        return text[:idx].rstrip(), text[idx:]

    def _try_pretty_json(self, text: str | None) -> str | None:
        if text is None:
            return None
        candidate = text.strip()
        if not candidate:
            return text
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            return None
        return json.dumps(parsed, indent=2, ensure_ascii=False)

    def apply_ui_state(self) -> None:
        # Aplica geometria e tamanhos de sashes apos Tk calcular layouts
        geom = self.ui_state.get("geometry")
        if geom:
            self.geometry(geom)

        def _apply():
            sashes = self.ui_state.get("right_sashes")
            if sashes and hasattr(self, "right_panes"):
                try:
                    self.right_panes.update_idletasks()
                    expected = len(self.right_panes.panes()) - 1
                    for idx, pos in enumerate(sashes[: expected]):
                        self.right_panes.sashpos(idx, pos)
                except tk.TclError:
                    pass
            main_sash = self.ui_state.get("main_sash")
            if main_sash is not None and hasattr(self, "main_panes"):
                try:
                    self.main_panes.update_idletasks()
                    self.main_panes.sashpos(0, main_sash)
                except tk.TclError:
                    pass

        self.after(150, _apply)

    def save_ui_state(self) -> None:
        if not hasattr(self, "right_panes"):
            return
        try:
            self.right_panes.update_idletasks()
            num_sashes = len(self.right_panes.panes()) - 1
            sashes = [self.right_panes.sashpos(i) for i in range(num_sashes)]
            self.ui_state["right_sashes"] = sashes
            if hasattr(self, "main_panes"):
                self.main_panes.update_idletasks()
                if len(self.main_panes.panes()) > 1:
                    self.ui_state["main_sash"] = self.main_panes.sashpos(0)
            self.ui_state["geometry"] = self.winfo_geometry()
            self.ui_state["fonts"] = {
                "headers": self.header_font.cget("size"),
                "body": self.body_font.cget("size"),
                "response": self.response_font.cget("size"),
            }
            self.persist_ui_state()
        except tk.TclError:
            pass

    def on_pane_release(self, event: tk.Event) -> None:
        self.save_ui_state()

    def on_main_pane_release(self, event: tk.Event) -> None:
        self.save_ui_state()

    def on_close(self) -> None:
        self.save_ui_state()
        self.destroy()

    def _make_font(self, key: str) -> tkfont.Font:
        if "TkFixedFont" in tkfont.names():
            base = tkfont.nametofont("TkFixedFont")
        else:
            base = tkfont.Font(family="Courier New", size=10)
        size_override = self.ui_state.get("fonts", {}).get(key)
        font_obj = tkfont.Font(family=base.cget("family"), size=size_override or base.cget("size"))
        return font_obj

    def _adjust_font(self, font_obj: tkfont.Font, delta: int, key: str) -> None:
        new_size = max(6, font_obj.cget("size") + delta)
        font_obj.configure(size=new_size)
        fonts_state = self.ui_state.setdefault("fonts", {})
        fonts_state[key] = new_size
        self.save_ui_state()


if __name__ == "__main__":
    app = EndpointTester()
    app.mainloop()
