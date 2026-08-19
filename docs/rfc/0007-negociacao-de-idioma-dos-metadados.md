# RFC 0007 — Negociação de idioma dos metadados

- Status: aceita
- Escopo: frontend, backend e migração

## Contexto

O público deve receber somente o abstract correspondente ao idioma da página,
inclusive nos cards da home e resultados de busca. O editor administrativo,
por outro lado, precisa carregar todas as traduções para não ocultar nem perder
valores durante um PATCH.

No DSpace 10, o filtro REST usa `Locale.getLanguage()`: a locale `pt_BR` é
comparada como `pt`. Qualifiers gravados como `pt_BR` não são selecionados e
podem provocar fallback para inglês.

## Decisão

- gravar o qualifier do abstract brasileiro como `pt`;
- manter `dc.language.iso=pt_BR`, pois ele descreve o documento, não o idioma
  do valor de metadado;
- configurar `default.locale=pt_BR` e `webui.supported.locales=pt_BR, en`;
- deixar páginas públicas e buscas usarem `Accept-Language` e a projeção REST
  padrão;
- solicitar `allLanguages` apenas no resolver do editor administrativo e na
  resposta de PATCH desse editor.

## Implementação

- `sql/extract_metadata.sql` e `src/dspace_migration/metadata.py`;
- `dspace-docker/docker-compose-rest.yml`;
- `frontend/overrides/edit-item-all-languages.resolver.ts`;
- `frontend/patches/apply-item-all-languages.mjs`;
- `backend/sql/normalize_abstract_languages.sql` para acervos existentes.

## Consequências e validação

O backend envia menos dados e o mesmo filtro atende página individual, home e
busca. Idiomas sem tradução caem no locale padrão do backend. A conversão SQL é
idempotente e exige `index-discovery -b`. Testes validam SAF, configuração,
escopo do SQL e exclusividade de `allLanguages`; o build Angular valida o patch
contra o fonte oficial 10.x.
