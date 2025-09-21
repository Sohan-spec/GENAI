document.addEventListener("DOMContentLoaded", () => {
  const toggles = document.querySelectorAll(".toggle-pass");
  toggles.forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-target");
      const input = document.getElementById(targetId);
      if (!input) return;
      const isPassword = input.type === "password";
      input.type = isPassword ? "text" : "password";
      btn.textContent = isPassword ? "Hide" : "Show";
    });
  });

  // very light client-side check example (non-blocking)
  const signupForm = document.getElementById("signupForm");
  if (signupForm) {
    signupForm.addEventListener("submit", (e) => {
      const pwd = document.getElementById("signupPassword");
      if (pwd && pwd.value.length < 6) {
        alert("Password should be at least 6 characters.");
      }
    });
  }
});



