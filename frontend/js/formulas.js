(() => {
  "use strict";

  const API = window.API_BASE || "";            // тот же хост, что и бэкенд
  const DEMO_URL = "data/formulas.json";        // относительно formulas.html
  const PHASES = ["pre", "during", "post"];
  const $ = (id) => document.getElementById(id);

  let sensors = [];    // из БД
  let formulas = [];   // из файла

  // ---------- утилиты ----------
  function log(msg, cls = "") {
    const line = document.createElement("div");
    line.className = cls;
    line.textContent = msg;
    $("log").appendChild(line);
    $("log").scrollTop = $("log").scrollHeight;
  }

  async function api(path, options) {
    let res;
    try {
      res = await fetch(API + path, options);
    } catch (e) {
      return { ok: false, status: 0, body: { detail: "нет связи с сервером: " + e.message } };
    }
    let body = null;
    try { body = await res.json(); } catch { /* пустой ответ */ }
    return { ok: res.ok, status: res.status, body };
  }

  function fmtDetail(body) {
    const d = body && body.detail;
    if (!d) return JSON.stringify(body);
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {        // ошибки pydantic
      return d.map((e) => `${(e.loc || []).slice(1).join(".")}: ${e.msg}`).join("; ");
    }
    return JSON.stringify(d);
  }

  function renderTable(box, head, rows) {
    box.replaceChildren();
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

  // ---------- 1. датчики ----------
  async function loadSensors() {
    const r = await api("/api/sensors");
    if (!r.ok) { log(`GET /api/sensors: ${r.status} ${fmtDetail(r.body)}`, "err"); return; }
    sensors = r.body;
    renderTable($("sensorsBox"),
      ["tag", "параметр", "ед.", "прибор", "valid_min", "valid_max"],
      sensors.map((s) => [s.tag,  s.parameter, s.unit, s.instrument, s.valid_min, s.valid_max]));
    log(`Датчиков в БД: ${sensors.length}`, sensors.length ? "ok" : "warn");
    if (!sensors.length) log("Пусто: выполните sql/seed_demo_sensors.sql или добавьте свои датчики.", "warn");
  }

  // ---------- 2. формулы ----------
  function setFormulas(json, source) {
    const list = Array.isArray(json) ? json : json.formulas;
    if (!Array.isArray(list)) { log("Ожидался массив формул или {\"formulas\": [...]}", "err"); return; }
    formulas = list;
    renderTable($("formulasBox"),
      ["#", "название", "версия", "шагов", "датчиков (уник.)"],
      formulas.map((f, i) => [i + 1, f.name, f.version, (f.steps || []).length, uniqueTags(f).size]));
    log(`Загружено формул: ${formulas.length} (${source})`, "ok");
  }

  function uniqueTags(f) {
    const tags = new Set();
    (f.steps || []).forEach((s) => Object.keys(s.dict_PLC_id || {}).forEach((t) => tags.add(t)));
    return tags;
  }

  async function loadDemo() {
    const res = await fetch(DEMO_URL);
    if (!res.ok) { log(`Не нашёл ${DEMO_URL}: ${res.status}`, "err"); return; }
    setFormulas(await res.json(), DEMO_URL);
  }

  function loadFile(file) {
    const reader = new FileReader();
    reader.onload = () => {
      try { setFormulas(JSON.parse(reader.result), file.name); }
      catch (e) { log("Невалидный JSON: " + e.message, "err"); }
    };
    reader.readAsText(file);
  }

  // ---------- 3. локальная проверка (зеркало серверных правил) ----------
  function validateLocal() {
    if (!formulas.length) { log("Сначала загрузите формулы.", "warn"); return false; }
    const known = new Map(sensors.map((s) => [s.tag, s]));
    if (!sensors.length) log("Датчики из БД не загружены - привязку тегов проверить нельзя.", "warn");

    const problems = [];
    const seenNameVer = new Set();

    formulas.forEach((f, fi) => {
      const where = `[${fi + 1}] ${f.name} v${f.version}`;
      const nv = `${f.name}#${f.version}`;
      if (seenNameVer.has(nv)) problems.push(`${where}: дубль name+version в файле`);
      seenNameVer.add(nv);

      const steps = f.steps || [];
      if (!steps.length) problems.push(`${where}: нет шагов`);
      const nums = steps.map((s) => s.step), keys = steps.map((s) => s.step_key);
      if (new Set(nums).size !== nums.length) problems.push(`${where}: номера шагов не уникальны`);
      if (new Set(keys).size !== keys.length) problems.push(`${where}: step_key не уникальны`);

      steps.forEach((s) => {
        const at = `${where}, шаг ${s.step}`;
        for (const [k, v] of Object.entries(s.in_data || {})) if (!(v > 0)) problems.push(`${at}: in_data['${k}'] должна быть > 0`);
        for (const [k, v] of Object.entries(s.out_data || {})) if (!(v >= 0)) problems.push(`${at}: out_data['${k}'] < 0`);
        for (const [k, v] of Object.entries(s.constant || {})) if (!(v > 0 && v <= 1)) problems.push(`${at}: constant['${k}'] вне (0, 1]`);

        for (const [tag, limits] of Object.entries(s.dict_PLC_id || {})) {
          const sensor = known.get(tag);
          if (sensors.length && !sensor) problems.push(`${at}: датчика '${tag}' нет в БД`);
          PHASES.forEach((ph) => {
            const r = limits[ph];
            if (!r) return;
            if (r.min == null && r.max == null) problems.push(`${at}, ${tag}/${ph}: нужен min или max`);
            if (r.min != null && r.max != null && r.min > r.max) problems.push(`${at}, ${tag}/${ph}: min > max`);
            if (sensor && sensor.valid_min != null && r.min != null && r.min < sensor.valid_min)
              problems.push(`${at}, ${tag}/${ph}: min ${r.min} < valid_min ${sensor.valid_min}`);
            if (sensor && sensor.valid_max != null && r.max != null && r.max > sensor.valid_max)
              problems.push(`${at}, ${tag}/${ph}: max ${r.max} > valid_max ${sensor.valid_max}`);
          });
        }
      });
    });

    if (problems.length) { problems.forEach((p) => log(p, "err")); log(`Проблем: ${problems.length}`, "err"); return false; }
    log("Локальная проверка пройдена.", "ok");
    return true;
  }

  // ---------- отправка ----------
  async function sendAll() {
    if (!validateLocal()) { log("Отправка отменена: исправьте ошибки выше.", "warn"); return; }
    for (const f of formulas) {
      const r = await api("/api/formulas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(f),
      });
      const label = `${f.name} v${f.version}`;
      if (r.ok) log(`${label}: сохранено, id=${r.body.id}, шагов ${r.body.steps_count}`, "ok");
      else if (r.status === 409) log(`${label}: уже есть в БД (409)`, "warn");
      else log(`${label}: ${r.status} ${fmtDetail(r.body)}`, "err");
    }
  }

  async function showDb() {
    const r = await api("/api/formulas");
    if (!r.ok) { log(`GET /api/formulas: ${r.status} ${fmtDetail(r.body)}`, "err"); return; }
    log(`В БД формул: ${r.body.length}`, "ok");
    for (const f of r.body) {
      const d = await api(`/api/formulas/${f.id}`);
      if (!d.ok) { log(`  #${f.id}: ${d.status}`, "err"); continue; }
      log(`  #${f.id} ${f.name} v${f.version}`);
      d.body.steps.forEach((s) => {
        const sens = Object.entries(s.sensors).map(([t, v]) => `${t} (${v.parameter}, ${v.unit || "?"})`).join(", ");
        log(`     шаг ${s.step} ${s.step_key}: датчики -> ${sens || "нет"}`);
      });
    }
  }

  // ---------- старт ----------
  $("btnSensors").addEventListener("click", loadSensors);
  $("btnDemo").addEventListener("click", loadDemo);
  $("fileInput").addEventListener("change", (e) => e.target.files[0] && loadFile(e.target.files[0]));
  $("btnValidate").addEventListener("click", validateLocal);
  $("btnSend").addEventListener("click", sendAll);
  $("btnList").addEventListener("click", showDb);
})();
