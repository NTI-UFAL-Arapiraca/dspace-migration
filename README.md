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

Revise o `.env`, principalmente as credenciais `DB_*` do PostgreSQL de origem,
`DSPACE_API_USER`/`DSPACE_API_PASSWORD` e o nome público `DSPACE_NAME`. O
diretório `SAF_BUNDLE_DIR` deve ser o mesmo montado no container DSpace. Com o
valor padrão `saf_bundle`, isso já é feito automaticamente. Para usar outro
disco, configure ambos com o mesmo caminho absoluto:

```dotenv
SAF_BUNDLE_DIR=/caminho/absoluto/saf_bundle
DSPACE_SAF_HOST_DIR=/caminho/absoluto/saf_bundle
```

Informe também o caminho absoluto do banco MaxMind GeoLite2 City. O arquivo
não faz parte do repositório e é montado somente para leitura no backend:

```dotenv
GEOLITE2_CITY_DB_PATH=/caminho/absoluto/GeoLite2-City.mmdb
```

O DSpace 10 usa o formato `.mmdb` e a propriedade
`usage-statistics.dbfile`. O exemplo antigo `GeoLiteCity.dat` não se aplica a
esta versão.

Backend, Solr, CLI e frontend acompanham o tag `dspace-10_x`, que recebe as
correções mais recentes da linha 10. Mantenha
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
6. injeção das estatísticas históricas no Solr;
7. reconstrução do índice OAI-PMH no core `oai` do Solr;
8. geração dos sitemaps XML e HTML para mecanismos de busca.

Ao terminar, revise `routing_report.csv`, `pdf_extraction_issues.csv` (se
existir) e um item bilíngue na interface em `http://localhost:4000`.

Para preencher do zero o índice OAI-PMH depois da importação inicial:

```bash
uv run rebuild-oai
```

Confira o endpoint com:

```bash
curl --fail \
  'http://localhost:8080/server/oai/request?verb=Identify'
```

O pipeline também gera os sitemaps imediatamente; o backend volta a gerá-los
todos os dias às 01:15. Para executar somente essa etapa:

```bash
uv run generate-sitemaps
```

Valide os três requisitos básicos de SEO:

```bash
curl --fail http://localhost:4000/robots.txt
curl --fail http://localhost:4000/sitemap_index.xml
curl --fail http://localhost:4000/sitemap_index.html
```

O container `dspace-angular` usa o runtime SSR oficial de produção. Uma
requisição direta a uma página de item deve retornar o título e os metadados no
HTML, mesmo sem executar JavaScript.

Em produção, configure `DSPACE_SERVER_URL`, `DSPACE_UI_URL` e
`DSPACE_ADMIN_EMAIL` no `.env` com o domínio HTTPS e o contato institucionais.
O endpoint público será
`{DSPACE_SERVER_URL}/{OAI_PATH}/request`. Para gerar miniaturas e texto
indexável dos PDFs, execute:

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

### Migração das Estatísticas de Acesso para o Solr

A última etapa do `uv run migrate` recria no core `statistics` do Solr as
visualizações históricas armazenadas em
`ud_biblioteca_publicacao.visualizacoes`. Esse dado não vira metadado Dublin
Core. Para cada visualização legada é criado um evento de consulta do item.

O relacionamento com o novo item ocorre em três passos:

1. o importador SAF grava em cada coleção um `mapfile.txt`, relacionando
   `item_<id da publicação>` ao handle criado pelo DSpace;
2. o pipeline resolve esse handle para o UUID do item no PostgreSQL do DSpace;
3. os eventos são enviados em lotes ao endpoint de atualização do core
   `statistics` e recebem um commit final.

As datas dos eventos são distribuídas uniformemente entre 1º de janeiro de
`ano_pub` e a data da migração. Quando o ano está ausente ou inválido, é usada
uma janela de cinco anos. Os identificadores dos eventos são determinísticos;
portanto, repetir a injeção para os mesmos itens sobrescreve os eventos
históricos em vez de duplicá-los.

Essa etapa exige o banco legado, o PostgreSQL do DSpace e o Solr acessíveis
pelas variáveis `DB_*`, `DSPACE_DB_*`, `SOLR_URL` e `SOLR_BATCH_SIZE` do `.env`.
Ela só pode rodar depois da importação SAF, pois depende dos `mapfile.txt`.

Para conferir a quantidade que será migrada sem escrever no Solr:

```bash
uv run inject-stats --dry-run
```

Para executar ou retomar apenas esta etapa:

```bash
uv run inject-stats
```

O `uv run migrate --skip-stats` pula a injeção. Itens com visualizações na
origem, mas sem handle/UUID correspondente no DSpace, são informados e
ignorados. O resumo final exibe o total de documentos Solr enviados e de itens
processados.

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
| `uv run rebuild-oai` | Limpa e reconstrói o índice OAI-PMH a partir dos itens do DSpace. |
| `uv run generate-sitemaps` | Gera os índices XML e HTML anunciados em `robots.txt`. |
| `uv run migrate` | Executa o pipeline completo: extração, hierarquia, importação SAF, embargos, estatísticas, OAI e sitemaps. |

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
4. **[Operação e manutenção: SEO, OAI, volumes e atualizações](docs/4_operacao_manutencao.md)**

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
