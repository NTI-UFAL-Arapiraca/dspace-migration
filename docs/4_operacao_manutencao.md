# Operação e Manutenção do DSpace

Este guia reúne os cuidados recorrentes das integrações OAI-PMH e SEO. Os
comandos assumem a raiz do projeto, a instância Compose `d10` e os serviços já
iniciados.

## 1. URLs públicas e proxy reverso

Em produção, nunca mantenha `localhost` nas variáveis públicas:

```dotenv
DSPACE_SERVER_URL=https://repositorio.exemplo.br/server
DSPACE_UI_URL=https://repositorio.exemplo.br
DSPACE_ADMIN_EMAIL=biblioteca@exemplo.br
```

As duas URLs precisam representar exatamente os endereços acessíveis na
internet, sem barra final. Elas são usadas em links REST, OAI, robots e
sitemaps. Depois de alterá-las, recrie backend e frontend e regenere os índices:

```bash
cd dspace-docker
docker compose --env-file ../.env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml \
  up -d --no-deps --force-recreate dspace dspace-angular
cd ..
uv run rebuild-oai
uv run generate-sitemaps
```

O proxy reverso deve encaminhar `Host`, `X-Forwarded-Host`,
`X-Forwarded-Proto` e o IP do cliente, preservar `/robots.txt` e `/sitemap*` na
raiz pública e direcionar as páginas da interface ao serviço SSR na porta
`4000`. Não sirva apenas os arquivos JavaScript do bundle Angular, pois isso
desativa a renderização no servidor.

## 2. Sitemaps

O backend atualiza os sitemaps diariamente às 01:15. O horário é configurável
por `SITEMAP_CRON` e usa a expressão Quartz definida no `.env`. Os arquivos
ficam no volume Docker `sitemaps`; não remova esse volume durante uma recriação
normal dos containers.

Execute uma geração manual depois de:

- uma migração ou importação em lote executada fora de `uv run migrate`;
- alterações em massa, exclusões, retiradas ou reintegrações de itens;
- mudança de domínio ou de `DSPACE_UI_URL`;
- restauração do banco ou recriação do volume de sitemaps.

```bash
uv run generate-sitemaps
```

Uma falha nessa etapa não altera os itens do DSpace. Corrija o backend e execute
novamente o comando. Monitore se os índices continuam acessíveis:

```bash
curl --fail "$DSPACE_UI_URL/robots.txt"
curl --fail "$DSPACE_UI_URL/sitemap_index.xml"
curl --fail "$DSPACE_UI_URL/sitemap_index.html"
```

Confira também se as URLs `<loc>` do XML usam o domínio HTTPS público, e não
`localhost`, nomes de container ou HTTP interno.

## 3. Robots.txt

O template mantido em
`dspace-docker/frontend/overrides/robots.txt.ejs` é compilado dentro da imagem
Angular. Qualquer alteração nele exige rebuild e recriação do frontend:

```bash
cd dspace-docker
docker compose --env-file ../.env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml \
  up -d --build --no-deps dspace-angular
```

Não bloqueie `/items/`, `/handle/`, `/communities/` ou `/collections/`. Antes de
adicionar uma regra ampla, confirme que ela não impede o acesso anônimo às
páginas dos documentos ou PDFs públicos. As duas linhas `Sitemap:` devem
continuar presentes e apontar para arquivos que respondem HTTP 200.

## 4. Server-side rendering

SSR é fornecido pelo runtime oficial `dspace-10_x-dist`, que inicia
`/app/dist/server/main.js` por PM2. Mudanças no tema, componentes, patches,
`robots.txt` ou dependências exigem um novo build; apenas recriar um container
com uma imagem antiga não incorpora essas mudanças.

Depois de atualizar a imagem ou o proxy, teste uma página real sem depender de
JavaScript:

```bash
curl --fail "$DSPACE_UI_URL/items/<uuid-do-item>" -o /tmp/item-ssr.html
rg '<title>|citation_title|dc.description.abstract' /tmp/item-ssr.html
```

O HTML deve conter o título e metadados do item. Uma página que contém apenas o
elemento raiz vazio do Angular indica que o proxy está servindo CSR ou que o
processo SSR não está sendo usado. Verifique os logs com:

```bash
docker logs --tail 200 dspace-angular
```

## 5. OAI-PMH

Execute a reconstrução OAI depois de importações em lote, restaurações ou
alterações que precisem aparecer imediatamente para colhedores:

```bash
uv run rebuild-oai
```

O comando limpa e reconstrói somente o core OAI; não remove itens do DSpace.
Não interrompa o processo durante uma reconstrução. Ao final, valide:

```bash
curl --fail \
  "$DSPACE_SERVER_URL/oai/request?verb=Identify"
curl --fail \
  "$DSPACE_SERVER_URL/oai/request?verb=ListRecords&metadataPrefix=oai_dc"
```

Confira `repositoryName`, `baseURL`, `adminEmail`, ausência de `<error>` e a
presença de registros ou `resumptionToken`. Itens privados, retirados ou ainda
embargados não devem ser expostos anonimamente.

## 6. Volumes e atualizações

Os dados não devem depender do filesystem efêmero dos containers. Preserve e
inclua no plano de backup, conforme a política da infraestrutura:

- `pgdata`: banco do DSpace;
- `assetstore`: PDFs e demais bitstreams;
- `solr_data`: índices de busca, estatísticas e OAI;
- `sitemaps`: arquivos XML e HTML gerados.

Os índices Solr, OAI e sitemaps podem ser reconstruídos, mas banco e assetstore
precisam ser restaurados como um conjunto consistente. Não use
`docker compose down -v` em produção: a opção `-v` remove os volumes.

Ao atualizar o tag `dspace-10_x`, execute a suíte e o build completo, pois os
patches do frontend têm guardas que falham quando o fonte oficial muda:

```bash
uv run python -m unittest discover -s tests -v
cd dspace-docker
docker compose --env-file ../.env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml \
  build --pull dspace-angular
```

## 7. Checklist após migração ou manutenção

- API REST responde e anuncia as URLs públicas corretas;
- uma página de item contém título e metadados no HTML SSR;
- `robots.txt` responde 200 e referencia os dois sitemaps;
- sitemap XML e HTML respondem 200 e usam o domínio público;
- OAI `Identify` e `ListRecords` respondem sem erro;
- um PDF público baixa anonimamente e um PDF embargado continua protegido;
- busca, home e página do item exibem apenas o resumo do idioma selecionado;
- containers não apresentam erros recorrentes nos logs.
