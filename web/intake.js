// Shared by from-map.html and manual.html: radio-driven option panels, floor-plan rows, submit + result.
const $ = s => document.querySelector(s);

function syncOptions() {
  document.querySelectorAll('.opt').forEach(o => { const [n, v] = o.dataset.for.split(':'); const r = document.querySelector(`input[name=${n}]:checked`); o.hidden = !r || r.value !== v; });
}
document.querySelectorAll('input[type=radio]').forEach(r => r.addEventListener('change', syncOptions));

let nPlans = 0;
function addPlanRow() {
  nPlans++;
  const lvl = document.createElement('select'); lvl.name = 'plan_level';
  const opts = ['G00', ...Array.from({ length: 20 }, (_, i) => 'F' + String(i + 1).padStart(2, '0'))];
  const def = nPlans === 1 ? 'G00' : 'F' + String(nPlans - 1).padStart(2, '0');
  lvl.innerHTML = opts.map(o => `<option ${o === def ? 'selected' : ''}>${o}</option>`).join('');
  const file = document.createElement('input'); file.type = 'file'; file.name = 'plan_image'; file.accept = 'image/*';
  $('#plans').append(lvl, file);
}
if ($('#addplan')) $('#addplan').onclick = addPlanRow;

// Polygon area in m² from lon/lat; equirectangular at the centroid is fine for one building.
function polyArea(geom) {
  const ring = geom.coordinates[0], lat0 = ring.reduce((s, p) => s + p[1], 0) / ring.length * Math.PI / 180;
  const kx = 111320 * Math.cos(lat0), ky = 110540;
  let a = 0;
  for (let i = 0; i < ring.length - 1; i++) a += (ring[i][0] * kx) * (ring[i + 1][1] * ky) - (ring[i + 1][0] * kx) * (ring[i][1] * ky);
  return Math.abs(a) / 2;
}

async function submitForm(form, mode, extra = {}) {
  const fd = new FormData(form);
  fd.append('mode', mode);
  for (const [k, v] of Object.entries(extra)) fd.append(k, v);
  const go = form.querySelector('button[type=submit]');
  go.disabled = true; $('#result').hidden = false; $('#result').textContent = 'Running the pipeline…';
  try {
    const r = await fetch('/api/submit', { method: 'POST', body: fd });
    const j = await r.json();
    if (!r.ok) { $('#result').innerHTML = `<p class="bad">Stopped: ${j.detail}</p>`; return; }
    const badge = j.accuracy === 'estimated' ? '<span class="badge est">estimated</span>' : '<span class="badge sur">surveyed</span>';
    const assumed = j.assumed && j.assumed.length ? `<p class="warn">Assumed, not measured:</p><ul>${j.assumed.map(a => `<li>${a}</li>`).join('')}</ul>` : '<p class="ok">Nothing assumed.</p>';
    $('#result').innerHTML = `<p>${badge} <span class="${j.findings ? 'bad' : 'ok'}">${j.units} volumes on ${j.levels} levels, validator: ${j.findings ? j.findings + ' findings' : 'clean'}.</span></p>
      <ol>${j.steps.map(s => `<li>${s}</li>`).join('')}</ol>${assumed}
      <p><a href="/?building=${encodeURIComponent(j.pand_id)}">Open building ${j.pand_id} in the 3D viewer</a></p>`;
  } catch (err) { $('#result').innerHTML = `<p class="bad">Request failed: ${err}</p>`; }
  finally { go.disabled = false; }
}
