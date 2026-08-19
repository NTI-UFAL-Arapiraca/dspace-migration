# RFCs dos overrides do DSpace

Este diretório registra cada comportamento em que o projeto sobrescreve ou
complementa o frontend ou o backend oficial do DSpace 10.x. As RFCs são a fonte
de contexto para reaplicar e revisar essas diferenças ao atualizar as imagens.

| RFC | Decisão |
| --- | --- |
| [0001](0001-build-e-ativacao-do-tema-custom.md) | Compilar e ativar o tema local sobre a imagem oficial. |
| [0002](0002-remocao-do-banner-promocional.md) | Remover o banner promocional da página inicial. |
| [0003](0003-idioma-anonimo-padrao-pt-br.md) | Usar pt-BR para visitantes anônimos sem preferência. |
| [0004](0004-metadados-academicos-na-pagina-do-item.md) | Exibir orientador e banca na página do item. |
| [0005](0005-formatacao-localizada-da-data.md) | Formatar datas no padrão brasileiro em pt-BR. |
| [0006](0006-alinhamento-justificado-do-resumo.md) | Justificar o texto do resumo. |
| [0007](0007-negociacao-de-idioma-dos-metadados.md) | Filtrar metadados públicos por idioma e preservar todos no editor. |
| [0008](0008-formulario-de-resumos-multilingues.md) | Permitir abstracts repetíveis e qualificados por idioma. |
| [0009](0009-ocultacao-de-notas-internas.md) | Ocultar provenance do público. |

Uma nova alteração por override deve incluir sua RFC neste índice no mesmo
commit. Cada RFC deve identificar arquivos, consequência operacional e testes.
