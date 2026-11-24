package org.leohelper.android;

import android.Manifest;
import android.app.DownloadManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Environment;
import android.util.Log;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;

final class ReleaseUpdates {
    private static final String REPO = "Pavel-Karpov-2002/LeoHelper";
    private static final String DOWNLOAD_BASE = "https://github.com/" + REPO + "/releases/download/";
    private static final String CHANNEL = "release_updates";
    private static final int POLL_JOB = 3001;
    private static final int UPDATE_NOTIFICATION = 3002;
    private static final String VERSION = "\\d{1,5}(?:\\.\\d{1,5}){1,2}";

    static final class Release {
        final String version;
        final String url;

        Release(String version, String url) {
            this.version = version;
            this.url = url;
        }

        String fileName() { return "LeoHelper-" + version + ".apk"; }
    }

    private ReleaseUpdates() {}

    static void schedule(Context context) {
        try {
            JobScheduler scheduler = context.getSystemService(JobScheduler.class);
            if (scheduler == null || scheduler.getPendingJob(POLL_JOB) != null) return;
            JobInfo job = new JobInfo.Builder(POLL_JOB, new ComponentName(context, UpdateJobService.class))
                .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY)
                .setPeriodic(8 * 60 * 60 * 1000L)
                .build();
            if (scheduler.schedule(job) != JobScheduler.RESULT_SUCCESS) {
                Log.w("LeoHelper", "Could not schedule background update checks");
            }
        } catch (RuntimeException error) {
            Log.w("LeoHelper", "Background update checks are unavailable", error);
        }
    }

    static Release latest(Context context) throws Exception {
        String installed = context.getPackageManager().getPackageInfo(context.getPackageName(), 0).versionName;
        HttpURLConnection connection = (HttpURLConnection) new URL(
            "https://api.github.com/repos/" + REPO + "/releases/latest").openConnection();
        connection.setRequestProperty("Accept", "application/vnd.github+json");
        connection.setRequestProperty("User-Agent", "LeoHelper-Android");
        connection.setConnectTimeout(6000);
        connection.setReadTimeout(6000);
        try {
            int code = connection.getResponseCode();
            if (code == 404) return null;
            if (code != 200) throw new IllegalStateException("GitHub returned " + code);
            try (InputStream input = connection.getInputStream(); ByteArrayOutputStream bytes = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[4096];
                for (int length; (length = input.read(buffer)) != -1;) {
                    if (bytes.size() + length > 1024 * 1024) throw new IllegalStateException("Release metadata is too large");
                    bytes.write(buffer, 0, length);
                }
                return selectRelease(new JSONObject(bytes.toString("UTF-8")), installed);
            }
        } finally {
            connection.disconnect();
        }
    }

    static Release selectRelease(JSONObject data, String installed) {
        String tag = data.optString("tag_name");
        if (!tag.matches("v" + VERSION) || installed == null || !installed.matches(VERSION)
            || data.optBoolean("draft") || data.optBoolean("prerelease")) return null;
        String version = tag.substring(1);
        if (compareVersions(version, installed) <= 0) return null;
        JSONArray assets = data.optJSONArray("assets");
        if (assets == null) return null;
        String expectedFile = "LeoHelper-" + version + ".apk";
        for (int i = 0; i < assets.length(); i++) {
            JSONObject asset = assets.optJSONObject(i);
            if (asset == null || !expectedFile.equals(asset.optString("name"))
                || !"uploaded".equals(asset.optString("state")) || asset.optLong("size") <= 0) continue;
            Release release = new Release(version, asset.optString("browser_download_url"));
            if (valid(release)) return release;
        }
        return null;
    }

    static int compareVersions(String first, String second) {
        String[] left = first.split("\\."), right = second.split("\\.");
        for (int i = 0; i < Math.max(left.length, right.length); i++) {
            int relation = Integer.compare(i < left.length ? Integer.parseInt(left[i]) : 0,
                                           i < right.length ? Integer.parseInt(right[i]) : 0);
            if (relation != 0) return relation;
        }
        return 0;
    }

    private static boolean valid(Release release) {
        return release.version != null && release.version.matches(VERSION)
            && (DOWNLOAD_BASE + "v" + release.version + "/" + release.fileName()).equals(release.url);
    }

    static void notifyOnce(Context context, Release release) {
        if (release == null || (Build.VERSION.SDK_INT >= 33 &&
            context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)) return;
        NotificationManager notifications = context.getSystemService(NotificationManager.class);
        if (!notifications.areNotificationsEnabled()) return;
        if (Build.VERSION.SDK_INT >= 26) {
            notifications.createNotificationChannel(new NotificationChannel(
                CHANNEL, "Обновления LeoHelper", NotificationManager.IMPORTANCE_DEFAULT));
        }
        android.content.SharedPreferences prefs = context.getSharedPreferences(CHANNEL, Context.MODE_PRIVATE);
        if (release.version.equals(prefs.getString("notifiedVersion", ""))) return;
        Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(release.url));
        PendingIntent open = PendingIntent.getActivity(context, 30, intent,
            PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder builder = Build.VERSION.SDK_INT >= 26
            ? new Notification.Builder(context, CHANNEL) : new Notification.Builder(context);
        notifications.notify(UPDATE_NOTIFICATION, builder.setSmallIcon(R.drawable.leo_notification)
            .setContentTitle("Доступен LeoHelper " + release.version)
            .setContentText("Нажмите, чтобы скачать APK")
            .setContentIntent(open).setAutoCancel(true).build());
        prefs.edit().putString("notifiedVersion", release.version).apply();
    }

    static boolean download(Context context, Release release) {
        if (!valid(release)) return false;
        Uri uri = Uri.parse(release.url);
        if (Build.VERSION.SDK_INT >= 29) {
            try {
                DownloadManager.Request request = new DownloadManager.Request(uri)
                    .setTitle(release.fileName()).setMimeType("application/vnd.android.package-archive")
                    .setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                    .setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, release.fileName());
                context.getSystemService(DownloadManager.class).enqueue(request);
                return true;
            } catch (RuntimeException error) {
                Log.w("LeoHelper", "Could not enqueue update download", error);
            }
        }
        try {
            context.startActivity(new Intent(Intent.ACTION_VIEW, uri));
            return true;
        } catch (RuntimeException error) {
            return false;
        }
    }
}
