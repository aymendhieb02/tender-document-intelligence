const navItems = [
  ["/", "Accueil", "TI"],
  ["/invoice", "Factures", "IN"],
  ["/cdc", "Cahier des Charges", "CD"],
  ["/cdc/male", "Ministère des Affaires Locales", "ML"],
];

export function mountShell(content, activePath) {
  const root = document.getElementById("app-shell");
  root.innerHTML = `<header class="topbar"><button class="mobile-menu" type="button" aria-label="Ouvrir la navigation" aria-expanded="false"><span></span><span></span><span></span></button><a class="brand" href="/"><span class="brand-mark">TI</span><span>Tender Intelligence<small>DOCUMENT WORKSPACE</small></span></a><div class="topbar-right"><span class="api-indicator"><i></i><span id="apiStatus">API locale</span></span><span class="topbar-label">ENVIRONNEMENT LOCAL</span></div></header><div class="app-frame"><aside class="sidebar"><div class="sidebar-label">DOCUMENTS</div><nav aria-label="Accueil"><a class="side-link ${activePath === "/" ? "active" : ""}" href="/"><span class="side-icon">TI</span><span>Accueil</span></a></nav><div class="sidebar-label sidebar-label-spaced">ANALYSES</div><nav aria-label="Analyses">${navItems.slice(1).map(([href, label, icon]) => `<a class="side-link ${activePath === href || activePath.startsWith(`${href}/`) ? "active" : ""}" href="${href}"><span class="side-icon">${icon}</span><span>${label}</span></a>`).join("")}</nav><div class="sidebar-label sidebar-label-spaced">PLATEFORME</div><a class="side-link" href="/#recent"><span class="side-icon">HI</span><span>Historique</span></a><div class="sidebar-bottom"><div class="sidebar-status"><span class="status-dot"></span><span>Traitement local</span></div><small>Version de travail</small></div></aside><main class="main-content" id="mainContent"></main></div><div class="sidebar-scrim"></div>`;
  const target = root.querySelector("#mainContent");
  if (content instanceof Node) target.append(content);
  root.querySelector(".mobile-menu").addEventListener("click", () => {
    const open = root.classList.toggle("sidebar-open");
    root.querySelector(".mobile-menu").setAttribute("aria-expanded", String(open));
  });
  root.querySelector(".sidebar-scrim").addEventListener("click", () => root.classList.remove("sidebar-open"));
  checkHealth(root);
  return target;
}

async function checkHealth(root) {
  try {
    const response = await fetch("/health");
    const body = await response.json();
    if (body.status === "ok") root.querySelector("#apiStatus").textContent = "API connectée";
  } catch { root.querySelector("#apiStatus").textContent = "API indisponible"; }
}
