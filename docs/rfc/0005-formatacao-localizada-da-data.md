# RFC 0005 — Formatação localizada da data

- Status: aceita
- Escopo: frontend

## Contexto

`dc.date.issued` chegava em ISO e era mostrado dessa forma mesmo quando a
interface estava em português do Brasil.

## Decisão

Substituir o campo de data da página simples por um componente que formata
`YYYY-MM-DD` como `DD/MM/YYYY` e `YYYY-MM` como `MM/YYYY` somente em `pt-BR`.
Outros idiomas, anos isolados e datas inválidas permanecem inalterados.

## Implementação

`frontend/themes/custom/app/item-page/simple/item-types/untyped-item/date/` e o
registro do componente em `untyped-item.component.ts`.

## Consequências e validação

O valor persistido continua ISO; a mudança é apenas de apresentação. A spec
Angular do componente cobre datas completas, parciais, inválidas e idiomas, e
`test_frontend_customization.py` confirma seu uso na página.
