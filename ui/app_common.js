/* L2M - shared UI core.
   Contains the mechanics used by the free desktop app: file list, conversion
   controls, log, events and the boot handshake. */
"use strict";

/* ---------- i18n ---------- */
/* Common strings. Edition files merge their own keys into I18N. */
const I18N = { en: {}, ar: {} };

function mergeI18n(dict) {
  ["en", "ar"].forEach(function (lang) {
    const src = dict[lang] || {};
    for (const k in src) I18N[lang][k] = src[k];
  });
}

mergeI18n({
  en: {
    recordings: "Recordings",
    rechor: "name \u2192 saved as .mp4",
    add: "+  Add files",
    clear: "Clear",
    convert: "Convert to MP4",
    stop: "Stop",
    openfolder: "Open folder",
    activity: "Activity",
    empty: "No recordings yet. Click \u201c+ Add files\u201d to begin.",
    "st.starting": "Starting",
    "st.converting": "Converting {i} of {n}",
    "st.stopping": "Stopping",
    "st.stopped": "Stopped",
    "st.alldone": "All done",
    "working": "Working",
    "loading": "Loading",
    "boot.error": "Could not start L2M. Please close this window and open the app again.",
    "toast.nofiles": "Add at least one .lrec file first",
    "toast.stopped": "Stopped",
    "toast.failed": "{ok} converted, {fail} failed \u2014 see log",
    "toast.done": "{ok} file(s) converted"
  },
  ar: {
    "recordings": "التسجيلات",
    "rechor": "اسم الملف → يُحفظ بصيغة .mp4",
    "add": "+  إضافة ملفات",
    "clear": "مسح",
    "convert": "تحويل إلى MP4",
    "stop": "إيقاف",
    "openfolder": "فتح المجلد",
    "activity": "النشاط",
    "empty": "لا توجد تسجيلات بعد. اضغط «إضافة ملفات» للبدء.",
    "st.starting": "جارٍ البدء",
    "st.converting": "جارٍ تحويل {i} من {n}",
    "st.stopping": "جارٍ الإيقاف",
    "st.stopped": "تم الإيقاف",
    "st.alldone": "انتهى الكل",
    "working": "جارٍ التحقق…",
    "loading": "جارٍ التحميل",
    "boot.error": "تعذر تشغيل L2M. أغلق النافذة وافتح التطبيق من جديد.",
    "toast.nofiles": "أضف ملف .lrec واحدًا على الأقل",
    "toast.stopped": "تم الإيقاف",
    "toast.failed": "نجح {ok} وفشل {fail} — راجع السجل",
    "toast.done": "تم تحويل {ok} من الملفات"
  }
});

/* ---------- state ---------- */
const state = {
  lang: "ar",
  files: [],
  busy: false
};

/* Edition hook for the small amount of edition-specific UI wiring. */
const EDITION = {
  id: "free",
  bind: function () {},
  applyDynamic: function () {},
  onBoot: function () {}
};

const $ = function (id) { return document.getElementById(id); };

function t(key, params) {
  var dict = I18N[state.lang] || I18N.en;
  var s = (key in dict) ? dict[key] : (I18N.en[key] !== undefined ? I18N.en[key] : key);
  if (params) {
    for (var k in params) s = s.split("{" + k + "}").join(params[k]);
  }
  return s;
}

/* ---------- api bridge ---------- */
async function apiCall(name) {
  var args = Array.prototype.slice.call(arguments, 1);
  if (!window.pywebview || !window.pywebview.api) return null;
  try {
    return await window.pywebview.api[name].apply(window.pywebview.api, args);
  } catch (e) {
    return null;
  }
}

/* ---------- rendering ---------- */
function applyLang() {
  document.documentElement.lang = state.lang;
  document.documentElement.dir = "ltr";
  document.querySelectorAll("[data-i18n]").forEach(function (el) {
    el.textContent = t(el.getAttribute("data-i18n"));
  });
  var sub = $("subtitle");
  if (sub) sub.textContent = t("subtitle");
  var bl = $("btn-lang");
  if (bl) bl.textContent = state.lang === "ar" ? "English" : "العربية";
  var ba = $("btn-add");
  if (ba) ba.textContent = t("add");
  var bs = $("btn-support");
  if (bs) bs.title = t("support.title");
  updateDynamic();
  renderFiles();
}

function updateDynamic() {
  var sp = $("splash-text");
  if (sp) sp.textContent = t("loading");
  EDITION.applyDynamic();
}

function renderFiles() {
  var list = $("list");
  if (!list) return;
  list.textContent = "";
  if (!state.files.length) {
    var d = document.createElement("div");
    d.className = "empty";
    d.textContent = t("empty");
    list.appendChild(d);
    return;
  }
  state.files.forEach(function (name, i) {
    var row = document.createElement("div");
    row.className = "row";
    row.dataset.index = String(i);

    var dot = document.createElement("span");
    dot.className = "dot";
    dot.dataset.role = "dot";

    var input = document.createElement("input");
    input.type = "text";
    input.value = name;
    input.spellcheck = false;
    input.addEventListener("change", function () { onRename(i, input); });
    input.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { input.blur(); }
    });

    var ext = document.createElement("span");
    ext.className = "suffix";
    ext.textContent = ".mp4";

    var rm = document.createElement("button");
    rm.className = "rm";
    rm.type = "button";
    rm.textContent = "\u2715";
    rm.addEventListener("click", function () { onRemove(i); });

    row.appendChild(dot);
    row.appendChild(input);
    row.appendChild(ext);
    row.appendChild(rm);
    list.appendChild(row);
  });
  if (state.busy) {
    document.querySelectorAll(".row input").forEach(function (i) { i.disabled = true; });
    document.querySelectorAll(".row .rm").forEach(function (b) { b.disabled = true; });
  }
}

function markFile(index, cls) {
  var row = document.querySelector('.row[data-index="' + index + '"]');
  if (!row) return;
  var dot = row.querySelector('[data-role="dot"]');
  if (dot) dot.className = "dot" + (cls ? " " + cls : "");
}

function clearMarks() {
  document.querySelectorAll('[data-role="dot"]').forEach(function (d) { d.className = "dot"; });
}

/* ---------- log ---------- */
function appendLog(line) {
  var log = $("log");
  log.textContent += (log.textContent ? "\n" : "") + line;
  log.scrollTop = log.scrollHeight;
}
function clearLog() { $("log").textContent = ""; }

/* ---------- toast ---------- */
let toastTimer = null;
function showToast(msg, kind) {
  var el = $("toast");
  el.textContent = msg;
  el.className = "toast show" + (kind ? " " + kind : "");
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(function () { el.className = "toast" + (kind ? " " + kind : ""); }, 4200);
}

/* ---------- modals ---------- */
function openModal(id) {
  var el = $(id);
  if (el) el.hidden = false;
}
function closeModal(id) {
  var el = $(id);
  if (el) el.hidden = true;
}
function closeAll() {
  closeModal("m-support");
}

/* ---------- actions ---------- */
function onRename(i, input) {
  if (state.busy) return;
  var val = input.value;
  apiCall("rename_file", i, val).then(function (clean) {
    if (typeof clean === "string") {
      input.value = clean;
      state.files[i] = clean;
    }
  });
}
function onRemove(i) {
  if (state.busy) return;
  apiCall("remove_file", i).then(function (files) {
    if (Array.isArray(files)) { state.files = files; renderFiles(); }
  });
}
function onAdd() {
  if (state.busy) return;
  apiCall("add_files").then(function (files) {
    if (Array.isArray(files)) { state.files = files; renderFiles(); }
  });
}
function onClear() {
  if (state.busy) return;
  apiCall("clear_files").then(function () {
    state.files = [];
    renderFiles();
    clearMarks();
  });
}
function onConvert() {
  if (state.busy) return;
  if (!state.files.length) {
    showToast(t("toast.nofiles"), "bad");
    return;
  }
  apiCall("start").then(function (res) {
    if (res && res.ok === false) {
      var reason = res.reason || "toast.nofiles";
      if (reason !== "busy") showToast(t(reason), "bad");
    }
  });
}
function onStop() { apiCall("cancel"); }
function onOpenFolder() { apiCall("open_folder"); }
function onOpenSupport() {
  updateDynamic();
  openModal("m-support");
}
function onOpenSupportSite() { apiCall("open_support"); }
function onOpenGitHub() { apiCall("open_github"); }
function onMin() { apiCall("minimize"); }
function onClose() { apiCall("close"); }
function onLang() {
  var next = state.lang === "ar" ? "en" : "ar";
  apiCall("set_lang", next).then(function () {
    state.lang = next;
    applyLang();
    renderFiles();
  });
}

/* ---------- busy / status ---------- */
function setBusy(on) {
  state.busy = !!on;
  $("btn-convert").disabled = state.busy;
  $("btn-stop").disabled = !state.busy;
  $("btn-add").disabled = state.busy;
  $("btn-clear").disabled = state.busy;
  document.querySelectorAll(".row input").forEach(function (i) { i.disabled = state.busy; });
  document.querySelectorAll(".row .rm").forEach(function (b) { b.disabled = state.busy; });
}

/* ---------- events from python ---------- */
function handleEvent(ev) {
  if (!ev || !ev.type) return;
  switch (ev.type) {
    case "log": appendLog(ev.line); break;
    case "clear-log": clearLog(); break;
    case "status": $("status").textContent = t(ev.key, ev); break;
    case "progress": {
      var f = Math.max(0, Math.min(1, Number(ev.frac) || 0));
      $("bar").style.width = (f * 100).toFixed(1) + "%";
      $("pct").textContent = f > 0 ? Math.round(f * 100) + "%" : "";
      break;
    }
    case "filetitle": $("filetitle").textContent = ev.text || ""; break;
    case "fstate": {
      var cls = ev.state === "active" ? "active" : (ev.state === "done" ? "done" : (ev.state === "fail" ? "fail" : ""));
      markFile(ev.index, cls);
      break;
    }
    case "busy": setBusy(ev.on); break;
    case "toast": {
      var msg = ev.text ? ev.text : t(ev.key, ev);
      showToast(msg, ev.kind || "");
      break;
    }
    default: break;
  }
}

async function poll() {
  var evs = await apiCall("poll_events");
  if (Array.isArray(evs)) evs.forEach(handleEvent);
}

/* ---------- boot ---------- */
let booting = false;
let booted = false;

function splashError(msg) {
  var spin = document.querySelector("#splash .spinner");
  if (spin) spin.style.display = "none";
  var box = $("splash-err");
  if (box) { box.textContent = msg; box.hidden = false; }
}

function hideSplash() {
  var s = $("splash");
  if (!s || s.classList.contains("hide")) return;
  s.classList.add("hide");
  setTimeout(function () { s.style.display = "none"; }, 320);
}

function startApp(info) {
  if (info && typeof info === "object") {
    state.lang = info.lang || "ar";
    state.files = Array.isArray(info.files) ? info.files : [];
  }
  applyLang();
  renderFiles();
  setBusy(false);
  EDITION.onBoot(info);
  requestAnimationFrame(function () {
    requestAnimationFrame(function () { setTimeout(hideSplash, 200); });
  });
  setInterval(poll, 150);
}

async function boot() {
  if (booted || booting) return;
  booting = true;
  try {
    for (var i = 0; i < 60; i++) {
      var info = await apiCall("boot");
      if (info && typeof info === "object") {
        booted = true;
        startApp(info);
        return;
      }
      await new Promise(function (r) { setTimeout(r, 120); });
    }
    splashError(t("boot.error"));
  } finally {
    booting = false;
  }
}

/* ---------- binding ---------- */
function bind() {
  var dragbar = $("dragbar");
  if (dragbar) {
    dragbar.addEventListener("mousedown", function (ev) {
      if (ev.button !== 0) return;
      ev.preventDefault();
      document.body.classList.add("dragging");
      apiCall("start_drag");
    });
  }
  window.addEventListener("mouseup", function () {
    document.body.classList.remove("dragging");
  });

  $("btn-github").addEventListener("click", onOpenGitHub);
  $("btn-lang").addEventListener("click", onLang);
  $("btn-support").addEventListener("click", onOpenSupport);
  $("btn-support-site").addEventListener("click", onOpenSupportSite);
  $("btn-star").addEventListener("click", onOpenGitHub);
  $("btn-min").addEventListener("click", onMin);
  $("btn-close").addEventListener("click", onClose);

  $("btn-add").addEventListener("click", onAdd);
  $("btn-clear").addEventListener("click", onClear);
  $("btn-convert").addEventListener("click", onConvert);
  $("btn-stop").addEventListener("click", onStop);
  $("btn-open").addEventListener("click", onOpenFolder);

  document.querySelectorAll("[data-close]").forEach(function (b) {
    b.addEventListener("click", function () { closeAll(); });
  });
  document.querySelectorAll(".overlay").forEach(function (o) {
    o.addEventListener("mousedown", function (e) { if (e.target === o) closeAll(); });
  });

  EDITION.bind();
}

window.addEventListener("DOMContentLoaded", function () {
  bind();
  applyLang();
  renderFiles();
  boot();
});
window.addEventListener("pywebviewready", function () { boot(); });
