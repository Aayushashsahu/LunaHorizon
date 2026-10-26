/* NISAR // Earth in Motion — local observation explorer (no frameworks, no network). */
"use strict";

const state = {
  index: null,
  observationId: null,
  obs: null,
  sampleToken: 0,
  thresholdTimer: null,
  hoverTimer: null,
  rawAvailable: true,
};

const map = {
  canvas: null,
  ctx: null,
  wrap: null,
  images: {},
  bounds: null,
  imgW: 0,
  imgH: 0,
  zoom: 1,
  panX: 0,
  panY: 0,
  overlay: null,
  coherence: null,
  threshold: 0.4,
  layer: "phase",
  marker: null,
  events: [],
  overlayEnabled: true,
  dragging: null,
};

const els = {};
const num = (v, digits = 2) =>
  v === null || v === undefined || Number.isNaN(Number(v))
    ? "—"
    : Number(v).toLocaleString(undefined, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
const int = (v) =>
  v === null || v === undefined ? "—" : Number(v).toLocaleString();
const pct = (v, digits = 1) => (v === null || v === undefined ? "—" : `${num(v, digits)}%`);
const prettyDate = (iso) => {
  if (!iso) return "date unknown";
  const s = String(iso);
  return s.includes("T") ? s.split("T")[0] : s;
};
const prettyTime = (iso) => {
  if (!iso) return "";
  const s = String(iso);
  if (!s.includes("T")) return "";
  return s.split("T")[1].split(".")[0] + " UTC";
};
const bytes = (v) => {
  if (!v && v !== 0) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let value = Number(v);
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${num(value, value >= 10 ? 0 : 1)} ${units[i]}`;
};
const escapeHtml = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function toast(message, isError = false) {
  const el = els.toast;
  el.textContent = message;
  el.classList.toggle("error", isError);
  el.hidden = false;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    el.hidden = true;
  }, isError ? 7000 : 3200);
}

async function copyToClipboard(text, buttonEl) {
  let copied = false;
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      copied = true;
    }
  } catch (clipErr) {
    // Clipboard writeText can fail when window is unfocused (e.g. headless tests)
  }

  if (!copied) {
    try {
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "absolute";
      textarea.style.left = "-9999px";
      document.body.appendChild(textarea);
      textarea.select();
      copied = document.execCommand("copy");
      document.body.removeChild(textarea);
    } catch (fallbackErr) {
      copied = false;
    }
  }

  if (buttonEl) {
    const textSpan = buttonEl.querySelector(".copy-text");
    const origText = textSpan ? textSpan.textContent : "Copy ID";
    if (textSpan) textSpan.textContent = copied ? "Copied!" : "Copied ID";
    buttonEl.classList.add("copied");
    setTimeout(() => {
      if (textSpan) textSpan.textContent = origText;
      buttonEl.classList.remove("copied");
    }, 2000);
  }
  toast(copied ? "Granule identifier copied to clipboard" : "Granule identifier: " + text.slice(0, 24) + "…");
}

async function api(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  let payload = null;
  try {
    payload = await response.json();
  } catch (err) {
    payload = null;
  }
  if (!response.ok) {
    const message = (payload && (payload.error || payload.message)) || `HTTP ${response.status}`;
    const error = new Error(message);
    error.details = payload && payload.details;
    throw error;
  }
  return payload;
}

/* ------------------------------------------------------------------ boot */
/* Every id below must exist in index.html.  The lookup is explicit so that a
 * missing control is reported loudly instead of throwing halfway through
 * initialization (which is exactly how the explorer navigation used to die:
 * "open-explorer" was forgotten here, the first addEventListener threw, and
 * every later binding - tabs, select, threshold, map, /api/index - never ran).
 */
const ELEMENT_IDS = [
  "server-status", "observation-cards", "dashboard-empty", "hero-stats", "case-strip",
  "dashboard-limitations", "observation-select", "explorer-toolbar-meta", "meta-body",
  "validation-list", "layer-tabs", "coverage-fill", "coverage-label", "coverage-grid",
  "layer-stats", "event-list", "threshold-table", "layer-explanations",
  "explorer-limitations", "explorer-warnings", "export-grid", "readout", "legend",
  "threshold", "threshold-value", "threshold-stats", "overlay-toggle", "map-hint",
  "map-badge", "toast", "canvas-wrap", "map-canvas", "open-explorer",
];

document.addEventListener("DOMContentLoaded", () => {
  ELEMENT_IDS.forEach((id) => {
    els[id] = document.getElementById(id);
    if (!els[id]) console.error(`[boot] missing control #${id} in index.html`);
  });

  // 1. Navigation first: switching views must work even if every API call fails.
  bindNavigation();

  // 2. Data-dependent controls, each isolated so one failure cannot abort boot.
  const steps = [
    ["observation select", () =>
      els["observation-select"].addEventListener("change", (event) =>
        openObservation(event.target.value))],
    ["threshold slider", () =>
      els["threshold"].addEventListener("input", (event) => {
        map.threshold = Number(event.target.value);
        els["threshold-value"].textContent = num(map.threshold, 2);
        clearTimeout(state.thresholdTimer);
        state.thresholdTimer = setTimeout(() => {
          buildOverlay();
          updateThresholdStats(map.threshold);
          drawMap();
        }, 90);
      })],
    ["coherence overlay toggle", () =>
      els["overlay-toggle"].addEventListener("change", (event) => {
        map.overlayEnabled = event.target.checked;
        drawMap();
      })],
    ["map canvas", bindMapEvents],
  ];
  for (const [name, bind] of steps) {
    try {
      bind();
    } catch (error) {
      console.error(`[boot] "${name}" failed to initialize`, error);
    }
  }

  // 3. Data load last; a failure leaves a recoverable "unavailable" state.
  loadIndex();
});

function bindNavigation() {
  // Native <button> controls: keyboard (Enter/Space) activation works for free.
  const tabs = [...document.querySelectorAll(".view-tab")];
  if (!tabs.length) console.error("[boot] no .view-tab navigation controls found");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => showView(tab.dataset.view || "dashboard"))
  });

  // CTA: open-explorer button – always use document.getElementById directly,
  // never depend on els[] lookup that could be undefined during boot.
  const ctaButton = document.getElementById("open-explorer");
  if (ctaButton) {
    ctaButton.addEventListener("click", () => showView("explorer"));
  } else {
    console.error("[boot] missing control #open-explorer; CTA disabled");
  }
}

function setServerStatus(state, detail = "") {
  const el = els["server-status"];
  if (!el) return;
  el.dataset.state = state;
  const label =
    state === "connected"
      ? "connected · local server"
      : state === "unavailable"
        ? "unavailable · offline data"
        : "connecting…";
  el.classList.toggle("error", state === "unavailable");
  el.innerHTML = `<span class="dot"></span> ${detail ? escapeHtml(detail) : label}`;
}

function showView(name) {
  document.querySelectorAll(".view-tab").forEach((tab) => {
    const active = tab.dataset.view === name;
    tab.classList.toggle("is-active", active);
    tab.setAttribute("aria-selected", active ? "true" : "false");
  });
  document.getElementById("view-dashboard").hidden = name !== "dashboard";
  document.getElementById("view-explorer").hidden = name !== "explorer";
  if (name === "explorer") {
    if (state.observationId) {
      requestAnimationFrame(() => {
        resizeCanvas();
        drawMap();
      });
    } else if (state.index && (state.index.observations || []).length) {
      openObservation(state.index.observations[0].observation_id);
    } else if (!state.index) {
      // API unavailable: say so instead of showing a dead canvas.
      setMapHint("The local application could not list observations. " +
        "Processed outputs are still on disk - retry from the dashboard.");
    } else {
      setMapHint("No processed observations yet. Run " +
        "`python -m nisar_eim process <granule> --id <name>` and reload.");
    }
  }
}

function setMapHint(message) {
  const hint = els["map-hint"];
  if (!hint) return;
  hint.hidden = false;
  hint.textContent = message;
}

async function loadIndex() {
  try {
    setServerStatus("connecting");
    const index = await api("/api/index");
    if (!index || !Array.isArray(index.observations)) {
      throw new Error("unexpected response shape from /api/index (missing 'observations')");
    }
    state.index = index;
    setServerStatus("connected");
    renderDashboard(index);
    populateObservationSelect(index.observations);
    if (index.observations.length && !state.observationId && !document.getElementById("view-explorer").hidden) {
      openObservation(index.observations[0].observation_id);
    }
  } catch (error) {
    state.index = null;
    setServerStatus("unavailable");
    console.error("[index] could not load /api/index", error);
    toast(`Could not reach the local application: ${error.message}`, true);
    renderIndexError(error);
  }
}

function renderIndexError(error) {
  const empty = els["dashboard-empty"];
  if (!empty) return;
  empty.hidden = false;
  const title = empty.querySelector("h4");
  const message = empty.querySelector("p");
  if (title) title.textContent = "The local application is unavailable";
  if (message) {
    message.textContent =
      `${error.message}. Nothing was modified: the processed observations and the raw ` +
      "granule are still on disk, so you can retry without reprocessing anything.";
  }
  if (els["hero-stats"]) {
    els["hero-stats"].innerHTML =
      '<div class="hero-stat"><div class="value">—</div>' +
      '<div class="label">local API unavailable</div>' +
      '<div class="sub">retry to load the observation inventory</div></div>';
  }
  if (!empty.querySelector("[data-retry]")) {
    const retry = document.createElement("button");
    retry.className = "button";
    retry.dataset.retry = "";
    retry.textContent = "Retry connection";
    retry.addEventListener("click", () => {
      retry.disabled = true;
      retry.textContent = "Retrying…";
      loadIndex().finally(() => {
        retry.disabled = false;
        retry.textContent = "Retry connection";
      });
    });
    empty.appendChild(retry);
  }
}

/* ------------------------------------------------------------- dashboard */
function renderDashboard(index) {
  const observations = index.observations || [];
  const hero = els["hero-stats"];
  const realObs = observations.find((o) => !o.is_pre_launch_sample) || observations[0];
  const realCount = observations.filter((o) => !o.is_pre_launch_sample).length;
  const sampleCount = observations.filter((o) => o.is_pre_launch_sample).length;
  const realCoverage = realObs?.phase?.coverage_percent;
  const realInterval = realObs ? `${realObs.temporal_baseline_days ?? 11} days` : "—";
  const eventsInside = observations.reduce(
    (acc, o) => acc + ((o.event_summary && o.event_summary.events_inside_raster_bounds) || 0),
    0
  );

  if (hero) {
    hero.innerHTML = `
    <div class="hero-stat">
      <div class="value">${observations.length}</div>
      <div class="label">Available Observations</div>
      <div class="sub">${realCount} Real NISAR · ${sampleCount} Sample</div>
    </div>
    <div class="hero-stat highlight">
      <div class="value">${realCoverage != null ? pct(realCoverage) : "—"}</div>
      <div class="label">${escapeHtml(realObs ? realObs.observation_id : "real")} Phase Coverage</div>
      <div class="sub">${realObs?.phase ? int(realObs.phase.valid_pixels) : "—"} valid pixels @ 80m</div>
    </div>
    <div class="hero-stat">
      <div class="value">${realInterval}</div>
      <div class="label">Repeat Baseline</div>
      <div class="sub">Track ${realObs?.track_number ?? "—"} · ${realObs ? prettyDate(realObs.reference_start) : ""}</div>
    </div>
    <div class="hero-stat">
      <div class="value">${eventsInside}</div>
      <div class="label">Events in Swath</div>
      <div class="sub">USGS locations checked on raster</div>
    </div>`;
  }

  const cards = els["observation-cards"];
  // One unreadable observation must not take down the whole dashboard.
  cards.innerHTML = observations
    .map((observation) => {
      try {
        return observationCard(observation, index);
      } catch (error) {
        console.error("[dashboard] could not render observation", observation?.observation_id, error);
        return `<article class="card card-error">
          <h4><span>${escapeHtml(observation?.observation_id || "unknown observation")}</span>
            <span class="tag bad">unreadable</span></h4>
          <p class="muted">This observation's metadata could not be displayed: ${escapeHtml(error.message)}.
          Other observations are unaffected; the files on disk were not modified.</p>
        </article>`;
      }
    })
    .join("");
  cards.querySelectorAll("[data-open]").forEach((button) =>
    button.addEventListener("click", () => {
      showView("explorer");
      openObservation(button.dataset.open);
    })
  );
  cards.querySelectorAll("[data-copy-granule]").forEach((button) =>
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      const text = button.dataset.copyGranule;
      if (!text) return;
      copyToClipboard(text, button);
    })
  );
  const empty = els["dashboard-empty"];
  empty.hidden = observations.length > 0;
  if (!empty.hidden) {
    const title = empty.querySelector("h4");
    const message = empty.querySelector("p");
    if (title && !empty.querySelector("[data-retry]")) {
      title.textContent = "No processed observations yet";
    }
    if (message && !empty.querySelector("[data-retry]")) {
      message.textContent =
        "Process a NISAR GUNW granule from the repository root, then reload this page:";
    }
  } else {
    empty.querySelector("[data-retry]")?.remove();
  }

  els["dashboard-limitations"].innerHTML = (index.limitations || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");

  const withEvents = observations.find((o) => o.event_assessment && o.event_assessment.events && o.event_assessment.events.length);
  els["case-strip"].innerHTML = withEvents
    ? withEvents.event_assessment.events
        .map((item) => {
          const event = item.event || {};
          const window = (item.windows || [])[item.windows.length - 1] || {};
          const nearest = item.nearest_valid_pixel || {};
          return `<article class="case-card">
            <div class="case-head">
              <strong>${escapeHtml(event.label || event.id)}</strong>
              <span class="tag ${item.status === "inside_usable" ? "valid" : item.status === "inside_marginal" ? "warn" : "bad"}">${escapeHtml(item.status)}</span>
            </div>
            <p>${escapeHtml(event.place || "")} · ${escapeHtml(prettyDate(event.time_utc))} · M${event.magnitude} ${escapeHtml(event.magnitude_type || "")} · ${event.depth_km} km depth</p>
            <div class="case-metrics">
              <span>inside image footprint <b>${item.inside_product_footprint ? "yes" : "no"}</b></span>
              <span>nearest valid pixel <b>${num(nearest.distance_km, 1)} km</b></span>
              <span>10 km window median coherence <b>${num(window.coherence_median, 2)}</b></span>
              <span>local data usable <b>${item.status === "inside_usable" ? "yes" : "no"}</b></span>
            </div>
            <p>${escapeHtml((item.notes || []).join(" "))}</p>
          </article>`;
        })
        .join("")
    : `<article class="case-card"><div class="case-head"><strong>Event verification runs with processing</strong></div>
        <p>Process a granule to compare its real footprint and local coherence against the independently sourced USGS epicentres. Acquisition dates alone are never treated as evidence.</p></article>`;
}

function observationCard(o, index) {
  const validation = o.validation || {};
  const overall = validation.overall_status || "incomplete";
  const events = o.event_assessment && o.event_assessment.summary;
  const chips = (o.validation_states || [])
    .filter((s) => s.status === "passed")
    .slice(0, 3)
    .map((s) => `<span class="tag valid">${escapeHtml(s.label)}</span>`)
    .join(" ");
  const notValidated = (o.validation_states || []).some(
    (s) => s.id === "scientific_interpretation_validated"
  );
  const granuleId = o.granule_id || "";
  return `<article class="card ${o.is_pre_launch_sample ? "card-sample" : ""}" data-observation-id="${escapeHtml(o.observation_id)}">
    <div class="card-header">
      <div class="card-title-group">
        <h4 class="card-title">${escapeHtml(o.label || o.observation_id)}</h4>
        <div class="card-badges">
          <span class="badge ${o.is_pre_launch_sample ? "badge-sample" : "badge-real"}">${o.is_pre_launch_sample ? "SAMPLE DATA" : "REAL NISAR"}</span>
          <span class="badge-sub">${escapeHtml(o.observation_id)}</span>
        </div>
      </div>
    </div>

    <div class="card-dates-hero">
      <div class="card-date-col">
        <span class="date-lbl">Reference pass</span>
        <span class="date-val">${escapeHtml(prettyDate(o.reference_start))}</span>
        <span class="date-time">${escapeHtml(prettyTime(o.reference_start))}</span>
      </div>
      <div class="date-arrow" aria-hidden="true">→</div>
      <div class="card-date-col">
        <span class="date-lbl">Secondary pass</span>
        <span class="date-val">${escapeHtml(prettyDate(o.secondary_start))}</span>
        <span class="date-time">${escapeHtml(prettyTime(o.secondary_start))}</span>
      </div>
    </div>

    <dl class="card-metrics-grid">
      <div class="metric-item">
        <dt>Phase coverage</dt>
        <dd><span class="metric-highlight">${pct(o.phase.coverage_percent)}</span></dd>
      </div>
      <div class="metric-item">
        <dt>Median coherence</dt>
        <dd><span class="metric-highlight">${num(o.coherence.median, 2)}</span></dd>
      </div>
      <div class="metric-item">
        <dt>Track / Frame</dt>
        <dd>${escapeHtml(o.track_number ?? "—")} / ${escapeHtml(o.frame_number ?? "—")}</dd>
      </div>
      <div class="metric-item">
        <dt>Orbit &amp; Pol</dt>
        <dd>${escapeHtml(o.orbit_pass_direction ?? "—")} · ${escapeHtml(o.polarization ?? "")}</dd>
      </div>
    </dl>

    <div class="card-event-banner">
      <span class="event-icon" aria-hidden="true">📍</span>
      <span class="event-text">${
        events
          ? `${events.footprint_overlaps_any_event ? "Footprint contains reference event" : "No reference event inside footprint"} · ${events.events_with_usable_local_data} usable local data`
          : "Event check not recorded"
      }</span>
    </div>

    <div class="card-chips">${chips}${notValidated ? '<span class="tag warn">interpretation not validated</span>' : ""}</div>

    <div class="card-granule-box">
      <div class="granule-header">
        <span class="granule-label">Granule identifier</span>
        ${granuleId ? `<button type="button" class="btn-copy" data-copy-granule="${escapeHtml(granuleId)}" title="Copy full granule identifier" aria-label="Copy granule identifier for ${escapeHtml(o.observation_id)}">
          <span class="copy-icon" aria-hidden="true">📋</span>
          <span class="copy-text">Copy ID</span>
        </button>` : ""}
      </div>
      <div class="granule-id-text" title="${escapeHtml(granuleId)}">${escapeHtml(granuleId || "—")}</div>
    </div>

    <div class="card-actions">
      <button class="button primary" data-open="${escapeHtml(o.observation_id)}">Open observation explorer</button>
      <a class="button ghost" href="/api/observations/${encodeURIComponent(o.observation_id)}/artifact/report.md" target="_blank" rel="noopener">Scientific report</a>
    </div>
  </article>`;
}

function populateObservationSelect(observations) {
  const select = els["observation-select"];
  if (!select) return;
  if (!observations || !observations.length) {
    select.innerHTML = '<option value="">no processed observations</option>';
    select.disabled = true;
    return;
  }
  select.disabled = false;
  select.innerHTML = observations
    .map((o) => `<option value="${escapeHtml(o.observation_id)}">${escapeHtml(o.observation_id)} · ${escapeHtml(prettyDate(o.reference_start))} → ${escapeHtml(prettyDate(o.secondary_start))}</option>`)
    .join("");
  select.value = observations[0].observation_id;
}

/* -------------------------------------------------------------- explorer */
async function openObservation(observationId) {
  if (!observationId) return;
  state.observationId = observationId;
  state.rawAvailable = true;
  setMapHint("loading observation…");
  els["observation-select"].value = observationId;
  try {
    const payload = await api(`/api/observations/${encodeURIComponent(observationId)}`);
    state.obs = payload;
    map.marker = null;
    map.zoom = 1;
    map.panX = 0;
    map.panY = 0;
    map.layer = "phase";
    map.events = (payload.metadata.event_assessment?.events || []).map((item) => ({
      lon: item.event.longitude,
      lat: item.event.latitude,
      label: item.event.label,
      status: item.status,
      item,
    }));
    renderExplorer(payload);
    await preloadImages(payload);
    await loadCoherencePreview(payload);
    els["map-hint"].hidden = true;
    resizeCanvas();
    drawMap();
  } catch (error) {
    state.observationId = null;
    console.error(`[explorer] could not open ${observationId}`, error);
    setMapHint(
      `Could not open "${observationId}": ${error.message}. ` +
      "Pick another observation, or check `python -m nisar_eim list` from the repository root.",
    );
    toast(`Could not open ${observationId}: ${error.message}`, true);
  }
}

function renderExplorer(payload) {
  const metadata = payload.metadata;
  const summary = payload.observation;
  const source = metadata.source || {};
  const geo = metadata.georeferencing || {};
  const mapView = metadata.map_view || {};
  const grid = mapView.display_grid || null;

  map.bounds = grid ? grid.bounds : null;
  map.imgW = grid ? grid.width : 0;
  map.imgH = grid ? grid.height : 0;
  map.threshold = Number(metadata.quality?.default_coherence_threshold ?? 0.4);
  els["threshold"].value = map.threshold;
  els["threshold-value"].textContent = num(map.threshold, 2);

  els["explorer-toolbar-meta"].textContent = [
    `track ${source.track_number ?? "—"}`,
    `frame ${source.frame_number ?? "—"}`,
    `${(source.orbit_pass_direction || "—").toLowerCase()} pass`,
    `${(source.look_direction || "—").toLowerCase()}-looking`,
    `${source.polarization || ""}`,
    `${geo.pixel_spacing ? geo.pixel_spacing.x : "?"} m posting`,
    `EPSG:${geo.epsg ?? "?"}`,
  ].join(" · ");

  const granuleId = source.granule_id || "";
  els["meta-body"].innerHTML = `
    <div class="meta-granule-box">
      <div class="meta-granule-header">
        <span class="meta-granule-label">Granule ID</span>
        ${granuleId ? `<button type="button" class="btn-copy btn-copy-sm" data-copy-granule="${escapeHtml(granuleId)}" title="Copy full granule identifier" aria-label="Copy full granule identifier">
          <span class="copy-icon" aria-hidden="true">📋</span>
          <span class="copy-text">Copy</span>
        </button>` : ""}
      </div>
      <div class="meta-granule-val" title="${escapeHtml(granuleId)}">${escapeHtml(granuleId || "—")}</div>
    </div>
    <dl>
      <dt>Observation</dt><dd>${escapeHtml(summary.observation_id)}</dd>
      <dt>Reference</dt><dd>${escapeHtml(prettyDate(source.reference_start))}<br>${escapeHtml(prettyTime(source.reference_start))}</dd>
      <dt>Secondary</dt><dd>${escapeHtml(prettyDate(source.secondary_start))}<br>${escapeHtml(prettyTime(source.secondary_start))}</dd>
      <dt>Baseline</dt><dd>${escapeHtml(source.temporal_baseline_days ?? "—")} days</dd>
      <dt>Product</dt><dd>${escapeHtml(source.product_type)} v${escapeHtml(source.product_version)}</dd>
      <dt>Specification</dt><dd>${escapeHtml(source.product_specification_version)}</dd>
      <dt>CRS</dt><dd>${escapeHtml(geo.crs_name)} (EPSG:${escapeHtml(geo.epsg)})</dd>
      <dt>Grid</dt><dd>${int(geo.width)} × ${int(geo.height)} px</dd>
      <dt>Posting</dt><dd>${num(geo.pixel_spacing?.x, 0)} × ${num(geo.pixel_spacing?.y, 0)} m</dd>
      <dt>Axes</dt><dd>x ${escapeHtml(geo.x_axis)}, y ${escapeHtml(geo.y_axis)}</dd>
      <dt>Georeferencing</dt><dd>${escapeHtml(geo.georeferencing_method)}</dd>
      <dt>Phase units</dt><dd>${escapeHtml(metadata.layers?.phase?.units)}</dd>
      <dt>Mask</dt><dd>${escapeHtml(metadata.layers?.mask?.coverage?.encoding || "none")}</dd>
      <dt>File size</dt><dd>${escapeHtml(bytes(source.file_size_bytes))}</dd>
      <dt>Processed</dt><dd>${escapeHtml(prettyDate(metadata.generated_utc))}</dd>
      <dt>DOI</dt><dd>${escapeHtml(source.product_doi || "not available")}</dd>
    </dl>`;

  els["validation-list"].innerHTML = (metadata.validation?.states || [])
    .map(
      (s) => `<li>
        <span class="check-dot ${escapeHtml(s.status)}"></span>
        <span class="check-body"><span class="check-label">${escapeHtml(s.label)}</span>
        ${s.detail ? `<span class="check-detail">${escapeHtml(s.detail)}</span>` : ""}</span>
      </li>`
    )
    .join("");

  const phaseStats = metadata.layers?.phase?.statistics || {};
  const cohStats = metadata.layers?.coherence?.statistics || {};
  const total = phaseStats.total_pixels || 0;
  const valid = phaseStats.measured_pixels || 0;
  const coverage = total ? (100 * valid) / total : 0;
  els["coverage-fill"].style.width = `${Math.max(0, Math.min(100, coverage))}%`;
  els["coverage-label"].textContent = `${pct(coverage)} of the raster has a valid phase measurement (${int(valid)} of ${int(total)} pixels)`;
  els["coverage-grid"].innerHTML = `
    <div><div class="k">water pixels</div><div class="v">${int(metadata.layers?.mask?.coverage?.water_pixels)}</div></div>
    <div><div class="k">iono-filled flagged</div><div class="v">${int(metadata.layers?.mask?.coverage?.ionosphere_filled_pixels)}</div></div>
    <div><div class="k">components</div><div class="v">${int(metadata.layers?.connected_components?.component_count)}</div></div>
    <div><div class="k">largest component</div><div class="v">${pct((metadata.layers?.connected_components?.largest_component_fraction || 0) * 100)}</div></div>`;

  els["layer-stats"].innerHTML = `
    <thead><tr><th>Quantity</th><th>Phase (rad)</th><th>Coherence</th></tr></thead>
    <tbody>
      <tr><td>median</td><td>${num(phaseStats.median, 2)}</td><td>${num(cohStats.median, 3)}</td></tr>
      <tr><td>p05</td><td>${num(phaseStats.p05, 2)}</td><td>${num(cohStats.p05, 3)}</td></tr>
      <tr><td>p95</td><td>${num(phaseStats.p95, 2)}</td><td>${num(cohStats.p95, 3)}</td></tr>
      <tr><td>min</td><td>${num(phaseStats.minimum, 2)}</td><td>${num(cohStats.minimum, 3)}</td></tr>
      <tr><td>max</td><td>${num(phaseStats.maximum, 2)}</td><td>${num(cohStats.maximum, 3)}</td></tr>
    </tbody>`;

  els["event-list"].innerHTML = map.events.length
    ? map.events
        .map((marker, index) => {
          const item = marker.item;
          const window = (item.windows || [])[item.windows.length - 1] || {};
          const nearest = item.nearest_valid_pixel || {};
          const klass =
            item.status === "inside_usable" ? "valid" : item.status === "inside_marginal" ? "warn" : "bad";
          return `<div class="event">
            <div class="event-head">
              <span class="event-title">${escapeHtml(marker.label)}</span>
              <span class="tag ${klass}">${escapeHtml(item.status)}</span>
            </div>
            <div class="event-metrics">
              <span>M${item.event.magnitude}</span>
              <span>inside footprint: ${item.inside_product_footprint ? "yes" : "no"}</span>
              <span>nearest valid: ${num(nearest.distance_km, 1)} km</span>
              <span>coh(10 km): ${num(window.coherence_median, 2)}</span>
            </div>
            ${(item.notes || []).length ? `<div class="event-notes">${escapeHtml(item.notes.join(" "))}</div>` : ""}
            <button class="button ghost" data-locate="${index}">Inspect epicentre</button>
          </div>`;
        })
        .join("")
    : `<p class="muted">No reference events were assessed for this observation.</p>`;
  els["event-list"].querySelectorAll("[data-locate]").forEach((button) =>
    button.addEventListener("click", () => locateEvent(Number(button.dataset.locate)))
  );

  renderThresholdTable(metadata.quality?.threshold_table || [], map.threshold);
  renderExplanations(payload.layer_descriptions || {});
  els["explorer-limitations"].innerHTML = (metadata.limitations || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
  const warnings = metadata.warnings || [];
  els["explorer-warnings"].innerHTML = warnings.length
    ? `<div class="warning-box"><strong>Warnings</strong><br>${warnings
        .map((w) => escapeHtml(w))
        .join("<br>")}</div>`
    : "";
  renderExports(payload);
  els["meta-body"].querySelectorAll("[data-copy-granule]").forEach((button) =>
    button.addEventListener("click", () => {
      const text = button.dataset.copyGranule;
      if (text) copyToClipboard(text, button);
    })
  );
  buildLayerTabs(payload);
  updateLegend();
  updateThresholdStats(map.threshold);
  els["readout"].innerHTML =
    '<span class="readout-muted">Hover the raster to read pixel values; click to pin a location.</span>';
}

function renderThresholdTable(rows, active) {
  const table = els["threshold-table"];
  if (!rows.length) {
    table.innerHTML = "";
    return;
  }
  table.innerHTML = `
    <thead><tr><th>≥</th><th>pixels</th><th>coverage</th><th>coh med</th></tr></thead>
    <tbody>${rows
      .map((row) => {
        const selected = Math.abs(row.threshold - active) < 0.026;
        return `<tr style="${selected ? "background:rgba(70,214,195,0.10)" : ""}">
          <td>${num(row.threshold, 2)}</td>
          <td>${int(row.valid_pixels)}</td>
          <td>${pct(row.coverage_percent)}</td>
          <td>${num(row.coherence_median, 2)}</td>
        </tr>`;
      })
      .join("")}</tbody>`;
}

function renderExplanations(descriptions) {
  els["layer-explanations"].innerHTML = Object.entries(descriptions)
    .map(
      ([key, info]) => `<div class="explain-card">
        <h4>${escapeHtml(info.title)}</h4>
        <div class="units">${escapeHtml(info.units)}</div>
        <p>${escapeHtml(info.meaning)}</p>
        <p class="no">${escapeHtml(info.not_this)}</p>
      </div>`
    )
    .join("");
}

function renderExports(payload) {
  const assets = payload.assets || {};
  const order = [
    ["phase_png", "Phase quicklook (PNG)", "legend, units, source line"],
    ["coherence_png", "Coherence quicklook (PNG)", "legend 0–1, invalid grey"],
    ["phase_tif", "Phase GeoTIFF", "float32 · native grid · NaN NoData"],
    ["coherence_tif", "Coherence GeoTIFF", "float32 · native grid · NaN NoData"],
    ["metadata_json", "Metadata (JSON)", "full provenance and statistics"],
    ["report_md", "Scientific report (MD)", "method, coverage, limits"],
  ];
  els["export-grid"].innerHTML = order
    .filter(([key]) => assets[key])
    .map(
      ([key, label, note]) => `<div class="export-item">
        <a href="${assets[key].url}" download>${escapeHtml(label)}</a>
        <span>${escapeHtml(note)}</span>
      </div>`
    )
    .join("");
}

/* ------------------------------------------------------------------- map */
function bindMapEvents() {
  map.canvas = els["map-canvas"];
  map.ctx = map.canvas.getContext("2d");
  map.wrap = els["canvas-wrap"];
  new ResizeObserver(() => {
    resizeCanvas();
    drawMap();
  }).observe(map.wrap);

  map.canvas.addEventListener("wheel", (event) => {
    if (!state.obs) return;
    event.preventDefault();
    const rect = map.canvas.getBoundingClientRect();
    const px = event.clientX - rect.left;
    const py = event.clientY - rect.top;
    const before = pointToLonLat(px, py);
    const factor = event.deltaY < 0 ? 1.25 : 0.8;
    map.zoom = Math.max(0.6, Math.min(40, map.zoom * factor));
    if (before) {
      const s = fitScale() * map.zoom;
      const ox = (map.canvas.clientWidth - map.imgW * s) / 2 + map.panX;
      const oy = (map.canvas.clientHeight - map.imgH * s) / 2 + map.panY;
      const fx = (before.lon - map.bounds.west) / (map.bounds.east - map.bounds.west);
      const fy = (map.bounds.north - before.lat) / (map.bounds.north - map.bounds.south);
      map.panX = px - fx * map.imgW * s - (map.canvas.clientWidth - map.imgW * s) / 2;
      map.panY = py - fy * map.imgH * s - (map.canvas.clientHeight - map.imgH * s) / 2;
      void ox;
      void oy;
    }
    drawMap();
  }, { passive: false });

  map.canvas.addEventListener("pointerdown", (event) => {
    if (!state.obs) return;
    map.dragging = { x: event.clientX, y: event.clientY, panX: map.panX, panY: map.panY, moved: false };
    map.canvas.setPointerCapture(event.pointerId);
  });
  map.canvas.addEventListener("pointermove", (event) => {
    if (!state.obs) return;
    if (map.dragging) {
      const dx = event.clientX - map.dragging.x;
      const dy = event.clientY - map.dragging.y;
      if (Math.abs(dx) + Math.abs(dy) > 3) map.dragging.moved = true;
      map.panX = map.dragging.panX + dx;
      map.panY = map.dragging.panY + dy;
      drawMap();
      return;
    }
    const rect = map.canvas.getBoundingClientRect();
    const point = pointToLonLat(event.clientX - rect.left, event.clientY - rect.top);
    if (!point) return;
    clearTimeout(state.hoverTimer);
    state.hoverTimer = setTimeout(() => sampleAt(point, false), 170);
  });
  map.canvas.addEventListener("pointerup", (event) => {
    const wasDragging = map.dragging && map.dragging.moved;
    map.dragging = null;
    if (!state.obs || wasDragging) return;
    const rect = map.canvas.getBoundingClientRect();
    const point = pointToLonLat(event.clientX - rect.left, event.clientY - rect.top);
    if (point) sampleAt(point, true);
  });
  map.canvas.addEventListener("pointerleave", () => {
    map.dragging = null;
  });

  document.getElementById("zoom-in").addEventListener("click", () => {
    map.zoom = Math.min(40, map.zoom * 1.3);
    drawMap();
  });
  document.getElementById("zoom-out").addEventListener("click", () => {
    map.zoom = Math.max(0.6, map.zoom / 1.3);
    drawMap();
  });
  document.getElementById("zoom-reset").addEventListener("click", () => {
    map.zoom = 1;
    map.panX = 0;
    map.panY = 0;
    drawMap();
  });
}

function resizeCanvas() {
  if (!map.canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const width = Math.max(1, map.canvas.clientWidth);
  const height = Math.max(1, map.canvas.clientHeight);
  if (map.canvas.width !== Math.round(width * dpr) || map.canvas.height !== Math.round(height * dpr)) {
    map.canvas.width = Math.round(width * dpr);
    map.canvas.height = Math.round(height * dpr);
  }
}

function fitScale() {
  if (!map.imgW || !map.imgH || !map.canvas) return 1;
  const width = map.canvas.clientWidth;
  const height = map.canvas.clientHeight;
  return Math.min(width / map.imgW, height / map.imgH) * 0.97;
}

function mapScale() {
  return fitScale() * map.zoom;
}

function mapOrigin(scale) {
  const width = map.canvas.clientWidth;
  const height = map.canvas.clientHeight;
  return [
    (width - map.imgW * scale) / 2 + map.panX,
    (height - map.imgH * scale) / 2 + map.panY,
  ];
}

function pointToLonLat(px, py) {
  if (!map.bounds || !map.imgW) return null;
  const scale = mapScale();
  const [ox, oy] = mapOrigin(scale);
  const fx = (px - ox) / (map.imgW * scale);
  const fy = (py - oy) / (map.imgH * scale);
  if (fx < 0 || fx > 1 || fy < 0 || fy > 1) return null;
  return {
    lon: map.bounds.west + fx * (map.bounds.east - map.bounds.west),
    lat: map.bounds.north - fy * (map.bounds.north - map.bounds.south),
    fx,
    fy,
  };
}

function lonLatToCanvas(lon, lat) {
  const scale = mapScale();
  const [ox, oy] = mapOrigin(scale);
  const fx = (lon - map.bounds.west) / (map.bounds.east - map.bounds.west);
  const fy = (map.bounds.north - lat) / (map.bounds.north - map.bounds.south);
  return [ox + fx * map.imgW * scale, oy + fy * map.imgH * scale];
}

function drawMap() {
  if (!map.ctx || !state.obs || !map.bounds) return;
  const ctx = map.ctx;
  const dpr = window.devicePixelRatio || 1;
  const width = map.canvas.clientWidth;
  const height = map.canvas.clientHeight;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  const scale = mapScale();
  const [ox, oy] = mapOrigin(scale);
  const img = map.images[map.layer];
  if (img) {
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(img, ox, oy, map.imgW * scale, map.imgH * scale);
    ctx.imageSmoothingEnabled = true;
  }
  if (map.overlay && map.overlayEnabled && (map.layer === "phase" || map.layer === "coherence")) {
    ctx.globalAlpha = 0.62;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(map.overlay, ox, oy, map.imgW * scale, map.imgH * scale);
    ctx.imageSmoothingEnabled = true;
    ctx.globalAlpha = 1;
  }
  drawFootprint(ctx, scale, ox, oy);
  drawGraticule(ctx, width, height);
  drawEvents(ctx);
  drawMarker(ctx);
  drawScaleBar(ctx, width, height);
}

function drawFootprint(ctx, scale, ox, oy) {
  const footprint = state.obs?.metadata?.georeferencing?.footprint;
  const polygon =
    footprint?.product_bounding_polygon?.coordinates || footprint?.grid_extent?.coordinates;
  if (!polygon) return;
  ctx.save();
  ctx.strokeStyle = "rgba(232,238,245,0.55)";
  ctx.lineWidth = 1.1;
  ctx.setLineDash([5, 4]);
  ctx.beginPath();
  polygon.forEach(([lon, lat], i) => {
    const [x, y] = lonLatToCanvas(lon, lat);
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.closePath();
  ctx.stroke();
  ctx.restore();
}

function drawGraticule(ctx, width, height) {
  if (!map.bounds) return;
  const steps = 5;
  ctx.save();
  ctx.font = "10px ui-monospace, monospace";
  ctx.fillStyle = "rgba(147,162,179,0.85)";
  ctx.strokeStyle = "rgba(147,162,179,0.12)";
  ctx.lineWidth = 1;
  for (let i = 0; i <= steps; i += 1) {
    const lon = map.bounds.west + ((map.bounds.east - map.bounds.west) * i) / steps;
    const [x] = lonLatToCanvas(lon, map.bounds.north);
    if (x < -20 || x > width + 20) continue;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, height);
    ctx.stroke();
    ctx.fillText(`${lon.toFixed(2)}°`, Math.min(width - 42, Math.max(3, x + 3)), height - 6);
  }
  for (let i = 0; i <= steps; i += 1) {
    const lat = map.bounds.north - ((map.bounds.north - map.bounds.south) * i) / steps;
    const [, y] = lonLatToCanvas(map.bounds.west, lat);
    if (y < -20 || y > height + 20) continue;
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(width, y);
    ctx.stroke();
    ctx.fillText(`${lat.toFixed(2)}°`, 5, Math.min(height - 4, Math.max(10, y - 4)));
  }
  ctx.restore();
}

function drawEvents(ctx) {
  if (!map.bounds) return;
  map.events.forEach((marker) => {
    const [x, y] = lonLatToCanvas(marker.lon, marker.lat);
    const colour =
      marker.status === "inside_usable" ? "#62d29b" : marker.status === "inside_marginal" ? "#f2b558" : "#f07878";
    ctx.save();
    ctx.strokeStyle = colour;
    ctx.fillStyle = "rgba(7,9,12,0.65)";
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.arc(x, y, 5.5, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(x - 9, y);
    ctx.lineTo(x + 9, y);
    ctx.moveTo(x, y - 9);
    ctx.lineTo(x, y + 9);
    ctx.stroke();
    ctx.font = "10px ui-monospace, monospace";
    ctx.fillStyle = colour;
    ctx.fillText(marker.label, x + 11, y - 6);
    ctx.restore();
  });
}

function drawMarker(ctx) {
  if (!map.marker || !map.bounds) return;
  const [x, y] = lonLatToCanvas(map.marker.lon, map.marker.lat);
  ctx.save();
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 1.2;
  ctx.beginPath();
  ctx.arc(x, y, 7, 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(x - 12, y);
  ctx.lineTo(x - 8, y);
  ctx.moveTo(x + 8, y);
  ctx.lineTo(x + 12, y);
  ctx.moveTo(x, y - 12);
  ctx.lineTo(x, y - 8);
  ctx.moveTo(x, y + 8);
  ctx.lineTo(x, y + 12);
  ctx.stroke();
  ctx.restore();
}

function drawScaleBar(ctx, width, height) {
  if (!map.bounds) return;
  const midLat = (map.bounds.north + map.bounds.south) / 2;
  const kmPerDegLat = 110.574;
  const totalKm = (map.bounds.north - map.bounds.south) * kmPerDegLat;
  const kmPerPixel = totalKm / (map.imgH * mapScale());
  const candidates = [5, 10, 25, 50, 100, 200];
  let chosen = candidates[candidates.length - 1];
  for (const candidate of candidates) {
    if (candidate / kmPerPixel < width * 0.3) {
      chosen = candidate;
      break;
    }
  }
  const lengthPx = chosen / kmPerPixel;
  const x = 14;
  const y = height - 26;
  ctx.save();
  ctx.strokeStyle = "rgba(232,238,245,0.85)";
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.moveTo(x, y);
  ctx.lineTo(x + lengthPx, y);
  ctx.moveTo(x, y - 5);
  ctx.lineTo(x, y + 5);
  ctx.moveTo(x + lengthPx, y - 5);
  ctx.lineTo(x + lengthPx, y + 5);
  ctx.stroke();
  ctx.fillStyle = "rgba(232,238,245,0.9)";
  ctx.font = "10px ui-monospace, monospace";
  ctx.fillText(`${chosen} km`, x + lengthPx / 2 - 14, y - 8);
  ctx.fillStyle = "rgba(147,162,179,0.8)";
  ctx.fillText(`≈ ${kmPerPixel.toFixed(1)} km / display px`, x, y - 22);
  void midLat;
  ctx.restore();
}

async function preloadImages(payload) {
  map.images = {};
  const images = payload.map?.images || {};
  const entries = Object.entries(images);
  await Promise.all(
    entries.map(
      ([key, info]) =>
        new Promise((resolve) => {
          const img = new Image();
          img.onload = () => {
            map.images[key] = img;
            resolve();
          };
          img.onerror = () => resolve();
          img.src = info.url;
        })
    )
  );
}

async function loadCoherencePreview(payload) {
  map.coherence = null;
  map.overlay = null;
  const preview = payload.map?.coherence_preview;
  if (!preview || !preview.url) return;
  try {
    const response = await fetch(preview.url);
    if (!response.ok) return;
    const buffer = await response.arrayBuffer();
    map.coherence = { data: new Uint8Array(buffer), width: preview.width, height: preview.height };
    buildOverlay();
  } catch (error) {
    console.warn("coherence preview unavailable", error);
  }
}

function buildOverlay() {
  if (!map.coherence) {
    map.overlay = null;
    return;
  }
  const { data, width, height } = map.coherence;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  const image = ctx.createImageData(width, height);
  const pixels = image.data;
  const threshold = map.threshold;
  for (let i = 0; i < data.length; i += 1) {
    const value = data[i];
    if (value === 255) continue; // invalid / outside swath
    if (value / 200 < threshold) {
      const p = i * 4;
      pixels[p] = 240;
      pixels[p + 1] = 108;
      pixels[p + 2] = 108;
      pixels[p + 3] = 145;
    }
  }
  ctx.putImageData(image, 0, 0);
  map.overlay = canvas;
}

/* --------------------------------------------------------------- sampling */
async function sampleAt(point, pin) {
  if (!state.obs) return;
  const token = ++state.sampleToken;
  const url = `/api/observations/${encodeURIComponent(state.observationId)}/sample?lon=${point.lon.toFixed(6)}&lat=${point.lat.toFixed(6)}`;
  try {
    const response = await fetch(url);
    const data = await response.json();
    if (token !== state.sampleToken) return;
    if (!response.ok) {
      showReadoutError(data);
      return;
    }
    renderReadout(data, pin);
    if (pin) {
      map.marker = { lon: data.lon, lat: data.lat, row: data.row, col: data.col };
      drawMap();
    }
  } catch (error) {
    if (token !== state.sampleToken) return;
    showReadoutError({ message: "Local server did not answer the pixel query." });
  }
}

function renderReadout(data, pinned) {
  const valid = data.valid;
  const mask = data.mask || {};
  els["readout"].innerHTML = `
    <span>${pinned ? "<b>pinned</b>" : "cursor"}</span>
    <span>lon <b>${num(data.lon, 5)}</b> lat <b>${num(data.lat, 5)}</b></span>
    <span>row <b>${int(data.row)}</b> col <b>${int(data.col)}</b></span>
    <span>phase <b>${num(data.phase_radians, 3)}</b> rad</span>
    <span>coherence <b>${num(data.coherence, 3)}</b></span>
    <span>component <b>${data.connected_component ?? "—"}</b></span>
    <span class="${valid ? "ok" : "bad"}">${valid ? "valid measurement" : "invalid / no data"}</span>
    <span>${mask.water ? "water" : "land"}${mask.reference_subswath ? ` · subswath ${mask.reference_subswath}/${mask.secondary_subswath}` : ""}${mask.ionosphere_filled ? " · iono-filled" : ""}</span>
    <span>${data.window ? `window coh med <b>${num(data.window.coherence_median, 2)}</b>` : ""}</span>`;
}

function showReadoutError(payload) {
  const message = payload && (payload.error || payload.message) ? payload.error || payload.message : "Pixel query failed.";
  if (/raw granule is not available/i.test(message)) state.rawAvailable = false;
  els["readout"].innerHTML = `<span class="bad">${escapeHtml(message)}</span>`;
}

function locateEvent(index) {
  const marker = map.events[index];
  if (!marker) return;
  const scale = mapScale();
  const fx = (marker.lon - map.bounds.west) / (map.bounds.east - map.bounds.west);
  const fy = (map.bounds.north - marker.lat) / (map.bounds.north - map.bounds.south);
  map.panX = (0.5 - fx) * map.imgW * scale;
  map.panY = (0.5 - fy) * map.imgH * scale;
  drawMap();
  sampleAt({ lon: marker.lon, lat: marker.lat }, true);
}

/* ------------------------------------------------------------- thresholds */
async function updateThresholdStats(threshold) {
  if (!state.observationId) return;
  try {
    const data = await api(
      `/api/observations/${encodeURIComponent(state.observationId)}/threshold?value=${threshold}`
    );
    els["threshold-stats"].textContent =
      `≥ ${num(data.threshold, 2)}: ${int(data.valid_pixels)} px · ${pct(data.coverage_percent)} of raster · median phase ${num(data.phase_median, 1)} rad`;
    renderThresholdTable(data.table || [], threshold);
  } catch (error) {
    els["threshold-stats"].textContent = "threshold statistics unavailable";
  }
}

/* ---------------------------------------------------------------- legends */
function buildLayerTabs(payload) {
  const available = Object.keys(payload.map?.images || {});
  const labels = {
    phase: "Phase (rad)",
    coherence: "Coherence",
    quality: "Quality mask",
    connected_components: "Components",
  };
  els["layer-tabs"].innerHTML = Object.keys(labels)
    .map(
      (key) =>
        `<button class="layer-tab ${key === map.layer ? "is-active" : ""}" data-layer="${key}" ${
          available.includes(key) ? "" : "disabled"
        }>${labels[key]}</button>`
    )
    .join("");
  els["layer-tabs"].querySelectorAll("[data-layer]").forEach((button) =>
    button.addEventListener("click", () => {
      if (button.disabled) return;
      map.layer = button.dataset.layer;
      els["layer-tabs"].querySelectorAll("[data-layer]").forEach((b) =>
        b.classList.toggle("is-active", b.dataset.layer === map.layer)
      );
      updateLegend();
      drawMap();
    })
  );
}

function updateLegend() {
  const legends = state.obs?.metadata?.map_view?.legends || {};
  const info = legends[map.layer];
  const badge = els["map-badge"];
  if (!info) {
    els["legend"].innerHTML = "";
    badge.textContent = "";
    return;
  }
  badge.textContent = `${(state.obs?.metadata?.source?.polarization || "")} · ${prettyDate(
    state.obs?.metadata?.source?.reference_start
  )} → ${prettyDate(state.obs?.metadata?.source?.secondary_start)}`;
  if (info.stops) {
    const gradient = info.stops.map((s) => `${s.hex} ${(s.t * 100).toFixed(0)}%`).join(", ");
    const vmin = info.vmin ?? 0;
    const vmax = info.vmax ?? 1;
    const mid = (vmin + vmax) / 2;
    const ticks =
      map.layer === "connected_components"
        ? `<div class="legend-ticks"><span>labels cycle</span><span>${info.label_count ?? "?"} labels</span></div>`
        : `<div class="legend-ticks"><span>${num(vmin, 2)}</span><span>${num(mid, 2)}</span><span>${num(vmax, 2)}</span></div>`;
    const clip =
      info.saturated_low_pixels || info.saturated_high_pixels
        ? `<span class="muted">display clips ${int(info.saturated_low_pixels)} low / ${int(info.saturated_high_pixels)} high values</span>`
        : "";
    els["legend"].innerHTML = `
      <span class="legend-title">${escapeHtml(info.label)}</span>
      <div>
        <div class="legend-bar" style="background:linear-gradient(90deg, ${gradient})"></div>
        ${ticks}
      </div>
      ${info.extend === "both" ? '<span class="muted">arrow ends: values beyond display range</span>' : ""}
      ${clip}`;
  } else {
    const swatches = (info.classes || [])
      .map(
        (c) =>
          `<span><span class="legend-swatch" style="background:${c.color === "transparent" ? "transparent" : c.color}"></span>${escapeHtml(c.label)}</span>`
      )
      .join("");
    els["legend"].innerHTML = `<span class="legend-title">${escapeHtml(info.label)}</span>${swatches}`;
  }
}
