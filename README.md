# Migração de Repositório Institucional: Odoo (PostgreSQL) ➔ DSpace (SAF)

Este projeto automatiza o processo de extração, limpeza, transformação de metadados e empacotamento de acervo acadêmico (Trabalhos de Conclusão de Curso e Artigos Científicos) legado de um banco relacional PostgreSQL (ERP Odoo) para o formato padrão **SAF (Simple Archive Format)** aceito nativamente pelo repositório **DSpace**.

---

## 🎯 Objetivo e Contexto

A base de origem é composta por cerca de 40.000 registros mantidos pela Biblioteca Universitária. A migração foi dividida em duas grandes etapas automatizadas:
1. **Higienização de Metadados e Estruturação SAF**: Limpeza de HTML, padronização de datas, triagem de observações vs citações e geração dos arquivos de metadados XML (`dublin_core.xml`).
2. **Extração Otimizada de PDFs Binários**: Busca e gravação física dos arquivos PDFs (armazenados como `bytea` no PostgreSQL) nas respetivas pastas SAF de cada item, com suporte completo a múltiplos anexos.

---

## 📦 Estrutura do Pacote e Comandos CLI (`uv`)

O projeto é empacotado via **`uv`** com código estruturado em `src/dspace_migration/`.

### Comandos CLI Disponíveis:

| Comando | Descrição |
| --- | --- |
| `uv run extract-metadata` | Conecta ao PostgreSQL legado, executa `sql/extract_metadata.sql`, higieniza os metadados e gera a estrutura SAF (`saf_bundle/item_[id]/dublin_core.xml`). |
| `uv run extract-pdfs` | Busca os PDFs binários (`bytea`) em lotes no PostgreSQL e salva os arquivos nas pastas correspondentes do SAF com o arquivo `contents`. |
| `uv run migrate` | Executa o pipeline completo (metadados + PDFs) em sequência. |

---

## 📁 Estrutura de Arquivos

- **`src/dspace_migration/`**: Código-fonte do pacote Python (`metadata.py`, `pdfs.py`, `cli.py`).
- **`sql/extract_metadata.sql`**: Consulta SQL para extração dos metadados brutos do PostgreSQL legado.
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

---

## 🔗 Links Úteis e Referências

- [Documentação Oficial DSpace](https://dspace.org/)
- [DSpace Simple Archive Format (SAF) Spec](https://wiki.lyrasis.org/pages/viewpage.action?pageId=104566653)
- [DSpace Docker Setup](https://wiki.lyrasis.org/display/DSPACE/Try+out+DSpace+9#TryoutDSpace9-InstallviaDocker)
