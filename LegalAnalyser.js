// src/api/legalAnalyser.js
// ─────────────────────────────────────────────────────────────────────────────
// API client for the Legal Analyser FastAPI backend.
// Usage in any React component:
//   import { useAnalyze, useGraph } from '../api/legalAnalyser'

const BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

// ─── Raw fetch helpers ────────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ─── API functions ────────────────────────────────────────────────────────────

/**
 * POST /analyze
 * @param {string} caseDescription - Free-text case description
 * @param {string} [state]         - Optional: "All India" | "Maharashtra" etc.
 * @param {string} [category]      - Optional: "Criminal" | "Civil"
 */
export async function analyzeCase(caseDescription, state = "All India", category = null) {
  return apiFetch("/analyze", {
    method: "POST",
    body: JSON.stringify({
      case_description: caseDescription,
      state,
      category,
    }),
  });
}

/**
 * GET /graph/:sectionId
 * Returns { nodes, edges, root } for graph visualization
 */
export async function getGraph(sectionId) {
  return apiFetch(`/graph/${encodeURIComponent(sectionId)}`);
}

/**
 * GET /section/:sectionId
 */
export async function getSection(sectionId) {
  return apiFetch(`/section/${encodeURIComponent(sectionId)}`);
}

/**
 * GET /search?q=
 */
export async function searchSections(query) {
  return apiFetch(`/search?q=${encodeURIComponent(query)}`);
}

/**
 * GET /health
 */
export async function checkHealth() {
  return apiFetch("/health");
}


// ─── React Hooks ──────────────────────────────────────────────────────────────
import { useState, useCallback } from "react";

/**
 * useAnalyze — hook for the main case analysis flow
 *
 * const { analyze, data, loading, error, reset } = useAnalyze()
 * await analyze("My neighbour cheated me out of money...")
 */
export function useAnalyze() {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState(null);

  const analyze = useCallback(async (caseDescription, state, category) => {
    setLoading(true);
    setError(null);
    try {
      const result = await analyzeCase(caseDescription, state, category);
      setData(result);
      return result;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  return { analyze, data, loading, error, reset };
}

/**
 * useGraph — hook to fetch graph data for a section
 *
 * const { fetchGraph, graphData, loading, error } = useGraph()
 * await fetchGraph("IPC_417")
 */
export function useGraph() {
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState(null);

  const fetchGraph = useCallback(async (sectionId) => {
    setLoading(true);
    setError(null);
    try {
      const result = await getGraph(sectionId);
      setGraphData(result);
      return result;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { fetchGraph, graphData, loading, error };
}


// ─── Response shape reference (for components) ────────────────────────────────
/*
analyzeCase() returns:
{
  case_description: string,
  matched_sections: [
    {
      section_id, section_number, section_title,
      layman_explanation, severity_level, cognizable,
      bailable, punishment_summary, max_punishment_years,
      relevance_score, case_type_id
    }
  ],
  case_types: [
    { id, description, duration, mistakes }
  ],
  action_plan: [
    {
      action_id, action_name, action_type, authority_involved,
      cost_min, cost_max, online_possible, risk_level,
      procedure_steps, sequence, conditions
    }
  ],
  evidence_checklist: [
    {
      evidence_id, evidence_name, evidence_type, description,
      legal_weight, evidence_source, storage_requirements,
      tamper_risk, necessity_level, how_it_proves
    }
  ],
  outcome_probabilities: [
    {
      outcome_id, outcome_description, outcome_type,
      timeline_months, appeal_possible, precedent_cases,
      probability, influencing_factors
    }
  ],
  reasoning_trace: [
    { step, type, description, result }
  ],
  confidence_score: 0.0–1.0
}

getGraph(sectionId) returns:
{
  nodes: [ { id, label, type, data } ],
  edges: [ { from, to, label, data } ],
  root: sectionId
}
*/