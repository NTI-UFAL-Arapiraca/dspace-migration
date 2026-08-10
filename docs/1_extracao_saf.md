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
- **Rotear cada publicação** para a coleção correta com base no mapeamento de cursos (`dspace-organization/map.json`).
- Criar a estrutura de diretórios do pacote SAF **hierárquica por polo e coleção**: `saf_bundle/<polo>/<coleção>/item_[id]/`.
- Gerar o arquivo `dublin_core.xml` para cada item com base nos metadados extraídos.
- Preencher `dc.language.iso` com `pt_BR` em todos os itens.
- Identificar embargos ativos pela coluna `data_limite_embargo` e restrições sem prazo.
- Gerar `access_policies.json` na raiz do bundle para conservar as datas de liberação.

Execute o comando:

```bash
uv run extract-metadata
```

*Os itens com restrição/embargo de acesso serão exportados para o arquivo `embargoed_items.csv` para referência. Uma data de embargo igual ou anterior ao dia da extração é considerada vencida.*
*O relatório de roteamento será exportado para `routing_report.csv`, indicando para qual coleção cada publicação foi direcionada.*

> [!NOTE]
> Publicações cujo curso de origem não tenha correspondência no `map.json` serão colocadas em `saf_bundle/_unmapped/` e registradas no relatório de roteamento com status `UNMAPPED`.

## 3. Extração dos Arquivos PDF Binários

O comando `extract-pdfs` extrai os anexos salvos em formato binário (`bytea`) do banco e os grava como arquivos PDF dentro da pasta de cada item no pacote SAF.

Execute o comando:

```bash
uv run extract-pdfs
```

*O script suporta paginação para não estourar a memória (configurável via `BATCH_SIZE` no `.env`) e gerencia adequadamente publicações com múltiplos anexos, criando/atualizando o arquivo `contents` do SAF automaticamente.*

Para itens embargados ou restritos, cada linha de `contents` recebe uma permissão de leitura exclusiva do grupo `Administrator`. Assim, o PDF já entra privado no DSpace, antes da configuração da data de liberação.

*Os diretórios de item são buscados recursivamente dentro do `saf_bundle/`, compatível com a estrutura hierárquica.*

## 4. Executando somente as duas extrações em sequência

Para gerar somente o pacote SAF, sem acessar ou alterar o DSpace, execute:

```bash
uv run extract-metadata
uv run extract-pdfs
```

O comando `uv run migrate` vai além desta etapa: ele também configura a hierarquia via API, gera e executa a importação no container DSpace, aplica os embargos e injeta as estatísticas. Use `--skip-docker` apenas quando os itens desta execução já tiverem sido importados e os `mapfile.txt` correspondentes existirem; use `--skip-stats` para não alterar o Solr.

## Resultado

Ao final desta etapa, você terá um diretório `saf_bundle/` (ou o nome configurado no `.env`) com a seguinte estrutura hierárquica:

```
saf_bundle/
├── access_policies.json
├── Arapiraca/
│   ├── Administração/
│   │   ├── item_123/
│   │   │   ├── dublin_core.xml
│   │   │   ├── contents
│   │   │   └── tcc_fulano.pdf
│   │   └── item_456/
│   │       └── ...
│   ├── Ciência da Computação/
│   │   └── ...
│   └── Outros/
│       └── Documentos (BSCA)/
│           └── ...
├── Penedo/
│   └── ...
├── Viçosa/
│   └── ...
├── Palmeira dos Índios/
│   └── ...
└── _unmapped/
    └── item_999/
        └── ...
```
