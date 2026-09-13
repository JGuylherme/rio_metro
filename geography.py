"""OSM extraction and geographic utilities."""
from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import json
import math
from pathlib import Path
import pickle

import mercantile
import mapbox_vector_tile
import numpy as np
import osmium
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write
from pyproj import Transformer
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, Polygon, box, mapping
from shapely.ops import polygonize, transform, unary_union
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'build' / 'RIO'
CACHE = ROOT / 'data'
BBOX = (-43.80, -23.10, -42.95, -22.70)
CLIP = box(*BBOX)
PROJECT = Transformer.from_crs(4326, 32723, always_xy=True).transform
UNPROJECT = Transformer.from_crs(32723, 4326, always_xy=True).transform
MERCATOR = Transformer.from_crs(4326, 3857, always_xy=True).transform
ROADS = {'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary',
         'primary_link', 'secondary', 'secondary_link', 'tertiary',
         'tertiary_link', 'residential', 'unclassified', 'living_street', 'service'}
SPEEDS = {'motorway': 75, 'trunk': 60, 'primary': 40, 'secondary': 35,
          'tertiary': 30, 'residential': 22, 'living_street': 12, 'service': 15}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')


def feature(geometry, properties):
    return {'type': 'Feature', 'geometry': mapping(geometry), 'properties': properties}


def collection(features):
    return {'type': 'FeatureCollection', 'features': features}


def parts(g, kind):
    if g.is_empty:
        return
    if g.geom_type == kind:
        yield g
    elif hasattr(g, 'geoms'):
        for child in g.geoms:
            yield from parts(child, kind)


def number(value, default):
    try:
        return float(str(value).split(';')[0].replace(' m', '').replace(',', '.'))
    except (TypeError, ValueError):
        return default


def extract(pbf):
    cached = CACHE / 'osm.pkl'
    if cached.exists():
        print('Reading cached Rio geography', flush=True)
        return pickle.loads(cached.read_bytes())
    nodes, labels = {}, []
    margin = box(BBOX[0]-.03, BBOX[1]-.03, BBOX[2]+.03, BBOX[3]+.03)
    bounds = margin.bounds
    print('Reading OSM nodes within Rio bounds', flush=True)
    for n in osmium.FileProcessor(str(pbf), entities=osmium.osm.NODE):
        if not n.location.valid():
            continue
        x, y = n.lon, n.lat
        if bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]:
            nodes[n.id] = (x, y)
            place, name = n.tags.get('place'), n.tags.get('name')
            if place and name and CLIP.covers(Point(x, y)):
                layer = ('city_labels' if place in {'city', 'town'} else
                         'suburb_labels' if place in {'suburb', 'village'} else
                         'neighborhood_labels')
                labels.append((layer, feature(Point(x, y), {'name': name})))
    print(f'{len(nodes):,} local nodes; reading ways', flush=True)
    ways = {}
    for w in osmium.FileProcessor(str(pbf), entities=osmium.osm.WAY):
        refs = [n.ref for n in w.nodes]
        if any(ref in nodes for ref in refs):
            ways[w.id] = (refs, dict(w.tags))
    relations = []
    for r in osmium.FileProcessor(str(pbf), entities=osmium.osm.RELATION):
        if r.tags.get('type') not in {'multipolygon', 'boundary'}:
            continue
        members = [(m.ref, m.role) for m in r.members if m.type == 'w']
        if any(ref in ways for ref, _ in members):
            relations.append((members, dict(r.tags)))
    result = nodes, ways, relations, labels
    cached.write_bytes(pickle.dumps(result, protocol=5))
    print(f'{len(ways):,} ways; {len(relations):,} polygon relations', flush=True)
    return result


def geography(raw):
    nodes, ways, relations, labels = raw
    buildings, roads, aeroways, coast, surfaces, edges = [], [], [], [], [], []
    used = set()

    def polygon_tags(tags):
        return any(k in tags for k in ('building', 'building:part', 'natural', 'landuse', 'leisure', 'aeroway', 'water', 'amenity'))

    def add_polygon(g, tags):
        if not g.is_valid:
            g = g.buffer(0)
        g = g.intersection(CLIP)
        for poly in parts(g, 'Polygon'):
            metric = transform(PROJECT, poly)
            if metric.area < 8:
                continue
            if tags.get('building') not in {None, 'no'}:
                h = max(3., min(300., number(tags.get('height'), number(tags.get('building:levels'), 2)*3)))
                cleaned = transform(UNPROJECT, metric.simplify(.15, preserve_topology=True))
                buildings.append(feature(cleaned, {'height': h, 'kind': 'building',
                    'height_known': bool(tags.get('height') or tags.get('building:levels')),
                    'use': tags.get('building', ''), 'name': tags.get('name', '')}))
            elif tags.get('aeroway') in {'runway', 'taxiway', 'apron'}:
                aeroways.append(feature(poly, {'roadType': 'runway', 'z_order': 0, 'area': metric.area}))
            elif tags.get('natural') == 'water' or 'water' in tags or tags.get('landuse') in {'reservoir', 'basin'}:
                surfaces.append(('water', feature(poly, {'kind': 'lake', 'sort_rank': 200})))
            elif tags.get('aeroway') == 'aerodrome':
                surfaces.append(('landuse', feature(poly, {'kind': 'aerodrome', 'sort_rank': 189})))
            elif tags.get('landuse') in {'commercial', 'retail'} or tags.get('amenity') in {'university', 'college', 'school'}:
                props = {'type': 'college'} if 'amenity' in tags else {'kind': tags['landuse']}
                surfaces.append(('commercial', feature(poly, props)))
            elif tags.get('landuse') in {'industrial', 'residential'}:
                surfaces.append((tags['landuse'], feature(poly, {'kind':tags['landuse'],'name':tags.get('name','')})))
            elif tags.get('natural') in {'wood', 'scrub', 'grassland', 'heath'} or tags.get('landuse') in {'forest', 'grass', 'recreation_ground'} or tags.get('leisure') in {'park', 'garden', 'nature_reserve', 'golf_course'}:
                surfaces.append(('landuse', feature(poly, {'kind': 'park', 'sort_rank': 189})))

    for members, tags in relations:
        if not polygon_tags(tags):
            continue
        outer, inner = [], []
        complete = True
        for ref, role in members:
            if ref not in ways or not all(n in nodes for n in ways[ref][0]):
                complete = False
                break
            coords = [nodes[n] for n in ways[ref][0]]
            if len(coords) >= 2:
                (inner if role == 'inner' else outer).append(LineString(coords))
        if complete and outer:
            g = unary_union(list(polygonize(unary_union(outer))))
            if inner:
                g = g.difference(unary_union(list(polygonize(unary_union(inner)))))
            if not g.is_empty:
                add_polygon(g, tags)
                used.update(ref for ref, _ in members)

    for wid, (refs, tags) in ways.items():
        # Split missing locations instead of inventing connecting segments.
        runs, run = [], []
        for ref in refs:
            if ref in nodes:
                run.append(ref)
            else:
                if len(run) >= 2: runs.append(run)
                run = []
        if len(run) >= 2: runs.append(run)
        for run in runs:
            coords = [nodes[n] for n in run]
            line = LineString(coords)
            if tags.get('natural') == 'coastline':
                coast.extend(parts(line.intersection(CLIP), 'LineString'))
            highway = tags.get('highway')
            if highway in ROADS:
                cls = 'highway' if highway.startswith(('motorway', 'trunk')) else 'major' if highway.startswith(('primary', 'secondary', 'tertiary')) else 'minor'
                structure = 'bridge' if tags.get('bridge') not in {None, 'no'} else 'tunnel' if tags.get('tunnel') not in {None, 'no'} else 'normal'
                for segment in parts(line.intersection(CLIP), 'LineString'):
                    roads.append(feature(segment, {'roadClass': cls, 'structure': structure, 'name': tags.get('name', tags.get('ref', ''))}))
                if tags.get('access') not in {'private', 'no'} and tags.get('motor_vehicle') != 'no':
                    speed = max(5, min(100, number(tags.get('maxspeed'), SPEEDS.get(highway, 25))))
                    oneway = tags.get('oneway', 'yes' if tags.get('junction') == 'roundabout' else 'no')
                    for a, b in zip(run, run[1:]):
                        if a == b or not CLIP.covers(Point(nodes[a])) or not CLIP.covers(Point(nodes[b])): continue
                        pa, pb = PROJECT(*nodes[a]), PROJECT(*nodes[b])
                        length = math.dist(pa, pb)
                        if length <= 0: continue
                        edges.append((a, b, length, length/(speed/3.6), oneway))
            if tags.get('aeroway') in {'runway', 'taxiway'} and coords[0] != coords[-1]:
                width = number(tags.get('width'), 45 if tags['aeroway'] == 'runway' else 20)
                g = transform(UNPROJECT, transform(PROJECT, line).buffer(width/2, cap_style=2)).intersection(CLIP)
                for poly in parts(g, 'Polygon'):
                    aeroways.append(feature(poly, {'roadType': 'runway', 'z_order': 0, 'osm_way_id': {str(i): c for i, c in enumerate(str(wid))}, 'area': transform(PROJECT, poly).area}))
            if wid not in used and len(run) == len(refs) and coords[0] == coords[-1] and len(coords) >= 4 and polygon_tags(tags):
                add_polygon(Polygon(coords), tags)

    # OSM coastline direction has land on the left. Polygonize against the
    # extraction rectangle, then classify faces with a right-side sea sample.
    coastline = unary_union(coast)
    faces = list(polygonize(unary_union([coastline, CLIP.boundary])))
    sea_samples = []
    for line in coast:
        coords = list(line.coords)
        a, b = max(zip(coords, coords[1:]), key=lambda ab: math.dist(*ab))
        dx, dy = b[0]-a[0], b[1]-a[1]
        norm = math.hypot(dx, dy)
        if norm:
            sea_samples.append(Point((a[0]+b[0])/2+dy/norm*1e-7, (a[1]+b[1])/2-dx/norm*1e-7))
    samples = STRtree(sea_samples)
    ocean_parts = [p for p in faces if len(samples.query(p, predicate='contains'))]
    if not ocean_parts:
        raise RuntimeError('Coastline did not produce an ocean polygon')
    ocean = unary_union(ocean_parts)
    assert ocean.covers(Point(-43.2, -23.06)), 'Missing Atlantic ocean'
    assert ocean.covers(Point(-43.15, -22.85)), 'Missing Guanabara Bay'
    assert not ocean.covers(Point(-43.2, -22.91)), 'Ocean covers central Rio'
    surfaces.append(('water', feature(ocean, {'kind': 'ocean', 'sort_rank': 200})))
    print(f'{len(buildings):,} buildings; {len(roads):,} roads; {len(aeroways)} airport polygons', flush=True)
    save(OUT/'roads.geojson', collection(roads))
    save(OUT/'runways_taxiways.geojson', collection(aeroways))
    save(CACHE/'buildings_cleaned.json', collection(buildings))
    save(CACHE/'surfaces.geojson', collection([f for _, f in surfaces]))
    return buildings, surfaces, labels, edges, nodes

