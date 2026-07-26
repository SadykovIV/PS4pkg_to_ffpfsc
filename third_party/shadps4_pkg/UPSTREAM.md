# shadPS4 PKG source subset

This directory contains only the C++ files needed by `ps4_pkg_extract`, derived
from shadPS4 v0.7.0 archive commit
`3b2c01272383e1fcd0b82c7873e1ebf1a641aada`.

The subset includes the local standalone/path-safety adjustments documented in
`docs/INITIAL_AUDIT.md`. Emulator UI, GPU, audio, Qt and runtime sources are not
included. The upstream GPL-2.0-or-later license is included as `LICENSE`.
