const $ = (s) => document.querySelector(s);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
let items = [],
  selected = new Set(),
  preview = null,
  activeDetail = null;
const api = async (url, options = {}) => {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok)
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "Please check the fields and try again.",
    );
  return body;
};
const json = (method, data) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});
function message(text, error = false) {
  const node = $("#message");
  node.textContent = text;
  node.classList.toggle("error", error);
  node.hidden = false;
  document.querySelectorAll(".dialog-error").forEach((n) => n.remove());
  if (error) {
    const open = document.querySelector("dialog[open]");
    if (open) {
      const p = document.createElement("p");
      p.className = "dialog-error message error";
      p.textContent = text;
      open.prepend(p);
    }
  }
}
const safe = (fn) => async (event) => {
  try {
    await fn(event);
  } catch (error) {
    message(error.message, true);
  }
};
const bytes = (n) =>
  n >= 1024 ** 3
    ? `${(n / 1024 ** 3).toFixed(1)} GB`
    : `${(n / 1024 ** 2).toFixed(1)} MB`;
function selectedItems() {
  return items.filter((i) => selected.has(i.id));
}
function selectionState() {
  $("#selection-count").textContent = `${selected.size} selected`;
  $("#preview-batch").disabled = selected.size === 0;
  const refs = selectedItems();
  $("#open-brief").disabled =
    !refs.length || refs.length > 5 || refs.some((i) => !i.study);
}
function visibleItems() {
  const q = $("#search").value.trim().toLowerCase(),
    status = $("#status-filter").value,
    collection = $("#collection-filter").value;
  return items.filter(
    (i) =>
      (!q || JSON.stringify(i).toLowerCase().includes(q)) &&
      (!status || i.status === status) &&
      (!collection || i.collections.includes(collection)),
  );
}
function render() {
  $("#total").textContent = items.length;
  $("#nav-count").textContent = items.length;
  $("#ready").textContent = items.filter((i) => i.study).length;
  $("#queued").textContent = items.filter((i) => !i.study).length;
  const visible = visibleItems();
  $("#empty").hidden = items.length > 0;
  $("#library-grid").innerHTML = visible
    .map(
      (i) =>
        `<article class="card ${selected.has(i.id) ? "selected" : ""}"><label class="card-check"><input type="checkbox" data-select="${i.id}" aria-label="Select ${esc(i.title)}" ${selected.has(i.id) ? "checked" : ""}></label><div class="card-cover">${i.media && i.study?.frames?.some((f) => f.file) ? `<img src="/api/items/${i.id}/frames/${encodeURIComponent(i.study.frames.find((f) => f.file).file)}" alt="Sampled video frame" loading="lazy">` : `<span class="cover-type">${i.url ? "↗" : "▶"}</span>`}<button data-open="${i.id}" aria-label="Open ${esc(i.title)}"></button></div><div class="card-body"><span class="badge ${i.status}">${i.status === "failed" ? "Needs attention" : i.status === "ready" ? "Ready to study" : i.status}</span><h3>${esc(i.title)}</h3><p>${esc(i.study?.topics?.join(" · ") || i.collections.join(" · ") || "Uncategorized reference")}</p>${i.error ? `<p class="card-error">${esc(i.error)}</p>` : ""}<p>${i.study ? `${i.study.observations.length} observations · ${Math.round(i.study.duration_s)}s` : "Select to start a study"}${i.study && !i.media ? " · Media removed" : ""}</p></div></article>`,
    )
    .join("");
  if (items.length && !visible.length)
    $("#library-grid").innerHTML =
      '<p class="muted">No references match these filters.</p>';
  selectionState();
}
async function refresh() {
  const fresh = await api("/api/items");
  if (JSON.stringify(fresh) === JSON.stringify(items)) return;
  items = fresh;
  const old = $("#collection-filter").value;
  const collections = [...new Set(items.flatMap((i) => i.collections))].sort();
  $("#collection-filter").innerHTML =
    '<option value="">All collections</option>' +
    collections.map((c) => `<option>${esc(c)}</option>`).join("");
  $("#collection-filter").value = collections.includes(old) ? old : "";
  render();
}
async function switchView(view) {
  document
    .querySelectorAll(".nav")
    .forEach((n) => n.classList.toggle("active", n.dataset.view === view));
  ["library", "briefs", "profile"].forEach(
    (v) => ($(`#${v}-view`).hidden = v !== view),
  );
  $("#page-title").innerHTML =
    {
      library: "Your creative library",
      briefs: "Your next ideas",
      profile: "Your creator profile",
    }[view] + "<span>.</span>";
  $("#page-subtitle").textContent = {
    library: "Understand the hook. Find the pattern. Make it your own.",
    briefs: "Original directions, grounded in the references you chose.",
    profile: "A consistent starting point. Room to change direction.",
  }[view];
  if (view === "briefs") await showBriefs();
  if (view === "profile") {
    const p = await api("/api/profile");
    Object.entries(p).forEach(
      ([k, v]) => ($("#profile-form").elements[k].value = v),
    );
  }
}
function openImport() {
  $("#import-dialog").showModal();
}
$("#open-import").onclick = openImport;
$("#empty-import").onclick = openImport;
document
  .querySelectorAll(".close")
  .forEach((b) => (b.onclick = () => b.closest("dialog").close()));
document
  .querySelectorAll(".nav")
  .forEach((b) => (b.onclick = safe(() => switchView(b.dataset.view))));
["#search", "#status-filter", "#collection-filter"].forEach((s) =>
  $(s).addEventListener("input", render),
);
$("#library-grid").onclick = safe(async (e) => {
  const b = e.target.closest("[data-open]");
  if (b) await showDetail(b.dataset.open);
});
$("#library-grid").onchange = (e) => {
  const id = e.target.dataset.select;
  if (!id) return;
  e.target.checked ? selected.add(id) : selected.delete(id);
  render();
};
$("#select-all").onchange = (e) => {
  visibleItems().forEach((i) =>
    e.target.checked ? selected.add(i.id) : selected.delete(i.id),
  );
  render();
};
$("#import-form").onsubmit = safe(async (e) => {
  e.preventDefault();
  const added = await api(
    "/api/import",
    json("POST", { text: $("#import-text").value }),
  );
  $("#import-dialog").close();
  $("#import-text").value = "";
  await refresh();
  message(
    `${added.length} references added or matched. Select a batch to study.`,
  );
});
$("#export-file").onchange = safe(async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  if (file.size > 10_000_000)
    throw new Error(
      "Export is larger than 10 MB. Split it into smaller URL lists.",
    );
  const added = await api(
    "/api/import",
    json("POST", { text: await file.text() }),
  );
  $("#import-dialog").close();
  e.target.value = "";
  await refresh();
  message(`${added.length} references found. No downloads started.`);
});
async function upload(file, itemId) {
  const body = new FormData();
  body.append("file", file);
  return api("/api/upload" + (itemId ? `?item_id=${itemId}` : ""), {
    method: "POST",
    body,
  });
}
$("#video-files").onchange = safe(async (e) => {
  let n = 0;
  for (const file of e.target.files) {
    await upload(file);
    n++;
  }
  $("#import-dialog").close();
  e.target.value = "";
  await refresh();
  message(`${n} local videos added. Select them to start studying.`);
});
$("#preview-batch").onclick = () => {
  preview = null;
  $("#batch-summary").textContent = "";
  $("#run-batch").disabled = true;
  $("#batch-dialog").showModal();
};
function invalidatePreview() {
  preview = null;
  $("#run-batch").disabled = true;
  $("#batch-summary").textContent =
    "Calculate a new preview for these settings.";
}
$("#provider").onchange = () => {
  $("#paid-fields").hidden = $("#provider").value !== "apify";
  invalidatePreview();
};
$("#unit-cost").oninput = invalidatePreview;
$("#batch-cap").oninput = invalidatePreview;
$("#refresh-preview").onclick = safe(async () => {
  const paid = $("#provider").value === "apify";
  preview = await api(
    "/api/batches/preview",
    json("POST", {
      ids: [...selected],
      provider: $("#provider").value,
      unit_cost: paid ? Number($("#unit-cost").value) : null,
      cap: paid ? Number($("#batch-cap").value) : null,
    }),
  );
  $("#batch-summary").innerHTML =
    `<b>${preview.ids.length} to study · ${preview.remote_count} downloads · ${preview.skipped} already complete</b><p>Estimated API charge: $${preview.estimated_usd.toFixed(4)}${preview.paid ? ` · Maximum batch charge: $${preview.cap_usd.toFixed(2)}` : ""}</p><ul>${preview.items.map((i) => `<li>${esc(i.title)}</li>`).join("")}</ul><p class="muted">${preview.paid ? "Approval applies only to this batch. A retry requires a new review." : "No paid fallback. Unavailable reels can be attached as local videos."}</p>`;
  $("#run-batch").disabled = !preview.ids.length;
  $("#run-batch").textContent = preview.paid
    ? `Approve up to $${preview.cap_usd.toFixed(2)} and start`
    : "Start reviewed batch";
});
$("#run-batch").onclick = safe(async () => {
  if (!preview) return;
  $("#run-batch").disabled = true;
  await api(
    "/api/batches/run",
    json("POST", { preview_id: preview.id, approve_cost: preview.paid }),
  );
  $("#batch-dialog").close();
  message("Batch started. You can follow each reference in the library.");
  await refresh();
});
async function showDetail(id) {
  activeDetail = id;
  const i = await api(`/api/items/${id}`),
    s = i.study;
  $("#detail-content").innerHTML =
    `<div class="detail-grid"><div class="detail-side">${i.media ? `<video id="player" controls preload="metadata" src="/api/items/${id}/media"></video>` : '<p class="muted">Local video is not retained.</p>'}${i.url ? `<a href="${esc(i.url)}" target="_blank" rel="noopener noreferrer">View original on Instagram ↗</a>` : ""}${i.media ? '<button id="delete-media">Delete retained media</button>' : ""}${!s || !i.media ? '<label class="file-button">Attach original local video<input id="attach-video" type="file" accept="video/*"></label>' : ""}<p class="muted">Deleting media preserves the study and original link. Frame images are removed too.</p>${s ? `<details><summary>Transcript</summary>${s.transcript.map((t) => `<button class="evidence" data-time="${t.start}">${t.start.toFixed(1)}s · ${esc(t.text)}</button>`).join("") || "<p>No speech transcript available.</p>"}</details>` : ""}</div><div><span class="badge ${i.status}">${esc(i.status)}</span><h2>${esc(i.title)}</h2>${i.error ? `<p class="message error">${esc(i.error)}</p>` : ""}${s ? `<p class="muted">Draft analysis · Verify observations against the source. All explanations of effectiveness, including those within observations, are hypotheses.</p>${s.observations.map((o) => `<div class="observation"><h4>${esc(o.aspect.replaceAll("_", " "))}</h4><p>${esc(o.text)}</p>${o.evidence.map((e) => `<button class="evidence" ${e.t !== null ? `data-time="${e.t}"` : ""}>${esc(e.source)}${e.t !== null ? ` · ${e.t.toFixed(1)}s` : ""}${e.quote ? ` · “${esc(e.quote)}”` : ""}</button>`).join("")}</div>`).join("")}<div class="hypotheses"><b>Effectiveness hypotheses</b>${s.hypotheses.map((h) => `<p>${esc(h)}</p>`).join("")}<p class="muted">These interpretations do not establish what caused engagement.</p></div><h3>Find related references</h3><div class="similar-controls"><button data-mode="subject">Same subject</button><button data-mode="creative">Similar creative approach</button></div><div id="similar-list" class="similar-list"></div>` : "<p>Select this reference in the library, then choose Study selected. If acquisition fails, attach a local video or retry with a new batch preview.</p>"}</div></div>`;
  if (!$("#detail-dialog").open) $("#detail-dialog").showModal();
  if ($("#delete-media"))
    $("#delete-media").onclick = safe(async () => {
      if (
        !confirm(
          "Delete this retained video and frame images? The study and source link will remain.",
        )
      )
        return;
      await api(`/api/items/${id}/media`, { method: "DELETE" });
      await showDetail(id);
      await refresh();
    });
  if ($("#attach-video"))
    $("#attach-video").onchange = safe(async (e) => {
      if (e.target.files[0]) {
        await upload(e.target.files[0], id);
        await showDetail(id);
        await refresh();
      }
    });
}
$("#detail-content").onclick = safe(async (e) => {
  const time = e.target.closest("[data-time]");
  if (time && $("#player")) {
    $("#player").currentTime = Number(time.dataset.time);
    $("#player")
      .play()
      .catch(() => {});
  }
  const mode = e.target.closest("[data-mode]");
  if (mode) {
    const rows = await api(
      `/api/items/${activeDetail}/similar?mode=${mode.dataset.mode}`,
    );
    $("#similar-list").innerHTML =
      rows
        .map(
          (r) =>
            `<button data-related="${r.item.id}">${esc(r.item.title)}<small>${esc(r.reason)}</small></button>`,
        )
        .join("") ||
      '<p class="muted">No matching studies yet. Analyze more references to compare.</p>';
  }
  const related = e.target.closest("[data-related]");
  if (related) await showDetail(related.dataset.related);
});
$("#profile-form").onsubmit = safe(async (e) => {
  e.preventDefault();
  await api(
    "/api/profile",
    json("PUT", Object.fromEntries(new FormData(e.target))),
  );
  message("Creator profile saved.");
});
$("#open-brief").onclick = () => {
  $("#brief-selection").textContent =
    `Using ${selected.size} completed references. Saved profile values apply unless overridden below.`;
  $("#brief-dialog").showModal();
};
$("#brief-form").onsubmit = safe(async (e) => {
  e.preventDefault();
  const form = e.target,
    button = form.querySelector("button"),
    data = Object.fromEntries(new FormData(form));
  const topic = data.topic;
  delete data.topic;
  const overrides = Object.fromEntries(
    Object.entries(data).filter(([, v]) => v.trim()),
  );
  button.disabled = true;
  button.textContent = "Generating locally…";
  try {
    await api(
      "/api/briefs",
      json("POST", { ids: [...selected], topic, overrides }),
    );
    $("#brief-dialog").close();
    await switchView("briefs");
    message(
      "Brief saved. Review the direction and references before using it.",
    );
  } finally {
    button.disabled = false;
    button.textContent = "Generate original brief";
  }
});
async function showBriefs() {
  const briefs = await api("/api/briefs");
  $("#brief-list").innerHTML = briefs.length
    ? briefs
        .map(
          (b) =>
            `<article class="brief-card"><span class="eyebrow">ORIGINAL CONTENT DIRECTION · DRAFT</span><h2>${esc(b.title)}</h2><p class="muted">${esc(b.profile.audience)} · ${esc(b.profile.format)}</p><h3>Three ways to open</h3><ol>${b.hooks.map((h) => `<li>${esc(h)}</li>`).join("")}</ol><h3>Beat outline</h3><ol>${b.beats.map((x) => `<li>${esc(x)}</li>`).join("")}</ol><h3>Visual suggestions</h3><ul>${b.visuals.map((x) => `<li>${esc(x)}</li>`).join("")}</ul><h3>Your references</h3><p class="muted">Reference rationales are model hypotheses, not proof of effectiveness.</p>${b.references.map((r) => `<button class="reference-link" data-ref="${r.id}">${esc(r.title)} ↗<small>${esc(r.reason)}</small></button>`).join("")}</article>`,
        )
        .join("")
    : '<div class="empty"><span class="eyebrow">START WITH SOMETHING THAT INSPIRES YOU</span><h2>Your next idea starts<br>with a few references.</h2><p>Select up to five completed studies in your library,<br>then choose Create a brief.</p></div>';
}
$("#brief-list").onclick = safe(async (e) => {
  const b = e.target.closest("[data-ref]");
  if (b) await showDetail(b.dataset.ref);
});
async function poll() {
  try {
    const state = await api("/api/status");
    $("#storage").textContent =
      `${bytes(state.media_bytes)} media · ${bytes(state.free_bytes)} free`;
    $("#processing-status").textContent = state.running
      ? "Processing locally…"
      : "Local workspace";
    await refresh();
    if ($("#message").textContent === "Cannot reach the local server. Restart it and refresh this page.") {
      $("#message").hidden = true;
    }
  } catch (error) {
    message(
      "Cannot reach the local server. Restart it and refresh this page.",
      true,
    );
  }
}
safe(async () => {
  await refresh();
  await poll();
})();
setInterval(poll, 5000);
