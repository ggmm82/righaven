# Schema model and documentation overrides

`model.json` (version 1) is engine neutral:

```yaml
name: vendite
description: Vendite del negozio online
source: {kind: ddl, dialect: postgres}     # metadata | ddl | files | documented
tables:
  - schema: vendite
    name: ordine
    description: Ordini di vendita
    rows: 500                               # rows per stub batch
    owner: ufficio commerciale
    grain: un ordine
    primary_key: [id]
    unique: [[numero]]
    foreign_keys:
      - {columns: [cliente_id], references: {schema: vendite, table: cliente, columns: [id]}, declared: true}
    checks:
      - {name: importo_positivo, expression: "importo >= 0"}
    columns:
      - {name: id, type: BIGINT, nullable: false, description: Numero interno}
      - {name: email_cliente, type: VARCHAR(120), pii: true, description: Email di contatto}
      - {name: stato, type: VARCHAR(10), generator: {values: [nuovo, pagato, spedito], weights: [2, 5, 3]}}
```

Types are SQLGlot portable types; `sqlglot.ddl` renders them per engine (unsigned integers widen, `VARCHAR(MAX)` becomes `TEXT`, Fabric text is capped at 8000).

## Documentation overrides (`overrides`)

Same shape, only the fields to add: table `description`, `labels`, `rows`, `owner`, `grain`, `refresh`; column `description`, `pii`, `labels`, `generator`, `example`; `foreign_keys` that are documented but not declared (stored with `declared: false`, shown as virtual relations in the catalog, not created as constraints). A documented type that differs from the observed one is reported in `issues`, never applied.

## Stub generator hints (`generator`)

`values` (+ `weights`), `min`/`max`, `faker` (any Faker provider, e.g. `company_vat`, `ssn` for the Italian fiscal code, `iban`), `pattern` (Faker bothify, `??-####`), `null_ratio`, `constant`, `start`/`step` for integer keys, `days_back` for dates. Simple CHECK constraints (`IN`, `>=`, `BETWEEN`) are applied automatically; other CHECKs are reported. Without hints the generator uses the column name (email, telefono, cap, partita_iva, codice_fiscale, importo, quantita, stato, ...) and the type.
