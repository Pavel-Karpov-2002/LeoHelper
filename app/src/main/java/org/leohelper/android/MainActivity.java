package org.leohelper.android;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.text.InputType;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.EditText;
import android.widget.Toast;

import com.chaquo.python.Python;

import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.CountDownLatch;

public final class MainActivity extends Activity {
    private static final int SAVE_CSV = 1;
    private WebView panel;
    private String baseUrl;
    private volatile boolean closing;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        panel = new WebView(this);
        panel.getSettings().setJavaScriptEnabled(true);
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
                return !target.equals(baseUrl) && !target.equals(baseUrl + "/journal");
            }
        });
        setContentView(panel);
        startHelper();
    }

    @Override protected void onResume() {
        super.onResume();
        if (baseUrl == null) return;
        String visible = panel.getUrl();
        if ((baseUrl + "/journal").equals(visible)) panel.loadUrl(visible);
        else panel.loadUrl(baseUrl);
    }

    private void startHelper() {
        panel.loadData("<meta charset=utf-8><p>Подключение к Telegram…</p>", "text/html", "UTF-8");
        new Thread(() -> {
            try {
                Python.getInstance().getModule("android_entry")
                    .callAttr("run", this, getFilesDir().getAbsolutePath());
            } catch (Exception error) {
                runOnUiThread(() -> {
                    if (closing) return;
                    new AlertDialog.Builder(this).setTitle("Не удалось запустить помощник")
                        .setMessage(error.getMessage())
                        .setPositiveButton("Повторить", (dialog, which) -> startHelper())
                        .setNegativeButton("Закрыть", (dialog, which) -> finish()).show();
                });
            }
        }, "leo-helper").start();
    }

    public boolean isClosing() {
        return closing;
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

    private void showToast(String text) {
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
        panel.destroy();
        super.onDestroy();
    }
}




