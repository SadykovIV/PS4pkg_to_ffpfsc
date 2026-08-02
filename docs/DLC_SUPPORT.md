# DLC support

DLC is recognized only when `CATEGORY == "ac"`. The entitlement label is accepted
only from a three-part `CONTENT_ID` when its final component is exactly 16
characters from `[A-Z0-9_]`.

Every extracted DLC is preserved at:

`unpacked/<TITLE_ID - title>/merged/addcont/<ENTITLEMENT_LABEL>/`

Its metadata records the cheap source identity and structural tree signature and
`runtime_support_status=packaged_not_runtime_verified`.

Default `auto` and explicit `separate` create one additional verified image per
selected entitlement, named with `[DLC <ENTITLEMENT_LABEL>]`. `off` does not
publish those images. DLC is never copied into the main app tree because PS4
addcont has separate entitlement, mount, and registration semantics.

The audited ShadowMountPlus source does not yet prove a complete PS4 addcont
mount/registration workflow. Therefore the converter records
`runtime_supported=false` and does not claim that a correctly generated DLC
image will become visible in the game. Direct `addcont.db`/`app.db` edits are
not made. The main base+patch image remains independent of DLC status.
