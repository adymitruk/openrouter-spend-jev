.pragma library

// DeepSeek exposes a single balance endpoint; no analytics, no per-day history.
// Docs: GET https://api.deepseek.com/user/balance with a Bearer API key.
//   { "is_available": true,
//     "balance_infos": [ { "currency": "USD",
//                          "total_balance": "14.50",
//                          "granted_balance": "0.00",
//                          "topped_up_balance": "14.50" } ] }
// Amounts arrive as strings; everything below the network layer gets numbers.

var BALANCE_URL = "https://api.deepseek.com/user/balance"
var MAX_RESPONSE = 512 * 1024

function requestBalance(apiKey, done) {
    var key = String(apiKey || "").trim()
    if (!key) {
        done("API key not set")
        return
    }
    var xhr = new XMLHttpRequest()
    var settled = false

    function finish(err, body) {
        if (settled)
            return
        settled = true
        done(err, body)
    }

    xhr.onreadystatechange = function() {
        if (xhr.readyState !== XMLHttpRequest.DONE)
            return
        if (xhr.status !== 200) {
            if (xhr.status === 0)
                finish("DeepSeek network failed (check connection)")
            else if (xhr.status === 401 || xhr.status === 403)
                finish("DeepSeek key rejected (HTTP " + xhr.status + ")")
            else
                finish("DeepSeek HTTP " + xhr.status)
            return
        }
        var body = xhr.responseText ? xhr.responseText.toString() : ""
        if (!body) {
            finish("DeepSeek empty response")
            return
        }
        if (body.length > MAX_RESPONSE) {
            finish("DeepSeek response too large")
            return
        }
        try {
            JSON.parse(body)
        } catch (e) {
            finish("DeepSeek invalid JSON")
            return
        }
        finish(null, body)
    }

    xhr.open("GET", BALANCE_URL)
    xhr.setRequestHeader("Accept", "application/json")
    xhr.setRequestHeader("Authorization", "Bearer " + key)
    xhr.send()
}
