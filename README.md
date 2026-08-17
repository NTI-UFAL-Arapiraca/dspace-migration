# Migração de Repositório Institucional: Odoo (PostgreSQL) ➔ DSpace (SAF)

Este projeto automatiza o processo de extração, limpeza, transformação de metadados e empacotamento de acervo acadêmico (Trabalhos de Conclusão de Curso e Artigos Científicos) legado de um banco relacional PostgreSQL (ERP Odoo) para o formato padrão **SAF (Simple Archive Format)** aceito nativamente pelo repositório **DSpace**.

---

## Objetivo e Contexto

A base de origem é composta por cerca de 40.000 registros mantidos pela Biblioteca Universitária. A migração foi dividida em etapas automatizadas:
1. **Higienização de Metadados e Estruturação SAF**: Limpeza de HTML, padronização de datas, triagem de observações vs citações e geração dos arquivos de metadados XML (`dublin_core.xml`).
2. **Extração Otimizada de PDFs Binários**: Busca e gravação física dos arquivos PDFs (armazenados como `bytea` no PostgreSQL) nas respetivas pastas SAF de cada item, com suporte completo a múltiplos anexos.
3. **Roteamento por Curso/Polo**: Cada publicação é encaminhada automaticamente para a coleção correta no DSpace, com base no seu curso de origem (`map.json`), criando a hierarquia de comunidades/coleções dinamicamente via API REST.
4. **Controle de acesso**: PDFs embargados ou restritos entram privados; embargos com data futura recebem uma política de liberação automática após a importação.
5. **Estatísticas históricas**: As contagens legadas de visualizações podem ser recriadas no core de estatísticas do Solr.

---

## Quickstart

O `uv run migrate` executa o pipeline de dados, mas **não** instala nem inicia o
Docker, não restaura o banco de origem, não cria o administrador do DSpace e
não cadastra os campos customizados. Em uma instalação limpa, execute os passos
abaixo a partir da raiz do repositório.

### 1. Preparar o ambiente

São necessários Docker com o plugin Compose, `uv` e as portas `4000`, `5432`,
`5440`, `8080` e `8983` livres.

```bash
cp .env.example .env
uv sync
mkdir -p saf_bundle
```

Revise o `.env`, principalmente as credenciais `DB_*` do PostgreSQL de origem
e `DSPACE_API_USER`/`DSPACE_API_PASSWORD`. O diretório `SAF_BUNDLE_DIR` deve ser
o mesmo montado no container DSpace. Com o valor padrão `saf_bundle`, isso já é
feito automaticamente. Para usar outro disco, configure ambos com o mesmo
caminho absoluto:

```dotenv
SAF_BUNDLE_DIR=/caminho/absoluto/saf_bundle
DSPACE_SAF_HOST_DIR=/caminho/absoluto/saf_bundle
```

Backend, Solr, CLI e frontend estão fixados em `dspace-10.0`. Mantenha
`DSPACE_VER` e `DSPACE_ANGULAR_TAG` com o mesmo valor; não use `latest` nem
`latest-test`, pois esses aliases podem apontar para o DSpace 11.

### 2. Disponibilizar o banco de origem

Se o PostgreSQL legado já estiver acessível pelas variáveis `DB_*`, pule este
passo. Para usar o banco local definido em `biblioteca-compose.yml`, coloque os
dumps esperados em `dumps/` e restaure-os com:

```bash
./scripts/init-db.sh
```

O script inicia o PostgreSQL na porta `5440` e restaura os dumps cujos nomes
estão definidos em `scripts/init-db.sh`. Ajuste esses nomes se os arquivos forem
diferentes. Se o volume já estiver restaurado, basta iniciá-lo:

```bash
docker compose -p biblioteca-migracao -f biblioteca-compose.yml up -d
```

### 3. Iniciar o DSpace

```bash
cd dspace-docker
docker compose --env-file ../.env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml \
  up -d --build
```

Esse comando inicia o frontend, a API REST, o PostgreSQL e o Solr. Aguarde a
API responder antes de continuar:

```bash
curl --fail http://localhost:8080/server/api
```

Em seguida, ainda em `dspace-docker/`, crie o administrador com as mesmas
credenciais configuradas em `DSPACE_API_USER` e `DSPACE_API_PASSWORD`. O
exemplo abaixo corresponde aos valores padrão do `.env.example`:

```bash
docker compose --env-file ../.env -p d10 -f cli.yml run --rm \
  dspace-cli create-administrator \
  -e test@test.edu -f admin -l user -p admin -c pt_BR
```

### 4. Cadastrar os campos customizados

Volte à raiz do repositório e execute o cadastro idempotente dos campos usados
pela migração, incluindo orientador, coorientador e membros da banca:

```bash
cd ..
./scripts/register_custom_fields.sh dspacedb
```

### 5. Executar a migração completa

```bash
uv run migrate
```

O comando realiza, nesta ordem:

1. extração, limpeza e geração dos metadados SAF;
2. extração e conversão dos PDFs;
3. criação/reutilização das comunidades e coleções pela API REST;
4. geração e execução de `import_all.sh` dentro do container `dspace`;
5. aplicação das políticas de embargo aos bitstreams;
6. injeção das estatísticas históricas no Solr.

Ao terminar, revise `routing_report.csv`, `pdf_extraction_issues.csv` (se
existir) e um item bilíngue na interface em `http://localhost:4000`. Para gerar
miniaturas e texto indexável dos PDFs, execute:

```bash
cd dspace-docker
docker compose --env-file ../.env -p d10 -f cli.yml run --rm \
  dspace-cli filter-media
```

> [!IMPORTANT]
> `uv run migrate` adiciona itens. Não execute novamente contra o mesmo banco
> DSpace depois de uma importação bem-sucedida, pois isso pode criar duplicatas.
> Uma nova execução completa é apropriada quando os volumes do DSpace foram
> removidos e a instância está vazia.

---

## Estrutura do Pacote e Comandos CLI (`uv`)

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

## Estrutura de Arquivos

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

## Como Executar o Pipeline

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

## Links Úteis e Referências

- [Documentação Oficial DSpace](https://dspace.org/)
- [DSpace Simple Archive Format (SAF) Spec](https://wiki.lyrasis.org/pages/viewpage.action?pageId=104566653)
- [DSpace Docker Setup](https://wiki.lyrasis.org/display/DSPACE/Try+out+DSpace+9#TryoutDSpace9-InstallviaDocker)
- [DSpace REST Client (Python)](https://pypi.org/project/dspace-rest-client/)
