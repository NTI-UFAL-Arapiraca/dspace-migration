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
o container. Siga o [guia completo do DSpace acadêmico](../../dspace-bca/docs/guia-dspace-academico.md),
com conceitos, preparação e comandos para cada ambiente.

Depois de iniciar o backend e conferir as credenciais no `.env` da migração,
execute em `dspace-bca`:

```bash
# Desenvolvimento isolado
bash scripts/prepare-academic.sh --development --project-name d10dev \
  --env-file .env.development --migration-env-file ../dspace-migration/.env
```

```bash
# Produção
bash scripts/prepare-academic.sh --project-name d10 \
  --env-file .env --migration-env-file ../dspace-migration/.env
```

O script registra os seis campos, inicializa os tipos e cria/reutiliza a
coleção Person. Salva `DSPACE_PERSON_COLLECTION_UUID` no `.env` informado.
Se o UUID já estiver preenchido, respeita sua seleção e valida o tipo da
coleção. As credenciais são do administrador da importação; nenhuma conta
é criada para os autores. Reinicie o backend após criar a coleção e
reindexe Discovery depois dos vínculos, conforme o guia.

Essa configuração requer um destino escolhido para Authority Framework.
Se já houver relações tradicionais com metadados virtuais, valide o plano
antes de alterar o modelo: o DSpace 10 não fornece conversão automática de
ida e volta.
[Limitação documentada pelos mantenedores](https://github.com/DSpace/DSpace/issues/12120).

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

Depois de gerar os pacotes e concluir sua importação SAF:

```bash
uv run apply-people --dry-run
uv run apply-people
```

Para selecionar explicitamente um lote/destino:

```bash
uv run apply-people --saf-bundle-dir /caminho/saf --collection-uuid UUID_DA_COLECAO
```

O `uv run migrate` executa essa etapa depois dos embargos e antes das
estatísticas, OAI e sitemaps. `--skip-people` permite adiar somente o
enriquecimento. Ao retomá-lo, execute `apply-people`, sem repetir a importação
SAF que adiciona os trabalhos. `--skip-docker` mantém o comportamento anterior
de regenerar a extração; use a mesma origem e confira o lote/mapfiles.

O comando primeiro valida os trabalhos do manifesto contra os mapfiles e
os valores existentes na API. Em seguida, recupera pessoas pelo
`local.identifier.legacy` usando a listagem administrativa baseada no banco,
sem depender da atualização imediata do Solr. Pessoas novas recebem nome,
tipo e identificador de origem; nenhuma conta, senha, e-mail ou data de
nascimento é criada.
[Criação administrativa de itens](https://raw.githubusercontent.com/DSpace/RestContract/main/items.md).

O arquivo `people-map.json`, dentro do SAF, registra o destino e os UUIDs.
É gravado atomicamente após cada pessoa criada. Uma falha entre a criação e
o checkpoint pode ser recuperada pela identidade persistida na API. Uma
segunda execução reutiliza pessoas e não repete vínculos já aceitos.
A simulação não cria pessoas, vínculos, mapas nem arquivo de lock; a
contagem de pessoas novas significa “seriam criadas”.

O enriquecimento preserva a ordem dos valores existentes, seus idiomas e
os demais metadados. Divergências de nomes, autoridades conflitantes,
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
As definições antigas no registro não são excluídas, e UUIDs, handles,
arquivos e políticas de acesso dos trabalhos são preservados.
[Operações oficiais de metadados por PATCH](https://raw.githubusercontent.com/DSpace/RestContract/main/metadata-patch.md).

Os testes automatizados usam origem e API simuladas para verificar
identidade, retomada, conflitos, simulação e preservação de traduções. Antes
do lote definitivo, valide um lote pequeno contra o backend 10.1 preparado,
incluindo a seleção de orientadores e suas listas na interface pública.
