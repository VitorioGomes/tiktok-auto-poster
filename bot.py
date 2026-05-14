#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Postagem Automática no TikTok
Posta 1 vídeo por conta em múltiplas contas.
Cada pasta de conta deve ter um atalho .lnk para o Opera (com perfil já logado no TikTok).
"""

APP_VERSION = "1.0"
GITHUB_USER = "VitorioGomes"
GITHUB_REPO = "tiktok-auto-poster"

import sys
import json
import random
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import threading
import os
import shutil
import time
from pathlib import Path
from datetime import datetime

import pyperclip

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    WebDriverException,
)

# ─────────────────────────────────────────────
# Configurações
# ─────────────────────────────────────────────
DEFAULT_DESCRIPTIONS = [
    "Você crê em mim meu filho? #jesus #fé #deus #amém❤️😇🙌🙏🙏🙏❤️ #féemdeus",
]
TIKTOK_UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".flv", ".wmv", ".webm"}
UPLOAD_TIMEOUT = 240   # segundos máximos para upload
VERIFICATION_WAIT = 30  # segundos de espera antes de verificar


# ─────────────────────────────────────────────
# Logger thread-safe para tkinter
# ─────────────────────────────────────────────
class ColorLogger:
    def __init__(self, widget: scrolledtext.ScrolledText):
        self.widget = widget

    def log(self, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        icons = {"INFO": "·", "OK": "✓", "ERROR": "✗", "WARN": "⚠"}
        icon = icons.get(level, "·")
        line = f"[{ts}] {icon}  {message}\n"
        self.widget.after(0, self._write, line, level.lower())

    def _write(self, text: str, tag: str):
        self.widget.configure(state="normal")
        self.widget.insert(tk.END, text, tag)
        self.widget.configure(state="disabled")
        self.widget.see(tk.END)


# ─────────────────────────────────────────────
# Utilitários de sistema de arquivos
# ─────────────────────────────────────────────
def read_lnk(lnk_path: Path) -> dict:
    import win32com.client
    import re

    shell = win32com.client.Dispatch("WScript.Shell")
    sc = shell.CreateShortCut(str(lnk_path))
    exe = Path(sc.Targetpath)
    args = sc.Arguments or ""

    m_data = re.search(r'--user-data-dir[= ]"?([^"]+?)"?(?:\s|$)', args)
    m_prof = re.search(r'--profile-directory[= ]"?([^"]+?)"?(?:\s|$)', args)

    return {
        "exe": exe,
        "args": args,
        "user_data_dir": m_data.group(1).strip() if m_data else None,
        "profile_directory": m_prof.group(1).strip() if m_prof else None,
    }


def find_shortcut(folder: Path) -> Path | None:
    """Procura o primeiro .lnk na pasta da conta."""
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() == ".lnk" and f.is_file():
            return f
    return None


def get_videos(folder: Path) -> list[Path]:
    return sorted(
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    )


def scan_accounts(base_dir: Path) -> list[dict]:
    accounts = []
    for folder in sorted(base_dir.iterdir()):
        if not folder.is_dir() or folder.name.lower() == "postados":
            continue

        lnk = find_shortcut(folder)
        if not lnk:
            continue

        try:
            info = read_lnk(lnk)
        except Exception:
            continue

        if not info["exe"].exists():
            continue

        videos = get_videos(folder)
        if not videos:
            continue

        accounts.append({
            "name": folder.name,
            "path": folder,
            "lnk": lnk,
            "opera_exe": info["exe"],
            "user_data_dir": info["user_data_dir"],
            "profile_directory": info["profile_directory"],
            "extra_args": info["args"],
            "videos": videos,
        })
    return accounts


def scan_nichos(root: Path) -> list[str]:
    """Retorna nomes de todas as subpastas de `root` que parecem nichos (exceto 'postados')."""
    nichos = []
    if not root.exists():
        return nichos
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        if folder.name.lower() in ("postados", "__pycache__"):
            continue
        nichos.append(folder.name)
    return nichos


def move_to_posted(video: Path, posted_dir: Path) -> Path:
    dest = posted_dir / video.name
    if dest.exists():
        i = 1
        while dest.exists():
            dest = posted_dir / f"{video.stem}_{i}{video.suffix}"
            i += 1
    shutil.move(str(video), str(dest))
    return dest


# ─────────────────────────────────────────────
# Automação Selenium
# ─────────────────────────────────────────────
def _find_real_opera(opera_exe: Path) -> tuple[Path, str | None]:
    import re
    opera_dir = opera_exe.parent
    version_dirs = [
        d for d in opera_dir.iterdir()
        if d.is_dir() and re.match(r"\d+\.\d+\.\d+", d.name)
    ]
    if version_dirs:
        version_dirs.sort(key=lambda p: [int(x) for x in p.name.split(".")])
        latest = version_dirs[-1]
        real_exe = latest / "opera.exe"
        if real_exe.exists():
            major = latest.name.split(".")[0]
            return real_exe, major
    return opera_exe, None


def create_driver(account: dict) -> webdriver.Chrome:
    import re
    from webdriver_manager.chrome import ChromeDriverManager

    real_exe, major = _find_real_opera(account["opera_exe"])

    opts = ChromeOptions()
    opts.binary_location = str(real_exe)
    if account["user_data_dir"]:
        opts.add_argument(f'--user-data-dir={account["user_data_dir"]}')
    if account["profile_directory"]:
        opts.add_argument(f'--profile-directory={account["profile_directory"]}')
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_argument("--no-first-run")
    opts.add_argument("--disable-default-apps")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    last_err = None
    for attempt in range(2):
        try:
            svc = ChromeService(ChromeDriverManager(driver_version=major).install())
            return webdriver.Chrome(service=svc, options=opts)
        except Exception as e:
            last_err = e
            m = re.search(r"Current browser version is (\d+)\.\d+", str(e))
            if m and attempt == 0:
                major = m.group(1)
                continue
            break

    raise RuntimeError(f"Não foi possível iniciar o Opera.\nDetalhe: {last_err}") from last_err


def do_upload(driver: webdriver.Chrome, video: Path, wait: WebDriverWait):
    """Faz upload via input[type=file]."""
    inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
    if not inputs:
        for xpath in [
            "//*[contains(text(),'Selecionar vídeo')]",
            "//*[contains(text(),'Select video')]",
            "//*[contains(@class,'upload-btn')]",
        ]:
            els = driver.find_elements(By.XPATH, xpath)
            for el in els:
                if el.is_displayed():
                    el.click()
                    time.sleep(1)
                    break
        inputs = wait.until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'input[type="file"]'))
        )

    file_input = inputs[0]
    driver.execute_script(
        "arguments[0].style.cssText = 'display:block !important; visibility:visible !important;';",
        file_input,
    )
    file_input.send_keys(str(video.absolute()))


def wait_upload_done(driver: webdriver.Chrome, timeout: int) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            body = driver.find_element(By.TAG_NAME, "body").text.lower()
            if any(x in body for x in ["enviado", "uploaded", "upload completo"]):
                time.sleep(2)
                return True
            descs = driver.find_elements(
                By.CSS_SELECTOR,
                '[contenteditable="true"], [data-e2e="caption-input"]',
            )
            for d in descs:
                if d.is_displayed() and d.size.get("height", 0) > 30:
                    time.sleep(1)
                    return True
        except (StaleElementReferenceException, WebDriverException):
            pass
        time.sleep(3)
    return False


def fill_description(driver: webdriver.Chrome, description: str):
    """Limpa e preenche a descrição via área de transferência (suporte a emojis)."""
    selectors = [
        '[data-e2e="caption-input"]',
        'div[contenteditable="true"].public-DraftEditor-content',
        '.DraftEditor-editorContainer [contenteditable="true"]',
        '[contenteditable="true"]',
        'div[role="textbox"]',
    ]
    el = None
    for sel in selectors:
        candidates = driver.find_elements(By.CSS_SELECTOR, sel)
        for c in candidates:
            if c.is_displayed() and c.size.get("height", 0) > 20:
                el = c
                break
        if el:
            break

    if not el:
        raise NoSuchElementException("Campo de descrição não encontrado")

    el.click()
    time.sleep(0.4)
    el.send_keys(Keys.CONTROL + "a")
    time.sleep(0.2)
    el.send_keys(Keys.DELETE)
    time.sleep(0.2)
    driver.execute_script(
        """
        arguments[0].innerHTML = '';
        arguments[0].textContent = '';
        arguments[0].dispatchEvent(new Event('input', {bubbles:true}));
        """,
        el,
    )
    time.sleep(0.3)

    pyperclip.copy(description)
    el.send_keys(Keys.CONTROL + "v")
    time.sleep(1)


def click_show_more(driver: webdriver.Chrome) -> bool:
    for xpath in [
        "//*[contains(text(),'Exibir mais')]",
        "//*[contains(text(),'Show more')]",
        "//*[contains(text(),'More options')]",
    ]:
        els = driver.find_elements(By.XPATH, xpath)
        for el in els:
            if el.is_displayed():
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                time.sleep(0.3)
                try:
                    el.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", el)
                time.sleep(1)
                return True
    return False


def enable_ai_toggle(driver: webdriver.Chrome) -> bool:
    """Habilita o toggle 'Conteúdo gerado por IA'."""
    labels = driver.find_elements(
        By.XPATH,
        "//*[contains(text(),'Conteúdo gerado por IA') or contains(text(),'AI-generated content')]",
    )
    for label in labels:
        if not label.is_displayed():
            continue
        container = label
        for _ in range(7):
            try:
                container = container.find_element(By.XPATH, "..")
                toggles = container.find_elements(
                    By.CSS_SELECTOR,
                    'input[type="checkbox"], [role="switch"], button[role="switch"]',
                )
                for toggle in toggles:
                    if not toggle.is_displayed():
                        continue
                    aria = toggle.get_attribute("aria-checked") or ""
                    checked = toggle.get_attribute("checked") or ""
                    if aria.lower() != "true" and checked.lower() not in ("true", "checked"):
                        driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", toggle
                        )
                        time.sleep(0.3)
                        try:
                            toggle.click()
                        except Exception:
                            driver.execute_script("arguments[0].click();", toggle)
                        time.sleep(0.5)
                        return True
                    return True
            except Exception:
                break

    for sw in driver.find_elements(By.CSS_SELECTOR, '[role="switch"]'):
        if sw.is_displayed() and (sw.get_attribute("aria-checked") or "").lower() != "true":
            driver.execute_script("arguments[0].click();", sw)
            time.sleep(0.5)
            return True
    return False


def check_verifications(driver: webdriver.Chrome) -> str:
    try:
        body = driver.find_element(By.TAG_NAME, "body").text.lower()

        restriction_phrases = [
            "o conteúdo pode estar restrito",
            "content may be restricted",
            "violação", "violation",
            "restrição", "restriction",
            "não pode ser publicado", "cannot be published",
            "conteúdo problemático",
            "ver detalhes",
            "view details",
        ]
        for phrase in restriction_phrases:
            if phrase in body:
                return "restriction"

        if "nenhum problema encontrado" in body:
            return "ok"

        return "ok"
    except Exception:
        return "ok"


def click_publish(driver: webdriver.Chrome) -> bool:
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(1)

    for xpath in [
        "//button[contains(text(),'Publicar')]",
        "//button[normalize-space()='Publicar']",
        "//button[contains(text(),'Post')]",
        "//*[@data-e2e='post-btn']",
        "//button[contains(@class,'btn-post')]",
        "//input[@type='submit']",
    ]:
        for el in driver.find_elements(By.XPATH, xpath):
            if el.is_displayed() and el.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                time.sleep(0.5)
                try:
                    el.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", el)
                return True

    clicked = driver.execute_script("""
        var buttons = document.querySelectorAll('button');
        for (var b of buttons) {
            var txt = (b.innerText || b.textContent || '').trim();
            if ((txt === 'Publicar' || txt === 'Post') && b.offsetParent !== null) {
                b.scrollIntoView({block:'center'});
                b.click();
                return true;
            }
        }
        return false;
    """)
    return bool(clicked)


def do_replace(driver: webdriver.Chrome, video: Path) -> bool:
    """Clica em Substituir e faz upload do próximo vídeo."""
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)
    for xpath in ["//*[contains(text(),'Substituir')]", "//*[contains(text(),'Replace')]"]:
        for el in driver.find_elements(By.XPATH, xpath):
            if el.is_displayed():
                try:
                    el.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", el)
                time.sleep(2)
                break

    inputs = driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
    if inputs:
        driver.execute_script(
            "arguments[0].style.cssText = 'display:block !important;';", inputs[0]
        )
        inputs[0].send_keys(str(video.absolute()))
        time.sleep(3)
        return True
    return False


# ─────────────────────────────────────────────
# Classe principal de automação
# ─────────────────────────────────────────────
class TikTokBot:
    def __init__(self, nicho_dir: str, descriptions: list[str],
                 logger: ColorLogger, stop_event: threading.Event):
        self.base_dir = Path(nicho_dir)
        self.posted_dir = self.base_dir / "postados"
        self.descriptions = descriptions if descriptions else list(DEFAULT_DESCRIPTIONS)
        self.log = logger.log
        self.stop = stop_event
        self.posted_dir.mkdir(exist_ok=True)

    def _get_description(self) -> str:
        return random.choice(self.descriptions)

    def run(self):
        self.log(f"Nicho: {self.base_dir.name}")
        self.log(f"Pasta postados: {self.posted_dir}")
        self.log(f"Descrições disponíveis: {len(self.descriptions)}")

        accounts = scan_accounts(self.base_dir)
        if not accounts:
            self.log("Nenhuma conta encontrada!", "ERROR")
            self.log("Estrutura esperada: nicho/conta_X/atalho.lnk + videos.mp4", "INFO")
            return

        self.log(f"{len(accounts)} conta(s) encontrada(s):")
        for a in accounts:
            self.log(f"  → {a['name']}  ({len(a['videos'])} vídeo(s))  atalho: {a['lnk'].name}")

        ok_count = 0
        err_count = 0
        for i, acc in enumerate(accounts, 1):
            if self.stop.is_set():
                self.log("Automação interrompida pelo usuário.", "WARN")
                break
            self.log(f"\n{'─' * 45}")
            self.log(f"[{i}/{len(accounts)}]  Conta: {acc['name']}")
            if self._process(acc):
                ok_count += 1
            else:
                err_count += 1
            if i < len(accounts) and not self.stop.is_set():
                self.log("Pausa de 5s antes da próxima conta...")
                time.sleep(5)

        self.log(f"\n{'═' * 45}")
        level = "OK" if err_count == 0 else "WARN"
        self.log(f"CONCLUÍDO — {ok_count} publicado(s), {err_count} erro(s).", level)

    def _process(self, account: dict) -> bool:
        videos = list(account["videos"])
        driver = None
        try:
            self.log(f"Atalho: {account['lnk'].name}")
            self.log(f"Opera: {account['opera_exe']}")
            if account["user_data_dir"]:
                self.log(f"Perfil: {account['user_data_dir']}  [{account['profile_directory'] or 'Default'}]")
            driver = create_driver(account)
            wait = WebDriverWait(driver, 30)

            self.log("Navegando para TikTok Studio...")
            driver.get(TIKTOK_UPLOAD_URL)
            time.sleep(4)

            if "login" in driver.current_url.lower():
                self.log("TikTok não está logado nesta conta!", "ERROR")
                return False

            is_replacement = False

            for idx, video in enumerate(videos):
                if self.stop.is_set():
                    return False

                self.log(f"Vídeo [{idx+1}/{len(videos)}]: {video.name}")

                # ── Upload ou Substituição ──────────────────────
                if not is_replacement:
                    self.log("Fazendo upload...")
                    try:
                        do_upload(driver, video, wait)
                    except Exception as e:
                        self.log(f"Erro no upload: {e}", "ERROR")
                        return False
                else:
                    self.log("Substituindo vídeo...")
                    if not do_replace(driver, video):
                        self.log("Substituição falhou.", "ERROR")
                        return False

                # ── Aguarda processamento ───────────────────────
                self.log("Aguardando upload/processamento...")
                time.sleep(5)
                wait_upload_done(driver, UPLOAD_TIMEOUT)
                time.sleep(2)

                # ── Descrição ───────────────────────────────────
                desc = self._get_description()
                self.log(f"Descrição: {desc[:60]}{'...' if len(desc) > 60 else ''}")
                try:
                    fill_description(driver, desc)
                    self.log("Descrição OK.", "OK")
                except Exception as e:
                    self.log(f"Aviso na descrição: {e}", "WARN")

                # ── Scroll e opções ─────────────────────────────
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)

                if not is_replacement:
                    self.log("Clicando em 'Exibir mais'...")
                    if click_show_more(driver):
                        self.log("'Exibir mais' expandido.", "OK")
                    else:
                        self.log("'Exibir mais' não encontrado (pode já estar expandido).", "WARN")
                    time.sleep(0.5)

                self.log("Habilitando 'Conteúdo gerado por IA'...")
                if enable_ai_toggle(driver):
                    self.log("Toggle IA habilitado.", "OK")
                else:
                    self.log("Toggle IA: não encontrado ou já ativo.", "WARN")

                # ── Espera verificações ─────────────────────────
                self.log(f"Aguardando {VERIFICATION_WAIT}s para verificações de direitos...")
                for _ in range(VERIFICATION_WAIT // 5):
                    if self.stop.is_set():
                        return False
                    time.sleep(5)

                # ── Checa restrições ────────────────────────────
                self.log("Verificando restrições de direitos autorais e conteúdo...")
                status = check_verifications(driver)

                if status == "restriction":
                    self.log(f"Restrição detectada em: {video.name}", "WARN")
                    dest = move_to_posted(video, self.posted_dir)
                    self.log(f"Movido para postados: {dest.name}", "WARN")
                    is_replacement = True

                    if idx + 1 >= len(videos):
                        self.log("Sem mais vídeos disponíveis para esta conta.", "ERROR")
                        return False
                    self.log(f"Tentando próximo vídeo: {videos[idx+1].name}")
                    continue

                # ── Publica ─────────────────────────────────────
                self.log("Verificações OK. Publicando...")
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(0.5)

                if click_publish(driver):
                    self.log(f"Publicado com sucesso: {video.name}", "OK")
                    time.sleep(3)
                    dest = move_to_posted(video, self.posted_dir)
                    self.log(f"Movido para postados: {dest.name}", "OK")
                    try:
                        driver.close()
                    except Exception:
                        pass
                    time.sleep(1)
                    return True
                else:
                    self.log("Botão 'Publicar' não encontrado.", "ERROR")
                    return False

            self.log(f"Todos os vídeos de '{account['name']}' tiveram restrições.", "ERROR")
            return False

        except Exception as e:
            self.log(f"Erro inesperado em '{account['name']}': {e}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            return False
        finally:
            if driver:
                try:
                    driver.close()
                except Exception:
                    pass
                try:
                    driver.quit()
                except Exception:
                    pass


# ─────────────────────────────────────────────
# Verificação de atualização
# ─────────────────────────────────────────────
def checar_atualizacao(callback):
    """Verifica no GitHub se há versão mais nova. Chama callback(versao, url) se houver."""
    import urllib.request, threading

    def _check():
        try:
            url = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}/releases/latest"
            req = urllib.request.Request(url, headers={"User-Agent": "TikTokAutoPoster"})
            with urllib.request.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
            tag = data.get("tag_name", "").lstrip("v")
            download_url = data.get("html_url", "")
            if tag and tag != APP_VERSION:
                callback(tag, download_url)
        except Exception:
            pass

    threading.Thread(target=_check, daemon=True).start()


# ─────────────────────────────────────────────
# Interface gráfica (tkinter)
# ─────────────────────────────────────────────
class App(tk.Tk):
    # Paleta: navy profundo + âmbar (legendas) + azul (nicho)
    C = {
        "bg":        "#070c18",
        "panel":     "#0d1526",
        "input":     "#111e33",
        "border":    "#1a2d4a",
        "dim":       "#1e2f47",
        "text":      "#dce8f5",
        "muted":     "#4a6585",
        "blue":      "#4d9fff",
        "blue_sel":  "#0d2545",
        "amber":     "#ffb830",
        "amber_dk":  "#2a1800",
        "amber_sel": "#3a2600",
        "green":     "#00d084",
        "green_dk":  "#003d26",
        "red":       "#ff3f5e",
        "yellow":    "#ffd060",
    }
    _PLACEHOLDER = "Digite a legenda com hashtags..."

    def __init__(self):
        super().__init__()
        self.title("TikTok Auto Poster")
        self.geometry("1020x740")
        self.minsize(820, 600)
        self.configure(bg=self.C["bg"])
        self._stop_event = threading.Event()
        self._thread = None
        self._pending_nicho = ""
        self._current_nicho = ""
        self._nicho_descs: dict[str, list[str]] = {}
        self._build_ui()
        base = self._base_dir()
        self.dir_var.set(str(base))
        self._criar_estrutura(base)
        self._load_config()
        self._scan_nichos()
        checar_atualizacao(self._aviso_atualizacao)

    @staticmethod
    def _base_dir() -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
        return Path(__file__).parent

    def _config_path(self) -> Path:
        return self._base_dir() / "config.json"

    def _load_config(self):
        try:
            with open(self._config_path(), encoding="utf-8") as f:
                cfg = json.load(f)
            self._nicho_descs = cfg.get("nicho_descriptions", {})
            self._pending_nicho = cfg.get("last_nicho", "")
        except Exception:
            self._nicho_descs = {}

    def _save_config(self):
        if self._current_nicho:
            self._nicho_descs[self._current_nicho] = self._get_descriptions()
        cfg = {
            "nicho_descriptions": self._nicho_descs,
            "last_nicho": self._current_nicho,
        }
        try:
            with open(self._config_path(), "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _get_descriptions(self) -> list[str]:
        result = []
        for item in self.desc_listbox.get(0, tk.END):
            if " │ " in item:
                result.append(item.split(" │ ", 1)[1])
            else:
                result.append(item)
        return [d for d in result if d.strip()]

    def _set_descriptions(self, descs: list[str]):
        self.desc_listbox.delete(0, tk.END)
        for i, d in enumerate(descs):
            if d.strip():
                self.desc_listbox.insert(tk.END, f"{i+1:02d} │ {d.strip()}")

    def _renumber_descs(self):
        raw = self._get_descriptions()
        self.desc_listbox.delete(0, tk.END)
        for i, d in enumerate(raw):
            self.desc_listbox.insert(tk.END, f"{i+1:02d} │ {d}")

    def _scan_nichos(self):
        root = Path(self.dir_var.get().strip())
        nichos = scan_nichos(root)
        self.nicho_listbox.delete(0, tk.END)
        for n in nichos:
            self.nicho_listbox.insert(tk.END, f"  {n}")
        target = self._pending_nicho if self._pending_nicho in nichos else (nichos[0] if nichos else "")
        if target:
            idx = nichos.index(target)
            self.nicho_listbox.selection_set(idx)
            self.nicho_listbox.see(idx)
            self._current_nicho = target
            descs = self._nicho_descs.get(target, list(DEFAULT_DESCRIPTIONS))
            self._set_descriptions(descs)
        if not nichos:
            self._set_status("Nenhum nicho encontrado. Crie subpastas.", "yellow")

    @staticmethod
    def _criar_estrutura(base: Path):
        has_nicho = False
        try:
            for d in base.iterdir():
                if not d.is_dir() or d.name.lower() in ("postados", "__pycache__"):
                    continue
                for sub in d.iterdir():
                    if sub.is_dir() and sub.name.lower() != "postados" and find_shortcut(sub):
                        has_nicho = True
                        break
                if has_nicho:
                    break
        except Exception:
            pass

        if not has_nicho:
            for n in ["Nicho 1", "Nicho 2"]:
                nicho = base / n
                nicho.mkdir(exist_ok=True)
                (nicho / "postados").mkdir(exist_ok=True)
                for i in range(1, 6):
                    (nicho / f"conta{i}").mkdir(exist_ok=True)

    # ── Helpers de UI ──────────────────────────────────────────────
    @staticmethod
    def _hover(widget, on: str, off: str):
        widget.bind("<Enter>", lambda e: widget.config(bg=on))
        widget.bind("<Leave>", lambda e: widget.config(bg=off))

    def _card(self, parent, accent_color: str, **pack_kwargs) -> tk.Frame:
        """Cria um card com borda fina e barra accent vertical colorida."""
        outer = tk.Frame(parent, bg=self.C["border"], padx=1, pady=1)
        outer.pack(**pack_kwargs)
        body = tk.Frame(outer, bg=self.C["panel"])
        body.pack(fill=tk.BOTH, expand=True)
        tk.Frame(body, bg=accent_color, width=4).pack(side=tk.LEFT, fill=tk.Y)
        content = tk.Frame(body, bg=self.C["panel"], padx=14, pady=12)
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        return content

    def _section_label(self, parent, dot_color: str, title: str, subtitle: str = ""):
        row = tk.Frame(parent, bg=self.C["panel"])
        row.pack(fill=tk.X, pady=(0, 8))
        tk.Label(row, text="●", bg=self.C["panel"], fg=dot_color,
                 font=("Segoe UI", 7)).pack(side=tk.LEFT)
        tk.Label(row, text=f"  {title}", bg=self.C["panel"], fg=self.C["text"],
                 font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        if subtitle:
            tk.Label(row, text=f"  —  {subtitle}", bg=self.C["panel"], fg=self.C["muted"],
                     font=("Segoe UI", 8)).pack(side=tk.LEFT)

    def _listbox_in(self, parent, **kw) -> tk.Listbox:
        """Cria um Listbox com borda fina e scrollbar integrada."""
        wrap = tk.Frame(parent, bg=self.C["border"], padx=1, pady=1)
        wrap.pack(fill=tk.BOTH, expand=True)
        inner = tk.Frame(wrap, bg=self.C["input"])
        inner.pack(fill=tk.BOTH, expand=True)
        sb = tk.Scrollbar(inner, relief=tk.FLAT, bd=0,
                          bg=self.C["dim"], troughcolor=self.C["input"])
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        lb = tk.Listbox(inner, relief=tk.FLAT, bd=0, activestyle="none",
                        bg=self.C["input"], fg=self.C["text"],
                        yscrollcommand=sb.set, **kw)
        lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=6, pady=4)
        sb.config(command=lb.yview)
        return lb

    def _set_status(self, text: str, color_key: str = "muted"):
        clr = self.C.get(color_key, self.C["muted"])
        self._dot.config(fg=clr)
        self.lbl_status.config(text=f"  {text}", fg=clr)

    # ── Build UI ───────────────────────────────────────────────────
    def _build_ui(self):
        C = self.C

        # ═══ CABEÇALHO ════════════════════════════════════════════
        hdr = tk.Frame(self, bg=C["panel"], padx=24, pady=14)
        hdr.pack(fill=tk.X)

        left = tk.Frame(hdr, bg=C["panel"])
        left.pack(side=tk.LEFT)
        tk.Label(left, text="TikTok Auto Poster",
                 font=("Segoe UI", 18, "bold"), bg=C["panel"], fg=C["text"]).pack(anchor=tk.W)
        tk.Label(left, text="Postagem automática  ·  1 vídeo por conta",
                 font=("Segoe UI", 8), bg=C["panel"], fg=C["muted"]).pack(anchor=tk.W)

        badge = tk.Label(hdr, text=f" v{APP_VERSION} ",
                         font=("Segoe UI", 8, "bold"),
                         bg=C["blue_sel"], fg=C["blue"], padx=6, pady=3)
        badge.pack(side=tk.RIGHT, anchor=tk.N, pady=6)

        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        # ═══ PASTA RAIZ ═══════════════════════════════════════════
        row = tk.Frame(self, bg=C["bg"], padx=16, pady=10)
        row.pack(fill=tk.X)
        tk.Label(row, text="PASTA RAIZ", bg=C["bg"], fg=C["muted"],
                 font=("Segoe UI", 8, "bold")).pack(side=tk.LEFT, padx=(0, 10))

        self.dir_var = tk.StringVar()
        ef = tk.Frame(row, bg=C["border"], padx=1, pady=1)
        ef.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 8))
        tk.Entry(ef, textvariable=self.dir_var, font=("Consolas", 9),
                 bg=C["input"], fg=C["text"], insertbackground=C["text"],
                 relief=tk.FLAT, bd=5).pack(fill=tk.X)

        b1 = tk.Button(row, text="Procurar", command=self._browse,
                       bg=C["blue"], fg="white", relief=tk.FLAT,
                       font=("Segoe UI", 9), padx=14, pady=5, cursor="hand2")
        b1.pack(side=tk.LEFT, padx=(0, 4))
        self._hover(b1, "#6db5ff", C["blue"])

        b2 = tk.Button(row, text="↻", command=self._scan_nichos,
                       bg=C["panel"], fg=C["muted"], relief=tk.FLAT,
                       font=("Segoe UI", 12), padx=10, pady=5, cursor="hand2")
        b2.pack(side=tk.LEFT)
        self._hover(b2, C["border"], C["panel"])

        tk.Frame(self, bg=C["dim"], height=1).pack(fill=tk.X, padx=16)

        # ═══ NICHO + LEGENDAS ════════════════════════════════════
        mid = tk.Frame(self, bg=C["bg"], padx=12, pady=10)
        mid.pack(fill=tk.X)

        # ─── NICHO (esquerda) ─────────────────────────────────────
        nicho_content = self._card(mid, C["blue"],
                                   side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self._section_label(nicho_content, C["blue"], "NICHO")
        self.nicho_listbox = self._listbox_in(
            nicho_content,
            font=("Segoe UI", 10),
            selectbackground=C["blue_sel"], selectforeground=C["blue"],
            height=5, width=20,
        )
        self.nicho_listbox.bind("<<ListboxSelect>>", self._on_nicho_select)

        # ─── LEGENDAS (direita) ───────────────────────────────────
        desc_content = self._card(mid, C["amber"],
                                  side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._section_label(desc_content, C["amber"], "LEGENDA",
                            "o bot sorteia uma diferente a cada vídeo")

        self.desc_listbox = self._listbox_in(
            desc_content,
            font=("Consolas", 9),
            selectbackground=C["amber_sel"], selectforeground=C["amber"],
            height=4,
        )

        # Separador fino antes do campo de adicionar
        tk.Frame(desc_content, bg=C["dim"], height=1).pack(fill=tk.X, pady=(10, 0))

        add_row = tk.Frame(desc_content, bg=C["panel"])
        add_row.pack(fill=tk.X, pady=(8, 0))

        ef2 = tk.Frame(add_row, bg=C["border"], padx=1, pady=1)
        ef2.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 8))
        self.desc_entry = tk.Entry(
            ef2, font=("Consolas", 9),
            bg=C["input"], fg=C["muted"], insertbackground=C["text"],
            relief=tk.FLAT, bd=5,
        )
        self.desc_entry.pack(fill=tk.X)
        self.desc_entry.insert(0, self._PLACEHOLDER)
        self.desc_entry.bind("<FocusIn>",  self._ph_in)
        self.desc_entry.bind("<FocusOut>", self._ph_out)
        self.desc_entry.bind("<Return>", lambda e: self._desc_add())

        b_add = tk.Button(add_row, text="+ Adicionar", command=self._desc_add,
                          bg=C["amber_dk"], fg=C["amber"], relief=tk.FLAT,
                          font=("Segoe UI", 9, "bold"), padx=14, pady=5, cursor="hand2")
        b_add.pack(side=tk.LEFT, padx=(0, 4))
        self._hover(b_add, "#4a2e00", C["amber_dk"])

        b_rem = tk.Button(add_row, text="✕ Remover", command=self._desc_remove,
                          bg=C["panel"], fg=C["muted"], relief=tk.FLAT,
                          font=("Segoe UI", 9), padx=12, pady=5, cursor="hand2")
        b_rem.pack(side=tk.LEFT)
        self._hover(b_rem, C["border"], C["panel"])

        # ═══ BOTÕES ══════════════════════════════════════════════
        tk.Frame(self, bg=C["dim"], height=1).pack(fill=tk.X, padx=16)

        btns = tk.Frame(self, bg=C["bg"], padx=14, pady=10)
        btns.pack(fill=tk.X)

        self.btn_start = tk.Button(
            btns, text="▶   INICIAR POSTAGEM",
            command=self._start,
            font=("Segoe UI", 12, "bold"),
            bg=C["green"], fg=C["bg"], relief=tk.FLAT,
            padx=28, pady=12, cursor="hand2",
        )
        self.btn_start.pack(side=tk.LEFT, padx=(0, 8))
        self._hover(self.btn_start, "#00f09a", C["green"])

        self.btn_stop = tk.Button(
            btns, text="⬛  PARAR",
            command=self._stop,
            font=("Segoe UI", 11),
            bg=C["panel"], fg=C["muted"], relief=tk.FLAT,
            padx=18, pady=12, cursor="hand2", state=tk.DISABLED,
        )
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 8))

        b_clr = tk.Button(btns, text="Limpar logs", command=self._clear,
                          font=("Segoe UI", 9), bg=C["panel"], fg=C["muted"],
                          relief=tk.FLAT, padx=14, pady=12, cursor="hand2")
        b_clr.pack(side=tk.LEFT)
        self._hover(b_clr, C["border"], C["panel"])

        sf = tk.Frame(btns, bg=C["bg"])
        sf.pack(side=tk.LEFT, padx=20)
        self._dot = tk.Label(sf, text="●", bg=C["bg"], fg=C["muted"],
                             font=("Segoe UI", 9))
        self._dot.pack(side=tk.LEFT)
        self.lbl_status = tk.Label(sf, text="  Selecione um nicho e clique em Iniciar",
                                   font=("Segoe UI", 9), bg=C["bg"], fg=C["muted"])
        self.lbl_status.pack(side=tk.LEFT)

        # ═══ LOGS ════════════════════════════════════════════════
        tk.Frame(self, bg=C["border"], height=1).pack(fill=tk.X)

        log_hdr = tk.Frame(self, bg=C["panel"], padx=16, pady=6)
        log_hdr.pack(fill=tk.X)
        tk.Label(log_hdr, text="LOGS", font=("Segoe UI", 8, "bold"),
                 bg=C["panel"], fg=C["muted"]).pack(side=tk.LEFT)
        for txt, clr in [("✓ OK", C["green"]), ("✗ ERRO", C["red"]), ("⚠ AVISO", C["yellow"])]:
            tk.Label(log_hdr, text=txt, font=("Segoe UI", 8),
                     bg=C["panel"], fg=clr).pack(side=tk.RIGHT, padx=10)

        lf = tk.Frame(self, bg=C["bg"], padx=10, pady=6)
        lf.pack(fill=tk.BOTH, expand=True)

        self.txt = scrolledtext.ScrolledText(
            lf, font=("Consolas", 9),
            bg=C["input"], fg=C["muted"],
            selectbackground=C["blue"],
            state="disabled", wrap=tk.WORD,
            relief=tk.FLAT, padx=12, pady=8,
            insertbackground="white",
        )
        self.txt.pack(fill=tk.BOTH, expand=True)
        self.txt.tag_config("ok",    foreground=C["green"])
        self.txt.tag_config("error", foreground=C["red"])
        self.txt.tag_config("warn",  foreground=C["yellow"])
        self.txt.tag_config("info",  foreground=C["muted"])

        footer = tk.Frame(self, bg=C["panel"], padx=16, pady=3)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(footer,
                 text="pasta_raiz / Nicho X / conta_Y / [atalho.lnk  videos.mp4]   →   Nicho X / postados /",
                 font=("Segoe UI", 7), bg=C["panel"], fg=C["dim"]).pack(side=tk.LEFT)
        tk.Label(footer, text="Criado por Vitório Gomes",
                 font=("Segoe UI", 7), bg=C["panel"], fg=C["muted"]).pack(side=tk.RIGHT)

    # ── Ações ──────────────────────────────────────────────────────
    def _on_nicho_select(self, _event):
        sel = self.nicho_listbox.curselection()
        if not sel:
            return
        new_nicho = self.nicho_listbox.get(sel[0]).strip()
        if new_nicho == self._current_nicho:
            return
        # Salva legendas do nicho anterior antes de trocar
        self._save_config()
        # Carrega legendas do novo nicho
        self._current_nicho = new_nicho
        descs = self._nicho_descs.get(new_nicho, list(DEFAULT_DESCRIPTIONS))
        self._set_descriptions(descs)

    def _ph_in(self, _event):
        if self.desc_entry.get() == self._PLACEHOLDER:
            self.desc_entry.delete(0, tk.END)
            self.desc_entry.config(fg=self.C["text"])

    def _ph_out(self, _event):
        if not self.desc_entry.get().strip():
            self.desc_entry.insert(0, self._PLACEHOLDER)
            self.desc_entry.config(fg=self.C["muted"])

    def _aviso_atualizacao(self, nova_versao: str, url: str):
        import webbrowser
        def _mostrar():
            resposta = messagebox.askyesno(
                "Atualização disponível",
                f"Nova versão {nova_versao} disponível!\n"
                f"Você está usando a versão {APP_VERSION}.\n\n"
                "Deseja abrir a página de download?",
            )
            if resposta:
                webbrowser.open(url)
        self.after(0, _mostrar)

    def _browse(self):
        d = filedialog.askdirectory(initialdir=self.dir_var.get() or str(Path.home()))
        if d:
            self.dir_var.set(d)
            self._scan_nichos()

    def _desc_add(self):
        text = self.desc_entry.get().strip()
        if text and text != self._PLACEHOLDER:
            raw = self._get_descriptions() + [text]
            self.desc_listbox.delete(0, tk.END)
            for i, d in enumerate(raw):
                self.desc_listbox.insert(tk.END, f"{i+1:02d} │ {d}")
            self.desc_entry.delete(0, tk.END)
            self.desc_entry.insert(0, self._PLACEHOLDER)
            self.desc_entry.config(fg=self.C["muted"])
            self._save_config()

    def _desc_remove(self):
        sel = self.desc_listbox.curselection()
        if sel:
            self.desc_listbox.delete(sel[0])
            self._renumber_descs()
            self._save_config()

    def _clear(self):
        self.txt.configure(state="normal")
        self.txt.delete(1.0, tk.END)
        self.txt.configure(state="disabled")

    def _start(self):
        base = self.dir_var.get().strip()
        if not base or not os.path.isdir(base):
            messagebox.showerror("Erro", "Selecione uma pasta raiz válida!")
            return

        if not self._current_nicho:
            messagebox.showerror("Erro", "Selecione um nicho na lista!")
            return
        nicho_name = self._current_nicho
        nicho_dir = Path(base) / nicho_name

        descriptions = self._get_descriptions()
        if not descriptions:
            messagebox.showerror("Erro", "Adicione pelo menos uma descrição!")
            return

        self._save_config()
        self._stop_event.clear()
        self.btn_start.config(state=tk.DISABLED, bg=self.C["dim"], fg=self.C["muted"])
        self.btn_stop.config(state=tk.NORMAL, bg=self.C["red"], fg="white")
        self._set_status(f"Executando: {nicho_name}...", "green")

        logger = ColorLogger(self.txt)
        bot = TikTokBot(str(nicho_dir), descriptions, logger, self._stop_event)

        def _run():
            try:
                bot.run()
            finally:
                self.after(0, self._done)

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def _stop(self):
        self._stop_event.set()
        self._set_status("Parando...", "yellow")
        self.btn_stop.config(state=tk.DISABLED)

    def _done(self):
        self.btn_start.config(state=tk.NORMAL, bg=self.C["green"], fg=self.C["bg"])
        self.btn_stop.config(state=tk.DISABLED, bg=self.C["panel"], fg=self.C["muted"])
        self._set_status("Finalizado.", "muted")


# ─────────────────────────────────────────────
if __name__ == "__main__":
    App().mainloop()
