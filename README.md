# Migração do repositório: Odoo → DSpace

Este projeto extrai metadados e arquivos do PostgreSQL legado, gera pacotes
SAF e importa trabalhos e pessoas bibliográficas no DSpace **10.1**.
O projeto irmão `dspace-bca` mantém a implantação e a interface do destino.

## Guias de execução

- [Inicializar o ambiente da migração](docs/guias/inicializacao.md).
- [Executar um piloto local](docs/guias/migracao-local.md).
- [Executar ou retomar a migração em produção](docs/guias/migracao-producao.md).
- [Executar a importação por etapas](docs/guias/importacao-por-etapas.md).
- [Migrar estatísticas históricas](docs/guias/estatisticas.md).
- [Operar, verificar e testar](docs/guias/operacao.md).

## Funcionamento do pipeline


A base de origem é composta por cerca de 40.000 registros mantidos pela Biblioteca Universitária. A migração foi dividida em etapas automatizadas:
1. **Higienização de Metadados e Estruturação SAF**: Limpeza de HTML, padronização de datas, triagem de observações vs citações e geração dos arquivos de metadados XML (`dublin_core.xml`).
2. **Extração Otimizada de PDFs Binários**: Busca e gravação física dos arquivos PDFs (armazenados como `bytea` no PostgreSQL) nas respetivas pastas SAF de cada item, com suporte completo a múltiplos anexos.
3. **Roteamento por Curso/Polo**: Cada publicação é encaminhada automaticamente para a coleção correta no DSpace, com base no seu curso de origem (`map.json`), criando a hierarquia de comunidades/coleções dinamicamente via API REST.
4. **Controle de acesso**: PDFs embargados ou restritos entram privados; embargos com data futura recebem uma política de liberação automática após a importação.
5. **Pessoas e vínculos**: Criação de entidades Person por ID legado e associação de autoria, orientação, coorientação e banca, sem contas de acesso.
6. **Estatísticas históricas**: As contagens legadas de visualizações podem ser recriadas no core de estatísticas do Solr.


O pipeline completo inclui OAI-PMH e sitemaps ao final. A preparação do
servidor e do administrador é externa ao pipeline. Uma importação SAF
adiciona itens; a retomada de pessoas e vínculos usa `apply-people`.
Os cadastros Person não criam contas EPerson.

## Referência

- [Campos migrados e regras de transformação](docs/referencia/campos-migrados.md).
- [Formato SAF e extração dos anexos](docs/referencia/extracao-saf.md).
- [Registro de metadados customizados](docs/referencia/metadados-customizados.md).
- [Pessoas, identidades, checkpoints e conflitos](docs/referencia/pessoas-e-vinculos.md).
- [Estatísticas históricas](docs/referencia/estatisticas.md).
- [Arquitetura do DSpace](../dspace-bca/docs/referencia/implantacao.md).
- [Índice da documentação](docs/README.md).

## Pacote e comandos disponíveis


O projeto é empacotado via **`uv`** com código estruturado em `src/dspace_migration/`.

| Comando | Descrição |
| --- | --- |
| `uv run extract-metadata` | Conecta ao PostgreSQL legado, extrai e higieniza metadados, e gera a estrutura SAF hierárquica (`saf_bundle/<polo>/<coleção>/item_[id]/dublin_core.xml`). |
| `uv run extract-pdfs` | Busca os PDFs binários (`bytea`) em lotes no PostgreSQL e salva os arquivos nas pastas correspondentes do SAF (busca recursiva). |
| `uv run setup-dspace` | Cria a hierarquia de comunidades e coleções no DSpace via API REST (com base em `communities.json`), salvando os UUIDs em `collection_uuids.json`. |
| `uv run generate-import-script` | Gera o script `import_all.sh` com um comando de importação por coleção, pronto para executar dentro do container Docker. |
| `uv run apply-embargoes` | Aplica no DSpace as datas de liberação dos PDFs embargados, após a importação SAF. |
| `uv run apply-people` | Cria/reutiliza Person e vincula os trabalhos; `--dry-run` apenas inspeciona. Também converte curso/campus dos lotes antigos. |
| `uv run inject-stats` | Injeta no Solr as contagens históricas de visualizações dos itens importados. |
| `uv run rebuild-oai` | Limpa e reconstrói o índice OAI-PMH a partir dos itens do DSpace. |
| `uv run generate-sitemaps` | Gera os índices XML e HTML anunciados em `robots.txt`. |
| `uv run migrate` | Executa o pipeline completo: extração, hierarquia, importação SAF, embargos, pessoas, estatísticas, OAI e sitemaps. |


## Estrutura de arquivos

| Caminho | Responsabilidade |
| --- | --- |
| `src/dspace_migration/metadata.py` | Transformações e geração de XML SAF. |
| `src/dspace_migration/pdfs.py` | Extração de anexos e conversão PDF/A. |
| `src/dspace_migration/organization.py` | Hierarquia, roteamento e script de importação. |
| `src/dspace_migration/people.py` | Identidades, criação de Person e vínculos retomáveis. |
| `src/dspace_migration/embargoes.py` | Políticas de liberação dos bitstreams. |
| `src/dspace_migration/statistics.py` | Eventos de visualização legados. |
| `src/dspace_migration/cli.py` | Comandos CLI e sequência do pipeline. |
| `sql/extract_metadata.sql` | Consulta dos metadados de origem. |
| `dspace-organization/` | Hierarquia de comunidades e mapeamento de cursos. |
| `config/registries/` | Registro dos campos adicionais. |
| `scripts/init-db.sh` e `biblioteca-compose.yml` | Banco legado local e restauração dos dumps. |
| `scripts/register_custom_fields.sh` | Cadastro isolado de campos pelo CLI oficial. |
| `docs/guias/` | Procedimentos de execução. |
| `docs/referencia/` | Descrição do funcionamento e dos dados. |

## Referências externas

- [DSpace](https://dspace.org/).
- [Simple Archive Format](https://wiki.lyrasis.org/pages/viewpage.action?pageId=104566653).
- [Cliente REST Python](https://pypi.org/project/dspace-rest-client/).
