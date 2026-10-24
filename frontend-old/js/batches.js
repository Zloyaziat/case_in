(() => {
  "use strict";

  const API = window.API_BASE || "";
  const POLL_MS = 500;
  const $ = (id) => document.getElementById(id);

  let batchId = null;
  let timer = null;
  let lastRecId = 0;

  // ---------- утилиты ----------
  function log(msg, cls = "") {
    const line = document.createElement("div");
    line.className = cls;
    line.textContent = msg;
    $("log").appendChild(line);
    $("log").scrollTop = $("log").scrollHeight;
  }

  async function api(path, method = "GET", body) {
    const opts = { method };
    if (body !== undefined) {
      opts.headers = { "Content-Type": "application/json" };
      opts.body = JSON.stringify(body);
    }
    let res;
    try {
      res = await fetch(API + path, opts);
    } catch (e) {
      return { ok: false, status: 0, body: { detail: "нет связи с сервером: " + e.message } };
    }
    let data = null;
    try { data = await res.json(); } catch { /* пустой ответ */ }
    return { ok: res.ok, status: res.status, body: data };
  }

  function detail(body) {
    const d = body && body.detail;
    if (!d) return JSON.stringify(body);
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((e) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join("; ");
    return JSON.stringify(d);
  }

  function renderTable(box, head, rows) {
    box.replaceChildren();
    if (!rows.length) return;
    const table = document.createElement("table");
    const thead = table.createTHead().insertRow();
    head.forEach((h) => { const th = document.createElement("th"); th.textContent = h; thead.appendChild(th); });
    const tbody = table.createTBody();
    rows.forEach((r) => {
      const tr = tbody.insertRow();
      r.forEach((c) => { tr.insertCell().textContent = c ?? ""; });
    });
    box.appendChild(table);
  }

  const time = (iso) => (iso ? new Date(iso).toLocaleTimeString() : "");
  const PHASE = {
    created: "создана", running: "идёт", awaiting_finish: "шаги пройдены — введите v_finish и качество",
    finished: "завершена", aborted: "прервана",
  };

  // ---------- 1. формула и сырьё ----------
  async function loadFormulas() {
    const r = await api("/api/formulas");
    if (!r.ok) { log(`GET /api/formulas: ${detail(r.body)}`, "err"); return; }
    $("formula").replaceChildren(...r.body.map((f) => new Option(`${f.id}: ${f.name} v${f.version}`, f.id)));
    if (r.body.some((f) => f.id === 15)) $("formula").value = "15";
    await loadVin();
  }

  async function loadVin() {
    // поля v_in - по реагентам первого шага формулы
    const r = await api(`/api/formulas/${$("formula").value}`);
    const box = $("vinBox");
    box.replaceChildren();
    if (!r.ok) return;
    const first = r.body.steps[0] || { in_data: {} };
    Object.entries(first.in_data || {}).forEach(([k, v]) => {
      const label = document.createElement("label");
      label.textContent = `${k} `;
      const input = document.createElement("input");
      Object.assign(input, { type: "number", min: "0", step: "any", value: v });
      input.dataset.key = k;
      input.style.width = "6rem";
      label.appendChild(input);
      box.appendChild(label);
    });
  }

  function readVin() {
    const v = {};
    $("vinBox").querySelectorAll("input").forEach((i) => { if (i.value !== "") v[i.dataset.key] = Number(i.value); });
    return v;
  }

  async function createAndStart() {
    const formulaId = Number($("formula").value);
    const c = await api("/api/batches", "POST", { formula_id: formulaId, v_in: readVin() });
    if (!c.ok) { log(`создание партии: ${detail(c.body)}`, "err"); return; }
    const s = await api(`/api/batches/${c.body.id}/start`, "POST", { speed: Number($("speed").value) || 1 });
    if (!s.ok) { log(`старт партии ${c.body.id}: ${detail(s.body)}`, "err"); return; }
    log(`партия ${c.body.id} запущена; эталоны: ${s.body.reference_batches.join(", ") || "нет"}`, "ok");
    watch(c.body.id);
  }

  // ---------- 2. ход партии ----------
  function watch(id) {
    batchId = id;
    lastRecId = 0;
    $("recs").replaceChildren();
    $("recs").textContent = "пока нет";
    $("recs").classList.add("muted");
    clearInterval(timer);
    refresh();
    timer = setInterval(refresh, POLL_MS);
  }

  async function refresh() {
    if (batchId == null) return;
    const r = await api(`/api/batches/${batchId}`);
    if (!r.ok) { log(`GET партии: ${detail(r.body)}`, "err"); return; }
    const b = r.body;
    const live = b.live;

    let state = `Партия ${b.id} (формула ${b.formula_id}): ${PHASE[b.phase] || b.phase}`;
    if (live && live.step != null) {
      state += ` · шаг ${live.step}, ${live.step_elapsed_s.toFixed(1)} из ${live.step_planned_s ?? "∞"} с`;
    }
    $("state").textContent = state;
    $("state").className = "";

    renderTable($("stepsBox"), ["шаг", "статус", "начат", "закончен", "план, с", "кем закончен"],
      b.steps.map((s) => [s.step, s.status, time(s.started_at), time(s.finished_at), s.planned_seconds, s.ended_by]));
    if (live) {
      const rd = live.readings;
      renderTable($("windowsBox"), ["шаг", "окно, с", "средние (V)", "точек"],
        live.last_windows.map((w) => [w.step, w.time_s,
          Object.entries(w.values).map(([k, v]) => `${k}=${v}`).join("  "), w.n_samples]));
      $("windowsBox").insertAdjacentText("beforeend",
        `показаний: принято ${rd.accepted}, не этого шага ${rd.ignored}, мусор ${rd.bad_value}, ` +
        `вне пределов датчика ${rd.out_of_range}; файл ${live.opc.read}/${live.opc.total}` +
        (live.error ? ` · ОШИБКА: ${live.error}` : ""));
    }

    await loadRecs();

    const running = b.status === "running";
    $("btnNext").disabled = !(running && b.current_step != null);
    $("btnAbort").disabled = !running;
    $("btnFinish").disabled = !running;
    if (!running) { clearInterval(timer); loadBatches(); }
  }

  async function loadRecs() {
    const r = await api(`/api/batches/${batchId}/recommendations?after_id=${lastRecId}`);
    if (!r.ok || !r.body.length) return;
    if (lastRecId === 0) {
      $("recs").replaceChildren();
      $("recs").classList.remove("muted");   // "пока нет" было серым, рекомендации - нет
    }
    r.body.forEach((x) => {
      const div = document.createElement("div");
      div.textContent = `шаг ${x.step}, ${x.time_s} с: ${x.message} ` +
        `(сейчас ${x.value}, эталон ${x.ref_avg} ± ${x.ref_std}, партий ${x.n_refs})`;
      $("recs").appendChild(div);
      lastRecId = x.id;
    });
  }

  async function post(path, body, okMsg) {
    const r = await api(`/api/batches/${batchId}/${path}`, "POST", body);
    if (!r.ok) { log(`${path}: ${detail(r.body)}`, "err"); return; }
    log(okMsg, "ok");
    refresh();
  }

  // ---------- 3. завершение ----------
  function finish() {
    if ($("vFinish").value === "" || $("quality").value === "") { log("введите v_finish и качество", "err"); return; }
    post("finish", {
      v_finish: Number($("vFinish").value), quality: Number($("quality").value),
      quality_unit: $("qualityUnit").value || "%", is_reference: $("isRef").checked,
    }, `партия ${batchId} завершена`);
  }

  async function loadBatches() {
    const r = await api("/api/batches");
    if (!r.ok) return;
    renderTable($("batchesBox"), ["id", "формула", "статус", "старт", "v_in", "v_finish", "качество", "эталон", ""],
      r.body.slice(0, 15).map((b) => [b.id, b.formula_id, PHASE[b.phase] || b.phase, time(b.started_at),
        JSON.stringify(b.v_in), b.v_finish, b.quality != null ? `${b.quality} ${b.quality_unit || ""}` : "",
        b.is_reference ? "да" : "", ""]));
    // кнопка «открыть» в последней колонке
    $("batchesBox").querySelectorAll("tbody tr").forEach((tr, i) => {
      const btn = document.createElement("button");
      btn.textContent = "открыть";
      btn.onclick = () => watch(r.body[i].id);
      tr.lastChild.appendChild(btn);
    });
  }

  $("formula").addEventListener("change", loadVin);
  $("btnStart").addEventListener("click", createAndStart);
  $("btnNext").addEventListener("click", () => post("next-step", undefined, "шаг завершён оператором"));
  $("btnAbort").addEventListener("click", () => post("abort", undefined, `партия ${batchId} прервана`));
  $("btnFinish").addEventListener("click", finish);

  loadFormulas();
  loadBatches();
})();
