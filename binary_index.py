"""Independent SBBI format validation."""
import struct
import numpy as np

def binary(path):
    data = path.read_bytes()
    header = struct.unpack_from('<4sBBH8I6d', data)
    magic, version, _, _, n, cols, rows, rings, coords, cells, refs, reserved, cell_size, depth, west, south, east, north = header
    assert magic == b'SBBI' and version == 1
    assert n > 1000 and cols > 0 and rows > 0 and cell_size > 0
    assert -44 < west < east < -42 and -24 < south < north < -22
    offset = 88

    def read(dtype, count):
        nonlocal offset
        result = np.frombuffer(data, dtype=dtype, count=count, offset=offset)
        offset += result.nbytes
        return result

    boxes = read('<f8', n*4).reshape(-1,4)
    depths = read('<f4', n)
    assert np.isfinite(boxes).all() and np.isfinite(depths).all()
    assert (boxes[:,0] <= boxes[:,2]).all() and (boxes[:,1] <= boxes[:,3]).all()
    assert (depths > 0).all() and depths.max() <= depth
    offset = (offset+7)&~7
    ring_offsets = read('<u4', n+1)
    coord_offsets = read('<u4', rings+1)
    assert ring_offsets[0] == 0 and ring_offsets[-1] == rings
    assert coord_offsets[0] == 0 and coord_offsets[-1] == coords
    assert (np.diff(ring_offsets.astype('int64')) >= 1).all()
    assert (np.diff(coord_offsets.astype('int64')) >= 4).all()
    offset = (offset+7)&~7
    vertices = read('<f8', coords*2).reshape(-1,2)
    assert np.isfinite(vertices).all()
    assert ((vertices[:,0] >= west-1e-5) & (vertices[:,0] <= east+1e-5)).all()
    assert ((vertices[:,1] >= south-1e-5) & (vertices[:,1] <= north+1e-5)).all()
    assert np.array_equal(vertices[coord_offsets[:-1]], vertices[coord_offsets[1:]-1])
    row_starts = read('<u4', rows+1)
    cell_columns = read('<u4', cells)
    ref_offsets = read('<u4', cells+1)
    building_ids = read('<u4', refs)
    assert row_starts[0] == 0 and row_starts[-1] == cells
    assert (np.diff(row_starts.astype('int64')) >= 0).all()
    assert (cell_columns < cols).all()
    assert ref_offsets[0] == 0 and ref_offsets[-1] == refs
    assert (np.diff(ref_offsets.astype('int64')) >= 1).all()
    assert (building_ids < n).all()
    assert len(np.unique(building_ids)) == n
    assert offset == len(data), (offset,len(data))
    # Every grid entry must overlap the referenced building's bounding box.
    lon_step = cell_size/np.cos(np.deg2rad((south+north)/2))
    for row in range(rows):
        for cell in range(int(row_starts[row]), int(row_starts[row+1])):
            bb = boxes[building_ids[ref_offsets[cell]:ref_offsets[cell+1]]]
            x = west+int(cell_columns[cell])*lon_step
            y = south+row*cell_size
            assert (bb[:,2] >= x-1e-8).all() and (bb[:,0] <= x+lon_step+1e-8).all()
            assert (bb[:,3] >= y-1e-8).all() and (bb[:,1] <= y+cell_size+1e-8).all()
    return {'buildings': n, 'rings': rings, 'vertices': coords, 'grid_cells': cells, 'bytes': len(data)}

