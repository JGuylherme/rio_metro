(function () {
    const api = window.SubwayBuilderAPI;
    if (!api) { console.error('[Rio] SubwayBuilderAPI indisponível.'); return; }
    const base = 'http://127.0.0.1:8080';
    api.registerCity({ ...{"name": "Rio de Janeiro", "code": "RIO", "description": "Build a rail network across Greater Rio, connecting Rio de Janeiro, the Baixada Fluminense, Niterói, São Gonçalo and the wider metropolitan area.", "population": 11491836, "initialViewState": {"zoom": 10.5, "latitude": -22.84, "longitude": -43.3, "bearing": 0}, "minZoom": 8, "buildingZoomOffset": -0.75}, mapImageUrl: base + '/RIO/thumbnail.png' });
    api.cities.registerTab({ id: 'BR', label: 'BR', emoji: '🇧🇷', cityCodes: ['RIO'] });
    api.cities.setCityDataFiles('RIO', {
        buildingsIndex: base + '/data/RIO/buildings_index.bin',
        demandData: base + '/data/RIO/demand_data.json',
        roads: base + '/data/RIO/roads.geojson',
        runwaysTaxiways: base + '/data/RIO/runways_taxiways.geojson',
        oceanDepthIndex: base + '/data/RIO/ocean_depth_index.json.gz'
    });
    api.map.setTileURLOverride({
        cityCode: 'RIO', tilesUrl: base + '/RIO/{z}/{x}/{y}.mvt',
        foundationTilesUrl: base + '/RIO_foundations/{z}/{x}/{y}.mvt', maxZoom: 15
    });
    api.map.setDefaultLayerVisibility('RIO', { buildingFoundations: true, oceanFoundations: false });
    api.map.registerSource('rio-scenery', {
        type: 'vector', tiles: [base + '/RIO/{z}/{x}/{y}.mvt'], minzoom: 6, maxzoom: 15,
        bounds: [-44.06, -23.24, -42.67, -22.40]
    });
    api.map.registerLayer({
        id: 'rio-scenery-roads', type: 'line', source: 'rio-scenery',
        'source-layer': 'scenery_roads',
        paint: { 'line-color': '#8a9195', 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.35, 14, 1.6], 'line-opacity': 0.65 }
    });
    api.hooks.onMapReady(function (map) {
        if (api.utils.getCityCode() !== 'RIO') return;
        map.setMaxBounds([[-44.06, -23.24], [-42.67, -22.40]]);
    });
    console.log('[Rio] Censo 2022, mapa ampliado e profundidades carregados.');
})();
