#!/bin/bash

# ==============================================================================
# Script de Registro de Campos Customizados do Dublin Core no DSpace
# ==============================================================================
# Este script registra exclusivamente os campos de metadados ausentes por 
# padrão no esquemas Dublin Core ('dc') do DSpace, necessários para a migração.
#
# Uso:
#   chmod +x register_custom_fields.sh
#   ./register_custom_fields.sh [NOME_CONTAINER_POSTGRES]
#
# Exemplo:
#   ./register_custom_fields.sh dspacedb
# ==============================================================================

CONTAINER_NAME="${1:-dspacedb}"
DB_USER="${DB_USER:-dspace}"
DB_NAME="${DB_NAME:-dspace}"

echo "======================================================================"
echo " Registrando metadados customizados no DSpace (Container: $CONTAINER_NAME)"
echo "======================================================================"

docker exec -i "$CONTAINER_NAME" psql -U "$DB_USER" -d "$DB_NAME" << 'EOF'
INSERT INTO metadatafieldregistry (metadata_schema_id, element, qualifier, scope_note)
SELECT 
    (SELECT metadata_schema_id FROM metadataschemaregistry WHERE short_id = 'dc'),
    elem.element,
    elem.qualifier,
    elem.scope_note
FROM (
    VALUES 
        ('publisher', 'department', 'Departamento, Campus ou Centro de Ensino responsável pela publicação/defesa.'),
        ('contributor', 'coadvisor', 'Nome do Coorientador do trabalho acadêmico (Formato: Sobrenome, Nome).'),
        ('contributor', 'committee', 'Membros da Banca Examinadora e avaliadores de defesa do trabalho.'),
        ('description', 'note', 'Notas sobre localização de acervo físico, observações internas ou notas gerais.'),
        ('publisher', 'place', 'Localidade (Cidade e Estado da Federação) da defesa ou publicação.'),
        ('type', 'degree', 'Nível ou tipo do grau acadêmico obtido (ex: Graduação, Mestrado, Doutorado).')
) AS elem(element, qualifier, scope_note)
WHERE NOT EXISTS (
    SELECT 1 
    FROM metadatafieldregistry mfr
    JOIN metadataschemaregistry msr ON mfr.metadata_schema_id = msr.metadata_schema_id
    WHERE msr.short_id = 'dc' 
      AND mfr.element = elem.element 
      AND (
          mfr.qualifier = elem.qualifier 
          OR (mfr.qualifier IS NULL AND elem.qualifier IS NULL)
      )
);
EOF

if [ $? -eq 0 ]; then
    echo "✔ Execução concluída com sucesso! Campos cadastrados/verificados."
else
    echo "✘ Erro ao registrar campos de metadados no banco do DSpace."
    exit 1
fi
