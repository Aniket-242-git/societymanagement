/* Shared UI helpers used across admin + resident pages. */
(function (window, $) {
  "use strict";

  const INR = (v) => "₹" + Number(v || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 });

  function statusPill(status) {
    return `<span class="status-pill st-${SMS.esc(status)}">${SMS.esc((status || "").replace("_", " "))}</span>`;
  }

  function formatDate(iso) {
    if (!iso) return "-";
    const d = new Date(iso);
    return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
  }

  // Simple client-side pagination renderer for tables fed by API list endpoints
  function renderPager(elId, count, page, pageSize, onChange) {
    const pages = Math.max(1, Math.ceil(count / pageSize));
    const cur = page;
    let html = "";
    if (pages <= 1) { $(elId).html(""); return; }
    html += `<li class="page-item ${cur <= 1 ? "disabled" : ""}"><a class="page-link" href="#" data-p="${cur - 1}">‹</a></li>`;
    const from = Math.max(1, cur - 2), to = Math.min(pages, cur + 2);
    for (let p = from; p <= to; p++) {
      html += `<li class="page-item ${p === cur ? "active" : ""}"><a class="page-link" href="#" data-p="${p}">${p}</a></li>`;
    }
    html += `<li class="page-item ${cur >= pages ? "disabled" : ""}"><a class="page-link" href="#" data-p="${cur + 1}">›</a></li>`;
    $(elId).html(`<nav><ul class="pagination pagination-sm mb-0 justify-content-end">${html}</ul></nav>`);
    $(elId).off("click").on("click", "a.page-link", function (e) {
      e.preventDefault();
      const p = parseInt($(this).data("p"), 10);
      if (p >= 1 && p <= pages && p !== cur) onChange(p);
    });
  }

  window.SMSUI = { INR, statusPill, formatDate, renderPager };
})(window, jQuery);
