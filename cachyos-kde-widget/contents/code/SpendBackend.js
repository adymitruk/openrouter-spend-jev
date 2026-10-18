.pragma library

var ANALYTICS_URL = "https://openrouter.ai/api/v1/analytics/query"
var ANALYTICS_ROW_LIMIT = 10000
var MAX_RESPONSE = 8 * 1024 * 1024

function pad2(n) {
    return (n < 10 ? "0" : "") + n
}

function localDateString(d) {
    return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate())
}

function utcStamp(d) {
    var x = new Date(d.getTime())
    x.setUTCSeconds(0, 0)
    return x.toISOString().replace(/\.\d{3}Z$/, "Z")
}

function parseUtcDt(s) {
    var text = String(s || "").trim()
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/.test(text))
        text = text.replace(" ", "T") + "Z"
    else if (text.indexOf("T") >= 0 && text.indexOf("Z") < 0 && text.indexOf("+") < 0)
        text = text + "Z"
    var d = new Date(text)
    return isNaN(d.getTime()) ? new Date() : d
}

function asFloat(value) {
    var n = Number(value)
    return isFinite(n) ? n : 0
}

function rowValue(row, keys) {
    if (!row || typeof row !== "object")
        return null
    for (var i = 0; i < keys.length; i++) {
        if (keys[i] in row && row[keys[i]] != null)
            return row[keys[i]]
    }
    return null
}

function canonicalModel(slug) {
    var raw = String(slug || "")
    var parts = raw.split("/")
    if (parts.length >= 2) {
        var name = parts[parts.length - 1].replace(/-\d{8}$/, "")
        return parts.slice(0, -1).join("/") + "/" + name
    }
    return raw.replace(/-\d{8}$/, "")
}

function splitMid(start, end, bucketMs) {
    if (end.getTime() <= start.getTime())
        return null
    var midMs = start.getTime() + (end.getTime() - start.getTime()) / 2
    var snapped = Math.floor(midMs / bucketMs) * bucketMs
    var mid = new Date(snapped)
    if (mid.getTime() <= start.getTime())
        mid = new Date(start.getTime() + bucketMs)
    if (mid.getTime() >= end.getTime())
        return null
    return mid
}

function datesCovering(startUtc, endUtc) {
    var out = {}
    if (endUtc.getTime() <= startUtc.getTime())
        return out
    var cur = new Date(startUtc.getTime())
    cur.setHours(0, 0, 0, 0)
    var last = new Date(endUtc.getTime() - 1)
    while (cur <= last) {
        out[localDateString(cur)] = true
        cur = new Date(cur.getFullYear(), cur.getMonth(), cur.getDate() + 1)
    }
    return out
}

function postAnalytics(apiKey, payload, done) {
    var xhr = new XMLHttpRequest()
    xhr.onreadystatechange = function() {
        if (xhr.readyState !== XMLHttpRequest.DONE)
            return
        if (xhr.status !== 200) {
            if (xhr.status === 0)
                done("OpenRouter network failed (check connection)")
            else
                done("OpenRouter HTTP " + xhr.status)
            return
        }
        var body = xhr.responseText ? xhr.responseText.toString() : ""
        if (body.length > MAX_RESPONSE) {
            done("OpenRouter response too large")
            return
        }
        try {
            var wrapped = JSON.parse(body)
            if (wrapped && wrapped.error) {
                done("OpenRouter API error")
                return
            }
            var data = wrapped && wrapped.data ? wrapped.data : {}
            var rows = data.data
            if (!rows || typeof rows.length !== "number") {
                done("OpenRouter invalid response")
                return
            }
            var meta = data.metadata && typeof data.metadata === "object" ? data.metadata : {}
            var truncated = !!meta.truncated
            var limit = payload.limit
            if (typeof limit === "number" && rows.length >= limit)
                truncated = true
            done(null, { rows: rows, truncated: truncated })
        } catch (e) {
            done("OpenRouter invalid JSON")
        }
    }
    xhr.open("POST", ANALYTICS_URL)
    xhr.setRequestHeader("Authorization", "Bearer " + apiKey)
    xhr.setRequestHeader("Content-Type", "application/json")
    xhr.send(JSON.stringify(payload))
}

function fetchAnalyticsRange(apiKey, template, start, end, minSpanMs, done) {
    if (end.getTime() <= start.getTime()) {
        done(null, [], [])
        return
    }
    var payload = {
        metrics: template.metrics,
        dimensions: template.dimensions,
        granularity: template.granularity,
        limit: ANALYTICS_ROW_LIMIT,
        time_range: { start: utcStamp(start), end: utcStamp(end) }
    }
    postAnalytics(apiKey, payload, function(err, result) {
        if (err) {
            done(err)
            return
        }
        if (!result) {
            done("OpenRouter request failed")
            return
        }
        if (!result.truncated) {
            done(null, result.rows, [])
            return
        }
        if (end.getTime() - start.getTime() <= minSpanMs) {
            done(null, [], [[start, end]])
            return
        }
        var mid = splitMid(start, end, minSpanMs)
        if (!mid) {
            done(null, [], [[start, end]])
            return
        }
        fetchAnalyticsRange(apiKey, template, start, mid, minSpanMs, function(errLeft, leftRows, leftInc) {
            if (errLeft) {
                done(errLeft)
                return
            }
            fetchAnalyticsRange(apiKey, template, mid, end, minSpanMs, function(errRight, rightRows, rightInc) {
                if (errRight) {
                    done(errRight)
                    return
                }
                done(null, leftRows.concat(rightRows), leftInc.concat(rightInc))
            })
        })
    })
}

function fetchWindowChunks(apiKey, template, windowStart, windowEnd, minSpanMs, done) {
    var allRows = []
    var incompleteDates = {}
    var chunkStart = new Date(windowStart.getTime())

    function nextChunk() {
        if (chunkStart.getTime() >= windowEnd.getTime()) {
            done(null, allRows, incompleteDates)
            return
        }
        var chunkEnd = new Date(Math.min(chunkStart.getTime() + 7 * 86400000, windowEnd.getTime()))
        fetchAnalyticsRange(apiKey, template, chunkStart, chunkEnd, minSpanMs, function(err, rows, incomplete) {
            if (err) {
                done(err)
                return
            }
            for (var i = 0; i < rows.length; i++)
                allRows.push(rows[i])
            for (var j = 0; j < incomplete.length; j++) {
                var span = incomplete[j]
                var covered = datesCovering(span[0], span[1])
                for (var k in covered)
                    incompleteDates[k] = true
            }
            chunkStart = chunkEnd
            nextChunk()
        })
    }
    nextChunk()
}

function buildSpendPayload(dailyTuples, hourTuples, slotTuples) {
    var nowLocal = new Date()
    var todayLocal = localDateString(nowLocal)
    var monthStart = new Date(nowLocal.getFullYear(), nowLocal.getMonth(), 1)
    var monthThreshold = localDateString(monthStart)
    var monthKey = monthStart.getFullYear() + "-" + pad2(monthStart.getMonth() + 1)

    if (!dailyTuples.length && !hourTuples.length && !slotTuples.length) {
        return JSON.stringify({
            month: monthKey,
            month_total: 0,
            last24h: 0,
            generated_at: Math.floor(nowLocal.getTime() / 1000),
            days: [],
            models: [],
            series: [],
            lastHour: [],
            todaySlots: []
        })
    }

    var daysByDate = {}
    var modelTotals = {}
    for (var i = 0; i < dailyTuples.length; i++) {
        var drow = dailyTuples[i]
        daysByDate[drow.date] = (daysByDate[drow.date] || 0) + drow.cost
        if (drow.date >= monthThreshold)
            modelTotals[drow.model] = (modelTotals[drow.model] || 0) + drow.cost
    }
    var days = []
    for (var dateKey in daysByDate)
        days.push({ date: dateKey, total: Math.round(daysByDate[dateKey] * 1e6) / 1e6 })
    days.sort(function(a, b) { return a.date < b.date ? 1 : a.date > b.date ? -1 : 0 })

    var monthTotal = 0
    for (var dk in daysByDate) {
        if (dk >= monthThreshold)
            monthTotal += daysByDate[dk]
    }
    monthTotal = Math.round(monthTotal * 1e6) / 1e6

    var models = []
    for (var mk in modelTotals) {
        if (modelTotals[mk] > 0)
            models.push({ model: mk, total: Math.round(modelTotals[mk] * 1e6) / 1e6 })
    }
    models.sort(function(a, b) { return b.total - a.total })

    var start30 = new Date(nowLocal.getFullYear(), nowLocal.getMonth(), nowLocal.getDate() - 29)
    var seriesByDate = {}
    for (var si = 0; si < dailyTuples.length; si++) {
        var srow = dailyTuples[si]
        var parts = srow.date.split("-")
        if (parts.length < 3)
            continue
        var dayDate = new Date(parseInt(parts[0], 10), parseInt(parts[1], 10) - 1, parseInt(parts[2], 10))
        if (dayDate < start30 || dayDate > nowLocal)
            continue
        if (!seriesByDate[srow.date])
            seriesByDate[srow.date] = {}
        seriesByDate[srow.date][srow.model] = (seriesByDate[srow.date][srow.model] || 0) + srow.cost
    }
    var series = []
    for (var dayIdx = 0; dayIdx < 30; dayIdx++) {
        var d = new Date(start30.getFullYear(), start30.getMonth(), start30.getDate() + dayIdx)
        var ds = localDateString(d)
        var dayModels = seriesByDate[ds] || {}
        var segs = []
        for (var sm in dayModels) {
            if (dayModels[sm] > 0)
                segs.push({ model: sm, total: Math.round(dayModels[sm] * 1e6) / 1e6 })
        }
        segs.sort(function(a, b) { return b.total - a.total })
        var daySum = 0
        for (var ss = 0; ss < segs.length; ss++)
            daySum += segs[ss].total
        series.push({ date: ds, total: Math.round(daySum * 1e6) / 1e6, models: segs })
    }

    var cutoff24 = new Date(nowLocal.getTime() - 24 * 3600000)
    var last24 = 0
    if (hourTuples.length) {
        for (var hi = 0; hi < hourTuples.length; hi++) {
            var hrow = hourTuples[hi]
            var start = new Date(hrow.date + "T" + hrow.hour + ":00:00")
            if (isNaN(start.getTime()))
                continue
            var end = new Date(start.getTime() + 3600000)
            if (end > cutoff24 && start <= nowLocal)
                last24 += hrow.cost
        }
    } else {
        for (var di = 0; di < dailyTuples.length; di++) {
            if (dailyTuples[di].date === todayLocal)
                last24 += dailyTuples[di].cost
        }
    }
    last24 = Math.round(last24 * 1e6) / 1e6

    var windowStart = new Date(nowLocal.getTime() - 60 * 60000)
    var minute = Math.floor(windowStart.getMinutes() / 5) * 5
    var boundary = new Date(windowStart.getFullYear(), windowStart.getMonth(), windowStart.getDate(),
                            windowStart.getHours(), minute, 0, 0)
    var bySlot = {}
    for (var sl = 0; sl < slotTuples.length; sl++) {
        var slotRow = slotTuples[sl]
        var slotDt = new Date(slotRow.date + "T" + slotRow.slot + ":00")
        if (isNaN(slotDt.getTime()) || slotDt < boundary || slotDt > nowLocal)
            continue
        var sk = slotRow.date + "\0" + slotRow.slot
        if (!bySlot[sk])
            bySlot[sk] = {}
        bySlot[sk][slotRow.model] = (bySlot[sk][slotRow.model] || 0) + slotRow.cost
    }
    var lastHour = []
    var slotDtIter = new Date(boundary.getTime())
    while (slotDtIter <= nowLocal && lastHour.length < 13) {
        var dateStr = localDateString(slotDtIter)
        var slotKey = pad2(slotDtIter.getHours()) + ":" + pad2(slotDtIter.getMinutes())
        var modelsMap = bySlot[dateStr + "\0" + slotKey] || {}
        var hourSegs = []
        var hourSum = 0
        for (var hm in modelsMap) {
            if (modelsMap[hm] > 0) {
                hourSegs.push({ model: hm, total: Math.round(modelsMap[hm] * 1e6) / 1e6 })
                hourSum += modelsMap[hm]
            }
        }
        hourSegs.sort(function(a, b) { return b.total - a.total })
        lastHour.push({ t: slotKey, total: Math.round(hourSum * 1e6) / 1e6, models: hourSegs })
        slotDtIter = new Date(slotDtIter.getTime() + 5 * 60000)
    }

    var dayMidnight = new Date(nowLocal.getFullYear(), nowLocal.getMonth(), nowLocal.getDate())
    var elapsedMins = Math.floor((nowLocal - dayMidnight) / 60000)
    var nSlots = Math.max(1, Math.floor(elapsedMins / 5) + 1)
    var todaySlots = []
    for (var ti = 0; ti < nSlots; ti++) {
        var tSlot = new Date(dayMidnight.getTime() + ti * 5 * 60000)
        var tKey = pad2(tSlot.getHours()) + ":" + pad2(tSlot.getMinutes())
        var tMap = {}
        for (var tj = 0; tj < slotTuples.length; tj++) {
            var tr = slotTuples[tj]
            if (tr.date === todayLocal && tr.slot === tKey)
                tMap[tr.model] = (tMap[tr.model] || 0) + tr.cost
        }
        var tSegs = []
        var tSum = 0
        for (var tm in tMap) {
            if (tMap[tm] > 0) {
                tSegs.push({ model: tm, total: Math.round(tMap[tm] * 1e6) / 1e6 })
                tSum += tMap[tm]
            }
        }
        tSegs.sort(function(a, b) { return b.total - a.total })
        todaySlots.push({ t: tKey, total: Math.round(tSum * 1e6) / 1e6, models: tSegs })
    }

    return JSON.stringify({
        month: monthKey,
        month_total: monthTotal,
        last24h: last24,
        generated_at: Math.floor(nowLocal.getTime() / 1000),
        days: days,
        models: models,
        series: series,
        lastHour: lastHour,
        todaySlots: todaySlots
    })
}

function rowsToDailyHour(dailyRows, incompleteDates, nowLocal) {
    var byDateModel = {}
    var recentHours = {}
    var hourCutoff = new Date(nowLocal.getTime() - 26 * 3600000)
    for (var i = 0; i < dailyRows.length; i++) {
        var row = dailyRows[i]
        var ts = rowValue(row, ["date__hour", "created_at__hour", "created_at"])
        var rawModel = rowValue(row, ["model", "model_name"])
        if (!ts || !rawModel)
            continue
        var localDt = parseUtcDt(ts)
        var dateStr = localDateString(localDt)
        if (incompleteDates[dateStr])
            continue
        var can = canonicalModel(rawModel)
        var cost = asFloat(rowValue(row, ["total_usage"]))
        var key = dateStr + "\0" + can
        byDateModel[key] = (byDateModel[key] || 0) + cost
        var hourStart = new Date(localDt.getFullYear(), localDt.getMonth(), localDt.getDate(), localDt.getHours(), 0, 0, 0)
        if (hourStart >= hourCutoff) {
            var hk = pad2(localDt.getHours())
            var hkey = dateStr + "\0" + hk + "\0" + can
            recentHours[hkey] = (recentHours[hkey] || 0) + cost
        }
    }
    var daily = []
    for (var dk in byDateModel) {
        var parts = dk.split("\0")
        daily.push({ date: parts[0], model: parts[1], cost: byDateModel[dk] })
    }
    var hours = []
    for (var rk in recentHours) {
        var hp = rk.split("\0")
        hours.push({ date: hp[0], hour: hp[1], model: hp[2], cost: recentHours[rk] })
    }
    return { daily: daily, hours: hours }
}

function rowsToSlots(minuteRows, nowLocal) {
    var grouped = {}
    var slotCutoff = new Date(nowLocal.getTime() - 70 * 60000)
    for (var i = 0; i < minuteRows.length; i++) {
        var row = minuteRows[i]
        var ts = rowValue(row, ["date__minute", "created_at__minute"])
        var rawModel = rowValue(row, ["model", "model_name"])
        if (!ts || !rawModel)
            continue
        var localDt = parseUtcDt(ts)
        var slotM = Math.floor(localDt.getMinutes() / 5) * 5
        var slotDt = new Date(localDt.getFullYear(), localDt.getMonth(), localDt.getDate(),
                              localDt.getHours(), slotM, 0, 0)
        if (slotDt < slotCutoff)
            continue
        var dateStr = localDateString(slotDt)
        var slotKey = pad2(slotDt.getHours()) + ":" + pad2(slotM)
        var can = canonicalModel(rawModel)
        var key = dateStr + "\0" + slotKey + "\0" + can
        grouped[key] = (grouped[key] || 0) + asFloat(rowValue(row, ["total_usage"]))
    }
    var slots = []
    for (var gk in grouped) {
        var gp = gk.split("\0")
        slots.push({ date: gp[0], slot: gp[1], model: gp[2], cost: grouped[gk] })
    }
    return slots
}

function fetchSpend(apiKey, done) {
    var key = String(apiKey || "").trim()
    if (key.indexOf("sk-or-") !== 0) {
        done("Management key not set")
        return
    }
    var nowLocal = new Date()
    var nowUtc = new Date()
    var windowStart = new Date(nowUtc.getTime() - 30 * 86400000)
    var hourQuery = {
        metrics: ["total_usage"],
        dimensions: ["model"],
        granularity: "hour"
    }
    fetchWindowChunks(apiKey, hourQuery, windowStart, nowUtc, 3600000, function(err, hourRows, incompleteDates) {
        if (err) {
            done(err)
            return
        }
        var dh = rowsToDailyHour(hourRows, incompleteDates, nowLocal)
        var minuteEnd = new Date(nowUtc.getTime())
        var minuteStart = new Date(nowUtc.getTime() - 70 * 60000)
        fetchAnalyticsRange(apiKey, {
            metrics: ["total_usage"],
            dimensions: ["model"],
            granularity: "minute"
        }, minuteStart, minuteEnd, 60000, function(errMin, minuteRows, incompleteMin) {
            if (errMin) {
                done(errMin)
                return
            }
            var slots = incompleteMin.length ? [] : rowsToSlots(minuteRows, nowLocal)
            done(null, buildSpendPayload(dh.daily, dh.hours, slots))
        })
    })
}
