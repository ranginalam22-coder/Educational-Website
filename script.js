const categoryTabs = document.querySelectorAll(".category-tab");
const courseCards = document.querySelectorAll(".course-card");
const courseSearch = document.querySelector("#course-search");
const emptyState = document.querySelector("#empty-state");
const menuToggle = document.querySelector(".menu-toggle");
const primaryNav = document.querySelector("#primary-nav");
let activeCategory = "all";

function filterCourses() {
  const query = courseSearch.value.trim().toLowerCase();
  let visibleCount = 0;

  courseCards.forEach((card) => {
    const matchesCategory = activeCategory === "all" || card.dataset.category === activeCategory;
    const matchesSearch = !query || `${card.dataset.search} ${card.querySelector("h3").textContent}`.toLowerCase().includes(query);
    const isVisible = matchesCategory && matchesSearch;
    card.hidden = !isVisible;
    if (isVisible) visibleCount += 1;
  });

  emptyState.hidden = visibleCount > 0;
}

categoryTabs.forEach((tab) => {
  tab.addEventListener("click", () => {
    activeCategory = tab.dataset.category;
    categoryTabs.forEach((item) => item.classList.toggle("active", item === tab));
    filterCourses();
  });
});

courseSearch.addEventListener("input", filterCourses);

menuToggle.addEventListener("click", () => {
  const isExpanded = menuToggle.getAttribute("aria-expanded") === "true";
  menuToggle.setAttribute("aria-expanded", String(!isExpanded));
  menuToggle.setAttribute("aria-label", isExpanded ? "Open navigation" : "Close navigation");
  primaryNav.classList.toggle("is-open", !isExpanded);
});

primaryNav.querySelectorAll("a").forEach((link) => {
  link.addEventListener("click", () => {
    primaryNav.classList.remove("is-open");
    menuToggle.setAttribute("aria-expanded", "false");
    menuToggle.setAttribute("aria-label", "Open navigation");
  });
});

document.querySelector("#newsletter-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const email = document.querySelector("#email");
  const message = document.querySelector("#form-message");
  message.textContent = `Thanks for joining us, ${email.value}! Keep an eye on your inbox.`;
  message.setAttribute("role", "status");
  email.value = "";
});
