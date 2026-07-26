# PS4 FFPFSC 0.2.0 — macOS arm64

## Русская версия

Самодостаточное приложение для Mac с Apple Silicon. Python, Qt for Python,
MkPFS, библиотеки сжатия/криптографии и модуль чтения метаданных и извлечения
PS4 PKG уже находятся внутри приложения. На целевом Mac не нужны Homebrew,
Python, исходный репозиторий или внешние приложения.

### Использование

1. Распакуйте ZIP.
2. Перенесите `PS4 FFPFSC.app` в `/Applications`.
3. При первом запуске нажмите приложение с зажатой клавишей Control и выберите
   **Открыть**.
4. Выберите отдельные PKG или папку для рекурсивного сканирования.
5. Укажите папки для готовых файлов и временных данных, выполните сканирование
   и запустите сборку.

GitHub-сборка подписана ad-hoc, поскольку сертификат Apple Developer ID не
использовался. Поэтому Gatekeeper может потребовать явного подтверждения при
первом запуске.

### Важно

- Принимаются только законно полученные поддерживаемые PKG.
- Patch (`CATEGORY=gp`) не является базовой игрой. Даже для большого patch-файла
  требуется base PKG с `CATEGORY=gd`.
- Новые образы имеют `ps5_runtime_verified=false`, пока не проверены на консоли.
- Исходники и лицензии:
  <https://github.com/SadykovIV/PS4pkg_to_ffpfsc>

---

## English version

Self-contained Apple Silicon application. Python, Qt for Python, MkPFS,
compression/cryptography runtimes and the PS4 PKG metadata/extraction helper are
inside the application bundle. Homebrew, Python and the source repository are
not required on the destination Mac.

## Usage

1. Extract the ZIP.
2. Move `PS4 FFPFSC.app` to `/Applications`.
3. On first launch, Control-click the application and select **Open**.
4. Select individual PKGs or a folder to scan recursively.
5. Select output and temporary directories, scan, then build.

The GitHub build is ad-hoc signed because no Apple Developer ID certificate was
available. This is why Gatekeeper may require the explicit first launch.

## Important

- Only legally obtained, supported PKGs are accepted.
- A patch (`CATEGORY=gp`) is not a base game. A valid base PKG
  (`CATEGORY=gd`) is required even when a patch file is large.
- New artifacts remain `ps5_runtime_verified=false` until tested on hardware.
- Source and license notices: <https://github.com/SadykovIV/PS4pkg_to_ffpfsc>
