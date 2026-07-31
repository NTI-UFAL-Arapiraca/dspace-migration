# Etapa 2: Configuração e Preparação do DSpace via Docker

Esta etapa descreve como inicializar a instância local do DSpace, preparar o banco de dados (cadastrando campos customizados) e montar o volume do pacote SAF gerado na etapa anterior para a importação.

## 1. Clonar o Repositório do DSpace Angular

Clone o repositório da interface do DSpace e acesse o diretório:

```bash
git clone https://github.com/DSpace/dspace-angular.git
cd dspace-angular
git checkout dspace-10_x
```

## 2. Configurar o Volume do SAF Bundle

Para que o container do DSpace consiga ler os arquivos gerados pela extração, você deve adicionar o mapeamento de volume no arquivo `docker/docker-compose-rest.yml`.

Abra o arquivo `docker/docker-compose-rest.yml` e, dentro do serviço `dspace`, localize a seção `volumes`. Adicione a linha correspondente ao diretório do `saf_bundle`:

```yaml
    volumes:
      # Keep DSpace assetstore directory between reboots
      - assetstore:/dspace/assetstore
      - /mnt/part2/saf_bundle:/dspace/saf_bundle
```
> [!NOTE]
> Substitua `/mnt/part2/saf_bundle` pelo caminho absoluto exato onde o seu pacote SAF foi gerado, caso seja diferente.

## 3. Iniciar os Containers

Faça o pull das imagens mais recentes e inicie os serviços em segundo plano:

```bash
docker compose -f docker/docker-compose-dist.yml -f docker/docker-compose-rest.yml pull
docker compose -p d10 -f docker/docker-compose-dist.yml -f docker/docker-compose-rest.yml up -d
```

### URLs de Acesso Pós-Inicialização:
- **Interface do Usuário (UI):** `http://localhost:4000/`
- **API REST:** `http://localhost:8080/server/`

## 4. Criar Conta de Administrador

Para realizar a importação de dados, você precisa de um usuário administrador no DSpace. Crie um rodando o comando a seguir:

```bash
docker compose -p d10 -f docker/cli.yml run --rm dspace-cli create-administrator -e test@test.edu -f admin -l user -p admin -c en
```

## 5. Registrar Campos de Metadados Customizados

Alguns metadados exigidos pela migração (como `dc.description.note` ou `dc.contributor.coadvisor`) não vêm nativamente no esquema básico do DSpace e precisam ser registrados. Caso contrário, a importação falhará por `bad_dublin_core`.

Execute o script fornecido no repositório da migração, que injetará esses campos diretamente no banco de dados do DSpace:

```bash
chmod +x register_custom_fields.sh
./register_custom_fields.sh dspacedb
```
*(Onde `dspacedb` é o nome do container Postgres do DSpace).*
