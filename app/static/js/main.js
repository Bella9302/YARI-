// Mobile menu toggle, quantity steppers, and auto-dismissing flash messages.
document.addEventListener("DOMContentLoaded", function () {
  var toggle = document.querySelector("[data-menu-toggle]");
  var menu = document.querySelector("[data-menu]");
  if (toggle && menu) {
    toggle.addEventListener("click", function () {
      var open = menu.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  document.querySelectorAll("[data-qty]").forEach(function (box) {
    var input = box.querySelector("input");
    box.querySelector("[data-minus]").addEventListener("click", function () {
      input.value = Math.max(parseInt(input.min || "0", 10), (parseInt(input.value, 10) || 0) - 1);
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    box.querySelector("[data-plus]").addEventListener("click", function () {
      input.value = (parseInt(input.value, 10) || 0) + 1;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
  });

  document.querySelectorAll("form[data-autosubmit]").forEach(function (form) {
    form.addEventListener("change", function () { form.submit(); });
  });

  document.querySelectorAll("[data-confirm]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (!window.confirm(form.getAttribute("data-confirm"))) e.preventDefault();
    });
  });

  document.querySelectorAll("[data-image-input]").forEach(function (input) {
    input.addEventListener("change", function () {
      var preview = document.querySelector(input.getAttribute("data-image-input"));
      if (preview && input.files && input.files[0]) preview.src = URL.createObjectURL(input.files[0]);
    });
  });

  var flashes = document.querySelector(".flashes");
  if (flashes) setTimeout(function () { flashes.style.transition = "opacity .6s"; flashes.style.opacity = "0"; }, 6000);
});
