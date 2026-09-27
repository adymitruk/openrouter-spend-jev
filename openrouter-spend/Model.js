// Display formatting for the OpenRouter spend widget, kept Qt-free so it can
// be unit tested under node. The widget does no math on spend — the helper
// script already aggregates; this only shapes strings for the bar and panel.

function parseSpend(raw) {
  try {
    var data = JSON.parse(String(raw || ""))
    if (!data || typeof data !== "object") return null
    return {
      month: String(data.month || ""),
      monthTotal: finiteNumber(data.month_total),
      last24h: finiteNumber(data.last24h),
      generatedAt: finiteNumber(data.generated_at),
      days: Array.isArray(data.days) ? data.days : [],
      models: Array.isArray(data.models) ? data.models : [],
      series: Array.isArray(data.series) ? data.series : [],
      lastHour: Array.isArray(data.lastHour) ? data.lastHour : [],
      todaySlots: Array.isArray(data.todaySlots) ? data.todaySlots : []
    }
  } catch (e) {
    return null
  }
}

function finiteNumber(value) {
  var n = Number(value)
  return isFinite(n) ? n : 0
}

// "$18.29" / "$123" / "$1.2k" / "$1.5M". Cents below $1 are still shown so a
// running tab never reads falsely as zero.
function money(value) {
  var n = finiteNumber(value)
  var neg = n < 0
  var v = Math.abs(n)
  var s
  if (v >= 1e6) s = (v / 1e6).toFixed(2).replace(/\.?0+$/, "") + "M"
  else if (v >= 1e3) s = (v / 1e3).toFixed(1).replace(/\.0$/, "") + "k"
  else if (v >= 100) s = v.toFixed(0)
  else s = v.toFixed(2)
  return (neg ? "-$" : "$") + s
}

// Bar pill label: fewer characters than the panel. Whole dollars above $100,
// cents below, an SI suffix for thousands so the pill stays tiny.
function barLabel(value) {
  var n = finiteNumber(value)
  var neg = n < 0
  var v = Math.abs(n)
  var s
  if (v >= 1e6) s = (v / 1e6).toFixed(2).replace(/\.?0+$/, "") + "M"
  else if (v >= 1e3) s = (v / 1e3).toFixed(1).replace(/\.0$/, "") + "k"
  else s = v >= 100 ? v.toFixed(0) : v.toFixed(2)
  return (neg ? "-$" : "$") + s
}

// Pill label. Shows "$20.00 ($1.00, $0.15)" — month total, last 24h, last hour.
// lastHour is the lastHour array from state (12 x 5-min bars); lastHourTotal
// is computed by summing the bar totals.
function pillLabel(monthTotal, last24, lastHour) {
  var main = barLabel(monthTotal)
  var parts = []
  if (finiteNumber(last24) > 0) parts.push(compactMoney(last24))
  var hourTotal = 0
  var bars = Array.isArray(lastHour) ? lastHour : []
  for (var i = 0; i < bars.length; i++) hourTotal += finiteNumber(bars[i] && bars[i].total)
  if (hourTotal > 0) parts.push(compactMoney(hourTotal))
  if (parts.length === 0) return main
  return main + " (" + parts.join(", ") + ")"
}

// "deepseek/deepseek-v4-flash-20260731" -> "deepseek v4 flash". Drop the
// author prefix and the trailing 8-digit release date so a bar/panel row stays
// short; the full slug is available as a tooltip.
function shortModel(slug) {
  var raw = String(slug || "")
  var slash = raw.lastIndexOf("/")
  var short = slash === -1 ? raw : raw.slice(slash + 1)
  return short.replace(/-\d{8}$/, "").replace(/[-_]+/g, " ").trim() || raw
}

var MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

function dateParts(dateString) {
  var parts = String(dateString || "").split("-")
  if (parts.length < 3) return null
  return { year: parseInt(parts[0], 10), month: parseInt(parts[1], 10) - 1, day: parseInt(parts[2], 10) }
}

// Panel row label for a day. Today is spelled out so the running figure reads
// at a glance; anything else is "27 SEP".
function dayLabel(dateString, todayString) {
  if (String(dateString) === String(todayString)) return "TODAY"
  var p = dateParts(dateString)
  if (!p || p.month < 0 || p.month > 11) return String(dateString || "")
  return p.day + " " + MONTHS[p.month]
}

// Today's local date as "YYYY-MM-DD", matching how the helper emits dates.
function todayDate() {
  var d = new Date()
  var pad = function(n) { return String(n < 10 ? "0" : "") + n }
  return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate())
}

// "2026-09" -> "SEP 2026"
function monthLabel(monthString) {
  var parts = String(monthString || "").split("-")
  var m = parseInt(parts[1], 10) - 1
  if (parts.length < 2 || m < 0 || m > 11) return String(monthString || "").toUpperCase()
  return MONTHS[m] + " " + parts[0]
}

// Highest single-day total, so day rows can size a proportional bar.
function maxDayTotal(spend) {
  var best = 0
  var days = spend && spend.days ? spend.days : []
  for (var i = 0; i < days.length; i++) {
    var t = finiteNumber(days[i] && days[i].total)
    if (t > best) best = t
  }
  return best
}

// Highest single-day total across the whole 30-day series, so each stacked
// bar scales off the same denominator.
function maxSeriesTotal(spend) {
  var best = 0
  var series = spend && spend.series ? spend.series : []
  for (var i = 0; i < series.length; i++) {
    var t = finiteNumber(series[i] && series[i].total)
    if (t > best) best = t
  }
  // Never divide by zero in the chart.
  return best > 0 ? best : 1
}

// Highest single per-minute total in the last-hour series, so the minute bars
// share one scale (guards against dividing by zero).
function maxHourTotal(spend) {
  var best = 0
  var h = spend && spend.lastHour ? spend.lastHour : []
  for (var i = 0; i < h.length; i++) {
    var t = finiteNumber(h[i] && h[i].total)
    if (t > best) best = t
  }
  return best > 0 ? best : 1
}

// Sum across the 30-day series for the chart header ("LAST 30 DAYS · $X").
function sumSeriesTotal(spend) {
  var total = 0
  var series = spend && spend.series ? spend.series : []
  for (var i = 0; i < series.length; i++) {
    total += finiteNumber(series[i] && series[i].total)
  }
  return total
}

// Axis tick for the chart, e.g. "26 SEP". Empty string is used as a spacer so
// the QML axis row can keep even spacing by calling this for every bar.
function seriesTickLabel(dateString) {
  var p = dateParts(dateString)
  if (!p || p.month < 0 || p.month > 11) return ""
  return p.day + " " + MONTHS[p.month].charAt(0)
}

// Stable per-model color for the stacked chart, keyed off the model's position
// in the (spend-descending) monthly model list so the same model is the same
// color across every day. Falls back to a hash of the slug. Palette is
// catppuccin-mocha-ish accents that read on the dark panel.
var PALETTE = [
  "#89b4fa", "#a6e3a1", "#f9e2af", "#f5c2e7",
  "#94e2d5", "#fab387", "#b4befe", "#eba0ac",
  "#74c7ec", "#c6a0f6"
]

function modelIndexin(slug, models) {
  for (var i = 0; i < (models ? models.length : 0); i++) {
    var m = models[i] && (models[i].model || models[i].name)
    if (m === slug) return i
  }
  var h = 0
  var s = String(slug || "")
  for (var k = 0; k < s.length; k++) h = (h * 31 + s.charCodeAt(k)) >>> 0
  return h
}

function colorForModel(slug, models) {
  var idx = modelIndexin(slug, models)
  return PALETTE[((idx % PALETTE.length) + PALETTE.length) % PALETTE.length]
}

// Compact money for the bracketed pill figure (reuses the pill formatter).
function compactMoney(value) {
  return barLabel(value)
}

// Humanised freshness, e.g. "4 minutes and 30 seconds ago". `now` and
// `timestamp` are epoch seconds. Feeds the "since X ago" readout that makes
// the 5-minute refresh visibly alive.
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
    parseSpend: parseSpend,
    finiteNumber: finiteNumber,
    money: money,
    barLabel: barLabel,
    pillLabel: pillLabel,
    shortModel: shortModel,
    dayLabel: dayLabel,
    monthLabel: monthLabel,
    maxDayTotal: maxDayTotal,
    maxSeriesTotal: maxSeriesTotal,
    maxHourTotal: maxHourTotal,
    sumSeriesTotal: sumSeriesTotal,
    seriesTickLabel: seriesTickLabel,
    colorForModel: colorForModel,
    compactMoney: compactMoney,
    timeAgo: timeAgo,
    todayDate: todayDate
  }
}
