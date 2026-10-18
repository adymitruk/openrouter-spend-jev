import QtQuick
import QtQuick.LocalStorage as SQL
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import "Model.js" as Model
import "../code/SpendBackend.js" as SpendBackend

PlasmoidItem {
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

    preferredRepresentation: Plasmoid.formFactor === PlasmaCore.Types.Planar ? fullRepresentation : null

    readonly property url panelIcon: Qt.resolvedUrl("../icons/openrouter-spend.svg")

    Plasmoid.icon: panelIcon
    Plasmoid.title: "OpenRouter Spend"
    badgeText: ""

    toolTipMainText: lastError !== "" ? lastError : pillText
    toolTipSubText: hasKey ? (Model.monthLabel(spend.month) || "OpenRouter") : "Management key not set — right-click to configure"

    function spendDatabase() {
        return SQL.LocalStorage.openDatabaseSync(
                    "OpenRouterSpendWidget", "1.0", "OpenRouter spend cache", 1000000)
    }

    function loadCachedSpend() {
        var json = ""
        var database = spendDatabase()
        database.transaction(function(tx) {
            tx.executeSql("CREATE TABLE IF NOT EXISTS cache (id INTEGER PRIMARY KEY, json TEXT)")
            var rs = tx.executeSql("SELECT json FROM cache WHERE id = 1")
            if (rs.rows.length > 0)
                json = rs.rows.item(0).json
        })
        if (!json)
            return
        var parsed = Model.parseSpend(json)
        if (parsed)
            applySpend(parsed)
    }

    function saveCachedSpend(json) {
        var database = spendDatabase()
        database.transaction(function(tx) {
            tx.executeSql("CREATE TABLE IF NOT EXISTS cache (id INTEGER PRIMARY KEY, json TEXT)")
            tx.executeSql("INSERT OR REPLACE INTO cache (id, json) VALUES (1, ?)", [json])
        })
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
        var action = Plasmoid.internalAction("configure")
        if (action)
            action.trigger()
    }

    onExpandedChanged: function(nowExpanded) {
        if (nowExpanded) {
            loadCachedSpend()
            refresh()
        }
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

    compactRepresentation: CompactRepresentation {
        plasmoidItem: root
    }

    fullRepresentation: FullRepresentation {
        spend: root.spend
        updatedNow: root.updatedNow
        fetchBusy: root.fetchBusy
        hasKey: root.hasKey
        lastError: root.lastError
        popupWidth: root.popupWidth
        popupHeight: root.popupHeight
        onConfigureRequested: root.openConfig()
    }
}
