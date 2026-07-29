const form = document.getElementById("job-form");
const submitBtn = document.getElementById("submit-btn");
const formError = document.getElementById("form-error");
const jobList = document.getElementById("job-list");

const activePollers = new Set();

function percentFor(job) {
  const { state, scene_done = 0, scene_total = 0 } = job;
  if (state === "queued") return 1;
  if (state === "preparing_audio") return 3;
  if (state === "narration") {
    const frac = scene_total ? scene_done / scene_total : 0;
    return 5 + frac * 75; // narration is the slow part - most of the bar
  }
  if (state === "rendering") {
    const frac = scene_total ? scene_done / scene_total : 0;
    return 80 + frac * 18;
  }
  if (state === "done") return 100;
  return 0;
}

function statusText(job) {
  switch (job.state) {
    case "queued": return "Queued...";
    case "preparing_audio": return "Cleaning up reference audio...";
    case "narration": return `Generating narration - scene ${job.scene_done}/${job.scene_total}`;
    case "rendering": return `Rendering video - scene ${job.scene_done}/${job.scene_total}`;
    case "done": return `Done - ${job.duration_seconds ? Math.round(job.duration_seconds) + "s" : ""}`;
    case "error": return `Error: ${job.error || "unknown error"}`;
    default: return job.state;
  }
}

function renderJobEl(el, job) {
  const fill = el.querySelector(".progress-fill");
  const status = el.querySelector(".job-status");
  const actions = el.querySelector(".job-actions");

  const pct = percentFor(job);
  fill.style.width = pct + "%";
  if (job.state === "error") fill.style.background = "#e05a56";

  status.textContent = statusText(job);

  if (job.state === "done") {
    actions.innerHTML = `
      <a href="/jobs/${job.id}/video" download>Download MP4</a>
      <button data-delete="${job.id}">Delete</button>
    `;
    if (!actions.querySelector("video")) {
      const v = document.createElement("video");
      v.src = `/jobs/${job.id}/video`;
      v.controls = true;
      el.appendChild(v);
    }
  } else if (job.state === "error") {
    actions.innerHTML = `<button data-delete="${job.id}">Delete</button>`;
  }
}

async function pollJob(jobId) {
  if (activePollers.has(jobId)) return;
  activePollers.add(jobId);

  const tick = async () => {
    try {
      const res = await fetch(`/jobs/${jobId}`);
      if (!res.ok) { activePollers.delete(jobId); return; }
      const job = await res.json();
      let el = jobList.querySelector(`[data-job-id="${jobId}"]`);
      if (!el) el = addJobElement(job);
      renderJobEl(el, job);
      if (job.state === "done" || job.state === "error") {
        activePollers.delete(jobId);
        return;
      }
      setTimeout(tick, 2000);
    } catch (e) {
      setTimeout(tick, 4000);
    }
  };
  tick();
}

function addJobElement(job) {
  const el = document.createElement("div");
  el.className = "job";
  el.dataset.jobId = job.id;
  el.innerHTML = `
    <div class="job-header">
      <strong>${job.title || "(untitled)"}</strong>
      <span class="job-time">${job.created_at || ""}</span>
    </div>
    <div class="progress-track"><div class="progress-fill" style="width:0%"></div></div>
    <div class="job-status">-</div>
    <div class="job-actions"></div>
  `;
  jobList.prepend(el);
  return el;
}

// Poll every existing job on the page once on load.
document.querySelectorAll(".job").forEach(el => pollJob(el.dataset.jobId));

jobList.addEventListener("click", async (e) => {
  const id = e.target.getAttribute("data-delete");
  if (!id) return;
  await fetch(`/jobs/${id}`, { method: "DELETE" });
  const el = jobList.querySelector(`[data-job-id="${id}"]`);
  if (el) el.remove();
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  formError.hidden = true;
  submitBtn.disabled = true;
  submitBtn.textContent = "Submitting...";

  try {
    const fd = new FormData(form);
    const res = await fetch("/jobs", { method: "POST", body: fd });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Request failed" }));
      throw new Error(err.detail || "Request failed");
    }
    const { id } = await res.json();
    form.reset();
    const el = addJobElement({ id, title: fd.get("title"), created_at: new Date().toISOString() });
    pollJob(id);
  } catch (err) {
    formError.textContent = err.message;
    formError.hidden = false;
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Generate video";
  }
});
