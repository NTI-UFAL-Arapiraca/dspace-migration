# Executar a importação por etapas

Use este roteiro quando quiser controlar cada etapa de um lote novo. Em
produção, a extração e a importação ocorrem em máquinas diferentes: o banco
`biblioteca` é acessado localmente e o SAF é transferido para o servidor.
Para o fluxo completo e a lista de verificações, consulte o
[roteiro de produção](migracao-producao.md).

## 1. Gerar os metadados e arquivos localmente

Na máquina com acesso ao PostgreSQL `biblioteca`, configure `DB_*` e um
`SAF_BUNDLE_DIR` local exclusivo no `.env` de `dspace-migration`. Execute na
raiz do repositório:

```bash
uv run extract-metadata
uv run extract-pdfs
```

Use o mesmo `--limit` nos dois comandos para um lote de teste. Revise
`routing_report.csv`, `pdf_extraction_issues.csv` e os itens do SAF. O bundle
inclui os metadados, PDFs, `people.json` e `access_policies.json`.

## 2. Transferir o SAF e montar no DSpace

Copie o conteúdo completo da pasta SAF para uma pasta persistente no servidor,
por exemplo:

```bash
SAF_BUNDLE_DIR="/caminho/local/lotes/lote-atual/saf_bundle"
ssh usuario@servidor \
  'mkdir -p /caminho/persistente/lotes/lote-atual/saf_bundle'
rsync -a --info=progress2 "$SAF_BUNDLE_DIR/" \
  usuario@servidor:/caminho/persistente/lotes/lote-atual/saf_bundle/
```

No servidor, configure `SAF_BUNDLE_DIR` no `.env` de `dspace-migration` e
`DSPACE_SAF_HOST_DIR` no `.env` de `dspace-bca` com o caminho absoluto da
cópia. Siga o passo 4 do [roteiro de produção](migracao-producao.md) para
preparar os campos e habilitar a montagem gravável que receberá os mapfiles.

## 3. Preparar a hierarquia e importar

No servidor, na raiz de `dspace-migration`:

```bash
uv run setup-dspace
uv run generate-import-script
docker cp import_all.sh dspace:/dspace/import_all.sh
docker exec dspace bash /dspace/import_all.sh
```

O script lê os itens em `/dspace/saf_bundle` e grava `mapfile.txt` junto aos
pacotes de cada coleção. Preserve esses arquivos e não importe novamente o
mesmo lote.

## 4. Aplicar embargos e pessoas

Ainda no servidor:

```bash
uv run apply-embargoes
uv run apply-people --dry-run
```

Revise a simulação e, sem divergências, aplique as pessoas:

```bash
uv run apply-people
```

Preserve `people.json`, `people-map.json`, `access_policies.json` e os
mapfiles para retomar operações. As permissões nos arquivos `contents`
mantêm os PDFs protegidos antes da aplicação das datas de liberação.

## 5. Finalizar

Siga a [operação pós-importação](operacao.md) para revisar os itens e atualizar
índices. Se precisar de miniaturas e texto extraído, execute após aplicar os
embargos:

```bash
docker exec dspace /dspace/bin/dspace filter-media
```

Depois da importação, restaure a montagem somente leitura conforme o passo 8
do [roteiro de produção](migracao-producao.md). As
[estatísticas históricas](estatisticas.md) são uma etapa separada e exigem
acesso à origem e ao Solr.
