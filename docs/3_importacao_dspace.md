# Etapa 3: Importação Final no DSpace

Nesta etapa, você criará a hierarquia de comunidades/coleções no DSpace e importará os itens do pacote SAF para as coleções corretas.

## 1. Criar a Hierarquia de Comunidades e Coleções

O comando `setup-dspace` conecta à API REST do DSpace e cria automaticamente as comunidades e coleções definidas em `dspace-organization/communities.json`. Se já existirem, são reutilizadas.

Certifique-se de que:
1. A instância DSpace está rodando e acessível.
2. As variáveis de ambiente estão configuradas no `.env`:
   - `DSPACE_API_URL` (default: `http://localhost:8080/server/api`)
   - `DSPACE_API_USER` (default: `test@test.edu`)
   - `DSPACE_API_PASSWORD` (default: `admin`)

```bash
uv run setup-dspace
```

O comando salva o mapeamento `{path → UUID}` em `collection_uuids.json`.

## 2. Gerar o Script de Importação

O comando `generate-import-script` gera o arquivo `import_all.sh` com um comando de importação por coleção:

```bash
uv run generate-import-script
```

O script gerado contém linhas como:

```bash
#!/bin/bash
set -e
/dspace/bin/dspace import -a -e test@test.edu -c <uuid> -s /dspace/saf_bundle/Arapiraca/Administração -m /dspace/saf_bundle/Arapiraca/Administração/mapfile.txt
/dspace/bin/dspace import -a -e test@test.edu -c <uuid> -s /dspace/saf_bundle/Penedo/Engenharia\ de\ Pesca -m /dspace/saf_bundle/Penedo/Engenharia\ de\ Pesca/mapfile.txt
# ... uma linha por coleção que contenha itens
```

## 3. Executar a Importação

Copie o script `import_all.sh` para dentro do container e execute:

```bash
docker cp import_all.sh dspace:/dspace/import_all.sh
docker exec -it dspace bash /dspace/import_all.sh
```

> [!IMPORTANT]
> Certifique-se de que o volume do `saf_bundle` está montado no container conforme descrito na Etapa 2 (`/dspace/saf_bundle`).

### Explicação dos Parâmetros (de cada linha do script)

* **`/dspace/bin/dspace import`**: O script nativo de importação em lote do DSpace.
* **`-a`** (add): Indica que os itens serão **adicionados** ao repositório.
* **`-e test@test.edu`** (eperson): O e-mail do usuário administrador que fará a ação.
* **`-c <uuid>`** (collection): O UUID da coleção destino (obtido automaticamente via `setup-dspace`).
* **`-s /dspace/saf_bundle/<polo>/<coleção>`** (source): Diretório com os itens SAF daquela coleção.
* **`-m .../mapfile.txt`** (mapfile): Arquivo de saída mapeando `id_origem` → `HANDLE` do DSpace.

## 4. Aplicação das Datas de Embargo

Antes de gerar miniaturas, aplique as datas de liberação dos embargos:

```bash
uv run apply-embargoes
```

O comando lê `access_policies.json` e os `mapfile.txt`, localiza os bitstreams do bundle `ORIGINAL` e cria uma política `READ` para o grupo `Anonymous` com início em `data_limite_embargo`. Até essa data, somente administradores conseguem baixar o arquivo. Restrições sem data permanecem privadas.

> [!IMPORTANT]
> Não remova a opção `permissions` dos arquivos `contents`. Ela garante que um PDF nunca fique público no intervalo entre a importação SAF e a aplicação da data de embargo.

## 5. Migração das Estatísticas de Acesso para o Solr

As visualizações históricas vêm de
`ud_biblioteca_publicacao.visualizacoes` no PostgreSQL legado. Elas não são
gravadas como metadados do item: o comando `inject-stats` cria eventos de
visualização diretamente no core `statistics` do Solr.

A injeção depende dos `mapfile.txt` produzidos pela etapa 3. Cada linha associa
`item_<id da publicação>` ao handle criado; o comando consulta o PostgreSQL do
DSpace para resolver o handle em UUID e então associa os eventos ao item certo.
Por isso, execute esta etapa somente após uma importação SAF concluída.

Confira primeiro o cruzamento e o volume sem modificar o Solr:

```bash
uv run inject-stats --dry-run
```

Depois, faça a injeção:

```bash
uv run inject-stats
```

O comando usa `DB_*` para ler a origem, `DSPACE_DB_*` para resolver os UUIDs e
`SOLR_URL`/`SOLR_BATCH_SIZE` para enviar os eventos em lotes. Para cada item,
são gerados tantos eventos quanto o valor de `visualizacoes`. Suas datas são
distribuídas entre janeiro de `ano_pub` e o momento da migração; sem ano válido,
usa-se uma janela de cinco anos.

Os UUIDs dos eventos são determinísticos. Assim, uma retomada com os mesmos
itens atualiza os documentos existentes e não duplica a contagem histórica.
Itens que têm acessos na origem, mas não possuem handle/UUID correspondente,
são indicados no log e ignorados. No pipeline completo, essa etapa é executada
automaticamente por `uv run migrate`; use `--skip-stats` para pulá-la.

## 6. Geração de Miniaturas e Pré-visualizações (Thumbnails / Media Filter)

Após a conclusão da importação dos itens, as miniaturas (thumbnails) e a extração de texto dos arquivos PDFs anexados precisam ser processadas. O DSpace **não** gera as miniaturas automaticamente durante a ingestão via SAF.

Para gerar as miniaturas e os textos indexáveis para pesquisa, execute o utilitário `filter-media`:

```bash
docker exec -it dspace /dspace/bin/dspace filter-media
```

Ou, caso esteja utilizando a estrutura de comandos do `dspace-docker`:

```bash
docker compose -p d10 -f cli.yml run --rm dspace-cli filter-media
```

### Opções Úteis do `filter-media`:

* **`-v`** (verbose): Exibe em tempo real os detalhes de cada arquivo sendo processado.
* **`-f`** (force): Força o reprocessamento de arquivos, mesmo aqueles que já possuem miniaturas previamente geradas.
* **`-p "ImageMagick PDF Thumbnail"`**: Processa especificamente as miniaturas de arquivos PDF utilizando ImageMagick (se configurado no DSpace).
