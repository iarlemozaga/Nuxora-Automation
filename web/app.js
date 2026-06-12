const API = "/api";

let token = localStorage.getItem("nx_token");
let selectedGuild = localStorage.getItem("nx_guild");
let guilds = [];
let allApplications = [];
let currentApplicationFilter = "pending";
let currentUser = null;
let adminUsers = [];
let adminGuilds = [];
let liveNotifications = [];
let currentAllowlistQuestions = [];

function el(id) {
  return document.getElementById(id);
}

function isAdmin() {
  return currentUser && ["admin", "owner"].includes(currentUser.role);
}

function embedFooterStorageKey() {
  return `nx_embed_footer_${selectedGuild || "global"}`;
}

function embedFooterFixedStorageKey() {
  return `nx_embed_footer_fixed_${selectedGuild || "global"}`;
}

function loadSavedEmbedFooter() {
  const footerInput = el("embed_footer");
  const footerFixedInput = el("embed_footer_fixed");

  if (!footerInput) return;

  const isFixed = localStorage.getItem(embedFooterFixedStorageKey()) === "true";

  if (footerFixedInput) {
    footerFixedInput.checked = isFixed;
  }

  footerInput.value = isFixed
    ? localStorage.getItem(embedFooterStorageKey()) || ""
    : "";
}

function saveEmbedFooterPreference() {
  const footerInput = el("embed_footer");
  const footerFixedInput = el("embed_footer_fixed");

  if (!footerInput || !footerFixedInput) return;

  if (footerFixedInput.checked) {
    localStorage.setItem(embedFooterFixedStorageKey(), "true");
    localStorage.setItem(embedFooterStorageKey(), footerInput.value || "");
  } else {
    localStorage.removeItem(embedFooterFixedStorageKey());
    localStorage.removeItem(embedFooterStorageKey());
  }
}

function authHeaders() {
  return {
    Authorization: "Bearer " + token,
    "Content-Type": "application/json",
  };
}

async function loadMe() {
  const res = await fetch(API + "/me", {
    headers: authHeaders(),
  });

  if (!res.ok) {
    currentUser = null;
    return null;
  }

  currentUser = await res.json();

  const adminBtn = el("adminNavBtn");
  if (adminBtn) {
    adminBtn.classList.toggle("hidden", !isAdmin());
  }

  return currentUser;
}

function showApp() {
  const sidebar = el("sidebar");
  const topBar = el("topBar");
  if (sidebar) sidebar.classList.remove("hidden");
  if (topBar) topBar.classList.remove("hidden");
  el("login").classList.add("hidden");
  el("app").classList.remove("hidden");
  el("guildBox").classList.remove("hidden");
  el("status").innerText = "online";
}

function showLogin() {
  const sidebar = el("sidebar");
  const topBar = el("topBar");
  if (sidebar) sidebar.classList.add("hidden");
  if (topBar) topBar.classList.add("hidden");
  el("login").classList.remove("hidden");
  el("app").classList.add("hidden");
  el("guildBox").classList.add("hidden");
  el("status").innerText = "offline";
}

function logout() {
  localStorage.removeItem("nx_token");
  localStorage.removeItem("nx_guild");
  location.reload();
}

async function doLogin() {
  try {
    const usernameInput = el("username");
    const passwordInput = el("password");

    if (!usernameInput || !passwordInput) {
      alert("Campos de login não encontrados no painel.");
      return;
    }

    console.log("Tentando login no painel", { username: usernameInput.value });

    const res = await fetch(API + "/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: usernameInput.value,
        password: passwordInput.value,
      }),
    });

    if (!res.ok) {
      const errorText = await res.text();
      console.error("Login recusado", res.status, errorText);
      alert("Login inválido ou API indisponível: " + errorText);
      return;
    }

    const data = await res.json();
    token = data.token;
    localStorage.setItem("nx_token", token);

    await boot();
  } catch (err) {
    console.error("Erro ao tentar fazer login", err);
    alert("Erro ao tentar fazer login. Veja o console do navegador.");
  }
}

async function boot() {
  showApp();
  bindSidebar();

  const me = await loadMe();

  if (!me) {
    showLogin();
    return;
  }

  await loadGuilds();

  if (guilds.length) {
    const foundSelected = guilds.find((g) => g.guild_id == selectedGuild);
    if (!selectedGuild || !foundSelected) {
      selectedGuild = guilds[0].guild_id;
    }

    localStorage.setItem("nx_guild", selectedGuild);
    await loadDashboard();
  } else {
    showTab("servers");
  }
}

async function loadGuilds() {
  const res = await fetch(API + "/guilds", {
    headers: authHeaders(),
  });

  if (!res.ok) {
    showLogin();
    return;
  }

  const data = await res.json();
  guilds = data.guilds || [];

  el("guildSelector").innerHTML = guilds
    .map((g) => {
      return `<option value="${g.guild_id}" ${g.guild_id == selectedGuild ? "selected" : ""}>${esc(g.guild_name)} • ${g.guild_id}</option>`;
    })
    .join("");

  renderGuilds();
}

function selectGuild(id) {
  selectedGuild = id;
  localStorage.setItem("nx_guild", id);
  loadDashboard();
}

async function addGuild() {
  const guildId = el("new_guild_id").value;
  const guildName = el("new_guild_name").value || "Servidor";

  const res = await fetch(API + "/guilds", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      guild_id: guildId,
      guild_name: guildName,
    }),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  await loadGuilds();

  selectedGuild = guildId.replace(/\D/g, "");
  localStorage.setItem("nx_guild", selectedGuild);

  await loadDashboard();
  showTab("dashboard");
}

function renderGuilds() {
  if (!guilds.length) {
    el("guilds-list").innerHTML =
      '<br><p class="muted">Nenhum servidor vinculado à sua conta ainda.</p>';
    return;
  }

  el("guilds-list").innerHTML =
    "<br><table><tr><th>Servidor</th><th>ID</th><th>Status</th><th>Ações</th></tr>" +
    guilds
      .map((g) => {
        const removeButton = isAdmin()
          ? `<button type="button" class="danger" onclick="removeGuild('${g.guild_id}')">Remover</button>`
          : "";

        return `
                                <tr>
                                    <td>${esc(g.guild_name)}</td>
                                    <td>${g.guild_id}</td>
                                    <td>${esc(g.status)}</td>
                                    <td>
                                        <button type="button" class="blue" onclick="selectGuild('${g.guild_id}')">Abrir</button>
                                        ${removeButton}
                                    </td>
                                </tr>
                            `;
      })
      .join("") +
    "</table>";
}

async function inviteBot() {
  const res = await fetch(API + "/discord/invite-url", {
    headers: authHeaders(),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  const data = await res.json();

  if (!data.url) {
    alert("URL de convite não retornada pela API.");
    return;
  }

  window.open(data.url, "_blank");
}

async function removeGuild(guildId) {
  if (!confirm("Tem certeza que deseja remover este servidor do painel?")) {
    return;
  }

  const res = await fetch(API + "/guilds/" + guildId, {
    method: "DELETE",
    headers: authHeaders(),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  if (selectedGuild === guildId) {
    selectedGuild = null;
    localStorage.removeItem("nx_guild");
  }

  await loadGuilds();

  if (guilds.length) {
    selectedGuild = guilds[0].guild_id;
    localStorage.setItem("nx_guild", selectedGuild);
    await loadDashboard();
  } else {
    showTab("servers");
  }

  alert("Servidor removido.");
}

function showTab(name) {
  if (name === "admin" && !isAdmin()) {
    alert("Acesso restrito ao admin.");
    name = "dashboard";
  }

  [
    "dashboard",
    "applications",
    "suggestions",
    "tickets",
    "settings",
    "servers",
    "admin",
    "embeds",
    "lives",
    "account",
  ].forEach((t) => {
    const tab = el("tab-" + t);
    if (tab) {
      tab.classList.toggle("hidden", t !== name);
    }
  });

  document.querySelectorAll(".nav-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.getAttribute("data-tab") === name);
  });

  el("currentPageLabel").innerText =
    {
      dashboard: "Dashboard",
      applications: "Allowlist",
      suggestions: "Sugestões",
      tickets: "Tickets",
      settings: "Configurações",
      servers: "Servidores",
      admin: "Admin",
      embeds: "Embeds",
      lives: "Lives",
      account: "Minha conta",
    }[name] || "Painel";

  if (name === "admin") {
    adminLoad();
  }

  if (name === "lives") {
    loadLiveNotifications();
  }
}

function bindSidebar() {
  document.querySelectorAll(".nav-btn[data-tab]").forEach((btn) => {
    btn.onclick = () => showTab(btn.getAttribute("data-tab"));
  });
}

async function loadDashboard() {
  loadSavedEmbedFooter();
  if (!selectedGuild) {
    showTab("servers");
    return;
  }

  const res = await fetch(API + "/guilds/" + selectedGuild + "/dashboard", {
    headers: authHeaders(),
  });

  if (!res.ok) {
    showTab("servers");
    return;
  }

  const data = await res.json();
  const s = data.stats || {};

  el("stat-apps").innerText = s.applications || 0;
  el("stat-pending").innerText = s.pending || 0;
  el("stat-approved").innerText = s.approved || 0;
  el("stat-rejected").innerText = s.rejected || 0;
  el("stat-interview").innerText = s.interview || 0;

  allApplications = data.applications || [];

  renderApplications();
  renderSuggestions(data.suggestions || []);
  fillSettings(data.settings || {});

  showTab("dashboard");
}

function setApplicationFilter(st) {
  currentApplicationFilter = st;

  ["all", "pending", "approved", "rejected", "interview"].forEach((s) => {
    const b = el("filter-" + s);
    if (b) {
      b.classList.toggle("active", s === st);
    }
  });

  renderApplications();
}

function renderApplications() {
  const items =
    currentApplicationFilter === "all"
      ? allApplications
      : allApplications.filter((a) => a.status === currentApplicationFilter);

  let html =
    "<table><tr><th>ID</th><th>Usuário</th><th>Status</th><th>Respostas</th><th>Ações</th></tr>";

  for (const a of items) {
    let ans = "";

    try {
      ans = JSON.parse(a.answers || "[]")
        .map((x) => `<b>${esc(x.question)}</b><br>${esc(x.answer)}`)
        .join("<hr>");
    } catch (e) {
      ans = esc(a.answers || "");
    }

    html += `
                    <tr>
                        <td>${a.id}</td>
                        <td>${esc(a.discord_name)}<br><small>${a.discord_id}</small></td>
                        <td><b>${a.status}</b></td>
                        <td>${ans}</td>
                        <td>
                            <button class="green" type="button" onclick="setAppStatus(${a.id}, 'approved')">Aprovar</button>
                            <button class="blue" type="button" onclick="setAppStatus(${a.id}, 'interview')">Entrevista</button>
                            <button class="danger" type="button" onclick="setAppStatus(${a.id}, 'rejected')">Reprovar</button>
                            <button class="danger" type="button" onclick="deleteApplication(${a.id})">Excluir</button>
                        </td>
                    </tr>
                `;
  }

  el("applications-table").innerHTML = html + "</table>";
}

function renderSuggestions(items) {
  let html =
    "<table><tr><th>ID</th><th>Usuário</th><th>Status</th><th>Conteúdo</th><th>Ações</th></tr>";

  for (const s of items) {
    html += `
                    <tr>
                        <td>${s.id}</td>
                        <td>${esc(s.discord_name)}</td>
                        <td>${esc(s.status)}</td>
                        <td>${esc(s.content)}</td>
                        <td>
                            <button class="green" type="button" onclick="setSuggestionStatus(${s.id}, 'accepted')">Aceita</button>
                            <button class="blue" type="button" onclick="setSuggestionStatus(${s.id}, 'implemented')">Implementada</button>
                            <button class="danger" type="button" onclick="setSuggestionStatus(${s.id}, 'rejected')">Negada</button>
                            <button class="danger" type="button" onclick="deleteSuggestion(${s.id})">Excluir</button>
                        </td>
                    </tr>
                `;
  }

  el("suggestions-table").innerHTML = html + "</table>";
}

async function setAppStatus(id, status) {
  const res = await fetch(
    API + `/guilds/${selectedGuild}/applications/${id}/status`,
    {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify({ status }),
    },
  );

  if (!res.ok) {
    alert("Erro ao alterar");
    return;
  }

  await loadDashboard();
  alert("Status atualizado");
}

async function deleteApplication(id) {
  if (!confirm("Excluir esta allowlist?")) return;

  const res = await fetch(API + `/guilds/${selectedGuild}/applications/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  await loadDashboard();
  alert("Allowlist excluída.");
}

async function setSuggestionStatus(id, status) {
  const res = await fetch(
    API + `/guilds/${selectedGuild}/suggestions/${id}/status`,
    {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify({ status }),
    },
  );

  if (!res.ok) {
    alert("Erro ao alterar");
    return;
  }

  await loadDashboard();
}

async function deleteSuggestion(id) {
  if (!confirm("Excluir esta sugestão?")) return;

  const res = await fetch(API + `/guilds/${selectedGuild}/suggestions/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  await loadDashboard();
  alert("Sugestão excluída.");
}

function setValue(id, v) {
  const input = el(id);
  if (input) {
    input.value = v || "";
  }
}

function fillSettings(s) {
  [
    "allowlist_title",
    "allowlist_description",
    "allowlist_footer",
    "allowlist_image_url",
    "allowlist_thumbnail_url",
    "allowlist_category_id",
    "staff_channel_id",
    "suggestion_channel_id",
    "approved_role_id",
    "remove_role_on_approved_id",
    "interview_role_id",
    "approved_channel_id",
    "rejected_channel_id",
    "autorole_role_id",
    "bot_color",
    "bot_profile_nick",
    "bot_profile_avatar_url",
    "bot_profile_banner_url",
    "bot_profile_bio",
    "ticket_panel_title",
    "ticket_panel_description",
    "ticket_panel_footer",
    "ticket_panel_image_url",
    "ticket_panel_thumbnail_url",
    "ticket_panel_color",
    "ticket_category_id",
    "ticket_staff_role_id",
    "logs_channel_id",
    "member_join_channel_id",
    "member_join_title",
    "member_join_description",
    "member_join_footer",
    "member_join_color",
    "member_join_image_url",
    "member_leave_channel_id",
    "member_leave_title",
    "member_leave_description",
    "member_leave_footer",
    "member_leave_color",
    "member_leave_image_url",
    "allowlist_approved_title",
    "allowlist_approved_description",
    "allowlist_approved_color",
    "allowlist_approved_footer",
    "allowlist_rejected_title",
    "allowlist_rejected_description",
    "allowlist_rejected_color",
    "allowlist_rejected_footer",
    "allowlist_interview_title",
    "allowlist_interview_description",
    "allowlist_interview_color",
    "allowlist_interview_footer",
  ].forEach((k) => setValue(k, s[k] || ""));

  try {
    currentAllowlistQuestions = JSON.parse(s.allowlist_questions || "[]");
    setValue("allowlist_questions", currentAllowlistQuestions.join("\n"));
  } catch (e) {
    currentAllowlistQuestions = [];
    setValue("allowlist_questions", "");
  }

  try {
    renderAnswerRoleMappings(
      JSON.parse(s.allowlist_answer_role_mappings || "[]"),
      currentAllowlistQuestions,
    );
  } catch (e) {
    renderAnswerRoleMappings([], currentAllowlistQuestions);
  }

  let types = [];

  try {
    types = JSON.parse(s.ticket_types || "[]");
  } catch (e) {}

  if (!types.length) {
    types = [
      {
        id: "suporte",
        label: "Suporte",
        emoji: "🛠️",
        description: "Suporte geral",
        style: "gray",
        category_id: "",
        allowed_role_ids: [],
      },
    ];
  }

  renderTicketTypes(types);
}

function renderAnswerRoleMappings(
  mappings,
  questions = currentAllowlistQuestions,
) {
  const box = el("allowlist-answer-role-mappings");

  if (!box) {
    return;
  }

  box.innerHTML = "";

  mappings.forEach((mapping) => {
    const div = document.createElement("div");
    div.className = "answer-role-mapping-card allowlist-answer-role-mapping";

    const selectedQuestion = mapping.question || "";
    const questionOptions = questions
      .map(
        (question) =>
          `<option value="${escAttr(question)}" ${question === selectedQuestion ? "selected" : ""}>${esc(question)}</option>`,
      )
      .join("");

    const answers = Array.isArray(mapping.answers)
      ? mapping.answers.join("\n")
      : mapping.answer || "";
    const roleIds = Array.isArray(mapping.role_ids)
      ? mapping.role_ids
      : String(mapping.role_id || "")
          .split(",")
          .map((x) => x.trim())
          .filter(Boolean);

    div.innerHTML = `
                    <label>Pergunta da allowlist</label>
                    <select class="arm-question">
                        <option value="">Selecione uma pergunta</option>
                        ${questionOptions}
                    </select>

                    <label>Respostas que ativam a regra, uma por linha</label>
                    <textarea class="arm-answers" rows="3" placeholder="Ex: Lobisomem">${esc(answers)}</textarea>

                    <label>Cargos para adicionar, separados por vírgula</label>
                    <input class="arm-role-ids" placeholder="123,456" value="${escAttr(roleIds.join(","))}">

                    <button type="button" onclick="this.parentElement.remove()">Remover regra</button>
                `;

    box.appendChild(div);
  });
}

function getAnswerRoleMappingsFromForm(options = {}) {
  const includeIncomplete = !!options.includeIncomplete;
  const mappings = Array.from(
    document.querySelectorAll(".allowlist-answer-role-mapping"),
  ).map((div) => ({
    question: div.querySelector(".arm-question").value.trim(),
    answers: div
      .querySelector(".arm-answers")
      .value.split(/\r?\n/)
      .map((x) => x.trim())
      .filter(Boolean),
    role_ids: div
      .querySelector(".arm-role-ids")
      .value.split(",")
      .map((x) => x.trim().replace(/\D/g, ""))
      .filter(Boolean),
  }));

  if (includeIncomplete) {
    return mappings;
  }

  const incomplete = mappings.find(
    (mapping) =>
      (mapping.question || mapping.answers.length || mapping.role_ids.length) &&
      (!mapping.question ||
        !mapping.answers.length ||
        !mapping.role_ids.length),
  );

  if (incomplete) {
    alert(
      "Complete todos os campos da regra de cargo por resposta: pergunta, resposta e cargo.",
    );
    return null;
  }

  return mappings.filter(
    (mapping) =>
      mapping.question && mapping.answers.length && mapping.role_ids.length,
  );
}

function addAnswerRoleMapping() {
  currentAllowlistQuestions = el("allowlist_questions")
    .value.split(/\r?\n/)
    .map((x) => x.trim())
    .filter(Boolean);

  const mappings = getAnswerRoleMappingsFromForm({ includeIncomplete: true });

  mappings.push({
    question: currentAllowlistQuestions[0] || "",
    answers: [],
    role_ids: [],
  });

  renderAnswerRoleMappings(mappings, currentAllowlistQuestions);
}

function renderTicketTypes(types) {
  const box = el("ticket-types");
  box.innerHTML = "";

  types.forEach((t) => {
    const div = document.createElement("div");
    div.className = "ticket-type";

    div.innerHTML = `
                    <label>ID</label>
                    <input class="tt-id" value="${escAttr(t.id || "")}">

                    <label>Label</label>
                    <input class="tt-label" value="${escAttr(t.label || "")}">

                    <label>Emoji</label>
                    <input class="tt-emoji" value="${escAttr(t.emoji || "")}">

                    <label>Descrição</label>
                    <textarea class="tt-description">${esc(t.description || "")}</textarea>

                    <label>Estilo</label>
                    <input class="tt-style" value="${escAttr(t.style || "gray")}">

                    <label>Categoria ID</label>
                    <input class="tt-category-id" value="${escAttr(t.category_id || "")}">

                    <label>Cargos acesso, vírgula</label>
                    <input class="tt-allowed-roles" value="${escAttr((t.allowed_role_ids || []).join(","))}">

                    <button type="button" onclick="this.parentElement.remove()">Remover</button>
                `;

    box.appendChild(div);
  });
}

function getTicketTypesFromForm() {
  const box = el("ticket-types");

  if (!box) {
    return [];
  }

  return Array.from(box.querySelectorAll(".ticket-type"))
    .map((div) => ({
      id: (div.querySelector(".tt-id")?.value || "").trim(),
      label: (div.querySelector(".tt-label")?.value || "").trim(),
      emoji: (div.querySelector(".tt-emoji")?.value || "").trim(),
      description: (div.querySelector(".tt-description")?.value || "").trim(),
      style: (div.querySelector(".tt-style")?.value || "gray").trim() || "gray",
      category_id: (div.querySelector(".tt-category-id")?.value || "").trim(),
      allowed_role_ids: (div.querySelector(".tt-allowed-roles")?.value || "")
        .split(",")
        .map((x) => x.trim())
        .filter(Boolean),
    }))
    .filter((t) => t.id && t.label);
}

function addTicketType() {
  const types = getTicketTypesFromForm();

  types.push({
    id: "novo",
    label: "Novo",
    emoji: "🎫",
    description: "Descrição",
    style: "gray",
    category_id: "",
    allowed_role_ids: [],
  });

  renderTicketTypes(types);
}

async function saveSettings() {
  try {
    if (!selectedGuild) {
      alert("Cadastre ou selecione um servidor primeiro.");
      showTab("servers");
      return;
    }

    const questionsInput = el("allowlist_questions");

    if (!questionsInput) {
      alert("Campo de perguntas da allowlist não encontrado no painel.");
      return;
    }

    const questions = questionsInput.value
      .split(/\r?\n/)
      .map((x) => x.trim())
      .filter(Boolean);

    const ids = [
      "allowlist_title",
      "allowlist_description",
      "allowlist_footer",
      "allowlist_image_url",
      "allowlist_thumbnail_url",
      "allowlist_category_id",
      "staff_channel_id",
      "suggestion_channel_id",
      "approved_role_id",
      "remove_role_on_approved_id",
      "interview_role_id",
      "approved_channel_id",
      "rejected_channel_id",
      "autorole_role_id",
      "bot_color",
      "bot_profile_nick",
      "bot_profile_avatar_url",
      "bot_profile_banner_url",
      "bot_profile_bio",
      "ticket_panel_title",
      "ticket_panel_description",
      "ticket_panel_footer",
      "ticket_panel_image_url",
      "ticket_panel_thumbnail_url",
      "ticket_panel_color",
      "ticket_category_id",
      "ticket_staff_role_id",
      "logs_channel_id",
      "member_join_channel_id",
      "member_join_title",
      "member_join_description",
      "member_join_footer",
      "member_join_color",
      "member_join_image_url",
      "member_leave_channel_id",
      "member_leave_title",
      "member_leave_description",
      "member_leave_footer",
      "member_leave_color",
      "member_leave_image_url",
      "allowlist_approved_title",
      "allowlist_approved_description",
      "allowlist_approved_color",
      "allowlist_approved_footer",
      "allowlist_rejected_title",
      "allowlist_rejected_description",
      "allowlist_rejected_color",
      "allowlist_rejected_footer",
      "allowlist_interview_title",
      "allowlist_interview_description",
      "allowlist_interview_color",
      "allowlist_interview_footer",
    ];

    currentAllowlistQuestions = questions;

    const answerRoleMappings = getAnswerRoleMappingsFromForm();

    if (answerRoleMappings === null) {
      return;
    }

    const settings = {
      allowlist_questions: questions,
      allowlist_answer_role_mappings: answerRoleMappings,
      ticket_types: getTicketTypesFromForm(),
    };

    ids.forEach((id) => {
      const input = el(id);
      settings[id] = input ? input.value : "";
    });

    console.log("Salvando configurações", {
      guild: selectedGuild,
      answerRoleMappings: settings.allowlist_answer_role_mappings,
    });

    const res = await fetch(API + `/guilds/${selectedGuild}/settings`, {
      method: "PUT",
      headers: authHeaders(),
      body: JSON.stringify({ settings }),
    });

    if (!res.ok) {
      const errorText = await res.text();
      console.error("Erro ao salvar configurações", res.status, errorText);
      alert("Erro ao salvar configurações: " + errorText);
      return;
    }

    const data = await res.json();
    console.log("Configurações salvas com sucesso", data);

    await loadDashboard();
    alert("Configurações salvas e sincronização enviada para o bot.");
  } catch (err) {
    console.error("Erro inesperado ao salvar configurações", err);
    alert(
      "Erro inesperado ao salvar configurações. Abra o console do navegador para ver detalhes.",
    );
  }
}

async function loadLiveNotifications() {
  if (!selectedGuild) {
    el("live-notifications-list").innerHTML =
      '<p class="muted">Selecione um servidor primeiro.</p>';
    return;
  }

  const res = await fetch(API + `/guilds/${selectedGuild}/live-notifications`, {
    headers: authHeaders(),
  });

  if (!res.ok) {
    el("live-notifications-list").innerHTML =
      `<p class="muted">Erro ao carregar lives: ${esc(await res.text())}</p>`;
    return;
  }

  const data = await res.json();
  liveNotifications = data.items || [];
  renderLiveNotifications();
}

function renderLiveNotifications() {
  const box = el("live-notifications-list");

  if (!box) return;

  if (!liveNotifications.length) {
    box.innerHTML =
      '<p class="muted">Nenhuma notificação de live configurada.</p>';
    return;
  }

  box.innerHTML =
    "<table><tr><th>Streamer</th><th>Canal Discord</th><th>Status</th><th>Ativa</th><th>Ações</th></tr>" +
    liveNotifications
      .map((item) => {
        const statusClass = item.is_live
          ? "live-status-online"
          : "live-status-offline";

        const statusText = item.is_live ? "Online" : "Offline";
        const enabledText = item.is_enabled ? "Sim" : "Não";
        const toggleLabel = item.is_enabled ? "Desativar" : "Ativar";

        return `
                                <tr>
                                    <td>
                                        <b>${esc(item.streamer_login)}</b><br>
                                        <small>twitch.tv/${esc(item.streamer_login)}</small>
                                    </td>
                                    <td>${esc(item.discord_channel_id)}</td>
                                    <td class="${statusClass}">${statusText}</td>
                                    <td>${enabledText}</td>
                                    <td>
                                        <button type="button" class="blue" onclick="fillLiveForm(${item.id})">Editar</button>
                                        <button type="button" onclick="toggleLiveNotification(${item.id})">${toggleLabel}</button>
                                        <button type="button" class="danger" onclick="deleteLiveNotification(${item.id})">Remover</button>
                                    </td>
                                </tr>
                            `;
      })
      .join("") +
    "</table>";
}

function fillLiveForm(id) {
  const item = liveNotifications.find((x) => Number(x.id) === Number(id));

  if (!item) return;

  el("live_streamer_login").value = item.streamer_login || "";
  el("live_discord_channel_id").value = item.discord_channel_id || "";
  el("live_message").value = item.message || "";
  el("live_embed_title").value = item.embed_title || "";
  el("live_embed_description").value = item.embed_description || "";
  el("live_embed_color").value = item.embed_color || "#9146FF";
  el("live_is_enabled").checked = !!item.is_enabled;
  el("live_streamer_login").dataset.editId = item.id;
}

function clearLiveForm() {
  el("live_streamer_login").value = "";
  el("live_discord_channel_id").value = "";
  el("live_message").value = "🔴 {streamer} está ao vivo!";
  el("live_embed_title").value = "{streamer} iniciou uma live";
  el("live_embed_description").value =
    "**{title}**\nJogando: {game}\nAssista: {url}";
  el("live_embed_color").value = "#9146FF";
  el("live_is_enabled").checked = true;
  delete el("live_streamer_login").dataset.editId;
}

async function saveLiveNotification() {
  if (!selectedGuild) {
    alert("Selecione um servidor primeiro.");
    showTab("servers");
    return;
  }

  const editId = el("live_streamer_login").dataset.editId;

  const payload = {
    streamer_login: el("live_streamer_login").value,
    discord_channel_id: el("live_discord_channel_id").value,
    message: el("live_message").value,
    embed_title: el("live_embed_title").value,
    embed_description: el("live_embed_description").value,
    embed_color: el("live_embed_color").value || "#9146FF",
    is_enabled: el("live_is_enabled").checked,
  };

  const url = editId
    ? API + `/guilds/${selectedGuild}/live-notifications/${editId}`
    : API + `/guilds/${selectedGuild}/live-notifications`;

  const res = await fetch(url, {
    method: editId ? "PATCH" : "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  clearLiveForm();
  await loadLiveNotifications();

  alert("Notificação de live salva.");
}

async function toggleLiveNotification(id) {
  const item = liveNotifications.find((x) => Number(x.id) === Number(id));
  if (!item) return;

  const res = await fetch(
    API + `/guilds/${selectedGuild}/live-notifications/${id}`,
    {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify({
        is_enabled: !item.is_enabled,
      }),
    },
  );

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  await loadLiveNotifications();
}

async function deleteLiveNotification(id) {
  if (!confirm("Remover esta notificação de live?")) return;

  const res = await fetch(
    API + `/guilds/${selectedGuild}/live-notifications/${id}`,
    {
      method: "DELETE",
      headers: authHeaders(),
    },
  );

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  await loadLiveNotifications();
}

async function changePassword() {
  const currentPassword = el("current_password").value;
  const newPassword = el("new_password").value;

  if (!currentPassword || !newPassword) {
    alert("Preencha a senha atual e a nova senha.");
    return;
  }

  const res = await fetch(API + "/me/password", {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  el("current_password").value = "";
  el("new_password").value = "";

  alert("Senha alterada com sucesso.");
}

async function sendEmbedFromPanel() {
  if (!selectedGuild) {
    alert("Selecione um servidor primeiro.");
    showTab("servers");
    return;
  }

  const res = await fetch(API + `/guilds/${selectedGuild}/embed`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      channel_id: el("embed_channel_id").value,
      title: el("embed_title").value,
      description: el("embed_description").value,
      color: el("embed_color").value || "#8B0000",
      footer: el("embed_footer").value,
      image_url: el("embed_image_url").value,
      thumbnail_url: el("embed_thumbnail_url").value,
    }),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  saveEmbedFooterPreference();
  alert("Embed enviado para o bot processar.");

  el("embed_title").value = "";
  el("embed_description").value = "";
  loadSavedEmbedFooter();
  el("embed_image_url").value = "";
  el("embed_thumbnail_url").value = "";
}

async function applyBotProfile() {
  if (!selectedGuild) {
    alert("Selecione um servidor primeiro.");
    showTab("servers");
    return;
  }

  const res = await fetch(API + `/guilds/${selectedGuild}/bot-profile`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      nick: el("bot_profile_nick").value,
      avatar_url: el("bot_profile_avatar_url").value,
      banner_url: el("bot_profile_banner_url").value,
      bio: "",
    }),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  alert("Perfil do bot enviado para aplicação. Aguarde alguns segundos.");
}

async function adminApplyBotActivity() {
  const text = el("admin_bot_activity_text").value.trim();
  const activityType = el("admin_bot_activity_type").value;

  const res = await fetch(API + "/admin/bot-activity", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      text,
      activity_type: activityType,
    }),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  alert("Atividade global enviada para o bot. Aguarde alguns segundos.");
}

async function adminLoad() {
  if (!isAdmin()) {
    return;
  }

  await adminLoadUsers();
  await adminLoadGuilds();
}

async function adminLoadUsers() {
  const res = await fetch(API + "/admin/users", {
    headers: authHeaders(),
  });

  if (!res.ok) {
    el("admin-users-list").innerHTML =
      '<p class="muted">Acesso admin indisponível para esta conta.</p>';
    return;
  }

  const data = await res.json();
  adminUsers = data.users || [];

  el("admin_link_user_id").innerHTML = adminUsers
    .filter((u) => u.is_active)
    .map((u) => {
      return `<option value="${u.id}">${esc(u.username)} • ${esc(u.email || "")} • ${esc(u.role)}</option>`;
    })
    .join("");

  el("admin-users-list").innerHTML =
    "<table><tr><th>ID</th><th>Usuário</th><th>E-mail</th><th>Role</th><th>Status</th><th>Ações</th></tr>" +
    adminUsers
      .map((u) => {
        return `
                                <tr>
                                    <td>${u.id}</td>
                                    <td>${esc(u.username)}</td>
                                    <td>${esc(u.email || "")}</td>
                                    <td>${esc(u.role)}</td>
                                    <td>${u.is_active ? "Ativo" : "Bloqueado"}</td>
                                    <td>
                                        <button type="button" class="blue" onclick="adminResetUserPassword(${u.id}, '${escAttr(u.username)}')">Resetar senha</button>
                                        <button type="button" class="danger" onclick="adminToggleUser(${u.id}, ${u.is_active ? "false" : "true"})">${u.is_active ? "Bloquear" : "Ativar"}</button>
                                        <button type="button" class="danger" onclick="adminDeleteUser(${u.id}, '${escAttr(u.username)}')">Excluir</button>
                                    </td>
                                </tr>
                            `;
      })
      .join("") +
    "</table>";
}

async function adminLoadGuilds() {
  const res = await fetch(API + "/admin/guilds", {
    headers: authHeaders(),
  });

  if (!res.ok) {
    el("admin-guilds-list").innerHTML =
      '<p class="muted">Nenhum servidor ou acesso negado.</p>';
    return;
  }

  const data = await res.json();
  adminGuilds = data.guilds || [];

  el("admin-guilds-list").innerHTML =
    "<table><tr><th>Servidor</th><th>Guild ID</th><th>Cliente</th><th>Plano</th><th>Status</th><th>Ações</th></tr>" +
    adminGuilds
      .map((g) => {
        return `
                                <tr>
                                    <td>${esc(g.guild_name)}</td>
                                    <td>${g.guild_id}</td>
                                    <td>${esc(g.username)}<br><small>${esc(g.email || "")}</small></td>
                                    <td>${esc(g.plan)}</td>
                                    <td>${esc(g.status)}</td>
                                    <td>
                                        <button type="button" class="blue" onclick="adminOpenGuild('${g.guild_id}')">Abrir</button>
                                        <button type="button" class="danger" onclick="adminRemoveGuild('${g.guild_id}')">Remover</button>
                                    </td>
                                </tr>
                            `;
      })
      .join("") +
    "</table>";
}

async function adminCreateUser() {
  const res = await fetch(API + "/admin/users", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      username: el("admin_new_username").value,
      password: el("admin_new_password").value,
      email: el("admin_new_email").value,
      role: el("admin_new_role").value,
    }),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  el("admin_new_username").value = "";
  el("admin_new_password").value = "";
  el("admin_new_email").value = "";

  await adminLoadUsers();
  alert("Cliente criado.");
}

async function adminToggleUser(userId, active) {
  const res = await fetch(API + `/admin/users/${userId}/status`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ is_active: active }),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  await adminLoadUsers();
}

async function adminResetUserPassword(userId, username) {
  const password = prompt(`Nova senha para ${username}:`);

  if (!password) {
    return;
  }

  const res = await fetch(API + `/admin/users/${userId}/password`, {
    method: "PATCH",
    headers: authHeaders(),
    body: JSON.stringify({ new_password: password }),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  alert("Senha redefinida.");
}

async function adminDeleteUser(userId, username) {
  if (
    !confirm(
      `Excluir a conta ${username}? Isso remove também os vínculos de servidores desse cliente.`,
    )
  ) {
    return;
  }

  const res = await fetch(API + `/admin/users/${userId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  await adminLoadUsers();
  await adminLoadGuilds();
  await loadGuilds();

  alert("Conta excluída.");
}

async function adminLinkGuild() {
  const res = await fetch(API + "/admin/guilds/link", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({
      user_id: Number(el("admin_link_user_id").value),
      guild_id: el("admin_link_guild_id").value,
      guild_name: el("admin_link_guild_name").value,
      plan: el("admin_link_plan").value || "manual",
      status: "active",
    }),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  el("admin_link_guild_id").value = "";
  el("admin_link_guild_name").value = "";

  await adminLoadGuilds();
  await loadGuilds();

  alert("Servidor vinculado ao cliente.");
}

async function adminRemoveGuild(guildId) {
  if (!confirm("Remover este servidor do cliente?")) return;

  const res = await fetch(API + "/admin/guilds/" + guildId, {
    method: "DELETE",
    headers: authHeaders(),
  });

  if (!res.ok) {
    alert(await res.text());
    return;
  }

  if (selectedGuild === guildId) {
    selectedGuild = null;
    localStorage.removeItem("nx_guild");
  }

  await adminLoadGuilds();
  await loadGuilds();

  alert("Servidor removido.");
}

function adminOpenGuild(guildId) {
  selectedGuild = guildId;
  localStorage.setItem("nx_guild", guildId);
  loadDashboard();
}

function esc(str) {
  return String(str || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escAttr(str) {
  return esc(str).replaceAll("\n", " ");
}

document.addEventListener("DOMContentLoaded", () => {
  const btnLogout = el("btnLogout");
  const btnManageServers = el("btnManageServers");
  const btnInviteBot = el("btnInviteBot");
  const btnAddTicketType = el("btnAddTicketType");
  const btnSaveTickets = el("btnSaveTickets");
  const btnAdminCreateUser = el("btnAdminCreateUser");
  const btnAdminLinkGuild = el("btnAdminLinkGuild");
  const btnChangePassword = el("btnChangePassword");
  const btnSendEmbed = el("btnSendEmbed");
  const btnApplyBotProfile = el("btnApplyBotProfile");
  const btnAdminApplyBotActivity = el("btnAdminApplyBotActivity");
  const btnAddLiveNotification = el("btnAddLiveNotification");
  const guildSelector = el("guildSelector");
  const embedFooter = el("embed_footer");
  const embedFooterFixed = el("embed_footer_fixed");

  if (embedFooter) {
    loadSavedEmbedFooter();
    embedFooter.addEventListener("input", () => {
      if (embedFooterFixed && embedFooterFixed.checked) {
        saveEmbedFooterPreference();
      }
    });
  }

  if (embedFooterFixed) {
    embedFooterFixed.addEventListener("change", saveEmbedFooterPreference);
  }

  if (btnLogout) btnLogout.addEventListener("click", logout);
  if (btnManageServers)
    btnManageServers.addEventListener("click", () => showTab("servers"));
  if (btnInviteBot) btnInviteBot.addEventListener("click", inviteBot);
  if (btnAddTicketType)
    btnAddTicketType.addEventListener("click", addTicketType);
  if (btnSaveTickets) btnSaveTickets.addEventListener("click", saveSettings);
  if (btnAdminCreateUser)
    btnAdminCreateUser.addEventListener("click", adminCreateUser);
  if (btnAdminLinkGuild)
    btnAdminLinkGuild.addEventListener("click", adminLinkGuild);
  if (btnChangePassword)
    btnChangePassword.addEventListener("click", changePassword);
  if (btnSendEmbed) btnSendEmbed.addEventListener("click", sendEmbedFromPanel);
  if (btnApplyBotProfile)
    btnApplyBotProfile.addEventListener("click", applyBotProfile);
  if (btnAdminApplyBotActivity)
    btnAdminApplyBotActivity.addEventListener("click", adminApplyBotActivity);
  if (btnAddLiveNotification)
    btnAddLiveNotification.addEventListener("click", saveLiveNotification);

  if (guildSelector) {
    guildSelector.addEventListener("change", (e) => {
      selectGuild(e.target.value);
    });
  }

  [
    ["filter-all", "all"],
    ["filter-pending", "pending"],
    ["filter-approved", "approved"],
    ["filter-rejected", "rejected"],
    ["filter-interview", "interview"],
  ].forEach(([id, status]) => {
    const btn = el(id);
    if (btn) {
      btn.addEventListener("click", () => setApplicationFilter(status));
    }
  });

  if (token) {
    boot();
  } else {
    showLogin();
    const adminBtn = el("adminNavBtn");
    if (adminBtn) {
      adminBtn.classList.add("hidden");
    }
  }
});
