-- Consulta SQL para extração de metadados das publicações do banco de dados legado (Odoo / PostgreSQL)
-- Tabela principal: ud_biblioteca_publicacao

SELECT 
    p.id AS id_origem,
    p.titulo AS "dc.title",
    p.titulo_alternativo AS "dc.title.alternative",
    p.autor AS "dc.contributor.author",
    p.resumo_pt AS "dc.description.abstract[pt_BR]",
    p.resumo_en AS "dc.description.abstract[en]",
    p.palavras_chave AS "dc.subject",
    p.data_emissao AS "dc.date.issued",
    p.idioma AS "dc.language.iso",
    p.tipo AS "dc.type",
    p.orientador AS "dc.contributor.advisor",
    p.coorientador AS "dc.contributor.coadvisor",
    p.grau_academico AS "dc.type.degree",
    p.curso AS "dc.description.degree",
    p.instituicao AS "dc.publisher",
    p.local_defesa AS "dc.publisher.place",
    p.banca AS "dc.contributor.committee",
    p.doi AS "dc.identifier.doi",
    p.revista AS "dc.relation.ispartof",
    p.citacao AS "dc.identifier.citation",
    p.url_original AS "dc.identifier.uri",
    p.observacao AS "dc.description.note",
    p.data_limite_embargo
FROM ud_biblioteca_publicacao p
ORDER BY p.id;
