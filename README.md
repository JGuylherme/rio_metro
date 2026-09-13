# Rio de Janeiro — Subway Builder

A custom **Subway Builder map of the Rio de Janeiro Metropolitan Area**, created to bring the scale and urban complexity of Greater Rio into the game. The project covers Rio de Janeiro and a large portion of its surrounding metropolitan region, including the **Baixada Fluminense, Niterói, São Gonçalo, Japeri, and other nearby areas**, allowing players to design metro and rail networks across multiple cities rather than being limited to Rio's central urban area.

## Building the Map

The generated Subway Builder package is always written to **`dist/RIO.zip`**, while the unpacked files are stored in **`build/RIO/`**. Running a new generation overwrites these paths.

To rebuild the map using the downloaded data sources:

```sh
.venv/bin/python -u build_rio.py
```

Generating millions of buildings and population locations can take several hours. Previously downloaded geographic data in `data/` is reused, so a normal rebuild does not automatically download newer versions of every source.

To recreate only the ZIP package and update the preview without rebuilding the geographic data:

```sh
.venv/bin/python -u build_rio.py --package-only
```

The resulting package is `dist/RIO.zip`. Do not run multiple map generations at the same time.

## GitHub Release

To package the existing map data and verify the ZIP's CRC integrity:

```sh
.venv/bin/python -u package_rio.py
```

Upload **both `dist/RIO.zip` and `dist/manifest.json` as separate assets** of release `v2.0.0` (matching `map_settings.py` and the generated map config). The root `manifest.json` is the source for the standalone asset; it is copied on every packaging run. Generated assets stay in the ignored `dist/` directory.

The ZIP contains these files directly at its root:

```text
RIO.pmtiles
RIO_foundations.pmtiles
buildings_index.bin
config.json
demand_data.json
roads.geojson
runways_taxiways.geojson
ocean_depth_index.json.gz
```

The [Registry integrity validator](https://github.com/Subway-Builder-Modded/registry/blob/main/scripts/lib/integrity.ts) accepts `buildings_index.bin` or `buildings_index.json` (including gzip variants). Keep the generated binary index; renaming it to JSON would not convert its contents.

The manifest currently targets **only Subway Builder `1.7.0`**, based on the locally installed game and mapLoader configuration. This is a conservative compatibility target, not an in-game test result. Before publishing, import the ZIP with Railyard and test it in that game version. Packaging checks required files, map code/version and ZIP CRC integrity; it does not test gameplay. Broaden the compatibility range only after testing other versions.

After publishing the two assets, submit the map through the Registry's **Publish New Map** issue form and complete its data-quality questions. Population and employment methodology is documented in [EMPLOYMENT.md](EMPLOYMENT.md).
