(function () {
    const api = window.SubwayBuilderAPI;
    if (!api) { console.error('[Rio] SubwayBuilderAPI indisponível.'); return; }
    const base = 'http://127.0.0.1:8080';
    api.registerCity({ ...__RIO_CITY_CONFIG__, mapImageUrl: base + '/RIO/thumbnail.png' });
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
