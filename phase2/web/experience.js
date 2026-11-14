'use strict';
const journey = el('section', undefined, 'panel'); journey.id='journey'; journey.dir='ltr'; journey.lang='en'; journey.hidden=true;
journey.innerHTML=`<div class="panel-heading"><div><div class="eyebrow">SPECTRA · RESULTS EXPLAINED</div><h2>What changed, and what comes next?</h2></div><button id="portableReport">Download report</button></div>
<p>1. Select a region from the list or map. 2. Inspect its priority and evidence. 3. Review alerts. 4. Compare runs or download your report.</p>
<p class="subtle">Reports are self-contained HTML files with imagery. Open one and use Print to save a PDF. Alerts stay inside this app and are review requests, not emergency warnings.</p>
<label for="explainZone">Select a region to explain</label><select id="explainZone"></select><article id="explanation" aria-live="polite"></article>
<h2>Review alerts</h2><p>Marking an alert reviewed records your review; it does not confirm an event or resolve a hazard.</p><div id="reviewAlerts"></div>
<h2>Compare analyses</h2><p>The current run is the first side. Select another completed run for the same area. Running the software again does not create a new satellite observation.</p>
<label for="compareRun">Other analysis</label><select id="compareRun"></select><button id="compareAction">Compare with current run</button><div id="comparison" role="status"></div>
<details><summary>Glacier movement: required inputs</summary><p id="movementInputs"></p></details>`;
$('evidence').before(advancedPanel, journey);
let currentInsights=null;
const textValue=value=>value===null||value===undefined?'Unavailable':typeof value==='number'?value.toLocaleString('en-US',{maximumFractionDigits:2}):String(value);
async function saveResponse(response,name){const blob=await response.blob(),url=URL.createObjectURL(blob),link=el('a');link.href=url;link.download=name;link.click();setTimeout(()=>URL.revokeObjectURL(url),3000);}
function explainRegion(id){
 if(!currentInsights)return;
 const zone=currentInsights.zones.find(item=>item.id===id); if(!zone)return;
 $('explainZone').value=id; const target=$('explanation');target.replaceChildren();
 target.append(el('h3',zone.id),el('p',zone.explanation_en),el('p',zone.priority_reason_en),el('p',zone.interpretation_en));
 target.append(el('p',`Dates: ${zone.source_dates.join(' → ')} | Quality indicator: ${(zone.confidence*100).toFixed(1)}% — not a calibrated probability.`));
 target.append(el('p',`Estimated residents: ${textValue(zone.population.estimated_residents)} · Mapped buildings: ${textValue(zone.mapped_buildings)} · Intersecting roads: ${textValue(zone.mapped_roads_m)} meters. A source value of zero does not prove the absence of people or assets.`));
 target.append(el('p',`Experimental risk priority score: ${textValue(zone.risk_score)}. Scores are unavailable when required coverage is incomplete.`));
 const links=el('div',undefined,'files');
 for(const name of zone.evidence){const button=el('button','Evidence: '+name);button.onclick=async()=>{try{const job=currentInsights.job_id;await saveResponse(await request('/jobs/'+job+'/artifacts/'+name),name.split('/').pop());}catch(error){fail(error);}};links.append(button);}
 target.append(links);
}
const previousInspect=inspectZone;
inspectZone=function(feature){previousInspect(feature);explainRegion(feature.properties.id);};
function renderAlerts(){
 $('reviewAlerts').replaceChildren();
 if(!currentInsights.alerts.length)$('reviewAlerts').append(el('p','No alerts under the current rules. This does not establish absence of hazards.'));
 for(const alert of currentInsights.alerts){const card=el('article',undefined,'alert-card');card.append(el('h3',alert.title_en),el('p',alert.reason_en));
 if(alert.zone_id){const zoneButton=el('button','View region');zoneButton.onclick=()=>explainRegion(alert.zone_id);card.append(zoneButton);}
 const review=el('button',alert.reviewed_at?'Reviewed':'Mark reviewed');review.disabled=Boolean(alert.reviewed_at);
 review.onclick=async()=>{const gen=generation,job=currentInsights.job_id;review.disabled=true;try{await json('/jobs/'+job+'/alerts/'+encodeURIComponent(alert.id)+'/review',{method:'PUT'});if(gen!==generation)return;const refreshed=await json('/jobs/'+job+'/insights');if(gen===generation){currentInsights=refreshed;renderAlerts();}}catch(error){if(gen===generation){review.disabled=false;fail(error);}}};
 card.append(review);$('reviewAlerts').append(card);}
}
const previousShowExperience=show;
show=async function(record,gen){await previousShowExperience(record,gen);if(gen!==generation||!record.result.phase3)return;
 const [insight,historyRows]=await Promise.all([json('/jobs/'+record.id+'/insights'),json('/jobs')]);if(gen!==generation)return;
 currentInsights=insight;journey.hidden=false;$('explainZone').replaceChildren();
 for(const zone of insight.zones){const option=el('option',zone.id+' · '+({exposure_review:'Exposure review',quality_review:'Quality review',standard_review:'Standard review'}[zone.review_priority]));option.value=zone.id;$('explainZone').append(option);}
 if(insight.zones.length)explainRegion(insight.zones[0].id);else $('explanation').replaceChildren(el('p','No regions passed screening; this does not establish absence of change.'));
 renderAlerts();$('comparison').textContent='';$('compareRun').replaceChildren();
 for(const row of historyRows.filter(item=>item.status==='COMPLETED_EXPLORATORY'&&item.id!==record.id)){const option=el('option',row.dataset+' · '+row.candidate_mode+' · '+row.submitted_at+' · '+row.id.slice(0,8));option.value=row.id;$('compareRun').append(option);}
 $('compareAction').disabled=!$('compareRun').options.length;
 if(!$('compareRun').options.length)$('comparison').textContent='Complete another analysis first. Try the broader screen for the same images to compare settings.';
 $('movementInputs').textContent=insight.movement.message_en+' Provide an original NISAR GOFF .h5 product covering the glacier and both acquisition dates, including quality layers; also provide a glacier boundary (.geojson or .gpkg). Existing GCOV images do not need to be uploaded again. See GLACIER-INPUTS.md for details.';
};
const previousSelectExperience=selectJob;
selectJob=async function(id){journey.hidden=true;currentInsights=null;return previousSelectExperience(id);};
$('disconnect').addEventListener('click',()=>{journey.hidden=true;currentInsights=null;for(const id of ['explanation','reviewAlerts','comparison','compareRun','explainZone'])$(id).replaceChildren();});
$('explainZone').onchange=()=>explainRegion($('explainZone').value);
$('portableReport').onclick=async()=>{if(!currentInsights)return;const job=currentInsights.job_id;try{await saveResponse(await request('/jobs/'+job+'/report'),'SPECTRA-'+job+'.html');}catch(error){fail(error);}};
$('compareAction').onclick=async()=>{if(!currentInsights)return;const gen=generation,job=currentInsights.job_id,other=$('compareRun').value;$('compareAction').disabled=true;try{const result=await json('/jobs/'+job+'/compare/'+other);if(gen!==generation)return;$('comparison').replaceChildren(el('p',result.interpretation_en),el('p',`First pair dates: ${result.left.dates.join(' → ')} | Other pair: ${result.right.dates.join(' → ')}`),el('p',`Candidate area difference: ${textValue(result.area_difference_m2)} m² · Pixel difference: ${textValue(result.retained_pixel_difference)} · Footprint overlap: ${result.footprint_iou===null?'Undefined: both footprints are empty':(100*result.footprint_iou).toFixed(1)+'%'}`));}catch(error){if(gen===generation)$('comparison').textContent='Comparison failed: check both runs are complete, cover the same area and have intact evidence.';}finally{if(gen===generation)$('compareAction').disabled=false;}};
const guide=el('section',undefined,'panel');guide.dir='ltr';guide.lang='en';guide.innerHTML='<h2>Start here</h2><p>Choose a Source Pair and click Run analysis. Explore the before/after images, change map, region explanations and review alerts, then download your report. Your existing image pair is already included.</p>';
$('controls').before(guide);
