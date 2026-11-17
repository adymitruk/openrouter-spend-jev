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

    property var spend: ({})
    property real updatedNow: 0
    property bool fetchBusy: false
    property bool hasKey: false
    property string lastError: ""
    property int popupWidth: Kirigami.Units.gridUnit * 32
    property int popupHeight: Kirigami.Units.gridUnit * 36
    signal configureRequested()

    property bool showHelp: false

    readonly property color secondary: Qt.alpha(Kirigami.Theme.textColor, 0.65)
    readonly property color hairline: Qt.alpha(Kirigami.Theme.textColor, 0.14)
    readonly property var series: spend && spend.series ? spend.series : []
    readonly property var hourBars: spend && spend.lastHour ? spend.lastHour : []
    readonly property var modelRows: spend && spend.models ? spend.models : []
    readonly property var dayRows: spend && spend.days ? spend.days : []
    readonly property int seriesCount: Model.listLength(series)
    readonly property int hourBarCount: Model.listLength(hourBars)
    readonly property int modelRowCount: Model.listLength(modelRows)
    readonly property int dayRowCount: Model.listLength(dayRows)
    readonly property real dayPeak: Model.sumSeriesTotal(spend) > 0 ? Model.maxSeriesTotal(spend) : 0
    readonly property real hourPeak: hourSum() > 0 ? Model.maxHourTotal(spend) : 0
    readonly property int maxDay: Model.maxDayTotal(spend)
    readonly property int rowHeight: Math.round(Kirigami.Units.gridUnit * 1.55)
    readonly property bool bothLists: modelRowCount > 0 && dayRowCount > 0
    readonly property int innerWidth: Math.max(Kirigami.Units.gridUnit * 16, popupWidth - Kirigami.Units.largeSpacing * 2)
    // Omarchy popup uses a fixed height so list flickables get space; here the body is
    // implicit-height inside a Flickable — Layout.fillHeight on lists collapses to zero.
    readonly property int listAreaHeight: Math.max(
                Kirigami.Units.gridUnit * 10,
                Math.min(Kirigami.Units.gridUnit * 20, Math.floor(popupHeight * 0.38)))

    Layout.minimumWidth: Math.min(popupWidth, Kirigami.Units.gridUnit * 22)
    Layout.minimumHeight: Math.min(popupHeight, Kirigami.Units.gridUnit * 14)
    Layout.preferredWidth: popupWidth
    Layout.preferredHeight: popupHeight
    Layout.maximumWidth: popupWidth
    Layout.maximumHeight: popupHeight

    function hourSum() {
        var rows = panel.hourBars
        var total = 0
        var n = rows && rows.length ? rows.length : 0
        for (var i = 0; i < n; i++)
            total += Model.finiteNumber(rows[i] && rows[i].total)
        return total
    }

    function tip(title, total, models) {
        var label = title + " · " + Model.money(total)
        var mods = models && models.length ? models : []
        if (!mods.length)
            return label
        var parts = []
        var n = Math.min(mods.length, 3)
        for (var i = 0; i < n; i++)
            parts.push(Model.shortModel(mods[i].model) + " " + Model.money(mods[i].total))
        label += "  |  " + parts.join(" · ")
        if (mods.length > n)
            label += " +" + (mods.length - n) + " more"
        return label
    }

    component SectionLabel: PlasmaComponents.Label {
        Layout.fillWidth: true
        font.pixelSize: Kirigami.Theme.smallFont.pixelSize
        font.letterSpacing: 1
        opacity: 0.65
        elide: Text.ElideRight
    }

    component SpendChart: Item {
        id: chart
        property real maxTotal: 0
        readonly property int axisWidth: Math.round(Kirigami.Units.gridUnit * 3)
        readonly property real scale: maxTotal > 0 ? maxTotal : 1
        readonly property real plotWidth: plot.width
        readonly property color axisColor: Qt.alpha(Kirigami.Theme.textColor, 0.6)
        readonly property color gridColor: Qt.alpha(Kirigami.Theme.textColor, 0.14)
        default property alias barContent: plot.data

        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 1
            color: chart.gridColor
        }
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            height: 1
            color: chart.gridColor
        }
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: chart.gridColor
        }

        Item {
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: chart.axisWidth

            PlasmaComponents.Label {
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.rightMargin: 2
                width: parent.width - 2
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideLeft
                text: Model.money(chart.maxTotal)
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                color: chart.axisColor
            }
            PlasmaComponents.Label {
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.rightMargin: 2
                width: parent.width - 2
                horizontalAlignment: Text.AlignRight
                elide: Text.ElideLeft
                text: Model.money(chart.maxTotal / 2)
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                color: chart.axisColor
            }
            PlasmaComponents.Label {
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.rightMargin: 2
                width: parent.width - 2
                horizontalAlignment: Text.AlignRight
                text: "$0.00"
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                color: chart.axisColor
            }
        }

        Item {
            id: plot
            anchors.left: parent.left
            anchors.leftMargin: chart.axisWidth
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            clip: true
        }
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

            Item { Layout.fillWidth: true }

            PlasmaComponents.ToolButton {
                text: "?"
                font.bold: true
                checkable: true
                checked: panel.showHelp
                onClicked: panel.showHelp = !panel.showHelp
                QQC2.ToolTip.text: panel.showHelp ? "Hide help" : "What the numbers mean"
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
            }

            PlasmaComponents.ToolButton {
                icon.name: "configure"
                display: QQC2.AbstractButton.IconOnly
                onClicked: panel.configureRequested()
                QQC2.ToolTip.text: "Set the OpenRouter management key"
                QQC2.ToolTip.visible: hovered
                QQC2.ToolTip.delay: Kirigami.Units.toolTipDelay
            }
        }

        ColumnLayout {
            visible: panel.showHelp
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            PlasmaComponents.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: panel.secondary
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                text: "Pill: $month ($24h, $1h). Month total, then the last 24 hours, then the last hour.\n\n" +
                      "Spend this month is the large figure. LAST 30 DAYS is stacked by model. LAST HOUR is 5-minute buckets. SPEND PER MODEL is this month, ranked. SPEND PER DAY labels today as TODAY.\n\n" +
                      "Days are cut off at local midnight. Data refreshes from OpenRouter when the popup opens. Click the gear to set the management key."
            }
        }

        ColumnLayout {
            visible: panel.lastError === "" && !panel.hasKey && Model.finiteNumber(panel.spend.monthTotal) === 0 && panel.modelRowCount === 0
            Layout.fillWidth: true
            spacing: 2

            PlasmaComponents.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: "OpenRouter management key not set"
            }
            PlasmaComponents.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: panel.secondary
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                text: "Click the gear (top right) to enter it"
            }
        }

        PlasmaComponents.Label {
            visible: panel.lastError !== ""
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: Kirigami.Theme.negativeTextColor
            font.pixelSize: Kirigami.Theme.smallFont.pixelSize
            text: panel.lastError
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            PlasmaComponents.Label {
                text: Model.money(panel.spend.monthTotal)
                textFormat: Text.PlainText
                font.bold: true
                font.pixelSize: Math.round(Kirigami.Units.gridUnit * 2.1)
            }
            PlasmaComponents.Label {
                text: (Model.monthLabel(panel.spend.month) || "THIS MONTH") + " · SPENT"
                color: panel.secondary
                font.pixelSize: Kirigami.Theme.smallFont.pixelSize
                font.letterSpacing: 2
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: panel.hairline
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing

            ColumnLayout {
                Layout.preferredWidth: Math.round(panel.innerWidth * 0.58)
                Layout.maximumWidth: Math.round(panel.innerWidth * 0.62)
                Layout.fillWidth: false
                spacing: Kirigami.Units.smallSpacing

                SectionLabel {
                    text: "LAST 30 DAYS · " + Model.money(Model.sumSeriesTotal(panel.spend))
                }

                SpendChart {
                    id: daysChart
                    Layout.fillWidth: true
                    Layout.preferredHeight: Kirigami.Units.gridUnit * 8
                    maxTotal: panel.dayPeak

                    Repeater {
                        model: panel.series

                        Item {
                            required property var modelData
                            required property int index
                            width: Math.max(1, daysChart.plotWidth) / Math.max(1, panel.seriesCount)
                            height: daysChart.height
                            x: index * width

                            Column {
                                anchors.bottom: parent.bottom
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: parent.width * 0.62
                                spacing: 1

                                Repeater {
                                    model: modelData.models
                                    Rectangle {
                                        required property var modelData
                                        width: parent.width
                                        height: Math.max(1, modelData.total / daysChart.scale * daysChart.height)
                                        radius: 1
                                        color: Model.colorForModel(modelData.model, panel.modelRows)
                                    }
                                }
                            }

                            MouseArea {
                                id: dayHover
                                anchors.fill: parent
                                hoverEnabled: true
                                PlasmaComponents.ToolTip {
                                    visible: dayHover.containsMouse
                                    text: panel.tip(Model.dayLabel(modelData.date, Model.todayDate()), modelData.total, modelData.models)
                                }
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                SectionLabel { text: "LAST HOUR" }

                SpendChart {
                    id: hourChart
                    Layout.fillWidth: true
                    Layout.preferredHeight: Kirigami.Units.gridUnit * 8
                    maxTotal: panel.hourPeak

                    Repeater {
                        model: panel.hourBars

                        Item {
                            required property var modelData
                            required property int index
                            width: Math.max(1, hourChart.plotWidth) / Math.max(1, panel.hourBarCount)
                            height: hourChart.height
                            x: index * width

                            Rectangle {
                                visible: modelData.total > 0 && !(modelData.models && modelData.models.length)
                                anchors.bottom: parent.bottom
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: parent.width * 0.7
                                height: Math.max(1, modelData.total / hourChart.scale * hourChart.height)
                                radius: 2
                                color: Kirigami.Theme.highlightColor
                            }

                            Column {
                                anchors.bottom: parent.bottom
                                anchors.horizontalCenter: parent.horizontalCenter
                                width: parent.width * 0.7
                                spacing: 1

                                Repeater {
                                    model: modelData.models || []
                                    Rectangle {
                                        required property var modelData
                                        width: parent.width
                                        height: Math.max(1, modelData.total / hourChart.scale * hourChart.height)
                                        radius: 1
                                        color: Model.colorForModel(modelData.model, panel.modelRows)
                                    }
                                }
                            }

                            MouseArea {
                                id: hourHover
                                anchors.fill: parent
                                hoverEnabled: true
                                PlasmaComponents.ToolTip {
                                    visible: hourHover.containsMouse
                                    text: panel.tip(modelData.t, modelData.total, modelData.models)
                                }
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: panel.hairline
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.preferredHeight: panel.modelRowCount > 0 || panel.dayRowCount > 0
                                      ? panel.listAreaHeight + Kirigami.Units.gridUnit * 2.2 : 0
            spacing: Kirigami.Units.largeSpacing

            ColumnLayout {
                visible: panel.modelRowCount > 0
                Layout.fillWidth: !panel.bothLists
                Layout.preferredWidth: panel.bothLists ? Math.round(panel.innerWidth * 0.58) : -1
                Layout.maximumWidth: panel.bothLists ? Math.round(panel.innerWidth * 0.62) : -1
                spacing: Kirigami.Units.smallSpacing

                SectionLabel { text: "SPEND PER MODEL" }

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: panel.listAreaHeight

                    PlasmaComponents.ScrollView {
                        id: modelScroll
                        anchors.fill: parent

                        Column {
                            id: modelColumn
                            width: modelScroll.availableWidth
                        spacing: 2

                        Repeater {
                            model: panel.modelRows

                            Item {
                                required property var modelData
                                width: parent.width
                                height: panel.rowHeight

                                Rectangle {
                                    id: swatch
                                    width: Kirigami.Units.smallSpacing * 3
                                    height: width
                                    radius: 2
                                    color: Model.colorForModel(modelData.model, panel.modelRows)
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: parent.left
                                    anchors.leftMargin: Kirigami.Units.smallSpacing
                                }

                                PlasmaComponents.Label {
                                    id: modelMoney
                                    text: Model.money(modelData.total)
                                    textFormat: Text.PlainText
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.right: parent.right
                                    anchors.rightMargin: Kirigami.Units.smallSpacing
                                }

                                PlasmaComponents.Label {
                                    text: Model.shortModel(modelData.model)
                                    textFormat: Text.PlainText
                                    elide: Text.ElideRight
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.left: swatch.right
                                    anchors.leftMargin: Kirigami.Units.smallSpacing
                                    anchors.right: modelMoney.left
                                    anchors.rightMargin: Kirigami.Units.smallSpacing

                                    MouseArea {
                                        id: nameHover
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        PlasmaComponents.ToolTip {
                                            visible: nameHover.containsMouse
                                            text: modelData.model
                                        }
                                    }
                                }
                            }
                        }
                    }
                    }
                }
            }

            ColumnLayout {
                visible: panel.dayRowCount > 0
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                SectionLabel { text: "SPEND PER DAY" }

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: panel.listAreaHeight

                    PlasmaComponents.ScrollView {
                        id: dayScroll
                        anchors.fill: parent

                        Column {
                            id: dayColumn
                            width: dayScroll.availableWidth

                        Repeater {
                            model: panel.dayRows

                            Item {
                                required property var modelData
                                width: parent.width
                                height: panel.rowHeight

                                Rectangle {
                                    width: panel.maxDay > 0 ? parent.width * Model.finiteNumber(modelData.total) / panel.maxDay : 0
                                    height: parent.height
                                    radius: Kirigami.Units.smallSpacing
                                    color: Kirigami.Theme.highlightColor
                                    opacity: 0.16
                                }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: Kirigami.Units.smallSpacing
                                    anchors.rightMargin: Kirigami.Units.smallSpacing * 2

                                    PlasmaComponents.Label {
                                        Layout.preferredWidth: Kirigami.Units.gridUnit * 4.5
                                        text: Model.dayLabel(modelData.date, Model.todayDate())
                                        textFormat: Text.PlainText
                                        elide: Text.ElideRight
                                    }
                                    PlasmaComponents.Label {
                                        Layout.fillWidth: true
                                        text: Model.money(modelData.total)
                                        textFormat: Text.PlainText
                                        horizontalAlignment: Text.AlignRight
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }
                    }
                }
            }
        }

        PlasmaComponents.Label {
            Layout.fillWidth: true
            Layout.bottomMargin: Kirigami.Units.largeSpacing
            visible: panel.fetchBusy || panel.lastError !== "" || Model.finiteNumber(panel.spend.generatedAt) > 0
            horizontalAlignment: Text.AlignHCenter
            font.italic: true
            font.pixelSize: Kirigami.Theme.smallFont.pixelSize
            color: panel.lastError !== "" ? Kirigami.Theme.negativeTextColor : panel.secondary
            text: panel.fetchBusy ? "fetching…" : (panel.lastError !== "" ? panel.lastError : ("since " + Model.timeAgo(panel.spend.generatedAt, panel.updatedNow / 1000)))
        }
        }
    }
}
