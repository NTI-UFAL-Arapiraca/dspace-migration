# Extração e formato SAF

As consultas de metadados e anexos usam o PostgreSQL legado. A extração
produz arquivos locais; o DSpace é acessado nas etapas seguintes.

## Metadados

O comando `extract-metadata` é responsável por:
- Conectar ao banco de dados PostgreSQL.
- Executar a consulta presente em `sql/extract_metadata.sql`.
- Limpar tags HTML dos textos.
- Padronizar datas para o formato ISO.
- **Rotear cada publicação** para a coleção correta com base no mapeamento de cursos (`dspace-organization/map.json`).
- Criar a estrutura de diretórios do pacote SAF **hierárquica por polo e coleção**: `saf_bundle/<polo>/<coleção>/item_[id]/`.
- Gerar o arquivo `dublin_core.xml` para cada item com base nos metadados extraídos.
- Preencher `dc.language.iso` com `pt_BR` em todos os itens.
- Identificar embargos ativos pela coluna `data_limite_embargo` e restrições sem prazo.
- Gerar `access_policies.json` na raiz do bundle para conservar as datas de liberação.


Curso e campus ficam em `metadata_local.xml`; os campos `dc` ficam em
`dublin_core.xml`. O manifesto `people.json` conserva identidades e papéis.
`dc.language.iso` usa `pt_BR`; os resumos usam qualifiers `pt` e `en`.

## Arquivos e acesso

`extract-pdfs` busca anexos `bytea` em lotes definidos por `BATCH_SIZE`,
converte PDFs com Ghostscript e atualiza o arquivo `contents`. Múltiplos
anexos são preservados. Falhas ficam em `pdf_extraction_issues.csv`.

Embargos futuros e restrições entram com leitura somente por Administrator.
`access_policies.json` conserva as datas para liberação posterior. Uma data
igual ou anterior à extração é considerada vencida. A nota de restrição em
metadados não substitui a política do bitstream.

Itens sem mapeamento de curso ficam em `_unmapped/` e em `routing_report.csv`.
Barras nos nomes de coleção viram `%2F` apenas nos diretórios SAF.
Os diretórios dos itens são localizados recursivamente.

## Estrutura gerada


Ao final desta etapa, você terá um diretório `saf_bundle/` (ou o nome configurado no `.env`) com a seguinte estrutura hierárquica:

```
saf_bundle/
├── people.json
├── access_policies.json
├── Arapiraca/
│   ├── Administração/
│   │   ├── item_123/
│   │   │   ├── dublin_core.xml
│   │   │   ├── metadata_local.xml
│   │   │   ├── contents
│   │   │   └── tcc_fulano.pdf
│   │   └── item_456/
│   │       └── ...
│   ├── Ciência da Computação/
│   │   └── ...
│   └── Outros/
│       └── Documentos (BSCA)/
│           └── ...
├── Penedo/
│   └── ...
├── Viçosa/
│   └── ...
├── Palmeira dos Índios/
│   └── ...
└── _unmapped/
    └── item_999/
        └── ...
```

Os comandos estão na [importação por etapas](../guias/importacao-por-etapas.md).

## Processamento de mídia no destino

A importação SAF não gera miniaturas automaticamente. `filter-media` pode
produzir thumbnails e texto indexável depois da aplicação dos embargos.
A opção `-v` detalha os arquivos; `-f` reprocessa os existentes; `-p` seleciona
um filtro, como `ImageMagick PDF Thumbnail`, quando configurado no DSpace.
