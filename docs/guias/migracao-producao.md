# Executar a migração em produção

Execute no servidor DSpace, com os dois projetos lado a lado. Pare se algum
comando falhar. Este roteiro mantém a publicação da interface pelo GitHub/GHCR.

## 1. Inicializar os projetos e revisar o piloto

- Conclua a [inicialização da migração](inicializacao.md).
- Conclua a [inicialização ou atualização do DSpace](../../../dspace-bca/docs/guias/inicializacao-producao.md).
- Revise o [piloto local](migracao-local.md) antes do lote definitivo.
- Preserve backup consistente do banco, assetstore e SAF, com os mapfiles.
- Confira se a pasta SAF é a mesma nos dois arquivos de ambiente.

## 2. Preparar campos e pessoas

Siga a [preparação acadêmica de produção](../../../dspace-bca/docs/guias/preparacao-academica.md).
Confira as credenciais administrativas, `DSPACE_PERSON_COLLECTION_UUID`
e a API após o reinício.

## 3. Permitir a gravação dos mapfiles

Na raiz de **`dspace-bca`**:

```bash
docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  -f docker-compose-migration.yml config --quiet

docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  -f docker-compose-migration.yml up -d --no-build --force-recreate dspace
```

Aguarde a API voltar.

## 4. Preparar os trabalhos: escolha apenas uma opção

Entre em **`dspace-migration`**:

```bash
cd ../dspace-migration
```

**A. Lote novo, ainda não importado:**

```bash
uv run migrate --docker-container dspace \
  --skip-people --skip-stats --skip-oai --skip-sitemaps
```

**B. Trabalhos já importados, com os mapfiles preservados:**

```bash
uv run extract-metadata
```

Na opção B, extraia exatamente o lote importado. Se ele usou `--limit 5`,
por exemplo, use `uv run extract-metadata --limit 5` com a mesma origem.
Não execute `migrate` novamente sobre o mesmo lote: ele pode duplicar trabalhos.

## 5. Aplicar pessoas e vínculos

Ainda em **`dspace-migration`**, simule primeiro:

```bash
uv run apply-people --dry-run
```

Confira as quantidades e resolva eventuais divergências. Depois aplique:

```bash
uv run apply-people
```

Para retomar uma interrupção nesta etapa, repita `apply-people`.
Preserve `people.json`, `people-map.json` e os mapfiles.

## 6. Atualizar buscas, OAI e sitemaps

```bash
cd ../dspace-bca
docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  exec -T dspace /dspace/bin/dspace index-discovery -b

cd ../dspace-migration
uv run rebuild-oai --docker-container dspace
uv run generate-sitemaps --docker-container dspace
```

## 7. Revisar na interface

- [ ] Em Editar (`edit-items/`), aparecem os dados acadêmicos.
- [ ] Curso e campus estão corretos e podem ser editados.
- [ ] Autor, orientador, coorientador e banca usam seleção de pessoa cadastrada.
- [ ] Os nomes na página pública abrem o perfil da pessoa.
- [ ] O perfil lista os trabalhos de cada papel corretamente.
- [ ] Resumos, PDFs e embargos continuam corretos.
- [ ] `routing_report.csv` e `pdf_extraction_issues.csv`, quando presentes, foram revisados.

## 8. Encerrar a importação

Depois da revisão, restaure o SAF como somente leitura, em **`dspace-bca`**:

```bash
cd ../dspace-bca
docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  up -d --no-build --force-recreate dspace
```

Guarde o SAF, os mapfiles e os relatórios junto ao registro do lote.
As estatísticas históricas ficam para uma operação separada; este roteiro
não as importa.

Para o funcionamento das identidades e checkpoints, consulte a
[referência de pessoas](../referencia/pessoas-e-vinculos.md). As estatísticas
históricas têm [procedimento separado](estatisticas.md).
