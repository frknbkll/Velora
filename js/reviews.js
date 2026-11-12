/* Real account reviews; identity and ownership are checked by the server. */
(() => {
  "use strict";
  const $ = (selector) => document.querySelector(selector);
  const form = $("#review-form");
  if (!form) return;
  const state = { user: null, own: null, reviews: [], cursor: null, loading: false, busy: false, processing: false, photo: null, photoChanged: false, photoVersion: 0, active: true, checkedAt: 0 };
  const dateFormat = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function message(text, success = false) {
    const node = $("#review-form-message");
    node.textContent = text;
    node.classList.toggle("is-success", success);
    node.classList.toggle("is-error", Boolean(text) && !success);
    node.setAttribute("role", text && !success ? "alert" : "status");
  }
  function updateAuthor() {
    const name = state.user?.name || "your account name";
    $("#review-account-name").textContent = name;
    $("#review-author-preview").textContent = $("#review-anonymous").checked
      ? "Your public name will be Anonymous. Your review stays linked to your account."
      : `Your public name will be ${name}.`;
  }
  function updateCount() {
    $("#review-body-count").textContent = `${$("#review-body").value.length} / 2,000 characters`;
  }
  function updateBusy() {
    form.setAttribute("aria-busy", String(state.busy || state.processing));
    for (const field of form.elements) field.disabled = state.busy;
    $("#review-submit").disabled = state.busy || state.processing;
    $("#review-submit").textContent = state.busy ? "Saving your review…" : state.processing ? "Preparing photo…" : state.own ? "Update review" : "Publish review";
  }
  function showPhoto(source) {
    const preview = $("#review-image-preview");
    preview.hidden = !source;
    $("#review-image-remove").hidden = !source;
    if (source) preview.src = source;
    else preview.removeAttribute("src");
  }
  function fillForm() {
    ++state.photoVersion;
    state.photo = null;
    state.photoChanged = false;
    state.processing = false;
    form.reset();
    const review = state.own;
    if (review) {
      form.querySelector(`input[name="rating"][value="${review.rating}"]`).checked = true;
      $("#review-title").value = review.title;
      $("#review-body").value = review.body;
      $("#review-anonymous").checked = review.anonymous;
    }
    $("#review-edit-note").hidden = !review;
    $("#review-cancel-edit").hidden = !review;
    $("#review-delete-own").hidden = !review;
    showPhoto(review?.image);
    updateAuthor();
    updateCount();
    updateBusy();
  }
  function requireSignIn() {
    state.user = null;
    state.own = null;
    ++state.photoVersion;
    state.photo = null;
    state.photoChanged = false;
    state.processing = false;
    form.reset();
    showPhoto(null);
    $("#review-account-name").textContent = "";
    $("#review-author-preview").textContent = "";
    $("#review-edit-note").hidden = true;
    form.hidden = true;
    $("#review-signin").hidden = false;
    renderReviews();
  }
  async function setUser(user) {
    state.user = user;
    if (!user) { requireSignIn(); return; }
    const { review } = await window.VeloraAuth.request("/api/reviews/mine");
    if (!state.active) return;
    state.own = review;
    fillForm();
    form.hidden = false;
    $("#review-signin").hidden = true;
    renderReviews();
  }
  function renderSummary(summary) {
    state.summaryLoaded = true;
    const count = summary.count;
    $("#review-average").textContent = count ? Number(summary.average).toFixed(1) : "—";
    $("#review-total").textContent = count ? `${count} ${count === 1 ? "review" : "reviews"}` : "No reviews yet";
    const rows = [5, 4, 3, 2, 1].map((rating) => {
      const value = Number(summary.distribution[String(rating)]) || 0;
      const row = element("div", "review-distribution-row");
      const meter = document.createElement("meter");
      meter.min = 0;
      meter.max = count || 1;
      meter.value = value;
      meter.setAttribute("aria-label", `${rating} ${rating === 1 ? "star" : "stars"}: ${value} ${value === 1 ? "review" : "reviews"}`);
      row.append(element("span", "", `${rating} ★`), meter, element("span", "", String(value)));
      return row;
    });
    $("#review-distribution").replaceChildren(...rows);
  }
  function openDelete(button) {
    if (state.busy || !state.own) return;
    state.deleteOpener = button;
    $("#review-delete-dialog").showModal();
    $("#review-delete-cancel").focus();
  }
  function openPhoto(review, opener) {
    state.photoOpener = opener;
    $("#review-photo-image").src = review.image;
    $("#review-photo-title").textContent = `Photo shared by ${review.authorName}`;
    $("#review-photo-dialog").showModal();
    $("#review-photo-close").focus();
  }
  function renderReviews() {
    const cards = state.reviews.map((review) => {
      const card = element("article", "review-card");
      card.dataset.reviewId = review.id;
      const header = element("div", "review-card-header");
      const initials = review.anonymous ? "A" : review.authorName.trim().split(/\s+/).slice(0, 2).map((part) => Array.from(part)[0] || "").join("").toUpperCase();
      const avatar = element("span", "review-avatar", initials);
      avatar.setAttribute("aria-hidden", "true");
      const identity = element("div", "review-identity");
      const date = element("time", "review-date");
      date.dateTime = review.createdAt;
      const timestamp = new Date(review.createdAt);
      date.textContent = Number.isNaN(timestamp.getTime()) ? "" : dateFormat.format(timestamp);
      identity.append(element("p", "review-author", review.authorName), date);
      const stars = element("span", "review-stars", "★".repeat(review.rating) + "☆".repeat(5 - review.rating));
      stars.setAttribute("role", "img");
      stars.setAttribute("aria-label", `${review.rating} out of 5 stars`);
      header.append(avatar, identity, stars);
      card.append(header);
      if (review.title) card.append(element("h3", "review-card-title", review.title));
      card.append(element("p", "review-card-body", review.body));
      if (review.image) {
        const photo = element("button", "review-photo");
        photo.type = "button";
        photo.setAttribute("aria-label", `View photo shared by ${review.authorName}`);
        photo.setAttribute("aria-haspopup", "dialog");
        const image = element("img");
        image.src = review.image;
        image.alt = "Photo shared with this review";
        image.loading = "lazy";
        image.decoding = "async";
        photo.append(image);
        photo.addEventListener("click", () => openPhoto(review, photo));
        card.append(photo);
      }
      if (review.id === state.own?.id && state.user) {
        const actions = element("div", "review-card-actions");
        const edit = element("button", "", "Edit your review");
        edit.type = "button";
        edit.addEventListener("click", () => {
          if (state.busy || state.processing) return;
          fillForm();
          message("");
          $("#review-composer").scrollIntoView({ block: "start" });
          $("#review-title").focus({ preventScroll: true });
        });
        const remove = element("button", "review-delete", "Delete");
        remove.type = "button";
        remove.addEventListener("click", () => openDelete(remove));
        actions.append(edit, remove);
        card.append(actions);
      }
      return card;
    });
    $("#reviews-list").replaceChildren(...cards);
  }
  async function loadReviews(append = false) {
    if (state.loading) {
      if (append) return;
      try { await state.listRequest; } catch { /* A new refresh can recover a failed request. */ }
      return loadReviews();
    }
    state.loading = true;
    $("#reviews-load-more").disabled = true;
    $("#reviews-state").textContent = "Loading reviews…";
    try {
      const cursor = append && state.cursor ? `&cursor=${encodeURIComponent(state.cursor)}` : "";
      state.listRequest = window.VeloraAuth.request(`/api/reviews?limit=12${cursor}`);
      const result = await state.listRequest;
      if (!state.active) return;
      state.reviews = append ? [...new Map([...state.reviews, ...result.reviews].map((review) => [review.id, review])).values()] : result.reviews;
      state.cursor = result.nextCursor;
      renderSummary(result.summary);
      renderReviews();
      $("#reviews-empty").hidden = result.summary.count !== 0;
      $("#reviews-load-more").hidden = !state.cursor;
      $("#reviews-state").textContent = result.summary.count ? `Showing ${state.reviews.length} of ${result.summary.count} reviews.` : "";
    } catch (error) {
      if (!state.summaryLoaded) $("#review-total").textContent = "Ratings unavailable";
      $("#reviews-state").textContent = `Reviews couldn't be loaded. ${error.message}`;
      throw error;
    } finally {
      state.loading = false;
      $("#reviews-load-more").disabled = false;
    }
  }

  function readFile(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error("This photo couldn't be opened. Please choose another."));
      reader.readAsDataURL(file);
    });
  }
  async function preparePhoto(file) {
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) throw new Error("Choose a JPG, PNG or WebP photo.");
    if (!file.size || file.size > 5 * 1024 * 1024) throw new Error("Choose a photo up to 5 MB.");
    const source = await readFile(file);
    const image = new Image();
    image.src = source;
    try { await image.decode(); } catch { throw new Error("This photo couldn't be opened. Please choose another."); }
    if (image.naturalWidth > 12000 || image.naturalHeight > 12000 || image.naturalWidth * image.naturalHeight > 32_000_000) throw new Error("This photo is too large. Choose one with fewer than 32 million pixels.");
    const scale = Math.min(1, 1600 / Math.max(image.naturalWidth, image.naturalHeight));
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
    canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Photo preparation is unavailable. Please try another browser.");
    context.fillStyle = "#fff";
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.drawImage(image, 0, 0, canvas.width, canvas.height);
    // Re-encoding respects browser image orientation and discards file metadata.
    return { name: "review-photo.jpg", data: canvas.toDataURL("image/jpeg", 0.86) };
  }
  $("#review-image").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const version = ++state.photoVersion;
    state.processing = true;
    message("");
    updateBusy();
    try {
      const photo = await preparePhoto(file);
      if (version !== state.photoVersion || !state.active) return;
      state.photo = photo;
      state.photoChanged = true;
      showPhoto(photo.data);
    } catch (error) {
      if (version === state.photoVersion) { event.target.value = ""; message(error.message); }
    } finally {
      if (version === state.photoVersion) { state.processing = false; updateBusy(); }
    }
  });
  $("#review-image-remove").addEventListener("click", () => {
    ++state.photoVersion;
    state.photo = null;
    state.photoChanged = true;
    state.processing = false;
    $("#review-image").value = "";
    showPhoto(null);
    updateBusy();
    message("");
  });
  $("#review-anonymous").addEventListener("change", updateAuthor);
  $("#review-body").addEventListener("input", updateCount);
  $("#review-cancel-edit").addEventListener("click", () => { fillForm(); message("Your published review is unchanged.", true); });
  $("#review-delete-own").addEventListener("click", (event) => openDelete(event.currentTarget));
  $("#reviews-load-more").addEventListener("click", () => { loadReviews(true).catch(() => {}); });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (state.busy || state.processing || !form.reportValidity()) return;
    if (!state.user) { requireSignIn(); return; }
    const body = {
      rating: Number(new FormData(form).get("rating")),
      title: $("#review-title").value.trim(),
      body: $("#review-body").value.trim(),
      anonymous: $("#review-anonymous").checked,
    };
    if (body.body.length < 20) { message("Tell us a little more: your review needs at least 20 characters."); $("#review-body").focus(); return; }
    state.busy = true;
    updateBusy();
    message("");
    const editing = Boolean(state.own);
    try {
      if (state.photoChanged || !editing) {
        body.image = state.photo ? (await window.VeloraAuth.request("/api/reviews/uploads", { method: "POST", body: state.photo })).uploadToken : null;
      }
      const result = await window.VeloraAuth.request(editing ? `/api/reviews/${state.own.id}` : "/api/reviews", { method: editing ? "PATCH" : "POST", body });
      if (!state.active) return;
      state.own = result.review;
      fillForm();
      message(editing ? "Your review has been updated." : "Thank you. Your review has been published.", true);
      await loadReviews().catch(() => { message("Your review was saved. The list couldn't refresh; reload the page to see it.", true); });
    } catch (error) {
      message(error.message || "Your review couldn't be saved. Please try again.");
      if (error.status === 409) {
        try {
          const { review } = await window.VeloraAuth.request("/api/reviews/mine");
          if (review) {
            state.own = review;
            fillForm();
            message("You already have a published review. You can update it below.", true);
          }
        } catch { /* Keep the original error and let the customer retry. */ }
      }
      if (error.status === 401) {
        requireSignIn();
        $("#reviews-state").textContent = "Your session has ended. Sign in again to publish your review.";
      }
    } finally { state.busy = false; updateBusy(); }
  });

  function closeDelete() {
    if (state.busy) return;
    $("#review-delete-dialog").close();
    state.deleteOpener?.focus();
  }
  $("#review-delete-cancel").addEventListener("click", closeDelete);
  $("#review-delete-dialog").addEventListener("cancel", (event) => { event.preventDefault(); closeDelete(); });
  $("#review-delete-confirm").addEventListener("click", async () => {
    if (state.busy || !state.own) return;
    state.busy = true;
    $("#review-delete-confirm").disabled = true;
    $("#review-delete-cancel").disabled = true;
    updateBusy();
    let deleted = false;
    try {
      await window.VeloraAuth.request(`/api/reviews/${state.own.id}`, { method: "DELETE", body: {} });
      state.own = null;
      fillForm();
      $("#review-delete-dialog").close();
      deleted = true;
      message("Your review and its photo have been deleted.", true);
      await loadReviews().catch(() => {});
    } catch (error) {
      $("#review-delete-dialog").close();
      message(error.message || "Your review couldn't be deleted. Please try again.");
      if (error.status === 401) requireSignIn();
    } finally {
      state.busy = false;
      $("#review-delete-confirm").disabled = false;
      $("#review-delete-cancel").disabled = false;
      updateBusy();
      if (deleted) $("#review-title").focus();
      else if (state.deleteOpener?.isConnected) state.deleteOpener.focus();
      else if (!state.user) $("#review-signin a")?.focus();
    }
  });
  $("#review-photo-close").addEventListener("click", () => $("#review-photo-dialog").close());
  $("#review-photo-dialog").addEventListener("close", () => {
    $("#review-photo-image").removeAttribute("src");
    if (state.photoOpener?.isConnected) state.photoOpener.focus();
  });
  $("#review-photo-dialog").addEventListener("click", (event) => { if (event.target === $("#review-photo-dialog")) $("#review-photo-dialog").close(); });

  loadReviews().catch(() => {});
  window.VeloraAuth.ready.then(setUser).catch((error) => {
    requireSignIn();
    $("#review-signin").append(element("p", "review-connection-error", error.message));
  });
  window.addEventListener("focus", async () => {
    if (state.busy || state.processing || Date.now() - state.checkedAt < 5000 || !state.active) return;
    state.checkedAt = Date.now();
    try {
      const previousId = state.user?.id;
      const { user } = await window.VeloraAuth.request("/api/auth/me");
      if (previousId !== user?.id) { await setUser(user); message(""); }
      else { state.user = user; updateAuthor(); }
    } catch { /* Submission still rechecks the session on the server. */ }
  });
  window.addEventListener("pagehide", () => {
    state.active = false;
    ++state.photoVersion;
    state.photo = null;
    state.user = null;
    state.own = null;
    form.reset();
    form.hidden = true;
    showPhoto(null);
    $("#review-account-name").textContent = "";
    $("#review-author-preview").textContent = "";
    if ($("#review-photo-dialog").open) $("#review-photo-dialog").close();
    if ($("#review-delete-dialog").open) $("#review-delete-dialog").close();
  });
  window.addEventListener("pageshow", (event) => { if (event.persisted) location.reload(); });
})();
