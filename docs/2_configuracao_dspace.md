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

## 3. Configurar os Formulários do Backend

O arquivo `dspace-docker/backend/config/submission-forms.xml` foi extraído da
imagem oficial e é montado em `/dspace/config/submission-forms.xml` pelos
serviços REST e CLI. Nele, `dc.description.abstract` está configurado como
repetível nos formulários `traditionalpagetwo` e
`openairePublicationPagetwoForm`.

Cada definição também habilita o seletor de idioma por meio de:

```xml
<language value-pairs-name="common_iso_languages">true</language>
<repeatable>true</repeatable>
```

A lista `common_iso_languages` contém `pt_BR`, compatível com o idioma gravado
pela migração, e `en`. Alterações nesse XML exigem a recriação do container
`dspace`, mas não a reconstrução da imagem.

## 4. Configurar o Frontend e o Tema

O frontend é compilado por `dspace-docker/Dockerfile.angular`. Ele usa o código
fonte presente na imagem oficial `dspace/dspace-angular:dspace-10_x`, sobrepõe
os arquivos mantidos em `frontend/themes/custom/` e executa o build de
produção. Dessa forma, o projeto mantém somente suas diferenças em vez de uma
cópia completa do repositório DSpace Angular.

O arquivo `frontend/config/config.prod.yml` é montado no container e carregado
por `DSPACE_APP_CONFIG_PATH`. Ele ativa o tema `custom` globalmente e pode
sobrescrever qualquer configuração de runtime. Variáveis de ambiente do
Compose continuam com prioridade sobre o YAML.

Use os diretórios abaixo para personalização:

- `frontend/themes/custom/styles/`: cores, fontes, variáveis e CSS global;
- `frontend/themes/custom/assets/`: logotipos, favicons, fontes e traduções;
- `frontend/themes/custom/app/`: componentes Angular sobrescritos, mantendo o
  mesmo caminho do template `src/themes/custom` da versão oficial.

Após alterar tema, assets ou componentes, reconstrua o serviço:

```bash
docker compose -p d10 -f docker-compose-dist.yml -f docker-compose-rest.yml \
  up -d --build dspace-angular
```

Alterações apenas em `frontend/config/config.prod.yml` não exigem compilação;
recrie o container com `--force-recreate`.

## 5. Iniciar os Containers do DSpace

Faça o pull das imagens do backend, compile o frontend e inicie os serviços:

```bash
docker compose -p d10 -f docker-compose-dist.yml -f docker-compose-rest.yml \
  pull dspace dspacedb dspacesolr
docker compose -p d10 -f docker-compose-dist.yml -f docker-compose-rest.yml \
  build --pull dspace-angular
docker compose -p d10 -f docker-compose-dist.yml -f docker-compose-rest.yml up -d
```

### URLs de Acesso Pós-Inicialização:
- **Interface do Usuário (UI):** `http://localhost:4000/`
- **API REST:** `http://localhost:8080/server/`

## 6. Criar Conta de Administrador

Para realizar a importação de dados, crie uma conta de administrador rodando o comando a seguir:

```bash
docker compose -p d10 -f cli.yml run --rm dspace-cli create-administrator -e test@test.edu -f admin -l user -p admin -c en
```

## 7. Registrar Campos de Metadados Customizados

Alguns metadados exigidos pela migração (como `dc.description.degree`, `dc.description.note`, `dc.contributor.coadvisor` e `dc.contributor.referee`) não vêm nativamente no esquema padrão do DSpace e precisam ser cadastrados.

Na raiz do repositório da migração, execute o script em `scripts/register_custom_fields.sh` para injetar estes campos no banco de dados do DSpace:

```bash
chmod +x scripts/register_custom_fields.sh
./scripts/register_custom_fields.sh dspacedb
```
*(Onde `dspacedb` é o nome do container Postgres do DSpace).*
