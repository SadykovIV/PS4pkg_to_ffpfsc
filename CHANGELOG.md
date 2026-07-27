# История изменений / Changelog

Все выпуски используют единый формат: сначала перечислены новые возможности,
затем исправления и важные улучшения. Готовые сборки macOS arm64 и Windows x64
являются самодостаточными и не требуют установленного Python или внешних
приложений.

All releases use the same format: new capabilities first, followed by fixes and
important improvements. The ready-made macOS arm64 and Windows x64 builds are
self-contained and require neither Python nor external applications.

## Русский

### 0.2.5

#### Добавлено

- Выбор каждого BASE, PATCH и DLC PKG непосредственно в списке найденных игр.
- Безопасное распознавание точных копий по встроенному digest из заголовка PKG:
  дубликаты отключаются по умолчанию, а разные `part1`/`part2` остаются
  выбранными.
- Настройка уровня deflate-сжатия FFPFSC от 0 до 9 с сохранением выбранного
  значения.
- Автоматическое использование всех доступных логических процессоров MkPFS.
- Единый двуязычный changelog и одинаковое оформление всех GitHub Releases.

#### Исправлено

- После ошибки или отмены повторный запуск быстро сверяет уже распакованные
  пакеты по метаданным и продолжает только с новых, изменённых или ранее
  незавершённых PKG.
- Состояние распаковки сохраняется после каждого успешного PKG и
  восстанавливается из актуального manifest, если отдельный state-файл утрачен.
- Проверка свободного места учитывает только пакеты, которые действительно
  осталось распаковать.
- Windows использует `%TEMP%` по умолчанию; старое значение из `AppData`
  автоматически переносится на системный временный каталог.
- Удалены лишние настройки «Совместимость» и DLC; безопасные значения
  ShadowMountPlus применяются автоматически.
- Обновлено двуязычное окно «О программе» с указанием автора и репозитория.

### 0.2.4

#### Добавлено

- Нормализация существующего `sce_sys/param.json`: поля игры сохраняются, а
  недостающие `titleId`, `titleName` и `localizedParameters` добавляются для
  ShadowMountPlus.
- Регрессионные C++-тесты для AES-записей PKG с неполным последним блоком.

#### Исправлено

- Устранено аварийное завершение Windows extractor `0xC0000374` при распаковке
  некоторых patch-PKG.
- Исправлена ошибка `param.json titleId mismatch: None` для It Takes Two и
  других игр с минимальным игровым JSON.
- Удалена завышенная повторная проверка свободного места в размере 2,2× всех
  исходных PKG.
- Linux CI дополнен системной библиотекой EGL для стабильных GUI-тестов.

### 0.2.3

#### Добавлено

- Размер каждого PKG, примерный суммарный размер игры и общий объём выбранных
  игр в GUI.
- Прогресс распаковки по реально записанным байтам с оценкой оставшегося
  времени.
- Одинаковые оптимизации и функции в сборках macOS arm64 и Windows x64.

#### Исправлено

- Ускорено чтение PKG с SMB/NAS: один открытый файловый дескриптор и
  ограниченный read-ahead cache 8 MiB вместо тысяч мелких операций.
- Индикатор прогресса больше не сканирует временное дерево и не создаёт
  дополнительные копии данных.
- После успешной сборки временный каталог игры удаляется автоматически.

### 0.2.2

#### Добавлено

- Самодостаточная сборка Windows x64 вместе с существующей macOS arm64.
- Полная английская локализация и переключатель **Русский / English** с
  сохранением выбора.
- Подробный общий прогресс: этап, подэтап, процент, прошедшее и оставшееся
  время.
- Безопасное продолжение после ошибки или отмены.

#### Исправлено

- Инвентарь Windows читается из выбранного временного каталога, а не из
  `AppData`.
- Все тяжёлые временные данные направляются только в выбранную пользователем
  папку.
- Уменьшено потребление диска за счёт hardlink, атомарного перемещения и
  безопасного резервного копирования.
- Контрольные суммы архивов приведены к переносимому формату.

### 0.2.1

#### Добавлено

- Точные сообщения об ошибках сборки в GUI.
- Проверка и автоматическое исключение полностью одинаковых PKG.

#### Исправлено

- Патчи корректно заменяют файлы базы, если путь отличается только регистром
  символов.
- Устранено повторное сканирование выбранного каталога перед сборкой.
- Исправлена обработка конфликтов нескольких BASE и PATCH.

### 0.2.0

#### Добавлено

- Первый публичный выпуск самодостаточного приложения macOS arm64.
- Выбор отдельных PKG или рекурсивное сканирование каталога.
- Группировка BASE, PATCH и DLC по `TITLE_ID`.
- Полный конвейер `PKG → объединённая игра → exFAT → FFPFSC`.
- Автоматическая проверка созданного контейнера и обязательных игровых файлов.
- Отдельные каталоги результата и временных данных; исходные PKG открываются
  только для чтения.

#### Исправлено

- Первый публичный выпуск; исправления продолжились в версии 0.2.1.

---

## English

### 0.2.5

#### Added

- Per-package selection for every BASE, PATCH, and DLC item in the discovered
  games tree.
- Safe exact-copy detection using the embedded PKG header digest: duplicates
  are unchecked by default, while different `part1`/`part2` packages remain
  selected.
- Selectable FFPFSC deflate compression levels from 0 through 9 with persistent
  settings.
- Automatic use of every logical CPU available to MkPFS.
- A unified bilingual changelog and consistent presentation for every GitHub
  Release.

#### Fixed

- After an error or cancellation, a later run quickly validates completed
  package trees using metadata and continues only with new, changed, or
  previously unfinished PKGs.
- Extraction state is saved after every successful PKG and recovered from the
  current manifest when the dedicated state file is missing.
- Free-space checks now account only for packages that still require
  extraction.
- Windows uses `%TEMP%` by default and automatically migrates the legacy
  `AppData` temporary setting.
- Redundant Compatibility and DLC controls were removed; safe ShadowMountPlus
  values are applied automatically.
- The bilingual About dialog now includes the author and repository.

### 0.2.4

#### Added

- Existing `sce_sys/param.json` files are normalized without losing game fields;
  missing `titleId`, `titleName`, and `localizedParameters` values are added for
  ShadowMountPlus.
- Native regression tests cover PKG AES records with a partial final block.

#### Fixed

- Fixed Windows extractor crashes with code `0xC0000374` on some patch PKGs.
- Fixed `param.json titleId mismatch: None` for It Takes Two and other games
  with minimal game-provided JSON.
- Removed the overly conservative repeated free-space check requiring 2.2× all
  source PKGs.
- Added the EGL system dependency required for stable Linux GUI tests.

### 0.2.3

#### Added

- Per-PKG size, approximate game size, and total selected size in the GUI.
- Extraction progress based on bytes actually written, including an ETA.
- The same features and optimizations in both macOS arm64 and Windows x64
  builds.

#### Fixed

- Faster PKG reads over SMB/NAS through one persistent file handle and a bounded
  8 MiB read-ahead cache.
- Progress reporting no longer scans temporary trees or creates extra data
  copies.
- Successful builds now remove their per-game temporary workspace.

### 0.2.2

#### Added

- A self-contained Windows x64 build alongside macOS arm64.
- Complete English localization and a persistent **Русский / English**
  selector.
- Detailed batch progress with stage, substage, percentage, elapsed time, and
  estimated time remaining.
- Safe continuation after an error or cancellation.

#### Fixed

- Windows reads inventory from the selected temporary directory instead of
  `AppData`.
- All heavy temporary data is routed exclusively to the user-selected folder.
- Lower disk usage through hard links, atomic moves, and a safe copy fallback.
- Portable checksum formatting for release archives.

### 0.2.1

#### Added

- Exact build error messages in the GUI.
- Detection and automatic exclusion of byte-identical PKGs.

#### Fixed

- Patches correctly replace base files when a path differs only by letter case.
- Removed the duplicate directory scan before a build.
- Corrected conflict handling for multiple BASE and PATCH packages.

### 0.2.0

#### Added

- First public self-contained macOS arm64 application.
- Selection of individual PKGs or recursive directory scanning.
- BASE, PATCH, and DLC grouping by `TITLE_ID`.
- Complete `PKG → merged game → exFAT → FFPFSC` pipeline.
- Automatic verification of the generated container and required game files.
- Separate output and temporary directories; source PKGs are opened read-only.

#### Fixed

- Initial public release; maintenance fixes started with version 0.2.1.
