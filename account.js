let csrfToken = "";
let sessionPromise;

function tr(text) {
  return window.translateUniversityText(text);
}

async function requestJson(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (options.method && options.method !== "GET") headers["X-CSRF-Token"] = csrfToken;
  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error("The server returned an invalid response. Please try again.");
  }
  if (!response.ok) throw new Error(payload.error || "The request could not be completed.");
  return payload;
}

function showFeedback(element, message, isError = false) {
  element.textContent = tr(message);
  element.classList.toggle("is-error", isError);
}

function valuesFrom(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function redirectByRole(user) {
  window.location.assign(user.role === "admin" ? "admin.html" : "dashboard.html");
}

function loadSession() {
  if (!sessionPromise) {
    sessionPromise = requestJson("/api/session").then((session) => {
      csrfToken = session.csrfToken;
      return session.user;
    }).catch((error) => {
      sessionPromise = null;
      throw error;
    });
  }
  return sessionPromise;
}

const signupForm = document.querySelector("#signup-form");
const loginForm = document.querySelector("#login-form");
if (signupForm || loginForm) {
  loadSession().then((user) => {
    if (user) redirectByRole(user);
  }).catch((error) => {
    const message = document.querySelector("#form-message");
    if (message) showFeedback(message, error.message, true);
  });
}

if (signupForm) {
  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = document.querySelector("#form-message");
    const values = valuesFrom(signupForm);
    try {
      if (!csrfToken) await loadSession();
      const result = await requestJson("/api/register", {
        method: "POST",
        body: JSON.stringify({
          firstName: values.firstName,
          lastName: values.lastName,
          email: values.email,
          password: values.password
        })
      });
      csrfToken = result.csrfToken;
      redirectByRole(result.user);
    } catch (error) {
      showFeedback(message, error.message, true);
    }
  });
}

if (loginForm) {
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = document.querySelector("#form-message");
    const values = valuesFrom(loginForm);
    try {
      if (!csrfToken) await loadSession();
      const result = await requestJson("/api/login", {
        method: "POST",
        body: JSON.stringify({ email: values.email, password: values.password })
      });
      csrfToken = result.csrfToken;
      redirectByRole(result.user);
    } catch (error) {
      showFeedback(message, error.message, true);
    }
  });
}

const admissionForm = document.querySelector("#admission-form");
if (admissionForm) {
  (async () => {
    try {
      const user = await loadSession();
      if (!user) {
        document.querySelector("#login-required").hidden = false;
        admissionForm.querySelectorAll("input, select, textarea, button").forEach((field) => {
          field.disabled = true;
        });
        return;
      }
      if (user.role !== "student") {
        window.location.assign("admin.html");
        return;
      }
      admissionForm.elements.firstName.value = user.firstName;
      admissionForm.elements.lastName.value = user.lastName;
      admissionForm.elements.email.value = user.email;
      admissionForm.elements.phone.value = user.phone;
    } catch (error) {
      showFeedback(document.querySelector("#form-message"), error.message, true);
    }
  })();

  admissionForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = document.querySelector("#form-message");
    const values = valuesFrom(admissionForm);
    try {
      if (!csrfToken) await loadSession();
      const result = await requestJson("/api/admissions", {
        method: "POST",
        body: JSON.stringify({
          dateOfBirth: values.dateOfBirth,
          phone: values.phone,
          country: values.country,
          address: values.address,
          education: values.education,
          school: values.school,
          faculty: values.faculty,
          program: values.program,
          startTerm: values.startTerm,
          statement: values.statement || "",
          consent: admissionForm.elements.consent.checked
        })
      });
      window.location.assign(`dashboard.html?submitted=${encodeURIComponent(result.reference)}`);
    } catch (error) {
      showFeedback(message, error.message, true);
    }
  });
}

const profileForm = document.querySelector("#profile-form");
if (profileForm) {
  (async () => {
    try {
      const user = await loadSession();
      if (!user) {
        window.location.replace("login.html");
        return;
      }
      if (user.role === "admin") {
        window.location.replace("admin.html");
        return;
      }
      document.querySelector("#student-name").textContent = `${user.firstName}.`;
      profileForm.elements.firstName.value = user.firstName;
      profileForm.elements.lastName.value = user.lastName;
      profileForm.elements.email.value = user.email;
      profileForm.elements.phone.value = user.phone;
      const { applications } = await requestJson("/api/applications");
      renderStudentApplications(applications);
      const submittedReference = new URLSearchParams(window.location.search).get("submitted");
      if (submittedReference) {
        showFeedback(document.querySelector("#profile-message"), `${tr("Application")} ${submittedReference} ${tr("was submitted successfully.")}`);
      }
    } catch (error) {
      showFeedback(document.querySelector("#profile-message"), error.message, true);
    }
  })();

  profileForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = document.querySelector("#profile-message");
    const values = valuesFrom(profileForm);
    try {
      const result = await requestJson("/api/profile", {
        method: "POST",
        body: JSON.stringify({ firstName: values.firstName, lastName: values.lastName, phone: values.phone || "" })
      });
      document.querySelector("#student-name").textContent = `${result.user.firstName}.`;
      showFeedback(message, "Your profile has been updated.");
    } catch (error) {
      showFeedback(message, error.message, true);
    }
  });
}

function renderStudentApplications(applications) {
  const list = document.querySelector("#application-list");
  document.querySelector("#application-count").textContent = applications.length;
  if (applications.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-applications";
    empty.textContent = tr("You haven’t submitted an application yet. Choose a faculty and program to get started.");
    list.replaceChildren(empty);
    return;
  }
  list.replaceChildren(...applications.map((application) => {
    const item = document.createElement("article");
    item.className = "student-application";
    const head = document.createElement("div");
    head.className = "application-head";
    const program = document.createElement("h3");
    program.textContent = tr(application.program);
    const status = document.createElement("span");
    status.className = `status-pill status-${application.status.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
    status.textContent = tr(application.status);
    head.append(program, status);
    const faculty = document.createElement("p");
    faculty.textContent = tr(application.faculty);
    const date = document.createElement("p");
    date.textContent = `${tr("Reference")} ${application.reference} · ${tr("Submitted")} ${window.formatUniversityDate(new Date(application.submittedAt))}`;
    item.append(head, faculty, date);
    return item;
  }));
}

const logoutButton = document.querySelector("#logout-button");
if (logoutButton) {
  logoutButton.addEventListener("click", async () => {
    try {
      if (!csrfToken) await loadSession();
      await requestJson("/api/logout", { method: "POST", body: "{}" });
      window.location.assign("index.html");
    } catch (error) {
      window.location.assign("login.html?message=" + encodeURIComponent(error.message));
    }
  });
}
