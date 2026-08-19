# RFC 0006 — Alinhamento justificado do resumo

- Status: aceita
- Escopo: frontend

## Contexto

Resumos acadêmicos extensos devem usar alinhamento justificado na página do
documento, sem afetar os demais metadados.

## Decisão

Aplicar a classe local `document-abstract` somente ao componente de abstract e
definir `text-align: justify` no SCSS da página simples.

## Implementação

- `untyped-item.component.html`;
- `untyped-item.component.scss`;
- `untyped-item.component.ts`.

## Consequências e validação

A regra fica restrita ao resumo e não altera descrição, assunto ou citação. O
teste `test_untyped_item_justifies_only_the_abstract_field` valida esse escopo.
