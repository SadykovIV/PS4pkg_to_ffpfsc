# PS4 FFPFSC 0.2.4 — macOS arm64

## Русская версия

Самодостаточное приложение для Mac с Apple Silicon. Python, Qt for Python,
MkPFS, библиотеки сжатия/криптографии и модуль чтения метаданных и извлечения
PS4 PKG уже находятся внутри приложения. На целевом Mac не нужны Homebrew,
Python, исходный репозиторий или внешние приложения.

### Исправления 0.2.4

- Исправлен выход за границы памяти при расшифровке AES-записей PKG, размер
  которых не кратен 16 байтам. Последний блок теперь безопасно дополняется и
  обрезается до исходного размера; исправление проверено под AddressSanitizer.
- Существующий игровой `sce_sys/param.json`, содержащий только `gameIntent`,
  теперь дополняется обязательными для ShadowMountPlus полями `titleId` и
  `titleName` без потери исходных игровых полей.
- Удалена завышенная повторная проверка, требовавшая перед MkPFS свободное место
  в размере 2,2× всех PKG. Используются точные проверки места назначения и
  временных PFSC spool-файлов самого MkPFS.
- Малый patch-PKG It Takes Two полностью распакован обычной и ASan-сборкой;
  также отдельно проверен patch-PKG Gran Turismo 7.
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
  мелких чтений по 64 KiB. Это особенно ускоряет чтение с SMB/NAS на macOS.
- Байтовые события прогресса передаются напрямую из цикла расшифровки с
  ограниченной частотой; приложение не обходит временное дерево во время
  распаковки и не создаёт дополнительных копий.
- Версия приложения и автономных архивов обновлена до 0.2.3.

### Исправления 0.2.2

- Распакованные PKG, рабочее дерево и MkPFS tmp теперь записываются в выбранную
  временную папку (`/tmp` по умолчанию), а не в
  `~/Library/Application Support/PS4 FFPFSC`.
- GUI читает созданный inventory по пути, который вернул worker, и не обращается
  к старому каталогу `Application Support/PS4 FFPFSC/unpacked`.
- Индикатор показывает общий процент, текущий подэтап, прошедшее время и
  расчётное время до завершения; прогресс извлечения и MkPFS обновляется во
  время работы.
- Объединение использует hardlinks с автоматическим fallback на копирование и
  удаляет уже ненужные распакованные PKG после проверенного merge.
- Обычная сборка больше не вычисляет полные хэши исходных PKG, распакованных и
  объединённых деревьев или готового образа. Resume использует быстрые
  идентификаторы пути/размера/mtime и структурные сигнатуры без чтения payload.
- После полностью успешной сборки временный каталог игры удаляется
  автоматически. При ошибке или отмене данные для продолжения сохраняются.
- Добавлена полная английская локализация GUI и переключатель
  **Русский / English** с сохранением выбора.

### Исправления 0.2.1

- Патч теперь корректно заменяет файл базы, когда путь отличается только
  регистром символов.
- GUI показывает точную причину ошибки сборки вместо одного кода возврата.
- Команда сборки больше не сканирует выбранный каталог PKG второй раз.

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

## Fixes in 0.2.4

- Fixed an out-of-bounds access while decrypting PKG AES metadata entries whose
  size is not divisible by 16 bytes. The final block is safely zero-padded and
  truncated to the original length; the fix was verified with AddressSanitizer.
- An existing game `sce_sys/param.json` containing only `gameIntent` is now
  augmented with the `titleId` and `titleName` fields required by
  ShadowMountPlus without losing original game metadata.
- Removed the redundant pre-MkPFS check that required free temporary space
  equal to 2.2× all PKGs. MkPFS now performs its own exact destination and PFSC
  spool space checks.
- The small It Takes Two patch PKG was fully extracted with both release and
  ASan builds; the Gran Turismo 7 patch PKG was also tested separately.
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
  tiny 64 KiB reads. This is particularly beneficial for SMB/NAS sources on
  macOS.
- Throttled byte progress is emitted directly by the decrypt/write loop, so no
  repeated temporary-tree scans or extra copies are introduced.
- Application and standalone archive versions were updated to 0.2.3.

## Fixes in 0.2.2

- Extracted PKGs, merge trees and MkPFS scratch data now use the selected
  temporary directory (`/tmp` by default), not
  `~/Library/Application Support/PS4 FFPFSC`.
- The GUI reads the inventory path reported by the worker instead of looking in
  the obsolete `Application Support/PS4 FFPFSC/unpacked` directory.
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

## Fixes in 0.2.1

- A patch can now replace a base file when its path changes only by letter case.
- The GUI displays the exact build failure instead of only an exit code.
- A build no longer scans the selected PKG directory twice.

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
