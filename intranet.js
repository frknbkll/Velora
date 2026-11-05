(() => {
  "use strict";

  const search = document.querySelector("#intranet-search");
  const people = [...document.querySelectorAll(".intranet-person")];
  const count = document.querySelector("#intranet-result-count");
  const noResults = document.querySelector("#intranet-no-results");
  const filters = [...document.querySelectorAll("[data-department-filter]")];
  let activeDepartment = "all";

  function filterPeople() {
    const query = search.value.trim().toLocaleLowerCase();
    let visible = 0;
    for (const person of people) {
      const matchesDepartment = activeDepartment === "all" || person.dataset.department === activeDepartment;
      const matchesSearch = !query || person.dataset.search.toLocaleLowerCase().includes(query);
      person.hidden = !(matchesDepartment && matchesSearch);
      if (!person.hidden) visible += 1;
    }
    count.textContent = `Showing ${visible} ${visible === 1 ? "colleague" : "colleagues"}`;
    noResults.hidden = visible !== 0;
  }

  search?.addEventListener("input", filterPeople);
  filters.forEach((button) => {
    button.addEventListener("click", () => {
      activeDepartment = button.dataset.departmentFilter;
      filters.forEach((filter) => filter.setAttribute("aria-pressed", String(filter === button)));
      filterPeople();
    });
  });

  const date = document.querySelector("#intranet-date");
  const greeting = document.querySelector("#intranet-greeting");
  if (greeting) {
    const hour = new Date().getHours();
    greeting.textContent = hour < 12 ? "Good morning," : hour < 18 ? "Good afternoon," : "Good evening,";
  }
  if (date) {
    date.textContent = new Intl.DateTimeFormat("en-GB", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    }).format(new Date());
  }

  const auth = window.VeloraAuth;
  if (!auth) return;
  auth.ready.then((user) => {
    if (!user) {
      location.replace("login.html?next=intranet.html");
      return;
    }
    if (user.role !== "admin") {
      location.replace("account.html");
      return;
    }
    const firstName = user.firstName || user.name?.trim().split(/\s+/)[0] || "team";
    document.querySelector("#intranet-greeting-name").textContent = `${firstName}.`;
    document.querySelector("#intranet-user-name").textContent = user.name || "Team member";
    document.querySelector("#intranet-avatar").textContent = firstName.slice(0, 1).toLocaleUpperCase();
  }).catch((error) => {
    const message = document.querySelector("#auth-message");
    message.textContent = error.message || "We couldn't verify your team access. Please sign in again.";
    message.classList.add("is-error");
    message.setAttribute("role", "alert");
  });
})();
