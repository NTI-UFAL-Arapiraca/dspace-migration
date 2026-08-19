# RFC 0009 — Ocultação de notas internas

- Status: aceita
- Escopo: backend

## Contexto

A migração usa `dc.description.provenance` para notas internas relacionadas a
restrição e embargo. Esse conteúdo não deve ser exposto anonimamente.

## Decisão

Sobrescrever `metadata.hide.dc.description.provenance=true` por variável de
ambiente no serviço REST. O valor continua disponível a administradores e para
rotinas internas do DSpace.

## Implementação

`dspace-docker/docker-compose-rest.yml`, variável
`metadata__P__hide__P__dc__P__description__P__provenance`.

## Consequências e validação

A alteração exige recriar o container do backend, sem rebuild da imagem. O
pipeline mantém o campo no SAF; apenas sua exposição pública é restringida.
