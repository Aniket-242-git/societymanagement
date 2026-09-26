/* =====================================================================
 * Central jQuery AJAX layer for the Society Management UI.
 * NEVER call $.ajax directly from page scripts — always use ajaxRequest().
 *
 *  - attaches JWT bearer token + CSRF header
 *  - shows/hides the global loader
 *  - drives toastr toasts from the standard envelope `message` field
 *  - centralized 401 handling -> redirect to login
 * ===================================================================== */
(function (window, $) {
  "use strict";

  const TOKEN_KEY = "sms_access_token";
  const REFRESH_KEY = "sms_refresh_token";

  const Auth = {
    get access() { return localStorage.getItem(TOKEN_KEY); },
    get refresh() { return localStorage.getItem(REFRESH_KEY); },
    set(access, refresh) {
      if (access) localStorage.setItem(TOKEN_KEY, access);
      if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
    },
    clear() {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_KEY);
    },
  };

  // expose API base
  const API_BASE = "/api/v1/";

  function csrfToken() {
    const m = document.cookie.match(/(^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[2]) : "";
  }

  let activeRequests = 0;
  function showLoader() {
    activeRequests += 1;
    $("#global-loader").removeClass("d-none");
  }
  function hideLoader() {
    activeRequests = Math.max(0, activeRequests - 1);
    if (activeRequests === 0) $("#global-loader").addClass("d-none");
  }

  /**
   * ajaxRequest({ url, method, data, formData, silent })
   * Returns a promise resolving with the parsed envelope `{success,message,data,errors}`.
   */
  function ajaxRequest(opts) {
    const settings = $.extend({
      url: "",
      method: "GET",
      data: null,
      formData: null,     // pass a FormData instance for file uploads
      silent: false,      // suppress automatic error toast
    }, opts);

    const dfd = $.Deferred();
    const config = {
      url: settings.url.startsWith("http") || settings.url.startsWith("/") ? settings.url : API_BASE + settings.url,
      method: settings.method,
      headers: {
        "X-CSRFToken": csrfToken(),
        Accept: "application/json",
      },
      beforeSend: showLoader,
      complete: hideLoader,
    };

    if (Auth.access) config.headers["Authorization"] = "Bearer " + Auth.access;

    if (settings.formData) {
      config.processData = false;
      config.contentType = false;
      config.data = settings.formData;
    } else if (settings.data !== null && ["POST", "PATCH", "PUT"].includes(settings.method.toUpperCase())) {
      config.contentType = "application/json";
      config.data = JSON.stringify(settings.data);
    } else if (settings.data !== null) {
      config.data = settings.data; // query string params
    }

    $.ajax(config)
      .done(function (res) {
        dfd.resolve(res);
      })
      .fail(function (xhr) {
        if (xhr.status === 401) {
          // try refresh once, else force login
          Auth.clear();
          window.location.href = "/ui/login/?next=" + encodeURIComponent(window.location.pathname);
          dfd.reject(xhr);
          return;
        }
        let res = null;
        try { res = JSON.parse(xhr.responseText); } catch (e) { /* ignore */ }
        if (!settings.silent) {
          const msg = (res && res.message) ? res.message : "Something went wrong (" + xhr.status + ")";
          toastError(msg);
        }
        dfd.reject(res || { success: false, message: "Request failed", errors: null });
      });

    return dfd.promise();
  }

  // ---------------- toastr helpers ----------------
  toastr.options = {
    closeButton: true, progressBar: true, timeOut: 3500,
    positionClass: "toast-top-right",
  };
  function toastSuccess(msg) { toastr.success(msg); }
  function toastError(msg) { toastr.error(msg); }

  // ---------------- convenience wrappers ----------------
  const Api = {
    get: (url, params) => ajaxRequest({ url, method: "GET", data: params }),
    post: (url, data) => ajaxRequest({ url, method: "POST", data }),
    patch: (url, data) => ajaxRequest({ url, method: "PATCH", data }),
    put: (url, data) => ajaxRequest({ url, method: "PUT", data }),
    del: (url, data) => ajaxRequest({ url, method: "DELETE", data }),
    upload: (url, formData) => ajaxRequest({ url, method: "POST", formData }),
  };

  // shared HTML escape helper
  function esc(s) {
    return $("<div>").text(s == null ? "" : String(s)).html();
  }

  // change-password form (present in base layout)
  $(function () {
    $("#change-pwd-form").on("submit", function (e) {
      e.preventDefault();
      const payload = {
        old_password: $(this).find('[name="old_password"]').val(),
        new_password: $(this).find('[name="new_password"]').val(),
      };
      Api.post("auth/change-password/", payload).done(function (res) {
        if (res.success) {
          toastSuccess(res.message);
          $("#changePwdModal").modal("hide");
        }
      });
    });
  });

  window.SMS = { Auth, Api, ajaxRequest, toastSuccess, toastError, esc, API_BASE };
})(window, jQuery);
