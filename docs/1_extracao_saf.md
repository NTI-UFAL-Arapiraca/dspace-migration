# Etapa 1: Extração e Geração do Pacote SAF

Esta etapa descreve como extrair os metadados e os arquivos PDF do banco de dados legado (PostgreSQL) e convertê-los para o formato **Simple Archive Format (SAF)** aceito pelo DSpace.

## 1. Configuração do Ambiente

1. Certifique-se de ter o `uv` (gerenciador de pacotes Python) instalado no seu ambiente local.
2. Copie o arquivo `.env.example` para `.env` e configure as credenciais de acesso ao banco de dados legado.

```bash
cp .env.example .env
```

3. Suba o container do PostgreSQL legado (se estiver rodando localmente a partir de `biblioteca-compose.yml`):

```bash
docker compose -f biblioteca-compose.yml up -d
```
*(Ou execute o script `./scripts/init-db.sh` caso vá restaurar os dumps).*

## 2. Processamento dos Metadados

O comando `extract-metadata` é responsável por:
- Conectar ao banco de dados PostgreSQL.
- Executar a consulta presente em `sql/extract_metadata.sql`.
- Limpar tags HTML dos textos.
- Padronizar datas para o formato ISO.
- Criar a estrutura de diretórios do pacote SAF (`saf_bundle/item_[id]/`).
- Gerar o arquivo `dublin_core.xml` para cada item com base nos metadados extraídos.

Execute o comando:

```bash
uv run extract-metadata
```

*Os itens com restrição/embargo de acesso serão exportados para o arquivo `embargoed_items.csv` para referência.*

## 3. Extração dos Arquivos PDF Binários

O comando `extract-pdfs` extrai os anexos salvos em formato binário (`bytea`) do banco e os grava como arquivos PDF dentro da pasta de cada item no pacote SAF.

Execute o comando:

```bash
uv run extract-pdfs
```

*O script suporta paginação para não estourar a memória (configurável via `BATCH_SIZE` no `.env`) e gerencia adequadamente publicações com múltiplos anexos, criando/atualizando o arquivo `contents` do SAF automaticamente.*

## 4. Executando Ambos em Sequência

Caso deseje rodar a extração completa de metadados e PDFs em um único comando, utilize:

```bash
uv run migrate
```

## Resultado

Ao final desta etapa, você terá um diretório `saf_bundle/` (ou o nome configurado no `.env`) contendo subpastas para cada publicação (ex: `item_930/`), e cada subpasta conterá os arquivos `dublin_core.xml`, `contents` e os respectivos arquivos `.pdf`.
