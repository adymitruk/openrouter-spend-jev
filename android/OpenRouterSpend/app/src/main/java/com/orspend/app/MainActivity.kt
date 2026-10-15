package com.orspend.app

import android.app.Activity
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.text.InputType
import android.text.method.PasswordTransformationMethod
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.io.InputStreamReader
import java.io.OutputStreamWriter
import java.net.URI
import java.text.NumberFormat
import java.time.Instant
import java.time.ZoneId
import java.util.Locale
import javax.net.ssl.HttpsURLConnection

/**
 * OpenRouter Spend Tracker
 *
 * Shows current-month OpenRouter spend in a pinned (non-dismissible)
 * notification. Set your management key (sk-or-...) in the app.
 * No data is hardcoded or committed.
 */
class MainActivity : Activity() {

    private lateinit var prefs: SharedPreferences
    private val nf = NumberFormat.getCurrencyInstance(Locale.US)
    private val handlers = Handler(Looper.getMainLooper())

    private lateinit var keyInput: EditText
    private lateinit var statusText: TextView
    private lateinit var monthVal: TextView
    private lateinit var dayVal: TextView
    private lateinit var updatedText: TextView
    private lateinit var fetchBtn: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        prefs = getSharedPreferences("orspend", Context.MODE_PRIVATE)

        if (Build.VERSION.SDK_INT >= 33) {
            requestPermissions(arrayOf("android.permission.POST_NOTIFICATIONS"), 100)
        }

        setContentView(buildUi())

        val saved = prefs.getString("api_key", "") ?: ""
        keyInput.setText(saved)
    }

    private fun buildUi(): View {
        val scroll = ScrollView(this)
        scroll.setPadding(16, 16, 16, 16)

        val root = LinearLayout(this)
        root.orientation = LinearLayout.VERTICAL
        root.layoutParams = ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        )

        // --- Settings ---
        val settingsCard = card()
        settingsCard.addView(label("Settings", 18f, true))

        keyInput = EditText(this)
        keyInput.hint = "sk-or-..."
        keyInput.inputType = InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD
        keyInput.transformationMethod = PasswordTransformationMethod.getInstance()
        settingsCard.addView(keyInput)

        val showBtn = Button(this)
        showBtn.text = "Show Key"
        showBtn.setOnClickListener {
            if (keyInput.transformationMethod != null) {
                keyInput.transformationMethod = null
                showBtn.text = "Hide Key"
            } else {
                keyInput.transformationMethod = PasswordTransformationMethod.getInstance()
                showBtn.text = "Show Key"
            }
        }
        settingsCard.addView(showBtn)
        settingsCard.addView(smallLabel("Get your key at openrouter.ai/keys"))
        root.addView(settingsCard)

        // --- Tracking toggle ---
        val trackCard = card()
        val trackRow = LinearLayout(this)
        trackRow.layoutParams = ViewGroup.LayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        )
        trackRow.orientation = LinearLayout.HORIZONTAL

        val trackLabel = LinearLayout(this)
        trackLabel.layoutParams = LinearLayout.LayoutParams(
            0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f
        )
        trackLabel.orientation = LinearLayout.VERTICAL
        trackLabel.addView(label("Pinned Notification", 16f, true))
        trackLabel.addView(smallLabel("Shows current-month spend"))

        val trackingSwitch = Switch(this)
        trackingSwitch.isChecked = false
        trackingSwitch.setOnCheckedChangeListener { _, isChecked ->
            if (!isChecked) {
                stopService(Intent(this, SpendService::class.java))
                return@setOnCheckedChangeListener
            }
            val key = keyInput.text.toString().trim()
            if (key.isEmpty()) {
                Toast.makeText(this, "Enter your API key first!", Toast.LENGTH_SHORT).show()
                trackingSwitch.isChecked = false
                return@setOnCheckedChangeListener
            }
            prefs.edit().putString("api_key", key).apply()
            startPinnedService(key)
        }

        trackRow.addView(trackLabel)
        trackRow.addView(trackingSwitch)
        trackCard.addView(trackRow)
        root.addView(trackCard)

        // --- Status ---
        statusText = TextView(this)
        statusText.visibility = View.GONE
        root.addView(statusText)

        // --- Spend display ---
        val spendCard = card()
        spendCard.addView(label("Month-to-Date Spend", 14f, false))

        monthVal = TextView(this)
        monthVal.text = "$0.00"
        monthVal.textSize = 28f
        spendCard.addView(monthVal)

        dayVal = TextView(this)
        dayVal.textSize = 18f
        dayVal.text = "$0.00"

        updatedText = TextView(this)
        updatedText.text = "—"

        val infoRow = LinearLayout(this)
        infoRow.orientation = LinearLayout.HORIZONTAL

        val col1 = LinearLayout(this)
        col1.orientation = LinearLayout.VERTICAL
        col1.layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        col1.addView(smallLabel("Today"))
        col1.addView(dayVal)

        val col2 = LinearLayout(this)
        col2.orientation = LinearLayout.VERTICAL
        col2.layoutParams = LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f)
        col2.addView(smallLabel("Updated"))
        col2.addView(updatedText)

        infoRow.addView(col1)
        infoRow.addView(col2)
        spendCard.addView(infoRow)
        root.addView(spendCard)

        // --- Fetch button ---
        fetchBtn = Button(this)
        fetchBtn.text = "Fetch Now"
        fetchBtn.setOnClickListener {
            val key = keyInput.text.toString().trim()
            if (key.isEmpty()) {
                Toast.makeText(this, "Enter API key first", Toast.LENGTH_SHORT).show()
                return@setOnClickListener
            }
            fetchBtn.isEnabled = false
            fetchBtn.text = "Fetching..."
            fetchSpend(key)
        }
        root.addView(fetchBtn)

        scroll.addView(root)
        return scroll
    }

    private fun card(): LinearLayout {
        val c = LinearLayout(this)
        c.orientation = LinearLayout.VERTICAL
        c.setPadding(20, 20, 20, 20)
        c.setBackgroundColor(0xFFF5F5F5.toInt())
        val m = ViewGroup.MarginLayoutParams(
            ViewGroup.LayoutParams.MATCH_PARENT,
            ViewGroup.LayoutParams.WRAP_CONTENT
        )
        m.bottomMargin = 16
        c.layoutParams = m
        return c
    }

    private fun label(text: String, size: Float, bold: Boolean): TextView {
        val tv = TextView(this)
        tv.text = text
        tv.textSize = size
        tv.setTypeface(null, if (bold) android.graphics.Typeface.BOLD else android.graphics.Typeface.NORMAL)
        return tv
    }

    private fun smallLabel(text: String): TextView {
        val tv = TextView(this)
        tv.text = text
        tv.textSize = 12f
        return tv
    }

    private fun fetchSpend(key: String) {
        Thread {
            try {
                val now = Instant.now()
                val zdt = now.atZone(ZoneId.systemDefault())
                val monthStart = zdt.toLocalDate().withDayOfMonth(1)
                    .atStartOfDay(ZoneId.systemDefault()).toInstant()

                val q = JSONObject()
                val metrics = JSONArray()
                metrics.put("total_usage")
                q.put("metrics", metrics)
                q.put("dimensions", JSONArray())
                q.put("granularity", "day")
                q.put("limit", 35)
                val tr = JSONObject()
                tr.put("start", monthStart.toString().substring(0, 19) + "Z")
                tr.put("end", now.toString().substring(0, 19) + "Z")
                q.put("time_range", tr)

                val url = URI("https://openrouter.ai/api/v1/analytics/query").toURL()
                val conn = url.openConnection() as HttpsURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Authorization", "Bearer $key")
                conn.setRequestProperty("Content-Type", "application/json")
                conn.doOutput = true
                conn.connectTimeout = 15000
                conn.readTimeout = 30000

                val wr = OutputStreamWriter(conn.outputStream)
                wr.write(q.toString())
                wr.flush()
                wr.close()

                val code = conn.responseCode
                if (code != 200) {
                    val errReader = BufferedReader(InputStreamReader(conn.errorStream))
                    val errBody = errReader.readText()
                    errReader.close()
                    handlers.post {
                        statusText.visibility = View.VISIBLE
                        statusText.text = "API error $code"
                        fetchBtn.isEnabled = true
                        fetchBtn.text = "Fetch Now"
                    }
                    return@Thread
                }

                val reader = BufferedReader(InputStreamReader(conn.inputStream))
                val body = reader.readText()
                reader.close()

                val json = JSONObject(body)
                val data = json.optJSONObject("data")
                val rows = data?.optJSONArray("data")

                var monthTotal = 0.0
                var dayTotal = 0.0
                val today = zdt.toLocalDate().toString()

                if (rows != null) {
                    for (i in 0 until rows.length()) {
                        val row = rows.optJSONObject(i) ?: continue
                        val c = row.optDouble("total_usage", 0.0)
                        monthTotal += c
                        if (row.optString("date__day", "") == today) dayTotal += c
                    }
                }

                val fetchTime = zdt.toLocalTime().toString().substring(0, 5)
                val monthLabel = "${zdt.monthValue}/${zdt.year}"

                handlers.post {
                    statusText.visibility = View.GONE
                    monthVal.text = nf.format(monthTotal)
                    dayVal.text = nf.format(dayTotal)
                    updatedText.text = fetchTime
                    fetchBtn.isEnabled = true
                    fetchBtn.text = "Fetch Now"
                }

                updatePinnedNotification(monthTotal, dayTotal, monthLabel)

            } catch (e: Exception) {
                handlers.post {
                    statusText.visibility = View.VISIBLE
                    statusText.text = "Error: ${e.message}"
                    fetchBtn.isEnabled = true
                    fetchBtn.text = "Fetch Now"
                }
            }
        }.start()
    }

    private fun startPinnedService(key: String) {
        fetchBtn.performClick()
        val si = Intent(this, SpendService::class.java)
        si.action = "start"
        si.putExtra("api_key", key)
        if (Build.VERSION.SDK_INT >= 28) {
            startForegroundService(si)
        } else {
            startService(si)
        }
    }

    private fun updatePinnedNotification(monthTotal: Double, dayTotal: Double, monthLabel: String) {
        val si = Intent(this, SpendService::class.java)
        si.action = "update"
        si.putExtra("month_total", monthTotal)
        si.putExtra("day_total", dayTotal)
        si.putExtra("month_label", monthLabel)
        startService(si)
    }
}

// ============================================================================
// Foreground Service — Pure AOSP APIs only
// ============================================================================

class SpendService : Service() {

    companion object {
        const val CHANNEL_ID = "orspend_pinned"
        const val CHANNEL_NAME = "OR Spend Tracker"
        const val NOTIFICATION_ID = 2001
    }

    private var started = false

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            "start" -> {
                val key = intent.getStringExtra("api_key") ?: return START_NOT_STICKY
                showNotification(0.0, 0.0, "—", true)
                doFetch(this, key)
            }

            "update" -> {
                val monthTotal = intent.getDoubleExtra("month_total", 0.0)
                val dayTotal = intent.getDoubleExtra("day_total", 0.0)
                val monthLabel = intent.getStringExtra("month_label") ?: "—"
                showNotification(monthTotal, dayTotal, monthLabel, false)
            }

            "stop" -> {
                started = false
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= 28) {
            val ch = NotificationChannel(
                CHANNEL_ID, CHANNEL_NAME, NotificationManager.IMPORTANCE_LOW
            )
            ch.setShowBadge(false)
            ch.enableVibration(false)
            ch.setSound(null, null)
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm.createNotificationChannel(ch)
        }
    }

    private fun showNotification(
        monthTotal: Double, dayTotal: Double, monthLabel: String, isFirst: Boolean
    ) {
        val nf = NumberFormat.getCurrencyInstance(Locale.US)
        val monthStr = nf.format(monthTotal)
        val dayStr = nf.format(dayTotal)

        val launchIntent = Intent(this, MainActivity::class.java)
        launchIntent.flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        val pi = PendingIntent.getActivity(
            this, 0, launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val builder = if (Build.VERSION.SDK_INT >= 28) {
            Notification.Builder(this, CHANNEL_ID)
        } else {
            Notification.Builder(this)
        }

        val notification = builder
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("OR Spend: $monthStr")
            .setContentText("$monthLabel  •  $dayStr today")
            .setContentIntent(pi)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setCategory(Notification.CATEGORY_SERVICE)
            .setVisibility(Notification.VISIBILITY_PUBLIC)
            .build()

        if (!started) {
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(
                    NOTIFICATION_ID, notification,
                    android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
                )
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
            started = true
        } else {
            val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            nm.notify(NOTIFICATION_ID, notification)
        }
    }

    private fun doFetch(context: Context, key: String) {
        Thread {
            try {
                val now = Instant.now()
                val zdt = now.atZone(ZoneId.systemDefault())
                val monthStart = zdt.toLocalDate().withDayOfMonth(1)
                    .atStartOfDay(ZoneId.systemDefault()).toInstant()

                val q = JSONObject()
                val metrics = JSONArray()
                metrics.put("total_usage")
                q.put("metrics", metrics)
                q.put("dimensions", JSONArray())
                q.put("granularity", "day")
                q.put("limit", 35)
                val tr = JSONObject()
                tr.put("start", monthStart.toString().substring(0, 19) + "Z")
                tr.put("end", now.toString().substring(0, 19) + "Z")
                q.put("time_range", tr)

                val url = URI("https://openrouter.ai/api/v1/analytics/query").toURL()
                val conn = url.openConnection() as HttpsURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Authorization", "Bearer $key")
                conn.setRequestProperty("Content-Type", "application/json")
                conn.doOutput = true
                conn.connectTimeout = 15000
                conn.readTimeout = 30000

                val wr = OutputStreamWriter(conn.outputStream)
                wr.write(q.toString())
                wr.flush()
                wr.close()

                if (conn.responseCode != 200) return@Thread

                val reader = BufferedReader(InputStreamReader(conn.inputStream))
                val body = reader.readText()
                reader.close()

                val json = JSONObject(body)
                val data = json.optJSONObject("data")
                val rows = data?.optJSONArray("data")

                var monthTotal = 0.0
                var dayTotal = 0.0
                val today = zdt.toLocalDate().toString()

                if (rows != null) {
                    for (i in 0 until rows.length()) {
                        val row = rows.optJSONObject(i) ?: continue
                        val c = row.optDouble("total_usage", 0.0)
                        monthTotal += c
                        if (row.optString("date__day", "") == today) dayTotal += c
                    }
                }

                showNotification(
                    monthTotal, dayTotal, "${zdt.monthValue}/${zdt.year}", false
                )
            } catch (_: Exception) { }
        }.start()
    }
}