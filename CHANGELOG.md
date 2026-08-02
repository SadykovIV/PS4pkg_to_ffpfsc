# История изменений / Changelog

Все выпуски используют единый формат: сначала перечислены новые возможности,
затем исправления и важные улучшения. Готовые сборки macOS arm64 и Windows x64
являются самодостаточными и не требуют установленного Python или внешних
приложений.

All releases use the same format: new capabilities first, followed by fixes and
important improvements. The ready-made macOS arm64 and Windows x64 builds are
self-contained and require neither Python nor external applications.

## Русский

### 0.2.7

#### Добавлено

- Третий режим источника: готовое распакованное дерево игры. Поддерживается
  плоский каталог с `eboot.bin` и `sce_sys/param.sfo`, а также структура
  `app/` + необязательный `patch/`, создаваемая игровыми дамперами. Исходное
  дерево используется только для чтения и никогда не переносится при merge.
- Поддержка явно обозначенных backport-слоёв. Имена с `backport`, `back-port`
  или `Fix<версия прошивки>` распознаются как дополнительный patch той же
  версии; порядок фиксируется как `base → обычные update → backport` и
  сохраняется в inventory и manifest.
- Ненулевые `USER_DEFINED_PARAM_1…4` из итогового `param.sfo` дополнительно
  зеркалируются как `userDefinedParam1…4` в `param.json` для совместимости
  запуска из образа. Сам `param.sfo` остаётся источником истины и сохраняется
  без переписывания.
- При наличии выбранных DLC режим `auto` теперь действительно создаёт
  отдельные проверенные DLC-образы вместо удаления подготовленного staging.

#### Исправлено

- Итоговый `param.sfo` теперь гарантированно остаётся байтовой копией
  последнего overlay: `CATEGORY=gp`, `APP_VER`, пользовательские параметры и
  другие поля патча больше не нормализуются по base-SFO.
- Windows extractor принимает Unicode-пути через широкую точку входа и
  сериализует пути как UTF-8. Исправлена обработка `™`, кириллицы и других
  символов как в имени PKG, так и во внутренних путях игры.
- Неподдерживаемые PKG остаются предупреждением и не блокируют сборку
  отмеченной поддерживаемой игры.
- Два разных patch одной версии больше не блокируют Overcooked 2, если один из
  них явно является backport-слоем. Неоднозначные варианты без маркера
  по-прежнему безопасно блокируются; в GUI лишний неоднозначный patch можно
  снять и собрать оставшийся валидный набор.
- Пустой или некорректный `APP_VER` блокирует только затронутую игру и больше
  не завершает всё сканирование с исключением.
- `unpack` и `merge` в CLI всегда пересканируют явно выбранные источники, а
  `list` показывает фактический порядок наложения patch.
- Resume распакованного дерева сравнивает полный tree signature и не
  переиспользует merge после изменения исходного файла.
- Добавлена проверка пересечения распакованного источника с временной рабочей
  областью и папкой результата. В GUI компоненты такого источника отображаются
  информационно, а выбор относится ко всему контейнеру.
- Публикация основного образа и отдельных DLC-артефактов стала атомарной:
  ошибка DLC не оставляет частичный набор, блокирующий повтор без `--force`.
- Создание иконки macOS больше не зависит от сломанного направления
  `iconset → icns` системной утилиты `iconutil` в macOS 26. Полный ICNS с
  вариантами 16–1024 пикселей формируется воспроизводимо самим проектом.

### 0.2.6

#### Добавлено

- Выбор формата результата: сжатый `FFPFSC` по умолчанию или несжатый raw
  `exFAT`. В режиме exFAT готовый образ формируется напрямую, а проверка читает
  только обязательные игровые файлы и метаданные — второй полный образ на
  диске не создаётся.
- Ручной выбор числа потоков сжатия MkPFS от 1 до количества доступных
  логических процессоров. Значение по умолчанию — половина логических
  процессоров, но не менее одного.
- Регрессионный тест для зашифрованной NP-метадаты: объявленные 532 байта
  `npbind.dat` извлекаются из полного 544-байтного AES-CBC ciphertext.

#### Исправлено

- Кнопка **«Отменить»** теперь завершает всё дерево процессов сборки на macOS и
  Windows, включая extractor и MkPFS, останавливает очередь выбранных игр и не
  оставляет фоновые процессы, продолжающие запись.
- Экстрактор корректно округляет хранимый размер зашифрованных NP-записей
  `0x400`–`0x403` до 16-байтной границы AES-CBC, расшифровывает полный последний
  блок и записывает только объявленный размер plaintext. Это устраняет
  повреждение последних байтов `npbind.dat`.
- Изменена ревизия extractor: временные деревья, созданные старой логикой,
  считаются устаревшими и не используются как корректный resumable-кэш.
- Проверка raw exFAT теперь побайтово сверяет выбранные обязательные файлы,
  валидирует внутренний SHA-1 `npbind.dat` и распознаёт exFAT по сигнатуре даже
  без расширения `.exfat`.
- Sidecar-файлы включают расширение образа в имя, поэтому FFPFSC и exFAT одной
  версии игры больше не перезаписывают manifest и ShadowMount-инструкцию друг
  друга.

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

### 0.2.7

#### Added

- A third source mode for an already unpacked game tree. Both a flat root with
  `eboot.bin` and `sce_sys/param.sfo`, and a dumper-style `app/` plus optional
  `patch/` layout are accepted. The selected tree remains read-only and is
  never consumed by the merge operation.
- Explicit backport-layer support. Names containing `backport`, `back-port`,
  or `Fix<firmware version>` are treated as an additional same-version patch;
  the fixed `base → ordinary updates → backport` order is recorded in the
  inventory and every build manifest.
- Non-zero `USER_DEFINED_PARAM_1…4` values from the final `param.sfo` are also
  projected as `userDefinedParam1…4` in `param.json` for image-launch
  compatibility. The original SFO remains authoritative and unchanged.
- With selected DLC, `auto` now emits separate verified DLC images instead of
  discarding the prepared staging tree.

#### Fixed

- The final `param.sfo` is guaranteed to remain a byte-for-byte copy of the
  last overlay. Patch `CATEGORY=gp`, `APP_VER`, user parameters, and other SFO
  fields are no longer normalized from the base package.
- The Windows helper now accepts wide command-line paths and serializes paths
  as UTF-8, fixing `™`, Cyrillic, and other non-ASCII characters in source PKG
  names and internal game paths.
- Unsupported PKGs remain warnings and no longer block a checked supported
  game.
- Same-version Overcooked 2 update and Fix5.05 packages can be composed when
  the latter is an explicit backport layer; ambiguous unmarked alternatives
  remain safely blocked. The GUI can deselect one ambiguous patch and build
  the remaining valid subset.
- An empty or malformed `APP_VER` now blocks only the affected game instead of
  terminating the complete scan with an exception.
- CLI `unpack` and `merge` always rescan explicitly selected sources, while
  `list` reports the actual patch overlay order.
- Unpacked-tree resume compares the complete tree signature and never reuses a
  merge after a source file changes.
- Unpacked sources are checked against temporary-workspace and output-path
  overlap. Their GUI component rows are informational, with selection applied
  to the complete container.
- Main-image and separate-DLC publication is atomic: a DLC failure leaves no
  partial new set that would require `--force` before retrying.
- macOS icon generation no longer depends on the broken `iconset → icns`
  direction of the system `iconutil` on macOS 26. The project now emits a
  complete, reproducible ICNS with 16-through-1024-pixel representations.

### 0.2.6

#### Added

- Output format selection: compressed `FFPFSC` by default or an uncompressed
  raw `exFAT` image. exFAT output is written directly and verification reads
  only required metadata, without creating a second full-size image.
- Manual MkPFS compression worker selection from 1 up to the available logical
  CPU count. The default is half of the logical CPUs, with a minimum of one.
- A regression test for encrypted NP metadata: a declared 532-byte
  `npbind.dat` is recovered from the complete 544-byte AES-CBC ciphertext.

#### Fixed

- **Cancel** now terminates the complete build process tree on macOS and
  Windows, including the extractor and MkPFS, stops the selected-game queue,
  and prevents detached background workers from continuing to write.
- The extractor now rounds the stored size of encrypted NP entries
  `0x400`–`0x403` to the 16-byte AES-CBC boundary, decrypts the complete final
  block, and writes only the declared plaintext size. This prevents corruption
  of the final `npbind.dat` bytes.
- The extractor revision was advanced so temporary trees produced by the old
  logic are treated as stale instead of being accepted as valid resumable
  cache entries.
- Raw exFAT verification now byte-compares the selected required files,
  validates the internal `npbind.dat` SHA-1, and detects exFAT by signature
  even when the file does not use the `.exfat` extension.
- Sidecar names now retain the image extension, preventing FFPFSC and exFAT for
  the same game version from overwriting each other's manifest and
  ShadowMount instructions.

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
