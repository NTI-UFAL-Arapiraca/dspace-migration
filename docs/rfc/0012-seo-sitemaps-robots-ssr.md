# RFC 0012 — SEO: sitemaps, robots.txt e SSR

- Status: aceita
- Escopo: frontend, backend e pipeline

## Contexto

O validador SEO indicava sitemap e `robots.txt` ausentes ou inacessíveis e SSR
desabilitado. A imagem Angular já executava o servidor SSR de produção e
entregava `robots.txt`, mas o backend ainda não havia gerado os arquivos de
sitemap. Sem eles, `/sitemap_index.xml` retornava 404 e os links anunciados no
`robots.txt` eram inválidos. Recriar o backend também apagaria os arquivos
gerados no filesystem efêmero do container.

## Decisão

- manter o runtime oficial `dspace-10_x-dist`, que executa
  `/app/dist/server/main.js` e renderiza páginas no servidor;
- declarar `transferState` e substituição da URL REST na configuração SSR;
- versionar o template `robots.txt.ejs`, mantendo páginas públicas rastreáveis
  e anunciando os índices XML e HTML;
- persistir `/dspace/sitemaps` em volume Docker;
- manter o agendamento diário oficial às 01:15;
- gerar os sitemaps ao final de `uv run migrate` e oferecer
  `uv run generate-sitemaps` para execução isolada.

## Implementação

- `dspace-docker/Dockerfile.angular` e
  `frontend/overrides/robots.txt.ejs`;
- `frontend/config/config.prod.yml`;
- `dspace-docker/docker-compose-rest.yml`;
- `src/dspace_migration/cli.py` e `pyproject.toml`;
- `.env.example` e documentação operacional.

## Consequências e validação

O frontend publica `/robots.txt`, `/sitemap_index.xml` e
`/sitemap_index.html`; as rotas de sitemap são encaminhadas ao backend. A
geração inicial deixa o conteúdo imediatamente disponível e o scheduler o
atualiza diariamente. `DSPACE_UI_URL` deve ser a URL HTTPS pública em produção,
pois é inserida no robots e nos sitemaps. Testes cobrem configurações, volume,
pipeline e política de crawlers; a validação ponta a ponta exige respostas 200
nos três arquivos e HTML de um item contendo título e metadados sem executar
JavaScript.
