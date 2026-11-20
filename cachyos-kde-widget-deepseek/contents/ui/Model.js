// Display and parsing helpers for the DeepSeek balance widget, kept Qt-free so
// they can be unit tested under node. BalanceBackend.js does the HTTP call;
// this file turns the endpoint's string amounts into display strings.

function finiteNumber(value) {
  var n = Number(value)
  return isFinite(n) ? n : 0
}

function emptyBalance() {
  return { available: false, items: [], fetchedAt: 0 }
}

function currencySymbol(code) {
  switch (String(code || "").toUpperCase()) {
  case "USD": return "$"
  case "CNY":
  case "RMB": return "\u00A5"
  case "EUR": return "\u20AC"
  case "GBP": return "\u00A3"
  default: return ""
  }
}

// "$14.50" / "\u00A514.50" / "14.50 AUD". Always two decimals: a wallet balance
// that reads "$0" while holding four cents is a lie. Thousands get separators.
function formatMoney(value, code) {
  var n = finiteNumber(value)
  var v = Math.abs(n)
  var whole = Math.floor(v + 1e-9)
  var cents = Math.round((v - whole) * 100)
  if (cents === 100) {
    whole += 1
    cents = 0
  }
  var group = String(whole).replace(/\B(?=(\d{3})+(?!\d))/g, ",")
  var frac = cents < 10 ? "0" + cents : String(cents)
  var symbol = currencySymbol(code)
  var body = symbol !== "" ? symbol + group + "." + frac
                         : group + "." + frac + " " + String(code || "").trim()
  return (n < 0 ? "-" : "") + body
}

// Compact form for the panel pill: cents below $100, whole dollars above so the
// pill never pushes the neighbouring applets around.
function barMoney(value, code) {
  var n = finiteNumber(value)
  var v = Math.abs(n)
  if (v >= 10000)
    return formatMoney(Math.round(n / 100) * 100, code)
  if (v >= 100) {
    var rounded = Math.round(v)
    var symbol = currencySymbol(code)
    var out = symbol !== "" ? symbol + String(rounded)
                           : String(rounded) + " " + String(code || "").trim()
    return (n < 0 ? "-" : "") + out
  }
  return formatMoney(n, code)
}

// Accepts the raw JSON string the endpoint returned. Returns null when the body
// is not a balance document at all; unknown or malformed entries are dropped
// rather than crashing the panel.
function parseBalance(raw) {
  var text = String(raw || "").trim()
  if (!text) return null
  var data
  try {
    data = JSON.parse(text)
  } catch (e) {
    return null
  }
  if (!data || typeof data !== "object" || Array.isArray(data)) return null
  if (!data.balance_infos && typeof data.is_available !== "boolean") return null

  var items = []
  var infos = data.balance_infos
  if (infos && typeof infos.length === "number") {
    for (var i = 0; i < infos.length; i++) {
      var info = infos[i]
      if (!info || typeof info !== "object") continue
      var currency = String(info.currency || "").toUpperCase()
      if (currency === "") continue
      items.push({
        currency: currency,
        total: finiteNumber(info.total_balance),
        granted: finiteNumber(info.granted_balance),
        toppedUp: finiteNumber(info.topped_up_balance)
      })
    }
  }

  return {
    available: data.is_available === true,
    items: items,
    fetchedAt: finiteNumber(data.__fetched_at)
  }
}

// The figure shown in the panel: USD when the account reports it (the common
// case), otherwise the first currency the API listed.
function primaryItem(balance) {
  var items = balance && balance.items ? balance.items : []
  if (!items.length) return null
  for (var i = 0; i < items.length; i++) {
    if (items[i].currency === "USD") return items[i]
  }
  return items[0]
}

function pillLabel(balance) {
  var item = primaryItem(balance)
  if (!item) return "\u2014"
  return barMoney(item.total, item.currency)
}

// Topped-up vs granted split for the popup bar. Shares are normalised against
// their own sum, so a drifted total_balance can never make the bar overflow.
function splitShares(item) {
  var topped = item ? finiteNumber(item.toppedUp) : 0
  var granted = item ? finiteNumber(item.granted) : 0
  var sum = topped + granted
  return {
    toppedUp: topped,
    granted: granted,
    sum: sum,
    hasSplit: sum > 0,
    toppedShare: sum > 0 ? topped / sum : 0,
    grantedShare: sum > 0 ? granted / sum : 0
  }
}

function statusText(balance) {
  if (!balance || !balance.items || !balance.items.length) return ""
  return balance.available ? "AVAILABLE" : "UNAVAILABLE"
}

function isLow(balance, threshold) {
  var item = primaryItem(balance)
  if (!item) return false
  var limit = finiteNumber(threshold)
  if (limit <= 0) return false
  return item.total < limit
}

// Keeps the panel pill short when the request failed. The full sentence stays
// in the tooltip and the popup.
function shortError(message) {
  var text = String(message || "")
  if (text === "") return ""
  if (/network failed/i.test(text)) return "offline"
  if (/key rejected|HTTP 401|HTTP 403/i.test(text)) return "key"
  if (/not set/i.test(text)) return "no key"
  var code = text.match(/HTTP (\d{3})/)
  if (code) return code[1]
  return "error"
}

// Humanised freshness, e.g. "4 minutes and 30 seconds ago". `now` and
// `timestamp` are epoch seconds.
function timeAgo(timestamp, now) {
  var diff = Math.max(0, finiteNumber(now) - finiteNumber(timestamp))
  if (diff < 5) return "just now"
  var clean = function(n) { return String(n).replace(/\.\d+$/, "") }
  var parts = []
  if (diff < 60) return clean(diff) + (diff === 1 ? " second ago" : " seconds ago")
  var m = Math.floor(diff / 60)
  var s = Math.floor(diff % 60)
  if (diff < 3600) {
    if (m) parts.push(clean(m) + (m === 1 ? " minute" : " minutes"))
    if (s) parts.push(clean(s) + (s === 1 ? " second" : " seconds"))
    return parts.join(" and ") + " ago"
  }
  var h = Math.floor(diff / 3600)
  var leftoverM = Math.floor((diff % 3600) / 60)
  if (diff < 86400) {
    parts.push(clean(h) + (h === 1 ? " hour" : " hours"))
    if (leftoverM) parts.push(clean(leftoverM) + (leftoverM === 1 ? " minute" : " minutes"))
    return parts.join(" and ") + " ago"
  }
  var d = Math.floor(diff / 86400)
  var leftoverH = Math.floor((diff % 86400) / 3600)
  parts.push(clean(d) + (d === 1 ? " day" : " days"))
  if (leftoverH) parts.push(clean(leftoverH) + (leftoverH === 1 ? " hour" : " hours"))
  return parts.join(" and ") + " ago"
}

if (typeof module !== "undefined") {
  module.exports = {
    emptyBalance: emptyBalance,
    finiteNumber: finiteNumber,
    currencySymbol: currencySymbol,
    formatMoney: formatMoney,
    barMoney: barMoney,
    parseBalance: parseBalance,
    primaryItem: primaryItem,
    pillLabel: pillLabel,
    splitShares: splitShares,
    statusText: statusText,
    isLow: isLow,
    shortError: shortError,
    timeAgo: timeAgo
  }
}
