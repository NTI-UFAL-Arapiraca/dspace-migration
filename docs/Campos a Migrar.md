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