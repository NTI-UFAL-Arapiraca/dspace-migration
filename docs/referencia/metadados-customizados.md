# Registro e significado dos metadados da migração

O DSpace permite ampliar o registro de metadados. Neste projeto, o cadastro é
automatizado pelo CLI oficial do DSpace 10.1, sem edição direta das tabelas e
sem exigir a interface administrativa. O XML versionado é
[`config/registries/migration-metadata.xml`](../../config/registries/migration-metadata.xml).

## Campos necessários

Estes dez campos são extensões dos esquemas `dc`, `local` e `person`, usadas
na extração SAF e na criação de perfis Person:

| Campo | Significado local | Origem e regra |
| --- | --- | --- |
| `local.course.name` | Curso ou programa | `ud_curso.name`. Guarda o curso, não o grau acadêmico. Também há roteamento por curso, mas a coleção não substitui esse valor descritivo do item. |
| `local.campus.name` | Campus de origem | `ud_campus.name`. Guarda o campus, não necessariamente departamento ou editora. |
| `local.date.defense` | Data de defesa | `ud_biblioteca_publicacao.data_defesa`, normalizada para ISO e preservada separadamente do ano de publicação. |
| `local.cnpq.area` | Grande área CNPq | Relação `categoria_cnpq_ids` → `ud_biblioteca_publicacao_categoria_cnpq.name`. Um valor por categoria, conforme o nome armazenado na origem. |
| `dc.contributor.coadvisor` | Coorientador | Relação de coorientadores. Um valor por pessoa, no formato `Sobrenome, Nome`. |
| `dc.contributor.referee` | Avaliador da banca | Relação de membros da banca. Um valor por pessoa, no formato `Sobrenome, Nome`. |
| `local.identifier.legacy` | Identidade da pessoa na origem | `odoo:TABELA:ID`; usado por `apply-people` para retomada sem duplicar pessoas. |
| `person.identifier.lattes` | Currículo Lattes | URL HTTPS canônica do currículo; extraída do cadastro de orientadores. |
| `local.person.degree` | Titulação da pessoa | Rótulo original de `ud_biblioteca_orientador_titulacao.name`; não representa cargo. |
| `dc.description.note` | Observação geral ou nota de acervo | Observações legadas após limpeza e classificação. Notas de restrição vão para `dc.description.provenance`; citações identificadas vão para `dc.identifier.citation`. A classificação é heurística e pode exigir revisão. |

Curso usa `local.course.name` e campus usa `local.campus.name`; os aliases
antigos eram `dc.description.degree` e `dc.publisher.department`.
Novos SAFs escrevem curso, campus, data de defesa e grandes áreas CNPq em
`metadata_local.xml`. `apply-people` converte os valores antigos de curso e
campus nos itens já importados, sem excluir definições do registro. Veja
[Pessoas e vínculos](pessoas-e-vinculos.md).

`dc.contributor.advisor` já existe no registro padrão do DSpace 10.1 e não
precisa ser recriado. Títulos, autores, resumos, assuntos, datas e outros
campos padrão continuam sendo usados. O mapeamento completo está em
[Campos migrados](campos-migrados.md).

O cadastro integrado é descrito na [preparação acadêmica](../../../dspace-bca/docs/guias/preparacao-academica.md).
Para executar somente o registro, consulte a [importação por etapas](../guias/importacao-por-etapas.md).

## Repetição e instalações existentes

O importador cria campos ausentes e ignora os já cadastrados. Portanto, pode
ser executado em instalação limpa ou após o antigo script SQL, sem duplicar
campos nem alterar metadados dos itens. Não é necessário reimportar o acervo.

As notas de escopo do XML são aplicadas apenas aos campos novos. Editar uma
nota no XML e executar novamente não atualiza a definição existente; revise
essas notas pela administração ou pela API administrativa quando necessário.
O XML não declara `dc-schema`, preservando os namespaces `dc` e `local`
já instalados no DSpace 10.1.

O antigo script também tentava cadastrar `dc.publisher.place` e
`dc.type.degree`. Esses campos não são preenchidos pela migração atual e
foram retirados do cadastro. Executar o novo script não os apaga de bancos
existentes.

A exclusão de definições antigas é uma manutenção separada. Ela depende de
verificar valores e configurações ainda vinculados aos campos e não é
executada pelo script de cadastro.

## Verificação e limites

A administração permite inspecionar os dez campos cadastrados. Essa
inspeção é independente da execução do registro pelo CLI.

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
