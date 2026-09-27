import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

BarWidget {
  id: root
  moduleName: "adam.openrouter-spend"

  // The display is fed entirely from disk: a 5-minute fetch writes
  // openrouter-spend.json, and the pill + hover panel only ever read it.
  readonly property string pythonPath: "/usr/bin/python3"
  readonly property string helperPath: String(Qt.resolvedUrl("openrouter-helper.py")).replace(/^file:\/\//, "")
  readonly property string stateFile: (Quickshell.env("HOME") || "") + "/.local/state/omarchy/settings/openrouter-spend.json"

  readonly property int refreshMinutes: Math.max(1, parseInt(root.setting("refreshMinutes", 5), 10) || 5)

  property var spend: ({ month: "", monthTotal: 0, days: [], models: [] })
  readonly property string barLabel: Model.barLabel(spend.monthTotal)

  function reload() {
    if (!readProc.running) readProc.running = true
  }

  function refresh() {
    if (!fetchProc.running) fetchProc.running = true
  }

  // Launch the tkinter dialog to enter the management key.
  Process {
    id: keyDialogProc
    command: [root.pythonPath, root.dialogPath]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        if (text.trim() !== "") root.reload()
      }
    }
  }

  readonly property string dialogPath: String(Qt.resolvedUrl("openrouter-key-dialog.py")).replace(/^file:\/\//, "")

  // Read a spacing/geometry key from shell.json config as a Style.space unit.
  // Every layout number is tunable in the dashboard config file (shell.json,
  // bar.layout.center -> adam.openrouter-spend -> config).
  function sp(key, fallback) {
    var v = parseInt(root.setting(key, fallback), 10)
    return isFinite(v) ? v : fallback
  }

  // ---- data lifecycle: re-read on popup open (always fresh when you look)
  //      and on init. Polls every 5 min to self-correct.
  Process {
    id: readProc
    command: [root.pythonPath, root.helperPath, "read", "openrouter-spend.json"]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var parsed = Model.parseSpend(text)
        if (parsed) root.spend = parsed
      }
    }
  }

  Process {
    id: fetchProc
    command: [root.pythonPath, root.helperPath, "fetch"]
    onExited: function(exitCode) {
      if (exitCode === 0) root.reload()
    }
  }

  Timer {
    interval: root.refreshMinutes * 60 * 1000
    running: true
    repeat: true
    triggeredOnStart: true
    onTriggered: root.refresh()
  }

  // Sync the management key from settings to the state dir on startup.
  Process {
    id: syncKeyProc
    command: [root.pythonPath, root.helperPath, "write-key", "openrouter-key", root.setting("openrouterKey", "")]
    onExited: function(exitCode) {
      if (exitCode !== 0) console.warn("openrouter-spend", "key sync failed")
    }
  }

  Component.onCompleted: {
    var k = root.setting("openrouterKey", "")
    if (k !== "") syncKeyProc.running = true
  }

  // An early read can race shell startup; one delayed re-read self-corrects.
  Timer {
    interval: 1500
    running: true
    onTriggered: root.reload()
  }

  // ---- hover panel ("explode"). Open while the pointer is on the pill or on
  //      the panel itself; close shortly after it leaves both. PopupCard is
  //      declared inline (anchorItem/bar/owner at creation) and `open` is
  //      driven declaratively — the same pattern as the built-in media widget.
  property bool popupOpen: false
  readonly property bool panelHovered: popup.containsMouse === true

  function openPanel() {
    root.reload()
    closeTimer.stop()
    root.popupOpen = true
  }

  onPanelHoveredChanged: {
    if (root.panelHovered) closeTimer.stop()
    else closeTimer.restart()
  }

  Timer {
    id: closeTimer
    interval: 300
    onTriggered: root.popupOpen = false
  }

  // One-second ticker driving the "since X ago" freshness readout, so the
  // countdown to the next 5-minute fetch is visible.
  property real updatedNow: Date.now()
  Timer {
    interval: 1000
    running: true
    repeat: true
    onTriggered: root.updatedNow = Date.now()
  }

  // ---- the pill: raw text + MouseArea, like the media widget (no WidgetButton,
  //      so hover is unambiguous).
  Item {
    id: pill
    anchors.fill: parent
    implicitWidth: pillText.implicitWidth + Style.space(16)
    implicitHeight: root.barSize

    Text {
      id: pillText
      anchors.centerIn: parent
      text: Model.pillLabel(root.spend.monthTotal, root.spend.last24h, root.spend.lastHourTotal)
      textFormat: Text.PlainText
      color: root.bar.foreground
      font.family: root.bar.fontFamily
      font.pixelSize: Style.font.caption
      font.bold: root.spend.monthTotal > 0
    }

    MouseArea {
      id: pillHover
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onEntered: root.openPanel()
      onExited: closeTimer.restart()
      onClicked: {
        if (root.popupOpen && !root.panelHovered && !pillHover.containsMouse) root.popupOpen = false
        else root.openPanel()
      }
    }
  }

  // ---- the popup, the size of the weather widget.
  PopupCard {
    id: popup
    anchorItem: root
    bar: root.bar
    owner: root
    triggerMode: "hover"
    open: root.popupOpen
    contentWidth: Style.space(root.sp("popupWidth", 500))
    contentHeight: Style.space(root.sp("popupHeight", 780))

    readonly property int maxDay: Model.maxDayTotal(root.spend)
    readonly property int modelRow: Style.space(root.sp("modelRowHeight", 34))
    readonly property int dayRow: Style.space(root.sp("dayRowHeight", 32))
    property bool showHelp: false

    // Single-line hover tooltip for a day bar: "26 SEP · $2.40" plus the top
    // three contributing models (so the stacked colors are legible).
    function chartTooltip(day) {
      var label = Model.dayLabel(day.date, Model.todayDate()) + " · " + Model.money(day.total)
      var mods = day.models || []
      if (mods.length) {
        var parts = []
        var n = Math.min(mods.length, 3)
        for (var i = 0; i < n; i++) parts.push(Model.shortModel(mods[i].model) + " " + Model.money(mods[i].total))
        label += "  |  " + parts.join(" · ")
        if (mods.length > n) label += " +" + (mods.length - n) + " more"
      }
      return label
    }

    function scrollVertically(flickable, wheel) {
      var delta = wheel.pixelDelta.y !== 0 ? wheel.pixelDelta.y : wheel.angleDelta.y
      delta = (delta / 120) * Style.space(48)
      flickable.contentY = Math.max(0, Math.min(Math.max(0, flickable.contentHeight - flickable.height), flickable.contentY - delta))
      wheel.accepted = true
    }

    ColumnLayout {
      anchors.fill: parent
      anchors.leftMargin: Style.space(root.sp("marginX", 20))
      anchors.rightMargin: Style.space(root.sp("marginX", 20))
      anchors.topMargin: Style.space(root.sp("marginY", 14))
      anchors.bottomMargin: Style.space(root.sp("marginY", 14))
      spacing: Style.space(root.sp("sectionGap", 10))

      // ---- Settings gear row (always visible).
      RowLayout {
        Layout.fillWidth: true
        Layout.preferredHeight: Style.space(28)
        spacing: Style.space(4)

        Item { Layout.fillWidth: true }

        // ? help icon — click toggles inline help below.
        Text {
          text: "?"
          color: Qt.darker(popup.bar.foreground, 1.4)
          font.family: popup.bar.fontFamily
          font.pixelSize: Style.font.body * 1.5
          font.bold: true
          Layout.alignment: Qt.AlignVCenter

          MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: popup.showHelp = !popup.showHelp
          }
        }

        Text {
          text: "\uF013"
          color: Qt.darker(popup.bar.foreground, 1.4)
          font.family: "JetBrainsMono Nerd Font"
          font.pixelSize: Style.font.body * 1.5
          Layout.alignment: Qt.AlignVCenter

          MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: keyDialogProc.running = true
          }
        }
      }

      // ---- Inline help text (toggled by clicking ?).
      Column {
        visible: popup.showHelp
        z: 10
        Layout.fillWidth: true
        spacing: Style.space(6)
        topPadding: Style.space(4)
        bottomPadding: Style.space(4)

        Text {
          width: parent.width
          textFormat: Text.RichText
          wrapMode: Text.WordWrap
          color: Qt.lighter(popup.bar.foreground, 1.1)
          font.family: popup.bar.fontFamily
          font.pixelSize: Style.font.bodySmall
          lineHeight: 1.5
          text: "<b>Pill (bar)</b><br>" +
                "$&lt;month&gt; ($&lt;24h&gt;, $&lt;1h&gt;)<br>" +
                "Month total · last 24 hours · last hour spend.<br><br>" +
                "<b>Panel</b><br>" +
                "• <b>Spend this month</b> — big hero number at top.<br>" +
                "• <b>LAST 30 DAYS</b> — stacked bar chart, per model per day.<br>" +
                "• <b>LAST HOUR</b> — 5-minute buckets for the last 60 minutes.<br>" +
                "• <b>SPEND PER MODEL</b> — ranked by cost this month.<br>" +
                "• <b>SPEND PER DAY</b> — daily totals, today labelled TODAY.<br>" +
                "• All times are your local timezone (cut-off at midnight).<br>" +
                "• Data refreshes every " + root.refreshMinutes + " minutes."
        }

        Text {
          width: parent.width
          textFormat: Text.RichText
          wrapMode: Text.WordWrap
          color: Qt.darker(popup.bar.foreground, 1.5)
          font.family: popup.bar.fontFamily
          font.pixelSize: Style.font.bodySmall
          font.italic: true
          text: "click ? to close"
        }
      }

      // ---- Key-entry prompt when no management key is set.
      Column {
        visible: root.spend.monthTotal === 0 && root.spend.models.length === 0
        Layout.fillWidth: true
        spacing: Style.space(6)

        Text {
          width: parent.width
          text: "OpenRouter management key not set"
          color: popup.bar.foreground
          font.family: popup.bar.fontFamily
          font.pixelSize: Style.font.caption
        }

        Text {
          width: parent.width
          text: "Click the gear (top right) to enter it"
          color: Qt.darker(popup.bar.foreground, 1.5)
          font.family: popup.bar.fontFamily
          font.pixelSize: Style.font.bodySmall
        }
      }

      // ---- Hero: dollars spent this month (static).
      Column {
        Layout.fillWidth: true
        Layout.preferredHeight: Style.space(root.sp("heroHeight", 66))
        spacing: Style.space(root.sp("heroGap", 14))

        Text {
          text: Model.money(root.spend.monthTotal)
          textFormat: Text.PlainText
          color: popup.bar.foreground
          font.family: popup.bar.fontFamily
          font.pixelSize: Style.font.displayLarge * 2
          font.bold: true
        }
        Text {
          text: Model.monthLabel(root.spend.month) + " · SPENT"
          color: Qt.darker(popup.bar.foreground, 1.4)
          font.family: popup.bar.fontFamily
          font.pixelSize: Style.font.caption
          font.letterSpacing: 2
          topPadding: Style.space(root.sp("heroCaptionPad", 2))
        }
      }

      Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: Style.spacing.hairline
        color: popup.bar.foreground
        opacity: 0.12
      }

      // ---- Two time-series charts side by side: LAST 30 DAYS (stacked, per
      //      model) and LAST HOUR (5-minute bars).
      RowLayout {
        Layout.fillWidth: true
        spacing: Style.space(root.sp("sectionGap", 10))

        // LAST 30 DAYS — stacked by model (takes 60% of the charts row; the
        //      hour chart has far fewer bars).
        Column {
          Layout.fillWidth: false
          Layout.preferredWidth: Math.max(200, parent.width * 0.60)
          spacing: Style.space(4)

          Text {
            width: parent.width
            text: "LAST 30 DAYS · " + Model.money(Model.sumSeriesTotal(root.spend))
            color: Qt.darker(popup.bar.foreground, 1.4)
            font.family: popup.bar.fontFamily
            font.pixelSize: Style.font.caption
            font.letterSpacing: 1
            topPadding: Style.space(root.sp("chartHeaderPad", 20))
          }

          Item {
            id: chartArea
            width: parent.width
            height: Style.space(root.sp("chartHeight", 150))
            clip: true

            readonly property int axisW: Style.space(36)
            property int count: Math.max(1, (root.spend.series && root.spend.series.length) || 0)
            readonly property real maxTotal: Model.maxSeriesTotal(root.spend)

            // Horizontal gridlines: max, midpoint, baseline.
            Rectangle { x: 0; y: 0; width: parent.width; height: Style.spacing.hairline; color: popup.bar.foreground; opacity: 0.08 }
            Rectangle { x: 0; y: parent.height / 2; width: parent.width; height: Style.spacing.hairline; color: popup.bar.foreground; opacity: 0.08 }
            Rectangle { x: 0; y: parent.height - Style.spacing.hairline; width: parent.width; height: Style.spacing.hairline; color: popup.bar.foreground; opacity: 0.12 }

            // Y-axis value labels (left edge).
            Item {
              anchors.left: parent.left
              anchors.top: parent.top
              anchors.bottom: parent.bottom
              width: chartArea.axisW

              Text {
                anchors.right: parent.right
                anchors.rightMargin: Style.space(2)
                anchors.top: parent.top
                anchors.topMargin: Style.space(2)
                horizontalAlignment: Text.AlignRight
                text: Model.money(chartArea.maxTotal)
                color: Qt.darker(popup.bar.foreground, 1.5)
                font.family: popup.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
              }
              Text {
                anchors.right: parent.right
                anchors.rightMargin: Style.space(2)
                anchors.verticalCenter: parent.verticalCenter
                horizontalAlignment: Text.AlignRight
                text: Model.money(chartArea.maxTotal / 2)
                color: Qt.darker(popup.bar.foreground, 1.5)
                font.family: popup.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
              }
              Text {
                anchors.right: parent.right
                anchors.rightMargin: Style.space(2)
                anchors.bottom: parent.bottom
                horizontalAlignment: Text.AlignRight
                text: "$0.00"
                color: Qt.darker(popup.bar.foreground, 1.5)
                font.family: popup.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
              }
            }

            // Bars, offset right to leave room for the axis.
            Item {
              id: barsArea30
              anchors.left: parent.left; anchors.leftMargin: chartArea.axisW
              anchors.right: parent.right
              anchors.top: parent.top
              anchors.bottom: parent.bottom

              Repeater {
                model: root.spend.series

                Item {
                  required property var modelData
                  required property int index
                  width: barsArea30.width / chartArea.count
                  height: barsArea30.height
                  x: index * width

                  Column {
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: parent.width * 0.62
                    spacing: Style.space(1)

                    Repeater {
                      model: modelData.models

                      Rectangle {
                        required property var modelData
                        width: parent.width
                        height: Math.max(1, modelData.total / chartArea.maxTotal * chartArea.height)
                        radius: Style.space(1)
                        color: Model.colorForModel(modelData.model, root.spend.models)
                      }
                    }
                  }

                  MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.NoButton
                    PanelToolTip {
                      visible: parent.containsMouse
                      text: popup.chartTooltip(modelData)
                      fontFamily: popup.bar.fontFamily
                    }
                  }
                }
              }
            }
          }
        }

        // LAST HOUR — 5-minute bars.
        Column {
          Layout.fillWidth: true
          spacing: Style.space(4)

          Text {
            width: parent.width
            text: "LAST HOUR"
            color: Qt.darker(popup.bar.foreground, 1.4)
            font.family: popup.bar.fontFamily
            font.pixelSize: Style.font.caption
            font.letterSpacing: 1
            topPadding: Style.space(root.sp("chartHeaderPad", 20))
          }

          Item {
            id: hourArea
            width: parent.width
            height: Style.space(root.sp("chartHeight", 150))
            clip: true

            readonly property int axisW: Style.space(36)
            property int count: Math.max(1, (root.spend.lastHour && root.spend.lastHour.length) || 0)
            readonly property real maxTotal: Model.maxHourTotal(root.spend)

            // Horizontal gridlines: max, midpoint, baseline.
            Rectangle { x: 0; y: 0; width: parent.width; height: Style.spacing.hairline; color: popup.bar.foreground; opacity: 0.08 }
            Rectangle { x: 0; y: parent.height / 2; width: parent.width; height: Style.spacing.hairline; color: popup.bar.foreground; opacity: 0.08 }
            Rectangle { x: 0; y: parent.height - Style.spacing.hairline; width: parent.width; height: Style.spacing.hairline; color: popup.bar.foreground; opacity: 0.12 }

            // Y-axis value labels (left edge) — the hour chart's max is cents,
            // so these make the scale obvious.
            Item {
              anchors.left: parent.left
              anchors.top: parent.top
              anchors.bottom: parent.bottom
              width: hourArea.axisW

              Text {
                anchors.right: parent.right
                anchors.rightMargin: Style.space(2)
                anchors.top: parent.top
                anchors.topMargin: Style.space(2)
                horizontalAlignment: Text.AlignRight
                text: Model.money(hourArea.maxTotal)
                color: Qt.darker(popup.bar.foreground, 1.5)
                font.family: popup.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
              }
              Text {
                anchors.right: parent.right
                anchors.rightMargin: Style.space(2)
                anchors.verticalCenter: parent.verticalCenter
                horizontalAlignment: Text.AlignRight
                text: Model.money(hourArea.maxTotal / 2)
                color: Qt.darker(popup.bar.foreground, 1.5)
                font.family: popup.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
              }
              Text {
                anchors.right: parent.right
                anchors.rightMargin: Style.space(2)
                anchors.bottom: parent.bottom
                horizontalAlignment: Text.AlignRight
                text: "$0.00"
                color: Qt.darker(popup.bar.foreground, 1.5)
                font.family: popup.bar.fontFamily
                font.pixelSize: Style.font.bodySmall
              }
            }

            // Bars, offset right for the axis.
            Item {
              id: barsArea60
              anchors.left: parent.left; anchors.leftMargin: hourArea.axisW
              anchors.right: parent.right
              anchors.top: parent.top
              anchors.bottom: parent.bottom

              Repeater {
                model: root.spend.lastHour

                Item {
                  required property var modelData
                  required property int index
                  width: barsArea60.width / hourArea.count
                  height: barsArea60.height
                  x: index * width

                  Rectangle {
                    visible: modelData.total > 0 && (!modelData.models || modelData.models.length === 0)
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: parent.width * 0.7
                    height: Math.max(1, modelData.total / hourArea.maxTotal * hourArea.height)
                    radius: Style.space(2)
                    color: Color.accent
                  }

                  // Per-model stacked segments (present after the next fetch
                  // cycle brings in per-model breakdown).
                  Column {
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: parent.width * 0.7
                    spacing: Style.space(1)

                    Repeater {
                      model: modelData.models || []

                      Rectangle {
                        required property var modelData
                        width: parent.width
                        height: Math.max(1, modelData.total / hourArea.maxTotal * hourArea.height)
                        radius: Style.space(1)
                        color: Model.colorForModel(modelData.model, root.spend.models)
                      }
                    }
                  }

                  MouseArea {
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.NoButton
                    PanelToolTip {
                      visible: parent.containsMouse
                      text: modelData.t + " · " + Model.money(modelData.total)
                      fontFamily: popup.bar.fontFamily
                    }
                  }
                }
              }
            }

            // No horizontal axis labels
          }
        }
      }

      Rectangle {
        Layout.fillWidth: true
        Layout.preferredHeight: Style.spacing.hairline
        color: popup.bar.foreground
        opacity: 0.12
      }

      // ---- The two spend lists side by side; each scrolls independently and
      //      fills the height below the charts.
      RowLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: Style.space(root.sp("sectionGap", 10))

        // SPEND PER MODEL (left) — fixed 60% of the row width.
        Item {
          Layout.fillWidth: false
          Layout.preferredWidth: Math.max(120, parent.width * 0.60)
          Layout.fillHeight: true
          visible: root.spend.models.length > 0

          ColumnLayout {
            anchors.fill: parent
            anchors.rightMargin: Style.space(14)
            spacing: Style.space(4)

            Text {
              Layout.fillWidth: true
              text: "SPEND PER MODEL"
              color: Qt.darker(popup.bar.foreground, 1.4)
              font.family: popup.bar.fontFamily
              font.pixelSize: Style.font.caption
              font.letterSpacing: 1
            }

            Flickable {
              id: modelFlick
              Layout.fillWidth: true
              Layout.fillHeight: true
              clip: true
              boundsBehavior: Flickable.StopAtBounds
              contentHeight: modelRows.implicitHeight
              interactive: contentHeight > height

              MouseArea {
                anchors.fill: parent
                z: 1
                acceptedButtons: Qt.NoButton
                onWheel: function(wheel) { popup.scrollVertically(modelFlick, wheel) }
              }

              Column {
                id: modelRows
                width: parent.width
                spacing: Style.space(root.sp("modelRowGap", 2))

                Repeater {
                  model: root.spend.models

                  Item {
                    required property var modelData
                    width: parent.width
                    height: popup.modelRow

                    // Legend swatch: same color as this model's chart segment.
                    Rectangle {
                      id: modelSwatch
                      width: Style.space(12)
                      height: Style.space(12)
                      radius: Style.space(2)
                      color: Model.colorForModel(modelData.model, root.spend.models)
                      anchors.verticalCenter: parent.verticalCenter
                      anchors.left: parent.left
                      anchors.leftMargin: Style.space(6)
                    }

                    // Money (right-aligned, sized to content).
                    Text {
                      id: modelMoney
                      text: Model.money(modelData.total)
                      textFormat: Text.PlainText
                      color: Qt.darker(popup.bar.foreground, 1.15)
                      font.family: popup.bar.fontFamily
                      font.pixelSize: Style.font.body
                      horizontalAlignment: Text.AlignRight
                      anchors.verticalCenter: parent.verticalCenter
                      anchors.right: parent.right
                      anchors.rightMargin: Style.space(6)
                    }

                    // Model name fills the space between swatch and money.
                    Text {
                      id: modelName
                      text: Model.shortModel(modelData.model)
                      textFormat: Text.PlainText
                      elide: Text.ElideRight
                      color: popup.bar.foreground
                      font.family: popup.bar.fontFamily
                      font.pixelSize: Style.font.body
                      anchors.verticalCenter: parent.verticalCenter
                      anchors.left: modelSwatch.right
                      anchors.leftMargin: Style.space(6)
                      anchors.right: modelMoney.left
                      anchors.rightMargin: Style.space(6)

                      MouseArea {
                        id: modelHover
                        anchors.fill: parent
                        hoverEnabled: true
                        acceptedButtons: Qt.NoButton
                        PanelToolTip {
                          visible: modelHover.containsMouse
                          text: modelData.model
                          fontFamily: popup.bar.fontFamily
                        }
                      }
                    }
                  }
                }
              }
            }
          }

          // Vertical scrollbar for the model list.
          Rectangle {
            visible: modelFlick.contentHeight > modelFlick.height
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: Style.space(5)
            radius: width / 2
            color: Qt.darker(popup.bar.foreground, 2.2)
            opacity: 0.25

            Rectangle {
              y: modelFlick.contentHeight > modelFlick.height
                ? (parent.height - height) * (modelFlick.contentY / (modelFlick.contentHeight - modelFlick.height)) : 0
              width: parent.width
              height: Math.max(Style.space(16), parent.height * modelFlick.height / modelFlick.contentHeight)
              radius: width / 2
              color: popup.bar.foreground
              opacity: 0.75
            }
          }
        }

        // SPEND PER DAY (right) — fills the remaining ~40%.
        Item {
          Layout.fillWidth: true
          Layout.fillHeight: true
          visible: root.spend.days.length > 0

          ColumnLayout {
            anchors.fill: parent
            anchors.rightMargin: Style.space(14)
            spacing: Style.space(4)

            Text {
              Layout.fillWidth: true
              text: "SPEND PER DAY"
              color: Qt.darker(popup.bar.foreground, 1.4)
              font.family: popup.bar.fontFamily
              font.pixelSize: Style.font.caption
              font.letterSpacing: 1
            }

            Flickable {
              id: dayFlick
              Layout.fillWidth: true
              Layout.fillHeight: true
              clip: true
              boundsBehavior: Flickable.StopAtBounds
              contentHeight: dayRows.implicitHeight
              interactive: contentHeight > height

              MouseArea {
                anchors.fill: parent
                z: 1
                acceptedButtons: Qt.NoButton
                onWheel: function(wheel) { popup.scrollVertically(dayFlick, wheel) }
              }

              Column {
                id: dayRows
                width: parent.width
                spacing: Style.space(root.sp("dayRowGap", 0))

                Repeater {
                  model: root.spend.days

                  Item {
                    required property var modelData
                    width: parent.width
                    height: popup.dayRow

                    Rectangle {
                      width: popup.maxDay > 0 ? (parent.width * Model.finiteNumber(modelData.total) / popup.maxDay) : 0
                      height: parent.height
                      radius: Style.cornerRadius
                      color: Style.hoverFillFor(popup.bar.foreground, Color.accent)
                      opacity: 0.16
                    }

                    Row {
                      anchors.left: parent.left
                      anchors.right: parent.right
                      anchors.leftMargin: Style.space(6)
                      anchors.rightMargin: Style.space(6)
                      anchors.verticalCenter: parent.verticalCenter

                      Text {
                        width: Style.space(84)
                        text: Model.dayLabel(modelData.date, Model.todayDate())
                        textFormat: Text.PlainText
                        color: popup.bar.foreground
                        font.family: popup.bar.fontFamily
                        font.pixelSize: Style.font.body
                      }

                      Text {
                        width: parent.width - Style.space(84)
                        text: Model.money(modelData.total)
                        textFormat: Text.PlainText
                        color: popup.bar.foreground
                        font.family: popup.bar.fontFamily
                        font.pixelSize: Style.font.body
                        horizontalAlignment: Text.AlignRight
                        elide: Text.ElideRight
                      }
                    }
                  }
                }
              }
            }
          }

          // Vertical scrollbar for the day list.
          Rectangle {
            visible: dayFlick.contentHeight > dayFlick.height
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: Style.space(5)
            radius: width / 2
            color: Qt.darker(popup.bar.foreground, 2.2)
            opacity: 0.25

            Rectangle {
              y: dayFlick.contentHeight > dayFlick.height
                ? (parent.height - height) * (dayFlick.contentY / (dayFlick.contentHeight - dayFlick.height)) : 0
              width: parent.width
              height: Math.max(Style.space(16), parent.height * dayFlick.height / dayFlick.contentHeight)
              radius: width / 2
              color: popup.bar.foreground
              opacity: 0.75
            }
          }
        }
      }

      // ---- last-updated freshness readout (ticks every second).
      Text {
        Layout.fillWidth: true
        visible: root.spend.generatedAt > 0
        text: "since " + Model.timeAgo(root.spend.generatedAt, root.updatedNow / 1000)
        color: Qt.darker(popup.bar.foreground, 1.6)
        font.family: popup.bar.fontFamily
        font.pixelSize: Style.font.bodySmall
        font.italic: true
        horizontalAlignment: Text.AlignHCenter
        topPadding: Style.space(2)
      }
    }
  }

  visible: true
  implicitWidth: pill.implicitWidth
  implicitHeight: pill.implicitHeight
}
