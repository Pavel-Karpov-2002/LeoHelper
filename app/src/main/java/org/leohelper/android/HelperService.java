package org.leohelper.android;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Binder;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;

import com.chaquo.python.Python;

public final class HelperService extends Service {
    private static final String CHANNEL = "background_auto_skip";
    private static final String STOP = "org.leohelper.android.STOP_AUTO";
    private final Handler main = new Handler(Looper.getMainLooper());
    private final LocalBinder binder = new LocalBinder();
    private volatile MainActivity activity;
    private volatile boolean closing;
    private volatile boolean stopAuto;
    private Thread worker;
    private String url;
    private boolean foreground;

    public final class LocalBinder extends Binder {
        HelperService service() { return HelperService.this; }
    }

    @Override public IBinder onBind(Intent intent) { return binder; }

    void attach(MainActivity next) {
        activity = next;
        if (url != null) next.ready(url);
        else startWorker();
    }

    void detach(MainActivity old) {
        if (activity == old) activity = null;
    }

    void startWorker() {
        if (worker != null) return;
        worker = new Thread(() -> {
            String error = null;
            try {
                Python.getInstance().getModule("android_entry")
                    .callAttr("run", this, getFilesDir().getAbsolutePath());
            } catch (Exception failure) {
                error = failure.getMessage();
            }
            final String reason = error;
            main.post(() -> {
                worker = null;
                url = null;
                leaveForeground();
                if (!closing && reason != null && activity != null) activity.showHelperError(reason);
            });
        }, "leo-helper");
        worker.start();
    }

    public boolean isClosing() { return closing; }

    public boolean consumeStop() {
        if (!stopAuto) return false;
        stopAuto = false;
        return true;
    }

    public String ask(String label, boolean secret) throws InterruptedException {
        MainActivity screen = activity;
        if (screen == null) throw new IllegalStateException("Откройте LeoHelper для входа в Telegram");
        return screen.ask(label, secret);
    }

    public void ready(String address) {
        main.post(() -> {
            if (closing) return;
            url = address;
            if (activity != null) activity.ready(address);
        });
    }

    public void autoModeChanged(boolean enabled) {
        main.post(() -> {
            if (closing) return;
            if (!enabled) {
                leaveForeground();
                return;
            }
            try {
                startService(new Intent(this, HelperService.class));
                startForeground(2, backgroundNotification());
                foreground = true;
            } catch (RuntimeException failure) {
                stopAuto = true;
                if (activity != null) activity.showToast("Android не разрешил фоновый автопропуск");
                leaveForeground();
            }
        });
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && STOP.equals(intent.getAction())) {
            stopAuto = true;
            leaveForeground();
        }
        return START_NOT_STICKY;
    }

    private Notification backgroundNotification() {
        if (Build.VERSION.SDK_INT >= 26) {
            getSystemService(NotificationManager.class).createNotificationChannel(
                new NotificationChannel(CHANNEL, "Фоновый автопропуск", NotificationManager.IMPORTANCE_LOW));
        }
        PendingIntent open = PendingIntent.getActivity(this, 0,
            new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        PendingIntent stop = PendingIntent.getService(this, 1,
            new Intent(this, HelperService.class).setAction(STOP),
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder builder = Build.VERSION.SDK_INT >= 26
            ? new Notification.Builder(this, CHANNEL) : new Notification.Builder(this);
        return builder.setSmallIcon(R.drawable.leo_notification)
            .setContentTitle("Автопропуск включён")
            .setContentText("LeoHelper проверяет повторы в чате с Дайвинчиком")
            .setContentIntent(open)
            .setOngoing(true)
            .setVisibility(Notification.VISIBILITY_PRIVATE)
            .addAction(new Notification.Action.Builder(null, "Выключить", stop).build())
            .build();
    }

    private void leaveForeground() {
        if (foreground) {
            stopForeground(STOP_FOREGROUND_REMOVE);
            foreground = false;
        }
        stopSelf();
    }

    public void notifyAutoStopped(String reason) {
        main.post(() -> {
            if (closing || (Build.VERSION.SDK_INT >= 33 &&
                checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)) return;
            NotificationManager manager = getSystemService(NotificationManager.class);
            String channel = "auto_skip";
            if (Build.VERSION.SDK_INT >= 26) {
                manager.createNotificationChannel(new NotificationChannel(channel, "Автопропуск", NotificationManager.IMPORTANCE_DEFAULT));
            }
            PendingIntent open = PendingIntent.getActivity(this, 0,
                new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
            Notification.Builder builder = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, channel) : new Notification.Builder(this);
            manager.notify(1, builder.setSmallIcon(R.drawable.leo_notification)
                .setContentTitle("Автопропуск остановился").setContentText(reason)
                .setContentIntent(open).setVisibility(Notification.VISIBILITY_PRIVATE)
                .setAutoCancel(true).build());
        });
    }

    @Override public void onDestroy() {
        closing = true;
        activity = null;
        if (worker != null) worker.interrupt();
        super.onDestroy();
    }
}
