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
const resultValue = document.getElementById("roll-result-value");
const magicCircle = document.getElementById("magicCircle");

const apiKeyInput = document.getElementById("id_dddice_api_key");
const roomIdInput = document.getElementById("id_dddice_room_id");
const roomPasswordInput = document.getElementById("id_dddice_room_password");
const themeSelect = document.getElementById("id_dddice_theme");
const refreshThemesButton = document.getElementById("dddice_refresh_sets");

const hasRollUI = Boolean(
    canvas &&
    roll1d10Button &&
    roll2d10Button &&
    resultDiv &&
    resultValue &&
    magicCircle
);
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

var html = "";
var stroke = 'white';
var size = 512;
var halfsize = size / 2;
var defaultStyle = { fill: 'none', stroke: stroke, 'stroke-width': '3' };
var defaultText = { fill: stroke, 'text-anchor': 'middle', 'font-family': 'Segoe UI Symbol' };
var defaultTextCircle = { fill: stroke, 'font-family': 'Segoe UI Symbol' };
var symbolSets = [
    "♈♉♊♋♌♍♎♏♐♑♒♓",
    "☉☽☾☿♀♁♂♃♄♅♆♇",
    Array.from({ length: 0x1F773 - 0x1F700 + 1 }, (_, i) => String.fromCodePoint(0x1F700 + i)),
];
var alphabets = [
    'ᚡᚢᚣᚤᚥᚦᚧᚨᚩᚪᚫᚬᚭᚮᚯᚰᚱᚲᚳᚴᚵᚶᚷᚸᚹᚺᚻᚼᚽᚾᚿᛀᛁᛂᛃᛄᛅᛆᛇᛈᛉᛊᛋᛌᛍᛎᛏᛐᛑᛒᛓᛔᛕᛖᛗᛘᛙᛚᛛᛜᛝᛞᛟᛠᛡᛢᛣᛤᛥᛦᛧᛨᛩᛪ',
    'ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΤΥΦΧΨ',
    'غظضذخثتشرقصفعسنملكيطحزوهدجبأ',
    'אבגדהוזחטיכךלמנסעפצקרשתםןףץ',
    'ⲀⲂⲄⲆⲈⲊⲌⲎⲐⲒⲔⲖⲘⲚⲜⲞⲠⲢⲤⲦⲨⲪⲬⲮⲰ',
    'ЀЁЂЃЄЅІЇЈЉЊЋЌЍЎЏАБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ',
];

function startAnimate(speed) {
    if (speed == 0) {
        return;
    }
    if (speed == undefined) {
        speed = randRangeReal(-0.05, 0.05);
    }
    html += '<g>';
    let sign;
    let period;
    let center = halfsize + ' ' + halfsize;
    if (speed < 0) {
        sign = '-';
        period = -1 / speed;
    } else {
        sign = '';
        period = 1 / speed;
    }
    html += '<animateTransform attributeName="transform" type="rotate" from="0 ' + center + '" to="' + sign + '360 ' + center + '" dur="' + period + 's" repeatCount="indefinite"/>';
}

function endAnimate() {
    html += '</g>';
}

function nextAnimate(speed) {
    endAnimate();
    startAnimate(speed);
}

function toPaddedHexString(num) {
    let str = num.toString(16);
    return ('0' + str).substr(-2);
}

function randomizeColor() {
    stroke = '#8e7bff';
    defaultStyle.stroke = stroke;
    defaultText.fill = stroke;
    defaultTextCircle.fill = stroke;
}

function styleToXML(styleDict, original) {
    if (original == undefined) {
        original = defaultStyle;
    }
    if (styleDict == undefined) {
        styleDict = original;
    } else {
        for (const key in original) {
            if (styleDict[key] === undefined) {
                styleDict[key] = original[key];
            }
        }
    }
    let text = 'style="';
    for (const key in styleDict) {
        text += key + ':' + styleDict[key] + '; ';
    }
    text += '"';
    return text;
}

function fromPolar(r, angle) {
    if (r == undefined) {
        return { x: halfsize, y: halfsize };
    }
    angle *= 2 * Math.PI;
    let x = size * (1 + r * Math.sin(angle)) / 2;
    let y = size * (1 - r * Math.cos(angle)) / 2;
    return { x: x, y: y };
}

function strFromPolar(r, angle) {
    let v = fromPolar(r, angle);
    return v.x + ',' + v.y + ' ';
}

function nRelativelyPrimeGram(n, m, r, offset) {
    html += '<polygon points="';
    let side = 0;
    for (let i = 0; i < n; ++i) {
        html += strFromPolar(r, side / n + offset);
        side += m;
    }
    html += '" ' + styleToXML() + '/>';
}

function gcf(a, b) {
    if (a == 0) {
        return b;
    }
    return gcf(b % a, a);
}

function nGram(n, m, r, offset) {
    if (offset == undefined) {
        offset = 0;
    } else if (offset == true) {
        offset = 1 / (2 * n);
    }
    let f = gcf(m, n);
    let nn = n / f;
    let mm = m / f;
    for (let i = 0; i < f; ++i) {
        nRelativelyPrimeGram(nn, mm, r, i / n + offset);
    }
    return r * Math.cos(Math.PI * m / n);
}

function nGramSolid(n, m, r, offset) {
    if (offset == undefined) {
        offset = 0;
    } else if (offset == true) {
        offset = 1 / (2 * n);
    }
    let rr = r * Math.sin(Math.PI * (1 / 2 - m / n)) / Math.sin(Math.PI * (1 / 2 + (m - 1) / n));
    html += '<polygon points="';
    let side = 0;
    for (let i = 0; i < n; ++i) {
        html += strFromPolar(r, side / n + offset);
        html += strFromPolar(rr, (side + 0.5) / n + offset);
        ++side;
    }
    html += '" ' + styleToXML({ fill: 'black' }) + '/>';
    return rr;
}

function text(r, angle, symbol, sizePx) {
    let c = fromPolar(r, angle);
    let symbolSize = getSizeOfText(symbol, 'Segoe UI Symbol', sizePx + 'px');
    let delta = (symbolSize.actualBoundingBoxAscent - symbolSize.actualBoundingBoxDescent) / 2;
    let textValue = '<text x="' + c.x + '" y="' + (c.y + delta) + '" ' + styleToXML({ 'font-size': sizePx + 'px' }, defaultText) + '>' + symbol + '</text>';
    html += textValue;
}

function textCircle(r, textValue, marginpx) {
    r -= marginpx / halfsize;
    let originalSize = getSizeOfText(textValue, 'Segoe UI Symbol', '1024px');
    let textSize = size * Math.PI * r / (originalSize.width / 1024);
    let factor = 1 - textSize * originalSize.actualBoundingBoxAscent / (1024 * r * halfsize);
    r *= factor;
    textSize *= factor;
    let finalR = r - textSize * originalSize.actualBoundingBoxDescent / (1024 * halfsize) - marginpx / halfsize;

    html += '<path id="textCircle" stroke="none" fill="none" d="';
    let v = fromPolar(r, 0);
    html += 'M ' + v.x + ' ' + v.y + ' ';
    v = fromPolar(r, 1 / 4);
    html += 'A ' + (r * halfsize) + ' ' + (r * halfsize) + ' 0 0 1 ' + v.x + ' ' + v.y + ' ';
    v = fromPolar(r, 0);
    html += 'A ' + (r * halfsize) + ' ' + (r * halfsize) + ' 0 1 1 ' + v.x + ' ' + v.y + ' ';
    html += 'Z"/>';

    html += '<text ' + styleToXML({ 'font-size': textSize + 'px' }, defaultTextCircle) + '><textPath href="#textCircle">' + textValue + '</textPath></text>';
    return finalR;
}

function nRelativelyPrimeGramCircle(n, m, r, phi, offset) {
    let psi = 1 / 4 - m / (2 * n) - phi / 720;
    let rc = halfsize * r * Math.sin(Math.PI * m / n) / Math.sin(psi * 2 * Math.PI);
    let rfull = halfsize * r * Math.cos(phi * Math.PI / 360) / Math.sin(psi * 2 * Math.PI);
    let newR = (rfull - rc) / halfsize;
    html += '<path ' + styleToXML() + ' d="';
    let v = fromPolar(r, offset);
    html += 'M ' + v.x + ' ' + v.y + ' ';
    let side = 0;
    for (let i = 0; i < n; ++i) {
        side = (side + m) % n;
        v = fromPolar(r, side / n + offset);
        html += 'A ' + rc + ' ' + rc + ' 0 0 0 ' + v.x + ' ' + v.y + ' ';
    }
    html += 'Z"/>';
    return newR;
}

function nGramCircle(n, m, r, phi, offset) {
    if (offset == undefined) {
        offset = 0;
    } else if (offset == true) {
        offset = 1 / (2 * n);
    }
    let f = gcf(m, n);
    let nn = n / f;
    let mm = m / f;
    let newR = 0;
    for (let i = 0; i < f; ++i) {
        newR = nRelativelyPrimeGramCircle(nn, mm, r, phi, i / n + offset);
    }
    return newR;
}

function choice(set) {
    return set[Math.floor(Math.random() * set.length)];
}

function toArray(collection) {
    if (typeof collection == 'string') {
        return collection.split('');
    }
    return [...collection];
}

function choiceRemove(set) {
    let i = Math.floor(Math.random() * set.length);
    let chosen = set[i];
    if (i == set.length - 1) {
        set.pop();
    } else {
        set[i] = set.pop();
    }
    return chosen;
}

function circleOfCircles(n, r, circleR, offset) {
    if (offset == undefined) {
        offset = 0;
    } else if (offset == true) {
        offset = 1 / (2 * n);
    }
    let symbolSet = toArray(choice(symbolSets));
    while (symbolSet.length < n) {
        symbolSet = toArray(choice(symbolSets));
    }
    for (let i = 0; i < n; ++i) {
        let angle = i / n + offset;
        circle(circleR, r, angle, { fill: 'black' });
        text(r, angle, choiceRemove(symbolSet), circleR * halfsize);
    }
}

function circleOfCircles2(n, r, circleR, offset) {
    if (offset == undefined) {
        offset = 0;
    } else if (offset == true) {
        offset = 1 / (2 * n);
    }
    let symbolSet = toArray(choice(symbolSets));
    while (symbolSet.length < n) {
        symbolSet = toArray(choice(symbolSets));
    }
    for (let i = 0; i < n; ++i) {
        let angle = i / n + offset;
        html += '<g transform = "rotate(' + (360 * angle) + ' ' + halfsize + ' ' + halfsize + ')">';
        circle(circleR, r, 0, { fill: 'black' });
        text(r, 0, choiceRemove(symbolSet), circleR * halfsize);
        html += '</g>';
    }
}

function getSizeOfText(txt, fontname, fontsize) {
    if (getSizeOfText.c === undefined) {
        getSizeOfText.c = document.createElement('canvas');
        getSizeOfText.ctx = getSizeOfText.c.getContext('2d');
    }
    var fontspec = fontsize + ' ' + fontname;
    if (getSizeOfText.ctx.font !== fontspec) {
        getSizeOfText.ctx.font = fontspec;
    }
    return getSizeOfText.ctx.measureText(txt);
}

function circle(r, R, angle, style) {
    let c = fromPolar(R, angle);
    html += '<circle cx="' + c.x + '" cy="' + c.y + '" r="' + (r * halfsize) + '" ' + styleToXML(style) + '/>';
}

function randomText(n, alphabet) {
    if (alphabet == undefined) {
        alphabet = choice(alphabets);
    }
    let textValue = '';
    for (let i = 0; i < n; ++i) {
        textValue += choice(alphabet);
    }
    return textValue;
}

function randRangeReal(a, b) {
    return Math.random() * (b - a) + a;
}

function randRange(a, b) {
    return Math.floor(randRangeReal(a, b));
}

function randBool() {
    return Math.random() < 0.5;
}

function starburst(r) {
    if (Math.random() < 0.15) {
        return r;
    }
    if (randBool()) {
        if (randBool()) {
            return nGram(randRange(12, 25), 3, r, randBool());
        }
        return nGram(randRange(15, 30), 4, r, randBool());
    }
    switch (randRange(1, 4)) {
        case 1:
            return nGramCircle(randRange(12, 40), 1, r, randRange(45, 90), randBool());
        case 2:
            return nGramCircle(randRange(12, 40), 2, r, randRange(45, 90), randBool());
        case 3:
            return nGramCircle(randRange(40, 60), 3, r, randRange(45, 90), randBool());
        default:
            return r;
    }
}

function textRing(r) {
    circle(r);
    r = textCircle(r, randomText(randRange(50, 150)), 6);
    circle(r);
    return r;
}

function nGramWithCircles(n, m, r, circleR, offset) {
    if (offset == undefined || offset == false) {
        offset = 0;
    } else if (offset == true) {
        offset = 1 / (2 * n);
    }
    r -= circleR;
    let newR = nGram(n, m, r, offset);
    circleOfCircles2(n, r, circleR, offset);
    return newR;
}

function nGramCircleWithCircles(n, m, r, phi, circleR, offset) {
    if (offset == undefined) {
        offset = 0;
    } else if (offset == true) {
        offset = 1 / (2 * n);
    }
    let newR = nGramCircle(n, m, r, phi, !offset);
    r -= circleR;
    circleOfCircles2(n, r, circleR, offset);
    return newR;
}

function nGramSolidWithCircles(n, m, r, circleR, offset) {
    r -= circleR;
    let newR = nGramSolid(n, m, r, offset);
    circleOfCircles2(n, r, circleR, offset);
    return newR;
}

function innerStar(r) {
    let n;
    let m;
    let circleR;
    switch (randRange(0, 3)) {
        case 0:
            n = randRange(5, 14);
            m = Math.ceil(n / 3);
            circleR = r * 0.61881 * n ** -0.563139;
            return nGramWithCircles(n, m, r, circleR, randBool());
        case 1:
            n = randRange(3, 10);
            let minM = 1;
            if (n > 4) {
                minM = 2;
            }
            m = randRange(minM, Math.ceil(n / 2));
            circleR = 0.9 * r * Math.sqrt(m) / n;
            return nGramCircleWithCircles(n, m, r, 0, circleR, randBool());
        case 2:
            n = randRange(5, 10);
            m = n * 0.4;
            circleR = r * 0.61881 * n ** -0.563139;
            let offset = randBool();
            let oldR = r;
            r = nGramSolidWithCircles(n, m, r, circleR, offset);
            let fraction = 0.85;
            r = fraction * r + (1 - fraction) * oldR;
            return nGramSolid(n, m, r, !offset);
        default:
            return r;
    }
}

function newCircle() {
    if (!magicCircle) {
        return;
    }

    html = '';
    randomizeColor();
    let r = 0.9;
    startAnimate();
    r = starburst(r);
    r *= 0.95;
    nextAnimate();
    r = textRing(r);
    r *= 0.9;
    nextAnimate();
    innerStar(r);
    endAnimate();
    magicCircle.innerHTML = html;
    const textArea = document.getElementById('textArea');
    if (textArea) {
        textArea.innerHTML = '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" style="background-color:black" viewBox="0 0 512 512">' + html + '</svg>';
    }
}

document.addEventListener('DOMContentLoaded', () => newCircle());

function hideRollResult() {
    if (!resultDiv) {
        return;
    }

    resultDiv.classList.remove("show");
}

function showRollResult(total) {
    if (!resultDiv || !resultValue) {
        return;
    }

    if (resultTimeoutId) {
        clearTimeout(resultTimeoutId);
        resultTimeoutId = null;
    }

    newCircle();
    resultValue.textContent = `${total}`;
    resultDiv.classList.remove("show");
    void resultDiv.offsetWidth;
    resultDiv.classList.add("show");

    resultTimeoutId = window.setTimeout(() => {
        hideRollResult();
        resultTimeoutId = null;
    }, 8000);
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

    if (hasRollUI && hasRollConfig) {
        try {
            await initDice();
        } catch (error) {
            console.error("DDDdice konnte beim Seitenstart nicht initialisiert werden.", error);
        }
    }

    await autoLoadDiceThemes();
});

