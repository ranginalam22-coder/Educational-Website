async function loadUniversityCatalog() {
  const response = await fetch("/api/catalog");
  if (!response.ok) throw new Error("University programs are temporarily unavailable. Please try again later.");
  return response.json();
}

window.universityCatalog = loadUniversityCatalog();

const universityMenu = document.querySelector(".uni-menu-toggle");
if (universityMenu) {
  const nav = document.querySelector("#uni-nav");
  universityMenu.addEventListener("click", () => {
    const expanded = universityMenu.getAttribute("aria-expanded") === "true";
    universityMenu.setAttribute("aria-expanded", String(!expanded));
    universityMenu.setAttribute("aria-label", expanded ? "Open navigation" : "Close navigation");
    nav.classList.toggle("is-open", !expanded);
  });
  nav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      nav.classList.remove("is-open");
      universityMenu.setAttribute("aria-expanded", "false");
      universityMenu.setAttribute("aria-label", "Open navigation");
    });
  });
}

const facultyPage = document.querySelector("[data-faculty]");
if (facultyPage) {
  window.universityCatalog.then(({ faculties }) => {
    const faculty = faculties.find((item) => item.slug === facultyPage.dataset.faculty);
    if (!faculty) throw new Error("This faculty could not be found.");
    document.querySelector("#faculty-intro").textContent = window.translateUniversityText(faculty.intro);
    const programGrid = document.querySelector("#program-grid");
    programGrid.replaceChildren(...faculty.programs.map((program, index) => {
      const card = document.createElement("article");
      card.className = "program-card";
      const top = document.createElement("div");
      top.className = "program-card-top";
      const programLabel = document.createElement("span");
      programLabel.textContent = window.translateUniversityText("PROGRAM");
      const programNumber = document.createElement("span");
      programNumber.textContent = (index + 1).toString().padStart(2, "0");
      top.append(programLabel, programNumber);
      const duration = document.createElement("span");
      duration.textContent = program.duration;
      top.append(duration);
      const title = document.createElement("h3");
      title.textContent = window.translateUniversityText(program.name);
      const description = document.createElement("p");
      description.textContent = window.translateUniversityText(program.description);
      const outcome = document.createElement("p");
      outcome.className = "program-outcome";
      outcome.textContent = window.translateUniversityText(program.outcomes);
      card.append(top, title, description, outcome);
      return card;
    }));
    const requirements = document.querySelector("#faculty-requirements");
    requirements.replaceChildren(...faculty.requirements.map((requirement) => {
      const item = document.createElement("li");
      item.textContent = window.translateUniversityText(requirement);
      return item;
    }));
  }).catch((error) => {
    const intro = document.querySelector("#faculty-intro");
    intro.textContent = error.message;
  });
}

const facultySelect = document.querySelector("#faculty-select");
if (facultySelect) {
  const programSelect = document.querySelector("#program-select");
  const requirementsList = document.querySelector("#admission-requirements");
  const urlFaculty = new URLSearchParams(window.location.search).get("faculty");

  window.universityCatalog.then(({ faculties }) => {
    facultySelect.replaceChildren(new Option("Select a faculty", ""));
    faculties.forEach((faculty) => facultySelect.add(new Option(window.translateUniversityText(faculty.name), faculty.slug)));
    if (urlFaculty && faculties.some((faculty) => faculty.slug === urlFaculty)) {
      facultySelect.value = urlFaculty;
      facultySelect.dispatchEvent(new Event("change"));
    }

    facultySelect.addEventListener("change", () => {
      const faculty = faculties.find((item) => item.slug === facultySelect.value);
      programSelect.replaceChildren(new Option(faculty ? "Select a program" : "Select a faculty first", ""));
      programSelect.disabled = !faculty;
      if (!faculty) {
        requirementsList.replaceChildren();
        const empty = document.createElement("li");
        empty.textContent = "Select a faculty to see its admission requirements.";
        requirementsList.append(empty);
        return;
      }
      faculty.programs.forEach((program) => programSelect.add(new Option(window.translateUniversityText(program.name), program.slug)));
      requirementsList.replaceChildren(...faculty.requirements.map((requirement) => {
        const item = document.createElement("li");
        item.textContent = window.translateUniversityText(requirement);
        return item;
      }));
    });
  }).catch((error) => {
    facultySelect.replaceChildren(new Option(error.message, ""));
    facultySelect.disabled = true;
  });
}
