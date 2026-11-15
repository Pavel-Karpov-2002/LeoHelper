# Помощник Дайвинчика

Android-приложение для просмотра анкет @leomatchbot с журналом ответов, CSV и автопропуском. Приложение использует собственную сессию Telegram. При первом запуске нужны api_id и api_hash из API development tools на https://my.telegram.org.

## Сборка

Установите JDK 17, Gradle 8.10.2, Python 3.12 и Android SDK Platform 35. Укажите путь к SDK в ANDROID_HOME или local.properties. Если Gradle не находит Python 3.12, задайте LEO_BUILD_PYTHON полным путём к интерпретатору.

```sh
python -m pip wheel --no-deps --wheel-dir app/wheels pyaes==1.6.1
gradle :app:assembleDebug
```

APK появится в app/build/outputs/apk/debug/app-debug.apk. Сессия Telegram и журнал хранятся в закрытой папке приложения на устройстве.
