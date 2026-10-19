# Operação da migração

Execute na raiz de `dspace-migration`, com o destino já inicializado.
Os exemplos usam o container de produção `dspace`. No desenvolvimento,
use `d10dev-dspace` e as URLs locais.

## 1. Atualizar índices e sitemaps

Depois da aplicação dos vínculos, execute Discovery em `dspace-bca`:

```bash
cd ../dspace-bca
docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  exec -T dspace /dspace/bin/dspace index-discovery -b

cd ../dspace-migration
uv run rebuild-oai --docker-container dspace
uv run generate-sitemaps --docker-container dspace
```

Depois de alterar `DSPACE_SERVER_URL` ou `DSPACE_UI_URL`, siga também a
[operação do servidor](../../../dspace-bca/docs/guias/operacao.md). O proxy
precisa preservar `Host` e `X-Forwarded-Proto`. O funcionamento de
`frontend/overrides/robots.txt.ejs` e do SSR em `/app/dist/server/main.js`
está na [referência de implantação](../../../dspace-bca/docs/referencia/implantacao.md).

## 2. Checklist após migração ou manutenção

Substitua o domínio ilustrativo pelos endereços públicos configurados:

```bash
curl --fail https://repo.interno.example.org/dspace/robots.txt
curl --fail https://repo.interno.example.org/dspace/sitemap_index.xml
curl --fail https://repo.interno.example.org/dspace/sitemap_index.html
curl --fail 'https://repo.interno.example.org/dspace-server/oai/request?verb=Identify'
curl --fail 'https://repo.interno.example.org/dspace-server/oai/request?verb=ListRecords&metadataPrefix=oai_dc'
```

- Confira URLs, contato administrativo e ausência de erros OAI.
- Confira título e metadados no HTML de uma página de item (SSR).
- Revise campos acadêmicos e listas de trabalhos nos perfis Person.
- Teste resumos em português e inglês e a ordem dos nomes.
- Teste download público e proteção de um PDF embargado.
- Confira GeoIP e logs no servidor; revise os relatórios CSV da migração.

## 3. Preservar dados para retomada

Guarde o banco e assetstore como conjunto consistente e conserve o SAF,
`people.json`, `people-map.json`, `access_policies.json`, os mapfiles e os
relatórios do lote. Inclua `solr_data` e `sitemaps` no plano de recuperação.
Não execute `docker compose down -v` em produção: a opção remove volumes.

Para retomar pessoas, use `apply-people`. Para estatísticas, use
`inject-stats`. Não repita a importação SAF sobre o mesmo lote.

## 4. Executar os testes

```bash
uv run python -m unittest discover -s tests -v
git diff --check
```

Mudanças no tema ou nos patches precisam também da compilação da interface
pelo workflow de `dspace-bca`. A publicação permanece pelo GitHub/GHCR.
