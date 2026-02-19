"""
Legal Analyser — Neo4j Graph Database Import Script
=====================================================
Imports all 10 CSVs into Neo4j as a fully connected knowledge graph.

Node types:    LegalSection, LegalAction, CaseType, Evidence, Outcome
Relationship types:
  (LegalSection)-[:RELATED_TO {type, explanation}]->(LegalSection)
  (LegalSection)-[:HAS_ACTION {sequence, conditions}]->(LegalAction)
  (LegalSection)-[:REQUIRES_EVIDENCE {necessity, how_it_proves}]->(Evidence)
  (LegalSection)-[:MAPS_TO_CASE_TYPE {relevance_score, conditions, exceptions}]->(CaseType)
  (LegalAction)-[:LEADS_TO_OUTCOME {probability_pct, influencing_factors}]->(Outcome)

Requirements:
  pip install neo4j pandas
"""

import pandas as pd
from neo4j import GraphDatabase
import os

# ─── CONFIG ───────────────────────────────────────────────────────────────────
NEO4J_URI      = "bolt://localhost:7687"   # Change to your Neo4j URI
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "your_password_here"      # ← Set your password

# Path to your CSV files (change this to wherever you store them)
DATA_DIR = "./data"   # Put all 10 CSVs in a folder called 'data'

# ─── CONNECTION ───────────────────────────────────────────────────────────────
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def run(query, params=None):
    with driver.session() as session:
        session.run(query, params or {})

def run_batch(query, rows):
    with driver.session() as session:
        session.run(query, {"rows": rows})

# ─── STEP 1: CONSTRAINTS & INDEXES ────────────────────────────────────────────
def create_constraints():
    print("Creating constraints and indexes...")
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:LegalSection) REQUIRE n.section_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:LegalAction)  REQUIRE n.action_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:CaseType)     REQUIRE n.case_type_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Evidence)     REQUIRE n.evidence_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Outcome)      REQUIRE n.outcome_id IS UNIQUE",
    ]
    indexes = [
        "CREATE INDEX IF NOT EXISTS FOR (n:LegalSection) ON (n.act_name)",
        "CREATE INDEX IF NOT EXISTS FOR (n:LegalSection) ON (n.category)",
        "CREATE INDEX IF NOT EXISTS FOR (n:LegalSection) ON (n.severity_level)",
        "CREATE INDEX IF NOT EXISTS FOR (n:CaseType)     ON (n.case_category)",
        "CREATE FULLTEXT INDEX IF NOT EXISTS sectionFulltext FOR (n:LegalSection) ON EACH [n.section_title, n.layman_explanation, n.embedding_text]",
        "CREATE FULLTEXT INDEX IF NOT EXISTS actionFulltext  FOR (n:LegalAction)  ON EACH [n.action_name, n.embedding_text]",
    ]
    for q in constraints + indexes:
        try:
            run(q)
        except Exception as e:
            print(f"  [skip] {e}")
    print("  ✓ Constraints and indexes ready")

# ─── STEP 2: IMPORT NODES ─────────────────────────────────────────────────────

def import_legal_sections():
    print("Importing LegalSection nodes...")
    df = pd.read_csv(os.path.join(DATA_DIR, "legal_sections__1_.csv")).fillna("")
    rows = df.to_dict(orient="records")
    query = """
    UNWIND $rows AS row
    MERGE (n:LegalSection {section_id: row.section_id})
    SET
      n.section_number     = row.section_number,
      n.act_name           = row.act_name,
      n.chapter_name       = row.chapter_name,
      n.section_title      = row.section_title,
      n.full_text          = row.full_text,
      n.layman_explanation = row.layman_explanation,
      n.category           = row.category,
      n.severity_level     = row.severity_level,
      n.punishment_summary = row.punishment_summary,
      n.max_punishment_years = toIntegerOrNull(toString(row.max_punishment_years)),
      n.cognizable         = row.cognizable,
      n.bailable           = row.bailable,
      n.applicable_states  = row.applicable_states,
      n.is_compoundable    = row.is_compoundable,
      n.embedding_text     = row.embedding_text
    """
    run_batch(query, rows)
    print(f"  ✓ {len(rows)} LegalSection nodes imported")


def import_legal_actions():
    print("Importing LegalAction nodes...")
    df = pd.read_csv(os.path.join(DATA_DIR, "legal_actions__.csv")).fillna("")
    rows = df.to_dict(orient="records")
    query = """
    UNWIND $rows AS row
    MERGE (n:LegalAction {action_id: row.action_id})
    SET
      n.action_name        = row.action_name,
      n.action_type        = row.action_type,
      n.authority_involved = row.authority_involved,
      n.prerequisites      = row.prerequisites,
      n.time_limit_days    = toString(row.time_limit_days),
      n.cost_estimate_min  = toIntegerOrNull(toString(row.cost_estimate_min)),
      n.cost_estimate_max  = toIntegerOrNull(toString(row.cost_estimate_max)),
      n.online_possible    = row.online_possible,
      n.risk_level         = row.risk_level,
      n.procedure_steps    = row.procedure_steps,
      n.embedding_text     = row.embedding_text
    """
    run_batch(query, rows)
    print(f"  ✓ {len(rows)} LegalAction nodes imported")


def import_case_types():
    print("Importing CaseType nodes...")
    df = pd.read_csv(os.path.join(DATA_DIR, "case_type_1.csv")).fillna("")
    rows = df.to_dict(orient="records")
    query = """
    UNWIND $rows AS row
    MERGE (n:CaseType {case_type_id: row.case_type_id})
    SET
      n.case_category             = row.case_category,
      n.scenario_description      = row.scenario_description,
      n.keywords                  = row.keywords,
      n.typical_duration_months   = toIntegerOrNull(toString(row.typical_duration_months)),
      n.recommended_first_action  = row.recommended_first_action,
      n.common_mistakes           = row.common_mistakes,
      n.embedding_text            = row.embedding_text
    """
    run_batch(query, rows)
    print(f"  ✓ {len(rows)} CaseType nodes imported")


def import_evidence():
    print("Importing Evidence nodes...")
    df = pd.read_csv(os.path.join(DATA_DIR, "evidence_requirements.csv")).fillna("")
    rows = df.to_dict(orient="records")
    query = """
    UNWIND $rows AS row
    MERGE (n:Evidence {evidence_id: row.evidence_id})
    SET
      n.evidence_type        = row.evidence_type,
      n.evidence_name        = row.evidence_name,
      n.description          = row.description,
      n.mandatory_or_optional= row.mandatory_or_optional,
      n.collection_difficulty= row.collection_difficulty,
      n.legal_weight         = row.legal_weight,
      n.evidence_source      = row.evidence_source,
      n.tamper_risk          = row.tamper_risk,
      n.storage_requirements = row.storage_requirements,
      n.embedding_text       = row.embedding_text
    """
    run_batch(query, rows)
    print(f"  ✓ {len(rows)} Evidence nodes imported")


def import_outcomes():
    print("Importing Outcome nodes...")
    df = pd.read_csv(os.path.join(DATA_DIR, "outcomes.csv")).fillna("")
    rows = df.to_dict(orient="records")
    query = """
    UNWIND $rows AS row
    MERGE (n:Outcome {outcome_id: row.outcome_id})
    SET
      n.outcome_description      = row.outcome_description,
      n.outcome_type             = row.outcome_type,
      n.typical_timeline_months  = toIntegerOrNull(toString(row.typical_timeline_months)),
      n.financial_implications   = row.financial_implications,
      n.appeal_possible          = row.appeal_possible,
      n.enforcement_mechanism    = row.enforcement_mechanism,
      n.precedent_cases          = row.precedent_cases,
      n.embedding_text           = row.embedding_text
    """
    run_batch(query, rows)
    print(f"  ✓ {len(rows)} Outcome nodes imported")


# ─── STEP 3: IMPORT RELATIONSHIPS ─────────────────────────────────────────────

def import_section_relationships():
    print("Importing Section→Section relationships...")
    df = pd.read_csv(os.path.join(DATA_DIR, "section_relationships.csv")).fillna("")
    rows = df.to_dict(orient="records")
    query = """
    UNWIND $rows AS row
    MATCH (parent:LegalSection {section_id: row.parent_section_id})
    MATCH (child:LegalSection  {section_id: row.child_section_id})
    MERGE (parent)-[r:RELATED_TO {relationship_type: row.relationship_type}]->(child)
    SET r.explanation = row.explanation
    """
    run_batch(query, rows)
    print(f"  ✓ {len(rows)} Section→Section edges created")


def import_section_to_action():
    print("Importing Section→Action relationships...")
    df = pd.read_csv(os.path.join(DATA_DIR, "section_to_action.csv")).fillna("")
    rows = df.to_dict(orient="records")
    query = """
    UNWIND $rows AS row
    MATCH (s:LegalSection {section_id: row.section_id})
    MATCH (a:LegalAction  {action_id:  row.action_id})
    MERGE (s)-[r:HAS_ACTION]->(a)
    SET
      r.action_sequence   = row.action_sequence,
      r.conditions_required = row.conditions_required
    """
    run_batch(query, rows)
    print(f"  ✓ {len(rows)} Section→Action edges created")


def import_section_to_evidence():
    print("Importing Section→Evidence relationships...")
    df = pd.read_csv(os.path.join(DATA_DIR, "section_to_evidence.csv")).fillna("")
    rows = df.to_dict(orient="records")
    query = """
    UNWIND $rows AS row
    MATCH (s:LegalSection {section_id: row.section_id})
    MATCH (e:Evidence     {evidence_id: row.evidence_id})
    MERGE (s)-[r:REQUIRES_EVIDENCE]->(e)
    SET
      r.necessity_level = row.necessity_level,
      r.how_it_proves   = row.how_it_proves
    """
    run_batch(query, rows)
    print(f"  ✓ {len(rows)} Section→Evidence edges created")


def import_section_to_case_type():
    print("Importing Section→CaseType relationships...")
    df = pd.read_csv(os.path.join(DATA_DIR, "section_to_case_type.csv")).fillna("")
    rows = df.to_dict(orient="records")
    query = """
    UNWIND $rows AS row
    MATCH (s:LegalSection {section_id:  row.section_id})
    MATCH (c:CaseType     {case_type_id: row.case_type_id})
    MERGE (s)-[r:MAPS_TO_CASE_TYPE {section_id: row.section_id, case_type_id: row.case_type_id}]->(c)
    SET
      r.relevance_score = toFloatOrNull(toString(row.relevance_score)),
      r.conditions      = row.conditions,
      r.exceptions      = row.exceptions
    """
    run_batch(query, rows)
    print(f"  ✓ {len(rows)} Section→CaseType edges created")


def import_action_to_outcome():
    print("Importing Action→Outcome relationships...")
    df = pd.read_csv(os.path.join(DATA_DIR, "action_to_outcome.csv")).fillna("")
    rows = df.to_dict(orient="records")
    query = """
    UNWIND $rows AS row
    MATCH (a:LegalAction {action_id:  row.action_id})
    MATCH (o:Outcome     {outcome_id: row.outcome_id})
    MERGE (a)-[r:LEADS_TO_OUTCOME]->(o)
    SET
      r.probability_percentage = toIntegerOrNull(toString(row.probability_percentage)),
      r.influencing_factors    = row.influencing_factors
    """
    run_batch(query, rows)
    print(f"  ✓ {len(rows)} Action→Outcome edges created")


# ─── STEP 4: VERIFICATION ─────────────────────────────────────────────────────

def verify():
    print("\nVerification — node & relationship counts:")
    counts = {
        "LegalSection nodes":        "MATCH (n:LegalSection) RETURN count(n) AS c",
        "LegalAction nodes":         "MATCH (n:LegalAction)  RETURN count(n) AS c",
        "CaseType nodes":            "MATCH (n:CaseType)     RETURN count(n) AS c",
        "Evidence nodes":            "MATCH (n:Evidence)     RETURN count(n) AS c",
        "Outcome nodes":             "MATCH (n:Outcome)      RETURN count(n) AS c",
        "RELATED_TO edges":          "MATCH ()-[r:RELATED_TO]->()          RETURN count(r) AS c",
        "HAS_ACTION edges":          "MATCH ()-[r:HAS_ACTION]->()          RETURN count(r) AS c",
        "REQUIRES_EVIDENCE edges":   "MATCH ()-[r:REQUIRES_EVIDENCE]->()   RETURN count(r) AS c",
        "MAPS_TO_CASE_TYPE edges":   "MATCH ()-[r:MAPS_TO_CASE_TYPE]->()   RETURN count(r) AS c",
        "LEADS_TO_OUTCOME edges":    "MATCH ()-[r:LEADS_TO_OUTCOME]->()    RETURN count(r) AS c",
    }
    with driver.session() as session:
        for label, q in counts.items():
            result = session.run(q).single()
            print(f"  {result['c']:>5}  {label}")

    # Sample query — full graph traversal for one case
    print("\nSample traversal — IPC 417 (Cheating) full path:")
    sample = """
    MATCH (s:LegalSection {section_id: 'IPC_417'})
    OPTIONAL MATCH (s)-[:MAPS_TO_CASE_TYPE]->(ct:CaseType)
    OPTIONAL MATCH (s)-[ha:HAS_ACTION]->(a:LegalAction)
    OPTIONAL MATCH (a)-[lo:LEADS_TO_OUTCOME]->(o:Outcome)
    OPTIONAL MATCH (s)-[re:REQUIRES_EVIDENCE]->(ev:Evidence)
    RETURN
      s.section_title AS section,
      collect(DISTINCT ct.case_type_id) AS case_types,
      collect(DISTINCT {action: a.action_name, seq: ha.action_sequence}) AS actions,
      collect(DISTINCT {evidence: ev.evidence_name, necessity: re.necessity_level}) AS evidence_needed,
      collect(DISTINCT {outcome: o.outcome_description, prob: lo.probability_percentage}) AS outcomes
    LIMIT 1
    """
    with driver.session() as session:
        result = session.run(sample).single()
        if result:
            print(f"  Section    : {result['section']}")
            print(f"  Case Types : {result['case_types']}")
            print(f"  Actions    : {[a['action'] for a in result['actions'] if a['action']][:3]}")
            print(f"  Evidence   : {[e['evidence'] for e in result['evidence_needed'] if e['evidence']][:3]}")
            print(f"  Outcomes   : {[o['outcome'][:50] for o in result['outcomes'] if o['outcome']][:2]}")


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  Legal Analyser — Neo4j Import")
    print("=" * 60)

    create_constraints()

    print("\nImporting nodes...")
    import_legal_sections()
    import_legal_actions()
    import_case_types()
    import_evidence()
    import_outcomes()

    print("\nImporting relationships...")
    import_section_relationships()
    import_section_to_action()
    import_section_to_evidence()
    import_section_to_case_type()
    import_action_to_outcome()

    verify()

    driver.close()
    print("\n✓ Import complete! Open Neo4j Browser and run:")
    print("  MATCH (n) RETURN n LIMIT 100")
    print("  to explore your knowledge graph.")
