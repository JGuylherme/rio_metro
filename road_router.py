"""Directed shortest driving paths shared by special-demand destinations."""
import math
import pickle
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree
from geography import PROJECT
from map_settings import DATA


class RoadRouter:
    def __init__(self):
        _, _, edges, nodes = pickle.loads((DATA / 'geography.pkl').read_bytes())
        ids = sorted({e[0] for e in edges} | {e[1] for e in edges})
        index = {node: i for i, node in enumerate(ids)}
        arcs = {}
        for a, b, length, seconds, direction in edges:
            directions = [(b, a)] if direction == '-1' else [(a, b)] if direction in {'yes', '1', 'true'} else [(a, b), (b, a)]
            for start, end in directions:
                key = (index[start], index[end])
                if key not in arcs or seconds < arcs[key][0]:
                    arcs[key] = (max(.001, seconds), length)
        rows, cols = zip(*arcs)
        graph = coo_matrix(([v[0] for v in arcs.values()], (rows, cols)), shape=(len(ids), len(ids))).tocsr()
        _, components = connected_components(graph, directed=True, connection='strong')
        keep = np.flatnonzero(components == np.bincount(components).argmax())
        self.graph = graph[keep][:, keep].T.tocsr()
        lengths = coo_matrix(([v[1] for v in arcs.values()], (rows, cols)), shape=graph.shape).tocsr()
        self.lengths = lengths[keep][:, keep].T.tocsr()
        positions = np.array([nodes[ids[i]] for i in keep])
        self.xy = np.column_stack(PROJECT(positions[:, 0], positions[:, 1]))
        self.tree = cKDTree(self.xy)

    def snap(self, locations):
        loc = np.asarray(locations)
        return self.tree.query(np.column_stack(PROJECT(loc[:, 0], loc[:, 1])))

    def to_destination(self, location, origins, max_access_m=1500):
        access, destination = self.snap([location])
        if access[0] > max_access_m:
            raise ValueError(f'Special destination too far from connected roads: {location}')
        origin_access, snapped = self.snap(origins)
        times, predecessors = dijkstra(self.graph, indices=int(destination[0]), return_predecessors=True)
        valid = np.flatnonzero(predecessors >= 0)
        edge_lengths = np.zeros(len(predecessors))
        edge_lengths[valid] = np.asarray(self.lengths[predecessors[valid], valid]).ravel()
        path_lengths = {int(destination[0]): 0.}
        result = []
        for offset, node in zip(origin_access, snapped):
            if offset > max_access_m or not math.isfinite(times[node]):
                result.append(None)
                continue
            cursor = int(node)
            trail = []
            while cursor not in path_lengths:
                previous = int(predecessors[cursor])
                if previous < 0:
                    raise ValueError('Broken shortest-path predecessor chain')
                trail.append((cursor, previous))
                cursor = previous
            for cursor, previous in reversed(trail):
                path_lengths[cursor] = path_lengths[previous] + edge_lengths[cursor]
            length = float(offset + access[0] + path_lengths[int(node)])
            # Access legs are explicit 20 km/h connectors, not fictitious graph arcs.
            seconds = times[node] + (offset + access[0]) / (20 / 3.6)
            result.append((max(1, round(length)), max(1, round(seconds))))
        return result
