SELECT
    -- ID original (essencial para eu vincular o metadado ao arquivo PDF binário depois)
    p.id AS "id_origem",

    -- Metadados básicos de identificação
    p.name AS "dc.title",
    p.titulo_abstract AS "dc.title.alternative",
    p.resumo AS "dc.description.abstract[pt_BR]",
    p.abstract AS "dc.description.abstract[en]",
    p.ano_pub AS "dc.date.issued",
    p.data_defesa AS "dc.date.submitted",
    p.numero_paginas AS "dc.format.extent",

    -- Separação estratégica: Observações Gerais vs Citações/Fontes externas
    p.observacoes AS "dc.description.note",
    p.observacoes AS "dc.identifier.citation", -- Vou filtrar e isolar as citações textuais por aqui

    -- Controle Crítico de Acesso (Crucial para eu configurar o bloqueio automatizado do PDF)
    p.data_limite_embargo AS "data_limite_embargo",
    p.autorizar_publicacao AS "autorizar_publicacao",

    -- Metadados de estrutura acadêmica (1:N)
    t.name AS "dc.type",
    c.name AS "dc.description.degree",
    camp.name AS "dc.publisher.department",
    -- Nome cru do curso para roteamento (NÃO incluído no dublin_core.xml)
    c.name AS "curso_nome",

    -- Relacionamentos Muitos-para-Muitos (N:N) agrupados com separador '||'
    (
        SELECT string_agg(CONCAT(aut.ultimo_nome, ', ', aut.name), '||')
        FROM ud_biblioteca_publicacao_autores pa
        JOIN ud_biblioteca_publicacao_autor aut ON aut.id = pa.autor_id
        WHERE pa.pub_id = p.id
    ) AS "dc.contributor.author",
    (
        SELECT string_agg(CONCAT(ori.ultimo_nome, ', ', ori.name), '||')
        FROM publicacao_orientador_rel por
        JOIN ud_biblioteca_publicacao_orientador ori ON ori.id = por.ud_biblioteca_publicacao_orientador_id
        WHERE por.ud_biblioteca_publicacao_id = p.id
    ) AS "dc.contributor.advisor",
    (
        SELECT string_agg(CONCAT(coori.ultimo_nome, ', ', coori.name), '||')
        FROM publicacao_coorientador_rel pco
        JOIN ud_biblioteca_publicacao_orientador coori ON coori.id = pco.ud_biblioteca_publicacao_orientador_id
        WHERE pco.ud_biblioteca_publicacao_id = p.id
    ) AS "dc.contributor.coadvisor",
    (
        SELECT string_agg(
            CONCAT(banca.ultimo_nome, ', ', banca.name),
            '||' ORDER BY banca.ultimo_nome, banca.name, banca.id
        )
        FROM publicacao_membro_banca_rel pmb
        JOIN ud_biblioteca_publicacao_orientador banca
          ON banca.id = pmb.ud_biblioteca_publicacao_orientador_id
        WHERE pmb.ud_biblioteca_publicacao_id = p.id
    ) AS "dc.contributor.referee",
    (
        SELECT string_agg(pc.name, '||')
        FROM publicacao_p_chave_rel pcr
        JOIN ud_biblioteca_p_chave pc ON pc.id = pcr.ud_biblioteca_p_chave_id
        WHERE pcr.ud_biblioteca_publicacao_id = p.id
    ) AS "dc.subject"

FROM ud_biblioteca_publicacao p
LEFT JOIN ud_biblioteca_publicacao_tipo t ON t.id = p.tipo_id
LEFT JOIN ud_curso c ON c.id = p.curso_id
LEFT JOIN ud_campus camp ON camp.id = p.campus_id

-- Removi o filtro restrito do WHERE para garantir que capturemos TODOS os registros.
-- Eu farei a triagem programática com base nas colunas "autorizar_publicacao" e "data_limite_embargo".
WHERE p.name IS NOT NULL
ORDER BY p.id;
