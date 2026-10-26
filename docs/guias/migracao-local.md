# Executar um piloto local

Use o destino isolado `d10dev`, vazio, e uma pasta SAF exclusiva do piloto.
Execute um comando por vez e pare se houver erro.

## 1. Inicializar os projetos

Siga a [inicialização da migração](inicializacao.md) e a
[inicialização local do DSpace](../../../dspace-bca/docs/guias/inicializacao-local.md).
Confira `SAF_BUNDLE_DIR`, `DSPACE_SAF_HOST_DIR` e as credenciais do destino local.

## 2. Preparar metadados e pessoas

Na raiz de `dspace-bca`:

```bash
bash scripts/prepare-academic.sh --development --project-name d10dev \
  --env-file .env.development --migration-env-file ../dspace-migration/.env

docker compose --env-file .env.development -p d10dev \
  -f docker-compose-rest.yml -f docker-compose-dev.yml restart dspace
```

Aguarde a API voltar. Confira `DSPACE_PERSON_COLLECTION_UUID` no `.env` da migração.

## 3. Importar cinco trabalhos

```bash
cd ../dspace-migration
uv run migrate --limit 5 --docker-container d10dev-dspace \
  --skip-people --skip-stats --skip-oai --skip-sitemaps
```

Não repita essa importação no mesmo destino. Se já importou o piloto,
regenere somente o manifesto com `uv run extract-metadata --limit 5`,
usando a mesma origem e preservando os mapfiles.

## 4. Conferir e aplicar pessoas

```bash
uv run apply-people --dry-run
```

Revise as quantidades. Sem divergências:

```bash
uv run apply-people
```

## 5. Atualizar índices

```bash
cd ../dspace-bca
docker compose --env-file .env.development -p d10dev \
  -f docker-compose-rest.yml -f docker-compose-dev.yml \
  exec -T dspace /dspace/bin/dspace index-discovery -b

cd ../dspace-migration
uv run rebuild-oai --docker-container d10dev-dspace
uv run generate-sitemaps --docker-container d10dev-dspace
```

## 6. Revisar

Abra `http://localhost:4000/`. Confira os campos em Editar, links para as
pessoas e listas por papel. Revise resumos, ordem da banca, PDFs, embargos,
`routing_report.csv` e `pdf_extraction_issues.csv`, quando presente.
Depois da revisão, use o [roteiro de produção](migracao-producao.md). O lote
definitivo é extraído localmente do banco `biblioteca`, copiado ao servidor e
importado no DSpace de produção; não é necessário disponibilizar esse banco no
servidor.
