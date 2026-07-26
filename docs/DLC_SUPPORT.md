# DLC support

DLC is recognized only when `CATEGORY == "ac"`. The entitlement label is accepted
only from a three-part `CONTENT_ID` when its final component is exactly 16
characters from `[A-Z0-9_]`.

Every extracted DLC is preserved at:

`unpacked/<TITLE_ID - title>/merged/addcont/<ENTITLEMENT_LABEL>/`

Its metadata records source/package/tree hashes and
`runtime_support_status=packaged_not_runtime_verified`.

The audited ShadowMountPlus source does not prove PS4 addcont mounting or
registration, and no safe system API workflow was confirmed. Therefore default
`auto` keeps DLC prepared and separate, `off` excludes it from output only,
and no mode claims runtime support. Direct `addcont.db`/`app.db` edits are not made.
The main base+patch image remains independent of DLC status.

