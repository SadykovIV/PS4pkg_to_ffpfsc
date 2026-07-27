# PS4 FFPFSC 0.2.3

## Русская версия

Версия 0.2.3 добавляет размер каждого PKG и примерный общий размер выбранных
игр в таблицу GUI. Прогресс распаковки и оставшееся время теперь рассчитываются
по реально записанным байтам с учётом размера base, patch и DLC.

Производительность чтения PKG с SMB/NAS на macOS улучшена: нативный extractor
держит один файловый дескриптор открытым и использует ограниченный 8 MiB
read-ahead cache вместо тысяч мелких чтений. Для расчёта прогресса временное
дерево не сканируется и дополнительные копии данных не создаются.

Сборки macOS arm64 и Windows x64 самодостаточны: внешние приложения, Python и
другие зависимости на целевой системе не требуются. После успешной сборки
временный каталог игры автоматически удаляется.

## English version

Version 0.2.3 adds every PKG size and the approximate total size of selected
games to the GUI. Extraction progress and its ETA now follow bytes actually
written, weighted by the source sizes of base, patch and DLC packages.

PKG reads from SMB/NAS are faster on macOS: the native extractor keeps one file
descriptor open and uses a bounded 8 MiB read-ahead cache instead of thousands
of small reads. Progress reporting does not scan the temporary tree or create
additional data copies.

The macOS arm64 and Windows x64 builds are self-contained and require no
external applications, Python installation or other runtime dependencies.
Successful builds automatically remove their per-game temporary workspace.
