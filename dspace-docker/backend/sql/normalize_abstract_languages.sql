BEGIN;

-- DSpace 10 filters metadata using Locale.getLanguage(), which turns pt_BR
-- into pt. Normalize only the language qualifier of Portuguese abstracts;
-- dc.language.iso and every other metadata field remain unchanged.
UPDATE metadatavalue AS value
SET text_lang = 'pt'
FROM metadatafieldregistry AS field
JOIN metadataschemaregistry AS schema
  ON schema.metadata_schema_id = field.metadata_schema_id
WHERE value.metadata_field_id = field.metadata_field_id
  AND schema.short_id = 'dc'
  AND field.element = 'description'
  AND field.qualifier = 'abstract'
  AND value.text_lang = 'pt_BR';

COMMIT;
