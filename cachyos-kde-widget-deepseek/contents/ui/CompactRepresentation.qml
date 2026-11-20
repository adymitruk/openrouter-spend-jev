/*
    Panel: colour DeepSeek mark + the current balance ("$14.50").
    Vertical panel: icon only (no room for a figure next to it).
*/
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Layouts

import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.kirigami as Kirigami

Item {
    id: root

    required property PlasmoidItem plasmoidItem

    readonly property bool horizontalPanel: Plasmoid.formFactor === PlasmaCore.Types.Horizontal
    readonly property int sidePadding: Kirigami.Units.smallSpacing * 2
    readonly property int iconSide: Kirigami.Units.iconSizes.smallMedium
    readonly property url panelIcon: Qt.resolvedUrl("../icons/deepseek-balance.svg")
    readonly property bool problem: plasmoidItem.lastError !== ""
    readonly property bool low: !problem && plasmoidItem.isLow

    implicitWidth: horizontalPanel ? pillRow.implicitWidth + sidePadding * 2 : iconSide
    implicitHeight: Math.max(iconSide, pillText.implicitHeight)

    Layout.minimumWidth: implicitWidth
    Layout.preferredWidth: implicitWidth
    Layout.minimumHeight: {
        switch (Plasmoid.formFactor) {
        case PlasmaCore.Types.Vertical:
            return width
        case PlasmaCore.Types.Horizontal:
            return 0
        default:
            return Kirigami.Units.gridUnit * 3
        }
    }

    RowLayout {
        id: pillRow
        anchors.centerIn: parent
        spacing: Kirigami.Units.smallSpacing

        Kirigami.Icon {
            Layout.preferredWidth: iconSide
            Layout.preferredHeight: iconSide
            Layout.alignment: Qt.AlignVCenter
            source: root.panelIcon
            isMask: false
            active: mouseArea.containsMouse
            opacity: root.problem ? 0.55 : 1
        }

        PlasmaComponents.Label {
            id: pillText
            visible: root.horizontalPanel
            Layout.alignment: Qt.AlignVCenter
            text: plasmoidItem.pillText
            font.bold: true
            color: root.problem ? Kirigami.Theme.negativeTextColor
                 : root.low ? Kirigami.Theme.neutralTextColor
                 : Kirigami.Theme.textColor
            elide: Text.ElideNone
        }
    }

    activeFocusOnTab: true

    Keys.onPressed: event => {
        switch (event.key) {
        case Qt.Key_Space:
        case Qt.Key_Enter:
        case Qt.Key_Return:
        case Qt.Key_Select:
            Plasmoid.activated()
            event.accepted = true
            break
        }
    }

    Accessible.name: Plasmoid.title
    Accessible.description: plasmoidItem.toolTipSubText ?? ""
    Accessible.role: Accessible.Button

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        property bool wasExpanded: false
        onPressed: wasExpanded = plasmoidItem.expanded
        onClicked: mouse => {
            if (mouse.button === Qt.MiddleButton)
                Plasmoid.secondaryActivated()
            else
                plasmoidItem.expanded = !wasExpanded
        }
    }
}
