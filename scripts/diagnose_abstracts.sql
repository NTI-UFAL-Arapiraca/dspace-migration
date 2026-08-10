-- =============================================================
-- DIAGNÓSTICO: Resumos com problemas de migração
-- =============================================================

-- 1. Quantos resumo pt_BR viram vazio após remover HTML?
SELECT 
  COUNT(*) AS total_com_resumo,
  COUNT(CASE 
    WHEN TRIM(REGEXP_REPLACE(resumo, '<[^>]+>|&nbsp;|\s+', ' ', 'g')) = '' 
    THEN 1 
  END) AS resumo_so_html_vazio,
  COUNT(CASE 
    WHEN TRIM(REGEXP_REPLACE(resumo, '<[^>]+>|&nbsp;|\s+', ' ', 'g')) != '' 
    THEN 1 
  END) AS resumo_com_conteudo_real
FROM ud_biblioteca_publicacao
WHERE resumo IS NOT NULL;

-- 2. Exemplos de resumo que são só HTML (virariam vazios após limpeza)
SELECT id, name, resumo
FROM ud_biblioteca_publicacao
WHERE resumo IS NOT NULL
  AND TRIM(REGEXP_REPLACE(resumo, '<[^>]+>|&nbsp;|\s+', ' ', 'g')) = ''
LIMIT 10;

-- 3. Casos onde resumo = abstract (conteúdo idêntico, provável duplicata)
SELECT COUNT(*) AS resumo_igual_abstract
FROM ud_biblioteca_publicacao
WHERE resumo IS NOT NULL 
  AND abstract IS NOT NULL
  AND TRIM(resumo) = TRIM(abstract);

-- 4. Amostra de registros com ambos preenchidos e diferentes
SELECT 
  id,
  name,
  LEFT(resumo, 120)    AS resumo_inicio,
  LEFT(abstract, 120)  AS abstract_inicio
FROM ud_biblioteca_publicacao
WHERE resumo IS NOT NULL 
  AND abstract IS NOT NULL
  AND TRIM(resumo) != TRIM(abstract)
  AND TRIM(REGEXP_REPLACE(resumo, '<[^>]+>|&nbsp;|\s+', ' ', 'g')) != ''
LIMIT 5;
