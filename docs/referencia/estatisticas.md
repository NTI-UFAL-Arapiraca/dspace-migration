# Migração das Estatísticas de Acesso


A etapa de estatísticas do `uv run migrate` recria no core `statistics` do Solr as
visualizações históricas armazenadas em
`ud_biblioteca_publicacao.visualizacoes`. Esse dado não vira metadado Dublin
Core. Para cada visualização legada é criado um evento de consulta do item.

O relacionamento com o novo item ocorre em três passos:

1. o importador SAF grava em cada coleção um `mapfile.txt`, relacionando
   `item_<id da publicação>` ao handle criado pelo DSpace;
2. o pipeline resolve esse handle para o UUID do item no PostgreSQL do DSpace;
3. os eventos são enviados em lotes ao endpoint de atualização do core
   `statistics` e recebem um commit final.

As datas dos eventos são distribuídas uniformemente entre 1º de janeiro de
`ano_pub` e a data da migração. Quando o ano está ausente ou inválido, é usada
uma janela de cinco anos. Os identificadores dos eventos são determinísticos;
portanto, repetir a injeção para os mesmos itens sobrescreve os eventos
históricos em vez de duplicá-los.

Essa etapa exige o banco legado, o PostgreSQL do DSpace e o Solr acessíveis
pelas variáveis `DB_*`, `DSPACE_DB_*`, `SOLR_URL` e `SOLR_BATCH_SIZE` do `.env`.
Ela só pode rodar depois da importação SAF, pois depende dos `mapfile.txt`.

A opção `--skip-stats` pula a injeção. Itens com visualizações na
origem, mas sem handle/UUID correspondente no DSpace, são informados e
ignorados. O resumo final exibe o total de documentos Solr enviados e de itens
processados.


O `uv run migrate --skip-stats` adia essa operação. O procedimento está no
[guia de estatísticas](../guias/estatisticas.md). A produção mantém PostgreSQL
e Solr na rede privada; a execução precisa ocorrer em ambiente com acesso a
esses serviços, sem expor suas portas publicamente.
