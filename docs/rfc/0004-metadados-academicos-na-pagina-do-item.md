# RFC 0004 — Metadados acadêmicos na página do item

- Status: aceita
- Escopo: frontend

## Contexto

A página simples oficial não mostrava orientador nem membros avaliadores da
banca, embora a migração preencha esses metadados.

## Decisão

Sobrescrever a página standalone do item sem tipo específico e exibir, logo
após os autores, `dc.contributor.advisor` e `dc.contributor.referee`. Os rótulos
são fornecidos em inglês e português do Brasil.

## Implementação

- `frontend/themes/custom/app/item-page/simple/item-types/untyped-item/`;
- `frontend/themes/custom/assets/i18n/en.json5`;
- `frontend/themes/custom/assets/i18n/pt-BR.json5`;
- registry listable descrito na RFC 0001.

## Consequências e validação

Itens sem esses campos não exibem blocos vazios. O teste
`test_untyped_item_shows_advisor_and_referees_after_authors` verifica campos,
rótulos e ordem visual.
