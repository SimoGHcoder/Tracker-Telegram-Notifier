let currentConfig = {};
let activeProfileId = "1";
let connectPollInterval = null;
let availableAddons = [];

document.addEventListener("DOMContentLoaded", () => {
    loadProfiles();
    loadDashboard();
    // Fetch and display application version
    fetch('/api/version')
        .then(response => response.json())
        .then(data => {
            document.getElementById('app-version').textContent = data.version;
        })
        .catch(error => {
            console.error('Error fetching version:', error);
        });
});

async function loadProfiles() {
    try {
        const configRes = await fetch("/api/config");
        const configData = await configRes.json();

        const hasEmail = configData.nuvio?.email && configData.nuvio.email.trim() !== "";
        const hasPassword = configData.nuvio?.password_configured;

        const select = document.getElementById("header-profile-select");
        if (!select) return;

        if (!hasEmail || !hasPassword) {
            setNuvioStatus(false, "Non configurato (Credenziali mancanti)");
            select.innerHTML = '<option value="">Nessun profilo disponibile</option>';
            select.disabled = true;
            return;
        }

        select.disabled = false;
        const res = await fetch("/api/profiles");
        const profiles = await res.json();
        select.innerHTML = "";

        if (profiles && profiles.length > 0) {
            profiles.forEach(p => {
                const opt = document.createElement("option");
                opt.value = p.id;
                opt.textContent = p.name;
                select.appendChild(opt);
            });
            setNuvioStatus(true, "Connesso");
        } else {
            select.innerHTML = '<option value="">Nessun profilo trovato</option>';
            setNuvioStatus(false, "Non connesso");
        }

        if (configData.nuvio?.profile_id) {
            select.value = configData.nuvio.profile_id;
            activeProfileId = String(configData.nuvio.profile_id);
        }
    } catch (e) {
        console.error("Errore caricamento profili:", e);
        setNuvioStatus(false, "Errore di connessione");
    }
}

function setNuvioStatus(isConnected, message) {
    const dot = document.getElementById("nuvio-status-dot");
    const text = document.getElementById("nuvio-status-text");
    if (!dot || !text) return;

    dot.className = "w-2.5 h-2.5 rounded-full " + (isConnected ? "bg-emerald-500 animate-pulse" : "bg-red-500");
    text.textContent = message;
}

function createTableCell(className, text) {
    const cell = document.createElement("td");
    cell.className = className;
    cell.textContent = text;
    return cell;
}

function createNotificationCheckbox(item) {
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = Boolean(item.notifications_enabled);
    checkbox.className = "w-4 h-4 accent-indigo-600 rounded cursor-pointer";
    checkbox.addEventListener("change", () => toggleNotification(item.content_id, checkbox.checked));
    return checkbox;
}

function toggleSavedPasswordRemoval(removePassword) {
    const passwordInput = document.getElementById("s-nuvio-password");
    if (!passwordInput) return;
    passwordInput.disabled = removePassword;
    if (removePassword) passwordInput.value = "";
}

async function loadDashboard() {
    try {
        const res = await fetch("/api/dashboard");
        const data = await res.json();

        if (document.getElementById("dash-active-shows")) {
            document.getElementById("dash-active-shows").textContent = `${data.active_notifications} / ${data.total_notification_items}`;
        }
        if (document.getElementById("dash-telegram-user")) {
            document.getElementById("dash-telegram-user").textContent = data.telegram_status;
        }
        if (document.getElementById("dash-interval")) {
            document.getElementById("dash-interval").textContent = `${data.check_interval_hours}h`;
        }
        if (document.getElementById("dash-lang")) {
            document.getElementById("dash-lang").textContent = data.dubbing_language;
        }

        const tbody = document.getElementById("dash-recent-table");
        if (tbody) {
            if (!data.recent_releases || data.recent_releases.length === 0) {
                tbody.innerHTML = '<tr><td colspan="3" class="py-6 text-center text-slate-500">Nessuna serie attiva trovata.</td></tr>';
                return;
            }

            tbody.replaceChildren();
            data.recent_releases.forEach(item => {
                const row = document.createElement("tr");
                row.className = "hover:bg-slate-900/40";
                row.appendChild(createTableCell("py-3 px-4 font-semibold text-white", item.title));
                row.appendChild(createTableCell(
                    "py-3 px-4 text-center text-slate-400",
                    `S${item.season || 1} E${item.episode || 0}`
                ));

                const statusCell = document.createElement("td");
                statusCell.className = "py-3 px-4 text-center";
                const status = document.createElement("span");
                status.className = item.notifications_enabled
                    ? "text-xs px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                    : "text-xs px-2.5 py-1 rounded-full bg-slate-800 text-slate-400";
                status.textContent = item.notifications_enabled ? "Attiva" : "Disattivata";
                statusCell.appendChild(status);
                row.appendChild(statusCell);
                tbody.appendChild(row);
            });
        }
    } catch (e) {
        console.error("Errore caricamento dashboard:", e);
    }
}

async function loadConfig() {
    if (connectPollInterval) {
        clearInterval(connectPollInterval);
        connectPollInterval = null;
    }

    try {
        const res = await fetch("/api/config");
        currentConfig = await res.json();

        const tokenStatus = document.getElementById("telegram-token-status");
        const removeTokenContainer = document.getElementById("remove-telegram-token-container");
        const removeTokenCheckbox = document.getElementById("s-remove-telegram-token");
        if (removeTokenContainer) {
            const tokenConfigured = Boolean(currentConfig.telegram?.bot_token_configured);
            removeTokenContainer.classList.toggle("hidden", !tokenConfigured);
            removeTokenContainer.classList.toggle("flex", tokenConfigured);
            if (removeTokenCheckbox) removeTokenCheckbox.checked = false;
            if (tokenStatus) {
                tokenStatus.textContent = tokenConfigured
                    ? "Token configurato. Inseriscine uno nuovo per sostituirlo."
                    : "Nessun token configurato.";
            }
        }

        const email = currentConfig.nuvio?.email || "";
        const passwordInput = document.getElementById("s-nuvio-password");

        if (document.getElementById("s-nuvio-email")) document.getElementById("s-nuvio-email").value = email;
        if (passwordInput) {
            passwordInput.value = "";
            passwordInput.disabled = false;
            passwordInput.placeholder = currentConfig.nuvio?.password_configured
                ? "Lascia vuoto per mantenere la password salvata"
                : "Inserisci la password Nuvio";
        }
        const clearPasswordCheckbox = document.getElementById("s-clear-nuvio-password");
        if (clearPasswordCheckbox) clearPasswordCheckbox.checked = false;
        const clearPasswordContainer = document.getElementById("clear-nuvio-password-container");
        if (clearPasswordContainer) {
            clearPasswordContainer.classList.toggle("hidden", !currentConfig.nuvio?.password_configured);
            clearPasswordContainer.classList.toggle("flex", Boolean(currentConfig.nuvio?.password_configured));
        }
        if (document.getElementById("s-check-interval")) document.getElementById("s-check-interval").value = currentConfig.check_interval_hours || 4;
        if (document.getElementById("s-dub-lang")) document.getElementById("s-dub-lang").value = currentConfig.dubbing_language || "ita";

        activeProfileId = String(currentConfig.nuvio?.profile_id || 1);

        const select = document.getElementById("header-profile-select");
        if (select && select.value !== activeProfileId) {
            select.value = activeProfileId;
        }

        if (!email.trim() || !currentConfig.nuvio?.password_configured) {
            setNuvioStatus(false, "Non configurato (Credenziali mancanti)");
        }

        const inheritPrefs = currentConfig.inherit_main_telegram || {};
        const isProfile1 = (activeProfileId === "1");

        const inheritContainer = document.getElementById("inherit-option-container");
        const inheritCheckbox = document.getElementById("s-inherit-main-tg");
        const dedicateBox = document.getElementById("telegram-dedicate-box");

        if (isProfile1) {
            if (inheritContainer) inheritContainer.style.display = "none";
            if (dedicateBox) dedicateBox.style.display = "flex";
        } else {
            if (inheritContainer) inheritContainer.style.display = "flex";
            const useInherit = inheritPrefs[activeProfileId] !== undefined ? inheritPrefs[activeProfileId] : true;
            if (inheritCheckbox) inheritCheckbox.checked = useInherit;

            if (dedicateBox) {
                dedicateBox.style.display = useInherit ? "none" : "flex";
            }
        }

        const profilesTelegram = currentConfig.profiles_telegram || {};
        const telegramUsernames = currentConfig.telegram_usernames || {};
        let displayChatId = "Non collegato";

        if (isProfile1) {
            const nameU = telegramUsernames["1"];
            const chatIdU = profilesTelegram["1"] || currentConfig.telegram?.chat_id;
            displayChatId = nameU ? `${nameU}` : (chatIdU || "Non collegato");
        } else {
            const useInherit = inheritPrefs[activeProfileId] !== undefined ? inheritPrefs[activeProfileId] : true;
            if (useInherit) {
                const mainName = telegramUsernames["1"] || profilesTelegram["1"] || "Profilo Principale";
                displayChatId = `${mainName} (Ereditato dal Profilo Principale)`;
            } else {
                const dedicatedName = telegramUsernames[activeProfileId];
                const dedicatedId = profilesTelegram[activeProfileId];
                displayChatId = dedicatedName ? `${dedicatedName}` : (dedicatedId || "Non collegato (Usa QR dedicato)");
            }
        }

        const chatIdDisplay = document.getElementById("s-chat-id-display");
        if (chatIdDisplay) chatIdDisplay.textContent = displayChatId;

        const profileBadge = document.getElementById("settings-profile-badge");
        if (profileBadge) {
            const name = select && select.selectedOptions[0] ? select.selectedOptions[0].textContent : `Profilo ${activeProfileId}`;
            profileBadge.textContent = name;
        }

        if (isProfile1 || (inheritPrefs[activeProfileId] === false)) {
            initTelegramQRCode();
        }

        await loadAvailableAddons();

    } catch (e) {
        console.error("Errore caricamento config:", e);
        setNuvioStatus(false, "Errore di caricamento");
    }
}

async function loadAvailableAddons() {
    const container = document.getElementById("addon-list");
    if (!container) return;

    container.replaceChildren();
    const loading = document.createElement("p");
    loading.className = "text-xs text-slate-500";
    loading.textContent = "Caricamento addon...";
    container.appendChild(loading);

    try {
        const res = await fetch("/api/addons");
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Impossibile recuperare gli addon Nuvio.");
        }

        availableAddons = data.addons || [];
        const selectedAddons = new Set(data.selected_addons || []);
        container.replaceChildren();

        if (availableAddons.length === 0) {
            const empty = document.createElement("p");
            empty.className = "text-xs text-slate-500";
            empty.textContent = "Nessun addon attivo trovato per il profilo Nuvio selezionato.";
            container.appendChild(empty);
            return;
        }

        availableAddons.forEach(addon => {
            const label = document.createElement("label");
            label.className = "flex items-center gap-3 bg-slate-950/60 border border-slate-800 rounded-xl px-3 py-2 cursor-pointer hover:border-indigo-500/50";

            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            checkbox.className = "w-4 h-4 accent-indigo-600 rounded cursor-pointer";
            checkbox.value = addon.url;
            checkbox.checked = selectedAddons.has(addon.url);

            const details = document.createElement("span");
            details.className = "min-w-0";
            const name = document.createElement("span");
            name.className = "block text-xs font-medium text-slate-200";
            name.textContent = addon.name;
            const host = document.createElement("span");
            host.className = "block text-[11px] text-slate-500 truncate";
            try {
                host.textContent = new URL(addon.url).hostname;
            } catch {
                host.textContent = addon.url;
            }

            details.append(name, host);
            label.append(checkbox, details);
            container.appendChild(label);
        });
    } catch (e) {
        console.error("Errore caricamento addon Nuvio:", e);
        container.replaceChildren();
        const error = document.createElement("p");
        error.className = "text-xs text-red-400";
        error.textContent = e.message || "Errore nel caricamento degli addon Nuvio.";
        container.appendChild(error);
    }
}

async function toggleInheritTelegram(inherit) {
    const payload = { inherit_main_telegram: inherit };
    try {
        await fetch("/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        loadConfig();
    } catch (e) {
        console.error("Errore salvataggio preferenza Telegram:", e);
    }
}

async function resetTelegramProfile() {
    const confirmed = confirm(`⚠️ Vuoi scollegare e resettare Telegram per il profilo attivo?`);
    if (!confirmed) return;

    try {
        const res = await fetch("/api/telegram/reset-profile", { method: "POST" });
        if (res.ok) {
            alert("✅ Collegamento Telegram resettato per questo profilo.");
            loadConfig();
        } else {
            alert("❌ Errore durante il reset Telegram del profilo.");
        }
    } catch (e) {
        alert("❌ Errore di connessione con il server.");
    }
}

async function changeActiveProfile(profileId) {
    if (!profileId) return;
    activeProfileId = String(profileId);

    try {
        await fetch("/api/select-profile", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ profile_id: parseInt(profileId) })
        });

        const select = document.getElementById("header-profile-select");
        if (select) select.value = activeProfileId;

        await loadConfig();

        const dashTab = document.getElementById("tab-content-dashboard");
        const historyTab = document.getElementById("tab-content-history");
        const libraryTab = document.getElementById("tab-content-library");

        if (dashTab && !dashTab.classList.contains("hidden")) {
            loadDashboard();
        } else if (historyTab && !historyTab.classList.contains("hidden")) {
            loadHistory();
        } else if (libraryTab && !libraryTab.classList.contains("hidden")) {
            loadLibrary();
        }

    } catch (e) {
        console.error("Errore durante il cambio profilo:", e);
        alert("❌ Errore durante il cambio del profilo attivo.");
    }
}

async function loadHistory() {
    const tbody = document.getElementById("history-table-body");
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="3" class="py-8 text-center text-slate-500">Caricamento in corso...</td></tr>';
    try {
        const res = await fetch("/api/history");
        const items = await res.json();
        if (!items || items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="py-8 text-center text-slate-500">Nessuna serie trovata nella cronologia per questo profilo.</td></tr>';
            return;
        }

        tbody.replaceChildren();
        items.forEach(item => {
            const row = document.createElement("tr");
            row.className = "hover:bg-slate-900/40";
            row.appendChild(createTableCell("py-3 px-4 font-semibold text-white", item.title));
            row.appendChild(createTableCell(
                "py-3 px-4 text-center text-slate-400",
                `S${item.season || 1} E${item.episode || 0}`
            ));
            const checkboxCell = document.createElement("td");
            checkboxCell.className = "py-3 px-4 text-center";
            checkboxCell.appendChild(createNotificationCheckbox(item));
            row.appendChild(checkboxCell);
            tbody.appendChild(row);
        });
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="3" class="py-8 text-center text-red-400">Errore nel caricamento della cronologia.</td></tr>';
    }
}

async function loadLibrary() {
    const tbody = document.getElementById("library-table-body");
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="3" class="py-8 text-center text-slate-500">Caricamento in corso...</td></tr>';
    try {
        const res = await fetch("/api/library");
        const items = await res.json();
        if (!items || items.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="py-8 text-center text-slate-500">Nessun elemento trovato nella libreria.</td></tr>';
            return;
        }
        tbody.replaceChildren();
        items.forEach(item => {
            const row = document.createElement("tr");
            row.className = "hover:bg-slate-900/40";
            row.appendChild(createTableCell("py-3 px-4 font-semibold text-white", item.title));
            row.appendChild(createTableCell("py-3 px-4 text-slate-400 uppercase text-xs", item.type));
            const checkboxCell = document.createElement("td");
            checkboxCell.className = "py-3 px-4 text-center";
            checkboxCell.appendChild(createNotificationCheckbox(item));
            row.appendChild(checkboxCell);
            tbody.appendChild(row);
        });
    } catch (e) {
        tbody.innerHTML = '<tr><td colspan="3" class="py-8 text-center text-red-400">Errore nel caricamento della libreria.</td></tr>';
    }
}

async function toggleNotification(contentId, enabled) {
    try {
        const res = await fetch("/api/toggle-notification", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content_id: contentId, enabled })
        });
        if (res.ok) await loadDashboard();
    } catch (e) {
        console.error("Errore aggiornamento preferenza notifiche:", e);
    }
}

async function toggleAllNotifications(scope, enabled) {
    try {
        const res = await fetch("/api/toggle-all-notifications", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ scope, enabled })
        });
        if (!res.ok) throw new Error("Impossibile aggiornare le notifiche.");

        if (scope === "history") await loadHistory();
        if (scope === "library") await loadLibrary();
        await loadDashboard();
    } catch (e) {
        console.error("Errore aggiornamento notifiche della scheda:", e);
        alert(e.message || "Errore durante l'aggiornamento delle notifiche.");
    }
}

async function saveSettings() {
    const nuvio = {
        email: document.getElementById("s-nuvio-email").value,
    };
    const password = document.getElementById("s-nuvio-password").value;
    const removePassword = document.getElementById("s-clear-nuvio-password").checked;
    if (removePassword) nuvio.password = "";
    else if (password) nuvio.password = password;

    const payload = {
        nuvio,
        check_interval_hours: parseInt(document.getElementById("s-check-interval").value),
        dubbing_language: document.getElementById("s-dub-lang").value,
        selected_addons: Array.from(document.querySelectorAll("#addon-list input[type='checkbox']:checked"))
            .map(input => input.value),
    };

    try {
        const res = await fetch("/api/config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            alert("✅ Impostazioni salvate con successo!");
            loadConfig();
            loadProfiles();
            loadDashboard();
        } else {
            alert("❌ Errore durante il salvataggio.");
        }
    } catch (e) {
        alert("❌ Errore di connessione con il server.");
    }
}

async function confirmResetApp() {
    const confirmed = confirm("⚠️ SEI SICURO?\n\nIl reset cancellerà credenziali Nuvio, profili, collegamenti Telegram e cronologia. La scelta sul token del bot ti verrà chiesta dopo.");
    if (!confirmed) return;

    const removeTelegramToken = confirm("Vuoi cancellare anche il token del bot Telegram?\n\nOK = rimuovi il token.\nAnnulla = mantieni il token salvato.");

    try {
        const res = await fetch("/api/reset", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ remove_telegram_token: removeTelegramToken })
        });
        if (res.ok) {
            alert(`✅ Ripristino completato. Token Telegram ${removeTelegramToken ? "rimosso" : "mantenuto"}. L'applicazione verrà ricaricata.`);
            window.location.reload();
        } else {
            alert("❌ Errore durante il ripristino dell'applicazione.");
        }
    } catch (e) {
        alert("❌ Errore di connessione con il server.");
    }
}

async function initTelegramQRCode() {
    try {
        const isProfile1 = (activeProfileId === "1");
        const inheritPrefs = currentConfig.inherit_main_telegram || {};
        const useInherit = inheritPrefs[activeProfileId] !== undefined ? inheritPrefs[activeProfileId] : true;

        const profilesTelegram = currentConfig.profiles_telegram || {};
        const hasDedicatedChat = !!profilesTelegram[activeProfileId];
        const hasMainChat = !!profilesTelegram["1"] || !!currentConfig.telegram?.chat_id;

        const isConnected = isProfile1 ? hasDedicatedChat : (!useInherit ? hasDedicatedChat : hasMainChat);

        const qrContainer = document.getElementById("telegram-qrcode");
        const statusMsg = document.getElementById("telegram-status-msg");
        const dedicateBox = document.getElementById("telegram-dedicate-box");

        if (!isProfile1 && useInherit) {
            if (connectPollInterval) {
                clearInterval(connectPollInterval);
                connectPollInterval = null;
            }
            if (dedicateBox) dedicateBox.style.display = "flex";
            if (qrContainer) {
                qrContainer.innerHTML = '<div class="text-[11px] text-slate-400 text-center px-2">Eredita la chat dal Principale</div>';
            }
            if (statusMsg) {
                statusMsg.innerHTML = '<span class="text-indigo-400 font-medium">ℹ️ Questo profilo sta usando le impostazioni del Profilo Principale. Disattiva "Usa Telegram Principale" per configurare un QR dedicato.</span>';
            }
            return;
        }

        if (isConnected) {
            if (connectPollInterval) {
                clearInterval(connectPollInterval);
                connectPollInterval = null;
            }
            if (dedicateBox) dedicateBox.style.display = "flex";
            if (qrContainer) {
                qrContainer.innerHTML = '<div class="w-32 h-32 flex flex-col items-center justify-center text-emerald-600 bg-emerald-50 rounded-lg"><i class="fa-solid fa-circle-check text-3xl mb-1"></i><span class="text-[10px] font-bold uppercase">Collegato</span></div>';
            }
            if (statusMsg) {
                statusMsg.innerHTML = '<span class="text-emerald-400 font-semibold">✅ Chat Telegram collegata e attiva per questo profilo.</span>';
            }
            return;
        }

        if (dedicateBox) dedicateBox.style.display = "flex";

        const res = await fetch("/api/telegram/start-connect", { method: "POST" });
        if (!res.ok) return;
        const data = await res.json();
        const deepLink = data.deep_link;

        if (!qrContainer) return;
        qrContainer.innerHTML = "";

        if (typeof QRCode !== "undefined") {
            new QRCode(qrContainer, {
                text: deepLink,
                width: 128,
                height: 128,
                colorDark: "#0f172a",
                colorLight: "#ffffff",
                correctLevel: QRCode.CorrectLevel.M
            });
        }

        if (statusMsg) {
            statusMsg.innerHTML = 'Inquadra il QR code con la fotocamera o clicca sul link per associare Telegram.';
        }

        if (connectPollInterval) clearInterval(connectPollInterval);
        connectPollInterval = setInterval(async () => {
            const checkRes = await fetch(`/api/telegram/check-link/${data.code}`);
            const checkData = await checkRes.json();
            if (checkData.status === "success") {
                clearInterval(connectPollInterval);
                connectPollInterval = null;
                if (statusMsg) {
                    statusMsg.innerHTML = '<span class="text-emerald-400 font-semibold">✅ Chat collegata con successo!</span>';
                }
                loadConfig();
            }
        }, 2000);

    } catch (e) {
        console.error("Errore QR Telegram:", e);
    }
}

async function sendTestNotification() {
    try {
        const res = await fetch("/api/telegram/test-notification", { method: "POST" });
        const data = await res.json();
        alert(data.message);
    } catch (e) {
        alert("❌ Errore durante l'invio della notifica di test.");
    }
}

async function saveTelegramToken() {
    const tokenInput = document.getElementById("s-telegram-bot-token");
    const removeTokenCheckbox = document.getElementById("s-remove-telegram-token");
    const status = document.getElementById("telegram-token-status");
    const removeToken = Boolean(removeTokenCheckbox?.checked);
    const botToken = removeToken ? "" : (tokenInput?.value || "").trim();

    if (!removeToken && !botToken) {
        if (status) status.textContent = "Inserisci un nuovo token o seleziona la rimozione.";
        return;
    }

    if (status) status.textContent = "Verifica del token in corso...";
    try {
        const res = await fetch("/api/telegram/token", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bot_token: botToken })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || "Impossibile salvare il token Telegram.");

        if (tokenInput) tokenInput.value = "";
        if (removeTokenCheckbox) removeTokenCheckbox.checked = false;
        if (status) {
            status.textContent = data.configured
                ? `Token verificato e salvato${data.bot_username ? ` (@${data.bot_username})` : ""}.`
                : "Token Telegram rimosso.";
        }
        await loadProfiles();
        await loadConfig();
    } catch (error) {
        if (status) status.textContent = error.message || "Errore durante il salvataggio del token.";
    }
}

async function triggerManualCheck() {
    try {
        const res = await fetch("/api/check-now", { method: "POST" });
        const data = await res.json();
        alert(`✅ Controllo completato! ${data.found ? data.found.length : 0} nuove uscite trovate.`);
        loadHistory();
        loadDashboard();
    } catch (e) {
        alert("❌ Errore durante il controllo manuale.");
    }
}

function switchTab(tab) {
    ['dashboard', 'history', 'library', 'settings'].forEach(t => {
        const content = document.getElementById(`tab-content-${t}`);
        const btn = document.getElementById(`tab-btn-${t}`);
        if (content) content.classList.add('hidden');
        if (btn) btn.className = "w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-medium transition text-slate-400 hover:bg-slate-800/50 hover:text-slate-200 cursor-pointer";
    });

    const activeContent = document.getElementById(`tab-content-${tab}`);
    const activeBtn = document.getElementById(`tab-btn-${tab}`);
    if (activeContent) activeContent.classList.remove('hidden');
    if (activeBtn) activeBtn.className = "w-full flex items-center space-x-3 px-4 py-3 rounded-xl text-sm font-medium transition bg-indigo-600/20 text-indigo-300 border border-indigo-500/30 cursor-pointer";

    if (tab === 'dashboard') loadDashboard();
    if (tab === 'history') loadHistory();
    if (tab === 'library') loadLibrary();
    if (tab === 'settings') loadConfig();
}