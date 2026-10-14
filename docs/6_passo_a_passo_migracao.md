# Passo a passo da migração acadêmica

Roteiro de **produção**, com publicação da interface pelo GitHub/GHCR.
Execute os comandos na ordem; se um falhar, corrija antes de continuar.
Os projetos `dspace-bca` e `dspace-migration` devem ficar lado a lado.
Para testar primeiro em `d10dev`, siga o [guia completo](../../dspace-bca/docs/guia-dspace-academico.md).

## 1. Conferir os pré-requisitos

- [ ] Docker com Compose, `uv` e Ghostscript (`gs`) instalados na máquina da migração.
- [ ] Banco legado acessível e arquivo GeoLite2 City disponível no servidor DSpace.
- [ ] Backup do banco DSpace, assetstore e SAF, incluindo os `mapfile.txt` existentes.
- [ ] Piloto revisado antes de executar o lote definitivo.

Este roteiro executa a migração no próprio servidor DSpace.
Se houver relacionamentos tradicionais entre entidades, revise sua conversão
antes de atualizar: a configuração nova desativa os metadados virtuais.

## 2. Publicar e atualizar os projetos

Faça commit e push das alterações de ambos os projetos pelo fluxo habitual.
Em `dspace-bca`, aguarde o workflow **Build and publish Angular image**
concluir com sucesso no GitHub Actions.

No servidor, começando na pasta `dspace-migration`:

```bash
git pull --ff-only
uv sync
cd ../dspace-bca
git pull --ff-only
```

## 3. Conferir os arquivos de ambiente

Edite os arquivos existentes. Se ainda não existirem, copie os respectivos
exemplos: `.env.production.example` em `dspace-bca` e `.env.example` em
`dspace-migration`.

Em **`dspace-bca/.env`**, confira:

```dotenv
DSPACE_ANGULAR_IMAGE=ghcr.io/nti-ufal-arapiraca/dspace-bca-angular
DSPACE_ANGULAR_TAG=dspace-10.1
DSPACE_SAF_HOST_DIR=/srv/dspace/saf_bundle
```

Preencha também senha do PostgreSQL, caminho do GeoLite2, URLs públicas e
demais valores de `.env.production.example`. Use seus caminhos e domínio reais.

Em **`dspace-migration/.env`**, confira:

```dotenv
SAF_BUNDLE_DIR=/srv/dspace/saf_bundle
DSPACE_API_URL=https://repo.interno.example.org/dspace-server/api
```

Preencha `DB_*`, `DSPACE_API_USER` e `DSPACE_API_PASSWORD` com os acessos
corretos. A pasta SAF deve existir e ser a mesma nos dois projetos.
Para lote novo, use uma pasta exclusiva; para trabalhos já importados,
preserve o SAF original e seus mapfiles.

Deixe `DSPACE_PERSON_COLLECTION_UUID` vazio na primeira preparação.
Ao trocar de ambiente, não reutilize o UUID nem o `people-map.json` de outro destino.

## 4. Atualizar o DSpace

Na pasta **`dspace-bca`**:

```bash
docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  -f docker-compose-migration.yml config --quiet

docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  -f docker-compose-migration.yml pull dspace-angular

docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  -f docker-compose-migration.yml \
  up -d --no-build --force-recreate dspace dspace-angular dspace-proxy
```

Aguarde a API e a interface responderem nas URLs públicas configuradas.

## 5. Preparar administrador, campos e coleção Pessoas

Se ainda não houver administrador, crie-o em **`dspace-bca`**:

```bash
docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  exec dspace /dspace/bin/dspace create-administrator
```

Use esse e-mail e senha em `DSPACE_API_USER` e `DSPACE_API_PASSWORD` do
`.env` da migração. Se já houver administrador, use a conta existente.

Ainda em **`dspace-bca`**:

```bash
bash scripts/prepare-academic.sh --project-name d10 \
  --env-file .env --migration-env-file ../dspace-migration/.env

docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  restart dspace
```

Confira o término da preparação e o preenchimento automático de
`DSPACE_PERSON_COLLECTION_UUID`. Aguarde a API voltar após o reinício.

## 6. Preparar os trabalhos: escolha apenas uma opção

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

## 7. Aplicar pessoas e vínculos

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

## 8. Atualizar buscas, OAI e sitemaps

```bash
cd ../dspace-bca
docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml -f docker-compose-prod.yml \
  exec -T dspace /dspace/bin/dspace index-discovery -b

cd ../dspace-migration
uv run rebuild-oai --docker-container dspace
uv run generate-sitemaps --docker-container dspace
```

## 9. Revisar na interface

- [ ] Em Editar (`edit-items/`), aparecem os dados acadêmicos.
- [ ] Curso e campus estão corretos e podem ser editados.
- [ ] Autor, orientador, coorientador e banca usam seleção de pessoa cadastrada.
- [ ] Os nomes na página pública abrem o perfil da pessoa.
- [ ] O perfil lista os trabalhos de cada papel corretamente.
- [ ] Resumos, PDFs e embargos continuam corretos.
- [ ] `routing_report.csv` e `pdf_extraction_issues.csv`, quando presentes, foram revisados.

## 10. Encerrar a importação

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

Para dúvidas, consulte o [guia completo](../../dspace-bca/docs/guia-dspace-academico.md)
e o [guia de pessoas e vínculos](5_pessoas_e_vinculos.md).
