# RFC 0008 — Formulário de resumos multilíngues

- Status: aceita
- Escopo: backend

## Contexto

Um item pode conter mais de um `dc.description.abstract`, distinguido pelo
qualifier de idioma. O formulário oficial não garantia a manutenção dessas
entradas em todos os formulários usados pelo projeto.

## Decisão

Montar uma cópia controlada de `submission-forms.xml` nos containers REST e
CLI. As duas definições de abstract são `repeatable=true`, habilitam o seletor
`common_iso_languages` e oferecem `pt` e `en`.

## Implementação

- `dspace-docker/backend/config/submission-forms.xml`;
- mounts em `docker-compose-rest.yml` e `cli.yml`.

## Consequências e validação

O arquivo deve ser reextraído e os overrides reaplicados ao atualizar o DSpace.
Os testes XML verificam ambos os formulários, repetibilidade, seletor e códigos
armazenados. A negociação pública é uma decisão separada, descrita na RFC 0007.
