// ============================================================================
// Unified Converter - Ersetzt "Code in JavaScript12" + "Supabase Format Converter"
// Replaces both Code nodes with a single node to avoid double-conversion bug.
//
// PROBLEM / PROBLEM:
//   Die beiden Code-Nodes gaben jeweils 2 Items zurueck [streamlitResponse, supabasePayload].
//   Der zweite Node hat die Ausgabe des ersten nochmal verarbeitet und dabei leere
//   Metriken {} weitergegeben. Der Webhook hat dann beide Items als Array gesendet.
//
//   Both Code nodes returned 2 items each. The second node re-processed the first
//   node's output, propagating empty metrics {}. The webhook sent both items as an array.
//
// FIX / LOESUNG:
//   Ein einziger Code-Node, der genau 1 Item zurueckgibt (den sauberen Contract).
//   A single Code node that returns exactly 1 item (the clean dashboard contract).
// ============================================================================

const input = $input.first().json;

// --- Hilfsfunktionen / Helper functions ---

/**
 * Prueft ob ein Objekt tatsaechlich Schluessel hat.
 * In JavaScript ist {} truthy — das war die Ursache fuer den Bug.
 *
 * Checks whether an object actually has keys.
 * In JavaScript {} is truthy — that was the root cause of the bug.
 */
function hasKeys(obj) {
  return obj !== null && obj !== undefined && typeof obj === 'object' && Object.keys(obj).length > 0;
}

/**
 * Sicheres JSON-Parsen mit Fallback auf null.
 * Safe JSON parsing that returns null on failure.
 */
function safeParse(str) {
  if (typeof str !== 'string') return null;
  try {
    return JSON.parse(str);
  } catch (e) {
    return null;
  }
}

// --- Bekannte Metrik-Schluessel / Known metric keys ---
const KNOWN_METRIC_KEYS = [
  'belegt',
  'frei',
  'belegungsgrad',
  'vertragsdauer_durchschnitt',
  'reminder_automat',
  'social_facebook',
  'social_google',
  'kundenherkunft',
  'zahlungsstatus',
  'neukunden_labels',
  'neukunden_monat',
];

// ============================================================================
// Schritt 1: Eingabeformat erkennen und Rohdaten extrahieren
// Step 1: Detect input format and extract raw data
// ============================================================================

let metrics = {};
let recommendations = [];
let customerMessage = '';
let analysisDate = '';
let tenantId = '';

// --- Strategie A: AI-Agent-Ausgabe ---
// Strategy A: AI Agent output (current_analysis with populated metrics)
if (input.current_analysis && hasKeys(input.current_analysis.metrics)) {
  const ca = input.current_analysis;
  metrics = ca.metrics;
  recommendations = ca.recommendations || [];
  customerMessage = ca.customer_message || '';
  analysisDate = ca.analysis_date || '';
  tenantId = input.tenant_id || ca.tenant_id || '';

// --- Strategie B: analysis_result als JSON-String ---
// Strategy B: analysis_result is a JSON string that needs parsing
} else if (typeof input.analysis_result === 'string') {
  const parsed = safeParse(input.analysis_result);
  if (parsed && hasKeys(parsed.metrics)) {
    metrics = parsed.metrics;
    recommendations = parsed.recommendations || [];
    customerMessage = parsed.customer_message || '';
    analysisDate = parsed.analysis_date || '';
    tenantId = input.tenant_id || parsed.tenant_id || '';
  } else if (parsed && hasKeys(parsed)) {
    // Vielleicht sind die Metriken direkt im geparsten Objekt
    // Maybe the metrics are directly in the parsed object
    metrics = parsed;
    tenantId = input.tenant_id || '';
  }

// --- Strategie C: analysis_result als Objekt ---
// Strategy C: analysis_result is already an object
} else if (input.analysis_result && typeof input.analysis_result === 'object') {
  const ar = input.analysis_result;
  if (hasKeys(ar.metrics)) {
    metrics = ar.metrics;
    recommendations = ar.recommendations || [];
    customerMessage = ar.customer_message || '';
    analysisDate = ar.analysis_date || '';
  } else if (hasKeys(ar)) {
    metrics = ar;
  }
  tenantId = input.tenant_id || ar.tenant_id || '';

// --- Strategie D: Rohe Geschaeftsdaten direkt im Input ---
// Strategy D: Raw business data at the top level of input
} else if (input.belegt !== undefined || input.frei !== undefined || input.belegungsgrad !== undefined) {
  for (const key of KNOWN_METRIC_KEYS) {
    if (input[key] !== undefined) {
      metrics[key] = input[key];
    }
  }
  tenantId = input.tenant_id || '';

// --- Strategie E: Vorformatierter Contract mit data.metrics ---
// Strategy E: Pre-formatted contract with data.metrics
} else if (input.data && hasKeys(input.data.metrics)) {
  metrics = input.data.metrics;
  recommendations = input.data.recommendations || [];
  customerMessage = input.data.customer_message || '';
  analysisDate = input.data.analysis_date || '';
  tenantId = input.data.tenant_id || input.tenant_id || '';

// --- Strategie F: Metriken irgendwo verschachtelt suchen ---
// Strategy F: Search for metrics nested anywhere in the input
} else {
  // Rekursive Suche nach einem Objekt mit bekannten Metrik-Schluesseln
  // Recursive search for an object containing known metric keys
  function findMetrics(obj, depth) {
    if (depth > 5 || !obj || typeof obj !== 'object') return null;
    // Pruefen ob dieses Objekt selbst Metriken enthaelt
    // Check if this object itself contains metrics
    const matchingKeys = KNOWN_METRIC_KEYS.filter(k => obj[k] !== undefined);
    if (matchingKeys.length >= 2) return obj;
    // In Kinder-Objekten suchen / Search child objects
    for (const key of Object.keys(obj)) {
      if (typeof obj[key] === 'object' && obj[key] !== null) {
        const found = findMetrics(obj[key], depth + 1);
        if (found) return found;
      }
    }
    return null;
  }

  const found = findMetrics(input, 0);
  if (found) {
    for (const key of KNOWN_METRIC_KEYS) {
      if (found[key] !== undefined) {
        metrics[key] = found[key];
      }
    }
  }
  tenantId = input.tenant_id || '';
}

// ============================================================================
// Schritt 2: Standardwerte setzen
// Step 2: Apply defaults
// ============================================================================

if (!analysisDate) {
  analysisDate = new Date().toISOString();
}

if (!tenantId) {
  tenantId = 'default';
}

// Sicherstellen, dass recommendations ein Array ist
// Ensure recommendations is an array
if (!Array.isArray(recommendations)) {
  if (typeof recommendations === 'string') {
    recommendations = [recommendations];
  } else {
    recommendations = [];
  }
}

// ============================================================================
// Schritt 3: Streamlit-Dashboard-Contract aufbauen
// Step 3: Build the Streamlit dashboard contract
// ============================================================================

const streamlitResponse = {
  success: hasKeys(metrics),
  tenant_id: tenantId,
  analysis_date: analysisDate,
  data: {
    metrics: metrics,
    recommendations: recommendations,
    customer_message: customerMessage,
    analysis_date: analysisDate,
    tenant_id: tenantId,
  },
};

// ============================================================================
// Schritt 4: NUR 1 Item zurueckgeben — kein zweites Item mehr!
// Step 4: Return ONLY 1 item — no second item anymore!
//
// Das ist der entscheidende Fix: Der Webhook bekommt genau ein Objekt,
// nicht ein Array aus [streamlitResponse, supabasePayload].
//
// This is the critical fix: the webhook receives exactly one object,
// not an array of [streamlitResponse, supabasePayload].
// ============================================================================

return [{ json: streamlitResponse }];
