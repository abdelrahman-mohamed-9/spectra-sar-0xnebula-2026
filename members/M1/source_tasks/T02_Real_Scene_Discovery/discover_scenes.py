#!/usr/bin/env python3
"""SPECTRA-SAR M1 T02: discover actual NASA CMR NISAR products near Juneau.

Uses the public NASA Common Metadata Repository API (no Earthdata login for search).
No synthetic satellite observations are created. Candidate pairs require scientific T03 validation.
"""
import argparse
import datetime as dt
import itertools
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = 'https://cmr.earthdata.nasa.gov/search/granules.json'
UTC = dt.timezone.utc
TODAY = dt.datetime.now(UTC).strftime('%Y-%m-%d')
AREAS = {
    # Approximate *search* extents only, not final scientific AOIs.
    'flood_mendenhall_valley': [-134.70, 58.33, -134.40, 58.55],
    'glacier_mendenhall': [-134.69, 58.44, -134.30, 58.70],
}
COLLECTIONS = {
    'GCOV': {
        'PROVISIONAL': ('NISAR_L2_GCOV_PROVISIONAL_V1', '2026-06-17T00:00:00Z', '2026-10-23T23:59:59Z'),
        'VALIDATED': ('NISAR_L2_GCOV_V1', '2026-10-21T00:00:00Z', None),
    },
    'GOFF': {
        'PROVISIONAL': ('NISAR_L2_GOFF_PROVISIONAL_V1', '2026-06-17T00:00:00Z', '2026-10-23T23:59:59Z'),
        'VALIDATED': ('NISAR_L2_GOFF_V1', '2026-10-21T00:00:00Z', None),
    },
}
FLOOD_EVENTS = ['2026-08-13', '2026-10-02']  # NOAA/NWS documented outburst floods


def iso(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace('Z', '+00:00')).astimezone(UTC)
    except (ValueError, TypeError):
        return None


def search_url(short_name, bbox, start, end, page=1, page_size=200):
    params = {'short_name': short_name, 'bounding_box': ','.join(map(str, bbox)),
              'temporal': ','.join([start, end or TODAY + 'T23:59:59Z']),
              'page_size': page_size, 'page_num': page, 'sort_key': 'start_date'}
    return BASE + '?' + urllib.parse.urlencode(params)


def cmr_query(url, timeout=20):
    req = urllib.request.Request(url, headers={'Accept': 'application/json', 'User-Agent': 'SPECTRA-SAR-0xNEBULA-M1-T02/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)


def get_records(short_name, bbox, start, end, max_pages=4):
    records = []
    urls = []
    for page in range(1, max_pages + 1):
        url = search_url(short_name, bbox, start, end, page=page)
        urls.append(url)
        payload = cmr_query(url)
        entries = payload.get('feed', {}).get('entry', [])
        if not isinstance(entries, list):
            raise ValueError('Unexpected CMR response: feed.entry must be a list')
        records.extend(entries)
        if len(entries) < 200:
            return records, urls, False
    return records, urls, True  # query may be truncated: do not claim exhaustive catalog


def parse_gcov_granule_name(name):
    # Example format documented by ASF: ..._GCOV_<cycle>_<track>_<dir>_<frame>_<mode>_<pol>_...
    tokens = re.split(r'[_/]', name or '')
    try:
        i = tokens.index('GCOV')
        cyc, track, direction, frame, mode, pol = tokens[i+1:i+7]
        if not (cyc.isdigit() and track.isdigit() and frame.isdigit() and
                direction in ('A', 'D') and mode.isdigit()):
            return None
        return {'cycle': cyc, 'track': track, 'direction': direction,
                'frame': frame, 'mode': mode, 'polarization_code': pol}
    except (ValueError, IndexError):
        return None


def simplify(entry, maturity, product):
    name = entry.get('producer_granule_id') or entry.get('title') or ''
    all_links = entry.get('links') or []
    download_urls = [link.get('href') for link in all_links if isinstance(link, dict)
                     and not link.get('inherited') and isinstance(link.get('href'), str)
                     and link['href'].lower().split('?')[0].endswith(('.h5', '.hdf5'))]
    obs_dates = sorted(set(re.findall(r'20\d{6}T\d{6}', name)))
    return {
        'granule_id': name,
        'cmr_concept_id': entry.get('id'),
        'collection_concept_id': entry.get('collection_concept_id'),
        'product': product,
        'maturity': maturity,
        'acquisition_start_utc': entry.get('time_start'),
        'acquisition_end_utc': entry.get('time_end'),
        'observation_times_in_id': obs_dates,
        'name_metadata': parse_gcov_granule_name(name) if product == 'GCOV' else None,
        'download_urls': download_urls[:3],
        'browse_url': 'https://search.asf.alaska.edu/',
        'footprint_from_CMR': entry.get('polygons') or entry.get('boxes') or [],
        'geolocation_validated': False,
        'actual_file_opened': False,
    }


def pair_rank(before, after):
    b = iso(before.get('acquisition_start_utc'))
    a = iso(after.get('acquisition_start_utc'))
    if not b or not a or a <= b:
        return None
    duration = (a - b).total_seconds() / 86400
    event_hits = []
    scores = []
    for day in FLOOD_EVENTS:
        event = dt.datetime.fromisoformat(day).replace(tzinfo=UTC)
        if b < event <= a:
            gap = (a-event).total_seconds()/86400
            event_hits.append({'event': day, 'after_event_days': round(gap, 2),
                               'event_time_capture_unverified': gap > 2})
            scores.append(gap + max(duration-48, 0)/3)
    if scores:
        score = min(scores)
    else:
        score = 1000 + duration  # ordinary change pair, not a flood-event confirmation
    return score, round(duration, 2), event_hits


def pair_gcov(records):
    by_group = {}
    for r in records:
        meta = r['name_metadata']
        if not meta or not iso(r['acquisition_start_utc']):
            continue
        key = (r['maturity'], meta['track'], meta['direction'], meta['frame'],
               meta['mode'], meta['polarization_code'])
        by_group.setdefault(key, []).append(r)
    candidates = []
    for key, group in by_group.items():
        group.sort(key=lambda v: v['acquisition_start_utc'])
        # Prefer nearby passes, retain a small diverse list. No cross-maturity pairing.
        for a, b in itertools.combinations(group, 2):
            rank = pair_rank(a, b)
            if not rank:
                continue
            score, duration, hit = rank
            candidates.append({
                'before': a,
                'after': b,
                'time_baseline_days': duration,
                'known_flood_event_window': hit,
                'interpretation': ('POTENTIAL_EVENT_BRACKETING_NOT_PROOF_OF_FLOOD'
                                   if hit else 'RADAR_CHANGE_ONLY_NOT_FLOOD_EVENT'),
                'metadata_match_key': dict(zip(('maturity','track','direction','frame','mode','polarization_code'),key)),
                't03_validation_required': [
                    'full footprint intersects target AOI',
                    'matching L-band polarization/covariance layer',
                    'matching CRID or quantified processing differences',
                    'alignment/geocoding and land/ice/water masks',
                    'acquisition close enough to flood peak for inundation claim'],
                '_score': score,
            })
    candidates.sort(key=lambda v: v['_score'])
    for p in candidates:
        del p['_score']
    return candidates[:8]


def produce(outdir, max_pages=4):
    outdir.mkdir(parents=True, exist_ok=True)
    archive = {}
    report = []
    for product in ('GCOV', 'GOFF'):
        region = 'flood_mendenhall_valley' if product == 'GCOV' else 'glacier_mendenhall'
        bbox = AREAS[region]
        coll_report = []
        all_records = []
        partial_error = False
        for maturity, (short_name, start, end) in COLLECTIONS[product].items():
            url = search_url(short_name, bbox, start, end)
            print(f'[{product}/{maturity}] {url}', flush=True)
            try:
                entries, urls, truncated = get_records(short_name, bbox, start, end, max_pages)
                slim = [simplify(e, maturity, product) for e in entries]
                slim = [r for r in slim if r.get('granule_id')]
                all_records.extend(slim)
                status = 'RESULTS' if slim else 'NO_MATCHES'
                coll_report.append({'short_name': short_name, 'search_status': status,
                                    'count_returned': len(slim), 'truncated': truncated,
                                    'query_url': url})
            except Exception as exc:
                partial_error = True
                coll_report.append({'short_name': short_name, 'search_status': 'ERROR',
                                    'count_returned': None, 'query_url': url,
                                    'error': f'{type(exc).__name__}: {exc}'})
        report.extend(coll_report)
        archive[product] = (all_records, partial_error, coll_report)
    gcov, gcov_error, gcov_reports = archive['GCOV']
    goff, goff_error, goff_reports = archive['GOFF']
    pairs = pair_gcov(gcov)
    scene = {
        'task': 'M1-T02', 'scientific_area': 'Mendenhall Valley flood',
        'search_timestamp_utc': dt.datetime.now(UTC).isoformat(),
        'study_area_bbox_lonlat': AREAS['flood_mendenhall_valley'],
        'status': ('PARTIAL_CATALOG_ERRORS' if gcov_error else
                   'CANDIDATE_FOUND_REQUIRES_T03' if pairs else 'NO_GCOV_PAIR_FOUND_IN_QUERIED_COLLECTIONS'),
        'confirmed_scientifically_valid_pair': False,
        'catalog_results_count': len(gcov),
        'searches': gcov_reports, 'candidate_pairs': pairs,
        'other_returned_granules': gcov[:30],
        'note': 'Search intersection and filename metadata alone do not establish aligned pixels, event-time flooding, or science validity.'
    }
    goff_doc = {
        'task': 'M1-T02', 'scientific_area': 'Mendenhall Glacier motion',
        'search_timestamp_utc': dt.datetime.now(UTC).isoformat(),
        'study_area_bbox_lonlat': AREAS['glacier_mendenhall'],
        'status': 'PARTIAL_CATALOG_ERRORS' if goff_error else ('CANDIDATES_FOUND_REQUIRES_T03' if goff else 'NO_GOFF_MATCHES_IN_QUERIED_COLLECTIONS'),
        'confirmed_usable_displacement_product': False,
        'catalog_results_count': len(goff),
        'searches': goff_reports,
        'candidate_granules': goff[:60],
        'note': 'GOFF contains paired offsets already. Before using: inspect pair dates, valid footprint, SNR, offset units, outliers, and quality layers.'
    }
    (outdir / 'scene-pair.json').write_text(json.dumps(scene, indent=2, ensure_ascii=False)+'\n')
    (outdir / 'goff-scenes.json').write_text(json.dumps(goff_doc, indent=2, ensure_ascii=False)+'\n')
    report_lines = ['# M1 T02 — NASA CMR Catalog Discovery Results', '',
                    f'Generated (UTC): {dt.datetime.now(UTC).isoformat()}', '',
                    f'GCOV: **{scene["status"]}**, {len(gcov)} returned granules, {len(pairs)} shortlisted pairs.',
                    f'GOFF: **{goff_doc["status"]}**, {len(goff)} returned granules.', '',
                    '## Queries', '']
    for item in report:
        report_lines.append(f'- {item["short_name"]}: {item["search_status"]}; {item["query_url"]}')
        if 'error' in item:
            report_lines.append(f'  - ERROR: {item["error"]}')
    report_lines.extend(['', '## Scientific acceptance', '',
                         '- GCOV shortlisting is **NOT** a scientifically approved scene pair (requires T03).',
                         '- GOFF shortlisting is **NOT** a validated glacier-velocity product.',
                         '- A before/after pair that missed the flood peak cannot prove a mapped flood extent.',
                         '- Never merge beta/provisional/validated acquisitions into a single scientific pair by default.',
                         '- Search rectangles are approximate; clip and validate AOIs with M1 T04.', ''])
    (outdir / 'discovery-report.md').write_text('\n'.join(report_lines), encoding='utf-8')
    print('\nRESULT:', scene['status'], '/', goff_doc['status'])
    return scene, goff_doc


def main():
    parser = argparse.ArgumentParser(description='Search NASA CMR for real NISAR GCOV/GOFF granules around Juneau.')
    parser.add_argument('--output', default='.', help='Directory for JSON and Markdown reports')
    parser.add_argument('--max-pages', type=int, default=4, help='CMR pages (200 granules each) per collection; default 4')
    args = parser.parse_args()
    produce(pathlib.Path(args.output), max_pages=args.max_pages)


if __name__ == '__main__':
    main()
