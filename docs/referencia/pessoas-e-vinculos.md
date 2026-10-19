# Pessoas e vínculos bibliográficos

A migração preserva pessoas bibliográficas e suas participações, sem criar
contas de acesso. Um registro `Person` pode ser reutilizado por vários
trabalhos e papéis. `EPerson` continua reservado aos usuários que precisam
entrar no sistema.

Esta etapa usa o Authority Framework do DSpace 10.1: o texto do metadado
continua legível e seu atributo `authority` recebe o UUID da pessoa. A
confiança fica em `600` (`CF_ACCEPTED`). Autoria, orientação, coorientação e
banca mantêm campos separados. A API é utilizada somente ao executar
`apply-people` ou a etapa correspondente de `migrate`.
[Authority Framework oficial](https://wiki.lyrasis.org/spaces/DSDOC10x/pages/425331229/Authority%2Bframework%2Bfunctionalities).

A implantação `dspace-bca` já contém os plugins configurados, seus mounts,
os formulários e os perfis de pessoas. Não copie o arquivo de exemplo para
o container. Os procedimentos estão na [preparação acadêmica](../../../dspace-bca/docs/guias/preparacao-academica.md)
e nos [roteiros de migração](../README.md).

## Identidade na origem

O SQL exporta `pessoas` como JSON estruturado contendo tabela, ID, nome e
sobrenome para cada papel. O mesmo conjunto gera o texto SAF e o manifesto
`saf_bundle/people.json`. Assim, não se tenta reconstruir identidade a partir
de uma lista de nomes agregados.

Os identificadores têm a forma `odoo:TABELA:ID`. Autores vêm de
`ud_biblioteca_publicacao_autor`; orientadores, coorientadores e avaliadores
vêm de `ud_biblioteca_publicacao_orientador`. O ID 7 de uma tabela é diferente
do ID 7 da outra. A mesma pessoa da tabela de orientadores é reutilizada em
orientação e banca. Não há fusão automática por nome.

Quando a curadoria confirmar que dois cadastros legados representam uma
única pessoa, é possível manter os dois valores `local.identifier.legacy`
na mesma entidade `Person`, antes de executar o enriquecimento. A listagem
administrativa reconhece todos os identificadores. Não edite apenas o
`people-map.json`: o identificador persistido no DSpace é a referência para
recuperar execuções interrompidas.

## Aplicação, checkpoints e conflitos

O comando primeiro valida os trabalhos do manifesto contra os mapfiles e
os valores existentes na API. Em seguida, recupera pessoas pelo
`local.identifier.legacy` usando a listagem administrativa baseada no banco,
sem depender da atualização imediata do Solr. Pessoas novas recebem nome,
tipo e identificador de origem. E-mail, currículo Lattes e titulação são
incluídos quando disponíveis e válidos. Nenhuma conta, senha ou data de
nascimento é criada.
[Criação administrativa de itens](https://raw.githubusercontent.com/DSpace/RestContract/main/items.md).

O arquivo `people-map.json`, dentro do SAF, registra o destino e os UUIDs.
É gravado atomicamente após cada pessoa criada. Uma falha entre a criação e
o checkpoint pode ser recuperada pela identidade persistida na API. Uma
segunda execução reutiliza pessoas e não repete vínculos já aceitos.
A simulação não cria pessoas, vínculos, mapas nem arquivo de lock; a
contagem de pessoas novas significa “seriam criadas”.

## Conteúdo dos perfis e atualização de lotes

O manifesto versão 1 aceita os campos opcionais `email`, `lattes` e `degree`
em cada pessoa; manifestos antigos continuam válidos. E-mail vem de `contato`
no cadastro da própria pessoa. Lattes e titulação vêm da tabela de
orientadores, também usada para coorientação e banca. O texto da titulação
é preservado em `local.person.degree`; a interface traduz abreviações como
Dr., Dr.ª, Me., Ma. e Esp. para descrições por extenso.

E-mails são limpos e têm o domínio normalizado. Lattes aceita URL do domínio
`lattes.cnpq.br` ou identificador de 16 dígitos e gera URL HTTPS canônica em
`person.identifier.lattes`. Formatos inválidos são omitidos e contabilizados
em `profile_issues`, sem copiar o conteúdo inválido para mensagens. O campo
de e-mail é `person.email`. A preparação acadêmica registra os campos novos.

`apply-people` também enriquece Person existentes. Preserva campos vazios na
origem e valores adicionais da curadoria; um campo já preenchido com valor
divergente interrompe a pré-validação, antes das escritas.

Para um SAF já importado, preserve pacotes, mapas e checkpoint e execute:

```bash
uv run apply-people --refresh-profiles --dry-run
uv run apply-people --refresh-profiles
```

A opção consulta a origem em transação somente de leitura, reextrai apenas
as publicações do manifesto e exige as mesmas identidades, nomes e
participações. Atualiza somente `people.json` e os perfis/vínculos previstos;
não regenera o SAF. Sem a opção, o comando usa o manifesto existente e não
acessa o banco de origem. A simulação não grava o manifesto atualizado.

Resumo das participações, temas, cursos e campus no perfil são derivados
do Discovery e dos metadados dos trabalhos. Não são copiados para a Person.
O total de trabalhos usa OR entre os quatro papéis, evitando dupla contagem
quando a mesma pessoa participa do mesmo trabalho em mais de um papel.

O enriquecimento preserva a ordem dos valores existentes, seus idiomas e
os demais metadados. Cada participação é atualizada com `replace` em
`/metadata/CAMPO/ÍNDICE`, enviando um objeto completo e verificando o campo
retornado. No DSpace 10.1, `add` insere um valor sem substituir o anterior,
e os PATCHes com arrays utilizam somente o primeiro elemento; por isso não
se envia a lista inteira de participações para o campo.
Divergências de nomes, autoridades conflitantes,
identificadores duplicados, homônimos ambíguos no mesmo campo ou trabalhos
sem handle interrompem a execução para revisão. Um lote já aplicado pode
ser retomado; não há transação única envolvendo todo o acervo.

Execute apenas um escritor por destino. Um lock impede duas aplicações
simultâneas sobre o mesmo diretório SAF, mas não coordena executores em
máquinas ou diretórios diferentes. Preserve o SAF e os mapfiles como parte
do registro da migração.

Para os campos acadêmicos, novas extrações produzem `local.course.name` e
`local.campus.name` em `metadata_local.xml`; `dublin_core.xml` permanece no
esquema `dc`. Programa de pós-graduação e grau acadêmico não são inferidos
do nome do curso.

Em trabalhos anteriormente importados, `apply-people` também copia
`dc.description.degree` para `local.course.name` e
`dc.publisher.department` para `local.campus.name`, preservando idiomas e
autoridades. Confirma a gravação antes de remover o campo antigo. Se ambos
existirem com conteúdos diferentes, a operação para, sem escolher um deles.
Uma cópia interrompida pode ser retomada quando o destino contém um prefixo
idêntico dos valores da origem; os demais valores são copiados individualmente.
As definições antigas no registro não são excluídas, e UUIDs, handles,
arquivos e políticas de acesso dos trabalhos são preservados.
[Operações oficiais de metadados por PATCH](https://raw.githubusercontent.com/DSpace/RestContract/main/metadata-patch.md).

Os testes automatizados usam origem e API simuladas para verificar
identidade, retomada, conflitos, simulação e preservação de traduções. Antes
do lote definitivo, valide um lote pequeno contra o backend 10.1 preparado,
incluindo a seleção de orientadores e suas listas na interface pública.
