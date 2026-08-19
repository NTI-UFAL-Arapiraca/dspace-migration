# RFC 0003 — Idioma anônimo padrão pt-BR

- Status: aceita
- Escopo: frontend

## Contexto

O fallback sozinho não era suficiente para todos os fluxos de inicialização.
Sem o cookie `dsLanguage`, o `LocaleService` oficial consulta o idioma do
navegador antes do fallback. Assim, uma guia anônima com `Accept-Language: en`
abria em inglês e a primeira chamada REST também solicitava metadados em inglês.

## Decisão

Definir `fallbackLanguage: pt-BR` e alterar a seleção inicial do
`LocaleService`: quando não existir cookie `dsLanguage`, usar diretamente o
fallback do repositório, sem inferir o idioma pelo `Accept-Language` do
navegador. Uma escolha explícita no seletor continua sendo persistida no cookie
e tem precedência nas visitas seguintes.

## Implementação

- `dspace-docker/frontend/config/config.prod.yml`;
- `dspace-docker/frontend/patches/apply-default-anonymous-language.mjs`;
- `dspace-docker/Dockerfile.angular`.

## Consequências e validação

A primeira visita fica em português do Brasil mesmo quando o navegador anuncia
inglês. A decisão ocorre antes da resolução das páginas e das chamadas REST, de
modo que a interface e os metadados já chegam em `pt-BR`. O teste
`test_anonymous_visitors_default_to_brazilian_portuguese` valida a configuração,
o patch com guarda de compatibilidade e a remoção do workaround tardio no header;
o teste ponta a ponta deve enviar `Accept-Language: en` sem cookie e ainda obter
`<html lang="pt-BR">`.
