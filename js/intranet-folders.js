(() => {
  "use strict";
  const auth = window.VeloraAuth;
  const $ = (id) => document.getElementById(id);
  if (!auth || !$("intranet-folder-grid")) return;
  const grid = $("intranet-folder-grid");
  const browser = $("intranet-file-browser");
  const list = $("intranet-file-list");
  const feedback = $("intranet-folder-feedback");
  let folders = [], files = [], current = null, shown = 30, generation = 0, deleting = null, writing = false;
  const folderPath = "M3 7a2 2 0 0 1 2-2h5l2 3h7a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z";
  const lockPath = "M8 10V7a4 4 0 0 1 8 0v3M6 10h12v11H6zM12 14v3";
  const filePath = "M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h6";
  const imagePath = "M3 4h18v16H3zM3 16l5-5 5 5 3-3 5 5M15 8h.01";
  function icon(path, className = "") {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", "0 0 24 24"); svg.setAttribute("fill", "none"); svg.setAttribute("stroke", "currentColor"); svg.setAttribute("stroke-width", "1.35"); svg.setAttribute("stroke-linecap", "round"); svg.setAttribute("stroke-linejoin", "round"); svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("class", className);
    const line = document.createElementNS(svg.namespaceURI, "path"); line.setAttribute("d", path); svg.append(line); return svg;
  }
  function element(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; }
  function say(text, error = false) { feedback.textContent = text; feedback.classList.toggle("is-error", error); feedback.setAttribute("role", error ? "alert" : "status"); }
  function safeURL(value, operation) {
    if (typeof value !== "string") return null;
    try {
      const url = new URL(value, location.origin);
      return url.origin === location.origin && /^\/api\/intranet\/files\/[A-Za-z0-9_-]+\/(download|preview)$/.test(url.pathname) && url.pathname.endsWith(`/${operation}`) && !url.search && !url.hash ? url.pathname : null;
    } catch { return null; }
  }
  function bytes(size) { return size < 1024 ? `${size} B` : size < 1048576 ? `${(size / 1024).toFixed(0)} KB` : `${(size / 1048576).toFixed(1)} MB`; }
  function date(value) { if (!value) return ""; const d = new Date(value); return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" }); }
  function closeDialogs() {
    document.querySelectorAll(".intranet-folder-dialog[open]").forEach((dialog) => dialog.close());
    $("intranet-read-note-content").textContent = "";
    $("intranet-note-form").reset(); deleting = null;
  }
  function closeFolder(focus = false) {
    generation++; current = null; files = []; list.replaceChildren(); browser.hidden = true; grid.hidden = false; closeDialogs();
    if (focus) grid.querySelector("button:not(:disabled)")?.focus();
  }
  function renderFolders() {
    grid.replaceChildren();
    folders.forEach((folder, index) => {
      const button = element("button", `intranet-department-folder ${folder.sensitive ? "is-sensitive" : ""} ${!folder.canRead ? "is-locked" : ""}`);
      button.type = "button"; button.dataset.folder = folder.id;
      button.disabled = !folder.canRead;
      button.setAttribute("aria-label", `${folder.name}: ${folder.canRead ? folder.canWrite ? "Manage files" : "Read files" : "Access restricted"}`);
      const top = element("span", "intranet-folder-top"); top.append(icon(folderPath, "intranet-folder-art"));
      const badge = element("span", "intranet-folder-badge", folder.sensitive ? "Restricted" : folder.id === "company" ? "Company library" : "Department");
      if (folder.sensitive) badge.prepend(icon(lockPath));
      top.append(badge);
      const name = element("strong", "", folder.name);
      const description = element("span", "intranet-department-description", folder.description);
      const bottom = element("span", "intranet-department-footer");
      const label = !folder.canRead ? "Access required" : `${folder.fileCount ?? 0} ${folder.fileCount === 1 ? "file" : "files"}`;
      bottom.append(element("span", "", label), element("span", "", !folder.canRead ? "Locked" : folder.canWrite ? "Manage ↗" : "Open ↗"));
      button.append(top, name, description, bottom);
      button.style.setProperty("--folder-order", index);
      if (folder.canRead) button.addEventListener("click", () => openFolder(folder.id));
      grid.append(button);
    });
    $("intranet-department-count").textContent = String(folders.filter((folder) => folder.id !== "company").length);
  }
  async function refreshFolders(announce = true) {
    try {
      const result = await auth.request("/api/intranet/folders");
      folders = result.folders || []; renderFolders();
      if (current) {
        const updated = folders.find((folder) => folder.id === current.id);
        if (!updated?.canRead) { closeFolder(); say("Your access to that folder has changed. Contact your administrator if you need access.", true); return; }
        current = updated; $("intranet-file-write-actions").hidden = !current.canWrite;
        $("intranet-open-folder-access").textContent = current.canWrite ? "Manage access · upload, add notes and delete private files" : "Read access · view and download files";
        renderFiles();
        if (!current.canWrite) closeDialogs();
      }
      if (announce) say("Choose a folder. Locked spaces require a permission grant from your administrator.");
    } catch (error) { await handleError(error, true); }
  }
  async function handleError(error, accessCheck = false) {
    if (error.status === 401) { closeFolder(); grid.replaceChildren(); location.replace("login.html?next=intranet.html"); return; }
    if (error.status === 403) {
      closeFolder();
      if (!accessCheck) await refreshFolders(false); else { grid.replaceChildren(); }
    }
    say(error.message || "This folder could not be loaded. Please try again.", true);
  }
  async function openFolder(id, moveFocus = true) {
    const folder = folders.find((item) => item.id === id);
    if (!folder?.canRead) return;
    const requestGeneration = ++generation;
    current = folder; files = []; shown = 30; closeDialogs();
    grid.hidden = true; browser.hidden = false;
    $("intranet-open-folder-name").textContent = folder.name;
    $("intranet-open-folder-description").textContent = folder.description;
    $("intranet-open-folder-access").textContent = folder.canWrite ? "Manage access · upload, add notes and delete private files" : "Read access · view and download files";
    $("intranet-file-write-actions").hidden = !folder.canWrite;
    $("intranet-library-note").hidden = id !== "company";
    $("intranet-file-search").value = "";
    list.replaceChildren(element("p", "intranet-files-empty", "Loading shared files…")); list.setAttribute("aria-busy", "true");
    $("intranet-show-files").hidden = true;
    say("");
    try {
      const result = await auth.request(`/api/intranet/folders/${encodeURIComponent(id)}/files`);
      if (generation !== requestGeneration) return;
      current = result.folder; files = result.files || [];
      $("intranet-file-write-actions").hidden = !current.canWrite;
      renderFiles();
      if (moveFocus) $("intranet-folders-back").focus({ preventScroll: true });
    } catch (error) { if (generation === requestGeneration) await handleError(error); }
    finally { if (generation === requestGeneration) list.setAttribute("aria-busy", "false"); }
  }
  function renderFiles() {
    list.replaceChildren();
    const query = $("intranet-file-search").value.trim().toLocaleLowerCase();
    const found = files.filter((file) => !query || `${file.name} ${file.kind}`.toLocaleLowerCase().includes(query));
    if (!found.length) list.append(element("p", "intranet-files-empty", files.length ? "No files match your search." : "A clear space for your team's work. Add the first document, image or note when you have manage access."));
    found.slice(0, shown).forEach((file) => {
      const card = element("article", "intranet-file-card");
      const picture = element("div", `intranet-file-picture is-${file.kind}`);
      const preview = safeURL(file.previewUrl, "preview");
      if (preview && file.kind === "image") {
        const img = element("img"); img.src = preview; img.alt = file.name; img.loading = "lazy"; img.decoding = "async";
        img.addEventListener("error", () => { img.remove(); picture.append(icon(imagePath)); }, { once: true });
        picture.append(img);
      } else picture.append(icon(file.kind === "image" ? imagePath : filePath));
      const copy = element("div", "intranet-file-copy");
      copy.append(element("span", "intranet-file-source", file.source === "website" ? "PUBLIC WEBSITE ORIGINAL" : "PRIVATE SHARED FILE"), element("h3", "", file.name));
      const detail = [file.kind === "note" ? "Team note" : file.kind === "image" ? "Image" : "Document", bytes(Number(file.size) || 0), date(file.createdAt)].filter(Boolean).join(" · ");
      copy.append(element("p", "intranet-file-details", detail));
      const actions = element("div", "intranet-file-actions");
      const download = safeURL(file.downloadUrl, "download");
      if (file.kind === "note" && download) {
        const read = element("button", "", "Read note"); read.type = "button"; read.addEventListener("click", () => readNote(file)); actions.append(read);
      }
      if (download) { const link = element("a", "", "Download"); link.href = download; link.download = file.name; actions.append(link); }
      if (file.canDelete && current?.canWrite && file.source !== "website") {
        const remove = element("button", "intranet-file-delete", "Delete"); remove.type = "button"; remove.disabled = writing;
        remove.addEventListener("click", () => { deleting = file; $("intranet-delete-description").textContent = `“${file.name}” will be permanently removed from this shared folder.`; $("intranet-delete-dialog").showModal(); }); actions.append(remove);
      }
      copy.append(actions); card.append(picture, copy); list.append(card);
    });
    $("intranet-show-files").hidden = found.length <= shown;
    $("intranet-file-help").textContent = `${found.length} ${found.length === 1 ? "file" : "files"}${query ? " matching your search" : " in this folder"}. ${current?.canWrite ? "Uploads: JPG, PNG, WebP, GIF, PDF, TXT, CSV and Office documents, up to 8 MB each." : "Read access allows viewing and downloading."}`;
  }
  async function readNote(file) {
    const requestGeneration = generation;
    try {
      const response = await fetch(safeURL(file.downloadUrl, "download"), { credentials: "same-origin", cache: "no-store", redirect: "error" });
      if (!response.ok) { const error = new Error("This note is no longer available with your current permissions."); error.status = response.status; throw error; }
      const text = await response.text();
      if (requestGeneration !== generation) return;
      $("intranet-read-note-title").textContent = file.name;
      $("intranet-read-note-content").textContent = text;
      $("intranet-read-note-dialog").showModal();
    } catch (error) { await handleError(error); }
  }
  function readData(file) { return new Promise((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = () => reject(new Error(`Could not read ${file.name}.`)); reader.readAsDataURL(file); }); }
  function setWriting(value) {
    writing = value;
    $("intranet-upload-button").disabled = value;
    $("intranet-new-note").disabled = value;
    $("intranet-save-note").disabled = value;
    $("intranet-confirm-delete").disabled = value;
    list.querySelectorAll(".intranet-file-delete").forEach((button) => { button.disabled = value; });
  }
  $("intranet-folders-back").addEventListener("click", () => { closeFolder(true); say("Choose a department folder to continue."); });
  $("intranet-folder-refresh").addEventListener("click", async () => { if (!current) return; const id = current.id; await refreshFolders(false); if (current?.id === id) await openFolder(id, false); });
  $("intranet-file-search").addEventListener("input", () => { shown = 30; renderFiles(); });
  $("intranet-show-files").addEventListener("click", () => { shown += 30; renderFiles(); });
  $("intranet-upload-button").addEventListener("click", () => $("intranet-upload-input").click());
  $("intranet-upload-input").addEventListener("change", async (event) => {
    if (writing || !current?.canWrite) return;
    const selected = [...event.target.files]; event.target.value = ""; if (!selected.length) return;
    const id = current.id; setWriting(true); let saved = 0;
    try {
      for (const file of selected) {
        if (file.size > 8 * 1024 * 1024) throw new Error(`“${file.name}” exceeds the 8 MB file limit.`);
        if (current?.id !== id) break;
        say(`Uploading ${saved + 1} of ${selected.length}: ${file.name}`);
        const data = await readData(file);
        await auth.request(`/api/intranet/folders/${encodeURIComponent(id)}/files`, { method: "POST", body: { name: file.name, data } }); saved++;
      }
      if (current?.id === id) { await openFolder(id, false); say(`${saved} ${saved === 1 ? "file" : "files"} uploaded to this folder.`); }
      await refreshFolders(false);
    } catch (error) { if (saved && current?.id === id) await openFolder(id, false); await handleError(error); }
    finally { setWriting(false); }
  });
  $("intranet-new-note").addEventListener("click", () => { if (!current?.canWrite) return; $("intranet-note-form").reset(); $("intranet-note-feedback").textContent = ""; $("intranet-note-dialog").showModal(); });
  $("intranet-note-form").addEventListener("submit", async (event) => {
    event.preventDefault(); if (writing || !current?.canWrite) return; const id = current.id;
    setWriting(true); $("intranet-note-feedback").textContent = "Saving your note…";
    try {
      await auth.request(`/api/intranet/folders/${encodeURIComponent(id)}/files`, { method: "POST", body: { name: $("intranet-note-name").value.trim(), kind: "note", text: $("intranet-note-text").value } });
      $("intranet-note-dialog").close(); if (current?.id === id) await openFolder(id, false); say("Your note is saved with this folder's access rules."); await refreshFolders(false);
    } catch (error) { $("intranet-note-feedback").textContent = error.message; if ([401, 403].includes(error.status)) await handleError(error); }
    finally { setWriting(false); }
  });
  $("intranet-confirm-delete").addEventListener("click", async () => {
    if (!deleting || writing || !current?.canWrite) return; const id = current.id, file = deleting;
    setWriting(true); $("intranet-confirm-delete").disabled = true;
    try { await auth.request(`/api/intranet/files/${encodeURIComponent(file.id)}`, { method: "DELETE", body: {} }); $("intranet-delete-dialog").close(); deleting = null; if (current?.id === id) await openFolder(id, false); say("The private file was deleted."); await refreshFolders(false); }
    catch (error) { $("intranet-delete-dialog").close(); await handleError(error); }
    finally { setWriting(false); $("intranet-confirm-delete").disabled = false; }
  });
  $("intranet-cancel-delete").addEventListener("click", () => { $("intranet-delete-dialog").close(); deleting = null; });
  document.querySelectorAll("[data-intranet-dialog-close]").forEach((button) => button.addEventListener("click", () => button.closest("dialog").close()));
  $("intranet-read-note-dialog").addEventListener("close", () => { $("intranet-read-note-content").textContent = ""; });
  auth.ready.then((user) => { if (user) return refreshFolders(); }).catch((error) => say(error.message, true));
  window.addEventListener("focus", () => { if (auth.user) refreshFolders(false); });
  window.addEventListener("pagehide", () => { closeFolder(); grid.replaceChildren(); });
  window.addEventListener("velora:auth-changed", (event) => { if (!event.detail.user) { closeFolder(); grid.replaceChildren(); location.replace("login.html?next=intranet.html"); } });
})();
