# PS4 FFPFSC 0.2.4

## Русская версия

Версия 0.2.4 исправляет аварийное завершение Windows extractor с кодом
`0xC0000374` при распаковке patch-PKG, содержащих AES-записи с размером, не
кратным 16 байтам. Последний блок теперь безопасно дополняется нулями и
обрезается до исходного размера без выхода за границы буфера.

Игровой `sce_sys/param.json`, содержащий только `gameIntent`, теперь аккуратно
дополняется полями `titleId`, `titleName` и `localizedParameters`, необходимыми
ShadowMountPlus. Исходные игровые поля и исходные PKG не изменяются.

Также удалена завышенная проверка свободного места в размере 2,2× всех PKG.
Перед упаковкой используются точные проверки целевого диска и временных PFSC
spool-файлов, встроенные в MkPFS.

Исправления проверены C++-тестами, AddressSanitizer, малым patch-PKG It Takes
Two и patch-PKG Gran Turismo 7. Сборки macOS arm64 и Windows x64
самодостаточны и не требуют внешних приложений или установленного Python.
Временное состояние распаковки от более старых версий один раз пересоздаётся,
чтобы исключить повторное использование данных старого extractor.

## English version

Version 0.2.4 fixes Windows extractor crashes with code `0xC0000374` while
processing patch PKGs whose AES metadata entry length is not divisible by
16 bytes. The final block is now safely zero-padded and truncated to its
original length without accessing memory outside the buffer.

A game-provided `sce_sys/param.json` containing only `gameIntent` is now
augmented with the `titleId`, `titleName`, and `localizedParameters` fields
required by ShadowMountPlus. Original game metadata and source PKGs remain
unchanged.

The overly conservative free-space check requiring 2.2× the total PKG size was
also removed. Packing now relies on MkPFS's exact destination and temporary PFSC
spool checks.

The fixes were verified with C++ regression tests, AddressSanitizer, the small
It Takes Two patch PKG, and the Gran Turismo 7 patch PKG. The macOS arm64 and
Windows x64 builds are self-contained and require no external applications or
Python installation. Temporary extraction state from earlier versions is
rebuilt once to prevent reuse of data produced by the old extractor.
