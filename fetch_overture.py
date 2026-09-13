"""Download public Overture building footprints for the visual extent."""
from pathlib import Path
import duckdb

Path('data').mkdir(parents=True,exist_ok=True)
con=duckdb.connect(config={'extension_directory':'data/duckdb_extensions'})
con.execute('INSTALL httpfs; LOAD httpfs;')
con.execute("SET s3_region='us-west-2'; SET threads=4; SET memory_limit='3GB';")
source='s3://overturemaps-us-west-2/release/2026-08-19.0/theme=buildings/type=building/*'
print('Downloading Overture footprints for greater Rio',flush=True)
con.execute(f"""COPY (
 SELECT id, geometry, height, num_floors, subtype, class
 FROM read_parquet('{source}', hive_partitioning=1)
 WHERE bbox.xmin < -42.67 AND bbox.xmax > -44.06
   AND bbox.ymin < -22.40 AND bbox.ymax > -23.24
) TO 'data/overture.parquet' (FORMAT PARQUET)""")
print(con.execute("SELECT count(*) FROM 'data/overture.parquet'").fetchone(),flush=True)
