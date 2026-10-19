# Executar a importação por etapas

Alternativa ao pipeline `migrate`. Use apenas para um lote novo em SAF
exclusivo; não execute sobre trabalhos já importados.
Para retomar pessoas, siga o [roteiro de produção](migracao-producao.md).

## 1. Preparar origem e destino

Conclua a [inicialização](inicializacao.md) e a
[preparação acadêmica](../../../dspace-bca/docs/guias/preparacao-academica.md).
Na produção, habilite o SAF gravável pelo passo 3 do
[roteiro de produção](migracao-producao.md).

Se precisar apenas cadastrar os campos, na raiz de `dspace-migration`:

```bash
./scripts/register_custom_fields.sh dspace
```

Esse cadastro isolado não substitui a preparação das autoridades e da coleção Person.

## 2. Extrair metadados e arquivos

Na raiz de **`dspace-migration`**:

```bash
uv run extract-metadata
uv run extract-pdfs
```

Revise `routing_report.csv`, `pdf_extraction_issues.csv` e os arquivos SAF.
Se limitar a extração, use o mesmo `--limit` nos dois comandos.

## 3. Preparar a hierarquia e importar

```bash
uv run setup-dspace
uv run generate-import-script
docker cp import_all.sh dspace:/dspace/import_all.sh
docker exec dspace bash /dspace/import_all.sh
```

O exemplo usa o container de produção `dspace`. Para o destino local,
substitua por `d10dev-dspace`. Preserve os `mapfile.txt` gerados.

## 4. Aplicar embargos e pessoas

```bash
uv run apply-embargoes
uv run apply-people --dry-run
```

Revise a simulação e aplique:

```bash
uv run apply-people
```

Não remova as permissões dos arquivos `contents`; elas mantêm os PDFs
privados antes da aplicação das datas de liberação.

## 5. Finalizar e revisar

Siga a [operação pós-importação](operacao.md) para índices e verificações.
Se precisar de miniaturas e texto extraído, após aplicar os embargos:

```bash
docker exec dspace /dspace/bin/dspace filter-media
```

As [estatísticas históricas](estatisticas.md) exigem acesso privado ao banco
e ao Solr. Na produção, encerre a montagem gravável seguindo o passo 8 do
[roteiro de produção](migracao-producao.md).
