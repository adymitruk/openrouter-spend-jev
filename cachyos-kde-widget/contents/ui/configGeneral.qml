import QtQuick 2.15
import QtQuick.Controls 2.15 as QQC2
import QtQuick.Layouts 1.15
import org.kde.kirigami 2.20 as Kirigami

// Plasma 5 config pages use a bare Kirigami.FormLayout as their root; the
// config dialog supplies the scroll container (KCM.SimpleKCM is the Plasma 6
// idiom and collapses when nested inside the KF5 dialog).
Kirigami.FormLayout {
    id: page

    property alias cfg_refreshMinutes: refreshSpin.value
    property alias cfg_openrouterKey: keyField.text

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

    // A definite width keeps the wrapping label from looping the FormLayout's
    // preferredHeight (Layout.fillWidth + wrap does not converge on KF5).
    QQC2.Label {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 24
        wrapMode: Text.WordWrap
        text: "Paste an OpenRouter management key (sk-or-...). It is stored in this widget's settings and used for HTTPS requests to OpenRouter."
    }
}
