# RAG Indexing Strategy for Mathematical Content

**Purpose**: Guide for setting up RAG (Retrieval-Augmented Generation) systems to effectively index and retrieve mathematical content from this repository.

**Last Updated**: 2025-12-31

**Context**: This document provides recommendations based on the structured mathematical documentation created in:
- `040_MATHEMATICAL_STRUCTURE.md` - Comprehensive mathematical framework
- `045_EQUATION_MAP.md` - Equation-to-code mapping
- `047_STATE_SPACE_AND_FLOW.md` - State space and computational flow

---

## Executive Summary

The structured mathematical documentation creates several advantages for RAG systems:

1. **Consistent equation IDs** (`eq:model`, `eq:bellman`, etc.) enable precise retrieval
2. **Cross-references** between equations, code, and paper create rich metadata
3. **Hierarchical organization** suggests optimal chunking strategies
4. **Multiple representations** (math notation, code, natural language) enable multi-modal retrieval
5. **Structured tables** provide extractable metadata for hybrid search

---

## 1. Optimal Chunking Strategy

### 1.1 Principle: Equation-Centered Chunking

**Recommendation**: Chunk content around individual equations or small equation groups, keeping related context together.

**Rationale**: 
- Equations are the atomic units of mathematical knowledge
- Each equation in `045_EQUATION_MAP.md` has associated context (paper reference, code location, mathematical form)
- Users query for specific equations or concepts

### 1.2 Recommended Chunk Boundaries

#### For `040_MATHEMATICAL_STRUCTURE.md`:

**Chunk 1**: Document header + Core Mathematical Objects (Section 1)
- Includes all core equations (value function, Euler, budget, consumption decomposition)
- Keep together because they define the fundamental structure

**Chunk 2-4**: Individual equation subsections (1.1-1.5)
- Each equation with its description, code location, paper reference
- Example: "eq:bellman - Value Function" = one chunk

**Chunk 5**: Equation Map table (Section 2)
- The entire table as one chunk (structured data)

**Chunk 6-9**: State Space sections (Section 3)
- State space structure, operators, aggregation

**Chunk 10-12**: Sequence-Space Jacobian (Section 4)
- SSJ framework documentation

**Chunk 13-15**: Computational Structure (Section 5)
- Algorithms and methods

**Chunk 16**: Notation Index (Section 7)
- Entire table as one chunk

#### For `045_EQUATION_MAP.md`:

**Chunk 1**: Quick Reference Table
- Entire table as one chunk (structured data, good for exact matching)

**Chunk 2-N**: Individual equation entries in "Detailed Equation Index"
- Each equation gets its own chunk:
  - Equation ID (e.g., `eq:model`)
  - Mathematical form
  - Paper reference
  - Code location
  - LaTeX source
  - Related code

**Chunk N+1**: Parameter Value Reference Table
- Entire table as one chunk

**Chunk N+2**: Code Function → Equation Mapping
- Entire table as one chunk

#### For `047_STATE_SPACE_AND_FLOW.md`:

**Chunk 1**: State Space Structure (Section 1)
- Individual agent state, employment states, aggregate state

**Chunk 2-4**: State Evolution sections (Section 2)
- Flow diagrams and descriptions

**Chunk 5-7**: Function Dependencies, Computational Graph (Sections 3-4)
- Dependency relationships

**Chunk 8-10**: Key Properties, Dimensions, Initialization (Sections 5-7)
- Mathematical properties and constraints

### 1.3 Chunk Size Guidelines

- **Target size**: 200-500 tokens per chunk
- **Maximum size**: 800 tokens (avoid splitting equations from their context)
- **Minimum size**: 50 tokens (if smaller, merge with adjacent content)

**Special cases**:
- Tables: Keep entire table as single chunk (even if large)
- Equations: Keep equation, description, and immediate context together
- Code blocks: Include code with its mathematical explanation

---

## 2. Metadata Extraction Strategy

### 2.1 Essential Metadata Fields

For each chunk, extract and store:

```json
{
  "equation_id": "eq:model",  // From equation IDs in documents
  "equation_type": "core_equation",  // core, income, aggregation, policy, etc.
  "paper_section": "Section 2.1, Eq. (1)",
  "code_location": "AggFiscalModel.py:consumption()",
  "mathematical_domain": "consumption_decomposition",  // consumption, income, state_space, etc.
  "related_equations": ["eq:splurge", "eq:budget"],  // From cross-references
  "document_source": "040_MATHEMATICAL_STRUCTURE.md",
  "section_number": "1.1",
  "has_latex": true,
  "has_code_reference": true,
  "parameter_symbols": ["c", "c_sp", "c_opt"],  // Symbols used
  "concept_tags": ["consumption", "splurge", "optimization"]
}
```

### 2.2 Structured Data Extraction

**From Tables** (`045_EQUATION_MAP.md` Quick Reference Table):

Extract as structured JSON:
```json
{
  "equation_map": [
    {
      "equation_id": "eq:model",
      "description": "Consumption decomposition",
      "paper_reference": "Eq. (1)",
      "code_location": "AggFiscalModel.py:consumption()",
      "mathematical_form": "c = c_sp + c_opt"
    },
    // ... more entries
  ]
}
```

**From Parameter Tables**:

Extract parameter-value mappings:
```json
{
  "parameters": [
    {
      "symbol": "ς",
      "name": "Splurge factor",
      "value": 0.249,
      "code_location": "EstimParameters.py: Splurge"
    },
    // ... more entries
  ]
}
```

### 2.3 Cross-Reference Graph

Build a knowledge graph from cross-references:

```
eq:model → (references) → eq:splurge
eq:model → (implemented_in) → AggFiscalModel.py:consumption()
eq:model → (defined_in_paper) → Section 2.1, Eq. (1)
eq:bellman → (solved_by) → EstimAggFiscalModel.solve()
eq:bellman → (uses) → eq:euler
```

Store as edges in a graph database or as metadata relationships.

---

## 3. Multi-Modal Content Handling

### 3.1 LaTeX Equations

**Challenge**: LaTeX equations need special handling for embedding

**Strategions**:

1. **Dual representation**:
   - Store LaTeX source: `$\mathbf{c} = \mathbf{c}_{sp} + \mathbf{c}_{opt}$`
   - Store natural language: "Consumption equals splurge consumption plus optimal consumption"
   - Store code representation: `c = cSplurge + cOpt`

2. **Equation normalization**:
   - Extract symbols: `{c, c_sp, c_opt}`
   - Extract operators: `{=, +}`
   - Create searchable string: "consumption equals splurge consumption plus optimal consumption"

3. **Embedding strategy**:
   - Use models that handle LaTeX (e.g., `text-embedding-ada-002` with LaTeX preprocessing)
   - Consider specialized math embeddings (e.g., `sentence-transformers/all-MiniLM-L6-v2` with LaTeX-aware tokenization)

### 3.2 Code References

**Strategy**: 
- Extract code paths: `Code/HA-Models/FromPandemicCode/AggFiscalModel.py`
- Extract function/method names: `consumption()`
- Create searchable code context: "AggFiscalModel consumption method implements consumption decomposition"

### 3.3 Paper References

**Strategy**:
- Normalize references: "Section 2.1, Equation (1)" → structured `{section: "2.1", equation: "1"}`
- Enable exact matching for paper-based queries

---

## 4. Hybrid Search Strategy

### 4.1 Recommended Approach: Dense + Sparse + Structured

**Three-tier retrieval**:

1. **Dense embeddings** (semantic search):
   - Embed chunk text using math-aware model
   - Use for conceptual queries: "How is consumption decomposed?"

2. **Sparse/keyword search** (BM25 or similar):
   - Index equation IDs: `eq:model`, `eq:bellman`
   - Index symbols: `c`, `β`, `ς`
   - Index code paths: `AggFiscalModel.py`
   - Use for exact queries: "eq:model" or "consumption decomposition"

3. **Structured/metadata filters**:
   - Filter by equation type: `equation_type: "core_equation"`
   - Filter by domain: `mathematical_domain: "consumption"`
   - Filter by code location: `code_location: "AggFiscalModel.py"`
   - Use for precise queries: "equations implemented in AggFiscalModel.py"

### 4.2 Query Routing

**Route queries based on pattern**:

- Query contains `eq:` → Use sparse search for equation ID
- Query contains file path → Use metadata filter
- Query contains LaTeX symbols → Use symbol extraction + sparse search
- Conceptual query → Use dense embedding search
- Query contains paper reference → Use metadata filter for paper section

**Example query routing**:
```
"eq:bellman" → Sparse search (exact match)
"value function" → Dense embedding (semantic)
"EstimAggFiscalModel.solve()" → Metadata filter (code location)
"Section 2.1" → Metadata filter (paper reference)
"consumption equals splurge plus optimal" → Dense embedding (conceptual)
```

---

## 5. Indexing Recommendations by RAG System

### 5.1 For ChromaDB

**Configuration**:
```python
collection = chromadb.Client().create_collection(
    name="hafiscal_equations",
    metadata={"hnsw:space": "cosine"},  # Use cosine similarity
)

# Add metadata for filtering
collection.add(
    documents=[chunk_text],
    metadatas=[{
        "equation_id": "eq:model",
        "document": "045_EQUATION_MAP.md",
        "section": "1.1",
        "has_code": True,
        "has_equation": True,
    }],
    ids=[f"eq:model"]
)
```

**Query strategy**: Use `where` filters for metadata, combine with semantic search

### 5.2 For Pinecone

**Configuration**:
- Use dimension 1536 (OpenAI embeddings) or 384 (sentence-transformers)
- Create metadata index for: `equation_id`, `document`, `section`, `code_location`

**Query strategy**: Hybrid search combining vector similarity with metadata filters

### 5.3 For FAISS + Metadata Store

**Architecture**:
- FAISS index for dense embeddings
- Separate metadata store (SQLite, PostgreSQL, or JSON) for structured data
- Join on chunk ID

**Query strategy**: 
1. Query FAISS for semantic similarity
2. Filter results using metadata store
3. Re-rank combining similarity score + metadata relevance

### 5.4 For Weaviate

**Schema**:
```json
{
  "class": "Equation",
  "properties": [
    {"name": "equation_id", "dataType": ["string"]},
    {"name": "content", "dataType": ["text"]},
    {"name": "code_location", "dataType": ["string"]},
    {"name": "paper_reference", "dataType": ["string"]},
    {"name": "mathematical_form", "dataType": ["text"]},
  ]
}
```

**Query strategy**: Use GraphQL `nearText` with `where` filters

---

## 6. Special Handling for Mathematical Symbols

### 6.1 Symbol Normalization

Create a symbol mapping table:

```json
{
  "symbol_mappings": {
    "c": ["consumption", "c", "\\mathbf{c}"],
    "c_sp": ["splurge consumption", "cSplurge", "\\mathbf{c}_{sp}"],
    "beta": ["discount factor", "β", "\\beta"],
    "varsigma": ["splurge factor", "ς", "\\varsigma", "Splurge"],
  }
}
```

**Usage**: 
- Index both LaTeX and normalized forms
- Enable queries using any representation: "ς", "varsigma", "splurge factor", "Splurge"

### 6.2 Symbol Extraction

From equations, extract:
- Variable symbols: `{c, c_sp, c_opt}`
- Parameter symbols: `{ς, β, γ}`
- Operator symbols: `{=, +, -, ×, /}`

Store as metadata for symbol-based queries.

---

## 7. Cross-Document Relationships

### 7.1 Relationship Types

From the structured documentation, identify:

1. **Equation relationships**:
   - `eq:model` → (uses) → `eq:splurge`
   - `eq:bellman` → (implements) → `eq:euler`

2. **Code relationships**:
   - `AggFiscalModel.consumption()` → (implements) → `eq:model`
   - `EstimAggFiscalModel.solve()` → (solves) → `eq:bellman`

3. **Document relationships**:
   - `040_MATHEMATICAL_STRUCTURE.md` → (references) → `045_EQUATION_MAP.md`
   - `045_EQUATION_MAP.md` → (maps_to) → Code files

### 7.2 Graph-Based Retrieval

**Recommendation**: Use graph RAG or multi-hop retrieval

1. Initial retrieval: Find relevant chunks
2. Expand: Follow relationships to related equations/code
3. Aggregate: Combine information from multiple related chunks

**Example**:
```
Query: "How is consumption computed?"
→ Retrieve: eq:model chunk
→ Expand: Follow to eq:splurge, eq:budget, AggFiscalModel.consumption()
→ Return: Consolidated answer from all related chunks
```

---

## 8. Query Optimization Strategies

### 8.1 Query Expansion

**For mathematical queries**, expand to include:
- Symbol variations: "consumption" → ["consumption", "c", "\\mathbf{c}", "c_i"]
- Related concepts: "value function" → ["value function", "Bellman equation", "V_s"]
- Code aliases: "splurge factor" → ["ς", "varsigma", "Splurge", "splurge factor"]

### 8.2 Re-ranking

**After initial retrieval**, re-rank using:

1. **Equation ID match** (highest priority): Exact match to `eq:*` IDs
2. **Symbol match**: Query symbols match equation symbols
3. **Code path match**: Query mentions code location
4. **Semantic similarity**: Embedding similarity score
5. **Cross-reference relevance**: Chunk is referenced by high-scoring chunks

### 8.3 Context Window Management

**For long context models** (GPT-4, Claude), include:
1. Primary chunk (highest relevance)
2. Related equations (from cross-references)
3. Code implementation (if code_location metadata present)
4. Paper context (if paper_reference metadata present)

---

## 9. Implementation Checklist

### Phase 1: Basic Indexing
- [ ] Extract chunks using equation-centered strategy
- [ ] Extract metadata (equation_id, code_location, paper_reference)
- [ ] Create dense embeddings using math-aware model
- [ ] Store in vector database with metadata

### Phase 2: Structured Data
- [ ] Extract tables from `045_EQUATION_MAP.md` as structured JSON
- [ ] Extract parameter values as structured data
- [ ] Create symbol mapping table
- [ ] Index symbol variations

### Phase 3: Relationships
- [ ] Build cross-reference graph
- [ ] Index relationship metadata (uses, implements, references)
- [ ] Implement multi-hop retrieval

### Phase 4: Hybrid Search
- [ ] Implement sparse/keyword search (BM25)
- [ ] Implement metadata filtering
- [ ] Combine dense + sparse + metadata in hybrid query
- [ ] Implement query routing based on query pattern

### Phase 5: Optimization
- [ ] Query expansion for mathematical symbols
- [ ] Re-ranking with multiple signals
- [ ] Context window optimization
- [ ] Performance tuning

---

## 10. Example Queries and Expected Retrieval

### Query 1: "What is the consumption decomposition equation?"

**Expected retrieval**:
- Primary: `eq:model` chunk from `045_EQUATION_MAP.md`
- Secondary: Consumption decomposition section from `040_MATHEMATICAL_STRUCTURE.md`
- Metadata filter: `equation_id: "eq:model"` OR `mathematical_domain: "consumption_decomposition"`

### Query 2: "Where is the Bellman equation implemented in code?"

**Expected retrieval**:
- Primary: `eq:bellman` chunk with code_location metadata
- Secondary: `EstimAggFiscalModel.py` code file (if indexed)
- Metadata filter: `equation_id: "eq:bellman"` AND `has_code_reference: True`

### Query 3: "What is the value of the splurge factor?"

**Expected retrieval**:
- Primary: Parameter table entry for `ς` from `045_EQUATION_MAP.md`
- Secondary: `eq:splurge` equation chunk
- Metadata filter: `parameter_symbols: ["ς", "varsigma"]` OR symbol match

### Query 4: "How does state transition work in the model?"

**Expected retrieval**:
- Primary: State evolution sections from `047_STATE_SPACE_AND_FLOW.md`
- Secondary: State space structure sections
- Semantic match: "state transition" → chunks about Markov process, state evolution

---

## 11. Tools and Libraries

### Recommended Stack

**For embeddings**:
- `sentence-transformers/all-mpnet-base-v2` (general purpose)
- `sentence-transformers/all-MiniLM-L6-v2` (faster, smaller)
- Consider math-specific models if available

**For vector databases**:
- **ChromaDB**: Easy setup, good metadata support
- **Pinecone**: Managed service, good for production
- **Weaviate**: Graph + vector capabilities
- **FAISS + metadata store**: Full control, requires more setup

**For sparse search**:
- **BM25**: Standard keyword search
- **Elasticsearch**: Full-featured search engine
- **Whoosh**: Python-native, lightweight

**For graph relationships**:
- **Neo4j**: Graph database
- **NetworkX**: Python graph library (for in-memory)
- **Simple graph structure**: JSON + custom traversal

---

## 12. Related Documents

- **040_MATHEMATICAL_STRUCTURE.md**: Source of mathematical framework
- **045_EQUATION_MAP.md**: Source of equation mappings
- **047_STATE_SPACE_AND_FLOW.md**: Source of state space documentation
- **035_MODEL_SUMMARY.md**: Additional mathematical content
- **060_CODE_NAVIGATION.md**: Code structure (for code-based queries)

---

## Summary

The structured mathematical documentation enables sophisticated RAG indexing:

1. **Equation-centered chunking** aligns with how users query mathematical content
2. **Rich metadata** (equation IDs, code locations, paper references) enables precise filtering
3. **Cross-references** enable graph-based multi-hop retrieval
4. **Multiple representations** (math, code, natural language) improve retrieval robustness
5. **Structured tables** provide exact-match capabilities for parameters and mappings

By implementing the strategies in this document, RAG systems can effectively retrieve mathematical content with high precision and recall.

