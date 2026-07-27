# PS4 FFPFSC 0.2.4 — Windows x64

## Русская версия

Самодостаточная версия для 64-битной Windows 10/11. Python, Qt for Python,
MkPFS, библиотеки сжатия/криптографии и модуль чтения и извлечения PS4 PKG уже
находятся внутри архива. Установка Python, Visual C++ Redistributable, Git,
Homebrew или других приложений не требуется.

### Исправления 0.2.4

- Исправлено аварийное завершение нативного PKG extractor с кодом Windows
  `0xC0000374` при распаковке patch-PKG, содержащих AES-записи с размером,
  не кратным 16 байтам. Последний блок теперь безопасно дополняется и
  обрезается до исходного размера без повреждения памяти.
- Существующий игровой `sce_sys/param.json`, содержащий только `gameIntent`,
  теперь дополняется обязательными для ShadowMountPlus полями `titleId` и
  `titleName`. Исходные игровые поля сохраняются.
- Удалена завышенная повторная проверка, требовавшая перед MkPFS свободное место
  в размере 2,2× всех PKG. Используются точные проверки места назначения и
  временных PFSC spool-файлов самого MkPFS.
- Добавлены C++-регрессионные тесты AES-записей размером 160 и 532 байта.
  Проблемные patch-PKG It Takes Two и Gran Turismo 7 проверены отдельно.
- Временное состояние распаковки, созданное версиями до 0.2.4, один раз
  пересоздаётся, чтобы не использовать данные, полученные старым extractor.
- Версия приложения и автономных архивов обновлена до 0.2.4.

### Изменения 0.2.3

- В таблицу **«3. Найденные игры»** добавлен размер каждого PKG и примерный
  суммарный размер выбранной игры; сводка также показывает общий объём
  отмеченных игр.
- Процент распаковки теперь рассчитывается по реально записанным байтам, а
  вклад base/patch/DLC в общий прогресс взвешивается по размеру исходных PKG.
  Для этапа распаковки показывается отдельная оценка оставшегося времени.
- Нативный PKG extractor держит исходный файл открытым в течение всей
  распаковки и использует ограниченный 8 MiB read-ahead cache вместо тысяч
  мелких чтений по 64 KiB, что особенно полезно для сетевых папок.
- Байтовые события прогресса передаются напрямую из цикла расшифровки с
  ограниченной частотой; временное дерево не сканируется во время распаковки.
- Версия приложения и автономных архивов обновлена до 0.2.3.

### Исправления 0.2.2

- Распакованные PKG, рабочее дерево и MkPFS tmp теперь записываются в выбранную
  временную папку, а не в `Application Support`.
- Пути и имена с кириллицей корректно обрабатываются worker и MkPFS в Windows.
- GUI читает созданный inventory по пути, который вернул worker; сканирование
  больше не обращается к старому каталогу `AppData\Local\PS4 FFPFSC\unpacked`.
- Индикатор показывает общий процент, текущий подэтап, прошедшее время и
  расчётное время до завершения; извлечение и MkPFS передают живой прогресс.
- Объединение использует hardlinks с автоматическим fallback на копирование и
  удаляет уже ненужные распакованные PKG после проверенного merge.
- Обычная сборка больше не вычисляет полные хэши исходных PKG, распакованных и
  объединённых деревьев или готового образа. Resume использует быстрые
  идентификаторы пути/размера/mtime и структурные сигнатуры без чтения payload.
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

## Fixes in 0.2.4

- Fixed native PKG extractor crashes with Windows code `0xC0000374` while
  extracting patch PKGs whose AES metadata entry length is not divisible by
  16 bytes. The final block is now safely zero-padded and truncated without
  accessing memory outside the buffer.
- An existing game `sce_sys/param.json` containing only `gameIntent` is now
  augmented with the `titleId` and `titleName` fields required by
  ShadowMountPlus while preserving the original game metadata.
- Removed the redundant pre-MkPFS check that required free temporary space
  equal to 2.2× all PKGs. MkPFS now performs its own exact destination and PFSC
  spool space checks.
- Added C++ regression tests for 160-byte and 532-byte AES entries. The
  reported It Takes Two and Gran Turismo 7 patch PKGs were tested separately.
- Temporary extraction state created before 0.2.4 is rebuilt once so data
  produced by the old extractor cannot be resumed.
- Application and standalone archive versions were updated to 0.2.4.

## Changes in 0.2.3

- The **3. Discovered games** table now shows every PKG size and an approximate
  total source size per game; the summary also shows the total size of checked
  games.
- Extraction progress now follows bytes actually written, while base, patch and
  DLC contributions are weighted by source PKG size. Extraction has its own
  byte-rate ETA.
- The native PKG extractor keeps one source file descriptor open for the whole
  operation and uses a bounded 8 MiB read-ahead cache instead of thousands of
  tiny 64 KiB reads, improving network-folder performance.
- Throttled byte progress is emitted directly by the decrypt/write loop, so the
  temporary tree is not repeatedly scanned during extraction.
- Application and standalone archive versions were updated to 0.2.3.

## Fixes in 0.2.2

- Extracted PKGs, merge trees and MkPFS scratch data now use the selected
  temporary directory instead of `Application Support`.
- The worker and MkPFS now handle Cyrillic paths and names correctly on Windows.
- The GUI reads the inventory path reported by the worker instead of looking in
  the obsolete `AppData\Local\PS4 FFPFSC\unpacked` directory.
- The progress area shows overall percentage, current substage, elapsed time and
  estimated time remaining, with live extraction and MkPFS updates.
- Merge staging uses hardlinks with an automatic copy fallback and discards
  extracted PKG trees after verification.
- Normal builds no longer fully hash source PKGs, extracted/merged trees, or the
  completed image. Resume uses cheap path/size/mtime identities and structural
  signatures without reading payload data.
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
