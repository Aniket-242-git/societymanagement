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

  // Month filter helpers — every list page with a month-wise filter uses these.
  const MONTHS = ["All Months", "January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"];

  // Injects <option>s into a month <select> (value "" = all months).
  function fillMonthSelect($sel, includeAll = true) {
    const start = includeAll ? 0 : 1;
    $sel.html(Array.from({ length: 13 - start }, (_, i) =>
      `<option value="${includeAll && i === 0 ? "" : i}">${MONTHS[i]}</option>`).join(""));
  }

  // Injects <option>s into a year <select> (value "" = all years).
  function fillYearSelect($sel, span = 4) {
    const y = new Date().getFullYear();
    const years = []; for (let i = y + 1; i >= y - span; i--) years.push(i);
    $sel.html(`<option value="">All Years</option>` + years.map(v => `<option value="${v}">${v}</option>`).join(""));
  }

  // Reads #month-filter/#year-filter (if present on the page) into API params.
  function monthParams(params) {
    params = params || {};
    const m = $("#month-filter").val(), y = $("#year-filter").val();
    if (m) params.month = m;
    if (y) params.year = y;
    return params;
  }

  window.SMSUI.MONTHS = MONTHS;
  window.SMSUI.fillMonthSelect = fillMonthSelect;
  window.SMSUI.fillYearSelect = fillYearSelect;
  window.SMSUI.monthParams = monthParams;
})(window, jQuery);
