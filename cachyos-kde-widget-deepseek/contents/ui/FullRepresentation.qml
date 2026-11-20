import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.kirigami as Kirigami
import "Model.js" as Model

PlasmaExtras.Representation {
    id: panel

    collapseMarginsHint: true

    property var balance: ({})
    property real updatedNow: 0
    property bool fetchBusy: false
    property bool hasKey: false
    property string lastError: ""
    property real lowThreshold: 0
    property int popupWidth: Kirigami.Units.gridUnit * 18
    signal configureRequested()
    signal refreshRequested()

    readonly property color secondary: Qt.alpha(Kirigami.Theme.textColor, 0.65)
    readonly property color hairline: Qt.alpha(Kirigami.Theme.textColor, 0.14)
    readonly property color toppedColor: Kirigami.Theme.highlightColor
    readonly property color grantedColor: "#E5A50A"
    readonly property var items: balance && balance.items ? balance.items : []
    readonly property int itemCount: items ? items.length : 0
    readonly property var primary: Model.primaryItem(balance)
    readonly property var shares: Model.splitShares(primary)
    readonly property bool low: Model.isLow(balance, lowThreshold)
    readonly property bool empty: !primary

    Layout.minimumWidth: Math.min(popupWidth, Kirigami.Units.gridUnit * 16)
    Layout.preferredWidth: popupWidth
    Layout.maximumWidth: popupWidth

    function secondaryLine() {
        if (!primary) return ""
        return "topped up " + Model.formatMoney(primary.toppedUp, primary.currency)
                + "   ·   granted " + Model.formatMoney(primary.granted, primary.currency)
    }

    component SectionLabel: PlasmaComponents.Label {
        Layout.fillWidth: true
        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
        font.letterSpacing: 1
        opacity: 0.65
        elide: Text.ElideRight
    }

    contentItem: PlasmaComponents.ScrollView {
        id: outerScroll
        clip: true

        ColumnLayout {
            id: body
            width: outerScroll.availableWidth
            spacing: Kirigami.Units.smallSpacing

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.smallSpacing

                SectionLabel { text: "DEEPSEEK BALANCE" }

                PlasmaComponents.Label {
                    visible: !panel.empty
                    text: Model.statusText(panel.balance)
                    font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                    font.letterSpacing: 1
                    font.bold: true
                    color: panel.balance && panel.balance.available
                           ? "#3DAE5B" : Kirigami.Theme.negativeTextColor
                }

                PlasmaComponents.ToolButton {
                    icon.name: "view-refresh"
                    display: QQC2.AbstractButton.IconOnly
                    enabled: !panel.fetchBusy
                    onClicked: panel.refreshRequested()
                    QQC2.ToolTip.text: panel.fetchBusy ? "Refreshing…" : "Refresh now"
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                }

                PlasmaComponents.ToolButton {
                    icon.name: "configure"
                    display: QQC2.AbstractButton.IconOnly
                    onClicked: panel.configureRequested()
                    QQC2.ToolTip.text: "Set the DeepSeek API key"
                    QQC2.ToolTip.visible: hovered
                    QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
                }
            }

            PlasmaComponents.Label {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.smallSpacing
                text: panel.primary ? Model.formatMoney(panel.primary.total, panel.primary.currency) : "\u2014"
                textFormat: Text.PlainText
                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 2.2)
                font.bold: true
                color: panel.low ? panel.grantedColor : Kirigami.Theme.textColor
                elide: Text.ElideRight
            }

            PlasmaComponents.Label {
                Layout.fillWidth: true
                visible: panel.primary !== null
                text: panel.secondaryLine()
                textFormat: Text.PlainText
                color: panel.secondary
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                elide: Text.ElideRight
            }

            // Split bar: topped-up (own money) against granted (free credit).
            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 0.6
                Layout.topMargin: Kirigami.Units.smallSpacing
                visible: panel.primary !== null

                Rectangle {
                    anchors.fill: parent
                    radius: height / 2
                    color: Qt.alpha(Kirigami.Theme.textColor, 0.12)
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: panel.shares.hasSplit ? parent.width * panel.shares.toppedShare : parent.width
                    radius: height / 2
                    color: panel.toppedColor
                    opacity: panel.shares.hasSplit ? 1 : 0.35
                }

                Rectangle {
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    visible: panel.shares.hasSplit && panel.shares.grantedShare > 0
                    width: parent.width * panel.shares.grantedShare
                    radius: height / 2
                    color: panel.grantedColor
                }
            }

            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 2
                visible: panel.primary !== null
                spacing: Kirigami.Units.smallSpacing

                Rectangle {
                    width: Kirigami.Units.smallSpacing * 2
                    height: width
                    radius: 2
                    color: panel.toppedColor
                }
                PlasmaComponents.Label {
                    text: "topped up"
                    color: panel.secondary
                    font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                }
                Item { Layout.fillWidth: true }
                Rectangle {
                    visible: panel.shares.hasSplit && panel.shares.grantedShare > 0
                    width: Kirigami.Units.smallSpacing * 2
                    height: width
                    radius: 2
                    color: panel.grantedColor
                }
                PlasmaComponents.Label {
                    visible: panel.shares.hasSplit && panel.shares.grantedShare > 0
                    text: "granted"
                    color: panel.secondary
                    font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                Layout.topMargin: Kirigami.Units.smallSpacing
                visible: panel.itemCount > 1
                color: panel.hairline
            }

            // Every currency the account reports; the hero above only shows one.
            Repeater {
                model: panel.itemCount > 1 ? panel.items : []

                RowLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    PlasmaComponents.Label {
                        Layout.fillWidth: true
                        text: modelData.currency
                        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                        font.letterSpacing: 1
                        color: panel.secondary
                    }
                    PlasmaComponents.Label {
                        text: Model.formatMoney(modelData.total, modelData.currency)
                        textFormat: Text.PlainText
                    }
                }
            }

            PlasmaComponents.Label {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.smallSpacing
                visible: panel.low && !panel.empty
                wrapMode: Text.WordWrap
                color: panel.grantedColor
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                text: "Balance is below " + Model.formatMoney(panel.lowThreshold, panel.primary ? panel.primary.currency : "USD")
                      + " — top up before the next run fails."
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.smallSpacing
                visible: panel.lastError === "" && !panel.hasKey
                spacing: 2

                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: "DeepSeek API key not set"
                }
                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: panel.secondary
                    font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                    text: "Click the gear (top right) to paste it — it goes to api.deepseek.com/user/balance over HTTPS."
                }
            }

            PlasmaComponents.Label {
                Layout.fillWidth: true
                Layout.topMargin: Kirigami.Units.smallSpacing
                Layout.bottomMargin: Kirigami.Units.largeSpacing
                visible: panel.fetchBusy || panel.lastError !== ""
                         || Model.finiteNumber(panel.balance.fetchedAt) > 0
                wrapMode: Text.WordWrap
                horizontalAlignment: Text.AlignHCenter
                font.italic: true
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                color: panel.lastError !== "" ? Kirigami.Theme.negativeTextColor : panel.secondary
                text: panel.fetchBusy ? "fetching…"
                      : (panel.lastError !== "" ? panel.lastError
                         : "updated " + Model.timeAgo(panel.balance.fetchedAt, panel.updatedNow / 1000))
            }
        }
    }
}
