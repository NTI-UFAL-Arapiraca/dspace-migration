# Tema customizado

Este diretório é sobreposto a `/app/src/themes/custom` da imagem oficial antes
da compilação. O DSpace Angular já registra o tema chamado `custom`; não é
necessário alterar `angular.json` para usar os arquivos SCSS abaixo.

Os registros mantidos um nível acima, em `frontend/themes/*.ts`, habilitam os
componentes eager e listable do tema. Eles são necessários para que overrides
de componentes e páginas entrem no bundle final, além do CSS do tema.

Arquivos mantidos inicialmente:

- `styles/_theme_sass_variable_overrides.scss`: cores, fontes e variáveis Sass;
- `styles/_theme_css_variable_overrides.scss`: variáveis CSS dos componentes;
- `styles/_global-styles.scss`: regras CSS globais adicionais;
- `assets/`: logotipos, favicons, fontes e traduções próprias. Os arquivos em
  `assets/i18n/` são mesclados aos idiomas oficiais antes do build;
- `app/item-page/simple/item-types/untyped-item/`: página usada pelos itens
  migrados, incluindo orientador e membros avaliadores abaixo dos autores.

O componente `app/home-page/home-news/home-news.component.ts` mantém a extensão
oficial registrada, mas usa um template vazio para remover da página inicial o
banner promocional padrão do DSpace.

Para substituir um componente, crie neste diretório o mesmo caminho existente
em `src/themes/custom` da versão `dspace-10.0`. Por exemplo, um cabeçalho pode
ser sobrescrito em `app/header/`. O caminho e as importações devem acompanhar a
mesma versão definida por `DSPACE_ANGULAR_TAG`.

Depois de qualquer alteração no tema, reconstrua a imagem:

```bash
docker compose -p d10 \
  -f docker-compose-dist.yml \
  -f docker-compose-rest.yml \
  up -d --build dspace-angular
```

Alterações em `frontend/config/config.prod.yml` exigem apenas a recriação do
container, pois esse arquivo é montado em tempo de execução.
