# Executar a migração em produção

O banco legado `biblioteca` fica na máquina local de extração. O servidor de
produção não precisa ter esse banco: o pacote SAF completo é gerado localmente,
copiado para o servidor e montado no container DSpace durante a importação.
Execute as etapas na ordem abaixo e pare se algum comando falhar.

## 1. Preparar os ambientes e revisar o piloto

- Conclua a [inicialização da migração](inicializacao.md).
- Conclua a [inicialização ou atualização do DSpace](../../../dspace-bca/docs/guias/inicializacao-producao.md).
- Revise o [piloto local](migracao-local.md) antes do lote definitivo.
- Defina um diretório exclusivo para o lote SAF local e outro caminho persistente no servidor.
- Faça backup do banco DSpace, do assetstore e dos SAFs/mapfiles já existentes.

O `SAF_BUNDLE_DIR` do projeto `dspace-migration` aponta para o SAF na máquina
onde cada comando é executado. Na máquina local ele aponta para a pasta de
extração; em produção aponta para a cópia recebida pelo servidor. No projeto
`dspace-bca`, configure `DSPACE_SAF_HOST_DIR` com o caminho absoluto do SAF no
servidor. Os dois caminhos de produção devem apontar para a mesma pasta do
servidor.

## 2. Gerar e conferir o SAF na máquina local

Na máquina que tem acesso ao PostgreSQL `biblioteca`, configure `DB_*` no
`.env` de `dspace-migration` para esse banco e defina `SAF_BUNDLE_DIR` para a
pasta local exclusiva deste lote. Execute na raiz do projeto:

```bash
uv sync
uv run extract-metadata
uv run extract-pdfs
```

Se estiver preparando um piloto limitado, use o mesmo `--limit` nos dois
comandos. Para o lote definitivo, não use `--limit`.

Confira os relatórios `routing_report.csv` e `pdf_extraction_issues.csv`,
quando presentes, e inspecione itens representativos. O bundle deve conter os
diretórios dos itens, `dublin_core.xml`, `metadata_local.xml` quando houver
campos locais, `contents`, `people.json` e `access_policies.json`. Corrija as
anomalias antes de transferir o lote.

Nesta etapa, não execute `uv run migrate`: esse comando também tenta preparar
o destino e importar no Docker. A geração local usa o banco legado somente
para produzir os dados e arquivos do SAF.

## 3. Copiar o bundle completo para produção

Copie o conteúdo completo da pasta SAF, incluindo os manifestos na raiz. Por
exemplo, com `rsync`:

```bash
SAF_BUNDLE_DIR="/caminho/local/lotes/lote-atual/saf_bundle"
ssh usuario@servidor \
  'mkdir -p /caminho/persistente/lotes/lote-atual/saf_bundle'
rsync -a --info=progress2 "$SAF_BUNDLE_DIR/" \
  usuario@servidor:/caminho/persistente/lotes/lote-atual/saf_bundle/
```

No servidor, confira se `people.json`, `access_policies.json` e os diretórios
de itens chegaram. Se for um lote novo, use uma pasta de lote vazia. Não
misture pacotes de lotes diferentes.

## 4. Preparar o DSpace e montar o SAF no servidor

No `.env` de `dspace-migration` em produção, defina `SAF_BUNDLE_DIR` com o
caminho absoluto da pasta copiada. Configure também a URL e as credenciais da
API DSpace usadas por `setup-dspace`, `apply-embargoes` e `apply-people`.
`DB_*` de `biblioteca` não é necessário para importar o SAF nem para aplicar
as pessoas e os embargos.

No `.env` de `dspace-bca`, defina `DSPACE_SAF_HOST_DIR` com o mesmo caminho
absoluto no servidor. A montagem no container é `/dspace/saf_bundle`.
O caminho precisa existir antes de iniciar o Compose e permitir que o processo
do DSpace leia os pacotes e grave os mapfiles durante a importação.
Prepare campos, autoridades e coleção Person seguindo a
[preparação acadêmica de produção](../../../dspace-bca/docs/guias/preparacao-academica.md).

Para permitir que o importador grave os `mapfile.txt`, habilite o overlay de
migração na composição de produção. Na raiz de `dspace-bca`:

```bash
docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  -f docker-compose-migration.yml config --quiet

docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  -f docker-compose-migration.yml up -d --no-build --force-recreate dspace
```

Aguarde a API voltar antes de continuar.
Confirme que o bundle aparece em `/dspace/saf_bundle` dentro do container
`dspace` antes de gerar o script de importação.

## 5. Criar a hierarquia e importar os itens

No servidor, na raiz de `dspace-migration`, confirme que `SAF_BUNDLE_DIR`
aponta para a cópia recebida e execute:

```bash
uv run setup-dspace
uv run generate-import-script
docker cp import_all.sh dspace:/dspace/import_all.sh
docker exec dspace bash /dspace/import_all.sh
```

O script importa os pacotes montados em `/dspace/saf_bundle` e grava os
mapfiles na pasta persistente do lote. Confira que os mapfiles foram gerados e
guarde uma cópia do SAF com eles. Não repita a importação do mesmo lote: o SAF
é aditivo e pode criar itens duplicados.

## 6. Aplicar embargos e pessoas

Ainda no servidor, aplique as políticas indicadas pelo manifesto copiado:

```bash
uv run apply-embargoes
uv run apply-people --dry-run
```

Revise a simulação de pessoas e resolva divergências. Depois aplique:

```bash
uv run apply-people
```

Para retomar esta etapa, repita `apply-people`. Preserve `people.json`,
`people-map.json`, `access_policies.json` e os mapfiles.

Se os trabalhos já foram importados e o objetivo for somente retomar pessoas,
gere `people.json` localmente com `uv run extract-metadata` para o mesmo lote e
transfira apenas esse manifesto para o SAF existente no servidor. Não
substitua os pacotes importados nem os mapfiles. Depois execute o dry-run e
`apply-people` no servidor.

## 7. Atualizar índices e revisar

Na raiz de `dspace-bca`, atualize o índice Discovery:

```bash
docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  exec -T dspace /dspace/bin/dspace index-discovery -b
```

Na raiz de `dspace-migration`, reconstrua OAI-PMH e sitemaps:

```bash
uv run rebuild-oai --docker-container dspace
uv run generate-sitemaps --docker-container dspace
```

Confira na interface:

- [ ] Metadados acadêmicos aparecem em Editar (`edit-items/`).
- [ ] Curso, campus e áreas CNPq têm valores corretos.
- [ ] Autor, orientador, coorientador e banca estão vinculados às pessoas esperadas.
- [ ] Os nomes abrem perfis, e cada perfil lista os trabalhos corretos.
- [ ] Resumos, PDFs e embargos continuam corretos.
- [ ] `routing_report.csv` e `pdf_extraction_issues.csv`, quando presentes, foram revisados.

## 8. Restaurar a montagem somente leitura

Depois da revisão, remova o overlay gravável e recrie o backend com a
composição regular de produção. Na raiz de `dspace-bca`:

```bash
docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  up -d --no-build --force-recreate dspace
```

Guarde o SAF, os mapfiles e os relatórios junto ao registro do lote. O banco
`biblioteca` não é necessário no servidor. A injeção das estatísticas
históricas é uma operação separada e exige acesso à origem e ao Solr; consulte
o [guia de estatísticas](estatisticas.md).

Para identidades e checkpoints, consulte a
[referência de pessoas](../referencia/pessoas-e-vinculos.md).
