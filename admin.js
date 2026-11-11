const adminStatusChoices = ["Under review", "Additional information needed", "Accepted", "Not accepted"];
let adminCsrfToken = "";

async function adminRequest(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (options.method && options.method !== "GET") headers["X-CSRF-Token"] = adminCsrfToken;
  const response = await fetch(path, { ...options, headers, credentials: "same-origin" });
  let payload;
  try {
    payload = await response.json();
  } catch {
    throw new Error("The server returned an invalid response.");
  }
  if (!response.ok) throw new Error(payload.error || "The request could not be completed.");
  return payload;
}

function adminFeedback(message, text, isError = false) {
  message.textContent = window.translateUniversityText(text);
  message.classList.toggle("is-error", isError);
}

function detailCell(label, value) {
  const wrapper = document.createElement("div");
  const term = document.createElement("dt");
  term.textContent = window.translateUniversityText(label);
  const description = document.createElement("dd");
  description.textContent = value || "Not provided";
  wrapper.append(term, description);
  return wrapper;
}

function renderAdminApplications(applications) {
  const container = document.querySelector("#admin-applications");
  document.querySelector("#admin-count").textContent = applications.length;
  if (!applications.length) {
    const empty = document.createElement("p");
    empty.className = "empty-applications";
    empty.textContent = window.translateUniversityText("There are no submitted applications yet.");
    container.replaceChildren(empty);
    return;
  }

  container.replaceChildren(...applications.map((application) => {
    const item = document.createElement("details");
    item.className = "admin-application";
    const summary = document.createElement("summary");
    const info = document.createElement("span");
    info.className = "admin-summary-info";
    const title = document.createElement("strong");
    title.textContent = `${window.translateUniversityText(application.program)} · ${application.first_name} ${application.last_name}`;
    const subline = document.createElement("small");
    subline.textContent = `${application.reference} · ${application.email} · ${new Date(application.submitted_at).toLocaleDateString()}`;
    const status = document.createElement("span");
    status.className = `status-pill status-${application.status.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
    status.textContent = window.translateUniversityText(application.status);
    info.append(title, subline);
    summary.append(info, status);

    const details = document.createElement("dl");
    details.className = "admin-detail-grid";
    const detailFields = [
      ["Faculty", application.faculty], ["Program", application.program], ["Email", application.email],
      ["Phone", application.phone], ["Date of birth", application.date_of_birth], ["Country", application.country],
      ["Address", application.address], ["Education", application.education], ["School", application.school],
      ["Preferred start", application.start_term], ["Submitted", new Date(application.submitted_at).toLocaleString()],
      ["Applicant statement", application.statement]
    ];
    detailFields.forEach(([label, value]) => details.append(detailCell(label, value)));

    const form = document.createElement("form");
    form.className = "admin-status-form";
    form.dataset.reference = application.reference;
    const label = document.createElement("label");
    label.textContent = window.translateUniversityText("Update application status");
    const select = document.createElement("select");
    select.name = "status";
    adminStatusChoices.forEach((choice) => {
      const option = new Option(window.translateUniversityText(choice), choice, false, choice === application.status);
      select.add(option);
    });
    label.append(select);
    const button = document.createElement("button");
    button.type = "submit";
    button.textContent = window.translateUniversityText("Save status");
    const feedback = document.createElement("span");
    feedback.className = "admin-row-message";
    feedback.setAttribute("role", "status");
    form.append(label, button, feedback);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      button.disabled = true;
      try {
        await adminRequest("/api/admin/status", {
          method: "POST",
          body: JSON.stringify({ reference: application.reference, status: select.value })
        });
        adminFeedback(feedback, "Status updated.");
        await loadAdminApplications();
      } catch (error) {
        adminFeedback(feedback, error.message, true);
      } finally {
        button.disabled = false;
      }
    });
    item.append(summary, details, form);
    return item;
  }));
}

async function loadAdminApplications() {
  const result = await adminRequest("/api/admin/applications");
  renderAdminApplications(result.applications);
}

function renderAdminStudents(students) {
  const container = document.querySelector("#admin-students");
  document.querySelector("#student-count").textContent = students.length;
  if (!students.length) {
    const empty = document.createElement("p");
    empty.className = "empty-applications";
    empty.textContent = "There are no registered student accounts yet.";
    container.replaceChildren(empty);
    return;
  }
  container.replaceChildren(...students.map((student) => {
    const row = document.createElement("article");
    row.className = "admin-student-row";
    const name = document.createElement("strong");
    name.textContent = `${student.first_name} ${student.last_name}`;
    const email = document.createElement("a");
    email.href = `mailto:${encodeURIComponent(student.email)}`;
    email.textContent = student.email;
    const phone = document.createElement("span");
    phone.textContent = student.phone || window.translateUniversityText("No phone on file");
    const count = document.createElement("span");
    count.textContent = `${student.application_count} ${window.translateUniversityText(student.application_count === 1 ? "application" : "applications")}`;
    const created = document.createElement("small");
    created.textContent = `${window.translateUniversityText("Registered")} ${window.formatUniversityDate(new Date(student.created_at))}`;
    row.append(name, email, phone, count, created);
    return row;
  }));
}

const adminContainer = document.querySelector("#admin-applications");
if (adminContainer) {
  (async () => {
    const message = document.querySelector("#admin-message");
    try {
      const session = await adminRequest("/api/session");
      adminCsrfToken = session.csrfToken;
      if (!session.user) {
        window.location.replace("login.html");
        return;
      }
      if (session.user.role !== "admin") {
        window.location.replace("dashboard.html");
        return;
      }
      const [applications, students] = await Promise.all([
        adminRequest("/api/admin/applications"),
        adminRequest("/api/admin/students")
      ]);
      renderAdminApplications(applications.applications);
      renderAdminStudents(students.students);
    } catch (error) {
      adminFeedback(message, error.message, true);
    }
  })();
}

const logoutButton = document.querySelector("#logout-button");
if (logoutButton) {
  logoutButton.addEventListener("click", async () => {
    try {
      if (!adminCsrfToken) {
        const session = await adminRequest("/api/session");
        adminCsrfToken = session.csrfToken;
      }
      await adminRequest("/api/logout", { method: "POST", body: "{}" });
      window.location.assign("index.html");
    } catch (error) {
      adminFeedback(document.querySelector("#admin-message"), error.message, true);
    }
  });
}
