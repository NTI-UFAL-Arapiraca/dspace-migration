# Inicializar o ambiente da migração

Execute na raiz de `dspace-migration`. Mantenha `dspace-bca` ao lado deste
projeto. Requer Docker com Compose, `uv` e Ghostscript (`gs`).

## 1. Instalar as dependências

```bash
uv sync
```

## 2. Preparar o arquivo de ambiente

Somente se ainda não houver `.env`:

```bash
cp .env.example .env
chmod 600 .env
```

Edite o `.env` e preencha:

| Variável | Valor a conferir |
| --- | --- |
| `DB_*` | Conexão com o PostgreSQL legado. |
| `SAF_BUNDLE_DIR` | Caminho absoluto da pasta deste lote. |
| `DSPACE_API_URL` | API do destino: local ou pública. |
| `DSPACE_API_USER` e `DSPACE_API_PASSWORD` | Conta administrativa do DSpace. |
| `DSPACE_PERSON_COLLECTION_UUID` | Vazio na primeira preparação; depois, UUID salvo pelo script. |

Para desenvolvimento, use `http://localhost:8080/server/api`. Na produção,
use sua URL pública, como `https://repo.interno.example.org/dspace-server/api`.
Crie a pasta SAF configurada. Ela deve ser a mesma de `DSPACE_SAF_HOST_DIR`
no arquivo de ambiente do projeto `dspace-bca`.

Para lote novo, use pasta exclusiva. Para retomar trabalhos importados,
preserve o SAF e os mapfiles originais. Ao trocar de destino, não reutilize
`people-map.json` nem UUIDs de coleções do ambiente anterior.

## 3. Disponibilizar a origem

Se `DB_*` já aponta para um banco acessível, prossiga para o passo 4.
Para restaurar os dumps locais, confira seus nomes em `scripts/init-db.sh`,
coloque-os em `dumps/` e execute:

```bash
./scripts/init-db.sh
```

Se o volume já tiver sido restaurado, apenas inicie o banco:

```bash
docker compose -p biblioteca-migracao -f biblioteca-compose.yml up -d
```

Confira a porta 5440 e as credenciais em `DB_*`.

## 4. Inicializar o destino

No projeto `dspace-bca`, siga somente o ambiente escolhido:

- [Inicialização local](../../../dspace-bca/docs/guias/inicializacao-local.md).
- [Inicialização de produção](../../../dspace-bca/docs/guias/inicializacao-producao.md).

Confira login na API antes de preparar os campos. O pipeline não inicia o
DSpace nem cria o administrador automaticamente.

## 5. Escolher o roteiro de dados

- [Piloto local](migracao-local.md).
- [Migração em produção ou atualização de lote existente](migracao-producao.md).
- [Importação por etapas](importacao-por-etapas.md).
