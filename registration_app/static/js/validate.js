document.addEventListener("DOMContentLoaded", function () {
  const form = document.getElementById("regForm");
  if (!form) return;

  const submitBtn = document.getElementById("submitBtn");
  const isEdit = form.action.includes("/update/");

  const NAME_RE = /^[A-Za-z][A-Za-z\s.'-]{1,79}$/;
  const MOBILE_RE = /^\d{10}$/;
  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const PIN_RE = /^\d{6}$/;

  function setError(fieldName, message) {
    const span = form.querySelector(`.error[data-for="${fieldName}"]`);
    const input = form.querySelector(`[name="${fieldName}"]`);
    if (span) span.textContent = message || "";
    if (input && input.classList) {
      input.classList.toggle("invalid", !!message);
    }
  }

  function validateField(name) {
    const el = form.querySelector(`[name="${name}"]`);
    const value = el ? el.value.trim() : "";

    switch (name) {
      case "full_name":
        if (!value) return "Full name is required.";
        if (!NAME_RE.test(value)) return "Full name must contain letters only (no numbers).";
        return "";
      case "mobile_number":
        if (!value) return "Mobile number is required.";
        if (!MOBILE_RE.test(value)) return "Mobile number must be exactly 10 digits.";
        return "";
      case "email":
        if (!value) return "Email is required.";
        if (!EMAIL_RE.test(value)) return "Please enter a valid email address.";
        return "";
      case "address":
        return value ? "" : "Address is required.";
      case "city":
        return value ? "" : "City is required.";
      case "state":
        return value ? "" : "State is required.";
      case "pin_code":
        if (!value) return "PIN code is required.";
        if (!PIN_RE.test(value)) return "PIN code must be exactly 6 digits.";
        return "";
      case "dob":
        if (!value) return "Date of birth is required.";
        if (new Date(value) >= new Date()) return "Date of birth must be in the past.";
        return "";
      case "education":
        return value ? "" : "Education is required.";
      case "position_applied":
        return value ? "" : "Position applied for is required.";
      case "skills":
        return value ? "" : "Skills are required.";
      default:
        return "";
    }
  }

  function validateGender() {
    const checked = form.querySelector('input[name="gender"]:checked');
    return checked ? "" : "Please select a gender.";
  }

  function validateFile(name, accept) {
    const input = form.querySelector(`[name="${name}"]`);
    if (!input || !input.files || input.files.length === 0) {
      // On edit page, files are optional (existing file is kept).
      return isEdit ? "" : `${name === "resume" ? "Resume" : "Profile photo"} is required.`;
    }
    const file = input.files[0];
    if (name === "resume" && file.type !== "application/pdf") {
      return "Resume must be a PDF file.";
    }
    if (name === "photo" && !file.type.startsWith("image/")) {
      return "Profile photo must be an image file.";
    }
    return "";
  }

  const textFields = [
    "full_name", "mobile_number", "email", "address", "city", "state",
    "pin_code", "dob", "education", "position_applied", "skills",
  ];

  textFields.forEach((name) => {
    const el = form.querySelector(`[name="${name}"]`);
    if (el) {
      el.addEventListener("blur", () => setError(name, validateField(name)));
      el.addEventListener("input", () => setError(name, ""));
    }
  });

  form.querySelectorAll('input[name="gender"]').forEach((el) => {
    el.addEventListener("change", () => setError("gender", ""));
  });

  ["resume", "photo"].forEach((name) => {
    const el = form.querySelector(`[name="${name}"]`);
    if (el) el.addEventListener("change", () => setError(name, validateFile(name)));
  });

  form.addEventListener("submit", function (e) {
    let hasError = false;

    textFields.forEach((name) => {
      const msg = validateField(name);
      setError(name, msg);
      if (msg) hasError = true;
    });

    const genderMsg = validateGender();
    setError("gender", genderMsg);
    if (genderMsg) hasError = true;

    const resumeMsg = validateFile("resume");
    setError("resume", resumeMsg);
    if (resumeMsg) hasError = true;

    const photoMsg = validateFile("photo");
    setError("photo", photoMsg);
    if (photoMsg) hasError = true;

    if (hasError) {
      e.preventDefault();
      const firstError = form.querySelector(".error:not(:empty)");
      if (firstError) firstError.scrollIntoView({ behavior: "smooth", block: "center" });
      return;
    }

    // disable the submit button immediately
    // and stop a second click/Enter from firing another request.
    if (submitBtn.dataset.submitted === "true") {
      e.preventDefault();
      return;
    }
    submitBtn.dataset.submitted = "true";
    submitBtn.disabled = true;
    submitBtn.textContent = "Submitting...";
  });
});
