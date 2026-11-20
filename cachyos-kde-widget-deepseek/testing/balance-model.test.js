#!/usr/bin/env node
// Run with: node testing/balance-model.test.js
// The widget's formatting and parsing live in Model.js so they can be checked
// without a Plasma session.

const assert = require("assert")
const M = require("../contents/ui/Model.js")

const SAMPLE = JSON.stringify({
  is_available: true,
  balance_infos: [
    { currency: "USD", total_balance: "14.50", granted_balance: "0.00", topped_up_balance: "14.50" }
  ]
})

let failures = 0
function test(name, fn) {
  try {
    fn()
    console.log("ok   " + name)
  } catch (e) {
    failures++
    console.log("FAIL " + name + "\n     " + e.message)
  }
}

test("parses the documented payload", () => {
  const b = M.parseBalance(SAMPLE)
  assert.strictEqual(b.available, true)
  assert.strictEqual(b.items.length, 1)
  assert.deepStrictEqual(b.items[0], { currency: "USD", total: 14.5, granted: 0, toppedUp: 14.5 })
})

test("amounts arrive as strings but leave as numbers", () => {
  const b = M.parseBalance(JSON.stringify({
    is_available: true,
    balance_infos: [{ currency: "CNY", total_balance: "1.10", granted_balance: "0.10", topped_up_balance: "1.00" }]
  }))
  assert.strictEqual(b.items[0].total, 1.1)
  assert.strictEqual(b.items[0].granted, 0.1)
})

test("unavailable accounts keep their figures", () => {
  const b = M.parseBalance(JSON.stringify({
    is_available: false,
    balance_infos: [{ currency: "USD", total_balance: "0.00", granted_balance: "0.00", topped_up_balance: "0.00" }]
  }))
  assert.strictEqual(b.available, false)
  assert.strictEqual(M.statusText(b), "UNAVAILABLE")
  assert.strictEqual(M.pillLabel(b), "$0.00")
})

test("rejects bodies that are not balances", () => {
  assert.strictEqual(M.parseBalance(""), null)
  assert.strictEqual(M.parseBalance("not json"), null)
  assert.strictEqual(M.parseBalance("[1,2,3]"), null)
  assert.strictEqual(M.parseBalance('{"error":{"message":"bad key"}}'), null)
})

test("drops malformed currency entries instead of crashing", () => {
  const b = M.parseBalance(JSON.stringify({
    is_available: true,
    balance_infos: [null, { total_balance: "5.00" }, { currency: "USD", total_balance: "5.00" }]
  }))
  assert.strictEqual(b.items.length, 1)
  assert.strictEqual(b.items[0].currency, "USD")
})

test("formats money per currency", () => {
  assert.strictEqual(M.formatMoney(14.5, "USD"), "$14.50")
  assert.strictEqual(M.formatMoney(0, "USD"), "$0.00")
  assert.strictEqual(M.formatMoney(1234.5, "USD"), "$1,234.50")
  assert.strictEqual(M.formatMoney(1.1, "CNY"), "\u00A51.10")
  assert.strictEqual(M.formatMoney(7, "AUD"), "7.00 AUD")
  assert.strictEqual(M.formatMoney(-2.5, "USD"), "-$2.50")
})

test("rounds cents without printing $1.00.01", () => {
  assert.strictEqual(M.formatMoney(0.999, "USD"), "$1.00")
  assert.strictEqual(M.formatMoney(0.005, "USD"), "$0.01")
})

test("pill label prefers USD, else the first currency", () => {
  const b = M.parseBalance(JSON.stringify({
    is_available: true,
    balance_infos: [
      { currency: "CNY", total_balance: "99.00", granted_balance: "0", topped_up_balance: "99.00" },
      { currency: "USD", total_balance: "14.50", granted_balance: "0", topped_up_balance: "14.50" }
    ]
  }))
  assert.strictEqual(M.pillLabel(b), "$14.50")
  const cnyOnly = M.parseBalance(JSON.stringify({
    is_available: true,
    balance_infos: [{ currency: "CNY", total_balance: "99.00", granted_balance: "0", topped_up_balance: "99.00" }]
  }))
  assert.strictEqual(M.pillLabel(cnyOnly), "\u00A599.00")
})

test("empty balance renders a dash, not $0.00", () => {
  assert.strictEqual(M.pillLabel(M.emptyBalance()), "\u2014")
  assert.strictEqual(M.pillLabel(null), "\u2014")
  assert.strictEqual(M.statusText(M.emptyBalance()), "")
})

test("split bar normalises topped-up against granted", () => {
  const s = M.splitShares({ toppedUp: 14.5, granted: 0 })
  assert.strictEqual(s.hasSplit, true)
  assert.strictEqual(s.toppedShare, 1)
  assert.strictEqual(s.grantedShare, 0)

  const half = M.splitShares({ toppedUp: 5, granted: 5 })
  assert.strictEqual(half.toppedShare, 0.5)
  assert.strictEqual(half.grantedShare, 0.5)

  const none = M.splitShares({ toppedUp: 0, granted: 0 })
  assert.strictEqual(none.hasSplit, false)
})

test("granted-only credit still paints a bar", () => {
  const s = M.splitShares({ toppedUp: 0, granted: 20 })
  assert.strictEqual(s.hasSplit, true)
  assert.strictEqual(s.grantedShare, 1)
})

test("low balance needs a threshold and a figure", () => {
  const b = M.parseBalance(SAMPLE)
  assert.strictEqual(M.isLow(b, 2), false)
  assert.strictEqual(M.isLow(b, 100), true)
  assert.strictEqual(M.isLow(b, 0), false)
  assert.strictEqual(M.isLow(M.emptyBalance(), 100), false)
})

test("short panel error codes", () => {
  assert.strictEqual(M.shortError("DeepSeek network failed (check connection)"), "offline")
  assert.strictEqual(M.shortError("DeepSeek key rejected (HTTP 401)"), "key")
  assert.strictEqual(M.shortError("API key not set"), "no key")
  assert.strictEqual(M.shortError("DeepSeek HTTP 503"), "503")
  assert.strictEqual(M.shortError("something else"), "error")
  assert.strictEqual(M.shortError(""), "")
})

test("freshness label", () => {
  assert.strictEqual(M.timeAgo(100, 101), "just now")
  assert.strictEqual(M.timeAgo(100, 130), "30 seconds ago")
  assert.strictEqual(M.timeAgo(0, 90), "1 minute and 30 seconds ago")
  assert.strictEqual(M.timeAgo(0, 3600), "1 hour ago")
})

test("missing or garbage fields never produce NaN", () => {
  const b = M.parseBalance(JSON.stringify({
    is_available: true,
    balance_infos: [{ currency: "usd", total_balance: "abc", granted_balance: null, topped_up_balance: undefined }]
  }))
  assert.strictEqual(b.items[0].currency, "USD")
  assert.strictEqual(b.items[0].total, 0)
  assert.strictEqual(M.pillLabel(b), "$0.00")
})

console.log("")
if (failures) {
  console.log(failures + " failing")
  process.exit(1)
}
console.log("all passing")
