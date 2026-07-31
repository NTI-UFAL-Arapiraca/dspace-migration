# Migração de Repositório Institucional: Odoo (PostgreSQL) ➔ DSpace (SAF)

Este projeto automatiza o processo de extração, limpeza, transformação de metadados e empacotamento de acervo acadêmico (Trabalhos de Conclusão de Curso e Artigos Científicos) legado de um banco relacional PostgreSQL (ERP Odoo) para o formato padrão **SAF (Simple Archive Format)** aceito nativamente pelo repositório **DSpace**.

---

## 🎯 Objetivo e Contexto

A base de origem é composta por cerca de 40.000 registros mantidos pela Biblioteca Universitária. A migração foi dividida em duas grandes etapas automatizadas:
1. **Higienização de Metadados e Estruturação SAF**: Limpeza de HTML, padronização de datas, triagem de observações vs citações e geração dos arquivos de metadados XML (`dublin_core.xml`).
2. **Extração Otimizada de PDFs Binários**: Busca e gravação física dos arquivos PDFs (armazenados como `bytea` no PostgreSQL) nas respetivas pastas SAF de cada item, com suporte completo a múltiplos anexos.

---

## 📁 Estrutura de Arquivos e Suas Funções

### Arquivos de Código, Configuração e Scripts (`scripts/`)

- **[`scripts/register_custom_fields.sh`](scripts/register_custom_fields.sh)**
  - Script Bash automatizado para cadastro idempotente de campos de metadados customizados/não padrão (`dc.description.degree`, `dc.description.note`, `dc.contributor.coadvisor`, etc.) no `metadatafieldregistry` do banco de dados PostgreSQL do DSpace (`dspacedb`).
  - Garante que a CLI do DSpace não falhe com erros de `bad_dublin_core`.

- **[`scripts/init-db.sh`](scripts/init-db.sh)**
  - Script Bash para subir o container PostgreSQL da base legada e restaurar os dumps em `/dumps`.

- **[`process_migration_data.py`](process_migration_data.py)**
  - Script em Python (utilizando **Pandas**) responsável pelo processamento de metadados diretamente a partir do PostgreSQL (usando `sql/extract_metadata.sql`).
  - **Funções principais**:
    - Remove tags HTML indesejadas de textos ricos via Expressões Regulares (preservando tags de formatação científica como `<i>` e `</i>`).
    - Limpa lixo de preenchimento ("Abstract") da coluna `dc.title.alternative`.
    - Normaliza datas para a norma ISO 8601 (`AAAA-01-01`).
    - Executa a triagem heurística entre **Notas de Acervo Físico** (`dc.description.note`) e **Citações/Referências Bibliográficas** (`dc.identifier.citation`).
    - Filtra e exporta a lista de itens com restrição/embargo de acesso (`embargoed_items.csv`).
    - Constrói o esqueleto das pastas em `saf_bundle/item_[id]/` contendo o `dublin_core.xml`. Preserva delimitadores de valores múltiplos (`||`).

- **[`extract_pdfs.py`](extract_pdfs.py)**
  - Script em Python utilizando `psycopg2` para extração dos arquivos binários (`bytea`) da tabela `ud_biblioteca_anexo`.
  - **Destaque de Performance & Memória**: Utiliza **paginação por lote de IDs (chunking)**. Busca apenas os IDs inteiros em uma primeira consulta leve e realiza queries pontuais por lote (parâmetro `BATCH_SIZE`), evitando estourar a memória RAM do container Docker do PostgreSQL e da máquina host.
  - **Múltiplos Anexos**: Suporta itens com mais de um PDF/anexo, sanitizando os nomes originais e reescrevendo o arquivo `contents` de cada item.

- **[`biblioteca-compose.yml`](biblioteca-compose.yml)**
  - Arquivo do Docker Compose para subir o container PostgreSQL local contendo a base legada `biblioteca`.

- **[`dspace-docker/`](dspace-docker/)**
  - Diretório contendo a configuração Docker do repositório DSpace para testes locais e execução dos containers (`dspace`, `dspacedb`, `dspace-ui`).

- **[`docs/`](docs/)**
  - Documentação detalhada e passo a passo da migração dividida em etapas numeradas (`0_campos_a_migrar.md`, `1_extracao_saf.md`, `2_configuracao_dspace.md`, `3_importacao_dspace.md`).

---

## 🚀 Como Executar o Pipeline

Consulte o guia completo passo a passo na pasta [`docs/`](docs/):

1. **[Etapa 1: Extração e Geração do Pacote SAF](docs/1_extracao_saf.md)**
2. **[Etapa 2: Configuração e Preparação do DSpace](docs/2_configuracao_dspace.md)**
3. **[Etapa 3: Importação Final no DSpace](docs/3_importacao_dspace.md)**

---

## 🔗 Links Úteis e Referências

- [Documentação Oficial DSpace](https://dspace.org/)
- [DSpace Simple Archive Format (SAF) Spec](https://wiki.lyrasis.org/pages/viewpage.action?pageId=104566653)
- [DSpace Docker Setup](https://wiki.lyrasis.org/display/DSPACE/Try+out+DSpace+9#TryoutDSpace9-InstallviaDocker)
