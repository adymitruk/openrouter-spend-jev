import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    id: page

    property alias cfg_refreshMinutes: refreshSpin.value
    property alias cfg_deepseekKey: keyField.text
    property alias cfg_lowBalanceThreshold: lowSpin.value
    property alias cfg_popupWidth: widthSpin.value

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
            Kirigami.FormData.label: "API key:"
            placeholderText: "sk-..."
        }

        QQC2.SpinBox {
            id: lowSpin
            Kirigami.FormData.label: "Warn below balance:"
            from: 0
            to: 1000
            editable: true
            textFromValue: function(value) { return "$" + value.toFixed(2) }
            valueFromText: function(text) { return parseFloat(String(text).replace(/[^0-9.]/g, "")) || 0 }
        }

        QQC2.SpinBox {
            id: widthSpin
            Kirigami.FormData.label: "Popup width (pixels):"
            from: 320
            to: 1200
            stepSize: 20
            editable: true
        }

        QQC2.Label {
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 26
            wrapMode: Text.WordWrap
            text: "Paste a DeepSeek API key (sk-...). It is stored in this widget's settings and sent to https://api.deepseek.com/user/balance over HTTPS. The balance is cached locally so the panel survives a network drop."
        }
    }
}
