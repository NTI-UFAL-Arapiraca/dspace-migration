# RFC 0002 — Remoção do banner promocional

- Status: aceita
- Escopo: frontend

## Contexto

O componente `home-news` oficial exibe o texto promocional “DSpace is the world
leading open source repository platform...”, inadequado para a página inicial
institucional.

## Decisão

Sobrescrever somente o componente `HomeNewsComponent` no tema `custom`,
mantendo seu registro oficial e usando um template vazio. A página inicial
oficial não é copiada.

## Implementação

`dspace-docker/frontend/themes/custom/app/home-page/home-news/home-news.component.ts`.

## Consequências e validação

Outras seções da home continuam herdadas do DSpace. O teste
`test_custom_theme_suppresses_stock_home_news_banner` garante o template vazio
e impede a reintrodução do texto promocional.
