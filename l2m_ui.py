"""L2M - LREC to MP4 (WebView2 desktop UI).

A thin, frameless pywebview shell around ``l2m_engine``. All of the Arabic /
bidi text rendering is handled by the WebView2 (Chromium) engine, so mixed
Arabic/Latin/number strings lay out correctly. The app is fully offline; the
only network call is the optional support link opened from the Support button.
"""

from __future__ import annotations

import ctypes
import json
import os
import queue
import sys
import threading
import time
import webbrowser
from pathlib import Path

import webview

import l2m_engine as engine

GITHUB_URL = "https://github.com/qusielh/lrec-to-mp4-converter"
DEFAULT_SUPPORT = "https://l2m-platform.qusielh.workers.dev"

FROZEN = getattr(sys, "frozen", False)
BASE = Path(sys._MEIPASS) if FROZEN else Path(__file__).resolve().parent
UI_DIR = BASE / "ui"

_PROC_T0 = time.perf_counter()


def _tmark(label):
    if os.environ.get("L2M_TIMING"):
        print("L2M-TIME %-16s %.3fs" % (label, time.perf_counter() - _PROC_T0),
              file=sys.stderr)


def _config_dir() -> str:
    d = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "L2M")
    os.makedirs(d, exist_ok=True)
    return d


def _config_file() -> str:
    return os.path.join(_config_dir(), "gui.json")


def _load_config() -> dict:
    try:
        with open(_config_file(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_config(cfg: dict) -> None:
    try:
        with open(_config_file(), "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ----------------------------------------------------------------- clipboard
_CF_UNICODETEXT = 13
_GMEM_MOVEABLE = 0x0002


def _clipboard_set(text: str) -> bool:
    if os.name != "nt":
        return False
    try:
        u = ctypes.windll.user32
        k = ctypes.windll.kernel32
        k.GlobalAlloc.restype = ctypes.c_void_p
        k.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        k.GlobalLock.restype = ctypes.c_void_p
        k.GlobalLock.argtypes = [ctypes.c_void_p]
        k.GlobalUnlock.argtypes = [ctypes.c_void_p]
        k.GlobalFree.argtypes = [ctypes.c_void_p]
        u.SetClipboardData.restype = ctypes.c_void_p
        u.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        u.OpenClipboard.argtypes = [ctypes.c_void_p]
        buf = ctypes.create_unicode_buffer(text or "")
        size = ctypes.sizeof(buf)
        handle = k.GlobalAlloc(_GMEM_MOVEABLE, size)
        if not handle:
            return False
        ptr = k.GlobalLock(handle)
        if not ptr:
            k.GlobalFree(handle)
            return False
        ctypes.memmove(ptr, buf, size)
        k.GlobalUnlock(handle)
        if not u.OpenClipboard(None):
            k.GlobalFree(handle)
            return False
        try:
            u.EmptyClipboard()
            u.SetClipboardData(_CF_UNICODETEXT, handle)
        finally:
            u.CloseClipboard()
        return True
    except Exception:
        return False


def _clipboard_get() -> str:
    if os.name != "nt":
        return ""
    try:
        u = ctypes.windll.user32
        k = ctypes.windll.kernel32
        k.GlobalLock.restype = ctypes.c_void_p
        k.GlobalLock.argtypes = [ctypes.c_void_p]
        k.GlobalUnlock.argtypes = [ctypes.c_void_p]
        u.GetClipboardData.restype = ctypes.c_void_p
        u.GetClipboardData.argtypes = [ctypes.c_uint]
        u.OpenClipboard.argtypes = [ctypes.c_void_p]
        if not u.OpenClipboard(None):
            return ""
        try:
            handle = u.GetClipboardData(_CF_UNICODETEXT)
            if not handle:
                return ""
            ptr = k.GlobalLock(handle)
            if not ptr:
                return ""
            try:
                return ctypes.c_wchar_p(ptr).value or ""
            finally:
                k.GlobalUnlock(handle)
        finally:
            u.CloseClipboard()
    except Exception:
        return ""


def _round_corners() -> None:
    if os.name != "nt":
        return
    try:
        u = ctypes.windll.user32
        u.FindWindowW.restype = ctypes.c_void_p
        hwnd = u.FindWindowW(None, "L2M")
        if not hwnd:
            return
        pref = ctypes.c_int(2)  # DWMWCP_ROUND
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            ctypes.c_void_p(hwnd), 33, ctypes.byref(pref), ctypes.sizeof(pref))
    except Exception:
        pass


_WM_NCLBUTTONDOWN = 0x00A1
_HTCAPTION = 2


def _native_drag() -> None:
    if os.name != "nt":
        return
    try:
        u = ctypes.windll.user32
        u.FindWindowW.restype = ctypes.c_void_p
        u.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        u.ReleaseCapture.argtypes = []
        u.SendMessageW.restype = ctypes.c_void_p
        u.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                   ctypes.c_void_p, ctypes.c_void_p]
        hwnd = u.FindWindowW(None, "L2M")
        if not hwnd:
            return
        u.ReleaseCapture()
        u.SendMessageW(hwnd, _WM_NCLBUTTONDOWN, ctypes.c_void_p(_HTCAPTION), None)
    except Exception:
        pass


# --------------------------------------------------------------------- api
class Api:
    def __init__(self) -> None:
        cfg = _load_config()
        self.lang = cfg.get("lang") or "ar"
        self.add_dir = cfg.get("add_dir") or ""
        self.convert_dir = cfg.get("convert_dir") or ""
        self.support_url = cfg.get("support_url") or DEFAULT_SUPPORT
        self.files: list[dict] = []
        self.busy = False
        self.cancelled = False
        self._window = None
        self._events: queue.Queue = queue.Queue()
        self._thread = None

    # ---- config helpers
    def _persist(self, **kw) -> None:
        cfg = _load_config()
        cfg.update(kw)
        _save_config(cfg)

    # ---- events
    def _emit(self, ev: dict) -> None:
        self._events.put(ev)

    def poll_events(self):
        out = []
        for _ in range(400):
            try:
                out.append(self._events.get_nowait())
            except queue.Empty:
                break
        return out

    # ---- boot / language
    def boot(self):
        _tmark("boot() enter")
        _tmark("boot ready")
        return {
            "lang": self.lang,
            "files": [f["name"] for f in self.files],
        }

    def set_lang(self, lang: str):
        self.lang = "ar" if str(lang).lower().startswith("ar") else "en"
        self._persist(lang=self.lang)
        return self.lang

    # ---- file list
    def _names(self):
        return [f["name"] for f in self.files]

    def add_files(self):
        if self.busy:
            return self._names()
        directory = self.add_dir if self.add_dir and os.path.isdir(self.add_dir) else ""
        try:
            picked = self._window.create_file_dialog(
                webview.OPEN_DIALOG,
                directory=directory,
                allow_multiple=True,
                file_types=("LREC recordings (*.lrec)", "All files (*.*)"),
            )
        except Exception:
            picked = None
        if not picked:
            return [f["name"] for f in self.files]
        if isinstance(picked, str):
            picked = [picked]
        for src in picked:
            if not src:
                continue
            stem = os.path.splitext(os.path.basename(src))[0]
            self.files.append({"src": src, "name": stem})
        if picked:
            first = [p for p in picked if p]
            if first:
                self.add_dir = os.path.dirname(first[0])
                self._persist(add_dir=self.add_dir)
        return [f["name"] for f in self.files]

    def remove_file(self, index):
        if self.busy:
            return self._names()
        try:
            index = int(index)
        except (TypeError, ValueError):
            return [f["name"] for f in self.files]
        if 0 <= index < len(self.files):
            self.files.pop(index)
        return [f["name"] for f in self.files]

    def clear_files(self):
        if self.busy:
            return self._names()
        self.files = []
        return []

    def rename_file(self, index, name):
        if self.busy:
            try:
                index = int(index)
            except (TypeError, ValueError):
                return name
            if 0 <= index < len(self.files):
                return self.files[index]["name"]
            return name
        try:
            index = int(index)
        except (TypeError, ValueError):
            return name
        clean = engine.sanitize_name(str(name or ""))
        if 0 <= index < len(self.files):
            self.files[index]["name"] = clean
        return clean

    # ---- conversion
    def start(self):
        if self.busy:
            return {"ok": False, "reason": "busy"}
        if not self.files:
            return {"ok": False, "reason": "toast.nofiles"}
        self.busy = True
        self.cancelled = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return {"ok": True}

    def cancel(self):
        self.cancelled = True
        proc = engine.CURRENT.get("proc")
        if proc is not None:
            try:
                proc.kill()
            except Exception:
                pass
        return True

    def _out_dir(self) -> str:
        if self.convert_dir and os.path.isdir(self.convert_dir):
            return self.convert_dir
        for f in self.files:
            d = os.path.dirname(f["src"])
            if d and os.path.isdir(d):
                return d
        return os.path.expanduser("~")

    def _run(self):
        out_dir = self._out_dir()
        jobs = list(self.files)
        total = len(jobs)
        used = set()
        ok = 0
        fail = 0
        self._emit({"type": "clear-log"})
        self._emit({"type": "busy", "on": True})
        self._emit({"type": "status", "key": "st.starting"})
        for i, job in enumerate(jobs):
            if self.cancelled:
                break
            self._emit({"type": "status", "key": "st.converting", "i": i + 1, "n": total})
            self._emit({"type": "fstate", "index": i, "state": "active"})
            base = job["name"]
            candidate = base
            n = 1
            while candidate.lower() in used:
                n += 1
                candidate = "%s_%d" % (base, n)
            used.add(candidate.lower())
            out_path = os.path.join(out_dir, candidate + ".mp4")
            self._emit({"type": "filetitle", "text": candidate + ".mp4"})
            self._emit({"type": "progress", "frac": 0.0})
            try:
                engine.convert_one(
                    job["src"],
                    out_path,
                    lambda line: self._emit({"type": "log", "line": line}),
                    lambda: self.cancelled,
                    lambda f, rem: self._emit({"type": "progress", "frac": f}),
                )
                ok += 1
                self._emit({"type": "fstate", "index": i, "state": "done"})
            except engine.Cancelled:
                self._emit({"type": "fstate", "index": i, "state": ""})
                break
            except Exception as exc:
                fail += 1
                self._emit({"type": "log", "line": "ERROR: %s" % exc})
                self._emit({"type": "fstate", "index": i, "state": "fail"})
        self._emit({"type": "progress", "frac": 1.0 if not self.cancelled else 0.0})
        self._emit({"type": "filetitle", "text": ""})

        if self.cancelled:
            self._emit({"type": "status", "key": "st.stopped"})
            if ok or fail:
                self._emit({"type": "toast", "key": "toast.stopped"})
        else:
            self._emit({"type": "status", "key": "st.alldone"})
            if fail:
                self._emit({"type": "toast", "key": "toast.failed",
                            "ok": ok, "fail": fail, "kind": "bad"})
            else:
                self._emit({"type": "toast", "key": "toast.done", "ok": ok, "kind": "ok"})
        self._emit({"type": "busy", "on": False})
        self.busy = False
        if ok:
            self.convert_dir = out_dir
            self._persist(convert_dir=out_dir)

    # ---- misc actions
    def open_folder(self):
        target = self._out_dir()
        try:
            os.startfile(target)
        except Exception:
            try:
                webbrowser.open("file:///" + target.replace("\\", "/"))
            except Exception:
                pass
        return True

    def open_support(self):
        try:
            webbrowser.open(self.support_url)
        except Exception:
            pass
        return True

    def open_github(self):
        try:
            webbrowser.open(GITHUB_URL)
        except Exception:
            pass
        return True

    def minimize(self):
        try:
            self._window.minimize()
        except Exception:
            pass
        return True

    def close(self):
        try:
            self._window.destroy()
        except Exception:
            os._exit(0)
        return True

    def copy_text(self, text):
        return _clipboard_set(str(text or ""))

    def get_clipboard(self):
        return _clipboard_get()

    def start_drag(self):
        _native_drag()
        return True

# ------------------------------------------------------------------- launch
def _enable_drag_region(window) -> bool:
    """Turn on WebView2's native non-client region support so CSS
    ``app-region: drag`` becomes a real title-bar drag (smooth, no per-move
    JS->Python round trips). Returns True once applied."""
    if os.name != "nt":
        return False
    try:
        import clr  # noqa: F401
        from System import Action  # type: ignore
    except Exception:
        return False

    wv = getattr(getattr(window, "native", None), "webview", None)
    if wv is None:
        return False

    state = {"ok": False}

    def _apply():
        try:
            core = wv.CoreWebView2
            if core is not None:
                core.Settings.IsNonClientRegionSupportEnabled = True
                state["ok"] = True
        except Exception:
            pass

    try:
        wv.Invoke(Action(_apply))
    except Exception:
        return False
    return state["ok"]


def _install_drag_region(window):
    try:
        import clr  # noqa: F401
    except Exception:
        return
    for _ in range(60):
        try:
            if _enable_drag_region(window):
                _tmark("drag native ON")
                return
        except Exception:
            return
        time.sleep(0.25)



def _round_after_start(window):
    _tmark("after_start enter")
    time.sleep(0.4)
    _tmark("round+sleep done")
    if os.name == "nt":
        try:
            hwnd = ctypes.windll.user32.FindWindowW(None, "L2M")
            if hwnd:
                pref = ctypes.c_int(2)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    ctypes.c_void_p(hwnd), 33, ctypes.byref(pref), ctypes.sizeof(pref))
        except Exception:
            pass
    threading.Thread(target=_install_drag_region, args=(window,), daemon=True).start()


def main():
    _t = [time.perf_counter()]
    def _mark(label):
        if os.environ.get("L2M_TIMING"):
            now = time.perf_counter()
            print("L2M-TIME %-16s %.3fs" % (label, now - _t[0]), file=sys.stderr)
            _t[0] = now
    api = Api()
    _mark("Api()")

    index = UI_DIR / "index.html"
    if not index.exists():
        sys.stderr.write("L2M: missing front end %s\n" % index)
        raise SystemExit(2)
    url = str(index)
    window = webview.create_window(
        "L2M",
        url=url,
        js_api=api,
        width=1000,
        height=780,
        min_size=(820, 700),
        frameless=True,
        easy_drag=False,
        background_color="#0e1322",
        text_select=False,
    )
    api._window = window
    _mark("create_window()")
    webview.start(_round_after_start, window, gui="edgechromium",
                  private_mode=False,
                  storage_path=os.path.join(_config_dir(), "webview"),
                  debug=bool(os.environ.get("L2M_DEBUG")))


if __name__ == "__main__":
    main()
