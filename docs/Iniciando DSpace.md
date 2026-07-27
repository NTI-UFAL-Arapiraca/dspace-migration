Para iniciar o DSpace via Docker e gerenciar a importação de arquivos/conteúdos com base nas instruções oficiais, você precisará seguir os requisitos e passos detalhados abaixo.

## 1. Pré-requisitos do Sistema

- **Ferramentas:** **Docker** (Docker Desktop para Windows/Mac ou Docker Engine para Linux) e **Git** instalados.
    
- **Recursos de Hardware:** Pelo menos **6GB de memória RAM** alocados para o Docker (8GB recomendados).
    

## 2. Passos para Iniciar o DSpace via Docker

Clone o repositório da interface Angular do DSpace e inicie os containers com os comandos do Docker Compose:

Bash

```
# 1. Clonar o repositório da UI
git clone https://github.com/DSpace/dspace-angular.git

# 2. Entrar no diretório do projeto
cd dspace-angular

# 3. Mudar para a branch correta (ex: dspace-9_x)
git checkout dspace-10_x

# 4. Baixar as imagens mais recentes do Docker (frontend e backend)
docker compose -f docker/docker-compose-dist.yml -f docker/docker-compose-rest.yml pull

# 5. Iniciar os serviços em segundo plano (-d)
docker compose -p d10 -f docker/docker-compose-dist.yml -f docker/docker-compose-rest.yml up -d
```

### URLs de Acesso Pós-Inicialização:

- **Interface do Usuário (UI):** `http://localhost:4000/`
    
- **API REST:** `http://localhost:8080/server/`
    

## 3. Importação de Arquivos e Dados (Ingest)

Para popular o ambiente Docker com pacotes de dados (como pacotes AIP de teste ou lotes estruturados), utilize o container CLI do DSpace (`dspace-cli`).

### Criar uma Conta de Administrador (Necessária para importações)

Antes de executar rotinas de importação que dependem de um usuário administrador, crie a conta padrão via CLI:

Bash

```
docker compose -p d10 -f docker/cli.yml run --rm dspace-cli create-administrator -e test@test.edu -f admin -l user -p admin -c en
```

### Importar Dados de Exemplo (AIP Test Data)

Se você deseja testar a importação automatizada utilizando o conjunto de dados padrão disponibilizado pelo DSpace (ou para adaptar para os seus lotes SAF customizados gerados na migração):

Bash

```
docker compose -p d10 -f docker/cli.yml -f ./docker/cli.ingest.yml run --rm dspace-cli
```

## 4. Gerenciamento e Monitoramento Útil

- **Monitorar logs de inicialização:**
    
    Bash
    
    ```
    docker compose -p d10 -f docker/docker-compose-dist.yml -f docker/docker-compose-rest.yml logs -f
    ```
    
- **Reiniciar o ambiente (caso ocorra algum erro):**
    
    Bash
    
    ```
    docker compose -p d10 -f docker/docker-compose-dist.yml -f docker/docker-compose-rest.yml down
    docker compose -p d10 -f docker/docker-compose-dist.yml -f docker/docker-compose-rest.yml up -d
    ```
    
- **Parar e limpar totalmente os dados e volumes:**
    
    Bash
    
    ```
    docker compose -p d10 -f docker/docker-compose-dist.yml -f docker/docker-compose-rest.yml down
    docker system prune --volumes
    ```