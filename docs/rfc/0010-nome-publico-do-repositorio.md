# RFC 0010 — Nome público do repositório

- Status: aceita
- Escopo: backend

## Contexto

O Compose oficial usava `DSpace Started with Docker Compose` como valor de
`dspace.name`. A API REST publica esse valor e o frontend o insere em textos
como “Estatísticas para DSpace Started with Docker Compose”, expondo um
placeholder técnico aos usuários.

## Decisão

Configurar `dspace.name` como `Repositório Institucional da UFAL` por padrão e
permitir sua substituição pela variável `DSPACE_NAME`. O nome permanece em uma
única fonte no backend; o frontend apenas consome o valor publicado pela API.

## Implementação

- `dspace-docker/docker-compose-rest.yml`;
- `.env.example`;
- documentação operacional em `README.md` e `dspace-docker/README.md`.

## Consequências e validação

A alteração exige apenas recriar o container `dspace`; não requer rebuild do
frontend nem reindexação do Solr. A raiz da API REST deve retornar
`"dspaceName": "Repositório Institucional da UFAL"`, e as páginas de
estatísticas passam a usar esse nome. O teste
`test_public_repository_name_is_institutional_and_configurable` impede o
retorno do placeholder oficial.
