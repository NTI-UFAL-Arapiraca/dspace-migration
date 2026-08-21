# RFC 0011 — Endpoint OAI-PMH

- Status: aceita
- Escopo: backend

## Contexto

O DSpace 10 incorpora o módulo OAI-PMH no mesmo Spring Boot da API REST, mas o
projeto não declarava sua ativação nem as URLs públicas usadas para construir o
`baseURL` e os identificadores. Também permanecia o e-mail administrativo de
exemplo da distribuição oficial. Sem uma etapa documentada de importação, o
core `oai` do Solr pode não representar o acervo migrado.

## Decisão

- habilitar explicitamente `oai.enabled` e manter o path configurável;
- publicar o protocolo em
  `${DSPACE_SERVER_URL}/${OAI_PATH}/request`;
- tornar configuráveis as URLs públicas e o e-mail administrativo;
- usar o core `oai` já criado pelo serviço Solr;
- executar `dspace oai import -c` depois da carga inicial do acervo;
- incluir a reconstrução no pipeline unificado e oferecer o comando isolado
  `uv run rebuild-oai`.

O OAI permanece no processo do backend existente; não é criado um container ou
uma porta adicional.

## Implementação

- `dspace-docker/docker-compose-rest.yml`;
- `.env.example`;
- `src/dspace_migration/cli.py` e o entrypoint em `pyproject.toml`;
- documentação operacional em `README.md`, `docs/` e
  `dspace-docker/README.md`.

## Consequências e validação

Alterações de configuração exigem apenas recriar o container `dspace`. Depois
de importar o índice, uma requisição `Identify` deve responder OAI-PMH 2.0 e
`ListRecords` deve expor somente itens públicos. Em produção,
`DSPACE_SERVER_URL` e `DSPACE_UI_URL` precisam usar o domínio HTTPS definitivo,
pois aparecem nas respostas e participam dos identificadores OAI. Os testes
protegem o contrato do Compose, a etapa do pipeline e o comando Docker exato.
