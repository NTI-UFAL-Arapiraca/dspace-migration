# DSpace Docker da Migração

Este diretório contém somente os arquivos usados para executar a instância do
DSpace necessária à migração:

| Arquivo | Uso |
| --- | --- |
| `docker-compose-rest.yml` | Backend DSpace, PostgreSQL, Solr, volumes persistentes e montagem do pacote SAF. |
| `docker-compose-dist.yml` | Interface web DSpace Angular. |
| `cli.yml` | Comandos administrativos, como criação do administrador e `filter-media`. |

## Inicialização

```bash
docker compose -p d10 -f docker-compose-dist.yml -f docker-compose-rest.yml pull
docker compose -p d10 -f docker-compose-dist.yml -f docker-compose-rest.yml up -d
```

O mesmo nome de projeto (`-p d10`) deve ser usado nos comandos de `cli.yml`,
pois esse arquivo conecta seus containers à rede e ao volume criados acima.

Consulte [`../docs/2_configuracao_dspace.md`](../docs/2_configuracao_dspace.md)
para a preparação completa e
[`../docs/3_importacao_dspace.md`](../docs/3_importacao_dspace.md) para a
importação.
