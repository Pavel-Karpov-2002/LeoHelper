package org.leohelper.android;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.app.DownloadManager;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Intent;
import android.content.ServiceConnection;
import android.net.Uri;
import android.content.pm.PackageManager;
import android.database.Cursor;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.provider.Settings;
import android.text.InputType;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.Toast;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.CountDownLatch;

public final class MainActivity extends Activity {
    private static final int SAVE_CSV = 1;
    private static final int NOTIFICATION_PERMISSION = 2;
    private static final int INSTALL_ACCESS = 3;
    private static final String PENDING_UPDATE = "pendingUpdateDownload";
    private final Handler updateHandler = new Handler(Looper.getMainLooper());
    private final Runnable updateDownloadCheck = this::checkUpdateDownload;
    private WebView panel;
    private String baseUrl;
    private volatile boolean closing;
    private boolean bound;
    private long checkedUpdatesAt;
    private String promptedVersion;
    private boolean resumed;
    private HelperService helper;
    private final ServiceConnection connection = new ServiceConnection() {
        @Override public void onServiceConnected(ComponentName name, IBinder binder) {
            helper = ((HelperService.LocalBinder) binder).service();
            helper.attach(MainActivity.this);
        }
        @Override public void onServiceDisconnected(ComponentName name) {
            helper = null;
            baseUrl = null;
        }
    };

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        panel = new WebView(this);
        panel.getSettings().setJavaScriptEnabled(true);
        panel.getSettings().setMediaPlaybackRequiresUserGesture(false);
        panel.setWebChromeClient(new WebChromeClient());
        panel.getSettings().setAllowFileAccess(false);
        panel.getSettings().setAllowContentAccess(false);
        panel.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String target = request.getUrl().toString();
                if (baseUrl == null) return true;
                if (target.equals(baseUrl + "/csv")) {
                    Intent save = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    save.addCategory(Intent.CATEGORY_OPENABLE);
                    save.setType("text/csv");
                    save.putExtra(Intent.EXTRA_TITLE, "leo-journal.csv");
                    startActivityForResult(save, SAVE_CSV);
                    return true;
                }
                if (request.isForMainFrame() && request.hasGesture()
                        && target.matches("https://www\\.instagram\\.com/[A-Za-z0-9_.]{1,30}/")) {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, request.getUrl()));
                    } catch (ActivityNotFoundException error) {
                        showToast("Не удалось открыть Instagram");
                    }
                    return true;
                }
                return !target.equals(baseUrl) && !target.equals(baseUrl + "/journal");
            }
        });
        setContentView(panel);
        prepareNotifications();
        ReleaseUpdates.schedule(this);
        panel.loadData("<meta charset=utf-8><p>Подключение к Telegram…</p>", "text/html", "UTF-8");
        bound = bindService(new Intent(this, HelperService.class), connection, BIND_AUTO_CREATE);
    }

    @Override protected void onResume() {
        super.onResume();
        resumed = true;
        updateHandler.post(updateDownloadCheck);
        checkUpdates();
        if (baseUrl == null) return;
        String visible = panel.getUrl();
        if ((baseUrl + "/journal").equals(visible)) panel.loadUrl(visible);
        else panel.loadUrl(baseUrl);
    }

    @Override protected void onPause() {
        resumed = false;
        updateHandler.removeCallbacks(updateDownloadCheck);
        super.onPause();
    }

    private void downloadUpdate(ReleaseUpdates.Release release) {
        long id = ReleaseUpdates.download(this, release);
        if (id > 0) {
            getPreferences(MODE_PRIVATE).edit().putLong(PENDING_UPDATE, id).apply();
            updateHandler.removeCallbacks(updateDownloadCheck);
            updateHandler.post(updateDownloadCheck);
        }
        showToast(id > 0 ? "Скачивание APK запущено" : id == 0 ? "Скачивание открыто в браузере"
            : "Не удалось открыть скачивание APK");
    }

    private void checkUpdateDownload() {
        if (!resumed || closing || isFinishing() || Build.VERSION.SDK_INT < 26) return;
        long id = getPreferences(MODE_PRIVATE).getLong(PENDING_UPDATE, 0);
        if (id == 0) return;
        DownloadManager manager = getSystemService(DownloadManager.class);
        try {
            int status;
            try (Cursor download = manager.query(new DownloadManager.Query().setFilterById(id))) {
                status = download != null && download.moveToFirst()
                    ? download.getInt(download.getColumnIndexOrThrow(DownloadManager.COLUMN_STATUS))
                    : DownloadManager.STATUS_FAILED;
            }
            if (status == DownloadManager.STATUS_FAILED) {
                clearPendingUpdate();
                promptedVersion = null;
                checkedUpdatesAt = 0;
                showToast("Не удалось скачать обновление");
            } else if (status != DownloadManager.STATUS_SUCCESSFUL) {
                updateHandler.postDelayed(updateDownloadCheck, 1000);
            } else if (!getPackageManager().canRequestPackageInstalls()) {
                showToast("Разрешите установку обновлений из LeoHelper");
                startActivityForResult(new Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:" + getPackageName())), INSTALL_ACCESS);
            } else {
                Uri apk = manager.getUriForDownloadedFile(id);
                clearPendingUpdate();
                if (apk == null) throw new IllegalStateException("Download URI is unavailable");
                startActivity(new Intent(Intent.ACTION_INSTALL_PACKAGE, apk)
                    .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION));
            }
        } catch (RuntimeException error) {
            clearPendingUpdate();
            showToast("Не удалось открыть установщик обновления");
        }
    }

    private void clearPendingUpdate() {
        getPreferences(MODE_PRIVATE).edit().remove(PENDING_UPDATE).apply();
    }

    private void checkUpdates() {
        long now = android.os.SystemClock.elapsedRealtime();
        if (checkedUpdatesAt != 0 && now - checkedUpdatesAt < 15 * 60 * 1000) return;
        checkedUpdatesAt = now;
        new Thread(() -> {
            try {
                ReleaseUpdates.Release release = ReleaseUpdates.latest(this);
                if (release == null) return;
                runOnUiThread(() -> {
                    ReleaseUpdates.notifyOnce(this, release);
                    if (closing || !resumed || release.version.equals(promptedVersion) ||
                        getPreferences(MODE_PRIVATE).getLong(PENDING_UPDATE, 0) > 0) return;
                    promptedVersion = release.version;
                    new AlertDialog.Builder(this).setTitle("Доступен LeoHelper " + release.version)
                        .setMessage("Скачать APK с GitHub?")
                        .setPositiveButton("Скачать APK", (dialog, which) -> downloadUpdate(release))
                        .setNegativeButton("Позже", null).show();
                });
            } catch (Exception networkFailure) {
                runOnUiThread(() -> checkedUpdatesAt = 0);
            }
        }, "leo-update-check").start();
    }

    private void prepareNotifications() {
        if (Build.VERSION.SDK_INT >= 33 &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED &&
            !getPreferences(MODE_PRIVATE).getBoolean("notificationsAsked", false)) {
            getPreferences(MODE_PRIVATE).edit().putBoolean("notificationsAsked", true).apply();
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, NOTIFICATION_PERMISSION);
        }
    }

    void showHelperError(String reason) {
        if (closing) return;
        new AlertDialog.Builder(this).setTitle("Не удалось запустить помощник")
            .setMessage(reason)
            .setPositiveButton("Повторить", (dialog, which) -> {
                if (helper != null) helper.startWorker();
            })
            .setNegativeButton("Закрыть", (dialog, which) -> finish()).show();
    }

    public void ready(String url) {
        runOnUiThread(() -> {
            if (closing) return;
            baseUrl = url;
            panel.loadUrl(url);
        });
    }

    public String ask(String label, boolean secret) throws InterruptedException {
        CountDownLatch finished = new CountDownLatch(1);
        String[] result = new String[1];
        runOnUiThread(() -> {
            if (closing) {
                finished.countDown();
                return;
            }
            EditText field = new EditText(this);
            field.setSingleLine();
            field.setInputType(secret ? InputType.TYPE_CLASS_TEXT |
                InputType.TYPE_TEXT_VARIATION_PASSWORD : InputType.TYPE_CLASS_TEXT);
            AlertDialog dialog = new AlertDialog.Builder(this).setTitle(label).setView(field)
                .setPositiveButton("Продолжить", (d, which) -> result[0] = field.getText().toString())
                .setNegativeButton("Отмена", null).create();
            dialog.setOnDismissListener(d -> finished.countDown());
            dialog.show();
        });
        finished.await();
        if (result[0] == null) throw new IllegalStateException("Вход отменён");
        return result[0];
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        if (request == INSTALL_ACCESS && Build.VERSION.SDK_INT >= 26) {
            if (!getPackageManager().canRequestPackageInstalls()) clearPendingUpdate();
            return;
        }
        if (request != SAVE_CSV || result != RESULT_OK || data == null || data.getData() == null) return;
        Uri target = data.getData();
        String source = baseUrl + "/csv";
        new Thread(() -> {
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(source).openConnection();
                connection.setConnectTimeout(5000);
                connection.setReadTimeout(90000);
                try (InputStream in = connection.getInputStream();
                     OutputStream out = getContentResolver().openOutputStream(target, "wt")) {
                    if (out == null) throw new IllegalStateException("Файл недоступен");
                    byte[] buffer = new byte[8192];
                    for (int length; (length = in.read(buffer)) != -1;) out.write(buffer, 0, length);
                }
                showToast("CSV сохранён");
            } catch (Exception error) {
                showToast("Не удалось сохранить CSV: " + error.getMessage());
            } finally {
                if (connection != null) connection.disconnect();
            }
        }, "leo-export").start();
    }

    void showToast(String text) {
        runOnUiThread(() -> Toast.makeText(this, text, Toast.LENGTH_LONG).show());
    }

    @Override public void onBackPressed() {
        panel.evaluateJavascript("(function(){const d=document.querySelector('#lightbox[open]');"
            + "if(!d)return false;d.close();return true;})()", closed -> {
            if ("true".equals(closed)) return;
            if (panel.canGoBack()) panel.goBack();
            else super.onBackPressed();
        });
    }

    @Override protected void onDestroy() {
        closing = true;
        if (helper != null) helper.detach(this);
        if (bound) unbindService(connection);
        panel.destroy();
        super.onDestroy();
    }
}




