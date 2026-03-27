import { ThreeDDice, ThreeDDiceAPI } from "/static/js/vendor/dddice-latest.web.mjs";

/* ---------------------------------------------------
   CONFIG
--------------------------------------------------- */

const configElement = document.getElementById("dddice-config");

let dddiceConfig = {};
try {
    dddiceConfig = configElement ? JSON.parse(configElement.textContent) : {};
} catch (error) {
    console.error("dddice-config JSON konnte nicht gelesen werden:", error);
    dddiceConfig = {};
}

const API_KEY = dddiceConfig?.apiKey ?? "";
const ROOM_SLUG = dddiceConfig?.roomId ?? "";
const ROOM_PASSCODE = dddiceConfig?.roomPassword ?? "";
const SAVED_THEME_ID = dddiceConfig?.themeId ?? "";

/* ---------------------------------------------------
   DOM
--------------------------------------------------- */

const canvas = document.getElementById("dddice");
const roll1d100Button = document.getElementById("roll-1d100");
const roll1d10Button = document.getElementById("roll-1d10");
const roll2d10Button = document.getElementById("roll-2d10");
const resultDiv = document.getElementById("roll-result");

const apiKeyInput = document.getElementById("id_dddice_api_key");
const roomIdInput = document.getElementById("id_dddice_room_id");
const roomPasswordInput = document.getElementById("id_dddice_room_password");
const themeSelect = document.getElementById("id_dddice_theme");
const refreshThemesButton = document.getElementById("dddice_refresh_sets");

const hasRollUI = Boolean(canvas && roll1d10Button && roll2d10Button && resultDiv);
const hasRollConfig = Boolean(API_KEY && ROOM_SLUG);

/* ---------------------------------------------------
   STATE
--------------------------------------------------- */

let dddice = null;
let connected = false;
let connecting = null;

let settingsApi = null;
let settingsApiSignature = "";

let resultTimeoutId = null;
let diceBoxThemesCache = [];
const loadedThemeIds = new Set();

/* ---------------------------------------------------
   HELPERS
--------------------------------------------------- */

function sleep(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function getCsrfToken() {
    const name = "csrftoken=";
    const cookies = document.cookie.split(";");

    for (const cookie of cookies) {
        const trimmed = cookie.trim();
        if (trimmed.startsWith(name)) {
            return trimmed.substring(name.length);
        }
    }

    return "";
}

function getThemeSelectCurrentValue() {
    if (!themeSelect) {
        return "";
    }

    return themeSelect.value || themeSelect.dataset.currentValue || "";
}

function setThemeSelectCurrentValue(value) {
    if (!themeSelect) {
        return;
    }

    const safeValue = value || "";
    themeSelect.dataset.currentValue = safeValue;
    themeSelect.value = safeValue;
}

function getSettingsCredentials() {
    return {
        apiKey: apiKeyInput?.value?.trim() || "",
        roomId: roomIdInput?.value?.trim() || "",
        roomPassword: roomPasswordInput?.value?.trim() || "",
    };
}

function dieMatchesType(availableDie, dieType) {
    if (!availableDie) {
        return false;
    }

    if (typeof availableDie === "string") {
        return availableDie === dieType;
    }

    return availableDie.id === dieType || availableDie.notation === dieType;
}

function themeSupportsDie(theme, dieType) {
    if (!theme || !Array.isArray(theme.available_dice)) {
        return false;
    }

    return theme.available_dice.some((availableDie) => dieMatchesType(availableDie, dieType));
}

function getThemeById(themeId) {
    if (!themeId) {
        return null;
    }

    return diceBoxThemesCache.find((theme) => theme?.id === themeId) || null;
}

function pickThemeForDie(themes, dieType) {
    const matchingTheme = themes.find((theme) => themeSupportsDie(theme, dieType));

    if (!matchingTheme?.id) {
        throw new Error(`Kein Würfelset gefunden, das ${dieType} unterstützt.`);
    }

    return matchingTheme.id;
}

function pickThemeForPercentile(themes) {
    const matchingTheme = themes.find(
        (theme) => themeSupportsDie(theme, "d10x") && themeSupportsDie(theme, "d10")
    );

    if (!matchingTheme?.id) {
        throw new Error("Kein Würfelset gefunden, das d10x und d10 unterstützt.");
    }

    return matchingTheme.id;
}

/* ---------------------------------------------------
   ROLL ENGINE
--------------------------------------------------- */

async function initDice() {
    if (!hasRollUI) {
        return false;
    }

    if (!hasRollConfig) {
        console.warn("DDDdice Roll-Konfiguration unvollständig.");
        return false;
    }

    if (connected && dddice) {
        return true;
    }

    if (connecting) {
        return connecting;
    }

    connecting = (async () => {
        if (!dddice) {
            dddice = new ThreeDDice(canvas, API_KEY);
        }

        await dddice.start();

        if (ROOM_PASSCODE) {
            await dddice.connect(ROOM_SLUG, ROOM_PASSCODE);
        } else {
            await dddice.connect(ROOM_SLUG);
        }

        connected = true;
        console.log("DDDICE CONNECT OK");
        return true;
    })();

    try {
        return await connecting;
    } finally {
        connecting = null;
    }
}

async function ensureRollThemeLoaded(themeId) {
    if (!themeId || !dddice || loadedThemeIds.has(themeId)) {
        return;
    }

    try {
        dddice.loadThemeResources(themeId);
        loadedThemeIds.add(themeId);
    } catch (error) {
        console.warn(`Theme-Ressourcen für ${themeId} konnten nicht vorgeladen werden.`, error);
    }
}

/* ---------------------------------------------------
   SETTINGS API / THEME LOADING
--------------------------------------------------- */

async function getSettingsApi() {
    const { apiKey, roomId, roomPassword } = getSettingsCredentials();

    if (!apiKey) {
        throw new Error("DDDdice API Key fehlt.");
    }

    if (!roomId) {
        throw new Error("DDDdice Room ID fehlt.");
    }

    const signature = `${apiKey}::${roomId}::${roomPassword}`;

    if (settingsApi && settingsApiSignature === signature) {
        return settingsApi;
    }

    settingsApi = new ThreeDDiceAPI(apiKey);
    settingsApiSignature = signature;

    if (roomPassword) {
        await settingsApi.connect(roomId, roomPassword);
    } else {
        await settingsApi.connect(roomId);
    }

    return settingsApi;
}

async function fetchDiceBoxThemes() {
    const api = await getSettingsApi();
    const response = await api.diceBox.list();
    const themes = Array.isArray(response?.data) ? response.data : [];

    diceBoxThemesCache = themes;
    return themes;
}

function fillThemeSelect(themes) {
    if (!themeSelect) {
        return;
    }

    const currentValue = getThemeSelectCurrentValue() || SAVED_THEME_ID || "";

    themeSelect.innerHTML = "";

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = "– Würfelset wählen –";
    themeSelect.appendChild(placeholder);

    for (const theme of themes) {
        if (!theme?.id) {
            continue;
        }

        const option = document.createElement("option");
        option.value = theme.id;
        option.textContent = theme.name || theme.id;

        if (theme.id === currentValue) {
            option.selected = true;
        }

        themeSelect.appendChild(option);
    }

    if (currentValue && getThemeById(currentValue)) {
        setThemeSelectCurrentValue(currentValue);
    } else {
        setThemeSelectCurrentValue("");
    }
}

async function refreshDiceThemes(event) {
    if (event) {
        event.preventDefault();
        event.stopPropagation();
    }

    if (!refreshThemesButton) {
        return;
    }

    const originalText = refreshThemesButton.textContent;
    refreshThemesButton.disabled = true;
    refreshThemesButton.textContent = "…";

    try {
        const themes = await fetchDiceBoxThemes();
        fillThemeSelect(themes);

        if (!themes.length) {
            alert("Keine Würfelsets in deiner DDDdice Dice Box gefunden.");
        }
    } catch (error) {
        console.error("DDDdice themes konnten nicht geladen werden:", error);
        alert(error?.message || "Würfelsets konnten nicht geladen werden.");
    } finally {
        refreshThemesButton.disabled = false;
        refreshThemesButton.textContent = originalText;
    }
}

async function autoLoadDiceThemes() {
    if (!themeSelect) {
        return;
    }

    const hasSettingsInputs = Boolean(apiKeyInput && roomIdInput);

    if (!hasSettingsInputs) {
        return;
    }

    const { apiKey, roomId } = getSettingsCredentials();

    if (!apiKey || !roomId) {
        return;
    }

    try {
        const themes = await fetchDiceBoxThemes();
        fillThemeSelect(themes);
    } catch (error) {
        console.warn("DDDdice Themes konnten nicht automatisch geladen werden.", error);
    }
}

/* ---------------------------------------------------
   THEME PICKING FOR ROLLS
--------------------------------------------------- */

function getPreferredThemeIdForDie(dieType) {
    const selectedThemeId = getThemeSelectCurrentValue() || SAVED_THEME_ID;
    const selectedTheme = getThemeById(selectedThemeId);

    if (selectedTheme) {
        if (!Array.isArray(selectedTheme.available_dice) || selectedTheme.available_dice.length === 0) {
            return selectedTheme.id;
        }

        if (themeSupportsDie(selectedTheme, dieType)) {
            return selectedTheme.id;
        }
    }

    if (selectedThemeId && !selectedTheme) {
        return selectedThemeId;
    }

    if (!diceBoxThemesCache.length) {
        throw new Error("Keine geladenen Würfelsets vorhanden.");
    }

    return pickThemeForDie(diceBoxThemesCache, dieType);
}

function getPreferredThemeIdForPercentile() {
    const selectedThemeId = getThemeSelectCurrentValue() || SAVED_THEME_ID;
    const selectedTheme = getThemeById(selectedThemeId);

    if (selectedTheme) {
        if (!Array.isArray(selectedTheme.available_dice) || selectedTheme.available_dice.length === 0) {
            return selectedTheme.id;
        }

        if (
            themeSupportsDie(selectedTheme, "d10x") &&
            themeSupportsDie(selectedTheme, "d10")
        ) {
            return selectedTheme.id;
        }
    }

    if (selectedThemeId && !selectedTheme) {
        return selectedThemeId;
    }

    if (!diceBoxThemesCache.length) {
        throw new Error("Keine geladenen Würfelsets vorhanden.");
    }

    return pickThemeForPercentile(diceBoxThemesCache);
}

async function ensureThemesAvailableForRolling() {
    if (diceBoxThemesCache.length) {
        return;
    }

    if (themeSelect && apiKeyInput && roomIdInput) {
        try {
            const themes = await fetchDiceBoxThemes();
            fillThemeSelect(themes);
            if (diceBoxThemesCache.length) {
                return;
            }
        } catch (error) {
            console.warn("Dice Box Themes konnten im Settings-Kontext nicht geladen werden.", error);
        }
    }

    if (SAVED_THEME_ID) {
        diceBoxThemesCache = [
            {
                id: SAVED_THEME_ID,
                name: SAVED_THEME_ID,
                available_dice: [],
            },
        ];
    }
}

/* ---------------------------------------------------
   BACKEND ROLL + DDDICE RENDER
--------------------------------------------------- */

async function fetchBackendRoll(sides = 10, count = 2) {
    const response = await fetch("/api/roll/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCsrfToken(),
            Accept: "application/json",
        },
        body: JSON.stringify({
            sides,
            count,
        }),
    });

    const rawText = await response.text();
    let data;

    try {
        data = JSON.parse(rawText);
    } catch {
        throw new Error(`Backend lieferte kein JSON. Status ${response.status}: ${rawText.slice(0, 200)}`);
    }

    console.log("BACKEND ROLL RESPONSE", data);

    if (!response.ok) {
        throw new Error(data?.error || "Backend-Wurf fehlgeschlagen.");
    }

    if (typeof data.total !== "number") {
        throw new Error("Backend hat kein gültiges Gesamtergebnis geliefert.");
    }

    if (sides !== 100) {
        if (!Array.isArray(data.rolls) || data.rolls.length !== count) {
            throw new Error("Backend hat keine gültigen Würfelwerte geliefert.");
        }
    }

    return data;
}

function buildPercentileDicePayload(total, themeId) {
    if (typeof total !== "number" || total < 1 || total > 100) {
        throw new Error(`Ungültiger d100-Wert: ${total}`);
    }

    let tensValue;
    let onesValue;

    if (total === 100) {
        tensValue = 9;
        onesValue = 10;
    } else {
        tensValue = Math.floor(total / 10);
        onesValue = total % 10;

        if (onesValue === 0) {
            onesValue = 10;
            tensValue -= 1;
        }
    }

    return [
        {
            type: "d10x",
            theme: themeId,
            value: tensValue,
        },
        {
            type: "d10",
            theme: themeId,
            value: onesValue,
        },
    ];
}

async function renderBackendRoll(sides = 10, count = 2) {
    const ready = await initDice();
    if (!ready) {
        throw new Error("DDDdice konnte nicht initialisiert werden.");
    }

    await ensureThemesAvailableForRolling();

    const backendRoll = await fetchBackendRoll(sides, count);

    let dicePayload;
    let themeId;

    if (backendRoll.sides === 100) {
        themeId = getPreferredThemeIdForPercentile();
        dicePayload = buildPercentileDicePayload(backendRoll.total, themeId);
    } else {
        const dieType = `d${sides}`;
        themeId = getPreferredThemeIdForDie(dieType);

        dicePayload = backendRoll.rolls.map((value) => ({
            type: dieType,
            theme: themeId,
            value,
        }));
    }

    await ensureRollThemeLoaded(themeId);

    const response = await fetch("https://dddice.com/api/1.0/roll", {
        method: "POST",
        headers: {
            Authorization: `Bearer ${API_KEY}`,
            "Content-Type": "application/json",
            Accept: "application/json",
        },
        body: JSON.stringify({
            dice: dicePayload,
            room: ROOM_SLUG,
            label: `${count}d${sides}: ${backendRoll.total}`,
        }),
    });

    const data = await response.json();
    console.log("DDDICE ROLL RESPONSE", data);

    if (!response.ok || data?.type === "error") {
        throw new Error(data?.data?.message || data?.message || "DDDice roll failed");
    }

    return {
        backendRoll,
        dddiceRoll: data,
    };
}

/* ---------------------------------------------------
   RESULT UI
--------------------------------------------------- */

function hideRollResult() {
    if (!resultDiv) {
        return;
    }

    resultDiv.classList.remove("show");
}

function showRollResult(total) {
    if (!resultDiv) {
        return;
    }

    if (resultTimeoutId) {
        clearTimeout(resultTimeoutId);
        resultTimeoutId = null;
    }

    resultDiv.textContent = `${total}`;
    resultDiv.classList.remove("show");
    void resultDiv.offsetWidth;
    resultDiv.classList.add("show");

    resultTimeoutId = window.setTimeout(() => {
        hideRollResult();
        resultTimeoutId = null;
    }, 5000);
}

/* ---------------------------------------------------
   PUBLIC ACTION
--------------------------------------------------- */

async function performRoll(sides = 10, count = 2) {
    try {
        hideRollResult();

        const result = await renderBackendRoll(sides, count);

        await sleep(2200);
        showRollResult(result.backendRoll.total);
    } catch (error) {
        console.error("FINAL ROLL FAILED", error);
    }
}

/* ---------------------------------------------------
   BINDINGS
--------------------------------------------------- */

function bindRollButtons() {
    if (roll1d100Button) {
        roll1d100Button.addEventListener("click", (event) => {
            event.preventDefault();
            performRoll(100, 1);
        });
    }

    if (roll1d10Button) {
        roll1d10Button.addEventListener("click", (event) => {
            event.preventDefault();
            performRoll(10, 1);
        });
    }

    if (roll2d10Button) {
        roll2d10Button.addEventListener("click", (event) => {
            event.preventDefault();
            performRoll(10, 2);
        });
    }
}

function bindSettingsControls() {
    if (refreshThemesButton) {
        refreshThemesButton.addEventListener("click", refreshDiceThemes);
    }

    if (themeSelect) {
        themeSelect.addEventListener("change", () => {
            setThemeSelectCurrentValue(themeSelect.value);
        });
    }
}

function bindKeyboardShortcuts() {
    document.addEventListener("keydown", (event) => {
        if (event.repeat) {
            return;
        }

        if (!event.ctrlKey) {
            return;
        }

        switch (event.key) {
            case "F9":
                event.preventDefault();
                performRoll(100, 1);
                break;

            case "F11":
                event.preventDefault();
                performRoll(10, 1);
                break;

            case "F12":
                event.preventDefault();
                performRoll(10, 2);
                break;

            default:
                break;
        }
    });
}

/* ---------------------------------------------------
   BOOT
--------------------------------------------------- */

document.addEventListener("DOMContentLoaded", async () => {
    console.log("dddice.js loaded");

    if (themeSelect && SAVED_THEME_ID && !themeSelect.value) {
        setThemeSelectCurrentValue(SAVED_THEME_ID);
    }

    bindSettingsControls();
    bindRollButtons();
    bindKeyboardShortcuts();

    await autoLoadDiceThemes();
});

