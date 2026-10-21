import QtQuick 2.15
import QtQuick.Layouts 1.15
import Qt.labs.settings 1.1
import org.kde.plasma.plasmoid 2.0
import org.kde.plasma.core 2.0 as PlasmaCore
import org.kde.kirigami 2.20 as Kirigami
import "Model.js" as Model
import "../code/SpendBackend.js" as SpendBackend

Item {
    id: root

    property var spend: Model.emptySpend()
    property bool fetchBusy: false
    property bool ready: false
    property string lastError: ""
    property real updatedNow: Date.now()

    readonly property string configuredKey: String(Plasmoid.configuration.openrouterKey || "").trim()
    readonly property bool hasKey: configuredKey.indexOf("sk-or-") === 0
    readonly property int refreshMinutes: {
        var n = parseInt(Plasmoid.configuration.refreshMinutes, 10)
        return isFinite(n) && n >= 1 ? Math.min(n, 120) : 5
    }
    readonly property string pillText: Model.pillLabel(spend.monthTotal, spend.last24h, spend.lastHour)
    readonly property int popupWidth: {
        var configured = parseInt(Plasmoid.configuration.popupWidth, 10)
        if (isFinite(configured) && configured > 0)
            return configured
        return Kirigami.Units.gridUnit * 20
    }
    readonly property int popupHeight: {
        var configured = parseInt(Plasmoid.configuration.popupHeight, 10)
        if (isFinite(configured) && configured > 0)
            return configured
        return Kirigami.Units.gridUnit * 48
    }

    readonly property url panelIcon: Qt.resolvedUrl("../icons/openrouter-spend.svg")

    // --- Plasma 5 / KF5 wiring -------------------------------------------------
    // On Plasma 6 these were root properties of a PlasmoidItem. In Plasma 5 the
    // applet root is a plain Item and everything hangs off the attached Plasmoid
    // object (same idiom as org.kde.plasma.systemmonitor).
    Plasmoid.preferredRepresentation: Plasmoid.formFactor === PlasmaCore.Types.Planar ? Plasmoid.fullRepresentation : null

    Plasmoid.icon: "openrouter-spend"
    Plasmoid.title: "OpenRouter Spend"

    Plasmoid.toolTipMainText: lastError !== "" ? lastError : pillText
    Plasmoid.toolTipSubText: hasKey ? (Model.monthLabel(spend.month) || "OpenRouter") : "Management key not set — right-click to configure"

    Plasmoid.compactRepresentation: CompactRepresentation {
        plasmoidItem: root
    }

    Plasmoid.fullRepresentation: FullRepresentation {
        spend: root.spend
        updatedNow: root.updatedNow
        fetchBusy: root.fetchBusy
        hasKey: root.hasKey
        lastError: root.lastError
        popupWidth: root.popupWidth
        popupHeight: root.popupHeight
        onConfigureRequested: root.openConfig()
    }

    // --- cache -------------------------------------------------------------
    // QtQuick.LocalStorage is an optional, separately-packaged module on most
    // KF5 distros (qml-module-qtquick-localstorage). Qt.labs.settings ships with
    // qtdeclarative and is always present, so the cache lives there instead.
    Settings {
        id: cache
        category: "OpenRouterSpend"
        property string cachedJson: ""
    }

    function loadCachedSpend() {
        var json = cache.cachedJson
        if (!json)
            return
        var parsed = Model.parseSpend(json)
        if (parsed)
            applySpend(parsed)
    }

    function saveCachedSpend(json) {
        cache.cachedJson = json
    }

    function setError(message) {
        lastError = String(message || "").trim()
    }

    function clearError() {
        lastError = ""
    }

    function applySpend(parsed) {
        if (!parsed)
            return
        Qt.callLater(function() {
            root.spend = parsed
        })
    }

    function refresh() {
        var key = String(Plasmoid.configuration.openrouterKey || "").trim()
        if (key.indexOf("sk-or-") !== 0) {
            loadCachedSpend()
            return
        }
        if (fetchBusy)
            return
        fetchBusy = true
        SpendBackend.fetchSpend(key, function(err, json) {
            Qt.callLater(function() {
                root.fetchBusy = false
                if (err) {
                    root.setError(String(err))
                    root.loadCachedSpend()
                    return
                }
                root.clearError()
                root.saveCachedSpend(json)
                var parsed = Model.parseSpend(json)
                if (parsed)
                    root.applySpend(parsed)
            })
        })
    }

    function readNow() {
        loadCachedSpend()
    }

    function openConfig() {
        // Plasma 5 has no internalAction(); the applet's own configure action is
        // reached through Plasmoid.action() (as paneltoolbox does).
        var action = Plasmoid.action("configure")
        if (action)
            action.trigger()
    }

    Component.onCompleted: startupTimer.start()

    Timer {
        id: startupTimer
        interval: 250
        repeat: false
        onTriggered: {
            root.ready = true
            root.loadCachedSpend()
            root.refresh()
        }
    }

    Timer {
        id: configRefreshDebounce
        interval: 300
        repeat: false
        onTriggered: root.refresh()
    }

    onConfiguredKeyChanged: {
        if (ready)
            configRefreshDebounce.restart()
    }

    Connections {
        target: plasmoid
        ignoreUnknownSignals: true
        function onConfigurationChanged() {
            if (root.ready)
                configRefreshDebounce.restart()
        }
        function onExpandedChanged() {
            if (root.ready && plasmoid.expanded) {
                root.loadCachedSpend()
                root.refresh()
            }
        }
    }

    Timer {
        interval: root.refreshMinutes * 60 * 1000
        repeat: true
        running: true
        onTriggered: root.refresh()
    }

    Timer {
        interval: 1000
        repeat: true
        running: true
        onTriggered: root.updatedNow = Date.now()
    }
}
