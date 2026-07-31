# Etapa 2: Configuração e Preparação do DSpace via Docker

Esta etapa descreve como inicializar a instância local do DSpace, preparar o banco de dados (cadastrando campos customizados) e montar o volume do pacote SAF gerado na etapa anterior para a importação.

## 1. Diretório do DSpace Docker

O projeto já inclui o ambiente configurado no diretório `dspace-docker/`. Caso esteja utilizando o repositório oficial `dspace-angular`, acesse a pasta equivalente.

```bash
cd dspace-docker
```

## 2. Configurar o Volume do SAF Bundle

Para que o container do DSpace consiga ler os arquivos gerados pela extração, você deve adicionar o mapeamento de volume no arquivo `docker-compose-rest.yml` (ou `docker/docker-compose-rest.yml`).

Abra o arquivo `docker-compose-rest.yml` e, dentro do serviço `dspace`, localize a seção `volumes`. Adicione a linha correspondente ao diretório do `saf_bundle`:

```yaml
    volumes:
      # Keep DSpace assetstore directory between reboots
      - assetstore:/dspace/assetstore
      - /mnt/part2/saf_bundle:/dspace/saf_bundle
```
> [!NOTE]
> Substitua `/mnt/part2/saf_bundle` pelo caminho absoluto exato onde o seu pacote SAF foi gerado na máquina host.

## 3. Iniciar os Containers do DSpace

Faça o pull das imagens e inicie os serviços em segundo plano:

```bash
docker compose -f docker-compose-dist.yml -f docker-compose-rest.yml pull
docker compose -p d10 -f docker-compose-dist.yml -f docker-compose-rest.yml up -d
```

### URLs de Acesso Pós-Inicialização:
- **Interface do Usuário (UI):** `http://localhost:4000/`
- **API REST:** `http://localhost:8080/server/`

## 4. Criar Conta de Administrador

Para realizar a importação de dados, crie uma conta de administrador rodando o comando a seguir:

```bash
docker compose -p d10 -f cli.yml run --rm dspace-cli create-administrator -e test@test.edu -f admin -l user -p admin -c en
```

## 5. Registrar Campos de Metadados Customizados

Alguns metadados exigidos pela migração (como `dc.description.degree`, `dc.description.note`, `dc.contributor.coadvisor`, etc.) não vêm nativamente no esquema padrão do DSpace e precisam ser cadastrados.

Na raiz do repositório da migração, execute o script em `scripts/register_custom_fields.sh` para injetar estes campos no banco de dados do DSpace:

```bash
chmod +x scripts/register_custom_fields.sh
./scripts/register_custom_fields.sh dspacedb
```
*(Onde `dspacedb` é o nome do container Postgres do DSpace).*
