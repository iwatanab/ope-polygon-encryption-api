# ASA Conditions Pipeline: Rewritten Technical Documentation

## Purpose

This document rewrites the repository documentation as a single, developer-facing manual. It is designed to make the workflow easy to follow from code entrypoint to final report artifact, with special attention to the algorithmic details that are easy to miss in the current docs.

The pipeline processes a single patient at a time. It discovers the patient’s relevant longitudinal documents, downloads and converts them to markdown, extracts condition evidence from each document, groups semantically related conditions across documents, synthesizes patient-level condition summaries with ICD-10-CM coding, critiques those summaries, and assembles a structured report artifact.

This repository is a proof of concept. The code is modular and unusually well structured for a PoC, but several critical behaviors depend on private packages and Mayo-specific infrastructure.

---

## What the pipeline actually does

At a high level, the codebase is not just an “ICD coding” system. It performs a sequence of transformations:

1. **Patient and document discovery** from a FHIR store.
2. **Attachment download** for the selected documents.
3. **Document normalization** into markdown.
4. **Per-document condition extraction** using an LLM.
5. **Cross-document condition grouping** into longitudinal communities.
6. **Per-community synthesis and ICD coding** using an LLM.
7. **Critique and codification evaluation** of those synthesized outputs.
8. **Final report assembly** into a structured patient-level artifact.

The key design idea is:

> The pipeline first extracts **evidence-backed condition mentions**, then turns those mentions into **longitudinal condition communities**, then asks an LLM to reason over each community rather than over raw documents.

That separation is the core of the architecture.

---

## How to read this repository

If you are new to the codebase, read it in this order:

1. `README.md`
2. `simplified_workflow.py`
3. `asa_conditions_workflow/workflow/_01_...` through `_08_...`
4. `asa_conditions_workflow/models/`
5. `asa_conditions_workflow/utilities/`
6. `docs/stage_specific/`
7. `tests/`

That order mirrors the actual runtime flow.

---

## Repository map

### Top level

- `README.md` — short project overview and setup.
- `simplified_workflow.py` — the simplest end-to-end orchestration entrypoint.
- `example.ipynb` — notebook demonstration.
- `pyproject.toml` / `requirements.txt` — dependencies.
- `docs/` — the primary human-facing documentation.
- `benchmarks/` — benchmark definitions, data prep, and reports.
- `tests/` — unit and integration tests.
- `tools/` — optimization and helper tooling.

### Main package: `asa_conditions_workflow/`

- `models/` — Pydantic models that define stage boundaries and final artifacts.
- `workflow/` — thin stage orchestrators.
- `utilities/` — the real implementation logic.
- `prompts/` — prompt files used by the LLM-driven stages.
- `templates/` — Jinja templates used for context packing and reporting.
- `data/` — lookup/configuration files such as document type filters and code tables.

---

## Architectural style

The repository follows a clear internal pattern.

### 1. Stage orchestrators are intentionally thin

Files under `asa_conditions_workflow/workflow/` are wrappers over utility code. They usually do five things:

1. accept typed inputs,
2. load or skip cached artifacts,
3. convert models to plain dictionaries when needed,
4. call utility functions,
5. validate and return typed outputs.

The workflow README states this directly, and the stage files are consistent with that design.

### 2. Local artifact files are the orchestration state

The pipeline stores stage outputs under:

```text
<patient_path>/__artifacts/
```

This directory is the pipeline’s persistent working state. It is what allows stages to be rerun or skipped.

### 3. Pydantic is used at the main stage boundaries

The code relies on Pydantic models to make the handoffs explicit. This is one of the strongest parts of the codebase because it clarifies what each stage produces.

### 4. Internal utility code often drops back to dictionaries

Inside many utilities, models are converted to raw dictionaries and then later revalidated. This makes the code flexible, but it also means the strongest invariants live at stage boundaries rather than throughout the full call stack.

---

## End-to-end workflow entrypoint

The simplest end-to-end driver is `simplified_workflow.py`.

### Main runtime order

```python
main(patient_fhir_id, anchor_date, days_range)
```

calls, in order:

1. `document_discovery_stage(...)`
2. `download_documents_stage(...)`
3. `convert_documents_to_markdown_stage(...)`
4. `condition_extraction_stage(...)`
5. `consolidate_conditions_stage(...)`
6. `map_conditions_to_ontology_stage(...)`
7. `condition_summary_evaluation_stage(...)`
8. `assemble_report_data(...)`

That file is the best compact statement of what the system considers the “official” flow.

---

## Artifacts written by the pipeline

Artifact filenames are centralized in `workflow/__artifact_names.py`.

### Core artifacts by stage

#### Stage 1

- `01.1_documents.json` — discovered documents
- `01.2_filtered_docs.json` — filtered documents actually selected for processing
- `01.3_patient_info.json` — patient demographic / FHIR resource subset
- `01.4_ode_documents.json` — ODE coverage information

#### Stages 2–3

- `02_03_downloaded_docs.json` — downloaded documents after content acquisition and conversion metadata updates

#### Stage 4

- `04.1_4.2_extracted_conditions.json` — raw extracted conditions per document
- `04.3_post_processed_conditions.json` — extraction results after cleanup and sentence expansion

#### Stage 5

- `05_condition_embeddings.parquet` — stored condition embeddings for grouping
- `05_conditions_groups.json` — pre-community grouping state
- `05_conditions_communities.json` — post-community-detection grouping state
- `05_unique_conditions.json` — reconciled provenance-rich organized conditions

#### Stage 6

- `06.1_conditions_packed_context.json` — rendered condition-community histories used as LLM input
- `06.2_condition_summaries.json` — condition summary outputs
- `06.3_condition_codes.json` — extracted code-focused outputs

#### Stage 7

- `07.1_alignment_result.json` — set-level alignment output
- `07.1_condition_evaluations.json` — codification evaluation results
- `07.2_critic_condition_summaries.json` — critique outputs
- `07.3_failed_critic_logs.json` — failures / retry trail for the critic loop

#### Stage 8

- `08_report_data.json` — final `ProblemLhistory` report artifact

### Important clarification for Stage 5 artifacts

The current names can be misleading if you do not know the algorithm:

- `05_conditions_groups.json` is the **pre-community** grouping state.
- `05_conditions_communities.json` is the **post-Leiden** community state.
- `05_unique_conditions.json` is the **reconciled provenance-rich** organized condition output that later stages actually consume.

---

## Data model map

Below is the most useful conceptual map of the Pydantic models.

### Stage 1–3 document models

Defined in `models/integration_1_3_models.py`.

- `DocumentComponent` — one content attachment / content-bearing component.
- `ReferencedDocument` — one document with metadata and components.
- `DocumentCategory` — grouped bucket of documents.
- `CategorizedDocuments` — all filtered documents by category.
- `DocumentalRecord` — the working document collection used in later stages.

These models cover discovery, acquisition, and conversion.

### Stage 4 extraction models

Defined in `models/stage_4_models.py`.

- `Condition`
  - `condition_name`
  - supporting evidence fragments
- `ConditionExtraction`
  - list of extracted conditions for one unit of document content

These are intentionally lean. Stage 4 only commits to the existence of candidate conditions plus evidence.

### Stage 4 integration models

Defined in `models/integration_4_models.py`.

These tie extracted annotations back onto converted documents, creating an annotated document structure.

### Stage 5 organization models

Defined in `models/integration_5_models.py`.

- `MentionedCondition` — a condition mention plus provenance.
- `ConditionCommunity` — a cluster of related condition mentions.
- `OrganizedConditions` — the patient’s full cross-document condition organization.

This is the most important intermediate representation in the system.

### Stage 6 synthesis models

Defined in `models/stage_6_models.py` and `models/integration_6_models.py`.

These models are much richer. They represent:

- packed historical context,
- condition descriptors,
- temporal interpretation,
- ICD-10 proposals,
- alternative codes,
- excluded conditions,
- summary-level reasoning.

### Stage 7 validation models

Defined in `models/stage_7_models.py`.

These models hold:

- summary critique scores,
- critique comments,
- codification evaluation outputs,
- alignment information.

### Stage 8 final report model

Defined in `models/stage_8_models.py`.

The final output is `ProblemLhistory`, which holds:

- patient info,
- inferred conditions,
- community references,
- supporting documents,
- course summaries,
- codification context,
- quality scores.

---

# Detailed workflow

## Stage 1: Discover documents

**Orchestrator:** `workflow/_01_document_discover.py`

### Purpose

Gather all patient-side metadata required to start the pipeline:

- the patient resource,
- the candidate documents,
- the filtered document subset,
- the problem list,
- ODE document coverage.

### Main functions involved

From `utilities/document_discovery.py` and related files:

- `fetch_patient_resource(...)`
- `discover_patient_documents(...)`
- `acquire_problem_list(...)`
- `get_patient_mrn(...)`
- `fetch_and_save_ode_documents(...)`

### What the stage actually does

1. **Fetches the patient resource** from the FHIR system.
2. **Queries document-bearing resources** such as `DocumentReference` and `DiagnosticReport`.
3. **Applies time filtering** using `anchor_date` and `days_range`.
4. **Filters document types** using `data/fhir_document_types.csv`.
5. **Obtains the current problem list**, when available.
6. **Looks up ODE coverage** to determine whether a higher-quality extracted version of a document may already exist.

### Why this stage is important

This stage determines the evidence universe for the entire run. If the wrong documents are filtered out here, nothing downstream can recover them.

### Inputs

- `patient_fhir_id`
- optional `anchor_date`
- optional `days_range`

### Outputs

- `FhirPatientResource`
- `CategorizedDocuments`
- `list[StructuredCondition] | None`
- ODE coverage payload or `None`

### Practical note

The document type filter file is a major configuration control. Adjusting `use_doc_type` changes what evidence the pipeline sees.

---

## Stage 2: Download documents

**Orchestrator:** `workflow/_02_download_documents.py`

### Purpose

Take the selected FHIR documents and download their attached content to local storage.

### Main functions involved

Primarily from `utilities/document_acquisition.py`.

### What the stage does

For each selected document:

1. inspect the available content attachments,
2. resolve storage locations,
3. download the content locally,
4. update the working document representation with local file paths and content metadata.

### Outputs

- `DocumentalRecord`

This becomes the working document set used by the conversion and extraction stages.

### Design note

This stage does not yet normalize the content. It simply makes the source material available to later stages.

---

## Stage 3: Convert documents to markdown

**Orchestrator:** `workflow/_03_convert_documents.py`

### Purpose

Normalize heterogeneous source files into markdown, which is the pipeline’s canonical text representation.

### Why markdown is the canonical intermediate

Markdown is a practical compromise:

- simple enough for prompt input,
- preserves headings and some table structure,
- easier to inspect than raw OCR JSON,
- general enough to represent text from PDFs, HTML, RTF, and ODE-derived content.

### Core substeps

#### 3.1 Content deduplication

If a document has multiple content variants, the pipeline prefers one over the others. The current preference order is roughly:

1. `text/plain`
2. `text/html`
3. `text/xhtml`
4. `application/pdf`
5. `text/xml`
6. `application/rtf`

That means the system usually prefers text-native forms before resorting to PDF or RTF parsing.

#### 3.2 ODE conversion path

If ODE coverage exists for a document, the pipeline can favor that output instead of using local conversion.

This matters because ODE may already contain better OCR or structure extraction than the local conversion path can produce.

#### 3.3 Local conversion path

If ODE output is unavailable, local conversion is used.

The implementation uses multiple methods depending on the source type, including combinations of:

- PDF handling,
- HTML cleanup,
- markdownification,
- Document AI / OCR,
- pypandoc,
- local scanned-PDF processing helpers.

### Table normalization is part of the real Stage 3 story

This is easy to miss from the high-level docs.

The repository includes `utilities/tabular_data_optimizing.py`, which detects and restructures markdown tables into row-level mini blocks so that Stage 4 sentence splitting can operate on them reliably.

This matters because clinical documents often store crucial evidence in:

- labs,
- medication tables,
- vitals tables,
- form-like layouts.

If those tables remain monolithic, Stage 4 evidence matching becomes much weaker.

### Outputs

- Updated `DocumentalRecord` with markdown-bearing content components

### Worked example

#### Input

A PDF lab report with a visually nested boxed table.

#### Intermediate markdown from converter

```text
+----------------------------+
| +------------------------+ |
| | SODIUM P              | |
| +----------------------+ |
| mmol/L                   |
| 131*                     |
+----------------------------+
```

#### After table optimization

```markdown
| Lab | Units | Value |
| --- | --- | --- |
| SODIUM P | mmol/L | 131* |
```

That reshaping is what allows sentence splitting and evidence anchoring to treat the row as a usable evidence unit later.

---

## Stage 4: Extract conditions from each document

**Orchestrator:** `workflow/_04_condition_extraction.py`

### Purpose

For each converted document, extract candidate patient conditions and the specific evidence text that supports them.

### Why this stage matters

This is where the pipeline changes from document processing to clinical interpretation. But the output is still intentionally conservative: it does not yet produce final patient-level conditions. It produces **document-level condition mentions with evidence**.

### Threading model

This stage is multithreaded.

The orchestrator:

1. checks if cached Stage 4 artifacts already exist,
2. provisions input and output queues,
3. spawns worker threads,
4. processes documents in parallel,
5. writes results into the accumulator artifact.

The queue-based interface matters because Stage 5 consumes Stage 4 results after thread completion.

### Main utility functions

From `utilities/extract_conditions.py`:

- `check_existing_stage_4_artifact(...)`
- `provision_queues_and_threads(...)`
- `multi_threaded_condition_extraction(...)`
- `remove_errors(...)`
- `remove_hallucinated(...)`
- `add_chunk_expansion(...)`
- `post_process_extracted_document(...)`

### Raw extraction behavior

The LLM sees document markdown and is asked to return structured `ConditionExtraction` output.

At minimum, the pipeline expects each condition to have:

- a `condition_name`,
- one or more evidence fragments.

### Important cleanup steps

The post-processing pipeline is not cosmetic. It is part of the correctness strategy.

#### 1. Remove error envelopes

If an extraction result is wrapped as an error object, it is discarded.

#### 2. Remove hallucinated conditions

Conditions lacking evidence text are dropped. This is one of the strongest safeguards in the repository.

The implicit contract is:

> A condition without quoted evidence is not trustworthy enough to keep.

#### 3. Sentence-level context expansion

The pipeline does not keep only the exact snippet returned by the LLM. It attempts to remap those snippets back into the note and expand them into more usable condition-centric chunks.

This logic lives in `utilities/sentence_matching.py`.

### What sentence matching actually does

The sentence matcher:

1. preprocesses markdown, including table expansion,
2. splits notes into sentences,
3. matches LLM evidence snippets back to sentences,
4. recovers additional anchors if a snippet spans multiple note fragments,
5. optionally attaches nearby condition-name mentions,
6. expands around core evidence sentences,
7. resolves overlap conflicts between conditions,
8. returns one or more chunks per condition.

This is a substantial algorithmic step, not a simple regex pass.

### Worked example

#### Input note text

```text
Assessment:
The patient reports difficulty sleeping for three weeks.
Melatonin has not helped.
No shortness of breath today.
```

#### Raw Stage 4 extraction

```json
{
  "conditions": [
    {
      "condition_name": "insomnia",
      "original_texts": ["difficulty sleeping for three weeks"]
    }
  ]
}
```

#### After sentence expansion

```json
{
  "conditions": [
    {
      "condition_name": "insomnia",
      "original_texts": ["difficulty sleeping for three weeks"],
      "text_chunks": [
        "The patient reports difficulty sleeping for three weeks. Melatonin has not helped."
      ]
    }
  ]
}
```

This expanded chunk is what later gives Stage 5 and Stage 6 better clinical context.

### Outputs

- output queue of processed documents
- worker thread handles
- cached artifacts:
  - raw extraction output
  - post-processed output

---

## Stage 5: Group conditions, detect communities, reconcile provenance

**Orchestrator:** `workflow/_05_condition_consol_recon.py`

This is the most under-explained part of the repository and the conceptual center of the pipeline.

### Purpose

Take document-level extracted conditions and turn them into **patient-level longitudinal condition communities** with retained provenance.

### Main utility files

- `utilities/aggregate_conditions.py`
- `utilities/community_provenance.py` (later bridge logic that depends on Stage 5 structures)

### What Stage 5 is doing conceptually

The stage is solving a hard problem:

> Different documents may refer to the same underlying condition using different names, abbreviations, levels of specificity, or plain-language paraphrases. Merge those mentions into coherent condition communities without losing the supporting evidence.

### The real Stage 5 abstraction

The current docs speak about “grouping” and “community detection,” but the crucial missing detail is the object being clustered.

The stage is not clustering raw strings directly all the way through. The actual flow is closer to:

1. collect raw extracted condition mentions,
2. generate embeddings for those mentions,
3. form provisional groups based on similarity and ontology grounding,
4. build a weighted graph over those groups,
5. run community detection on that graph,
6. perform within-community consolidation,
7. reconcile those consolidated concepts back to document-level evidence.

### The key entities

#### Raw mention

One extracted condition from one document or subdocument.

Example:

```json
{
  "document_id": "doc_1",
  "condition_name": "CHF",
  "text_chunks": ["History of chronic CHF with edema"]
}
```

#### Provisional group

A set of mentions that appear to refer to the same condition concept or near neighbor before graph-level community detection.

#### Community

A cluster of related provisional groups found by community detection.

A community may correspond to:

- one clinical condition with synonyms,
- a small concept neighborhood that still needs internal consolidation,
- a mix of specific and generic terms that must later be normalized.

#### Reconciled community output

A final structure that preserves:

- the community identity,
- grouped concept labels,
- all supporting `MentionedCondition` items,
- document and page provenance.

### What is missing from the current docs

The current docs do not make explicit enough:

- what a node is,
- what an edge is,
- what gets clustered before and after ontology grounding,
- what “reconciliation” specifically means.

The easiest way to understand the stage is to see a worked example.

### Worked example: raw extractions to grouped communities

#### Stage 4 output from two documents

```json
{
  "doc_1": [
    {"condition_name": "heart failure", "text_chunks": ["..."]},
    {"condition_name": "insomnia", "text_chunks": ["..."]}
  ],
  "doc_2": [
    {"condition_name": "CHF", "text_chunks": ["..."]},
    {"condition_name": "inability to sleep", "text_chunks": ["..."]}
  ]
}
```

#### Provisional grouping intuition

```json
{
  "g1": {
    "terms": ["heart failure", "CHF"],
    "mentions": ["doc_1:heart failure", "doc_2:CHF"]
  },
  "g2": {
    "terms": ["insomnia", "inability to sleep"],
    "mentions": ["doc_1:insomnia", "doc_2:inability to sleep"]
  }
}
```

#### Graph intuition

- **Node** = provisional condition group
- **Edge** = semantic or ontology-informed similarity between groups
- **Community** = Leiden cluster of related groups

If `g1` and `g2` are unrelated, they end in separate communities.

### Why Leiden is used

The docs mention Leiden but do not explain why it matters.

Leiden is not a cosmetic choice. It improves on Louvain by adding a refinement phase that avoids badly connected communities. That matters here because later stages assume each community is a coherent clinical evidence neighborhood. If the graph partition is structurally poor, the LLM in Stage 6 gets low-quality grouped context.

### Within-community consolidation

After community detection, the code still has work to do. A community can contain:

- two groups that really are the same coded concept,
- one coded group plus one orphan plain-language variant,
- a generic term and a specific term that need deliberate handling.

The docs currently mention coded aliasing and orphan handling, but they need a more concrete example.

#### Example

Before consolidation:

```json
{
  "community_7": {
    "g10": {"snomed_code": "84114007", "terms": ["heart failure"]},
    "g11": {"snomed_code": "84114007", "terms": ["CHF"]},
    "g12": {"snomed_code": null, "terms": ["cardiac pump problem"]}
  }
}
```

After consolidation:

```json
{
  "community_7": {
    "84114007": {
      "terms": ["heart failure", "CHF", "cardiac pump problem"]
    }
  }
}
```

That kind of consolidation is what converts graph communities into patient-usable condition communities.

### Provenance reconciliation

This is another detail the current docs do not explain concretely enough.

The grouped community output must be reattached to the original Stage 4 evidence, including subdocument granularity.

That means the code is not merely saying “this condition came from document X.” It is trying to preserve:

- document ID,
- document type,
- document date,
- subdocument/page section,
- start page,
- end page,
- chunk text.

#### Example

Suppose Stage 5 has the grouped condition label `Sleeplessness`, and one of its original terms was `insomnia` from `docA`.

Stage 4 had two matching subdocument sections:

```json
[
  {
    "doc-sub-type": "Page 1",
    "start_page": 1,
    "end_page": 1,
    "results": {
      "conditions": [
        {"condition_name": "insomnia", "text_chunks": ["difficulty sleeping for 3 weeks"]}
      ]
    }
  },
  {
    "doc-sub-type": "Page 3",
    "start_page": 3,
    "end_page": 3,
    "results": {
      "conditions": [
        {"condition_name": "insomnia", "text_chunks": ["persistent insomnia despite melatonin"]}
      ]
    }
  }
]
```

The reconciled output should retain both provenance records under the grouped condition rather than collapsing them into one document-level blob.

### Hidden dependency: `asa-sct`

A critical architectural fact is that the most important Stage 5 logic is not fully visible in this repository. The graph building, ontology indexing, and some concept-comparison logic rely on the private `asa-sct` package.

That means the public repository documentation should explicitly say:

- what is implemented locally,
- what is delegated to `asa-sct`,
- what assumptions are made about the external ontology/index layer.

### Important missing detail: SNOMED hierarchy acceleration

The current repository docs imply ontology-aware grouping, but they do not reveal how SNOMED hierarchy membership or subsumption is accelerated under the hood.

There is no explicit bitmap or bitset implementation visible in this repository. If the system uses transitive-closure tables, bitmaps, roaring bitmaps, or another compressed hierarchy index, that implementation appears to live in the private dependency layer, not in the repo itself.

That distinction matters because it changes what this repository is responsible for versus what the external ontology runtime is responsible for.

### Outputs

- `OrganizedConditions`
- a community-view structure used for later synthesis
- saved embeddings / groups / communities / reconciled outputs

---

## Stage 6: Pack context and synthesize condition summaries with ICD coding

**Orchestrator:** `workflow/_06_condition_mapping.py`

### Purpose

Turn each Stage 5 condition community into a rich patient-level synthesis suitable for reporting and coding.

### Main functions involved

- `pack_context(...)` from `utilities/render_prompt_jinja.py`
- `extract_condition_summaries_codes(...)` from `utilities/llm_processing`

### What Stage 6 does

1. render each community’s evidence and history into a stable markdown context package,
2. send that context to the LLM,
3. receive structured condition evaluation output,
4. extract code-oriented artifacts and summary-oriented artifacts.

### Why Stage 6 is different from Stage 4

Stage 4 asks:

> What conditions appear in this one document, and what text supports them?

Stage 6 asks:

> Given all evidence for this condition community across the patient’s history, what is the coherent longitudinal interpretation and what ICD-10-CM coding best represents it?

This is a much higher-level reasoning step.

### Context packing

This step is more important than the docs currently convey.

The Jinja templates do the real work of transforming messy grouped evidence into a consistent prompt structure. They encode the community’s mention history, document evidence, and summary framing in a deterministic way.

Key templates include:

- `condition_cluster_history.j2`
- `condition_cluster_history_initial.j2`
- `condition_history.j2`
- `packed_context_template.md.j2`

### Worked example

#### Input community

```json
{
  "community_name": "Heart Failure",
  "mentions": [
    {
      "document_date": "2024-01-05",
      "condition_name": "CHF",
      "text_chunks": ["History of chronic CHF"]
    },
    {
      "document_date": "2024-03-11",
      "condition_name": "heart failure",
      "text_chunks": ["Symptoms improved after diuresis"]
    }
  ]
}
```

#### Packed prompt intuition

```markdown
## Condition Community: Heart Failure

### Mention 1
Date: 2024-01-05
Observed term: CHF
Evidence:
- History of chronic CHF

### Mention 2
Date: 2024-03-11
Observed term: heart failure
Evidence:
- Symptoms improved after diuresis
```

That packaged context is what the LLM actually reasons over.

### Output richness

Stage 6 outputs are not just code predictions. The models in `stage_6_models.py` support rich attributes such as:

- descriptor / wording,
- temporal assessment,
- condition facets,
- primary and alternative ICD-10 code sets,
- justifications,
- excluded conditions.

This is a broad “condition assessment” stage rather than a narrow coder.

### Outputs

- `condition_codes`
- `CommunitiesEval` (condition summaries / evaluations)
- `CommunitiesHistory` (packed contexts)

---

## Stage 7: Critique condition summaries and evaluate codification

**Orchestrator:** `workflow/_07_condition_evaluation.py`

### Purpose

Perform two distinct validation passes:

1. critique the quality of the synthesized condition summaries,
2. evaluate the proposed codifications against the problem list or evaluation machinery.

### Substage 7.1: Summary critic

This stage critiques the Stage 6 output using the original packed context plus the generated summary.

### Why it exists

The repository does not trust the first LLM output as final. Instead, it asks a second structured process to judge:

- whether the summary is well grounded,
- whether temporal interpretation is coherent,
- whether the synthesis is clinically plausible,
- whether the codification is justified.

### Important behavior: targeted regeneration

If a summary fails critique badly enough, the pipeline can rerun summary generation with access to the critique feedback. That means the critique stage is not just a scoring layer. It is part of a closed-loop repair mechanism.

This is one of the most mature design choices in the repository.

### Substage 7.2: Codification evaluation

This stage uses evaluation machinery to compare proposed code sets against a gold-standard problem list when available.

The visible code in `eval_functions.py` indicates:

- code sets are assembled from primary and alternative codifications,
- patient metadata and anchor-date context are supplied,
- a process-wide evaluator singleton is used,
- set-level alignment is computed separately.

### Alignment output

The alignment artifact captures how predicted codes align against available gold-standard codes, which is useful for evaluation and benchmarking.

### Outputs

- `CodeCheckedConditionEvaluations`
- `CritiquedConditionEvaluations`
- possibly updated `CommunitiesEval`

---

## Stage 8: Assemble final report data

**Orchestrator:** `workflow/_08_report_generation.py`

### Purpose

Combine all upstream artifacts into a final structured patient-level report.

### Main function involved

- `ProblemListMapper().map(...)`

### What the stage merges

- patient metadata,
- organized Stage 5 condition communities,
- Stage 6 evaluations,
- Stage 7 critiques,
- Stage 7 codification checks,
- document references,
- problem list context.

### Why this is not a trivial final formatting step

The stage must reconcile two views of the world:

1. the **evidence/provenance view** from Stage 5,
2. the **evaluated summary/coding view** from Stages 6 and 7.

The final artifact has to preserve both.

### Final model

The output `ProblemLhistory` includes concepts such as:

- inferred conditions,
- supporting documents,
- course summaries,
- codification context,
- quality/grade signals.

### Key product idea

The final report is not just a list of codes. It is a structured explanation of what the patient likely has, why the system thinks so, and how strongly that output survived critique and coding checks.

---

# The Stage 6 to Stage 8 provenance bridge

## Why `community_provenance.py` matters

This file deserves special explanation because it solves an important practical problem.

The LLM in Stage 6 may rename or merge conditions. Example:

- Stage 5 right-side community label: `Acid reflux`
- Stage 6 evaluated label: `Acid Reflux`
- Stage 6 excluded labels: `Voice impact`, `Decreased appetite`, both superseded by `Acid Reflux`

The system then must map the Stage 6 outputs back to the original Stage 5 synonym sets so it can recover evidence, provenance, and community identifiers.

## What the matcher actually does

The algorithm in `community_provenance.py` is much more sophisticated than a simple string match.

It performs:

1. **supersession folding** — excluded conditions are folded into canonical groups when they are superseded by an evaluated condition,
2. **normalization** — punctuation and casing are normalized,
3. **lexical scoring** — exact and fuzzy textual similarity,
4. **optional embedding scoring** — used when lexical certainty is not already high,
5. **deterministic locking** — clear 1:1 anchors are locked early,
6. **optional two-set merge proposals** — one evaluated condition may map to more than one right-side synonym set,
7. **global solving with reuse penalties** — avoids over-assigning the same right-side set everywhere,
8. **citation overlap estimation** — compares document-ID overlap fuzzily.

That is a real matching subsystem and should be documented as such.

### Worked example: supersession folding

#### Stage 6 output

```json
{
  "evaluated": [
    {"condition_name": "Acid Reflux"}
  ],
  "excluded": [
    {"condition_name": "Voice impact", "superseded_by": "Acid Reflux"},
    {"condition_name": "Decreased appetite", "superseded_by": "Acid Reflux"}
  ]
}
```

#### Right-side Stage 5 synonym sets

```json
[
  ["Acid reflux"]
]
```

#### Canonicalized matching group

```json
{
  "canonical_name": "Acid Reflux",
  "evaluated_name": "Acid Reflux",
  "excluded_members": [
    ["Voice impact", "Acid Reflux"],
    ["Decreased appetite", "Acid Reflux"]
  ]
}
```

This is the left-side object the matcher actually aligns.

### Worked example: two-set merge

Suppose Stage 6 returns:

```json
{
  "condition_name": "Chronic constipation and diarrhea"
}
```

but Stage 5 right-side synonym sets are:

```json
[
  ["Chronic constipation"],
  ["Chronic diarrhea"]
]
```

The matcher can consider a combination explanation rather than forcing a bad one-to-one assignment.

This is why `matched_right_rids` is a tuple rather than a scalar.

---

# Prompts and templates

## Prompt files

The repository stores stage prompts under `asa_conditions_workflow/prompts/`.

The major active prompt files are:

- `system_prompt_4.1_4.2.md`
- `system_prompt_6.2.md`
- `system_prompt_7.md`

These control the major LLM reasoning stages.

## Template files

The Jinja templates under `templates/` are part of the algorithm, not merely presentation assets.

They control:

- how evidence is packed,
- how community histories are rendered,
- how report sections are structured.

Any documentation of pipeline behavior should treat templates as execution-critical configuration.

---

# Benchmarks and tests

## Benchmarks

The `benchmarks/` directory contains staged benchmark scaffolding for:

- Stage 4 extraction,
- Stage 5 grouping,
- Stage 6 coding,
- Stage 7 summarization critique,
- end-to-end benchmark runs.

This indicates that the team is evaluating stages separately rather than only evaluating end-to-end performance.

## Tests

The test suite includes coverage around:

- sentence matching,
- table parsing,
- document conversion,
- discovery,
- ODE integration,
- stage boundaries,
- critique behavior,
- community provenance matching,
- integration workflows.

The strongest algorithmic test concentration appears to be around:

- sentence matching,
- table normalization,
- provenance/matching behavior.

That is appropriate because those areas are both fragile and central.

---

# Operational guidance

## Setup dependencies

To run the repository successfully, you need more than Python packages.

### Required environment and access

- access to the private Azure Artifacts feed,
- FHIR store access,
- Google Cloud access,
- Vertex / Gemini access,
- ODE access if using that integration,
- a valid `DATA_ROOT` for patient artifact storage.

### Important private dependencies

The architecture depends materially on private packages, especially:

- `asa-sct`
- `py-ode-client`

This should be made very explicit in the top-level docs because some of the most important semantic and ontology functionality lives outside this repository.

## Caching behavior

Most stages will skip work if the relevant artifact already exists and validates.

That is useful for development, but it also means:

- stale artifacts can mask code changes,
- reruns can appear successful without recomputation,
- debugging sometimes requires manual artifact deletion.

A good operator workflow is:

1. inspect `__artifacts/`,
2. delete only the stage outputs you want recomputed,
3. rerun from the appropriate orchestration entrypoint.

---

# What the current documentation should say more explicitly

## 1. What is local vs external

The current docs should separate:

- logic implemented in this repository,
- logic implemented in private packages,
- environment-specific infrastructure assumptions.

Without that, new developers cannot tell where to look when a Stage 5 or coding behavior seems “magical.”

## 2. What exactly is being clustered in Stage 5

The docs should define:

- mention,
- provisional group,
- group graph,
- community,
- consolidated community,
- reconciled provenance output.

Right now those ideas are present but not concrete enough.

## 3. Why the provenance bridge exists

The current docs mention Stage 6 and Stage 8 outputs but do not make clear that an explicit matching subsystem is needed because Stage 6 labels are not guaranteed to preserve Stage 5 naming.

## 4. Why table handling and sentence matching are correctness features

These are not cleanup niceties. They directly affect what evidence the LLM sees and what evidence is retained.

## 5. What the final report really represents

The final report is a fused artifact combining:

- extracted evidence,
- grouped longitudinal condition structure,
- LLM synthesis,
- critique output,
- coding evaluation,
- problem-list comparison.

It is not a single-model answer.

---

# Short end-to-end example

This example shows the full conceptual flow on a toy patient.

## Input documents

### Document A

```text
The patient reports difficulty sleeping for three weeks.
Melatonin has not helped.
```

### Document B

```text
Past medical history notable for chronic CHF.
Symptoms improved after diuresis.
```

## Stage 4 output

```json
{
  "docA": [
    {"condition_name": "insomnia", "text_chunks": ["difficulty sleeping for three weeks. Melatonin has not helped."]}
  ],
  "docB": [
    {"condition_name": "CHF", "text_chunks": ["Past medical history notable for chronic CHF. Symptoms improved after diuresis."]}
  ]
}
```

## Stage 5 output

```json
{
  "communities": {
    "community_1": {
      "label": "Insomnia",
      "mentions": ["docA:insomnia"]
    },
    "community_2": {
      "label": "Heart Failure",
      "mentions": ["docB:CHF"]
    }
  }
}
```

## Stage 6 output

```json
{
  "community_1": {
    "evaluated_conditions": [
      {
        "condition_name": "Insomnia",
        "condition_descriptor": "persistent insomnia",
        "proposed_icd_10_codification": [{"code": "G47.00", "title": "Insomnia, unspecified"}]
      }
    ]
  },
  "community_2": {
    "evaluated_conditions": [
      {
        "condition_name": "Heart Failure",
        "condition_descriptor": "chronic heart failure",
        "proposed_icd_10_codification": [{"code": "I50.9", "title": "Heart failure, unspecified"}]
      }
    ]
  }
}
```

## Stage 7 output

```json
{
  "community_1": {"critic": "pass", "coding_check": "acceptable"},
  "community_2": {"critic": "pass", "coding_check": "acceptable"}
}
```

## Stage 8 output

A final `ProblemLhistory` report with:

- the patient,
- inferred condition entries for insomnia and heart failure,
- supporting evidence references to Documents A and B,
- coding context,
- critique/evaluation metadata.

---

# Recommended rewrite targets for the repo docs

If this documentation is split back into the repository docs, the best structure is:

## `README.md`

Keep brief, but make these explicit:

- what the pipeline does in one paragraph,
- what private dependencies are required,
- what the entrypoint is,
- where the full workflow manual lives.

## `docs/ASA_Workflow.md`

Turn into the main conceptual manual:

- stage-by-stage flow,
- concrete inputs/outputs,
- one example for each stage,
- explicit Stage 5 and provenance-bridge explanations.

## `docs/Artifact_Descriptions.md`

Turn into a practical operator’s reference:

- exact artifact names,
- which stage writes them,
- what they contain,
- whether they are pre- or post-reconciliation,
- whether deleting them forces recomputation.

## `docs/stage_specific/stage_5_condition_aggregation.md`

Expand substantially:

- define node/edge/community,
- explain grouping flow,
- show pre- and post-community examples,
- clarify what is handled by `asa-sct`.

## `docs/stage_specific/stage_6_community_provenance.md`

Add:

- supersession folding example,
- deterministic locking example,
- combo merge example,
- explanation of why Stage 6 labels cannot be assumed to equal Stage 5 labels.

## `docs/stage_specific/stage_8_problem_list_mapper.md`

Explain how evaluated conditions, critiques, codification checks, and evidence all converge into `ProblemLhistory`.

---

# Final assessment of the codebase

This repository is best understood as a staged, artifact-backed, longitudinal clinical condition synthesis pipeline.

Its strongest design choices are:

- clear stage decomposition,
- typed stage boundaries,
- evidence-first extraction,
- explicit condition grouping before final coding,
- critique and regeneration loop,
- provenance retention.

Its biggest documentation gaps are:

- hidden Stage 5 algorithmic assumptions,
- insufficient explanation of graph/community semantics,
- unclear boundary between this repo and private ontology/evaluation packages,
- underdocumentation of the Stage 6 to Stage 8 provenance matcher.

Once those are made explicit, the codebase becomes much easier to reason about.
