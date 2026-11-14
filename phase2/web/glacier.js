'use strict';
const glacierPanel=el('section',undefined,'panel');glacierPanel.id='glacier';glacierPanel.hidden=true;
glacierPanel.innerHTML='<div class="eyebrow">GLACIER DISPLACEMENT</div><h2>Review glacier movement</h2><p>Upload a prepared displacement bundle for this area. Original GOFF HDF5 files require preparation first; see GLACIER-INPUTS.md. Backscatter images alone do not measure velocity.</p><label for="glacierBundle">Displacement ZIP (maximum 32 MB)</label><input id="glacierBundle" type="file" accept=".zip"><button id="glacierAnalyze">Analyze displacement</button><div id="glacierResults" aria-live="polite">Awaiting displacement measurements.</div>';
journey.after(glacierPanel);
function displayGlaciers(results){
 $('glacierResults').replaceChildren();
 if(!results.length)$('glacierResults').append(el('p','Input required: displacement layers, quality, acquisition dates and glacier boundaries.'));
 for(const result of results){
  const card=el('article',undefined,'alert-card');
  card.append(el('h3',result.status),el('p',result.source.reference_time+' → '+result.source.secondary_time),
   el('p',result.retained_cells+' retained glacier cells / '+result.valid_glacier_cells+' valid glacier cells'));
  for(const [name,stats] of Object.entries(result.components))card.append(el('p',name.replaceAll('_',' ')+': '+(stats.median_rate_m_per_day===null?'Unavailable':stats.median_rate_m_per_day.toFixed(4)+' m/day (median component rate)')));
  for(const note of result.limitations)card.append(el('p',note,'subtle'));
  const download=el('button','Download displacement result & hashes');
  download.onclick=()=>saveResponse(new Response(JSON.stringify(result,null,2)),'SPECTRA-glacier-'+result.id+'.json');
  card.append(download);$('glacierResults').append(card);
 }
}
const beforeGlacierShow=show;
show=async function(record,gen){await beforeGlacierShow(record,gen);if(gen!==generation)return;
 const results=await json('/jobs/'+record.id+'/glacier');if(gen!==generation)return;glacierPanel.hidden=false;displayGlaciers(results);};
const beforeGlacierSelect=selectJob;
selectJob=async function(id){glacierPanel.hidden=true;$('glacierBundle').value='';return beforeGlacierSelect(id);};
$('disconnect').addEventListener('click',()=>{glacierPanel.hidden=true;$('glacierBundle').value='';$('glacierResults').replaceChildren();});
$('glacierAnalyze').onclick=async()=>{
 const file=$('glacierBundle').files[0];if(!current||!file){fail(new Error('Choose a completed analysis and a displacement ZIP.'));return;}
 if(file.size>32*1024*1024){fail(new Error('Crop the bundle to 32 MB or less.'));return;}
 const gen=generation,job=current;$('glacierAnalyze').disabled=true;
 try{await json('/jobs/'+job+'/glacier',{method:'POST',body:file,headers:{'Content-Type':'application/zip'}});
 const results=await json('/jobs/'+job+'/glacier');if(gen===generation)displayGlaciers(results);
 }catch(error){if(gen===generation)fail(error);}finally{$('glacierAnalyze').disabled=false;}
};
