import QtQuick
import QtQuick.LocalStorage as SQL
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import "Model.js" as Model
import "../code/BalanceBackend.js" as Backend

PlasmoidItem {
    id: root

    property var balance: Model.emptyBalance()
    property bool fetchBusy: false
    property bool ready: false
    property string lastError: ""
    property real updatedNow: Date.now()

    readonly property string configuredKey: String(Plasmoid.configuration.deepseekKey || "").trim()
    readonly property bool hasKey: configuredKey.length > 0
    readonly property int refreshMinutes: {
        var n = parseInt(Plasmoid.configuration.refreshMinutes, 10)
        return isFinite(n) && n >= 1 ? Math.min(n, 120) : 10
    }
    readonly property real lowThreshold: {
        var n = Number(Plasmoid.configuration.lowBalanceThreshold)
        return isFinite(n) && n > 0 ? n : 0
    }
    readonly property bool isLow: Model.isLow(balance, lowThreshold)
    readonly property string pillText: lastError !== "" ? Model.shortError(lastError) : Model.pillLabel(balance)
    readonly property string statusText: Model.statusText(balance)
    readonly property int popupWidth: {
        var configured = parseInt(Plasmoid.configuration.popupWidth, 10)
        if (isFinite(configured) && configured > 0)
            return configured
        return Kirigami.Units.gridUnit * 18
    }

    preferredRepresentation: Plasmoid.formFactor === PlasmaCore.Types.Planar ? fullRepresentation : null

    readonly property url panelIcon: Qt.resolvedUrl("../icons/deepseek-balance.svg")

    Plasmoid.icon: panelIcon
    Plasmoid.title: "DeepSeek Balance"
    badgeText: ""

    toolTipMainText: lastError !== "" ? lastError : Model.pillLabel(balance)
    toolTipSubText: {
        if (!hasKey)
            return "API key not set — right-click to configure"
        if (lastError !== "")
            return balance.items.length ? "Showing cached balance" : "No cached balance yet"
        var item = Model.primaryItem(balance)
        if (!item)
            return "DeepSeek"
        return (Model.statusText(balance) || "DeepSeek") + " · topped up "
                + Model.formatMoney(item.toppedUp, item.currency) + " · granted "
                + Model.formatMoney(item.granted, item.currency)
    }

    function balanceDatabase() {
        return SQL.LocalStorage.openDatabaseSync(
                    "DeepSeekBalanceWidget", "1.0", "DeepSeek balance cache", 100000)
    }

    function loadCachedBalance() {
        var json = ""
        var database = balanceDatabase()
        database.transaction(function(tx) {
            tx.executeSql("CREATE TABLE IF NOT EXISTS cache (id INTEGER PRIMARY KEY, json TEXT)")
            var rs = tx.executeSql("SELECT json FROM cache WHERE id = 1")
            if (rs.rows.length > 0)
                json = rs.rows.item(0).json
        })
        if (!json)
            return
        var parsed = Model.parseBalance(json)
        if (parsed)
            applyBalance(parsed)
    }

    function saveCachedBalance(json) {
        var database = balanceDatabase()
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

    // Keep the endpoint's own fetch time so "updated X ago" never claims a
    // freshness the payload does not have.
    function stamp(json, fetchedAt) {
        var text = String(json || "")
        try {
            var data = JSON.parse(text)
            data.__fetched_at = fetchedAt
            return JSON.stringify(data)
        } catch (e) {
            return text
        }
    }

    function applyBalance(parsed) {
        if (!parsed)
            return
        Qt.callLater(function() {
            root.balance = parsed
        })
    }

    function refresh() {
        var key = String(Plasmoid.configuration.deepseekKey || "").trim()
        if (!key) {
            loadCachedBalance()
            return
        }
        if (fetchBusy)
            return
        fetchBusy = true
        var started = Date.now()
        Backend.requestBalance(key, function(err, json) {
            Qt.callLater(function() {
                root.fetchBusy = false
                if (err) {
                    root.setError(String(err))
                    root.loadCachedBalance()
                    return
                }
                root.clearError()
                var stamped = root.stamp(json, Math.floor(started / 1000))
                root.saveCachedBalance(stamped)
                var parsed = Model.parseBalance(stamped)
                if (parsed)
                    root.applyBalance(parsed)
            })
        })
    }

    function openConfig() {
        var action = Plasmoid.internalAction("configure")
        if (action)
            action.trigger()
    }

    onExpandedChanged: function(nowExpanded) {
        if (nowExpanded) {
            loadCachedBalance()
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
            root.loadCachedBalance()
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

    // A hung request must not wedge the widget behind a permanent "busy".
    Timer {
        id: busyWatchdog
        interval: 20000
        running: root.fetchBusy
        repeat: false
        onTriggered: root.fetchBusy = false
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
        balance: root.balance
        updatedNow: root.updatedNow
        fetchBusy: root.fetchBusy
        hasKey: root.hasKey
        lastError: root.lastError
        lowThreshold: root.lowThreshold
        popupWidth: root.popupWidth
        onConfigureRequested: root.openConfig()
        onRefreshRequested: root.refresh()
    }
}
