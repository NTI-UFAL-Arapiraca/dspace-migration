# DSpace Docker da Migração

Este diretório contém somente os arquivos usados para executar a instância do
DSpace necessária à migração:

| Arquivo | Uso |
| --- | --- |
| `docker-compose-rest.yml` | Backend DSpace, PostgreSQL, Solr, volumes persistentes e montagem do pacote SAF. |
| `docker-compose-dist.yml` | Build e execução da interface DSpace Angular customizada. |
| `Dockerfile.angular` | Compila o tema local sobre o código-fonte da versão oficial. |
| `backend/config/submission-forms.xml` | Formulários oficiais do backend com os overrides locais de metadados. |
| `frontend/themes/custom/` | SCSS, assets e componentes sobrescritos pelo projeto. |
| `frontend/config/config.prod.yml` | Configuração local carregada em tempo de execução. |
| `cli.yml` | Comandos administrativos, como criação do administrador e `filter-media`. |

## Inicialização

```bash
docker compose -p d10 -f docker-compose-dist.yml -f docker-compose-rest.yml \
  pull dspace dspacedb dspacesolr
docker compose -p d10 -f docker-compose-dist.yml -f docker-compose-rest.yml \
  build --pull dspace-angular
docker compose -p d10 -f docker-compose-dist.yml -f docker-compose-rest.yml up -d
```

O frontend não usa mais diretamente a imagem `*-dist` publicada. O
`Dockerfile.angular` parte da imagem oficial `dspace-10_x`, sobrepõe os arquivos
locais no tema oficial `custom`, compila a distribuição e reutiliza a imagem
oficial `dspace-10_x-dist` como runtime.

O backend negocia o idioma público por `Accept-Language` e devolve somente a
variante correspondente dos metadados. O qualifier do resumo em português é
`pt` (idioma-base da locale `pt_BR` no DSpace 10), enquanto
`dc.language.iso` continua recebendo `pt_BR`. Antes da compilação, o frontend
aplica um patch restrito à área administrativa: apenas o editor de metadados e
suas respostas de salvamento solicitam a projeção REST `allLanguages`, para que
nenhuma tradução fique oculta durante a edição.

O nome público do repositório vem de `DSPACE_NAME` e usa
`Repositório Institucional da UFAL` por padrão. O backend publica esse valor
como `dspace.name`; o frontend o reutiliza em títulos como “Estatísticas para
Repositório Institucional da UFAL”. Depois de alterar a variável, recrie o
container `dspace`.

## OAI-PMH

O módulo OAI-PMH está explicitamente habilitado no backend e usa o mesmo
container e a mesma porta da API REST. Com a configuração local padrão, o
endpoint é:

```text
http://localhost:8080/server/oai/request
```

Valide o protocolo com o verbo `Identify`:

```bash
curl --fail \
  'http://localhost:8080/server/oai/request?verb=Identify'
```

Depois de uma importação inicial ou reconstrução completa do acervo, popule o
core `oai` do Solr:

```bash
docker compose --env-file ../.env -p d10 -f cli.yml run --rm \
  dspace-cli oai import -c
```

O `-c` limpa somente o índice OAI antes de reconstruí-lo; não remove itens do
DSpace. Para uma atualização sem limpeza, omita essa opção. Em produção,
configure `DSPACE_SERVER_URL`, `DSPACE_UI_URL` e `DSPACE_ADMIN_EMAIL` no
`.env`. O hostname de `DSPACE_UI_URL` também é usado como prefixo padrão dos
identificadores OAI. `OAI_ENABLED` permite desligar o módulo e `OAI_PATH`
permite alterar apenas o segmento de URL.

## SEO: sitemap, robots.txt e SSR

O backend gera sitemaps XML e HTML diariamente às 01:15, conforme
`SITEMAP_CRON`, e mantém os arquivos no volume nomeado `sitemaps`. A geração
inicial pode ser executada da raiz do projeto com:

```bash
uv run generate-sitemaps
```

O frontend encaminha `/sitemap*` para esses arquivos e renderiza o template
versionado `frontend/overrides/robots.txt.ejs` em `/robots.txt`. Esse template
anuncia os dois índices e não bloqueia itens, handles, comunidades ou coleções.

SSR não é um processo separado: a imagem customizada reutiliza o entrypoint
`pm2-runtime` de `dspace-10_x-dist`, que executa `dist/server/main.js`. A
configuração local mantém `transferState` e a substituição da URL REST ativas.
Valide o ambiente iniciado com:

```bash
curl --fail http://localhost:4000/robots.txt
curl --fail http://localhost:4000/sitemap_index.xml
curl --fail http://localhost:4000/sitemap_index.html
```

Em produção, substitua `localhost` pelo domínio HTTPS e configure exatamente
esse domínio em `DSPACE_UI_URL`; caso contrário, robots e sitemaps anunciarão
URLs incorretas e validadores externos poderão considerar também o SSR
inacessível.

Acervos importados antes dessa normalização devem executar uma vez
`backend/sql/normalize_abstract_languages.sql` e depois `index-discovery -b`,
conforme `docs/2_configuracao_dspace.md`.

O tema `custom` é ativado em `frontend/config/config.prod.yml`. Mudanças em
SCSS, assets ou componentes exigem `build --no-cache dspace-angular` quando for
necessário invalidar todo o cache. Mudanças apenas nesse YAML exigem somente:

```bash
docker compose -p d10 -f docker-compose-dist.yml -f docker-compose-rest.yml \
  up -d --force-recreate dspace-angular
```

`DSPACE_VER` e `DSPACE_ANGULAR_TAG` usam `dspace-10_x`, o canal com as correções
mais recentes da linha 10, e devem permanecer alinhadas. Não use `latest` nem
`latest-test`: esses aliases podem avançar para uma versão principal
incompatível. `DSPACE_ANGULAR_IMAGE` pode ser usada para nomear a imagem
customizada. O tag Angular precisa existir tanto na forma normal quanto com o
sufixo `-dist` no repositório oficial de imagens.

> [!IMPORTANT]
> Um banco que já tenha executado migrações do DSpace 11 não deve ser aberto
> pelo backend 10. Em um ambiente descartável e ainda vazio, remova os volumes
> criados pela versão 11 antes de iniciar novamente. Em um ambiente com dados,
> restaure um backup feito ainda no DSpace 10.

O mesmo nome de projeto (`-p d10`) deve ser usado nos comandos de `cli.yml`,
pois esse arquivo conecta seus containers à rede e ao volume criados acima.

O serviço REST monta `../saf_bundle` por padrão e reutiliza `SAF_BUNDLE_DIR` se
ela estiver definida. `DSPACE_SAF_HOST_DIR` permite sobrescrever somente o
mount; nesse caso, seu caminho deve identificar o mesmo diretório usado pela
migração.

## Configuração do backend

O `submission-forms.xml` da imagem oficial está versionado em
`backend/config/` e é montado como somente leitura nos serviços `dspace` e
`dspace-cli`. As duas definições de `dc.description.abstract` são repetíveis e
expõem a seleção de idioma do DSpace; a lista inclui explicitamente `pt`, usado
como qualifier do resumo em português, além de `en`. O metadado
`dc.language.iso` continua usando `pt_BR`.

Depois de alterar essa configuração, recrie o backend:

```bash
docker compose -p d10 -f docker-compose-dist.yml -f docker-compose-rest.yml \
  up -d --force-recreate dspace
```

Consulte [`../docs/2_configuracao_dspace.md`](../docs/2_configuracao_dspace.md)
para a preparação completa e
[`../docs/3_importacao_dspace.md`](../docs/3_importacao_dspace.md) para a
importação.
