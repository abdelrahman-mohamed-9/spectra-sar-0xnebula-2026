'use strict';
const advancedPanel = el('section', undefined, 'panel');
advancedPanel.id = 'phase3'; advancedPanel.hidden = true;
advancedPanel.innerHTML = `<div class="panel-heading"><div><div class="eyebrow">PHASE 3 · QUALITY & EXPOSURE</div><h2>Risk review map</h2></div><span class="tag">Exploratory</span></div>
<p id="phase3Summary"></p><p class="subtle">Local WGS84 vector map · north up · no external basemap. Confidence is a quality index, not a probability. Grey means risk cannot be calculated.</p>
<div class="controls"><label>Minimum confidence <input id="confidenceFilter" type="range" min="0" max="1" step="0.05" value="0"><output id="confidenceValue">0.00</output></label><label>Colour by <select id="mapMetric"><option value="risk">Risk</option><option value="confidence">Confidence</option></select></label><button id="mapZoomIn">Zoom +</button><button id="mapZoomOut">Zoom −</button><button id="mapReset">Reset</button></div>
<svg id="riskMap" role="img" aria-label="Interactive candidate risk map" width="100%" height="360"></svg>
<p id="zoneDetails" aria-live="polite">Select a zone to inspect exposure and evidence.</p><div class="table-scroll"><table><thead><tr><th>Zone</th><th>Confidence</th><th>Risk</th><th>People</th><th>Buildings</th><th>Road metres</th></tr></thead><tbody id="zoneRows"></tbody></table></div>
<details><summary>Processing evidence and source hashes</summary><pre id="phase3Evidence"></pre></details>`;
document.querySelector('footer').before(advancedPanel);
const phase3Style = document.createElement('link'); phase3Style.rel = 'stylesheet'; phase3Style.href = '/assets/phase3.css'; document.head.append(phase3Style);
let advancedData = null, mapView = null, mapOriginal = null;
const svgNS = 'http://www.w3.org/2000/svg';
function updateMapView() { $('riskMap').setAttribute('viewBox', mapView.join(' ')); }
function inspectZone(feature) {
 const props = feature.properties;
 document.querySelectorAll('#riskMap path').forEach(path => path.setAttribute('aria-pressed', String(path.getAttribute('aria-label') === props.id)));
 $('zoneDetails').textContent = `${props.id}: ${props.direction}, ${props.area_m2.toFixed(1)} m². Confidence ${(props.confidence * 100).toFixed(1)}% (uncalibrated). Risk: ${props.risk_level}. Evidence: ${props.evidence.join(', ')}. Source and output hashes are recorded below and available in Downloads.`;
}
function drawRiskMap() {
 if (!advancedData) return;
 $('riskMap').replaceChildren(); $('zoneRows').replaceChildren();
 const minimum = Number($('confidenceFilter').value); $('confidenceValue').textContent = minimum.toFixed(2);
 const bounds = advancedData.analysis.bounds_wgs84;
 const cosine = Math.cos((bounds[1] + bounds[3]) / 2 * Math.PI / 180);
 const point = coordinate => [coordinate[0] * cosine, -coordinate[1]];
 if (!mapView) {
  mapOriginal = [bounds[0] * cosine, -bounds[3], (bounds[2] - bounds[0]) * cosine, bounds[3] - bounds[1]];
  const coordinates = advancedData.zones.features.flatMap(feature => feature.geometry.type === 'Polygon' ? feature.geometry.coordinates.flat() : feature.geometry.coordinates.flat(2)).map(point);
  if (coordinates.length) {
   const horizontal = coordinates.map(value => value[0]), vertical = coordinates.map(value => value[1]);
   const left = Math.min(...horizontal), top = Math.min(...vertical), width = Math.max(...horizontal)-left, height = Math.max(...vertical)-top;
   mapOriginal = [left-width*0.1, top-height*0.1, width*1.2, height*1.2];
  }
  mapView = [...mapOriginal];
 }
 updateMapView();
 for (const feature of advancedData.zones.features.filter(item => item.properties.confidence >= minimum)) {
  const props = feature.properties, geometry = feature.geometry;
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  const path = document.createElementNS(svgNS, 'path');
  path.setAttribute('d', polygons.flatMap(polygon => polygon.map(ring => ring.map((coordinate, index) => (index ? 'L' : 'M') + point(coordinate).join(' ')).join(' ') + 'Z')).join(' '));
  path.setAttribute('fill-rule', 'evenodd');
  const colours = {unavailable:'#88949f',low:'#56c5ae',medium:'#efb65e',high:'#ec6767'};
  path.setAttribute('fill', $('mapMetric').value === 'risk' ? colours[props.risk_level] : `hsl(${props.confidence * 140} 60% 55%)`);
  path.setAttribute('tabindex', '0'); path.setAttribute('role', 'button'); path.setAttribute('aria-label', props.id);
  const title = document.createElementNS(svgNS, 'title'); title.textContent = props.id + ' · ' + props.risk_level; path.append(title);
  path.onclick = () => { if (!suppressMapClick) { inspectZone(feature); $('zoneDetails').scrollIntoView({block:'nearest',behavior:'smooth'}); } };
  path.onkeydown = event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); inspectZone(feature); } };
  $('riskMap').append(path);
  const row = el('tr'), button = el('button', props.id), cell = el('td'); button.onclick = () => inspectZone(feature); cell.append(button); row.append(cell);
  for (const value of [(props.confidence * 100).toFixed(1) + '%', props.risk_score === null ? 'Unavailable' : props.risk_level + ' · ' + props.risk_score, props.population.estimated_residents, props.mapped_buildings, props.mapped_roads_m === null ? null : props.mapped_roads_m.toFixed(1)]) row.append(el('td', value === null ? 'Unavailable' : String(value)));
  $('zoneRows').append(row);
 }
}
const phase2Show = show;
show = async function(record, gen) {
 await phase2Show(record, gen);
 if (!record.result.phase3) return;
 const data = await json('/jobs/' + record.id + '/phase3');
 if (gen !== generation) return;
 advancedData = data; mapView = null; advancedPanel.hidden = false;
 $('phase3Summary').textContent = `${data.analysis.retained_pixels} retained pixels in ${data.analysis.zones} zones. Missing inputs: ${data.analysis.data_gaps.join(', ') || 'none declared'}. Risk policy is experimental. AOI WGS84: ${data.analysis.bounds_wgs84.map(value => value.toFixed(4)).join(', ')}.`;
 if (data.analysis.population_source) $('phase3Summary').append(document.createTextNode(` Population: ${data.analysis.population_source.product || 'count raster'}, year ${data.analysis.population_source.year || 'unspecified'}. Model estimates, not observed residents; zero does not certify absence.`));
 $('phase3Evidence').textContent = JSON.stringify(data.evidence, null, 2); drawRiskMap();
};
const phase2Select = selectJob;
selectJob = async function(id) { advancedPanel.hidden = true; advancedData = null; return phase2Select(id); };
$('disconnect').addEventListener('click', () => { advancedPanel.hidden = true; advancedData = null; $('phase3Evidence').textContent = ''; $('riskMap').replaceChildren(); $('zoneRows').replaceChildren(); });
$('confidenceFilter').oninput = drawRiskMap; $('mapMetric').onchange = drawRiskMap;
function zoomMap(factor) { if (!mapView) return; mapView = [mapView[0] + mapView[2] * (1-factor)/2, mapView[1] + mapView[3] * (1-factor)/2, mapView[2]*factor, mapView[3]*factor]; updateMapView(); }
$('mapZoomIn').onclick = () => zoomMap(0.7); $('mapZoomOut').onclick = () => zoomMap(1/0.7);
$('mapReset').onclick = () => { if (mapOriginal) { mapView = [...mapOriginal]; updateMapView(); } };
let dragStart = null, suppressMapClick = false;
$('riskMap').onpointerdown = event => {
 if (!mapView || event.button !== 0) return;
 suppressMapClick = false;
 dragStart = {x:event.clientX,y:event.clientY,view:[...mapView]};
};
$('riskMap').onpointermove = event => {
 if (!dragStart) return;
 const dx=event.clientX-dragStart.x, dy=event.clientY-dragStart.y;
 if (!suppressMapClick && Math.hypot(dx,dy) < 5) return;
 // Capturing on pointerdown retargets zone clicks to the SVG background.
 suppressMapClick = true;
 $('riskMap').setPointerCapture(event.pointerId);
 const rect = $('riskMap').getBoundingClientRect();
 const scale = Math.max(dragStart.view[2]/rect.width, dragStart.view[3]/rect.height);
 mapView = [dragStart.view[0]-dx*scale,dragStart.view[1]-dy*scale,...dragStart.view.slice(2)];
 updateMapView();
};
$('riskMap').onpointerup = $('riskMap').onpointercancel = event => {
 dragStart = null;
 if ($('riskMap').hasPointerCapture(event.pointerId)) $('riskMap').releasePointerCapture(event.pointerId);
};
$('riskMap').onpointerleave = () => { if (!suppressMapClick) dragStart = null; };
