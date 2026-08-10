# Migração de Repositório Institucional: Odoo (PostgreSQL) ➔ DSpace (SAF)

Este projeto automatiza o processo de extração, limpeza, transformação de metadados e empacotamento de acervo acadêmico (Trabalhos de Conclusão de Curso e Artigos Científicos) legado de um banco relacional PostgreSQL (ERP Odoo) para o formato padrão **SAF (Simple Archive Format)** aceito nativamente pelo repositório **DSpace**.

---

## 🎯 Objetivo e Contexto

A base de origem é composta por cerca de 40.000 registros mantidos pela Biblioteca Universitária. A migração foi dividida em etapas automatizadas:
1. **Higienização de Metadados e Estruturação SAF**: Limpeza de HTML, padronização de datas, triagem de observações vs citações e geração dos arquivos de metadados XML (`dublin_core.xml`).
2. **Extração Otimizada de PDFs Binários**: Busca e gravação física dos arquivos PDFs (armazenados como `bytea` no PostgreSQL) nas respetivas pastas SAF de cada item, com suporte completo a múltiplos anexos.
3. **Roteamento por Curso/Polo**: Cada publicação é encaminhada automaticamente para a coleção correta no DSpace, com base no seu curso de origem (`map.json`), criando a hierarquia de comunidades/coleções dinamicamente via API REST.
4. **Controle de acesso**: PDFs embargados ou restritos entram privados; embargos com data futura recebem uma política de liberação automática após a importação.
5. **Estatísticas históricas**: As contagens legadas de visualizações podem ser recriadas no core de estatísticas do Solr.

---

## 📦 Estrutura do Pacote e Comandos CLI (`uv`)

O projeto é empacotado via **`uv`** com código estruturado em `src/dspace_migration/`.

### Comandos CLI Disponíveis:

| Comando | Descrição |
| --- | --- |
| `uv run extract-metadata` | Conecta ao PostgreSQL legado, extrai e higieniza metadados, e gera a estrutura SAF hierárquica (`saf_bundle/<polo>/<coleção>/item_[id]/dublin_core.xml`). |
| `uv run extract-pdfs` | Busca os PDFs binários (`bytea`) em lotes no PostgreSQL e salva os arquivos nas pastas correspondentes do SAF (busca recursiva). |
| `uv run setup-dspace` | Cria a hierarquia de comunidades e coleções no DSpace via API REST (com base em `communities.json`), salvando os UUIDs em `collection_uuids.json`. |
| `uv run generate-import-script` | Gera o script `import_all.sh` com um comando de importação por coleção, pronto para executar dentro do container Docker. |
| `uv run apply-embargoes` | Aplica no DSpace as datas de liberação dos PDFs embargados, após a importação SAF. |
| `uv run inject-stats` | Injeta no Solr as contagens históricas de visualizações dos itens importados. |
| `uv run migrate` | Executa o pipeline completo: extração, hierarquia, importação SAF, embargos e estatísticas. |

---

## 📁 Estrutura de Arquivos

- **`src/dspace_migration/`**: Código-fonte do pacote Python.
  - `metadata.py` — Extração e higienização de metadados, geração SAF hierárquica.
  - `pdfs.py` — Extração de PDFs binários e conversão PDF/A.
  - `organization.py` — Gestão da hierarquia DSpace (API REST) e roteamento de cursos.
  - `cli.py` — Entry points dos comandos CLI.
- **`sql/extract_metadata.sql`**: Consulta SQL para extração dos metadados brutos do PostgreSQL legado.
- **`dspace-organization/`**: Configuração da estrutura organizacional do DSpace.
  - `communities.json` — Árvore de comunidades e coleções a criar.
  - `map.json` — Mapeamento de nomes antigos de curso para coleções destino.
- **[`scripts/register_custom_fields.sh`](scripts/register_custom_fields.sh)**: Script para cadastro dos campos customizados no banco do DSpace.
- **[`scripts/init-db.sh`](scripts/init-db.sh)**: Script para subir o banco legado e carregar os dumps.
- **[`biblioteca-compose.yml`](biblioteca-compose.yml)**: Docker Compose do banco PostgreSQL legado.
- **[`dspace-docker/`](dspace-docker/)**: Configuração Docker da instância do DSpace.
- **[`docs/`](docs/)**: Guia detalhado passo a passo da migração.

---

## 🚀 Como Executar o Pipeline

Consulte o guia completo passo a passo na pasta [`docs/`](docs/):

1. **[Etapa 1: Extração e Geração do Pacote SAF](docs/1_extracao_saf.md)**
2. **[Etapa 2: Configuração e Preparação do DSpace](docs/2_configuracao_dspace.md)**
3. **[Etapa 3: Importação Final no DSpace](docs/3_importacao_dspace.md)**

## Testes automatizados

Execute a suíte completa a partir da raiz do projeto:

```bash
uv run python -m unittest discover -s tests -v
```

---

## 🔗 Links Úteis e Referências

- [Documentação Oficial DSpace](https://dspace.org/)
- [DSpace Simple Archive Format (SAF) Spec](https://wiki.lyrasis.org/pages/viewpage.action?pageId=104566653)
- [DSpace Docker Setup](https://wiki.lyrasis.org/display/DSPACE/Try+out+DSpace+9#TryoutDSpace9-InstallviaDocker)
- [DSpace REST Client (Python)](https://pypi.org/project/dspace-rest-client/)
