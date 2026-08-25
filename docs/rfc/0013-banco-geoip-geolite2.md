# RFC 0013 — Banco GeoIP GeoLite2 City

- Status: aceita
- Escopo: backend e operação

## Contexto

O indicador GeoIP do DSpace reportava que a configuração obrigatória `dbfile`
estava ausente. No DSpace 10, a propriedade completa é
`usage-statistics.dbfile` e o formato atual suportado é MaxMind DB (`.mmdb`),
não o arquivo legado `GeoLiteCity.dat`. Sem um banco válido, eventos novos de
uso não recebem localização geográfica e podem deixar de ser contabilizados em
alguns fluxos de estatísticas.

## Decisão

- exigir `GEOLITE2_CITY_DB_PATH` no `.env` como caminho absoluto no host;
- montar o arquivo em `/dspace/config/GeoLite2-City.mmdb`, somente para leitura;
- configurar `usage-statistics.dbfile` com esse caminho interno;
- não copiar nem versionar o banco GeoLite2 no repositório;
- atribuir ao operador a atualização periódica do arquivo conforme os termos
  de distribuição da MaxMind.

## Implementação

- `dspace-docker/docker-compose-rest.yml` define a propriedade e o bind mount;
- `.env.example` documenta a variável obrigatória;
- `docs/4_operacao_manutencao.md` descreve atualização e diagnóstico;
- testes estruturais impedem a remoção acidental da configuração.

## Consequências e validação

O backend não inicia pelo Compose se a variável estiver ausente ou se o caminho
não apontar para um arquivo existente, evitando que o Docker crie silenciosamente
um diretório no lugar do banco. Após recriar o backend, o arquivo deve aparecer
como legível e somente leitura no container, `usage-statistics.dbfile` deve
resolver para o caminho interno e o componente GeoIP de `/health` deve ficar
`UP`. A substituição do arquivo no host exige a recriação do backend para
reabrir o banco e aplicar a versão nova.
