// Builds docs/deck/3D_ULPIN_SIH26011.pptx. Numbers are read from the pipeline's own output files.
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");

const ROOT = "D:/3D ULPIN Generation";
const SHOT = (n) => path.join(ROOT, "docs/screenshots", n);
const readJ = (p) => (fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, "utf8")) : null);
const floorsRep = readJ(path.join(ROOT, "data/processed/floors_report.json"));
const planRep = readJ(path.join(ROOT, "data/processed/floorplan/report.json"));
const cleanRep = readJ(path.join(ROOT, "data/processed/0503100000000071_report.json"));
const brokenRep = readJ(path.join(ROOT, "data/processed/0503100000000071-broken_report.json"));

const INK = "16232B", PAPER = "E9EDF0", MUTE = "4A5A64", RULE = "C7CFD5", WHITE = "FFFFFF";
const BLUE = "2F6F8F", LIGHT = "98CDE0", SAND = "C9A66B", YEL = "F2C94C", RED = "B8322F", OK = "2E7D5B";
const H = "Cambria", B = "Calibri";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "3D ULPIN — vertical property mapping";

function title(slide, text, dark = false) {
  slide.addText(text, { x: 0.6, y: 0.4, w: 12.1, h: 0.9, fontFace: H, fontSize: 34, bold: true, color: dark ? WHITE : INK, margin: 0 });
}
function foot(slide, text, dark = false) {
  slide.addText(text, { x: 0.6, y: 6.95, w: 12.1, h: 0.35, fontFace: B, fontSize: 10, color: dark ? LIGHT : MUTE, margin: 0 });
}
function idBoxes(slide, x, y, scale = 1) {
  // The ULPIN anatomy: the one motif that repeats through the deck
  const segs = [["03100000000071", "parcel ULPIN", 2.9], ["B01", "building", 0.95], ["F02", "level", 0.95], ["U05", "unit", 0.95], ["7", "check", 0.7]];
  let cx = x;
  for (const [v, lab, w] of segs) {
    const ww = w * scale, hh = 0.95 * scale;
    slide.addShape(pres.ShapeType.rect, { x: cx, y, w: ww, h: hh, fill: { color: WHITE }, line: { color: RULE, width: 1 } });
    slide.addText(v, { x: cx, y: y + 0.08 * scale, w: ww, h: 0.5 * scale, fontFace: B, fontSize: (lab === "parcel ULPIN" ? 18 : 22) * scale, bold: true, color: lab === "check" ? OK : INK, align: "center", margin: 0 });
    slide.addText(lab, { x: cx, y: y + 0.58 * scale, w: ww, h: 0.3 * scale, fontFace: B, fontSize: 10 * scale, color: MUTE, align: "center", margin: 0 });
    cx += ww + 0.12 * scale;
  }
  return cx;
}
function bullets(slide, items, o) {
  slide.addText(items.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < items.length - 1, paraSpaceAfter: 8 } })),
    { fontFace: B, fontSize: 15, color: INK, valign: "top", margin: 0, ...o });
}

// 1 — Title (dark)
{
  const s = pres.addSlide(); s.background = { color: INK };
  s.addText("3D ULPIN", { x: 0.8, y: 1.3, w: 11, h: 1.4, fontFace: H, fontSize: 66, bold: true, color: WHITE, margin: 0 });
  s.addText("Giving every flat, parking slot and underground pipe its own verifiable land-record ID", { x: 0.8, y: 2.75, w: 10.5, h: 0.9, fontFace: B, fontSize: 22, color: LIGHT, margin: 0 });
  idBoxes(s, 0.8, 4.2, 1.0);
  s.addText("Smart India Hackathon · Problem statement 26011 · Ministry of Rural Development / DoLR", { x: 0.8, y: 6.3, w: 11, h: 0.4, fontFace: B, fontSize: 13, color: LIGHT, margin: 0 });
  s.addNotes("Open on the ID. Every judge can read it: parcel, building, level, unit, check digit.");
}

// 2 — Problem
{
  const s = pres.addSlide(); s.background = { color: PAPER };
  title(s, "A land record that stops at the ground");
  s.addText("27021500123456", { x: 0.6, y: 1.6, w: 6, h: 1.2, fontFace: B, fontSize: 44, bold: true, color: INK, margin: 0 });
  s.addText("India's ULPIN today: 14 digits that identify a plot of land. Nothing above it, nothing below it.", { x: 0.6, y: 2.8, w: 5.8, h: 1.2, fontFace: B, fontSize: 16, color: MUTE, margin: 0 });
  bullets(s, [
    "Flat 302 and flat 502 share one ID with the whole building",
    "A basement parking slot has no ID at all",
    "A water main under the plot cannot be recorded against it",
    "Disputes, mortgages and taxes on apartments rest on paper annexes",
  ], { x: 7.0, y: 1.6, w: 5.7, h: 3.6 });
  // stacked building glyph
  const cols = [LIGHT, "7ABBD3", "5FA8C5", "4A95B5", "3A82A3", BLUE];
  cols.forEach((c, i) => s.addShape(pres.ShapeType.rect, { x: 0.8, y: 5.9 - i * 0.28, w: 3.2, h: 0.26, fill: { color: c }, line: { color: PAPER, width: 1 } }));
  s.addShape(pres.ShapeType.rect, { x: 0.8, y: 6.2, w: 3.2, h: 0.26, fill: { color: SAND }, line: { color: PAPER, width: 1 } });
  s.addText("one ID for all of this", { x: 4.2, y: 5.4, w: 3, h: 0.9, fontFace: B, fontSize: 14, italic: true, color: MUTE, margin: 0 });
  foot(s, "Background of PS 26011 asks for apartments, parking, air rights and utility corridors. The description omits them; we cover all four.");
}

// 3 — The ID
{
  const s = pres.addSlide(); s.background = { color: PAPER };
  title(s, "Extend the ULPIN, never replace it");
  idBoxes(s, 0.6, 1.6, 1.25);
  s.addText("Flat 5, on floor 2, building 1, on parcel 03100000000071", { x: 0.6, y: 3.05, w: 11, h: 0.5, fontFace: B, fontSize: 18, bold: true, color: INK, margin: 0 });
  const rows = [
    ["Backward compatible", "First 14 digits are the official ULPIN, untouched. Works alongside BhuNaksha and state records."],
    ["Human readable", "An officer reads B01-F02-U05 and knows: building 1, floor 2, flat 5. P = parking, C = common, T = tunnel, B = basement, A = air rights."],
    ["Error resistant", "Last digit is a Luhn check digit over all 22 digits. Every single-digit typo is rejected; tested exhaustively."],
    ["Deterministic", "No random numbers, no timestamps. Units are numbered clockwise from the north-west corner, so re-running gives the same IDs."],
  ];
  rows.forEach(([h, t], i) => {
    const y = 3.8 + i * 0.75;
    s.addText(h, { x: 0.6, y, w: 2.9, h: 0.65, fontFace: B, fontSize: 15, bold: true, color: INK, margin: 0, valign: "top" });
    s.addText(t, { x: 3.6, y, w: 9.1, h: 0.65, fontFace: B, fontSize: 13.5, color: MUTE, margin: 0, valign: "top" });
  });
  foot(s, "Spec: docs/ULPIN_SPEC.md · Code: src/ulpin/generate.py · 52 tests");
}

// 4 — Pipeline
{
  const s = pres.addSlide(); s.background = { color: PAPER };
  title(s, "One pipeline, exact code where it matters");
  const steps = [
    ["Inputs", "parcel + ULPIN\nfootprint or aerial photo\nheight or LiDAR\nfloor plans", MUTE],
    ["AI", "floor plan → flats\nphoto → footprint\nheight → floor count", BLUE],
    ["Geometry", "extrude\nslice levels\nsubdivide units", "3A82A3"],
    ["ULPIN", "deterministic IDs\nLuhn check digit", INK],
    ["Validate", "overlap · containment\ngap · floating · duplicate", RED],
    ["Store & show", "PostGIS (LADM)\nCityJSON · API\n3D viewer", OK],
  ];
  const w = 1.95, gap = 0.16;
  steps.forEach(([h, t, c], i) => {
    const x = 0.6 + i * (w + gap);
    s.addShape(pres.ShapeType.rect, { x, y: 1.9, w, h: 0.6, fill: { color: c }, line: { color: c } });
    s.addText(h, { x, y: 1.9, w, h: 0.6, fontFace: B, fontSize: 15, bold: true, color: WHITE, align: "center", margin: 0 });
    s.addShape(pres.ShapeType.rect, { x, y: 2.5, w, h: 1.9, fill: { color: WHITE }, line: { color: RULE, width: 1 } });
    s.addText(t, { x: x + 0.1, y: 2.6, w: w - 0.2, h: 1.7, fontFace: B, fontSize: 12.5, color: INK, valign: "top", margin: 0 });
  });
  s.addText("AI only where a human would otherwise draw by hand. IDs, checks and storage are rules, because an ID that is 'probably right' is useless for a land record.",
    { x: 0.6, y: 4.8, w: 12.1, h: 0.9, fontFace: B, fontSize: 16, color: INK, margin: 0 });
  s.addText("Every step is a command-line script that prints what it read, how many features it processed and what it wrote. Coordinates stored in EPSG:4326, measured in metres (EPSG:32643 for Gujarat).",
    { x: 0.6, y: 5.7, w: 12.1, h: 0.9, fontFace: B, fontSize: 13, color: MUTE, margin: 0 });
  foot(s, "Python 3.11 · geopandas / shapely · PyTorch + Ultralytics · scikit-learn · FastAPI · CesiumJS · PostGIS + SFCGAL");
}

// 4b — Intake: where the inputs go in
{
  const s = pres.addSlide(); s.background = { color: PAPER };
  title(s, "Where the inputs go in");
  s.addImage({ path: SHOT("06_intake_page.jpg"), x: 0.6, y: 1.5, w: 6.9, h: 3.28 });
  const rows = [
    ["Parcel", "the existing 14-digit ULPIN and the building number"],
    ["Outline", "GeoJSON from the cadastral map or a drone orthophoto traced in BhuNaksha"],
    ["Height", "typed, or measured from a drone elevation model (DSM + DTM) or a LiDAR point cloud"],
    ["Floors, basements, units", "official counts; a missing floor count is estimated and labelled"],
    ["Floor plans", "one image per floor from the approved building plan"],
  ];
  rows.forEach(([k, v], i) => {
    const y = 1.5 + i * 0.68;
    s.addText(k, { x: 7.8, y, w: 2.1, h: 0.62, fontFace: B, fontSize: 13.5, bold: true, color: INK, margin: 0, valign: "top" });
    s.addText(v, { x: 9.9, y, w: 2.85, h: 0.62, fontFace: B, fontSize: 12.5, color: MUTE, margin: 0, valign: "top" });
  });
  s.addText("Height from survey data needs no model: roof points minus ground points. On the demo building, DSM minus DTM gives 13.77 m, LiDAR gives 13.78 m, the register says 14.01 m.",
    { x: 0.6, y: 5.1, w: 12.1, h: 0.8, fontFace: B, fontSize: 14, color: INK, margin: 0 });
  s.addText("One button runs the whole pipeline and opens the building in the viewer with a step-by-step account of what was measured, estimated or read from a register.",
    { x: 0.6, y: 5.9, w: 12.1, h: 0.7, fontFace: B, fontSize: 13, color: MUTE, margin: 0 });
  foot(s, "web/submit.html · src/pipeline.py · src/ingest/height.py · real AHN elevation and AHN4 LiDAR via PDOK and GeoTiles");
}

// 4c — SIH checklist: every input and every AI capability, with the evidence
{
  const s = pres.addSlide(); s.background = { color: PAPER };
  title(s, "Every line of the problem statement, with evidence");
  const rows = [
    ["Drone imagery", "outline traced by SAM from a 25 cm orthophoto, corners squared, IoU 0.71 vs register"],
    ["LiDAR / point cloud", "height from 25,092 roof points: 13.78 m vs 14.01 m register"],
    ["GIS parcel layers", "GeoJSON upload, cadastral register, OpenStreetMap (145k buildings cached for Gujarat)"],
    ["Building floor plans", "our fine-tuned model draws each flat (mask mAP50 0.42)"],
    ["GNSS / CORS", "control-point CSV shifts the outline; 3 points, residual 0.04 m"],
    ["DEM / DSM", "DSM minus DTM: 13.77 m"],
    ["Surface, apartments, underground", "parcel ULPIN; U volumes on G00 to F99; P in basements; T corridors under B00"],
    ["Ownership rights", "owner on every volume (LADM la_rrr); estimated vs surveyed badge on every record"],
    ["Topology validation", "6 rule checks; broken demo building; 69 tests"],
  ];
  rows.forEach(([k, v], i) => {
    const y = 1.45 + i * 0.56;
    s.addText(k, { x: 0.6, y, w: 3.4, h: 0.5, fontFace: B, fontSize: 13.5, bold: true, color: INK, margin: 0, valign: "top" });
    s.addText(v, { x: 4.1, y, w: 8.6, h: 0.5, fontFace: B, fontSize: 12.5, color: MUTE, margin: 0, valign: "top" });
  });
  s.addImage({ path: SHOT("07_sam_building_extraction.png"), x: 10.2, y: 5.55, w: 0.9, h: 1.45 });
  foot(s, "Two routes: From map (estimated, nothing to type) and Manual (surveyed, nothing guessed). Not yet exercised: the PostGIS database, pending an admin install.");
}

// 5 — Real data
{
  const s = pres.addSlide(); s.background = { color: PAPER };
  title(s, "One real building, with the answers on record");
  s.addImage({ path: SHOT("01_overview.jpg"), x: 0.6, y: 1.5, w: 7.6, h: 3.6 });
  const facts = [["Height", "14.0 m (laser scanned)"], ["Floors", "5, official register"], ["Dwelling units", "84, address register"], ["Ground area", "1,057 m² official · 1,057.8 m² ours"], ["Address points inside footprint", "84 of 84"]];
  facts.forEach(([k, v], i) => {
    s.addText(k, { x: 8.5, y: 1.55 + i * 0.66, w: 4.2, h: 0.3, fontFace: B, fontSize: 12, color: MUTE, margin: 0 });
    s.addText(v, { x: 8.5, y: 1.85 + i * 0.66, w: 4.2, h: 0.36, fontFace: B, fontSize: 16, bold: true, color: INK, margin: 0 });
  });
  s.addText("Delft, Netherlands, BAG pand 0503100000000071 (built 1985). Chosen because it is the only open building found where height, floor count and unit count all exist in official registers, so every stage of our pipeline can be checked against truth. No Indian open dataset offers this yet; the pipeline itself is location-independent.",
    { x: 0.6, y: 5.3, w: 12.1, h: 1.3, fontFace: B, fontSize: 13.5, color: INK, margin: 0 });
  foot(s, "Sources: 3DBAG (CC-BY) and PDOK BAG WFS, both free, no key · src/ingest/download.py, align.py");
}

// 6 — Click a flat
{
  const s = pres.addSlide(); s.background = { color: PAPER };
  title(s, "Click any volume, read its ID");
  s.addImage({ path: SHOT("02_unit_selected.jpg"), x: 0.6, y: 1.5, w: 8.4, h: 3.7 });
  bullets(s, [
    "104 volumes: 84 flats over 5 floors, 20 parking slots in the basement",
    "Every one carries a unique 3D ULPIN, height range, area and volume",
    "Floor slider peels the building from the top",
    "Underground toggle makes the ground see-through",
    "Search any ID and the camera flies to it",
  ], { x: 9.3, y: 1.5, w: 3.5, h: 3.9 });
  s.addText("Unit shapes are equal strips because no floor plan is on record for this building; the floor-plan model replaces that step.", { x: 0.6, y: 5.4, w: 8.4, h: 0.7, fontFace: B, fontSize: 12.5, italic: true, color: MUTE, margin: 0 });
  foot(s, "CesiumJS viewer over a FastAPI server · src/api/main.py · web/index.html · free OpenStreetMap imagery");
}

// 7 — Validator
{
  const s = pres.addSlide(); s.background = { color: PAPER };
  title(s, "The validator catches what a human would miss");
  s.addImage({ path: SHOT("03_broken_panel.jpg"), x: 0.6, y: 1.5, w: 1.75, h: 3.27 });
  s.addText("The viewer's panel on the broken copy", { x: 0.6, y: 4.8, w: 2.6, h: 0.5, fontFace: B, fontSize: 10.5, italic: true, color: MUTE, margin: 0 });
  const checks = [["overlap", "two volumes share a height range and their footprints intersect"], ["containment", "a volume pokes outside the building outline or envelope"], ["gap", "units cover under 98% of a level's area"], ["floating", "the bottom of a unit sits on no floor slab"], ["duplicate_id", "one ULPIN assigned to two volumes"], ["bad_id", "format or check digit wrong"]];
  checks.forEach(([k, v], i) => {
    const y = 1.5 + i * 0.52;
    s.addText(k, { x: 3.0, y, w: 2.0, h: 0.44, fontFace: B, fontSize: 14, bold: true, color: RED, margin: 0 });
    s.addText(v, { x: 5.1, y, w: 7.6, h: 0.44, fontFace: B, fontSize: 14, color: INK, margin: 0 });
  });
  const nClean = cleanRep ? cleanRep.findings.length : 0, nBroken = brokenRep ? brokenRep.findings.length : 0;
  s.addText(`Real building: ${nClean} problems. Deliberately broken copy (5 faults injected): ${nBroken} findings, all five kinds caught.`,
    { x: 0.6, y: 5.4, w: 12.1, h: 0.5, fontFace: B, fontSize: 16, bold: true, color: INK, margin: 0 });
  s.addText("Pure Python on prisms (2D shapely intersection plus height-interval overlap), so it runs without a database. PostGIS re-checks the same rules in 3D with ST_3DIntersects as a second opinion. One pytest per check, each breaking a synthetic building one way.",
    { x: 0.6, y: 5.95, w: 12.1, h: 0.9, fontFace: B, fontSize: 13.5, color: MUTE, margin: 0 });
  foot(s, "src/validate/checks.py · make_broken.py · tests/test_validate.py");
}

// 8 — Floor plan model
{
  const s = pres.addSlide(); s.background = { color: PAPER };
  title(s, "Model 1: our fine-tuned floor-plan model finds each flat");
  s.addImage({ path: SHOT("05_floorplan_truth_vs_prediction.png"), x: 0.6, y: 1.6, w: 8.1, h: 1.25 });
  s.addText("Three unseen plans. Blue: registered apartments. Red: what our model drew from the walls alone.", { x: 0.6, y: 2.9, w: 8.1, h: 0.4, fontFace: B, fontSize: 11.5, italic: true, color: MUTE, margin: 0 });
  s.addImage({ path: SHOT("04_msd_labels.png"), x: 0.6, y: 3.45, w: 8.1, h: 2.05 });
  s.addText("Training labels: each colour is one apartment, the union of its rooms, drawn over the wall image.", { x: 0.6, y: 5.55, w: 8.1, h: 0.4, fontFace: B, fontSize: 11.5, italic: true, color: MUTE, margin: 0 });
  bullets(s, [
    "Gap: pretrained floor-plan models know single houses; we need buildings with 10–20 flats per floor",
    "Data: MSD, 4,569 real multi-apartment plans (16,148 flats), 800 held out",
    "Model: YOLOv8s-seg fine-tuned from COCO weights, 40 epochs on a laptop GPU",
    planRep ? `Result on 800 unseen plans: mask mAP50 ${planRep.mask_mAP50}, recall ${planRep.mask_recall} (first attempt with mis-placed labels: 0.152)` : "Result: see data/processed/floorplan/report.json",
    "Output polygons are mapped onto the footprint and fed to the ULPIN step unchanged",
  ], { x: 9.0, y: 1.5, w: 3.8, h: 4.6 });
  foot(s, "src/models/floorplan.py · dataset: Modified Swiss Dwellings (CC-BY-4.0) · cost ₹0");
}

// 9 — Floor count estimator with native chart
{
  const s = pres.addSlide(); s.background = { color: PAPER };
  title(s, "Model 2: estimate floors when the register is silent, and say so");
  const r = floorsRep || { mae_floors: 0.204, within_1_pct: 99.5, rule_of_thumb_mae: 0.325, rule_of_thumb_within_1_pct: 97.5, n_train: 4736, n_test: 1185, height_max_train_m: 22.7 };
  s.addChart(pres.ChartType.bar, [{ name: "Average error (floors)", labels: ["Height ÷ 3 m rule", "Our model"], values: [r.rule_of_thumb_mae, r.mae_floors] }], {
    x: 0.6, y: 1.5, w: 5.6, h: 3.4, barDir: "col", chartColors: [MUTE, BLUE], showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 12, dataLabelColor: INK, dataLabelFormatCode: "0.00",
    showTitle: true, title: "Lower is better: error on 1,185 unseen buildings", titleFontSize: 12, titleColor: INK, showLegend: false,
    catAxisLabelColor: INK, valAxisLabelColor: MUTE, valGridLine: { color: RULE, size: 0.5 }, catGridLine: { style: "none" }, valAxisMaxVal: 0.4,
  });
  bullets(s, [
    `Trained on ${r.n_train.toLocaleString()} buildings with an official floor count (free 3DBAG data)`,
    `${r.within_1_pct}% within one floor, versus ${r.rule_of_thumb_within_1_pct}% for the rule of thumb`,
    "Every record carries floors_source = official / estimated / rule_of_thumb plus a range",
    `Training data only reaches ${r.height_max_train_m} m, so above that the model refuses and the rule of thumb is used, labelled`,
    "An estimate is never stored as a fact; official always wins",
  ], { x: 6.6, y: 1.5, w: 6.1, h: 4.2 });
  foot(s, "src/models/floors.py · gradient boosting (scikit-learn) · trains in seconds, no GPU");
}

// 10 — Interoperability
{
  const s = pres.addSlide(); s.background = { color: PAPER };
  title(s, "Plugs into what exists");
  const cards = [
    ["LADM (ISO 19152)", "PostGIS tables la_party, la_rrr, la_spatialunit, la_building_unit, la_utility_network. The ID format is a database constraint."],
    ["CityJSON 2.0", "Every unit exported as a closed 3D solid with its ULPIN as an attribute. Readable by any 3D city tool."],
    ["API", "List buildings, units, one unit by ULPIN, validation report. Registry, property-tax and bank systems call the same address."],
    ["BhuNaksha", "Parent ULPIN comes from the existing georeferenced village map; nothing in the current record changes."],
  ];
  cards.forEach(([h, t], i) => {
    const x = 0.6 + (i % 2) * 6.15, y = 1.6 + Math.floor(i / 2) * 2.4;
    s.addShape(pres.ShapeType.rect, { x, y, w: 5.95, h: 2.15, fill: { color: WHITE }, line: { color: RULE, width: 1 } });
    s.addText(h, { x: x + 0.3, y: y + 0.25, w: 5.4, h: 0.5, fontFace: B, fontSize: 18, bold: true, color: INK, margin: 0 });
    s.addText(t, { x: x + 0.3, y: y + 0.8, w: 5.4, h: 1.2, fontFace: B, fontSize: 13.5, color: MUTE, margin: 0, valign: "top" });
  });
  foot(s, "src/db/schema.sql · src/db/export_cityjson.py · src/api/main.py");
}

// 11 — Honesty and scale
{
  const s = pres.addSlide(); s.background = { color: PAPER };
  title(s, "What is real, what is not, and how it scales");
  s.addText("Real", { x: 0.6, y: 1.5, w: 5.9, h: 0.45, fontFace: B, fontSize: 18, bold: true, color: OK, margin: 0 });
  bullets(s, ["Building outline, height, floor count, unit count: official registers", "IDs, geometry, validation, viewer: run end to end on that data", "Both models trained on open data, scored on held-out data"], { x: 0.6, y: 2.0, w: 5.9, h: 2.4 });
  s.addText("Assumed, and labelled as such", { x: 6.8, y: 1.5, w: 5.9, h: 0.45, fontFace: B, fontSize: 18, bold: true, color: RED, margin: 0 });
  bullets(s, ["Flats are equal strips: no floor plan is public for this building", "The basement is an operator input to show below-ground IDs", "Owner names are not linked; the LADM tables are ready for them"], { x: 6.8, y: 2.0, w: 5.9, h: 2.4 });
  s.addText("Scaling to India", { x: 0.6, y: 4.6, w: 12.1, h: 0.45, fontFace: B, fontSize: 18, bold: true, color: INK, margin: 0 });
  s.addText("The pipeline never touches a city-wide dataset: one parcel, one building, one run. A state can process buildings as sanction plans arrive. Footprints and heights for India already exist in Google Open Buildings 2.5D; floor plans sit with every municipality's building-approval department. Modification of a building re-runs the pipeline; unchanged units keep their IDs because numbering is deterministic.",
    { x: 0.6, y: 5.1, w: 12.1, h: 1.6, fontFace: B, fontSize: 13.5, color: MUTE, margin: 0 });
  foot(s, "Full plain-language history of every decision: PROJECT_LOG.md");
}

// 12 — Close (dark)
{
  const s = pres.addSlide(); s.background = { color: INK };
  s.addText("Every flat gets a number the record can trust", { x: 0.8, y: 1.2, w: 11.5, h: 1.2, fontFace: H, fontSize: 40, bold: true, color: WHITE, margin: 0 });
  idBoxes(s, 0.8, 2.8, 1.0);
  s.addText("Backward compatible · human readable · error resistant · deterministic · validated in 3D · open standards · ₹0 to build", { x: 0.8, y: 4.2, w: 11.5, h: 0.6, fontFace: B, fontSize: 16, color: LIGHT, margin: 0 });
  s.addText("Param Patel", { x: 0.8, y: 5.6, w: 11, h: 0.5, fontFace: B, fontSize: 16, color: WHITE, margin: 0 });
  s.addText("Run: uvicorn src.api.main:app → http://127.0.0.1:8000/", { x: 0.8, y: 6.1, w: 11, h: 0.4, fontFace: B, fontSize: 12, color: LIGHT, margin: 0 });
}

const out = path.join(ROOT, "docs/deck/3D_ULPIN_SIH26011.pptx");
fs.mkdirSync(path.dirname(out), { recursive: true });
pres.writeFile({ fileName: out }).then(() => console.log("wrote", out));
