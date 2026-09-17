(function () {
    const api = window.SubwayBuilderAPI;
    if (!api || window.__rioMenuInstalled) return;
    window.__rioMenuInstalled = true;
    const originalFetch = globalThis.fetch.bind(globalThis);
    globalThis.fetch = async function (input, init) {
        const response = await originalFetch(input, init);
        const url = typeof input === 'string' ? input : input.url || String(input);
        if (!/\/cityPopulations\.json(?:[?#]|$)/.test(url) || !response.ok) return response;
        const data = await response.clone().json();
        if (!Array.isArray(data)) return response;
        const rows = data.filter(city => city.code !== 'RIO');
        rows.push({ code: 'RIO', population: 11491836 });
        const headers = new Headers(response.headers);
        headers.delete('content-length'); headers.delete('content-encoding');
        headers.set('content-type', 'application/json');
        return new Response(JSON.stringify(rows), { status: response.status, headers });
    };
    api.cities.registerTab({ id: 'BR', label: 'BR', emoji: '🇧🇷', cityCodes: ['RIO'] });
    api.map.setDefaultLayerVisibility('RIO', { oceanFoundations: false });
})();

// Thin waterways and shorelines need line layers as well as water polygons.
(function () {
    const api = window.SubwayBuilderAPI;
    if (!api || window.__rioSurfaceLayersInstalled) return;
    window.__rioSurfaceLayersInstalled = true;
    let activeMap;
    let pending = false;
    function update() {
        pending = false;
        const map = activeMap;
        const code = String(api.utils.getCityCode() || '').split(':').pop();
        if (!map || code !== 'RIO' || !map.getSource('general-tiles')) return;
        const dark = api.ui?.getResolvedTheme?.() === 'dark';
        const colors = api.gameState?.getMapColors?.() || {};
        const water = colors.water || (dark ? '#294d60' : '#91bccf');
        const layers = [
            { id: 'rio-waterways', type: 'line', source: 'general-tiles', 'source-layer': 'waterways', minzoom: 8,
              paint: { 'line-color': water, 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.5, 12, 1.2, 16, 2.2] } },
            { id: 'rio-coastline', type: 'line', source: 'general-tiles', 'source-layer': 'coastline',
              paint: { 'line-color': dark ? '#527888' : '#648e9f', 'line-width': ['interpolate', ['linear'], ['zoom'], 6, 0.3, 13, 0.7, 16, 1.1], 'line-opacity': 0.75 } },
            { id: 'rio-scenery-roads', type: 'line', source: 'general-tiles', 'source-layer': 'scenery_roads',
              paint: { 'line-color': dark ? '#69757a' : '#959e9f', 'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.3, 14, 1.2], 'line-opacity': 0.7 } }
        ];
        const before = ['buildings-3d', 'building-foundations'].find(id => map.getLayer(id));
        for (const layer of layers) if (!map.getLayer(layer.id)) map.addLayer(layer, before);
    }
    function schedule() {
        if (pending) return;
        pending = true;
        setTimeout(update, 0);
    }
    api.hooks.onMapReady(function (map) {
        if (activeMap) activeMap.off('styledata', schedule);
        activeMap = map || api.utils.getMap();
        if (!activeMap) return;
        activeMap.on('styledata', schedule);
        schedule();
    });
    api.hooks.onCityLoad(schedule);
})();
