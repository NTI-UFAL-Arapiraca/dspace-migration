# RFC 0014 — Ano de publicação e data de defesa

- Status: aceita
- Escopo: extração SAF e metadados de item

## Contexto

A migração gravava `data_defesa` como `dc.date.issued`, embora a origem também
possua `ano_pub`. A página e o catálogo passavam a tratar a data da defesa como
se fosse data de publicação.

## Decisão

A migração grava `ano_pub` em `dc.date.issued`, preservando apenas a precisão
do ano, e `data_defesa` em `local.date.defense`. O SAF guarda o campo local em
`metadata_local.xml`. A data de submissão e as datas internas do DSpace não são
usadas para esses valores.

## Implementação

A consulta, a serialização de metadados, o registro idempotente do campo e a
documentação do mapeamento acompanham essa decisão. O campo `local.date.defense`
deve existir no registro de metadados do DSpace antes da importação.

## Consequências operacionais

Pacotes SAF novos passam a conter os dois campos separados. A importação SAF é
aditiva; repetir a importação em um repositório que já recebeu os itens pode
criar duplicatas. Itens existentes exigem atualização de metadados in-place.
