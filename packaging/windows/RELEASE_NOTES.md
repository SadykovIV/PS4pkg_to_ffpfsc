# PS4 FFPFSC 0.2.2 — Windows x64

## Русская версия

Самодостаточная версия для 64-битной Windows 10/11. Python, Qt for Python,
MkPFS, библиотеки сжатия/криптографии и модуль чтения и извлечения PS4 PKG уже
находятся внутри архива. Установка Python, Visual C++ Redistributable, Git,
Homebrew или других приложений не требуется.

### Исправления 0.2.2

- Распакованные PKG, рабочее дерево и MkPFS tmp теперь записываются в выбранную
  временную папку, а не в `Application Support`.
- Пути и имена с кириллицей корректно обрабатываются worker и MkPFS в Windows.
- GUI читает созданный inventory по пути, который вернул worker; сканирование
  больше не обращается к старому каталогу `AppData\Local\PS4 FFPFSC\unpacked`.
- Индикатор показывает общий процент, текущий подэтап, прошедшее время и
  расчётное время до завершения; извлечение и MkPFS передают живой прогресс.
- Объединение использует hardlinks с автоматическим fallback на копирование,
  не хеширует распакованное дерево дважды и удаляет уже ненужные распакованные
  PKG после проверенного merge.
- После полностью успешной сборки временный каталог игры удаляется
  автоматически. При ошибке или отмене данные для продолжения сохраняются.
- Добавлена полная английская локализация GUI и переключатель
  **Русский / English** с сохранением выбора.

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

## Fixes in 0.2.2

- Extracted PKGs, merge trees and MkPFS scratch data now use the selected
  temporary directory instead of `Application Support`.
- The worker and MkPFS now handle Cyrillic paths and names correctly on Windows.
- The GUI reads the inventory path reported by the worker instead of looking in
  the obsolete `AppData\Local\PS4 FFPFSC\unpacked` directory.
- The progress area shows overall percentage, current substage, elapsed time and
  estimated time remaining, with live extraction and MkPFS updates.
- Merge staging uses hardlinks with an automatic copy fallback, avoids hashing
  an extracted tree twice, and discards extracted PKG trees after verification.
- A fully successful build automatically removes its per-game temporary
  workspace. Failed or cancelled builds keep resumable state.
- Full English GUI localization and a persistent **Русский / English** language
  selector were added.

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
