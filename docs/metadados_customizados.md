# Registro e significado dos metadados da migração

O DSpace permite ampliar o registro de metadados. Neste projeto, o cadastro é
automatizado pelo CLI oficial do DSpace 10.1, sem edição direta das tabelas e
sem exigir a interface administrativa. O XML versionado é
[`config/registries/migration-metadata.xml`](../config/registries/migration-metadata.xml).

## Campos necessários

Estes cinco campos são extensões locais do esquema `dc`, utilizadas pelo
[`SQL de extração`](../sql/extract_metadata.sql) e pelo gerador SAF:

| Campo | Significado local | Origem e regra |
| --- | --- | --- |
| `dc.description.degree` | Curso ou programa | `ud_curso.name`. Guarda o curso, não o grau acadêmico. Também há roteamento por curso, mas a coleção não substitui esse valor descritivo do item. |
| `dc.publisher.department` | Campus de origem | `ud_campus.name`. Guarda o campus, não necessariamente departamento ou editora. |
| `dc.contributor.coadvisor` | Coorientador | Relação de coorientadores. Um valor por pessoa, no formato `Sobrenome, Nome`. |
| `dc.contributor.referee` | Avaliador da banca | Relação de membros da banca. Um valor por pessoa, no formato `Sobrenome, Nome`. |
| `dc.description.note` | Observação geral ou nota de acervo | Observações legadas após limpeza e classificação. Notas de restrição vão para `dc.description.provenance`; citações identificadas vão para `dc.identifier.citation`. A classificação é heurística e pode exigir revisão. |

Os nomes são convenções locais preservadas para manter compatibilidade com os
pacotes SAF e os itens já importados. Eles não constituem uma recomendação
universal de catalogação. Mudar um nome exige revisar o SQL, os pacotes SAF,
os valores já armazenados e as configurações de exibição, submissão, busca e
exportação que o utilizem.

`dc.contributor.advisor` já existe no registro padrão do DSpace 10.1 e não
precisa ser recriado. Títulos, autores, resumos, assuntos, datas e outros
campos padrão continuam sendo usados. O mapeamento completo está em
[`0_campos_a_migrar.md`](0_campos_a_migrar.md).

## Aplicar o registro

Execute antes de importar os itens SAF. O backend deve estar iniciado, com
`/dspace/bin/dspace` disponível e acesso ao banco DSpace de destino. O usuário
que executa o script precisa ter acesso ao Docker; não são necessárias
credenciais da API REST nem do PostgreSQL no script.

Na raiz deste repositório:

```bash
./scripts/register_custom_fields.sh NOME_OU_ID_DO_CONTAINER_DSPACE
```

O argumento identifica o **container do backend**, não o PostgreSQL. Use
`docker ps` para descobrir seu nome. Sem argumento, o script usa
`DSPACE_CONTAINER` do ambiente ou `dspace`. O script não carrega o `.env`.

Em produção, também é possível obter o ID pelo Compose. Execute na pasta da
instalação DSpace (ajuste o caminho do repositório da migração):

```bash
docker compose --env-file .env -p d10 \
  -f docker-compose-dist.yml -f docker-compose-rest.yml \
  -f docker-compose-prod.yml ps -q dspace
```

Passe o ID retornado ao script:

```bash
~/dspace-migration/scripts/register_custom_fields.sh ID_RETORNADO
```

O script resolve o XML em relação à sua própria localização, copia-o para um
arquivo temporário no container e executa:

```bash
/dspace/bin/dspace registry-loader -m /tmp/ARQUIVO_TEMPORARIO.xml
```

O arquivo temporário é removido ao terminar. Falhas na cópia ou no importador
fazem o script terminar com código diferente de zero; consulte a saída do CLI.
O cadastro é independente da hierarquia de comunidades e coleções e não é
executado automaticamente por `uv run migrate`.

## Repetição e instalações existentes

O importador cria campos ausentes e ignora os já cadastrados. Portanto, pode
ser executado em instalação limpa ou após o antigo script SQL, sem duplicar
campos nem alterar metadados dos itens. Não é necessário reimportar o acervo.

As notas de escopo do XML são aplicadas apenas aos campos novos. Editar uma
nota no XML e executar novamente não atualiza a definição existente; revise
essas notas pela administração ou pela API administrativa quando necessário.
O XML não contém uma declaração `dc-schema`, para preservar o namespace do
esquema já instalado.

O antigo script também tentava cadastrar `dc.publisher.place` e
`dc.type.degree`. Esses campos não são preenchidos pela migração atual e
foram retirados do cadastro. Executar o novo script não os apaga de bancos
existentes.

Antes de remover esses dois campos em uma instalação existente, confira se
há valores ou configurações locais que os utilizam. Na administração do
DSpace, abra o registro de metadados, selecione o esquema `dc` e os campos
correspondentes. Remova somente as definições sem uso; se houver valores,
primeiro decida como preservá-los. A exclusão é uma manutenção separada do
cadastro e não é executada por este script.

## Verificação e limites

Após executar o script, confira no registro de metadados da administração
que os cinco campos estão presentes. A interface é uma opção de inspeção,
não uma etapa obrigatória para o cadastro. Registre a saída do CLI junto à
execução da migração e teste a importação de um pacote SAF representativo.

Cadastrar um campo permite armazenar seus valores; não cria automaticamente
um controle no formulário de submissão, uma seção na página do item, uma
faceta de busca ou um mapeamento OAI-PMH. Essas configurações devem ser
mantidas na instalação DSpace e verificadas separadamente. A presença de
texto sobre embargo em um campo também não impõe restrições de acesso:
estas são aplicadas por políticas nos bitstreams.

## Referências da versão 10.1

- [Comando registry-loader no launcher oficial](https://github.com/DSpace/DSpace/blob/dspace-10.1/dspace/config/launcher.xml).
- [RegistryLoader: opção -m e chamada do importador](https://github.com/DSpace/DSpace/blob/dspace-10.1/dspace-api/src/main/java/org/dspace/administer/RegistryLoader.java).
- [MetadataImporter: formato XML, transação e tratamento de campos existentes](https://github.com/DSpace/DSpace/blob/dspace-10.1/dspace-api/src/main/java/org/dspace/administer/MetadataImporter.java).
- [Registro Dublin Core padrão](https://github.com/DSpace/DSpace/blob/dspace-10.1/dspace/config/registries/dublin-core-types.xml).

O procedimento mantido no projeto usa o comando nomeado do launcher oficial:
`registry-loader -m arquivo.xml`.
