# Migrar estatísticas históricas

Execute somente após concluir a importação SAF e preservar os `mapfile.txt`.
Requer acesso ao banco legado, ao PostgreSQL do DSpace e ao Solr pela rede
privada. Não publique suas portas em produção para executar esta etapa.

## 1. Conferir o ambiente

No `.env` da migração, confira `DB_*`, `DSPACE_DB_*`, `SOLR_URL`,
`SOLR_BATCH_SIZE` e `SAF_BUNDLE_DIR`. Use os mapfiles do destino correto.

## 2. Simular

Na raiz de **`dspace-migration`**:

```bash
uv run inject-stats --dry-run
```

Confira o total de eventos e resolva os avisos de handles ou UUIDs ausentes.

## 3. Aplicar

```bash
uv run inject-stats
```

Guarde o resumo junto ao registro do lote. Para retomar apenas essa etapa,
repita `inject-stats`, sem reimportar trabalhos.

O pipeline pode adiar esta operação com `--skip-stats`. A distribuição das
datas e os identificadores determinísticos são descritos na
[referência das estatísticas](../referencia/estatisticas.md).
