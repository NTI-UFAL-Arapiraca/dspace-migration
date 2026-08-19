# RFC 0001 — Build e ativação do tema custom

- Status: aceita
- Escopo: frontend

## Contexto

A imagem `dspace-angular:*‑dist` não permite compilar componentes e estilos
locais. Manter um fork completo do Angular aumentaria o custo de atualização.

## Decisão

Compilar sobre `dspace/dspace-angular:dspace-10_x`, copiando apenas o overlay
`frontend/themes/`, e reutilizar `dspace-10_x-dist` como runtime. O tema
`custom` é o primeiro tema da configuração de produção. Os registros eager e
listable incluem componentes do tema custom e do tema oficial.

## Implementação

- `dspace-docker/Dockerfile.angular`;
- `dspace-docker/docker-compose-dist.yml`;
- `dspace-docker/frontend/config/config.prod.yml`;
- `dspace-docker/frontend/themes/eager-themes-components.ts`;
- `dspace-docker/frontend/themes/themes-listable-components.ts`.

Os catálogos i18n locais são mesclados antes do build para participarem dos
hashes de produção.

## Consequências e validação

Mudanças de código ou SCSS exigem rebuild do frontend; alterações apenas no
YAML runtime exigem recriação do container. O build contém verificações exatas
contra o fonte 10.x e os testes em `test_frontend_customization.py` validam
tema, registries e ordem da compilação.
