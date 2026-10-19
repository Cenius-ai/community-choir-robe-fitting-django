/* Community Choir Robe Fitting — progressive enhancement only.
   The whole app works with JavaScript disabled; this adds the scroll
   progress thread, the password reveal toggle and a double-submit guard. */
(function () {
  "use strict";

  var thread = document.querySelector("[data-scroll-thread]");

  function scrollTarget() {
    var canvas = document.querySelector(".app-canvas");
    if (canvas) {
      var overflow = window.getComputedStyle(canvas).overflowY;
      if (overflow === "auto" || overflow === "scroll") {
        return canvas;
      }
    }
    return document.scrollingElement || document.documentElement;
  }

  function updateThread() {
    if (!thread) {
      return;
    }
    var target = scrollTarget();
    var scrollable = target.scrollHeight - target.clientHeight;
    var progress = scrollable > 0 ? target.scrollTop / scrollable : 0;
    var clamped = Math.min(1, Math.max(0, progress));
    thread.style.width = (clamped * 100).toFixed(2) + "%";
  }

  if (thread) {
    window.addEventListener("scroll", updateThread, { passive: true, capture: true });
    window.addEventListener("resize", updateThread, { passive: true });
    updateThread();
  }

  document.querySelectorAll("[data-toggle-password]").forEach(function (button) {
    button.addEventListener("click", function () {
      var input = document.querySelector(button.getAttribute("data-toggle-password"));
      if (!input) {
        return;
      }
      var reveal = input.type === "password";
      input.type = reveal ? "text" : "password";
      button.textContent = reveal ? "Hide password" : "Show password";
    });
  });

  /* Re-entrancy guard: a double-click cannot create two records. */
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement)) {
      return;
    }
    if (form.dataset.submitting === "true") {
      event.preventDefault();
      return;
    }
    form.dataset.submitting = "true";
    var button = form.querySelector('button[type="submit"]');
    if (button) {
      /* Disable after the browser has serialized the form so the clicked
         button's name/value still reaches the server. */
      window.setTimeout(function () {
        button.setAttribute("disabled", "");
      }, 0);
    }
  });

  /* Restore buttons when a page is served from the back/forward cache. */
  window.addEventListener("pageshow", function () {
    document.querySelectorAll('form[data-submitting="true"]').forEach(function (form) {
      form.dataset.submitting = "false";
      form.querySelectorAll("button[disabled]").forEach(function (button) {
        button.removeAttribute("disabled");
      });
    });
  });
})();
