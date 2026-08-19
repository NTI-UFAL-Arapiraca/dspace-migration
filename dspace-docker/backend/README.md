# Configuração do backend DSpace

`config/submission-forms.xml` é uma cópia da configuração oficial da branch
`dspace-10_x` do repositório `DSpace/DSpace`. O arquivo é montado diretamente
em `/dspace/config/submission-forms.xml` pelos serviços REST e CLI.

Overrides mantidos pelo projeto:

- todas as definições de `dc.description.abstract` usam `repeatable=true`;
- o seletor de idioma é habilitado com `language` e
  `common_iso_languages`;
- `pt` e `en` são oferecidos para corresponder aos qualifiers dos abstracts;
- `dc.language.iso` permanece independente e recebe `pt_BR` na migração.

Ao atualizar a versão do DSpace, extraia novamente o arquivo da branch ou da
imagem correspondente, reaplique somente esses overrides e execute os testes
de `test_backend_configuration.py`.
