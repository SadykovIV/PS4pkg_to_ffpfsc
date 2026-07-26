# PS4 FFPFSC 0.2.1 — Windows x64

## Русская версия

Самодостаточная версия для 64-битной Windows 10/11. Python, Qt for Python,
MkPFS, библиотеки сжатия/криптографии и модуль чтения и извлечения PS4 PKG уже
находятся внутри архива. Установка Python, Visual C++ Redistributable, Git,
Homebrew или других приложений не требуется.

### Использование

1. Распакуйте ZIP полностью в обычную папку.
2. Запустите `PS4 FFPFSC.exe`. Файл `ps4ffpsc-worker.exe` должен оставаться
   рядом — GUI запускает его автоматически и без отдельного окна консоли.
3. Выберите отдельные PKG или папку для рекурсивного сканирования.
4. Укажите папки для готовых файлов и временных данных, выполните сканирование
   и запустите сборку.

Сборка не подписана коммерческим Windows Code Signing сертификатом. При первом
запуске Microsoft Defender SmartScreen может показать предупреждение; проверьте
SHA-256 скачанного ZIP перед явным разрешением запуска.

### Важно

- Принимаются только законно полученные поддерживаемые PKG.
- Patch (`CATEGORY=gp`) не заменяет обязательный base PKG (`CATEGORY=gd`).
- Исходные PKG не перемещаются и не изменяются.
- Новые образы имеют `ps5_runtime_verified=false`, пока не проверены на консоли.
- Исходники и лицензии:
  <https://github.com/SadykovIV/PS4pkg_to_ffpfsc>

---

## English version

Self-contained build for 64-bit Windows 10/11. Python, Qt for Python, MkPFS,
compression/cryptography libraries and the PS4 PKG inspection/extraction helper
are included. Python, the Visual C++ Redistributable, Git, Homebrew and other
applications are not required.

## Usage

1. Extract the entire ZIP to a regular folder.
2. Run `PS4 FFPFSC.exe`. Keep `ps4ffpsc-worker.exe` beside it; the GUI starts
   the worker automatically without a separate console window.
3. Select individual PKGs or a folder to scan recursively.
4. Select output and temporary directories, scan, then build.

The build is not signed with a commercial Windows Code Signing certificate.
Microsoft Defender SmartScreen may warn on first launch; verify the downloaded
ZIP's SHA-256 before explicitly allowing it to run.

## Important

- Only legally obtained, supported PKGs are accepted.
- A patch (`CATEGORY=gp`) does not replace the required base PKG (`CATEGORY=gd`).
- Source PKGs are never moved or modified.
- New artifacts remain `ps5_runtime_verified=false` until tested on hardware.
- Source and license notices: <https://github.com/SadykovIV/PS4pkg_to_ffpfsc>
