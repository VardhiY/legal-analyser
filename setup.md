# Legal Analyser — Setup Guide
# ══════════════════════════════════════════════════════════════

## Step 1 — Neo4j setup

1. Download Neo4j Desktop from https://neo4j.com/download/
   OR use Neo4j AuraDB (free cloud tier) at https://console.neo4j.io

2. Create a new database named: legal_analyser
   Note your: URI (bolt://localhost:7687), username, password

3. Install Python deps:
   pip install neo4j pandas

4. Put all 10 CSV files in a folder called `data/`
   Then run:
   python neo4j_import.py

5. Verify: open Neo4j Browser → run:
   MATCH (n) RETURN n LIMIT 100


## Step 2 — FastAPI backend

1. Install:
   pip install fastapi uvicorn python-dotenv

2. Create a .env file (copy from .env.example below):
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password

3. Run the backend:
   uvicorn main:app --reload --port 8000

4. Test it:
   curl -X POST http://localhost:8000/analyze \
     -H "Content-Type: application/json" \
     -d '{"case_description": "My neighbour cheated me out of money using false promises"}'

   Open API docs: http://localhost:8000/docs


## Step 3 — React frontend

1. Create React app:
   npx create-react-app legal-analyser-frontend
   cd legal-analyser-frontend

2. Install graph viz lib:
   npm install react-force-graph axios

3. Copy legalAnalyser.js to: src/api/legalAnalyser.js

4. Create .env in your React project:
   REACT_APP_API_URL=http://localhost:8000

5. Run:
   npm start


## File structure

legal-analyser/
├── data/                        ← your 10 CSV files go here
│   ├── legal_sections__1_.csv
│   ├── legal_actions__.csv
│   ├── case_type_1.csv
│   ├── evidence_requirements.csv
│   ├── outcomes.csv
│   ├── section_relationships.csv
│   ├── section_to_action.csv
│   ├── section_to_evidence.csv
│   ├── section_to_case_type.csv
│   └── action_to_outcome.csv
├── neo4j_import.py              ← run this first
├── main.py                      ← FastAPI backend
├── .env                         ← your credentials
└── legal-analyser-frontend/
    └── src/
        └── api/
            └── legalAnalyser.js ← paste this in


## .env.example
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
REACT_APP_API_URL=http://localhost:8000


## Key API endpoints

POST /analyze           → Full case analysis
GET  /graph/{id}        → Graph JSON for vis
GET  /section/{id}      → Section detail
GET  /search?q=theft    → Full-text search
GET  /health            → DB connection check
GET  /docs              → Auto-generated API docs (Swagger UI)


## Neo4j graph schema

Nodes:
  (:LegalSection  {section_id, section_number, act_name, ...})
  (:LegalAction   {action_id, action_name, procedure_steps, ...})
  (:CaseType      {case_type_id, scenario_description, ...})
  (:Evidence      {evidence_id, evidence_name, legal_weight, ...})
  (:Outcome       {outcome_id, outcome_description, probability, ...})

Relationships:
  (LegalSection)-[:RELATED_TO {type, explanation}]->(LegalSection)
  (LegalSection)-[:HAS_ACTION {sequence, conditions}]->(LegalAction)
  (LegalSection)-[:REQUIRES_EVIDENCE {necessity, how_it_proves}]->(Evidence)
  (LegalSection)-[:MAPS_TO_CASE_TYPE {relevance_score}]->(CaseType)
  (LegalAction) -[:LEADS_TO_OUTCOME  {probability_pct}]->(Outcome)
