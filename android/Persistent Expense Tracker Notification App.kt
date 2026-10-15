/**
 * ============================================================================
 * 1. ANDROID MANIFEST (app/src/main/AndroidManifest.xml)
 * ============================================================================
 * Copy the contents below into your project's AndroidManifest.xml file.
 * Notice the required permissions for Android 13+ (POST_NOTIFICATIONS) and
 * Android 14+ (FOREGROUND_SERVICE_DATA_SYNC or SPECIAL_USE).
 *
 * <?xml version="1.0" encoding="utf-8"?>
 * <manifest xmlns:android="http://schemas.android.com/apk/res/android"
 *     package="com.example.expensetracker">
 *
 *     <!-- Required to run a Foreground Service on Android 9 (API 28) and higher -->
 *     <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
 *
 *     <!-- Required for Android 14 (API 34+) Foreground Service Type -->
 *     <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC" />
 *
 *     <!-- Required for Android 13 (API 33+) to display any notifications -->
 *     <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
 *
 *     <application
 *         android:allowBackup="true"
 *         android:icon="@mipmap/ic_launcher"
 *         android:label="Expense Tracker"
 *         android:roundIcon="@mipmap/ic_launcher_round"
 *         android:supportsRtl="true"
 *         android:theme="@style/Theme.Material3.DayNight.NoActionBar">
 *
 *         <activity
 *             android:name=".MainActivity"
 *             android:exported="true"
 *             android:launchMode="singleTop">
 *             <intent-filter>
 *                 <action android:name="android.intent.action.MAIN" />
 *                 <category android:name="android.intent.category.LAUNCHER" />
 *             </intent-filter>
 *         </activity>
 *
 *         <!-- Foreground Service Declaration -->
 *         <service
 *             android:name=".ExpenseForegroundService"
 *             android:enabled="true"
 *             android:exported="false"
 *             android:foregroundServiceType="dataSync" />
 *     </application>
 * </manifest>
 */

/**
 * ============================================================================
 * 2. CUSTOM NOTIFICATION LAYOUT (app/src/main/res/layout/notification_expense.xml)
 * ============================================================================
 * Create a file named `notification_expense.xml` inside `res/layout/` and paste
 * this XML. Note that RemoteViews only supports a specific subset of ViewGroups
 * (like LinearLayout, RelativeLayout, FrameLayout) and Views (TextView, ImageView).
 *
 * <?xml version="1.0" encoding="utf-8"?>
 * <LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
 *     android:id="@+id/notification_root"
 *     android:layout_width="match_parent"
 *     android:layout_height="wrap_content"
 *     android:orientation="vertical"
 *     android:padding="12dp">
 *
 *     <!-- Header Row -->
 *     <LinearLayout
 *         android:layout_width="match_parent"
 *         android:layout_height="wrap_content"
 *         android:gravity="center_vertical"
 *         android:orientation="horizontal"
 *         android:paddingBottom="8dp">
 *
 *         <TextView
 *             android:id="@+id/tv_notification_title"
 *             style="@style/TextAppearance.Compat.Notification.Title"
 *             android:layout_width="0dp"
 *             android:layout_height="wrap_content"
 *             android:layout_weight="1"
 *             android:text="Live Expense Summary"
 *             android:textSize="13sp"
 *             android:textStyle="bold" />
 *
 *         <TextView
 *             android:id="@+id/tv_notification_badge"
 *             style="@style/TextAppearance.Compat.Notification.Info"
 *             android:layout_width="wrap_content"
 *             android:layout_height="wrap_content"
 *             android:text="PINNED"
 *             android:textSize="10sp"
 *             android:textStyle="bold" />
 *     </LinearLayout>
 *
 *     <!-- 3-Column Expense Breakdown Row -->
 *     <LinearLayout
 *         android:layout_width="match_parent"
 *         android:layout_height="wrap_content"
 *         android:baselineAligned="false"
 *         android:orientation="horizontal"
 *         android:weightSum="3">
 *
 *         <!-- Column 1: Daily -->
 *         <LinearLayout
 *             android:layout_width="0dp"
 *             android:layout_height="wrap_content"
 *             android:layout_weight="1"
 *             android:gravity="start"
 *             android:orientation="vertical">
 *
 *             <TextView
 *                 style="@style/TextAppearance.Compat.Notification.Info"
 *                 android:layout_width="wrap_content"
 *                 android:layout_height="wrap_content"
 *                 android:text="Daily"
 *                 android:textSize="11sp" />
 *
 *             <TextView
 *                 android:id="@+id/tv_daily_val"
 *                 style="@style/TextAppearance.Compat.Notification.Title"
 *                 android:layout_width="wrap_content"
 *                 android:layout_height="wrap_content"
 *                 android:text="Daily: $0.00"
 *                 android:textSize="14sp"
 *                 android:textStyle="bold" />
 *         </LinearLayout>
 *
 *         <!-- Column 2: Weekly -->
 *         <LinearLayout
 *             android:layout_width="0dp"
 *             android:layout_height="wrap_content"
 *             android:layout_weight="1"
 *             android:gravity="center_horizontal"
 *             android:orientation="vertical">
 *
 *             <TextView
 *                 style="@style/TextAppearance.Compat.Notification.Info"
 *                 android:layout_width="wrap_content"
 *                 android:layout_height="wrap_content"
 *                 android:text="Weekly"
 *                 android:textSize="11sp" />
 *
 *             <TextView
 *                 android:id="@+id/tv_weekly_val"
 *                 style="@style/TextAppearance.Compat.Notification.Title"
 *                 android:layout_width="wrap_content"
 *                 android:layout_height="wrap_content"
 *                 android:text="Weekly: $0.00"
 *                 android:textSize="14sp"
 *                 android:textStyle="bold" />
 *         </LinearLayout>
 *
 *         <!-- Column 3: Monthly -->
 *         <LinearLayout
 *             android:layout_width="0dp"
 *             android:layout_height="wrap_content"
 *             android:layout_weight="1"
 *             android:gravity="end"
 *             android:orientation="vertical">
 *
 *             <TextView
 *                 style="@style/TextAppearance.Compat.Notification.Info"
 *                 android:layout_width="wrap_content"
 *                 android:layout_height="wrap_content"
 *                 android:text="Monthly"
 *                 android:textSize="11sp" />
 *
 *             <TextView
 *                 android:id="@+id/tv_monthly_val"
 *                 style="@style/TextAppearance.Compat.Notification.Title"
 *                 android:layout_width="wrap_content"
 *                 android:layout_height="wrap_content"
 *                 android:text="Monthly: $0.00"
 *                 android:textSize="14sp"
 *                 android:textStyle="bold" />
 *         </LinearLayout>
 *     </LinearLayout>
 * </LinearLayout>
 */

package com.example.expensetracker

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.widget.RemoteViews
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableDoubleStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import java.util.Locale

/**
 * ============================================================================
 * 3. MAIN ACTIVITY (MainActivity.kt)
 * ============================================================================
 * Hosts the Jetpack Compose UI, handles runtime permission requests for
 * POST_NOTIFICATIONS (Android 13+), and dispatches updated expense totals via
 * Intents to the ExpenseForegroundService.
 */
class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background
                ) {
                    ExpenseTrackerScreen()
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ExpenseTrackerScreen() {
    val context = LocalContext.current

    // Default stubbed-out expense values
    var dailyTotal by rememberSaveable { mutableDoubleStateOf(42.50) }
    var weeklyTotal by rememberSaveable { mutableDoubleStateOf(285.75) }
    var monthlyTotal by rememberSaveable { mutableDoubleStateOf(1240.00) }

    // Tracking state for the foreground service
    var isTracking by rememberSaveable { mutableStateOf(false) }

    // Permission state for Android 13+ (TIRAMISU) POST_NOTIFICATIONS
    var hasNotificationPermission by remember {
        mutableStateOf(
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                ContextCompat.checkSelfPermission(
                    context,
                    Manifest.permission.POST_NOTIFICATIONS
                ) == PackageManager.PERMISSION_GRANTED
            } else {
                true
            }
        )
    }

    // Status banner message for permission feedback
    var statusMessage by remember { mutableStateOf<String?>(null) }

    // Launcher for requesting POST_NOTIFICATIONS at runtime
    val permissionLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.RequestPermission()
    ) { isGranted ->
        hasNotificationPermission = isGranted
        if (isGranted) {
            statusMessage = null
            isTracking = true
            dispatchExpenseServiceUpdate(context, dailyTotal, weeklyTotal, monthlyTotal)
        } else {
            isTracking = false
            statusMessage = "Notification permission denied. Enable it in System Settings to pin live expenses."
        }
    }

    // Whenever any of the 3 expense values change while tracking is ON, immediately push to the service
    LaunchedEffect(dailyTotal, weeklyTotal, monthlyTotal, isTracking) {
        if (isTracking && hasNotificationPermission) {
            dispatchExpenseServiceUpdate(
                context = context,
                daily = dailyTotal,
                weekly = weeklyTotal,
                monthly = monthlyTotal
            )
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            imageVector = Icons.Default.Notifications,
                            contentDescription = null,
                            modifier = Modifier.padding(end = 8.dp)
                        )
                        Text(
                            text = "Pinned Expense Notifier",
                            fontWeight = FontWeight.Bold
                        )
                    }
                },
                actions = {
                    IconButton(
                        onClick = {
                            dailyTotal = 42.50
                            weeklyTotal = 285.75
                            monthlyTotal = 1240.00
                        }
                    ) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Reset stubbed values"
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    titleContentColor = MaterialTheme.colorScheme.onPrimaryContainer
                )
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // 1. Live Notification Preview Card (mirrors what the user sees in the notification shade)
            LiveNotificationPreviewCard(
                isTracking = isTracking,
                daily = dailyTotal,
                weekly = weeklyTotal,
                monthly = monthlyTotal
            )

            // 2. Start / Stop Tracking Master Switch Card
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                colors = CardDefaults.cardColors(
                    containerColor = if (isTracking) {
                        MaterialTheme.colorScheme.secondaryContainer
                    } else {
                        MaterialTheme.colorScheme.surfaceVariant
                    }
                )
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp, vertical = 16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = if (isTracking) "Tracking Active (Pinned)" else "Start/Stop Tracking",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = if (isTracking) {
                                "Foreground service is pinning your live totals to the notification shade."
                            } else {
                                "Toggle on to pin a non-dismissible expense summary notification."
                            },
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }

                    Spacer(modifier = Modifier.width(12.dp))

                    Switch(
                        checked = isTracking,
                        onCheckedChange = { shouldTrack ->
                            if (shouldTrack) {
                                // Check Android 13+ notification permission first
                                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !hasNotificationPermission) {
                                    permissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                                } else {
                                    isTracking = true
                                    statusMessage = null
                                    dispatchExpenseServiceUpdate(context, dailyTotal, weeklyTotal, monthlyTotal)
                                }
                            } else {
                                isTracking = false
                                stopExpenseService(context)
                            }
                        }
                    )
                }
            }

            // Optional Warning Banner if permission was denied
            AnimatedVisibility(visible = statusMessage != null) {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer
                    ),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Column(modifier = Modifier.padding(16.dp)) {
                        Text(
                            text = statusMessage.orEmpty(),
                            color = MaterialTheme.colorScheme.onErrorContainer,
                            style = MaterialTheme.typography.bodyMedium
                        )
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU && !hasNotificationPermission) {
                            Spacer(modifier = Modifier.height(8.dp))
                            Button(
                                onClick = {
                                    permissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                                }
                            ) {
                                Text("Request Permission Again")
                            }
                        }
                    }
                }
            }

            Text(
                text = "Adjust Expense Totals",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(top = 4.dp)
            )

            // Daily Expense Control
            ExpenseInputControlCard(
                label = "Daily Total",
                value = dailyTotal,
                maxRange = 500f,
                onValueChange = { newDaily -> dailyTotal = newDaily }
            )

            // Weekly Expense Control
            ExpenseInputControlCard(
                label = "Weekly Total",
                value = weeklyTotal,
                maxRange = 2500f,
                onValueChange = { newWeekly -> weeklyTotal = newWeekly }
            )

            // Monthly Expense Control
            ExpenseInputControlCard(
                label = "Monthly Total",
                value = monthlyTotal,
                maxRange = 10000f,
                onValueChange = { newMonthly -> monthlyTotal = newMonthly }
            )
        }
    }
}

/**
 * Mirrors the exact visual layout of `res/layout/notification_expense.xml` inside the app
 * so the user can preview the 3-column RemoteViews notification alongside the system shade.
 */
@Composable
fun LiveNotificationPreviewCard(
    isTracking: Boolean,
    daily: Double,
    weekly: Double,
    monthly: Double
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        elevation = CardDefaults.cardElevation(defaultElevation = 4.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        )
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(8.dp)
                            .clip(CircleShape)
                            .background(
                                if (isTracking) MaterialTheme.colorScheme.primary
                                else MaterialTheme.colorScheme.outline
                            )
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Live Expense Summary (RemoteViews Preview)",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold
                    )
                }

                Text(
                    text = if (isTracking) "ONGOING • PINNED" else "STOPPED",
                    style = MaterialTheme.typography.labelSmall,
                    color = if (isTracking) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                    fontWeight = FontWeight.Bold
                )
            }

            HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp))

            // 3-Column Display matching notification_expense.xml
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    horizontalAlignment = Alignment.Start
                ) {
                    Text(
                        text = "Daily",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = formatCurrencyLabel("Daily", daily),
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Bold
                    )
                }

                Column(
                    modifier = Modifier.weight(1f),
                    horizontalAlignment = Alignment.CenterHorizontally
                ) {
                    Text(
                        text = "Weekly",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = formatCurrencyLabel("Weekly", weekly),
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Bold
                    )
                }

                Column(
                    modifier = Modifier.weight(1f),
                    horizontalAlignment = Alignment.End
                ) {
                    Text(
                        text = "Monthly",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    Text(
                        text = formatCurrencyLabel("Monthly", monthly),
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }
    }
}

/**
 * Reusable card providing both an OutlinedTextField for exact numeric entry
 * and a Slider for smooth real-time scrubbing.
 */
@Composable
fun ExpenseInputControlCard(
    label: String,
    value: Double,
    maxRange: Float,
    onValueChange: (Double) -> Unit
) {
    var textInput by remember(value) {
        mutableStateOf(String.format(Locale.US, "%.2f", value))
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = label,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold
                )
                Text(
                    text = String.format(Locale.US, "$%.2f", value),
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.ExtraBold,
                    fontSize = 18.sp
                )
            }

            Spacer(modifier = Modifier.height(8.dp))

            OutlinedTextField(
                value = textInput,
                onValueChange = { raw ->
                    textInput = raw
                    val parsed = raw.toDoubleOrNull()
                    if (parsed != null && parsed >= 0.0) {
                        onValueChange(parsed)
                    }
                },
                label = { Text("$ Amount") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                modifier = Modifier.fillMaxWidth()
            )

            Spacer(modifier = Modifier.height(8.dp))

            Slider(
                value = value.toFloat().coerceIn(0f, maxRange),
                onValueChange = { sliderVal ->
                    // Round to nearest 0.50 for clean scrubbing
                    val rounded = (Math.round(sliderVal * 2) / 2.0)
                    onValueChange(rounded)
                },
                valueRange = 0f..maxRange,
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}

/**
 * Dispatches an Intent with the updated Daily, Weekly, and Monthly extras to
 * [ExpenseForegroundService]. Uses `startForegroundService` on Android O+.
 */
private fun dispatchExpenseServiceUpdate(
    context: Context,
    daily: Double,
    weekly: Double,
    monthly: Double
) {
    val serviceIntent = Intent(context, ExpenseForegroundService::class.java).apply {
        action = ExpenseForegroundService.ACTION_START_OR_UPDATE
        putExtra(ExpenseForegroundService.EXTRA_DAILY, daily)
        putExtra(ExpenseForegroundService.EXTRA_WEEKLY, weekly)
        putExtra(ExpenseForegroundService.EXTRA_MONTHLY, monthly)
    }
    ContextCompat.startForegroundService(context, serviceIntent)
}

/**
 * Sends a stop action to [ExpenseForegroundService] so it unpins the notification
 * and cleanly stops itself.
 */
private fun stopExpenseService(context: Context) {
    val stopIntent = Intent(context, ExpenseForegroundService::class.java).apply {
        action = ExpenseForegroundService.ACTION_STOP
    }
    context.startService(stopIntent)
}

private fun formatCurrencyLabel(prefix: String, amount: Double): String {
    return String.format(Locale.US, "%s: $%.2f", prefix, amount)
}

/**
 * ============================================================================
 * 4. FOREGROUND SERVICE (ExpenseForegroundService.kt)
 * ============================================================================
 * Manages a persistent, non-dismissible notification with `IMPORTANCE_LOW`,
 * `.setOngoing(true)`, and `.setOnlyAlertOnce(true)`. Updates the custom
 * `RemoteViews` layout whenever new Intent extras arrive in `onStartCommand`.
 */
class ExpenseForegroundService : Service() {

    companion object {
        const val CHANNEL_ID = "expense_tracker_pinned_channel"
        const val CHANNEL_NAME = "Live Expense Tracker"
        const val NOTIFICATION_ID = 1001

        const val ACTION_START_OR_UPDATE = "com.example.expensetracker.ACTION_START_OR_UPDATE"
        const val ACTION_STOP = "com.example.expensetracker.ACTION_STOP"

        const val EXTRA_DAILY = "extra_daily_total"
        const val EXTRA_WEEKLY = "extra_weekly_total"
        const val EXTRA_MONTHLY = "extra_monthly_total"
    }

    private lateinit var notificationManager: NotificationManager
    private var isForegroundStarted = false

    override fun onCreate() {
        super.onCreate()
        notificationManager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        createLowImportanceNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> {
                stopForegroundServiceCleanly()
                return START_NOT_STICKY
            }

            ACTION_START_OR_UPDATE, null -> {
                val daily = intent?.getDoubleExtra(EXTRA_DAILY, 42.50) ?: 42.50
                val weekly = intent?.getDoubleExtra(EXTRA_WEEKLY, 285.75) ?: 285.75
                val monthly = intent?.getDoubleExtra(EXTRA_MONTHLY, 1240.00) ?: 1240.00

                val notification = buildPinnedExpenseNotification(
                    daily = daily,
                    weekly = weekly,
                    monthly = monthly
                )

                if (!isForegroundStarted) {
                    // Promote to foreground with Android 14+ foregroundServiceType support
                    ServiceCompat.startForeground(
                        this,
                        NOTIFICATION_ID,
                        notification,
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
                            ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
                        } else {
                            0
                        }
                    )
                    isForegroundStarted = true
                } else {
                    // Refresh the pinned notification immediately via NotificationManager.notify()
                    notificationManager.notify(NOTIFICATION_ID, notification)
                }
            }
        }

        // If the system kills the service under extreme memory pressure, recreate with last intent
        return START_REDELIVER_INTENT
    }

    override fun onBind(intent: Intent?): IBinder? = null

    /**
     * Creates a persistent notification channel with `IMPORTANCE_LOW` so updates
     * never trigger an audible chime or heads-up popup.
     */
    private fun createLowImportanceNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                CHANNEL_NAME,
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Displays pinned Daily, Weekly, and Monthly expense totals"
                setShowBadge(false)
                enableVibration(false)
                setSound(null, null)
            }
            notificationManager.createNotificationChannel(channel)
        }
    }

    /**
     * Populates `res/layout/notification_expense.xml` using [RemoteViews] and configures
     * the notification as ongoing (non-dismissible) and alert-once.
     */
    private fun buildPinnedExpenseNotification(
        daily: Double,
        weekly: Double,
        monthly: Double
    ): Notification {
        val dailyFormatted = String.format(Locale.US, "Daily: $%.2f", daily)
        val weeklyFormatted = String.format(Locale.US, "Weekly: $%.2f", weekly)
        val monthlyFormatted = String.format(Locale.US, "Monthly: $%.2f", monthly)

        // Tap intent to bring the user back to MainActivity
        val launchIntent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        // Resolve layout and view IDs dynamically so this file compiles cleanly
        // once `res/layout/notification_expense.xml` is placed in the project.
        val layoutId = resources.getIdentifier(
            "notification_expense",
            "layout",
            packageName
        )

        val remoteViews: RemoteViews? = if (layoutId != 0) {
            RemoteViews(packageName, layoutId).apply {
                val dailyId = resources.getIdentifier("tv_daily_val", "id", packageName)
                val weeklyId = resources.getIdentifier("tv_weekly_val", "id", packageName)
                val monthlyId = resources.getIdentifier("tv_monthly_val", "id", packageName)

                if (dailyId != 0) setTextViewText(dailyId, dailyFormatted)
                if (weeklyId != 0) setTextViewText(weeklyId, weeklyFormatted)
                if (monthlyId != 0) setTextViewText(monthlyId, monthlyFormatted)
            }
        } else {
            null
        }

        val builder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle("Live Expense Summary")
            .setContentText("$dailyFormatted  •  $weeklyFormatted  •  $monthlyFormatted")
            .setContentIntent(pendingIntent)
            // Prevent the user from swiping it away or clearing it via "Clear All"
            .setOngoing(true)
            // Prevent vibration or sound when values are updated
            .setOnlyAlertOnce(true)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .setCategory(NotificationCompat.CATEGORY_SERVICE)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            // Ensure immediate display on Android 12+ without the 10-second foreground deferral
            .setForegroundServiceBehavior(NotificationCompat.FOREGROUND_SERVICE_IMMEDIATE)

        // Attach the custom RemoteViews layout if present in res/layout/notification_expense.xml
        if (remoteViews != null) {
            builder.setStyle(NotificationCompat.DecoratedCustomViewStyle())
            builder.setCustomContentView(remoteViews)
            builder.setCustomBigContentView(remoteViews)
        }

        return builder.build().apply {
            // Reinforce non-dismissible flags at the raw Notification level
            flags = flags or Notification.FLAG_ONGOING_EVENT or Notification.FLAG_NO_CLEAR
        }
    }

    private fun stopForegroundServiceCleanly() {
        isForegroundStarted = false
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
    }
}