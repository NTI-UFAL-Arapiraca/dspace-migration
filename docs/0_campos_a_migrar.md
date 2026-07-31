### 1. Metadados Obrigatórios e Identificação (Artigos e TCCs)

| Informação no Banco de Origem | Campo Destino no DSpace | Formato / Observação |
| --- | --- | --- |
| Título Principal | `dc.title` | Texto limpo (sem caixa alta desnecessária). |
| Título Alternativo (Traduzido) | `dc.title.alternative` | Geralmente o título em inglês. |
| Nome do Autor (ou autores) | `dc.contributor.author` | Formato: `Sobrenome, Nome` (um por linha/campo). |
| Resumo na língua nativa | `dc.description.abstract` | Texto corrido (sem quebras de linha abruptas). |
| Abstract (Resumo em inglês) | `dc.description.abstract` | Configurar o idioma do metadado como `en`. |
| Palavras-chave | `dc.subject` | Separadas individualmente (uma por linha/campo). |
| Data de Publicação/Defesa | `dc.date.issued` | Padrão ISO: `AAAA-MM-DD` ou `AAAA-MM` ou `AAAA`. |
| Idioma do trabalho | `dc.language.iso` | Código de 3 letras (ex: `por`, `eng`, `spa`). |
| Tipo de Documento | `dc.type` | Termos controlados (ex: `article`, `thesis`, `dissertation`). |

### 2. Metadados Específicos para TCCs, Dissertações e Teses (Padrão BDTD/IBICT)

Se o seu DSpace for integrar com a Biblioteca Digital de Teses e Dissertações (BDTD), você precisará buscar e extrair estes campos adicionais:

| Informação no Banco de Origem | Campo Destino no DSpace | Observação |
| --- | --- | --- |
| Nome do Orientador | `dc.contributor.advisor` | Formato: `Sobrenome, Nome`. |
| Nome do Coorientador (se houver) | `dc.contributor.coadvisor` | Formato: `Sobrenome, Nome`. |
| Grau Acadêmico | `dc.type.degree` | Ex: `Graduação`, `Mestrado`, `Doutorado`. |
| Nome do Curso ou Programa | `dc.description.degree` | Ex: `Programa de Pós-Graduação em Informática`. |
| Instituição de Defesa | `dc.publisher` | Nome da sua Universidade Federal. |
| Local de Defesa | `dc.publisher.place` | Cidade e Estado da federação. |
| Membros da Banca | `dc.contributor.committee` | Avaliadores da defesa (opcional, mas recomendado). |

### 3. Metadados Específicos para Artigos Científicos

| Informação no Banco de Origem | Campo Destino no DSpace | Observação |
| --- | --- | --- |
| Identificador DOI | `dc.identifier.doi` | Apenas o link ou o código do DOI. |
| Nome da Revista / Periódico | `dc.relation.ispartof` | Ex: `Revista Brasileira de Ciência da Informação`. |
| Dados de Citação da Revista | `dc.identifier.citation` | Volume, número, paginação (ex: `v. 12, n. 2, p. 45-60`). |
| URL da publicação original | `dc.identifier.uri` | Link para o site da editora (se houver). |

### 4. Gestão de Arquivos e Direitos de Acesso

Além do texto, extraia os dados de controle do arquivo físico e regras de exibição:

| Informação no Banco de Origem | Uso na Migração | Observação |
| --- | --- | --- |
| **Caminho/Nome do Arquivo PDF** | Coluna `filename` do SAF | O nome exato do arquivo armazenado no servidor (ex: `tcc_id_5432.pdf`). |
| **Status de Acesso / Sigilo** | `dc.rights` ou políticas de restrição | Identificar se o trabalho é de *Acesso Aberto* ou se possui *Embargo* (restrito temporariamente por patentes ou publicação pendente). |

### 5. Mapeamento de Origem dos Dados (Banco de Dados Antigo)

Abaixo encontra-se a referência técnica de onde cada informação está sendo extraída no banco de dados PostgreSQL de origem (`biblioteca`).

| Informação / Metadado | Tabela de Origem | Coluna(s) de Origem | Observações |
| --- | --- | --- | --- |
| **Título Principal** | `ud_biblioteca_publicacao` | `name` | Mapeado para `dc.title` |
| **Título Alternativo** | `ud_biblioteca_publicacao` | `titulo_abstract` | Mapeado para `dc.title.alternative` |
| **Resumo (pt_BR)** | `ud_biblioteca_publicacao` | `resumo` | Mapeado para `dc.description.abstract[pt_BR]` |
| **Abstract (en)** | `ud_biblioteca_publicacao` | `abstract` | Mapeado para `dc.description.abstract[en]` |
| **Data de Publicação** | `ud_biblioteca_publicacao` | `ano_pub` | Mapeado para `dc.date.issued` |
| **Data de Defesa** | `ud_biblioteca_publicacao` | `data_defesa` | Mapeado para `dc.date.submitted` |
| **Número de Páginas** | `ud_biblioteca_publicacao` | `numero_paginas` | Mapeado para `dc.format.extent` |
| **Observações / Citações** | `ud_biblioteca_publicacao` | `observacoes` | Extraído para notas ou citações |
| **Controle de Acesso** | `ud_biblioteca_publicacao` | `data_limite_embargo`, `autorizar_publicacao` | Define se pode ser exposto publicamente |
| **Tipo de Documento** | `ud_biblioteca_publicacao_tipo` | `name` | Mapeado para `dc.type` |
| **Nome do Curso/Grau** | `ud_curso` | `name` | Mapeado para `dc.description.degree` |
| **Departamento/Campus** | `ud_campus` | `name` | Mapeado para `dc.publisher.department` |
| **Autor(es)** | `ud_biblioteca_publicacao_autor` | `ultimo_nome`, `name` | Junção N:N por `ud_biblioteca_publicacao_autores` |
| **Orientador(es)** | `ud_biblioteca_publicacao_orientador` | `ultimo_nome`, `name` | Junção N:N por `publicacao_orientador_rel` |
| **Coorientador(es)** | `ud_biblioteca_publicacao_orientador` | `ultimo_nome`, `name` | Junção N:N por `publicacao_coorientador_rel` |
| **Palavras-chave** | `ud_biblioteca_p_chave` | `name` | Junção N:N por `publicacao_p_chave_rel` |
| **Arquivo PDF (Binário)** | `ud_biblioteca_anexo` | `arquivo` | Processado por `pdfs.py` e convertido a PDF/A |
| **Nome do Arquivo PDF** | `ud_biblioteca_anexo` | `name` | Utilizado para nomear o arquivo físico |
| **Exibir PDF (Controle)** | `ud_biblioteca_anexo` | `exibir_pdf` | Define se o anexo deve ser importado |