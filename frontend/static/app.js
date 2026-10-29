/* ============================================================
   EcoTwin-AI Dashboard
   Digital Twin + Live Telemetry
   ============================================================ */

const FACILITY_ID = 1;

let telemetryTimer = null;
let twinTimer = null;

const $ = (id) => document.getElementById(id);

function setText(id, value, fallback = "--") {
    const el = $(id);
    if (!el) return;

    if (value === null || value === undefined || value === "") {
        el.textContent = fallback;
    } else {
        el.textContent = value;
    }
}

function numberValue(value, digits = 2) {
    if (value === null || value === undefined || value === "") {
        return "--";
    }

    const n = Number(value);

    if (!Number.isFinite(n)) {
        return "--";
    }

    return n.toFixed(digits);
}

function getTelemetry(twin) {
    /*
       IMPORTANT:
       The backend returns the reliable solar telemetry here:

       digital_twin.snapshot.telemetry
    */

    const snapshot =
        twin?.digital_twin?.snapshot || {};

    const telemetry =
        snapshot.telemetry ||
        twin?.digital_twin?.telemetry ||
        {};

    return {
        ambient_temperature:
            telemetry.ambient_temperature ??
            telemetry.temperature ??
            null,

        module_temperature:
            telemetry.module_temperature ??
            null,

        voltage:
            telemetry.voltage ??
            null,

        current:
            telemetry.current ??
            null,

        power:
            telemetry.power ??
            null,

        irradiance:
            telemetry.irradiance ??
            telemetry.light_intensity ??
            null,

        vibration:
            telemetry.vibration ??
            null
    };
}


/* ============================================================
   TELEMETRY
   ============================================================ */

async function loadTelemetry() {
    try {
        const response = await fetch(
            `/api/telemetry/latest?facility_id=${FACILITY_ID}`,
            {
                cache: "no-store"
            }
        );

        if (!response.ok) {
            throw new Error(
                `Telemetry HTTP ${response.status}`
            );
        }

        const data = await response.json();

        if (!data.success) {
            throw new Error(
                data.error || "Telemetry unavailable"
            );
        }

        const t = data.telemetry || {};

        updateTelemetryCards({
            ambient_temperature:
                t.ambient_temperature?.value ??
                t.ambient_temperature,

            module_temperature:
                t.module_temperature?.value ??
                t.module_temperature,

            voltage:
                t.voltage?.value ??
                t.voltage,

            current:
                t.current?.value ??
                t.current,

            power:
                t.power?.value ??
                t.power,

            irradiance:
                t.irradiance?.value ??
                t.irradiance,

            vibration:
                t.vibration?.value ??
                t.vibration
        });

        setLastUpdate(
            t.ambient_temperature?.timestamp ||
            new Date().toISOString()
        );

    } catch (error) {
        console.error(
            "Telemetry loading failed:",
            error
        );
    }
}


/* ============================================================
   DIGITAL TWIN
   ============================================================ */

async function loadDigitalTwin() {
    try {
        const response = await fetch(
            `/api/digital-twin?facility_id=${FACILITY_ID}`,
            {
                cache: "no-store"
            }
        );

        if (!response.ok) {
            throw new Error(
                `Digital Twin HTTP ${response.status}`
            );
        }

        const data = await response.json();

        if (!data.success) {
            throw new Error(
                data.error || "Digital Twin unavailable"
            );
        }

        const twin = data.digital_twin;

        if (!twin) {
            throw new Error(
                "Digital Twin data missing"
            );
        }

        updateTwin(twin);

    } catch (error) {
        console.error(
            "Digital Twin loading failed:",
            error
        );
    }
}


/* ============================================================
   UPDATE TELEMETRY CARDS
   ============================================================ */

function updateTelemetryCards(t) {

    /*
       These IDs support the most common dashboard naming
       conventions. Multiple aliases are updated so the
       existing dashboard does not need to be rewritten.
    */

    updateIds(
        [
            "ambient-temperature",
            "ambientTemperature",
            "ambient-temp",
            "ambient_temperature"
        ],
        `${numberValue(t.ambient_temperature, 1)} °C`
    );

    updateIds(
        [
            "module-temperature",
            "moduleTemperature",
            "module-temp",
            "module_temperature"
        ],
        `${numberValue(t.module_temperature, 1)} °C`
    );

    updateIds(
        [
            "voltage",
            "voltage-value"
        ],
        `${numberValue(t.voltage, 2)} V`
    );

    updateIds(
        [
            "current",
            "current-value"
        ],
        `${numberValue(t.current, 2)} A`
    );

    updateIds(
        [
            "power",
            "power-value"
        ],
        `${numberValue(t.power, 2)} W`
    );

    updateIds(
        [
            "irradiance",
            "irradiance-value",
            "light-intensity"
        ],
        `${numberValue(t.irradiance, 0)} W/m²`
    );

    updateIds(
        [
            "vibration",
            "vibration-value"
        ],
        `${numberValue(t.vibration, 2)} mm/s`
    );
}


function updateIds(ids, value) {
    ids.forEach(id => {
        const el = $(id);

        if (el) {
            el.textContent = value;
        }
    });
}


/* ============================================================
   DIGITAL TWIN STATE
   ============================================================ */

function updateTwin(twin) {

    const telemetry = getTelemetry({
        digital_twin: twin
    });

    updateTelemetryCards(telemetry);

    /* --------------------------------------------------------
       Health
       -------------------------------------------------------- */

    const health =
        twin.health || {};

    const score =
        health.score ??
        health.health_score ??
        null;

    const status =
        health.status ||
        "Unknown";

    const failureProbability =
        health.failure_probability ??
        0;

    const rul =
        health.rul ??
        null;

    updateIds(
        [
            "health-status",
            "healthStatus",
            "twin-health-status"
        ],
        status
    );

    updateIds(
        [
            "health-score",
            "healthScore",
            "twin-health-score"
        ],
        `${numberValue(score, 1)}%`
    );

    updateIds(
        [
            "failure-probability",
            "failureProbability"
        ],
        `${numberValue(failureProbability, 2)}%`
    );

    updateIds(
        [
            "rul",
            "remaining-useful-life"
        ],
        rul === null
            ? "--"
            : `${numberValue(rul, 0)} h`
    );


    /* --------------------------------------------------------
       Risk
       -------------------------------------------------------- */

    const risk =
        twin.risk || {};

    updateIds(
        [
            "risk-level",
            "riskLevel",
            "twin-risk"
        ],
        risk.level || "--"
    );


    /* --------------------------------------------------------
       Maintenance
       -------------------------------------------------------- */

    updateIds(
        [
            "maintenance-recommendation",
            "maintenanceRecommendation",
            "recommendation"
        ],
        twin.maintenance_recommendation ||
        "No recommendation available"
    );


    /* --------------------------------------------------------
       Device
       -------------------------------------------------------- */

    updateIds(
        [
            "device-id",
            "deviceId"
        ],
        twin.device_id || "--"
    );


    /* --------------------------------------------------------
       Facility
       -------------------------------------------------------- */

    const snapshot =
        twin.snapshot || {};

    const facility =
        snapshot.facility || {};

    updateIds(
        [
            "facility-name",
            "facilityName",
            "asset-name"
        ],
        snapshot.asset_name ||
        facility.name ||
        "EcoTwin-AI Solar Energy Facility"
    );


    /* --------------------------------------------------------
       Synchronization
       -------------------------------------------------------- */

    updateIds(
        [
            "sync-status",
            "synchronization-status"
        ],
        "Synchronized"
    );

    updateIds(
        [
            "sync-time",
            "synchronized-at"
        ],
        formatDate(
            twin.synchronized_at
        )
    );


    /* --------------------------------------------------------
       Alerts
       -------------------------------------------------------- */

    updateAlerts(
        twin.active_alerts || []
    );


    /* --------------------------------------------------------
       Virtual Asset
       -------------------------------------------------------- */

    updateVirtualAsset(
        status,
        risk.level
    );
}


/* ============================================================
   VIRTUAL SOLAR ASSET
   ============================================================ */

function updateVirtualAsset(
    healthStatus,
    riskLevel
) {

    const asset =
        document.querySelector(
            ".virtual-asset"
        );

    if (!asset) return;

    asset.dataset.health =
        String(healthStatus || "")
            .toLowerCase();

    asset.dataset.risk =
        String(riskLevel || "")
            .toLowerCase();

    /*
       Add an active state if the dashboard has
       a visual virtual asset.
    */

    asset.classList.add("asset-online");
}


/* ============================================================
   ALERTS
   ============================================================ */

function updateAlerts(alerts) {

    const containers = [
        $("alerts-list"),
        $("alertsList"),
        $("active-alerts"),
        $("alert-container")
    ].filter(Boolean);

    if (!containers.length) {
        return;
    }

    containers.forEach(container => {

        container.innerHTML = "";

        if (!alerts.length) {

            container.innerHTML = `
                <div class="empty-state">
                    <span>✓</span>
                    <div>
                        <strong>No active alerts</strong>
                        <small>System operating normally</small>
                    </div>
                </div>
            `;

            return;
        }

        alerts.forEach(alert => {

            const item =
                document.createElement("div");

            item.className =
                "alert-item";

            const severity =
                alert.severity ||
                "Warning";

            item.innerHTML = `
                <div class="alert-severity">
                    ${escapeHtml(severity)}
                </div>

                <div class="alert-content">
                    <strong>
                        ${escapeHtml(
                            alert.alert_type ||
                            "System Alert"
                        )}
                    </strong>

                    <p>
                        ${escapeHtml(
                            alert.message ||
                            "Alert generated."
                        )}
                    </p>

                    <small>
                        ${formatDate(
                            alert.created_at
                        )}
                    </small>
                </div>
            `;

            container.appendChild(item);
        });
    });
}


/* ============================================================
   LAST UPDATE
   ============================================================ */

function setLastUpdate(timestamp) {

    updateIds(
        [
            "last-update",
            "lastUpdate",
            "telemetry-last-update"
        ],
        `Updated ${formatDate(timestamp)}`
    );
}


/* ============================================================
   DATE FORMAT
   ============================================================ */

function formatDate(value) {

    if (!value) {
        return "--";
    }

    const date =
        new Date(value);

    if (Number.isNaN(
        date.getTime()
    )) {
        return value;
    }

    return date.toLocaleString();
}


/* ============================================================
   SAFE HTML
   ============================================================ */

function escapeHtml(value) {

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


/* ============================================================
   SYNCHRONIZE DIGITAL TWIN
   ============================================================ */

async function synchronizeTwin() {

    try {

        const response =
            await fetch(
                "/api/digital-twin/synchronize",
                {
                    method: "POST",
                    headers: {
                        "Content-Type":
                            "application/json"
                    },
                    body: JSON.stringify({
                        facility_id:
                            FACILITY_ID
                    })
                }
            );

        const data =
            await response.json();

        if (!response.ok ||
            !data.success) {

            console.error(
                "Twin synchronization failed:",
                data
            );

            return;
        }

        console.log(
            "Digital Twin synchronized:",
            data
        );

        await loadDigitalTwin();

    } catch (error) {

        console.error(
            "Twin synchronization error:",
            error
        );
    }
}


/* ============================================================
   BUTTONS
   ============================================================ */

function setupButtons() {

    document
        .querySelectorAll(
            "[data-action]"
        )
        .forEach(button => {

            button.addEventListener(
                "click",
                async function () {

                    const action =
                        this.dataset.action;

                    switch (action) {

                        case "refresh":
                            await refreshDashboard();
                            break;

                        case "synchronize":
                            await synchronizeTwin();
                            break;

                        case "telemetry":
                            await loadTelemetry();
                            break;

                        case "digital-twin":
                            await loadDigitalTwin();
                            break;

                        default:
                            console.log(
                                "Dashboard action:",
                                action
                            );
                    }
                }
            );
        });
}


/* ============================================================
   REFRESH EVERYTHING
   ============================================================ */

async function refreshDashboard() {

    await loadTelemetry();
    await loadDigitalTwin();

}


/* ============================================================
   INITIALIZATION
   ============================================================ */

async function initializeDashboard() {

    console.log(
        "EcoTwin-AI Dashboard starting..."
    );

    setupButtons();

    await refreshDashboard();

    /*
       Refresh live telemetry every 5 seconds.
    */

    if (telemetryTimer) {
        clearInterval(telemetryTimer);
    }

    telemetryTimer =
        setInterval(
            loadTelemetry,
            5000
        );


    /*
       Refresh Digital Twin every 10 seconds.
    */

    if (twinTimer) {
        clearInterval(twinTimer);
    }

    twinTimer =
        setInterval(
            loadDigitalTwin,
            10000
        );

    console.log(
        "EcoTwin-AI Dashboard ready."
    );
}


/* ============================================================
   START
   ============================================================ */

if (
    document.readyState ===
    "loading"
) {

    document.addEventListener(
        "DOMContentLoaded",
        initializeDashboard
    );

} else {

    initializeDashboard();

}