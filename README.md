# Migração de Repositório Institucional: Odoo (PostgreSQL) ➔ DSpace (SAF)

Este projeto automatiza o processo de extração, limpeza, transformação de metadados e empacotamento de acervo acadêmico (Trabalhos de Conclusão de Curso e Artigos Científicos) legado de um banco relacional PostgreSQL (ERP Odoo) para o formato padrão **SAF (Simple Archive Format)** aceito nativamente pelo repositório **DSpace**.

---

## 🎯 Objetivo e Contexto

A base de origem é composta por cerca de 40.000 registros mantidos pela Biblioteca Universitária. A migração foi dividida em duas grandes etapas automatizadas:
1. **Higienização de Metadados e Estruturação SAF**: Limpeza de HTML, padronização de datas, triagem de observações vs citações e geração dos arquivos de metadados XML (`dublin_core.xml`).
2. **Extração Otimizada de PDFs Binários**: Busca e gravação física dos arquivos PDFs (armazenados como `bytea` no PostgreSQL) nas respetivas pastas SAF de cada item, com suporte completo a múltiplos anexos.

---

## 📁 Estrutura de Arquivos e Suas Funções

### Arquivos de Código e Configuração (Versionados no Git)

- **[`register_custom_fields.sh`](file:///home/danilo/dev/dspace-migration/register_custom_fields.sh)**
  - Script Bash automatizado para cadastro idempotente de campos de metadados customizados/não padrão no `metadatafieldregistry` do banco de dados PostgreSQL do DSpace (`dspacedb`).
  - Garante que a CLI do DSpace não falhe com erros de `bad_dublin_core`.

- **[`process_migration_data.py`](file:///home/danilo/dev/dspace-migration/process_migration_data.py)**
  - Script em Python (utilizando **Pandas**) responsável pelo processamento de metadados.
  - **Funções principais**:
    - Remove tags HTML indesejadas de textos ricos via Expressões Regulares (preservando tags de formatação científica como `<i>` e `</i>`).
    - Limpa lixo de preenchimento ("Abstract") da coluna `dc.title.alternative`.
    - Normaliza datas para a norma ISO 8601 (`AAAA-01-01`).
    - Executa a triagem heurística entre **Notas de Acervo Físico** (`dc.description.note`) e **Citações/Referências Bibliográficas** (`dc.identifier.citation`).
    - Filtra e exporta a lista de itens com restrição/embargo de acesso.
    - Constrói o esqueleto das pastas em `saf_bundle/item_[id]/` contendo o `dublin_core.xml` e o ponteiro `contents`. Preserva delimitadores de valores múltiplos (`||`).

- **[`extract_pdfs.py`](file:///home/danilo/dev/dspace-migration/extract_pdfs.py)**
  - Script em Python utilizando `psycopg2` para extração dos arquivos binários (`bytea`) da tabela `ud_biblioteca_anexo`.
  - **Destaque de Performance & Memória**: Utiliza **paginação por lote de IDs (chunking)**. Busca apenas os IDs inteiros em uma primeira consulta leve e realiza queries pontuais por lote (parâmetro `BATCH_SIZE`), evitando estourar a memória RAM do container Docker do PostgreSQL e da máquina host.
  - **Múltiplos Anexos**: Suporta itens com mais de um PDF/anexo, sanitizando os nomes originais e reescrevendo o arquivo `contents` de cada item.

- **[`compose.yml`](file:///home/danilo/dev/dspace-migration/compose.yml)**
  - Arquivo do Docker Compose para subir o container PostgreSQL local contendo a base legada `biblioteca`.
  - Mapeia credenciais e portas dinamicamente através do arquivo de ambiente `.env`.

- **[`.env.example`](file:///home/danilo/dev/dspace-migration/.env.example)**
  - Modelo de variáveis de ambiente para conexão ao banco de dados (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) e configurações do lote (`BATCH_SIZE`, `SAF_BUNDLE_DIR`).

- **[`pyproject.toml`](file:///home/danilo/dev/dspace-migration/pyproject.toml) e [`uv.lock`](file:///home/danilo/dev/dspace-migration/uv.lock)**
  - Configurações do ambiente de desenvolvimento e gerenciamento de dependências (`pandas`, `psycopg2-binary`, `python-dotenv`) gerenciados via **`uv`**.

- **[`mise.toml`](file:///home/danilo/dev/dspace-migration/mise.toml)**
  - Configuração do gerenciador de runtime local (Mise).

- **[`.gitignore`](file:///home/danilo/dev/dspace-migration/.gitignore)**
  - Garante que dados legados brutos, CSVs intermediários e o pacote gerado com milhares de PDFs permaneçam exclusivamente na máquina local e não sejam enviados ao repositório Git.

---

### Arquivos de Dados e Saídas Geradas (Mantidos no Dispositivo Local)

- **`data.csv`**
  - Dump brutos de metadados extraídos do PostgreSQL de origem.
- **`processed_data.csv`**
  - CSV limpo e totalmente padronizado com as tags Qualified Dublin Core prontas.
- **`embargoed_items.csv`**
  - Relatório contendo os registros identificados com restrição de acesso e datas limite de embargo para aplicação de políticas de bloqueio no DSpace.
- **`saf_bundle/`**
  - Diretório raiz no formato **Simple Archive Format (SAF)** do DSpace.
  - **Estrutura interna**:
    ```text
    saf_bundle/
    ├── item_930/
    │   ├── dublin_core.xml   # Metadados no formato XML do DSpace
    │   ├── contents          # Arquivo de mapeamento contendo os nomes dos PDFs
    │   └── documento.pdf     # Arquivo PDF binário extraído do banco
    ├── item_5312/
    │   ├── dublin_core.xml
    │   ├── contents
    │   └── documento.pdf
    └── ...
    ```

---

## 🚀 Como Executar o Pipeline

### 1. Configurar o Ambiente de Desenvolvimento

Certifique-se de ter o `uv` instalado no ambiente e crie seu arquivo `.env`:

```bash
cp .env.example .env
# Edite o .env se necessário para ajustar senhas ou portas de banco de dados
```

### 2. Subir o Banco PostgreSQL Legado (Se Aplicável)

```bash
docker compose up -d
```

### 3. Registrar Campos Customizados no DSpace

Antes de importar o pacote SAF no DSpace, registre os campos de metadados adicionais no banco do DSpace (`dspacedb`):

```bash
chmod +x register_custom_fields.sh
./register_custom_fields.sh dspacedb
```

### 4. Fazer a Limpeza de Metadados e Gerar a Estrutura SAF

```bash
uv run python process_migration_data.py
```
*Este comando processará o `data.csv`, gerando o `processed_data.csv`, o `embargoed_items.csv` e criando a estrutura de pastas em `saf_bundle/`.*

### 5. Extrair os Arquivos PDF Binários

```bash
uv run python extract_pdfs.py
```
*Este comando consultará o PostgreSQL em lotes pequenos e gravará cada anexo PDF dentro da pasta correspondente em `saf_bundle/`.*

---

## 📥 Importação Final no DSpace

Com o pacote `saf_bundle/` completo (contendo o `dublin_core.xml`, `contents` e os arquivos PDFs por item), execute a CLI nativa de importação em lote do seu servidor DSpace:

```bash
/dspace/bin/dspace import \
  --add \
  --eperson=admin@sua-instituicao.edu.br \
  --collection=HANDLE_DA_COLECAO \
  --source=/caminho/para/saf_bundle \
  --mapfile=mapfile_migration
```

---

## 🔗 Links Úteis e Referências

- [Documentação Oficial DSpace](https://dspace.org/)
- [DSpace Simple Archive Format (SAF) Spec](https://wiki.lyrasis.org/pages/viewpage.action?pageId=104566653)
- [DSpace Docker Setup](https://wiki.lyrasis.org/display/DSPACE/Try+out+DSpace+9#TryoutDSpace9-InstallviaDocker)
