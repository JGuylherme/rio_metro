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
