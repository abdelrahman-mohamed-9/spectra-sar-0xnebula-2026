"""Evidence-backed explanations, review alerts, comparison and portable reports."""

import base64
import html
import json

from pyproj import Transformer
from shapely import transform
from shapely.geometry import box, shape
from shapely.ops import unary_union

from .integrity import verified_bytes


def read_entifact(queue, row, name):
    receipt = json.loads(row['receipt'] or '{}').get(name)
    if receipt is None:
        raise ValueError('This historical run does not include the required artifact')
    return verified_bytes(queue.runs / row['id'], name, receipt)


def document(queue, row, name):
    return json.loads(read_entifact(queue, row, name))


def insights(queue, row):
    analysis = document(queue, row, 'Phase3/analysis.json')
    features = document(queue, row, 'Phase3/risk-zones.geojson')['features']
    manifest = document(queue, row, 'sources/nisar/manifest.json')
    quality = document(queue, row, 'M1/quality-report.json')
    zones, alerts = [], []
    for feature in features:
        props = feature['properties']
        people = props['population']['estimated_residents']
        exposure = (people or 0) > 0 or (props['mapped_buildings'] or 0) > 0 or (props['mapped_roads_m'] or 0) > 0
        priority = 'exposure_review' if exposure else 'quality_review' if props['confidence'] < 0.5 else 'standard_review'
        direction = 'decreased' if props['direction'] == 'decrease' else 'increased'
        explanation = f"Radar backscatter {direction} across {props['area_m2']:.1f} square meters. This region passed stability, minimum-size and valid-edge screening."
        reason = 'Estimated residents or mapped assets overlap this region; review exposure first.' if exposure else 'Quality is below the 0.5 review threshold; inspect alignment and processing.' if priority == 'quality_review' else 'Candidate change needs review; available data show no positive exposure.'
        zones.append({**props, 'explanation_en': explanation, 'review_priority':priority, 'priority_reason_en':reason,
            'interpretation_en':'Backscatter change alone does not establish flooding, damage or glacier velocity.',
            'source_dates':[manifest[side]['acquired_utc'] for side in ('before','after')]})
        if props['area_m2'] >= 1000 and props['confidence'] >= 0.5:
            alerts.append({'id':f"candidate-{props['id']}", 'zone_id':props['id'], 'kind':'candidate_review',
                'title_en':'Change region flagged for review', 'reason_en':f"Area {props['area_m2']:.1f} m² >= 1000 and quality score {props['confidence']:.3f} >= 0.5.",
                'evidence':props['evidence'], 'official_warning':False})
        if exposure:
            alerts.append({'id':f"exposure-{props['id']}", 'zone_id':props['id'], 'kind':'mapped_exposure',
                'title_en':'Overlap with estimated residents or mapped assets', 'reason_en':reason, 'evidence':props['evidence'], 'official_warning':False})
    if analysis['data_gaps']:
        alerts.append({'id':'coverage-review', 'zone_id':None, 'kind':'data_quality', 'title_en':'Review exposure-data coverage',
            'reason_en':'Missing exposure data or incomplete coverage: '+', '.join(analysis['data_gaps']),
            'evidence':['sources/geography/geography-source.json'], 'official_warning':False})
    if quality.get('processing_identifiers', {}).get('before') != quality.get('processing_identifiers', {}).get('after'):
        alerts.append({'id':'processing-review','zone_id':None,'kind':'data_quality','title_en':'Different processing versions',
            'reason_en':'Processing differences may contribute to observed changes; independent validation is required.', 'evidence':['M1/quality-report.json'],'official_warning':False})
    zones.sort(key=lambda item: ({'exposure_review':0,'quality_review':1,'standard_review':2}[item['review_priority']], -item['area_m2']))
    return {'schema_version':'3.2','job_id':row['id'],'dataset':row['dataset'],'pair_id':manifest['pair_id'],
        'dates':[manifest[side]['acquired_utc'] for side in ('before','after')], 'candidate_mode':row['candidate_mode'],
        'zones':zones,'alerts':alerts,'analysis':analysis,'quality':quality,
        'alert_policy':{'version':'1.0','candidate_min_enea_m2':1000,'candidate_min_confidence':0.5,'delivery':'in_app_only','meaning':'Review rules, not validated hazard thresholds'},
        'movement':{'status':'INPUT_REQUIRED','required':['GOFF displacement product for the existing AOI','quality layers, units and acquisition dates'], 'message_en':'Glacier movement requires displacement data; current imagery supports backscatter-change analysis only.'}}


def comparison(queue, left, right):
    first = insights(queue, left)
    second = insights(queue, right)
    left_bounds = box(*first['analysis']['bounds_wgs84'])
    right_bounds = box(*second['analysis']['bounds_wgs84'])
    overlap = left_bounds.intersection(right_bounds).area / max(left_bounds.area, right_bounds.area)
    if overlap < 0.99:
        raise ValueError('Choose runs covering the same AOI (at least 99% common bounding extent)')
    manifests = [document(queue, row, 'sources/nisar/manifest.json') for row in (left,right)]
    if manifests[0].get('sensor') != manifests[1].get('sensor') or manifests[0]['polarizations'] != manifests[1]['polarizations']:
        raise ValueError('Sensor and polarization must match')
    same_pair = all(read_entifact(queue,left,f'sources/nisar/{manifests[0][side]["raster_files"][manifests[0]["polarizations"][0]]}') == read_entifact(queue,right,f'sources/nisar/{manifests[1][side]["raster_files"][manifests[1]["polarizations"][0]]}') for side in ('before','after'))
    projector = Transformer.from_crs('EPSG:4326','EPSG:6933',always_xy=True)
    footprints = []
    for row in (left,right):
        geometry = unary_union([shape(item['geometry']) for item in document(queue,row,'Phase3/risk-zones.geojson')['features']])
        footprints.append(transform(geometry,projector.transform,interleaved=False))
    union = footprints[0].union(footprints[1]).area
    return {'left':{'id':left['id'],'dates':first['dates'],'mode':first['candidate_mode']},
        'right':{'id':right['id'],'dates':second['dates'],'mode':second['candidate_mode']},
        'same_observations':same_pair,'comparison_type':'same_pair_processing_comparison' if same_pair else 'different_observation_pairs',
        'area_before_m2':footprints[0].area,'area_after_m2':footprints[1].area,
        'area_difference_m2':footprints[1].area-footprints[0].area,
        'footprint_iou':footprints[0].intersection(footprints[1]).area/union if union else None,
        'retained_pixel_difference':second['analysis']['retained_pixels']-first['analysis']['retained_pixels'],
        'interpretation_en':'Same observations: differences reflect analysis settings, not change over time.' if same_pair else 'Descriptive comparison of two observation pairs; not a velocity measurement or forecast.',
        'limitations':['Footprints compare any retained change, not signed-class agreement','Matching extents do not certify radiometric or geometric compatibility']}


def report_html(queue, row):
    data = insights(queue,row)
    escape = lambda value: html.escape(str(value))
    images = {name:base64.b64encode(read_entifact(queue,row,f'preview/{name}.png')).decode() for name in ('before','after',row['candidate_mode'])}
    zones = document(queue,row,'Phase3/risk-zones.geojson')['features']
    polygons = []
    for feature in zones:
        geometry = feature['geometry']
        for polygon in ([geometry['coordinates']] if geometry['type']=='Polygon' else geometry['coordinates']):
            polygons.append(polygon)
    bounds = data['analysis']['bounds_wgs84']
    paths = ''.join('<path fill-rule="evenodd" d="'+ ' '.join(' '.join(('M' if index==0 else 'L')+f'{(point[0]-bounds[0])/(bounds[2]-bounds[0])*800:.3f},{(bounds[3]-point[1])/(bounds[3]-bounds[1])*400:.3f}' for index,point in enumerate(ring))+'Z' for ring in polygon)+'"/>' for polygon in polygons)
    rows = ''.join('<tr>'+''.join('<td>'+escape(value)+'</td>' for value in (zone['id'],zone['explanation_en'],f"{zone['confidence']*100:.1f}%",zone['population']['estimated_residents'] if zone['population']['estimated_residents'] is not None else 'Unavailable',zone['mapped_buildings'] if zone['mapped_buildings'] is not None else 'Unavailable',zone['mapped_roads_m'] if zone['mapped_roads_m'] is not None else 'Unavailable',zone['priority_reason_en']))+'</tr>' for zone in data['zones'])
    receipts = json.loads(row['receipt'])
    hashes = '\n'.join(name+'  '+receipt['sha256'] for name,receipt in receipts.items())
    alerts = ''.join('<li>'+escape(alert['title_en']+' — '+alert['reason_en'])+'</li>' for alert in data['alerts']) or '<li>No alerts under the current rules; this does not establish absence of hazards.</li>'
    figures = ''.join(f'<figure><img alt="{name}" src="data:image/png;base64,{image}"><figcaption>{name}</figcaption></figure>' for name,image in images.items())
    return f'''<!doctype html><html lang="en" dir="ltr"><meta charset="utf-8"><title>SPECTRA Analysis Report</title>
    <style>body{{font:16px Arial,sans-serif;max-width:1100px;margin:35px auto;padding:20px;color:#152b3e}}h1,h2{{color:#126e70}}.figures{{display:flex;gap:15px}}figure{{flex:1;margin:0}}img{{width:100%}}table{{border-collapse:collapse;width:100%;font-size:12px}}td,th{{border:1px solid #bbb;padding:8px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;direction:ltr;font-size:10px}}svg{{background:#edf5f5;width:100%}}path{{fill:#237e82}}@media print{{body{{margin:0}}tr,figure{{break-inside:avoid}}h2{{break-after:avoid}}}}</style>
    <h1>SPECTRA — Change and Exposure Report</h1><p>Use your browser Print menu and Save as PDF. This self-contained file includes imagery and evidence.</p>
    <p>Analysis: {escape(row['id'])}<br>Source: {escape(data['pair_id'])}<br>Acquisition dates: {escape(' → '.join(data['dates']))}<br>Screen: {escape(data['candidate_mode'])}</p>
    <p>Exploratory analysis. Confidence is an uncalibrated quality indicator; overlap is not confirmed damage. Alerts request review and are not emergency warnings.</p>
    <h2>Before, after and selected candidate screen</h2><div class="figures">{figures}</div>
    <h2>Retained change regions</h2><p>Schematic in geographic coordinates; not a basemap or a distance scale.</p><svg viewBox="0 0 800 400" role="img" aria-label="Change regions">{paths}</svg>
    <table><tr><th>Region</th><th>Explanation</th><th>Quality</th><th>Estimated residents</th><th>Mapped buildings</th><th>Roads (m)</th><th>Priority reason</th></tr>{rows}</table>
    <h2>Review alerts</h2><ul>{alerts}</ul><h2>Population source and limitations</h2><pre>{escape(json.dumps(data['analysis'].get('population_source'),ensure_ascii=False,indent=2))}</pre>
    <p>{escape(data['movement']['message_en'])}</p><pre>{escape(json.dumps(data['analysis']['data_gaps'],ensure_ascii=False))}</pre>
    <h2>Evidence file hashes (SHA-256)</h2><p>Local integrity hashes, not independent signatures from the data provider.</p><pre>{escape(hashes)}</pre></html>'''
