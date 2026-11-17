import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    id: page

    property alias cfg_refreshMinutes: refreshSpin.value
    property alias cfg_openrouterKey: keyField.text

    Kirigami.FormLayout {
        QQC2.SpinBox {
            id: refreshSpin
            Kirigami.FormData.label: "Refresh interval (minutes):"
            from: 1
            to: 120
            editable: true
        }

        Kirigami.PasswordField {
            id: keyField
            Kirigami.FormData.label: "Management key:"
            placeholderText: "sk-or-..."
        }

        QQC2.Label {
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 24
            wrapMode: Text.WordWrap
            text: "Paste an OpenRouter management key (sk-or-...). It is stored in this widget's settings and used for HTTPS requests to OpenRouter."
        }
    }
}
