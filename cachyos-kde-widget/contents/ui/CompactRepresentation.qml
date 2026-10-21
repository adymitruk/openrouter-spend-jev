/*
    Horizontal panel: wallet icon + pill text ($month ($24h, $1h)).
    Vertical panel: icon only (panel thickness is too narrow for three figures).
*/

import QtQuick 2.15
import QtQuick.Layouts 1.15

import org.kde.plasma.core 2.0 as PlasmaCore
import org.kde.plasma.plasmoid 2.0
import org.kde.plasma.components 3.0 as PlasmaComponents
import org.kde.kirigami 2.20 as Kirigami

Item {
    id: root

    // The applet root item (a plain Item on Plasma 5, a PlasmoidItem on Plasma 6).
    property var plasmoidItem

    readonly property bool horizontalPanel: Plasmoid.formFactor === PlasmaCore.Types.Horizontal
    readonly property int sidePadding: Kirigami.Units.smallSpacing * 2
    readonly property int iconSide: Kirigami.Units.iconSizes.smallMedium
    readonly property url panelIcon: Qt.resolvedUrl("../icons/openrouter-spend.svg")

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
            source: panelIcon
            isMask: false
            active: mouseArea.containsMouse
        }

        PlasmaComponents.Label {
            id: pillText
            visible: root.horizontalPanel
            Layout.alignment: Qt.AlignVCenter
            text: {
                if (root.plasmoidItem && root.plasmoidItem.lastError !== "")
                    return root.plasmoidItem.lastError
                return root.plasmoidItem ? root.plasmoidItem.pillText : ""
            }
            font.bold: root.plasmoidItem ? root.plasmoidItem.spend.monthTotal > 0 : false
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
    Accessible.description: Plasmoid.toolTipSubText ? Plasmoid.toolTipSubText : ""
    Accessible.role: Accessible.Button

    MouseArea {
        id: mouseArea
        anchors.fill: parent
        hoverEnabled: true
        property bool wasExpanded: false
        onPressed: wasExpanded = Plasmoid.expanded
        onClicked: mouse => {
            // Plasma 5 has no Plasmoid.secondaryActivated(); middle click just
            // activates like a left click instead.
            Plasmoid.expanded = !wasExpanded
        }
    }
}
