# Mapeamento Efetivo dos Dados Migrados

Este documento descreve o que o pipeline realmente migra hoje. As fontes de verdade técnicas são `sql/extract_metadata.sql` e os módulos em `src/dspace_migration/`.

O fluxo parte do banco PostgreSQL legado `biblioteca`, gera um pacote SAF e importa os itens no DSpace. Alguns dados não viram metadados Dublin Core: eles são usados para roteamento, controle de acesso, arquivos ou estatísticas.

## 1. Metadados Descritivos do Item

| Dado migrado | Origem | Destino no DSpace | Tratamento aplicado |
| --- | --- | --- | --- |
| Título principal | `ud_biblioteca_publicacao.name` | `dc.title` | Remove HTML, entidades HTML e espaços/quebras de linha excedentes. |
| Título alternativo | `ud_biblioteca_publicacao.titulo_abstract` | `dc.title.alternative` | O valor isolado `Abstract` é descartado por não representar um título. |
| Resumo em português | `ud_biblioteca_publicacao.resumo` | `dc.description.abstract`, idioma `pt_BR` | Remove HTML e normaliza espaços e quebras de linha. |
| Abstract em inglês | `ud_biblioteca_publicacao.abstract` | `dc.description.abstract`, idioma `en` | Recebe a mesma limpeza. Se for idêntico ao resumo em português, a duplicata em inglês é removida. |
| Data de defesa | `ud_biblioteca_publicacao.data_defesa` | `dc.date.issued` | Mantida no formato retornado pelo PostgreSQL. `dc.date.submitted` não é gerado pela migração. |
| Número de páginas | `ud_biblioteca_publicacao.numero_paginas` | `dc.format.extent` | Migrado como texto. |
| Tipo de documento | `ud_biblioteca_publicacao.tipo_id` → `ud_biblioteca_publicacao_tipo.name` | `dc.type` | Mantém a denominação existente na base. |
| Curso | `ud_biblioteca_publicacao.curso_id` → `ud_curso.name` | `dc.description.degree` | Também é usado para escolher a coleção de destino; veja a seção 4. |
| Campus/departamento | `ud_biblioteca_publicacao.campus_id` → `ud_campus.name` | `dc.publisher.department` | Mantém a denominação existente na base. |
| Palavras-chave | relação `publicacao_p_chave_rel` → `ud_biblioteca_p_chave.name` | `dc.subject` | Cada palavra-chave vira um valor separado no XML. |
| Idioma do documento | Valor definido pela migração | `dc.language.iso` | Todos os itens recebem `pt_BR`, indicando português do Brasil. Não existe uma coluna de idioma consultada na origem. |

## 2. Pessoas Relacionadas à Publicação

| Dado migrado | Origem e relacionamento | Destino no DSpace | Formato |
| --- | --- | --- | --- |
| Autores | `ud_biblioteca_publicacao_autores` → `ud_biblioteca_publicacao_autor` (`ultimo_nome`, `name`) | `dc.contributor.author` | `Sobrenome, Nome`; um valor por autor. |
| Orientadores | `publicacao_orientador_rel` → `ud_biblioteca_publicacao_orientador` (`ultimo_nome`, `name`) | `dc.contributor.advisor` | `Sobrenome, Nome`; um valor por orientador. |
| Coorientadores | `publicacao_coorientador_rel` → `ud_biblioteca_publicacao_orientador` (`ultimo_nome`, `name`) | `dc.contributor.coadvisor` | `Sobrenome, Nome`; um valor por coorientador. |
| Membros avaliadores da banca | `publicacao_membro_banca_rel` → `ud_biblioteca_publicacao_orientador` (`ultimo_nome`, `name`) | `dc.contributor.referee` | `Sobrenome, Nome`; um valor por avaliador. |

Os valores múltiplos são agregados pela consulta SQL com o separador interno `||` e voltam a ser separados na geração do `dublin_core.xml`.

## 3. Observações, Citações e Notas Internas

Todos estes destinos partem de `ud_biblioteca_publicacao.observacoes`. O texto passa por limpeza de HTML e por uma classificação baseada em palavras-chave:

| Conteúdo identificado | Destino no DSpace | Exemplos de indicadores |
| --- | --- | --- |
| Restrição, embargo ou informação confidencial | `dc.description.provenance` | `restrito`, `embargo`, `sigilo`, `somente admin`, `sem autorização` ou `autorização pendente/negada` |
| Nota sobre acervo ou exemplar físico | `dc.description.note` | `acervo`, `impresso`, `biblioteca`, `BCA` |
| Referência bibliográfica ou publicação externa | `dc.identifier.citation` | volume, número, página, ISSN, DOI, URL, revista ou anais |

`dc.description.provenance` é ocultado do público pela configuração do DSpace, pois pode conter informação administrativa. Se uma observação não corresponder a uma restrição nem a uma citação, ela é preservada somente em `dc.description.note`.

## 4. Identificação e Roteamento do Item

| Dado de controle | Origem | Destino/uso |
| --- | --- | --- |
| ID da publicação | `ud_biblioteca_publicacao.id` | Nome da pasta SAF, no formato `item_<id>`; depois é relacionado ao handle do DSpace nos arquivos `mapfile.txt`. Não vira metadado Dublin Core. |
| Curso para roteamento | `ud_curso.name` | Consultado em `dspace-organization/map.json` para escolher `saf_bundle/<polo>/<coleção>/item_<id>`. |
| Curso sem mapeamento | `ud_curso.name` sem correspondência no `map.json` | Item colocado em `saf_bundle/_unmapped/` e registrado em `routing_report.csv`. |

A hierarquia de comunidades e coleções é definida em `dspace-organization/communities.json`. Portanto, o nome do curso na origem não é usado diretamente como nome de coleção sem antes passar pelo mapeamento.

## 5. Arquivos e Bitstreams

| Dado migrado | Origem | Destino no DSpace | Tratamento aplicado |
| --- | --- | --- | --- |
| Vínculo do anexo com o item | `ud_biblioteca_anexo.publicacao_id` | Bitstream do item correspondente no bundle `ORIGINAL` | O ID localiza a pasta `item_<id>` gerada anteriormente. |
| Nome do arquivo | `ud_biblioteca_anexo.name` | Nome do bitstream e entrada no arquivo SAF `contents` | Caracteres inválidos são substituídos; nomes repetidos recebem o ID do anexo. |
| Conteúdo binário | `ud_biblioteca_anexo.arquivo` | Arquivo físico/bitstream | Decodifica `bytea`, hexadecimal ou Base64. PDFs são convertidos para PDF/A-2 com Ghostscript; se a conversão falhar, o original é preservado e a falha é registrada. |
| Indicador de exibição | `ud_biblioteca_anexo.exibir_pdf` | Filtro da extração | Somente anexos com `exibir_pdf = true` são migrados. |
| ID do anexo | `ud_biblioteca_anexo.id` | Controle interno da migração | Usado para diferenciar nomes e registrar ocorrências em `pdf_extraction_issues.csv`; não vira metadado. |

Arquivos não PDF também são preservados quando o registro selecionado por `exibir_pdf` os contém. Publicações com mais de um anexo geram várias linhas em `contents`.

## 6. Embargos e Restrições de Acesso

O item e seus metadados continuam no DSpace; a restrição é aplicada aos bitstreams para impedir o download do documento.

| Controle na origem | Interpretação | Destino/efeito no DSpace |
| --- | --- | --- |
| `ud_biblioteca_publicacao.data_limite_embargo` com data futura | Embargo ativo até a data informada | O `contents` do SAF restringe inicialmente o arquivo ao grupo `Administrator`. Após a importação, é criada uma Resource Policy `READ` para `Anonymous`, com `startDate` igual à data de liberação. |
| `data_limite_embargo` igual ou anterior à data da extração | Embargo encerrado | O bitstream é importado com o acesso normal da coleção. |
| `data_limite_embargo` preenchida, mas inválida | Erro de dado que não pode liberar o arquivo com segurança | O bitstream permanece restrito, sem liberação automática. |
| `autorizar_publicacao = false`, sem data de embargo | Restrição sem prazo | O bitstream fica acessível apenas para administradores. |
| Observação que indica restrição, sem data | Restrição sem prazo | O bitstream fica acessível apenas para administradores. |

As decisões de acesso são registradas em `saf_bundle/access_policies.json` e resumidas em `embargoed_items.csv`. O comando `apply-embargoes` usa esse manifesto e os `mapfile.txt` para configurar as datas no DSpace. Se essa etapa falhar, o arquivo permanece privado.

## 7. Estatísticas de Visualização

| Dado migrado | Origem | Destino no DSpace | Tratamento aplicado |
| --- | --- | --- | --- |
| Total histórico de visualizações | `ud_biblioteca_publicacao.visualizacoes` | Core `statistics` do Solr | Para valores maiores que zero, o pipeline gera a mesma quantidade de eventos de visualização associados ao UUID do item. |
| Ano de referência | `ud_biblioteca_publicacao.ano_pub` | Data dos eventos sintéticos no Solr | Os eventos são distribuídos uniformemente entre janeiro do ano de publicação e a data da migração. Sem ano, usa-se uma janela de cinco anos. |

Esses eventos preservam a contagem total, mas não representam as datas, IPs ou sessões reais das visualizações ocorridas no sistema antigo.

## 8. Campos que Não São Migrados pelo Fluxo Atual

Os campos abaixo apareciam em versões anteriores deste documento como desejáveis, mas não possuem extração ou mapeamento implementado no pipeline atual:

- data de submissão (`dc.date.submitted`), reservada ao preenchimento interno pelo DSpace;
- grau acadêmico (`dc.type.degree`);
- instituição e local de defesa (`dc.publisher` e `dc.publisher.place`);
- DOI estruturado (`dc.identifier.doi`);
- nome do periódico (`dc.relation.ispartof`);
- URL estruturada da publicação original (`dc.identifier.uri`).

Uma observação livre pode conter DOI, URL ou dados de periódico e ser classificada como `dc.identifier.citation`, mas isso não equivale a preencher os campos estruturados acima.

## 9. Arquivos de Saída e Auditoria

| Arquivo | Finalidade |
| --- | --- |
| `saf_bundle/**/item_<id>/dublin_core.xml` | Metadados que serão importados no item. |
| `saf_bundle/**/item_<id>/contents` | Lista dos bitstreams e, quando necessário, sua restrição inicial. |
| `saf_bundle/access_policies.json` | Manifesto de embargos e restrições por ID de origem. |
| `embargoed_items.csv` | Relatório legível dos itens com acesso controlado. |
| `routing_report.csv` | Curso, coleção de destino e itens sem mapeamento. |
| `pdf_extraction_issues.csv` | Anomalias de binário, nome, gravação ou conversão PDF/A. |
| `mapfile.txt` em cada coleção | Relação entre `item_<id>` e handle gerada pelo importador do DSpace. |
