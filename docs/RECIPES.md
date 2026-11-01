# Recipes

A recipe is a tested path for one kind of work: which documents to attach, which
questions will be asked, which phases run, where you are asked to confirm and what
you receive at the end. Recipes are offered on demand: nothing has to be installed
or activated beforehand. Their tools are prepared automatically at the first
assignment that needs them (a few minutes the first time; later runs reuse the
prepared image).

## Two ways to start

1. **Recipes page** (sidebar → *Work* → *Recipes*). Each card shows *What you attach*,
   *What you will be asked*, *What you get*, *How it runs* and *Before you start*.
   **Use this recipe** opens a new task with the starter message already written in
   your language: fill in the bracketed parts, attach the files and send.
2. **Just describe the work.** The coordinator receives the recipe catalog with the
   skills it is allowed to use; when a request matches a recipe it proposes it, asks
   only for what is missing and follows the recipe's phases. You can decline and the
   ordinary method is used.

During the run, phases marked as checkpoints stop and ask you to confirm (for the data
pipeline: intake, catalog review, BI tables). The final delivery separates the
products, their editable sources and the verification report, which states what was
tested and what remains to be tested outside RigHaven.

## Recipe: end-to-end data pipeline

| | |
|---|---|
| **You attach** | at least one description of the schema: DDL scripts (schema only), an analysis document (PDF, Word, Excel) or sample JSON/XML/Parquet/CSV files. Useful: data dictionary, priority tables, examples of the expected reports, schedule constraints. Never: production passwords. |
| **You are asked** | source database, production destination (PostgreSQL, SQL Server, Microsoft Fabric), BI tool, frequencies, test batch size, unless already stated. |
| **You get** | data catalog (a page per table, relationship diagram, personal data marked), schema model and creation scripts per database, empty local replica with synthetic test batches, production package (ingestion, transformations, BI tables, schedule, container, CI, release guide), verification report. |
| **You prepare** | nothing to start. To go to production afterwards: a Docker host or a Fabric workspace and a read-only account on the source. |

Technical details: [Data Engineering](DATA-ENGINEERING.md#recipe-end-to-end-data-pipeline).

## Adding a recipe

A recipe is an entry in `righaven/recipes.json` (texts in Italian and English, the
skill that holds its method, the catalog tools, an environment preset) plus that
skill under `skills/custom/`. `scripts/validate.py` and `tests/test_recipes.py` check
that skill, tools and preset exist and that both languages describe the same phases.
