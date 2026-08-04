# Etapa 3: Importação Final no DSpace

Nesta etapa, você usará a ferramenta de linha de comando (`dspace-cli`) de dentro do container docker para ingerir o pacote SAF (Simple Archive Format) para dentro do repositório DSpace.

## Executando o Comando de Importação

Certifique-se de que:
1. O volume do `saf_bundle` está corretamente montado (conforme Etapa 2).
2. O usuário administrador (`test@test.edu`) existe e tem as permissões corretas.
3. Você tem o ID UUID (`-c`) da Coleção de destino onde os itens serão publicados.

Execute o comando de importação abaixo diretamente através do utilitário `docker exec`:

```bash
docker exec -it dspace /dspace/bin/dspace import -a -e test@test.edu -c 2dff658e-9ed6-490c-80ac-826f0ed342fb -s /dspace/saf_bundle -m /dspace/saf_bundle/mapfile.txt
```

### Explicação dos Parâmetros

* **`docker exec -it dspace`**: Executa o comando interativamente dentro do container nomeado `dspace`.
* **`/dspace/bin/dspace import`**: O script nativo de importação em lote do DSpace.
* **`-a`** (add): Indica que os itens serão **adicionados** ao repositório.
* **`-e test@test.edu`** (eperson): O e-mail do usuário administrador que fará a ação.
* **`-c 2dff658e-9ed6-490c-80ac-826f0ed342fb`** (collection): O UUID da coleção que receberá as publicações. *Troque este UUID pelo ID correspondente à sua comunidade/coleção se for diferente.*
* **`-s /dspace/saf_bundle`** (source): O caminho de origem (agora dentro do container) onde o seu SAF bundle está armazenado, montado como volume.
* **`-m /dspace/saf_bundle/mapfile.txt`** (mapfile): O arquivo de saída (mapfile) que o DSpace vai gerar ao concluir a importação, mapeando os `id_origem` com os novos `HANDLEs` gerados no DSpace. Útil para reverter importações futuramente caso ocorram erros.

## Geração de Miniaturas e Pré-visualizações (Thumbnails / Media Filter)

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

