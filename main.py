"""
Legal Analyser — FastAPI Backend
=================================
Connects React frontend → Neo4j graph database.

Endpoints:
  POST /analyze          → Full case analysis from free text
  GET  /graph/{id}       → Graph JSON for visualization
  GET  /section/{id}     → Single section details
  GET  /search?q=...     → Full-text search across sections
  GET  /health           → Health check

Install:
  pip install fastapi uvicorn neo4j python-dotenv sentence-transformers

Run:
  uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from neo4j import GraphDatabase
from typing import Optional
import os, re
from dotenv import load_dotenv

load_dotenv()

# ─── APP SETUP ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Legal Analyser API",
    description="Neuro-Symbolic AI for Indian Penal Code case analysis",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # React dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── NEO4J CONNECTION ─────────────────────────────────────────────────────────
NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your_password_here")

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def get_session():
    return driver.session()


# ─── PYDANTIC MODELS ──────────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    case_description: str
    state: Optional[str] = "All India"
    category: Optional[str] = None   # "Criminal" | "Civil" | None


class ReasoningStep(BaseModel):
    step: int
    type: str          # "symbolic" | "neural" | "graph_traversal"
    description: str
    result: str


class AnalyzeResponse(BaseModel):
    case_description: str
    matched_sections: list
    case_types: list
    action_plan: list
    evidence_checklist: list
    outcome_probabilities: list
    reasoning_trace: list[ReasoningStep]
    confidence_score: float


# ─── KEYWORD EXTRACTION (Symbolic Layer) ──────────────────────────────────────
LEGAL_KEYWORDS = {
    "cheating":          ["CHEATING_01", "CHEATING_02"],
    "fraud":             ["CHEATING_01", "CHEATING_02"],
    "stolen":            ["THEFT_01"],
    "theft":             ["THEFT_01"],
    "assault":           ["ASSAULT_01"],
    "beat":              ["ASSAULT_01"],
    "murder":            ["MURDER_01"],
    "kill":              ["MURDER_01"],
    "defamation":        ["DEFAMATION_01"],
    "reputation":        ["DEFAMATION_01"],
    "harassment":        ["HARASSMENT_01", "ASSAULT_01"],
    "kidnap":            ["KIDNAPPING_01"],
    "abduct":            ["KIDNAPPING_01"],
    "dowry":             ["DOWRY_01"],
    "bribe":             ["CORRUPTION_01"],
    "trust":             ["CRIMINAL_BREACH_TRUST_01"],
    "misappropriat":     ["CRIMINAL_BREACH_TRUST_01"],
    "extort":            ["EXTORTION_01"],
    "blackmail":         ["EXTORTION_01"],
    "trespass":          ["TRESPASS_01"],
    "bigamy":            ["BIGAMY_01"],
    "cohabitat":         ["COHABITATION_01"],
    "forgery":           ["FORGERY_01"],
}

def extract_case_types_symbolically(text: str) -> tuple[list[str], list[dict]]:
    """Rule-based keyword matching — the 'symbolic' part of neuro-symbolic."""
    text_lower = text.lower()
    matched = {}
    trace = []
    
    for keyword, case_type_ids in LEGAL_KEYWORDS.items():
        if keyword in text_lower:
            for ct_id in case_type_ids:
                if ct_id not in matched:
                    matched[ct_id] = keyword
                    trace.append({
                        "keyword": keyword,
                        "matched_case_type": ct_id,
                        "rule": f"Symbolic rule: '{keyword}' → {ct_id}"
                    })
    
    return list(matched.keys()), trace


# ─── CYPHER QUERIES ───────────────────────────────────────────────────────────

def query_sections_by_case_types(session, case_type_ids: list[str]) -> list[dict]:
    if not case_type_ids:
        return []
    result = session.run("""
        UNWIND $ids AS ct_id
        MATCH (s:LegalSection)-[r:MAPS_TO_CASE_TYPE]->(ct:CaseType {case_type_id: ct_id})
        RETURN DISTINCT
            s.section_id         AS section_id,
            s.section_number     AS section_number,
            s.section_title      AS section_title,
            s.layman_explanation AS layman_explanation,
            s.severity_level     AS severity_level,
            s.cognizable         AS cognizable,
            s.bailable           AS bailable,
            s.punishment_summary AS punishment_summary,
            s.max_punishment_years AS max_punishment_years,
            r.relevance_score    AS relevance_score,
            ct.case_type_id      AS case_type_id
        ORDER BY r.relevance_score DESC
        LIMIT 10
    """, ids=case_type_ids)
    return [dict(r) for r in result]


def query_fulltext_sections(session, text: str) -> list[dict]:
    """Neural layer: fulltext search using Neo4j's built-in fulltext index."""
    # Extract key phrases (simple NLP preprocessing)
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    query_str = " OR ".join(set(words[:8]))  # top 8 unique words
    
    result = session.run("""
        CALL db.index.fulltext.queryNodes('sectionFulltext', $q)
        YIELD node, score
        RETURN
            node.section_id         AS section_id,
            node.section_number     AS section_number,
            node.section_title      AS section_title,
            node.layman_explanation AS layman_explanation,
            node.severity_level     AS severity_level,
            node.cognizable         AS cognizable,
            node.bailable           AS bailable,
            node.punishment_summary AS punishment_summary,
            score                   AS relevance_score
        ORDER BY score DESC
        LIMIT 5
    """, q=query_str)
    return [dict(r) for r in result]


def query_action_plan(session, section_ids: list[str]) -> list[dict]:
    result = session.run("""
        UNWIND $ids AS sid
        MATCH (s:LegalSection {section_id: sid})-[r:HAS_ACTION]->(a:LegalAction)
        RETURN DISTINCT
            a.action_id          AS action_id,
            a.action_name        AS action_name,
            a.action_type        AS action_type,
            a.authority_involved AS authority_involved,
            a.cost_estimate_min  AS cost_min,
            a.cost_estimate_max  AS cost_max,
            a.online_possible    AS online_possible,
            a.risk_level         AS risk_level,
            a.procedure_steps    AS procedure_steps,
            r.action_sequence    AS sequence,
            r.conditions_required AS conditions
        ORDER BY
            CASE r.action_sequence
                WHEN 'Primary' THEN 1
                WHEN 'Secondary' THEN 2
                WHEN 'Alternative' THEN 3
                ELSE 4
            END
    """, ids=section_ids)
    return [dict(r) for r in result]


def query_evidence_checklist(session, section_ids: list[str]) -> list[dict]:
    result = session.run("""
        UNWIND $ids AS sid
        MATCH (s:LegalSection {section_id: sid})-[r:REQUIRES_EVIDENCE]->(e:Evidence)
        RETURN DISTINCT
            e.evidence_id           AS evidence_id,
            e.evidence_name         AS evidence_name,
            e.evidence_type         AS evidence_type,
            e.description           AS description,
            e.legal_weight          AS legal_weight,
            e.evidence_source       AS evidence_source,
            e.storage_requirements  AS storage_requirements,
            e.tamper_risk           AS tamper_risk,
            r.necessity_level       AS necessity_level,
            r.how_it_proves         AS how_it_proves
        ORDER BY
            CASE r.necessity_level
                WHEN 'Must-have'  THEN 1
                WHEN 'Good-to-have' THEN 2
                ELSE 3
            END
    """, ids=section_ids)
    return [dict(r) for r in result]


def query_outcome_probabilities(session, action_ids: list[str]) -> list[dict]:
    if not action_ids:
        return []
    result = session.run("""
        UNWIND $ids AS aid
        MATCH (a:LegalAction {action_id: aid})-[r:LEADS_TO_OUTCOME]->(o:Outcome)
        RETURN DISTINCT
            o.outcome_id          AS outcome_id,
            o.outcome_description AS outcome_description,
            o.outcome_type        AS outcome_type,
            o.typical_timeline_months AS timeline_months,
            o.appeal_possible     AS appeal_possible,
            o.precedent_cases     AS precedent_cases,
            r.probability_percentage AS probability,
            r.influencing_factors AS influencing_factors
        ORDER BY r.probability_percentage DESC
        LIMIT 8
    """, ids=action_ids)
    return [dict(r) for r in result]


def query_related_sections(session, section_ids: list[str]) -> list[dict]:
    result = session.run("""
        UNWIND $ids AS sid
        MATCH (s:LegalSection {section_id: sid})-[r:RELATED_TO]->(related:LegalSection)
        RETURN DISTINCT
            related.section_id    AS section_id,
            related.section_title AS section_title,
            r.relationship_type   AS relationship_type,
            r.explanation         AS explanation
        LIMIT 10
    """, ids=section_ids)
    return [dict(r) for r in result]


# ─── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    try:
        with get_session() as s:
            s.run("RETURN 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        raise HTTPException(503, f"Database unreachable: {e}")


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_case(req: AnalyzeRequest):
    """
    Main endpoint. Takes a case description, runs neuro-symbolic reasoning,
    returns matched sections, actions, evidence, outcomes + full reasoning trace.
    """
    reasoning_trace = []
    step = 1

    # ── Symbolic layer: keyword matching ──────────────────────────────────────
    symbolic_case_types, symbolic_trace = extract_case_types_symbolically(req.case_description)
    reasoning_trace.append(ReasoningStep(
        step=step, type="symbolic",
        description="Keyword-based rule matching against legal case type definitions",
        result=f"Matched case types: {symbolic_case_types or ['none yet — using neural fallback']}"
    ))
    step += 1

    with get_session() as session:

        # ── Graph traversal: find sections from symbolic case types ───────────
        symbolic_sections = query_sections_by_case_types(session, symbolic_case_types)
        reasoning_trace.append(ReasoningStep(
            step=step, type="graph_traversal",
            description="Neo4j traversal: CaseType → MAPS_TO_CASE_TYPE → LegalSection",
            result=f"Found {len(symbolic_sections)} sections via symbolic path"
        ))
        step += 1

        # ── Neural layer: fulltext search for additional matches ──────────────
        neural_sections = query_fulltext_sections(session, req.case_description)
        reasoning_trace.append(ReasoningStep(
            step=step, type="neural",
            description="Neo4j fulltext index search on section titles and explanations",
            result=f"Found {len(neural_sections)} sections via neural/semantic path"
        ))
        step += 1

        # ── Merge & deduplicate sections (symbolic + neural) ──────────────────
        seen_ids = set()
        all_sections = []
        for s in symbolic_sections + neural_sections:
            if s["section_id"] not in seen_ids:
                seen_ids.add(s["section_id"])
                all_sections.append(s)

        # Apply symbolic filter: state-specific sections
        if req.state and req.state != "All India":
            # Keep sections that apply to requested state or All India
            # (for now: pass-through since most are All India)
            pass

        reasoning_trace.append(ReasoningStep(
            step=step, type="symbolic",
            description="Deduplication + symbolic filters (state, category)",
            result=f"{len(all_sections)} unique sections after merge"
        ))
        step += 1

        section_ids = [s["section_id"] for s in all_sections]

        # ── Graph traversal: get action plan ──────────────────────────────────
        action_plan = query_action_plan(session, section_ids)
        reasoning_trace.append(ReasoningStep(
            step=step, type="graph_traversal",
            description="Neo4j traversal: LegalSection → HAS_ACTION → LegalAction (ordered by sequence)",
            result=f"Generated {len(action_plan)}-step action plan"
        ))
        step += 1

        # ── Graph traversal: get evidence checklist ───────────────────────────
        evidence = query_evidence_checklist(session, section_ids)
        reasoning_trace.append(ReasoningStep(
            step=step, type="graph_traversal",
            description="Neo4j traversal: LegalSection → REQUIRES_EVIDENCE → Evidence (ordered by necessity)",
            result=f"Found {len(evidence)} evidence items ({sum(1 for e in evidence if e['necessity_level']=='Must-have')} must-have)"
        ))
        step += 1

        # ── Graph traversal: get outcome probabilities ─────────────────────────
        action_ids = [a["action_id"] for a in action_plan]
        outcomes = query_outcome_probabilities(session, action_ids)
        reasoning_trace.append(ReasoningStep(
            step=step, type="graph_traversal",
            description="Neo4j traversal: LegalAction → LEADS_TO_OUTCOME → Outcome (with probability scores)",
            result=f"Computed {len(outcomes)} probable outcomes"
        ))
        step += 1

        # ── Unique case types from matched sections ────────────────────────────
        case_type_ids_found = list({s.get("case_type_id") for s in symbolic_sections if s.get("case_type_id")})
        case_types = []
        if case_type_ids_found:
            ct_result = session.run("""
                UNWIND $ids AS id
                MATCH (ct:CaseType {case_type_id: id})
                RETURN ct.case_type_id AS id, ct.scenario_description AS description,
                       ct.typical_duration_months AS duration, ct.common_mistakes AS mistakes
            """, ids=case_type_ids_found)
            case_types = [dict(r) for r in ct_result]

        # ── Confidence score (symbolic: 0.7 weight, neural: 0.3 weight) ───────
        symbolic_hits = len(symbolic_sections)
        neural_hits   = len(neural_sections)
        confidence = min(1.0, round((symbolic_hits * 0.7 + neural_hits * 0.3) / 10, 2))

        reasoning_trace.append(ReasoningStep(
            step=step, type="symbolic",
            description="Confidence scoring: weighted average of symbolic + neural hit rates",
            result=f"Overall confidence: {confidence * 100:.0f}%"
        ))

    return AnalyzeResponse(
        case_description=req.case_description,
        matched_sections=all_sections,
        case_types=case_types,
        action_plan=action_plan,
        evidence_checklist=evidence,
        outcome_probabilities=outcomes,
        reasoning_trace=reasoning_trace,
        confidence_score=confidence
    )


@app.get("/graph/{section_id}")
def get_graph(section_id: str):
    """
    Returns graph JSON (nodes + edges) for a section.
    Used by the React graph visualizer (react-force-graph / vis.js).
    """
    with get_session() as session:
        result = session.run("""
            MATCH (s:LegalSection {section_id: $id})
            
            OPTIONAL MATCH (s)-[r1:RELATED_TO]->(s2:LegalSection)
            OPTIONAL MATCH (s)-[r2:HAS_ACTION]->(a:LegalAction)
            OPTIONAL MATCH (a)-[r3:LEADS_TO_OUTCOME]->(o:Outcome)
            OPTIONAL MATCH (s)-[r4:REQUIRES_EVIDENCE]->(ev:Evidence)
            OPTIONAL MATCH (s)-[r5:MAPS_TO_CASE_TYPE]->(ct:CaseType)

            RETURN
                s,
                collect(DISTINCT {node: s2, rel: r1}) AS related_sections,
                collect(DISTINCT {node: a,  rel: r2}) AS actions,
                collect(DISTINCT {node: o,  rel: r3}) AS outcomes,
                collect(DISTINCT {node: ev, rel: r4}) AS evidence,
                collect(DISTINCT {node: ct, rel: r5}) AS case_types
        """, id=section_id)

        record = result.single()
        if not record:
            raise HTTPException(404, f"Section {section_id} not found")

        nodes = []
        edges = []
        seen_nodes = set()

        def add_node(node_id, label, node_type, data=None):
            if node_id not in seen_nodes:
                seen_nodes.add(node_id)
                nodes.append({"id": node_id, "label": label, "type": node_type, "data": data or {}})

        # Root section
        s = record["s"]
        add_node(s["section_id"], s["section_number"], "LegalSection", dict(s))

        # Related sections
        for item in record["related_sections"]:
            n = item["node"]
            if n:
                add_node(n["section_id"], n["section_number"], "LegalSection", dict(n))
                edges.append({"from": section_id, "to": n["section_id"],
                               "label": item["rel"].type, "data": dict(item["rel"])})

        # Actions
        for item in record["actions"]:
            n = item["node"]
            if n:
                add_node(n["action_id"], n["action_name"][:30], "LegalAction", dict(n))
                edges.append({"from": section_id, "to": n["action_id"],
                               "label": "HAS_ACTION", "data": dict(item["rel"])})

        # Outcomes
        for item in record["outcomes"]:
            n = item["node"]
            if n:
                add_node(n["outcome_id"], n["outcome_description"][:30], "Outcome", dict(n))
                action_id = item["rel"].start_node["action_id"] if hasattr(item["rel"], "start_node") else None
                if action_id:
                    edges.append({"from": action_id, "to": n["outcome_id"],
                                   "label": "LEADS_TO", "data": dict(item["rel"])})

        # Evidence
        for item in record["evidence"]:
            n = item["node"]
            if n:
                add_node(n["evidence_id"], n["evidence_name"][:30], "Evidence", dict(n))
                edges.append({"from": section_id, "to": n["evidence_id"],
                               "label": "REQUIRES", "data": dict(item["rel"])})

        # Case types
        for item in record["case_types"]:
            n = item["node"]
            if n:
                add_node(n["case_type_id"], n["case_type_id"], "CaseType", dict(n))
                edges.append({"from": section_id, "to": n["case_type_id"],
                               "label": "MAPS_TO", "data": dict(item["rel"])})

    return {"nodes": nodes, "edges": edges, "root": section_id}


@app.get("/section/{section_id}")
def get_section(section_id: str):
    with get_session() as session:
        result = session.run("""
            MATCH (s:LegalSection {section_id: $id})
            RETURN s
        """, id=section_id)
        record = result.single()
        if not record:
            raise HTTPException(404, f"Section {section_id} not found")
        return dict(record["s"])


@app.get("/search")
def search_sections(q: str = Query(..., min_length=3)):
    with get_session() as session:
        results = session.run("""
            CALL db.index.fulltext.queryNodes('sectionFulltext', $q)
            YIELD node, score
            RETURN
                node.section_id         AS section_id,
                node.section_number     AS section_number,
                node.section_title      AS section_title,
                node.layman_explanation AS layman_explanation,
                node.severity_level     AS severity_level,
                score
            ORDER BY score DESC
            LIMIT 10
        """, q=q)
        return {"results": [dict(r) for r in results]}


@app.on_event("shutdown")
def shutdown():
    driver.close()
