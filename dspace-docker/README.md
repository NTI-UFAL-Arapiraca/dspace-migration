# DSpace Docker da Migração

Este diretório contém somente os arquivos usados para executar a instância do
DSpace necessária à migração:

| Arquivo | Uso |
| --- | --- |
| `docker-compose-rest.yml` | Backend DSpace, PostgreSQL, Solr, volumes persistentes e montagem do pacote SAF. |
| `docker-compose-dist.yml` | Build e execução da interface DSpace Angular customizada. |
| `Dockerfile.angular` | Compila o tema local sobre o código-fonte da versão oficial. |
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

O tema `custom` é ativado em `frontend/config/config.prod.yml`. Mudanças em
SCSS, assets ou componentes exigem `build --no-cache dspace-angular` quando for
necessário invalidar todo o cache. Mudanças apenas nesse YAML exigem somente:

```bash
docker compose -p d10 -f docker-compose-dist.yml -f docker-compose-rest.yml \
  up -d --force-recreate dspace-angular
```

As variáveis `DSPACE_ANGULAR_TAG` e `DSPACE_ANGULAR_IMAGE` podem ser definidas
no `.env`. O tag precisa existir tanto na forma normal quanto com o sufixo
`-dist` no repositório oficial de imagens.

O mesmo nome de projeto (`-p d10`) deve ser usado nos comandos de `cli.yml`,
pois esse arquivo conecta seus containers à rede e ao volume criados acima.

Consulte [`../docs/2_configuracao_dspace.md`](../docs/2_configuracao_dspace.md)
para a preparação completa e
[`../docs/3_importacao_dspace.md`](../docs/3_importacao_dspace.md) para a
importação.
